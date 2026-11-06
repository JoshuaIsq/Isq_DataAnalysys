from pathlib import Path
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QFrame, QSizePolicy,
                               QPushButton, QDoubleSpinBox, QLabel, QFileDialog, QMessageBox,)
from isq_dataanalysys.interface.base import Tela
from isq_dataanalysys.leitores.acelerometria import (
    EIXOS, EIXO_DESCONHECIDO, ler_lynx_acelerometria,
)
from isq_dataanalysys.leitores.lynx import LinhaFinalIncompleta, aviso_unidades
from isq_dataanalysys.processamento.sinais import Processamento
from isq_dataanalysys.processamento.integracao import integrar_relativo
from isq_dataanalysys.interface.integracao import TelaIntegracao, mostrar_resultado
from isq_dataanalysys.interface.passa_banda import DialogoPassaBanda
from isq_dataanalysys import __version__ as VERSAO
from isq_dataanalysys.leitores.metadados import ler_inicio_lynx
from isq_dataanalysys.interface.eixo_temporal import EixoDataHora, configurar_eixo_temporal


class TelaLynxAcelerometria(Tela):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Análise de dados - Lynx Acelerometria — v{VERSAO}")
        self.rotulo_versao = QLabel(f"v{VERSAO}")
        self.rotulo_versao.setToolTip(f"Código em execução: {Path(__file__).resolve()}")
        self.statusBar().addPermanentWidget(self.rotulo_versao)
        self.checkboxes_eixos = {}
        self.curvas_lynx = {}
        self.grupos_eixos = []
        self.recriar_sensores([])
        self.tempo = None
        self.df_original = None
        self.df_sensores = None
        self.sensores_lynx = []
        self.caminho_atual = None
        self.inicio_arquivo = None
        self.info_processamento = {}
        self.info_arquivo = {}
        self.info_rms = None
        self.info_fft = None
        self.abrir.clicked.connect(self.carregar_arquivo_lynx)
        self.criar_controle_passa_banda()
        self.criar_controles_rms()
        self.janelas_resultados = []
        self.criar_controles_integracao()
        self.rotulo_importacao = QLabel()
        self.rotulo_importacao.setWordWrap(True)
        self.rotulo_importacao.setStyleSheet("color: #6b4e16; background: #fff4dc; padding: 4px;")
        self.rotulo_importacao.hide()
        self.layout_controles.addWidget(self.rotulo_importacao, 6, 0, 1, 4)

    def criar_controle_passa_banda(self):
        # Mantém os controles dentro da largura de 1330 px usada pela tela.
        self.layout_controles.setHorizontalSpacing(16)
        self.botao_passa_banda = QPushButton("Passa-banda…")
        self.botao_passa_banda.setObjectName("passa_banda")
        self.botao_passa_banda.setEnabled(False)
        self.botao_passa_banda.setToolTip(
            "Define Low cutoff e High cutoff em Hz para os canais carregados. "
            "Passa-alta e passa-baixa só atuam se você também os aplicar."
        )
        self.layout_controles.addWidget(self.botao_passa_banda, 2, 2)
        self.botao_passa_banda.clicked.connect(self.abrir_passa_banda)

    def abrir_passa_banda(self):
        if self.df_original is None:
            return
        dialogo = DialogoPassaBanda(
            self.info_processamento["fs"],
            self.config_filtros.get("passa_banda"),
            parent=self,
        )

        def aplicar(desativar=False):
            proposta = self.config_filtros.copy()
            if desativar:
                proposta.pop("passa_banda", None)
            else:
                proposta["passa_banda"] = dialogo.cortes()
            # Só fecha após um cálculo válido. Um erro preserva dados e configuração.
            if self.aplicar_configuracao(proposta):
                dialogo.accept()

        dialogo.botao_aplicar.clicked.connect(lambda: aplicar())
        dialogo.botao_desativar.clicked.connect(lambda: aplicar(desativar=True))
        dialogo.exec()
        dialogo.deleteLater()

    def atualizar_indicacao_filtros(self):
        super().atualizar_indicacao_filtros()
        cortes = self.config_filtros.get("passa_banda")
        if cortes is None:
            self.botao_passa_banda.setText("Passa-banda…")
            return
        inferior, superior = cortes
        descricao = f"Passa-banda: {inferior:g}–{superior:g} Hz"
        self.botao_passa_banda.setText(descricao)
        texto = self.rotulo_ativos.text()
        if texto == "Tratamentos ativos: nenhum":
            texto = "Tratamentos ativos: " + descricao
        else:
            texto += "; " + descricao
        self.rotulo_ativos.setText(texto)

    def criar_controles_integracao(self):
        painel = QFrame()
        painel.setObjectName("painel_integracao")
        painel.setStyleSheet(
            "QFrame#painel_integracao {background: #eef5ff; border-radius: 4px;}"
            "QLabel {color: #26364a;}"
        )
        linha = QHBoxLayout(painel)
        linha.setContentsMargins(8, 6, 8, 6)
        self.botao_velocidade = QPushButton("Gerar velocidade")
        self.botao_velocidade.setObjectName("gerar_velocidade")
        self.botao_velocidade.setMinimumHeight(34)
        self.botao_velocidade.setEnabled(False)
        self.botao_velocidade.setStyleSheet(
            "QPushButton {background: #1565c0; color: white; padding: 6px 18px; border-radius: 4px;}"
            "QPushButton:hover {background: #0d47a1;}"
            "QPushButton:disabled {background: #d4dce5; color: #536170;}"
        )
        self.botao_velocidade.setToolTip(
            "Abre outra janela em mm/s. Remove uma reta da aceleração tratada e integra "
            "todo o intervalo temporal, mesmo quando FFT ou RMS está visível."
        )
        linha.addWidget(self.botao_velocidade)
        descricao = QLabel(
            "Integração temporal → mm/s · ajuste linear · velocidade inicial zero\n"
            "Abre uma nova janela; resultado relativo ao início do intervalo."
        )
        descricao.setWordWrap(True)
        descricao.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        linha.addWidget(descricao, 1)
        self.layout_controles.addWidget(painel, 5, 0, 1, 4)
        self.botao_velocidade.clicked.connect(self.gerar_velocidade)

    def criar_controles_rms(self):
        linha = QHBoxLayout()
        self.botao_rms = QPushButton("RMS AC")
        self.botao_rms.setCheckable(True)
        self.botao_rms.setEnabled(False)
        self.botao_rms.setToolTip("Marque para ver RMS AC; desmarque para voltar ao sinal no tempo.")
        self.campo_janela_rms = QDoubleSpinBox()
        self.campo_janela_rms.setDecimals(6)
        self.campo_janela_rms.setRange(0.005, 3600)
        self.campo_janela_rms.setValue(0.5)
        self.campo_janela_rms.setSuffix(" s")
        self.campo_janela_rms.setEnabled(False)
        self.checkbox_log_rms = QCheckBox("RMS em escala logarítmica")
        self.checkbox_log_rms.setEnabled(False)
        self.checkbox_log_rms.setToolTip("RMS igual a zero fica sem ponto na escala logarítmica.")
        self.botao_fft = QPushButton("FFT")
        self.botao_fft.setCheckable(True)
        self.botao_fft.setEnabled(False)
        self.botao_fft.setToolTip(
            "Espectro de amplitude de pico do sinal tratado, sem média. "
            "Usa todo o registro com janela retangular; desmarque para voltar ao tempo."
        )
        linha.addWidget(self.botao_fft)
        linha.addWidget(self.botao_rms)
        linha.addWidget(QLabel("Janela RMS:"))
        linha.addWidget(self.campo_janela_rms)
        linha.addWidget(self.checkbox_log_rms)
        linha.addStretch()
        self.layout_controles.addLayout(linha, 4, 0, 1, 4)
        self.botao_rms.toggled.connect(
            lambda marcado: self.alternar_modo(self.botao_rms, marcado)
        )
        self.botao_fft.toggled.connect(
            lambda marcado: self.alternar_modo(self.botao_fft, marcado)
        )
        self.campo_janela_rms.editingFinished.connect(self.mudar_visualizacao)
        self.checkbox_log_rms.toggled.connect(self.mudar_visualizacao)

    def carregar_arquivo_lynx(self):
        caminho, _ = QFileDialog.getOpenFileName(self, "Abrir acelerometria Lynx", "", "Arquivos CSV (*.csv)")
        if caminho:
            try:
                self.importar_caminho(caminho)
            except LinhaFinalIncompleta as erro:
                resposta = QMessageBox.question(
                    self, "Última linha incompleta",
                    str(erro) + "\n\nDeseja ignorar somente essa última linha?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if resposta == QMessageBox.StandardButton.Yes:
                    self.importar_caminho(caminho, ignorar_ultima_incompleta=True)

    def importar_caminho(self, caminho, ignorar_ultima_incompleta=False):
        try:
            tempo, canais, sensores, info = ler_lynx_acelerometria(caminho, ignorar_ultima_incompleta)
            fs = Processamento.validar_dados(tempo, canais)
        except LinhaFinalIncompleta:
            raise
        except (OSError, ValueError) as erro:
            QMessageBox.warning(self, "Falha ao importar", str(erro))
            return False
        self.tempo = tempo
        self.df_original = canais.copy()
        self.df_sensores = canais.copy()
        self.sensores_lynx = sensores
        self.info_arquivo = info
        self.caminho_atual = Path(caminho)
        self.inicio_arquivo = ler_inicio_lynx(caminho)
        self.config_filtros = {}
        self.info_processamento = {"fs": fs, "substituicoes": {}}
        self.botao_rms.blockSignals(True)
        self.botao_rms.setChecked(False)
        self.botao_rms.blockSignals(False)
        self.botao_fft.blockSignals(True)
        self.botao_fft.setChecked(False)
        self.botao_fft.blockSignals(False)
        self.botao_velocidade.setEnabled(True)
        self.botao_passa_banda.setEnabled(True)
        self.botao_fft.setEnabled(True)
        self.botao_rms.setEnabled(True)
        self.campo_janela_rms.setEnabled(True)
        self.campo_janela_rms.setRange(2 / fs, len(tempo) / fs)
        self.checkbox_log_rms.setEnabled(False)
        self.recriar_sensores(sensores)
        avisos = info["avisos"]
        self.rotulo_importacao.setText(
            f"{len(canais.columns)} canais em g importados; {len(avisos)} aviso(s). "
            "Passe o mouse aqui para conferir a identificação dos canais."
        )
        self.rotulo_importacao.setToolTip("\n".join(avisos))
        self.rotulo_importacao.setVisible(bool(avisos))
        self.atualizar_indicacao_filtros()
        self.plotar_dados_lynx()
        aviso = aviso_unidades(info, "acelerometria")
        if aviso:
            QMessageBox.warning(self, "Canais de outra medição", aviso)
        return True

    def criar_graficos(self, layout_direito):
        self.grafico = pg.GraphicsLayoutWidget()
        self.grafico.setBackground("w")
        self.graficos_eixos = {}
        for linha, eixo in enumerate("XYZ"):
            self.adicionar_grafico_eixo(eixo, linha)
        self.graficos_eixos["Y"].setXLink(self.graficos_eixos["X"])
        self.graficos_eixos["Z"].setXLink(self.graficos_eixos["X"])
        layout_direito.addWidget(self.grafico, 1)

    def adicionar_grafico_eixo(self, eixo, linha):
        titulo = eixo if eixo == EIXO_DESCONHECIDO else f"Eixo {eixo}"
        grafico = self.grafico.addPlot(
            row=linha, col=0, title=titulo,
            axisItems={"bottom": EixoDataHora(orientation="bottom")},
        )
        grafico.setLabel("bottom", "Tempo", units="s")
        grafico.setLabel("left", "Aceleração", units="g")
        grafico.showGrid(x=True, y=True, alpha=0.25)
        grafico.addLegend(colCount=4, offset=(10, 5), labelTextColor="#333333")
        for lado in ("left", "bottom"):
            grafico.getAxis(lado).setPen("#555555")
            grafico.getAxis(lado).setTextPen("#333333")
        grafico.getAxis("left").enableAutoSIPrefix(False)
        self.graficos_eixos[eixo] = grafico

    def recriar_sensores(self, sensores):
        for widget in list(self.checkboxes_canais.values()) + self.grupos_eixos:
            self.layout_canais.removeWidget(widget)
            widget.hide()
            widget.deleteLater()
        self.checkboxes_canais = {}
        self.checkboxes_eixos = {}
        self.grupos_eixos = []
        for numero, sensor in enumerate(sensores, 1):
            checkbox = QCheckBox(self.info_arquivo["rotulos_sensores"][numero - 1])
            checkbox.setChecked(True)
            checkbox.setToolTip("\n".join(
                f"{eixo}: Canal {n} — {self.info_arquivo['nomes'][n]}"
                for eixo, n in sensor.items()
            ))
            self.layout_canais.insertWidget(self.layout_canais.count() - 1, checkbox)
            self.checkboxes_canais[numero] = checkbox
        self.adicionar_checkboxes_eixos()

    def adicionar_checkboxes_eixos(self):
        for numero, checkbox_sensor in self.checkboxes_canais.items():
            grupo = QWidget()
            self.grupos_eixos.append(grupo)
            layout = QVBoxLayout(grupo)
            layout.setContentsMargins(20, 0, 0, 0)
            layout.setSpacing(4)
            sensor = self.sensores_lynx[numero - 1]
            for eixo in sorted(sensor, key=EIXOS.index):
                n = sensor[eixo]
                checkbox = QCheckBox(f"{eixo}: Canal {n} — {self.info_arquivo['nomes'][n]}")
                checkbox.setToolTip(checkbox.text())
                checkbox.setChecked(True)
                self.checkboxes_eixos[(numero, eixo)] = checkbox
                layout.addWidget(checkbox)
                checkbox.toggled.connect(self.atualizar_visibilidade)
            posicao = self.layout_canais.indexOf(checkbox_sensor)
            self.layout_canais.insertWidget(posicao + 1, grupo)
            checkbox_sensor.toggled.connect(lambda marcado, n=numero: self.alternar_acelerometro(n, marcado))

    def alternar_acelerometro(self, numero, marcado):
        for (n, _eixo), checkbox in self.checkboxes_eixos.items():
            if n == numero:
                checkbox.setEnabled(marcado)
        self.atualizar_visibilidade()

    def atualizar_visibilidade(self):
        for (numero, eixo), curva in self.curvas_lynx.items():
            curva.setVisible(self.checkboxes_canais[numero].isChecked()
                             and self.checkboxes_eixos[(numero, eixo)].isChecked())

    def alternar_modo(self, botao, marcado):
        if marcado:
            outro = (
                self.botao_fft
                if botao is self.botao_rms
                else self.botao_rms
            )
            outro.blockSignals(True)
            outro.setChecked(False)
            outro.blockSignals(False)

        self.mudar_visualizacao()

    def mudar_visualizacao(self, *args):
        if self.df_sensores is None:
            return

        self.checkbox_log_rms.setEnabled(self.botao_rms.isChecked())
        self.campo_janela_rms.setEnabled(
            not self.botao_fft.isChecked()
        )

        try:
            self.plotar_dados_lynx()
        except ValueError as erro:
            QMessageBox.warning(
                self, "Visualização inválida", str(erro)
            )

            for botao in (self.botao_rms, self.botao_fft):
                botao.blockSignals(True)
                botao.setChecked(False)
                botao.blockSignals(False)

            self.checkbox_log_rms.setEnabled(False)
            self.campo_janela_rms.setEnabled(True)
            self.plotar_dados_lynx()

    def atualizar_graficos(self):
        self.mudar_visualizacao()

    def restaurar_original(self):
        for botao in (self.botao_rms, self.botao_fft):
            botao.blockSignals(True)
            botao.setChecked(False)
            botao.blockSignals(False)

        self.checkbox_log_rms.setEnabled(False)
        super().restaurar_original()

    def plotar_dados_lynx(self):
        if self.df_sensores is None:
            return

        rms = self.botao_rms.isChecked()
        fft = self.botao_fft.isChecked()
        log = rms and self.checkbox_log_rms.isChecked()

        self.info_rms = None
        self.info_fft = None

        if fft:
            tempo_plot, dados_plot, self.info_fft = Processamento.fft_ac(
                self.tempo, self.df_sensores
            )
            rotulo, unidade = "Amplitude de pico (AC)", "g"
            titulo_modo = "FFT"

        elif rms:
            tempo_plot, dados_plot, self.info_rms = Processamento.rms_ac(
                self.tempo,
                self.df_sensores,
                self.campo_janela_rms.value(),
            )
            dados_plot = dados_plot * 1000
            rotulo, unidade = "RMS AC", "mg"
            titulo_modo = "RMS AC"

        else:
            tempo_plot, dados_plot = self.tempo, self.df_sensores
            rotulo, unidade = "Aceleração", "g"
            titulo_modo = "sinal no tempo"

        if (any(EIXO_DESCONHECIDO in sensor for sensor in self.sensores_lynx)
                and EIXO_DESCONHECIDO not in self.graficos_eixos):
            self.adicionar_grafico_eixo(EIXO_DESCONHECIDO, 3)

        self.curvas_lynx.clear()

        for eixo, grafico in self.graficos_eixos.items():
            grafico.clear()
            grafico.setLogMode(x=False, y=log)
            titulo_eixo = eixo if eixo == EIXO_DESCONHECIDO else f"Eixo {eixo}"
            grafico.setTitle(
                f"{titulo_eixo} — {titulo_modo}",
                color="#333333",
            )
            grafico.setLabel("left", rotulo, units=unidade)
            configurar_eixo_temporal(grafico, None if fft else self.inicio_arquivo)
            if fft:
                grafico.setLabel("bottom", "Frequência", units="Hz")

        cores = ["#1565C0", "#D55E00", "#18864B", "#8E44AD"]

        for numero, sensor in enumerate(self.sensores_lynx, start=1):
            for eixo, n in sensor.items():
                valores = dados_plot[n].to_numpy()

                if log:
                    valores = np.where(valores > 0, valores, np.nan)

                curva = self.graficos_eixos[eixo].plot(
                    tempo_plot,
                    valores,
                    pen=pg.mkPen(cores[(numero - 1) % len(cores)], width=1),
                    name=f"Canal {n} — {self.info_arquivo['nomes'][n]}",
                    connect="finite",
                )
                self.curvas_lynx[(numero, eixo)] = curva

        self.atualizar_visibilidade()
        presentes = {e for sensor in self.sensores_lynx for e in sensor}
        base = None
        for eixo, grafico in self.graficos_eixos.items():
            grafico.setVisible(eixo in presentes)
            grafico.setXLink(None)
            if eixo in presentes:
                if base is None:
                    base = grafico
                else:
                    grafico.setXLink(base)

        for grafico in self.graficos_eixos.values():
            grafico.enableAutoRange()

        fs = self.info_processamento["fs"]
        modo = "Sinal no tempo"

        if fft:
            resolucao = self.info_fft["resolucao_hz"]
            modo = (
                f"FFT AC: amplitude de pico, Δf = {resolucao:g} Hz; "
                "janela retangular"
            )

        elif rms:
            info = self.info_rms
            modo = (
                f"RMS AC: {info['janela_efetiva_s']:g} s, "
                f"{info['amostras_por_janela']} amostras/janela"
            )

            if info["ultima_janela"] < info["amostras_por_janela"]:
                modo += f"; última parcial: {info['ultima_janela']}"

            if info["descartadas"]:
                modo += (
                    "; amostra final isolada omitida: "
                    f"{info['descartadas']}"
                )

            if log:
                modo += "; log (zeros sem ponto)"

        substituidas = sum(
            self.info_processamento.get("substituicoes", {}).values()
        )
        self.statusBar().showMessage(
            f"{self.caminho_atual.name} | {fs:g} Hz | "
            f"{len(self.tempo)} amostras | {modo} | "
            f"{substituidas} substituições de outliers"
        )


    def gerar_velocidade(self):
        if self.df_sensores is None:
            return
        canais = {}
        for numero, sensor in enumerate(self.sensores_lynx, 1):
            for eixo, canal in sensor.items():
                if (self.checkboxes_canais[numero].isChecked()
                        and self.checkboxes_eixos[(numero, eixo)].isChecked()):
                    canais[canal] = (eixo, f"Canal {canal} — {self.info_arquivo['nomes'][canal]}")
        if not canais:
            QMessageBox.information(self, "Integração", "Selecione pelo menos um canal.")
            return
        canais = dict(sorted(canais.items()))
        try:
            dados = integrar_relativo(self.tempo, self.df_sensores[list(canais)], 'aceleracao')
        except ValueError as erro:
            QMessageBox.warning(self, "Falha ao integrar", str(erro))
            return
        janela = TelaIntegracao(
            self.tempo, dados, canais, 'velocidade', self.caminho_atual,
            inicio_arquivo=self.inicio_arquivo,
        )
        return mostrar_resultado(self, janela)
