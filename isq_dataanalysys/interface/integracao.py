"""Janelas independentes para os resultados temporais da acelerometria."""
from copy import deepcopy
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QCheckBox,
    QPushButton, QLabel, QMenu, QMessageBox, QScrollArea, QFrame,
)
from .exportacao import ExportacaoGraficos
from isq_dataanalysys.processamento.integracao import integrar_relativo
from isq_dataanalysys.leitores.acelerometria import EIXOS, EIXO_DESCONHECIDO
from isq_dataanalysys import __version__ as VERSAO


# Janelas sem pai Qt continuam abertas mesmo após fechar a origem.
# A referência fica aqui até a janela ser destruída e seus dados liberados.
_JANELAS_ABERTAS = set()


def mostrar_resultado(origem, janela):
    origem.janelas_resultados.append(janela)
    _JANELAS_ABERTAS.add(janela)
    janela.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

    def liberar():
        _JANELAS_ABERTAS.discard(janela)
        origem.janelas_resultados.remove(janela)

    janela.destroyed.connect(liberar)
    janela.show()
    janela.raise_()
    janela.activateWindow()
    return janela


class TelaIntegracao(ExportacaoGraficos, QMainWindow):
    def __init__(self, tempo, dados, canais, grandeza, caminho=None, inicio_arquivo=None):
        super().__init__()
        if grandeza not in ('velocidade', 'deslocamento'):
            raise ValueError('Grandeza de resultado desconhecida.')
        self.tempo = np.array(tempo, dtype=float, copy=True)
        self.df_sensores = dados.copy(deep=True)
        self.canais = deepcopy(canais)
        self.grandeza = grandeza
        self.caminho_atual = caminho
        # Preserva a referência temporal sem reler o CSV ao exportar.
        self.inicio_exportacao = inicio_arquivo
        self.janelas_resultados = []
        velocidade = grandeza == 'velocidade'
        nome, unidade, condicao = ('Velocidade', 'mm/s', 'v₀') if velocidade else ('Deslocamento', 'mm', 'd₀')
        referencia = 'relativa ao início do intervalo' if velocidade else 'relativo ao início do intervalo'
        metodo = (
            'Aceleração tratada em g → remover ajuste linear → integrar; 1 g = 9806,65 mm/s².'
            if velocidade else
            'Velocidade em mm/s → remover ajuste quadrático → integrar para mm.'
        )
        self.descricao_exportacao = (
            f'{nome} {referencia}; {condicao} = 0 {unidade}; '
            f'intervalo: {self.tempo[0]:g} a {self.tempo[-1]:g} s.\n{metodo}'
        )
        self.setWindowTitle(f'{nome} — {referencia} — v{VERSAO}')
        self.resize(1100, 700)
        central = QWidget()
        self.setCentralWidget(central)
        principal = QHBoxLayout(central)

        painel_canais = QWidget()
        controles = QVBoxLayout(painel_canais)
        controles.addWidget(QLabel('<b>Canais do resultado</b>'))
        self.checkboxes_canais = {}
        self.curvas = {}
        for canal, (eixo, rotulo) in self.canais.items():
            checkbox = QCheckBox(f'{eixo}: {rotulo}')
            checkbox.setToolTip(checkbox.text())
            checkbox.setChecked(True)
            checkbox.toggled.connect(self.atualizar_visibilidade)
            controles.addWidget(checkbox)
            self.checkboxes_canais[canal] = checkbox
        controles.addStretch()
        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setWidget(painel_canais)
        rolagem.setFixedWidth(240)
        principal.addWidget(rolagem)

        direito = QVBoxLayout()
        principal.addLayout(direito, 1)
        painel = QFrame()
        painel.setFrameShape(QFrame.Shape.StyledPanel)
        cabecalho = QVBoxLayout(painel)
        self.rotulo_referencia = QLabel(self.descricao_exportacao)
        self.rotulo_referencia.setWordWrap(True)
        cabecalho.addWidget(self.rotulo_referencia)
        acoes = QHBoxLayout()
        cabecalho.addLayout(acoes)
        self.exportar = QPushButton('Exportar')
        menu = QMenu(self.exportar)
        menu.addAction('SVG vetorial').triggered.connect(self.exportar_svg)
        menu.addAction('HTML interativo').triggered.connect(self.exportar_html)
        self.exportar.setMenu(menu)
        acoes.addWidget(self.exportar)
        if velocidade:
            self.botao_deslocamento = QPushButton('Gerar deslocamento')
            self.botao_deslocamento.setObjectName('gerar_deslocamento')
            self.botao_deslocamento.setMinimumHeight(34)
            self.botao_deslocamento.setToolTip('Abre outra janela em mm, com deslocamento inicial zero.')
            self.botao_deslocamento.clicked.connect(self.gerar_deslocamento)
            acoes.addWidget(self.botao_deslocamento)
        acoes.addStretch()
        direito.addWidget(painel)

        self.grafico = pg.GraphicsLayoutWidget()
        self.grafico.setBackground('w')
        direito.addWidget(self.grafico, 1)
        self.graficos_eixos = {}
        presentes = {eixo for eixo, _rotulo in self.canais.values()}
        eixos = [e for e in EIXOS if e in presentes]
        base = None
        for linha, eixo in enumerate(eixos):
            plot = self.grafico.addPlot(row=linha, col=0)
            titulo_eixo = eixo if eixo == EIXO_DESCONHECIDO else f'Eixo {eixo}'
            plot.setTitle(f'{titulo_eixo} — {nome} {referencia}', color='#333333', size='10pt')
            plot.setLabel('bottom', 'Tempo', units='s')
            plot.setLabel('left', nome, units=unidade)
            for lado in ('left', 'bottom'):
                plot.getAxis(lado).enableAutoSIPrefix(False)
                plot.getAxis(lado).setPen('#555555')
                plot.getAxis(lado).setTextPen('#333333')
            plot.showGrid(x=True, y=True, alpha=.25)
            plot.addLegend(colCount=4, offset=(10, 5), labelTextColor='#333333')
            self.graficos_eixos[eixo] = plot
            if base is None:
                base = plot
            else:
                plot.setXLink(base)
        cores = ['#1565C0', '#D55E00', '#18864B', '#8E44AD']
        for numero, (canal, (eixo, rotulo)) in enumerate(self.canais.items()):
            self.curvas[canal] = self.graficos_eixos[eixo].plot(
                self.tempo, self.df_sensores[canal].to_numpy(),
                pen=pg.mkPen(cores[(numero // 3) % len(cores)], width=1), name=rotulo,
            )
        self.statusBar().showMessage(f'{len(self.tempo)} amostras | {nome} em {unidade} | {condicao} = 0')
        self.statusBar().addPermanentWidget(QLabel(f'v{VERSAO}'))

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
        janela = TelaIntegracao(
            self.tempo, dados, canais, 'deslocamento', self.caminho_atual,
            inicio_arquivo=self.inicio_exportacao,
        )
        return mostrar_resultado(self, janela)
