"""Escala e intervalo de visualização compartilhados por medições escalares."""
import numpy as np
from PySide6.QtWidgets import QDoubleSpinBox, QHBoxLayout, QLabel, QMessageBox, QPushButton


class VisualizacaoTemporal:
    """Requer grafico, tempo, df_sensores, unidade_visual e series_para_ajuste()."""

    def criar_limites_visualizacao(self, linha_inicial=5):
        self.campo_y_min = self.campo_limite()
        self.campo_y_max = self.campo_limite()
        self.campo_tempo_inicio = self.campo_limite(" s")
        self.campo_tempo_fim = self.campo_limite(" s")
        linha = QHBoxLayout()
        for texto, campo in (("Escala mínima:", self.campo_y_min), ("máxima:", self.campo_y_max),
                             ("Tempo inicial:", self.campo_tempo_inicio), ("final:", self.campo_tempo_fim)):
            rotulo = QLabel(texto)
            rotulo.setFixedWidth(rotulo.sizeHint().width())
            linha.addWidget(rotulo)
            linha.addWidget(campo)
            linha.setSpacing(12)
        linha.addStretch(1)
        self.layout_controles.addLayout(linha, linha_inicial, 0, 1, 4)
        botoes = QHBoxLayout()
        self.botao_aplicar_visualizacao = QPushButton("Aplicar escala e tempo")
        self.botao_ajustar = QPushButton("Ajustar aos dados")
        self.botao_aplicar_visualizacao.clicked.connect(self.aplicar_visualizacao)
        self.botao_ajustar.clicked.connect(self.ajustar_aos_dados)
        for botao in (self.botao_aplicar_visualizacao, self.botao_ajustar):
            botao.setEnabled(False)
            botoes.addWidget(botao)
        botoes.addStretch()
        self.layout_controles.addLayout(botoes, linha_inicial + 1, 0, 1, 4)

    @staticmethod
    def campo_limite(sufixo=""):
        campo = QDoubleSpinBox()
        campo.setDecimals(2)
        campo.setRange(-1e100, 1e100)
        campo.setSuffix(sufixo)
        campo.setFixedWidth(120) 
        campo.setEnabled(False)
        return campo

    def habilitar_limites_visualizacao(self):
        for campo in (self.campo_y_min, self.campo_y_max, self.campo_tempo_inicio, self.campo_tempo_fim):
            campo.setEnabled(True)
        for campo in (self.campo_tempo_inicio, self.campo_tempo_fim):
            campo.setRange(float(self.tempo[0]), float(self.tempo[-1]))
        self.botao_aplicar_visualizacao.setEnabled(True)
        self.botao_ajustar.setEnabled(True)

    def definir_limites(self, tempo, escala):
        for campo, valor in zip((self.campo_tempo_inicio, self.campo_tempo_fim, self.campo_y_min, self.campo_y_max),
                                (*tempo, *escala)):
            campo.setValue(float(valor))
        self.grafico.setRange(xRange=tempo, yRange=escala, padding=0, disableAutoRange=True)
        self.limites_visualizacao[self.unidade_visual] = [list(tempo), list(escala)]

    def aplicar_visualizacao(self):
        if self.df_sensores is None:
            return
        tempo = [self.campo_tempo_inicio.value(), self.campo_tempo_fim.value()]
        escala = [self.campo_y_min.value(), self.campo_y_max.value()]
        if tempo[0] >= tempo[1] or escala[0] >= escala[1]:
            QMessageBox.warning(self, "Limites inválidos", "O início deve ser menor que o fim e a escala mínima deve ser menor que a máxima.")
            return False
        self.definir_limites(tempo, escala)
        return True

    def ajustar_aos_dados(self):
        if self.df_sensores is None:
            return
        series = self.series_para_ajuste()
        if not series:
            return
        minimo = min(float(np.min(v)) for v in series)
        maximo = max(float(np.max(v)) for v in series)
        margem = max((maximo - minimo) * 0.05, abs(maximo) * 1e-6, 1e-9)
        self.definir_limites([float(self.tempo[0]), float(self.tempo[-1])], [minimo - margem, maximo + margem])
