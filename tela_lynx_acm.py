from pathlib import Path
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, 
                               QPushButton, QDoubleSpinBox, QLabel, QFileDialog, QMessageBox,)
from tela import Tela
from leitor_lynx_acm import ler_lynx_acelerometria
from processamento import Processamento


class TelaLynxAcelerometria(Tela):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Análise de dados - Lynx Acelerometria")
        for numero, checkbox in self.checkboxes_canais.items():
            checkbox.setText(f"Acelerômetro {numero}")
        self.checkboxes_eixos = {}
        self.curvas_lynx = {}
        self.adicionar_checkboxes_eixos()
        self.tempo = None
        self.df_original = None
        self.df_sensores = None
        self.sensores_lynx = []
        self.caminho_atual = None
        self.info_processamento = {}
        self.info_rms = None
        self.abrir.clicked.connect(self.carregar_arquivo_lynx)
        self.abrir_arquivo.triggered.connect(self.carregar_arquivo_lynx)
        self.criar_controles_rms()

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
        self.botao_rms.toggled.connect(self.mudar_visualizacao)
        self.campo_janela_rms.editingFinished.connect(self.mudar_visualizacao)
        self.checkbox_log_rms.toggled.connect(self.mudar_visualizacao)

    def carregar_arquivo_lynx(self):
        caminho, _ = QFileDialog.getOpenFileName(self, "Abrir acelerometria Lynx", "", "Arquivos CSV (*.csv)")
        if caminho:
            self.importar_caminho(caminho)

    def importar_caminho(self, caminho):
        try:
            tempo, canais, sensores = ler_lynx_acelerometria(caminho)
            fs = Processamento.validar_dados(tempo, canais)
        except (OSError, ValueError) as erro:
            QMessageBox.warning(self, "Falha ao importar", str(erro))
            return False
        self.tempo = tempo
        self.df_original = canais.copy()
        self.df_sensores = canais.copy()
        self.sensores_lynx = sensores
        self.caminho_atual = Path(caminho)
        self.config_filtros = {}
        self.info_processamento = {"fs": fs, "substituicoes": {}}
        self.botao_rms.blockSignals(True)
        self.botao_rms.setChecked(False)
        self.botao_rms.blockSignals(False)
        self.botao_rms.setEnabled(True)
        self.campo_janela_rms.setEnabled(True)
        self.campo_janela_rms.setRange(2 / fs, len(tempo) / fs)
        self.checkbox_log_rms.setEnabled(False)
        for numero, sensor in enumerate(sensores, start=1):
            self.checkboxes_canais[numero].setText(sensor)
        self.atualizar_indicacao_filtros()
        self.plotar_dados_lynx()
        return True

    def criar_graficos(self, layout_direito):
        self.grafico = pg.GraphicsLayoutWidget()
        self.grafico.setBackground("w")
        self.graficos_eixos = {}
        for linha, eixo in enumerate("XYZ"):
            grafico = self.grafico.addPlot(row=linha, col=0, title=f"Eixo {eixo}")
            grafico.setLabel("bottom", "Tempo", units="s")
            grafico.setLabel("left", "Aceleração", units="g")
            grafico.showGrid(x=True, y=True, alpha=0.25)
            grafico.addLegend(colCount=4, offset=(10, 5), labelTextColor="#333333")
            for lado in ("left", "bottom"):
                grafico.getAxis(lado).setPen("#555555")
                grafico.getAxis(lado).setTextPen("#333333")
            grafico.getAxis("left").enableAutoSIPrefix(False)
            self.graficos_eixos[eixo] = grafico
        self.graficos_eixos["Y"].setXLink(self.graficos_eixos["X"])
        self.graficos_eixos["Z"].setXLink(self.graficos_eixos["X"])
        layout_direito.addWidget(self.grafico, 1)

    def adicionar_checkboxes_eixos(self):
        for numero, checkbox_sensor in self.checkboxes_canais.items():
            grupo = QWidget()
            layout = QVBoxLayout(grupo)
            layout.setContentsMargins(20, 0, 0, 0)
            layout.setSpacing(4)
            for eixo in "XYZ":
                checkbox = QCheckBox(f"Eixo {eixo}")
                checkbox.setChecked(True)
                self.checkboxes_eixos[(numero, eixo)] = checkbox
                layout.addWidget(checkbox)
                checkbox.toggled.connect(self.atualizar_visibilidade)
            posicao = self.layout_canais.indexOf(checkbox_sensor)
            self.layout_canais.insertWidget(posicao + 1, grupo)
            checkbox_sensor.toggled.connect(lambda marcado, n=numero: self.alternar_acelerometro(n, marcado))

    def alternar_acelerometro(self, numero, marcado):
        for eixo in "XYZ":
            self.checkboxes_eixos[(numero, eixo)].setEnabled(marcado)
        self.atualizar_visibilidade()

    def atualizar_visibilidade(self):
        for (numero, eixo), curva in self.curvas_lynx.items():
            curva.setVisible(self.checkboxes_canais[numero].isChecked()
                             and self.checkboxes_eixos[(numero, eixo)].isChecked())

    def mudar_visualizacao(self, *args):
        if self.df_sensores is None:
            return
        self.checkbox_log_rms.setEnabled(self.botao_rms.isChecked())
        try:
            self.plotar_dados_lynx()
        except ValueError as erro:
            QMessageBox.warning(self, "Janela RMS inválida", str(erro))
            self.botao_rms.blockSignals(True)
            self.botao_rms.setChecked(False)
            self.botao_rms.blockSignals(False)
            self.checkbox_log_rms.setEnabled(False)
            self.plotar_dados_lynx()

    def atualizar_graficos(self):
        self.mudar_visualizacao()

    def restaurar_original(self):
        self.botao_rms.blockSignals(True)
        self.botao_rms.setChecked(False)
        self.botao_rms.blockSignals(False)
        self.checkbox_log_rms.setEnabled(False)
        super().restaurar_original()

    def plotar_dados_lynx(self):
        if self.df_sensores is None:
            return
        rms = self.botao_rms.isChecked()
        log = rms and self.checkbox_log_rms.isChecked()
        self.info_rms = None
        if rms:
            tempo_plot, dados_plot, self.info_rms = Processamento.rms_ac(
                self.tempo, self.df_sensores, self.campo_janela_rms.value()
            )
            dados_plot = dados_plot * 1000  # Apenas a apresentação RMS passa de g para mg.
            rotulo, unidade = "RMS AC", "mg"
        else:
            tempo_plot, dados_plot = self.tempo, self.df_sensores
            rotulo, unidade = "Aceleração", "g"
        self.curvas_lynx.clear()
        for eixo, grafico in self.graficos_eixos.items():
            grafico.clear()
            grafico.setLogMode(x=False, y=log)
            grafico.setTitle(f"Eixo {eixo} — {'RMS AC' if rms else 'sinal no tempo'}", color="#333333")
            grafico.setLabel("left", rotulo, units=unidade)
        cores = ["#1565C0", "#D55E00", "#18864B", "#8E44AD"]
        for numero, sensor in enumerate(self.sensores_lynx, start=1):
            for eixo in "XYZ":
                valores = dados_plot[f"{sensor} - {eixo}"].to_numpy()
                if log:
                    valores = np.where(valores > 0, valores, np.nan)
                curva = self.graficos_eixos[eixo].plot(
                    tempo_plot, valores, pen=pg.mkPen(cores[numero - 1], width=1),
                    name=sensor, connect="finite",
                )
                self.curvas_lynx[(numero, eixo)] = curva
        self.atualizar_visibilidade()
        for grafico in self.graficos_eixos.values():
            grafico.enableAutoRange()
        fs = self.info_processamento["fs"]
        modo = "Sinal no tempo"
        if rms:
            info = self.info_rms
            modo = f"RMS AC: {info['janela_efetiva_s']:g} s, {info['amostras_por_janela']} amostras/janela"
            if info["ultima_janela"] < info["amostras_por_janela"]:
                modo += f"; última parcial: {info['ultima_janela']}"
            if info["descartadas"]:
                modo += f"; amostra final isolada omitida: {info['descartadas']}"
            if log:
                modo += "; log (zeros sem ponto)"
        substituidas = sum(self.info_processamento.get("substituicoes", {}).values())
        self.statusBar().showMessage(
            f"{self.caminho_atual.name} | {fs:g} Hz | {len(self.tempo)} amostras | "
            f"{modo} | {substituidas} substituições de outliers"
        )