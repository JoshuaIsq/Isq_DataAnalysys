"""Janelas independentes para os resultados temporais da acelerometria."""
from copy import deepcopy
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QCheckBox,
    QPushButton, QLabel, QMenu, QMessageBox, QScrollArea,
)
from tela import Tela
from integracao import integrar_relativo


class TelaIntegracao(QMainWindow):
    # Compartilha os exportadores, que usam as curvas visíveis e seus rótulos.
    exportar_svg = Tela.exportar_svg
    exportar_html = Tela.exportar_html

    def __init__(self, tempo, dados, canais, grandeza, caminho=None):
        super().__init__()
        self.tempo = np.array(tempo, dtype=float, copy=True)
        self.df_sensores = dados.copy(deep=True)
        self.canais = deepcopy(canais)
        self.grandeza = grandeza
        self.caminho_atual = caminho
        self.janelas_resultados = []
        nome, unidade = ('Velocidade', 'mm/s') if grandeza == 'velocidade' else ('Deslocamento', 'mm')
        referencia = 'relativo ao início do intervalo' if grandeza == 'deslocamento' else 'relativa ao início do intervalo'
        self.setWindowTitle(f'{nome} — {referencia}')
        self.resize(1100, 700)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        descricao = f'{nome} {referencia}; condição inicial = 0 {unidade}; início: {self.tempo[0]:g} s'
        layout.addWidget(QLabel(descricao))
        painel_canais = QWidget()
        controles = QVBoxLayout(painel_canais)
        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setMaximumHeight(180)
        rolagem.setWidget(painel_canais)
        layout.addWidget(rolagem)
        acoes = QHBoxLayout()
        layout.addLayout(acoes)
        self.checkboxes_canais = {}
        self.curvas = {}
        for canal, (eixo, rotulo) in self.canais.items():
            checkbox = QCheckBox(f'{eixo}: {rotulo}')
            checkbox.setChecked(True)
            checkbox.toggled.connect(self.atualizar_visibilidade)
            controles.addWidget(checkbox)
            self.checkboxes_canais[canal] = checkbox
        self.exportar = QPushButton('Exportar')
        menu = QMenu(self.exportar)
        menu.addAction('SVG vetorial').triggered.connect(self.exportar_svg)
        menu.addAction('HTML interativo').triggered.connect(self.exportar_html)
        self.exportar.setMenu(menu)
        acoes.addWidget(self.exportar)
        if grandeza == 'velocidade':
            self.botao_deslocamento = QPushButton('Gerar deslocamento')
            self.botao_deslocamento.clicked.connect(self.gerar_deslocamento)
            acoes.addWidget(self.botao_deslocamento)
        self.grafico = pg.GraphicsLayoutWidget()
        self.grafico.setBackground('w')
        layout.addWidget(self.grafico)
        self.graficos_eixos = {}
        for linha, eixo in enumerate('XYZ'):
            plot = self.grafico.addPlot(row=linha, col=0, title=f'Eixo {eixo} — {nome} {referencia}')
            plot.setLabel('bottom', 'Tempo', units='s')
            plot.setLabel('left', nome, units=unidade)
            plot.getAxis('left').enableAutoSIPrefix(False)
            plot.showGrid(x=True, y=True, alpha=.25)
            plot.addLegend()
            self.graficos_eixos[eixo] = plot
            if linha:
                plot.setXLink(self.graficos_eixos['X'])
        for numero, (canal, (eixo, rotulo)) in enumerate(self.canais.items()):
            self.curvas[canal] = self.graficos_eixos[eixo].plot(
                self.tempo, self.df_sensores[canal].to_numpy(),
                pen=pg.intColor(numero), name=rotulo,
            )
        self.statusBar().showMessage(descricao)

    def atualizar_visibilidade(self):
        for canal, curva in self.curvas.items():
            curva.setVisible(self.checkboxes_canais[canal].isChecked())

    def gerar_deslocamento(self):
        canais = {c: info for c, info in self.canais.items() if self.checkboxes_canais[c].isChecked()}
        if not canais:
            QMessageBox.information(self, 'Integração', 'Selecione pelo menos um canal.')
            return
        try:
            dados = integrar_relativo(self.tempo, self.df_sensores[list(canais)], 'velocidade')
        except ValueError as erro:
            QMessageBox.warning(self, 'Falha ao integrar', str(erro))
            return
        janela = TelaIntegracao(self.tempo, dados, canais, 'deslocamento', self.caminho_atual)
        self.janelas_resultados.append(janela)
        janela.show()
        return janela
