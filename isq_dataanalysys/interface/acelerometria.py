from pathlib import Path
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QFrame, QSizePolicy,
                               QPushButton, QDoubleSpinBox, QLabel, QFileDialog, QMessageBox,)
from isq_dataanalysys.interface.base import Tela
from isq_dataanalysys.leitores.acelerometria import (
    EIXOS, ler_lynx_acelerometria,
)
from isq_dataanalysys.leitores.lynx import LinhaFinalIncompleta, aviso_unidades
from isq_dataanalysys.processamento.sinais import Processamento
from isq_dataanalysys.processamento.cinematica import converter_aceleracao, integrar_segmento, FATOR_G_MM_S2
from isq_dataanalysys.interface.cinematica import TelaCinematica
from isq_dataanalysys.interface.integracao import mostrar_resultado
from isq_dataanalysys.interface.passa_banda import ControlePassaBanda
from isq_dataanalysys import __version__ as VERSAO
from isq_dataanalysys.interface.eixo_temporal import EixoDataHora, configurar_eixo_temporal
from .intervalo_temporal import VinculoIntervalos
from .visualizacao_acelerometria import VisualizacaoAcelerometria
from .layout_acelerometria import montar_lateral_acelerometria


class TelaLynxAcelerometria(VisualizacaoAcelerometria, Tela):
    FILTROS_DISPONIVEIS = ("offset",)

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
        self.df_tratado_g = None
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
        self.layout_controles.addWidget(self.rotulo_importacao, 8, 0, 1, 4)
        self._intervalo_temporal = None
        self._escalas_modos = {}
        self.criar_limites_visualizacao(linha_inicial=6)
        montar_lateral_acelerometria(self)

    def mostrar_metodo_integracao(self):
        QMessageBox.information(self, "Sobre a integração", self.rotulo_metodo_integracao.text())

    @property
    def unidade_aceleracao(self):
        return 'mm/s²' if self.botao_converter.isChecked() else 'g'

    def modo_espectral(self):
        return self.botao_fft.isChecked() or self.botao_psd.isChecked()

    def aplicar_configuracao(self, proposta):
        # Os filtros sempre partem do CSV em g, mesmo com a conversão ativa.
        try:
            resultado, info = Processamento.aplicar(self.tempo, self.df_original, proposta)
            exibido = (converter_aceleracao(self.tempo, resultado)
                       if self.botao_converter.isChecked() else resultado.copy())
        except ValueError as erro:
            QMessageBox.warning(self, 'Parâmetro inválido', str(erro))
            return False
        self.df_tratado_g = resultado
        self.df_sensores = exibido
        self.config_filtros = proposta.copy()
        self.info_processamento = info
        self.atualizar_indicacao_filtros()
        self.atualizar_graficos()
        return True

    def alternar_conversao(self, ativo):
        if self.df_tratado_g is None:
            return
        try:
            resultado = (converter_aceleracao(self.tempo, self.df_tratado_g)
                         if ativo else self.df_tratado_g.copy())
        except ValueError as erro:
            self.botao_converter.blockSignals(True)
            self.botao_converter.setChecked(not ativo)
            self.botao_converter.blockSignals(False)
            QMessageBox.warning(self, 'Conversão inválida', str(erro))
            return
        self.df_sensores = resultado
        self.botao_velocidade.setEnabled(ativo)
        # Mostra imediatamente o sinal convertido no domínio temporal.
        for botao in (self.botao_fft, self.botao_psd, self.botao_rms):
            botao.blockSignals(True)
            botao.setChecked(False)
            botao.blockSignals(False)
        self.mudar_visualizacao()

    def criar_controle_passa_banda(self):
        self.layout_controles.setHorizontalSpacing(16)
        self.layout_controles.addWidget(self.controle_offset, 0, 1)
        self.controle_passa_banda = ControlePassaBanda()
        self.layout_controles.addWidget(self.controle_passa_banda, 0, 3, 3, 1)
        self.controle_passa_banda.botao_aplicar.clicked.connect(self.aplicar_passa_banda)
        self.controle_passa_banda.botao_desativar.clicked.connect(
            lambda: self.aplicar_passa_banda(desativar=True))

    def aplicar_passa_banda(self, desativar=False):
        if self.df_original is None:
            return False
        proposta = self.config_filtros.copy()
        if desativar:
            proposta.pop("passa_banda", None)
        else:
            proposta["passa_banda"] = self.controle_passa_banda.cortes()
        return self.aplicar_configuracao(proposta)

    def atualizar_indicacao_filtros(self):
        super().atualizar_indicacao_filtros()
        cortes = self.config_filtros.get("passa_banda")
        self.controle_passa_banda.mostrar_cortes(cortes)
        if cortes is None:
            return
        inferior, superior = cortes
        descricao = f"Passa-banda: {inferior:g}–{superior:g} Hz"
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
        linha.addWidget(self.botao_velocidade)
        self.botao_converter = QPushButton('Converter g → mm/s² (×9810)')
        self.botao_converter.setObjectName('converter_aceleracao')
        self.botao_converter.setCheckable(True)
        self.botao_converter.setEnabled(False)
        self.botao_converter.setToolTip('Após o passa-banda, converte o sinal temporal uma única vez. '
                                       'Desmarque para voltar a g. FFT e PSD continuam em g e g²/Hz.')
        self.botao_converter.toggled.connect(self.alternar_conversao)
        linha.addWidget(self.botao_converter)
        self.rotulo_metodo_integracao = QLabel()
        self.rotulo_metodo_integracao.setWordWrap(True)
        self.rotulo_metodo_integracao.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        linha.addWidget(self.rotulo_metodo_integracao, 1)
        self.layout_controles.addWidget(painel, 5, 0, 1, 4)
        self.botao_velocidade.clicked.connect(self.gerar_velocidade)
        self.atualizar_metodo_integracao()

    def atualizar_metodo_integracao(self):
        self.rotulo_metodo_integracao.setText(
            'Aceleração em g → passa-banda → converter ×9810 para mm/s².\n'
            'Velocidade: soma X·dt → subtrair ajuste linear por mínimos quadrados.\n'
            'Posição: soma da velocidade corrigida ·dt → subtrair ajuste de grau 2.\n'
            'Cada arquivo é um segmento independente, sem retirada automática da média da aceleração. '
            'FFT e PSD usam a aceleração tratada em g, antes da conversão. '
            'Os ajustes removem componentes lentas; não determinam a posição física absoluta.'
        )
        self.botao_velocidade.setToolTip(
            'Converta para mm/s² primeiro. Integra todo o sinal temporal e subtrai a reta '
            'ajustada à velocidade, mesmo quando FFT/PSD/RMS está visível.'
        )

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
        self.botao_psd = QPushButton('PSD')
        self.botao_psd.setCheckable(True)
        self.botao_psd.setEnabled(False)
        self.botao_psd.setToolTip('Densidade espectral de potência em g²/Hz. Periodograma unilateral, '
                                'sem média, janela retangular e registro completo.')
        self.botao_psd.toggled.connect(lambda marcado: self.alternar_modo(self.botao_psd, marcado))
        linha.addWidget(self.botao_fft)
        linha.addWidget(self.botao_psd)
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
        self.df_tratado_g = canais.copy()
        self.botao_converter.blockSignals(True)
        self.botao_converter.setChecked(False)
        self.botao_converter.blockSignals(False)
        self.botao_converter.setEnabled(True)
        self.reiniciar_limites_visualizacao()
        self.sensores_lynx = sensores
        self.info_arquivo = info
        self.caminho_atual = Path(caminho)
        self.carregar_referencia_temporal(caminho)
        self.config_filtros = {}
        self.info_processamento = {"fs": fs, "substituicoes": {}}
        self.botao_rms.blockSignals(True)
        self.botao_rms.setChecked(False)
        self.botao_rms.blockSignals(False)
        self.botao_fft.blockSignals(True)
        self.botao_fft.setChecked(False)
        self.botao_fft.blockSignals(False)
        self.botao_psd.blockSignals(True)
        self.botao_psd.setChecked(False)
        self.botao_psd.blockSignals(False)
        self.botao_psd.setEnabled(True)
        self.botao_velocidade.setEnabled(False)
        self.controle_passa_banda.configurar_amostragem(fs)
        self.botao_fft.setEnabled(True)
        self.botao_rms.setEnabled(True)
        self.campo_janela_rms.setEnabled(True)
        self.campo_janela_rms.setRange(2 / fs, len(tempo) / fs)
        self.checkbox_log_rms.setEnabled(False)
        self.recriar_sensores(sensores)
        self.recriar_graficos_sensores()
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
        self.vinculo_intervalos = VinculoIntervalos()
        self.adicionar_grafico_sensor(0, 'Sensores', 0)
        layout_direito.addWidget(self.grafico, 1)

    def recriar_graficos_sensores(self):
        self.vinculo_intervalos.limpar()
        self.curvas_lynx.clear()
        self.grafico.clear()
        # Nome compartilhado com os serviços de escala/exportação. Nesta tela,
        # as chaves são os números dos sensores, não os eixos físicos.
        self.graficos_eixos = {}
        for numero, titulo in enumerate(self.info_arquivo['rotulos_sensores'], 1):
            self.adicionar_grafico_sensor(numero, titulo, numero - 1)

    def adicionar_grafico_sensor(self, numero, titulo, linha):
        grafico = self.grafico.addPlot(
            row=linha, col=0, title=titulo,
            axisItems={"bottom": EixoDataHora(orientation="bottom")},
        )
        grafico.setTitle(titulo, color="#202428")
        grafico.setLabel("bottom", "Tempo", units="s")
        grafico.setLabel("left", "Aceleração", units="g")
        grafico.showGrid(x=True, y=True, alpha=0.25)
        grafico.addLegend(colCount=3, offset=(10, 5), labelTextColor="#333333")
        for lado in ("left", "bottom"):
            grafico.getAxis(lado).setPen("#555555")
            grafico.getAxis(lado).setTextPen("#333333")
        grafico.getAxis("left").enableAutoSIPrefix(False)
        # Margens iguais alinham os painéis; os limites X são sincronizados numericamente.
        grafico.getAxis("left").setWidth(52)
        self.graficos_eixos[numero] = grafico
        self.vinculo_intervalos.adicionar_plot(grafico)

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
            for outro in (self.botao_fft, self.botao_psd, self.botao_rms):
                if outro is not botao:
                    outro.blockSignals(True)
                    outro.setChecked(False)
                    outro.blockSignals(False)

        self.mudar_visualizacao()

    def mudar_visualizacao(self, *args):
        if self.df_sensores is None:
            return

        self.checkbox_log_rms.setEnabled(self.botao_rms.isChecked())
        self.campo_janela_rms.setEnabled(
            not self.modo_espectral()
        )

        try:
            self.plotar_dados_lynx()
        except ValueError as erro:
            QMessageBox.warning(
                self, "Visualização inválida", str(erro)
            )

            for botao in (self.botao_rms, self.botao_fft, self.botao_psd):
                botao.blockSignals(True)
                botao.setChecked(False)
                botao.blockSignals(False)

            self.checkbox_log_rms.setEnabled(False)
            self.campo_janela_rms.setEnabled(True)
            self.plotar_dados_lynx()

    def atualizar_graficos(self):
        self.mudar_visualizacao()

    def restaurar_original(self):
        for botao in (self.botao_rms, self.botao_fft, self.botao_psd, self.botao_converter):
            botao.blockSignals(True)
            botao.setChecked(False)
            botao.blockSignals(False)

        self.checkbox_log_rms.setEnabled(False)
        self.botao_velocidade.setEnabled(False)
        super().restaurar_original()

    def plotar_dados_lynx(self):
        if self.df_sensores is None:
            return

        rms = self.botao_rms.isChecked()
        fft = self.botao_fft.isChecked()
        psd = self.botao_psd.isChecked()
        log = rms and self.checkbox_log_rms.isChecked()

        self.info_rms = None
        self.info_fft = None
        self.info_psd = None

        if fft:
            tempo_plot, dados_plot, self.info_fft = Processamento.fft_ac(
                self.tempo, self.df_tratado_g
            )
            rotulo, unidade = "Amplitude de pico (AC)", "g"
            titulo_modo = "FFT"

        elif psd:
            tempo_plot, dados_plot, self.info_psd = Processamento.psd_ac(self.tempo, self.df_tratado_g)
            rotulo, unidade = 'PSD', 'g²/Hz'
            titulo_modo = 'PSD'

        elif rms:
            tempo_plot, dados_plot, self.info_rms = Processamento.rms_ac(
                self.tempo,
                self.df_sensores,
                self.campo_janela_rms.value(),
            )
            if not self.botao_converter.isChecked():
                dados_plot = dados_plot * 1000
            rotulo, unidade = 'RMS AC', ('mm/s²' if self.botao_converter.isChecked() else 'mg')
            titulo_modo = "RMS AC"

        else:
            tempo_plot, dados_plot = self.tempo, self.df_sensores
            rotulo, unidade = "Aceleração", self.unidade_aceleracao
            titulo_modo = "sinal no tempo"

        self.curvas_lynx.clear()

        for numero, grafico in self.graficos_eixos.items():
            grafico.clear()
            grafico.setLogMode(x=False, y=log)
            titulo_sensor = self.info_arquivo['rotulos_sensores'][numero - 1]
            grafico.setTitle(
                f"{titulo_sensor} — {titulo_modo}",
                color="#333333",
            )
            grafico.setLabel("left", rotulo, units=unidade)
            grafico.getAxis('left').setWidth(80 if psd else 52)
            configurar_eixo_temporal(grafico, None if fft or psd else self.inicio_arquivo)
            if fft or psd:
                grafico.setLabel("bottom", "Frequência", units="Hz")

        cores = {'X': '#ff0000', 'Y': '#00ff00', 'Z': '#0000ff'}

        for numero, sensor in enumerate(self.sensores_lynx, start=1):
            for eixo, n in sensor.items():
                valores = dados_plot[n].to_numpy()

                if log:
                    valores = np.where(valores > 0, valores, np.nan)

                curva = self.graficos_eixos[numero].plot(
                    tempo_plot,
                    valores,
                    pen=pg.mkPen(cores.get(eixo, '#666666'), width=1),
                    name=f"Canal {n} — {eixo}: {self.info_arquivo['nomes'][n]}",
                    connect="finite",
                )
                if log:
                    curva.dados_csv = np.array(dados_plot[n].to_numpy(),copy=True)
                self.curvas_lynx[(numero, eixo)] = curva

        self.atualizar_visibilidade()
        self.atualizar_limites_visualizacao()

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

        elif psd:
            modo = f"PSD AC: g²/Hz, Δf = {self.info_psd['resolucao_hz']:g} Hz; periodograma retangular"

        self.descricao_exportacao = (self.rotulo_ativos.text() + '\n' + modo +
                                    f'; unidade exibida: {unidade}. ' +
                                    ('Conversão temporal g → mm/s²: ×9810.' if self.botao_converter.isChecked()
                                     else 'Aceleração temporal em g.'))
        self.metadados_tratados = {'fator_g_mm_s2': FATOR_G_MM_S2,
                                  'conversao_ativa': self.botao_converter.isChecked(),
                                  'filtros_aceleracao': self.config_filtros.copy(),
                                  'modo': titulo_modo, 'unidade': unidade}

        self.statusBar().showMessage(
            f"{self.caminho_atual.name} | {fs:g} Hz | "
            f"{len(self.tempo)} amostras | {modo}"
        )

    def gerar_velocidade(self):
        if self.df_sensores is None:
            return
        if not self.botao_converter.isChecked():
            QMessageBox.information(self, 'Velocidade', 'Clique em Converter g → mm/s² antes de gerar velocidade.')
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
            entrada = self.df_sensores[list(canais)]
            dados = integrar_segmento(self.tempo, entrada)
            janela = TelaCinematica(
                self.tempo, dados, canais, 'velocidade', self.caminho_atual,
                inicio_arquivo=self.inicio_arquivo,
                metadados={'fator_g_mm_s2': FATOR_G_MM_S2,
                           'filtros_aceleracao': self.config_filtros.copy(),
                           'media_aceleracao_retirada': False},
                intervalo_visualizacao=self._intervalo_temporal,
            )
        except ValueError as erro:
            QMessageBox.warning(self, "Falha ao integrar", str(erro))
            return
        return mostrar_resultado(self, janela)
