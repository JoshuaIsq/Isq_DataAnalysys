"""Seleção das análises implementadas e referências às janelas abertas."""

from importlib.resources import as_file, files
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout, QMenu, QMessageBox
from isq_dataanalysys import __version__
from isq_dataanalysys.aplicacao import diagnostico
from .acelerometria import TelaLynxAcelerometria
from .extensometria import TelaLynxExtensometria
from .regua import TelaLynxReguaPotenciometrica
from .dados_tratados import TelaDadosTratados, mostrar_resultado


class TelaInicial(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'ISQ_Analysys — v{__version__}')
        self.resize(1000, 600)
        self.setObjectName('tela_inicial')
        self.setStyleSheet('''QWidget#tela_inicial {background-color: #FFFFFF;}''')
        self.janela_acelerometria = None
        self.janela_extensometria = None
        self.janela_regua = None
        self.janelas_resultados = []
        self.janelas_dados_tratados = self.janelas_resultados
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(15)
        logo = QLabel()
        with as_file(files('isq_dataanalysys').joinpath('recursos/logo_isq.png')) as caminho:
            imagem = QPixmap(str(caminho))
        logo.setPixmap(imagem.scaled(220, 220, Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(logo, 0, Qt.AlignmentFlag.AlignHCenter)
        titulo = QLabel('Selecione sua placa')
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(titulo, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(20)
        self.botao_lynx = QPushButton('Lynx')
        self.botao_lynx.setStyleSheet('border: 1px solid #63757F')
        menu = QMenu(self.botao_lynx)
        menu.addAction('Extensometria').triggered.connect(self.abrir_extensometria)
        menu.addAction('Acelerometria').triggered.connect(self.abrir_acelerometria)
        menu.addAction('Régua potenciométrica').triggered.connect(self.abrir_regua)
        self.botao_lynx.setMenu(menu)
        layout.addWidget(self.botao_lynx)
        self.botao_dados_tratados = QPushButton('Dados tratados')
        self.botao_dados_tratados.clicked.connect(self.abrir_dados_tratados)
        layout.addWidget(self.botao_dados_tratados)
        layout.addStretch(1)

    def abrir_acelerometria(self):
        return self._abrir_analise('janela_acelerometria', TelaLynxAcelerometria)

    def abrir_extensometria(self):
        return self._abrir_analise('janela_extensometria', TelaLynxExtensometria)

    def abrir_regua(self):
        return self._abrir_analise('janela_regua', TelaLynxReguaPotenciometrica)

    def _abrir_analise(self, atributo, classe):
        try:
            janela = getattr(self, atributo)
            if janela is None:
                janela = classe()
                setattr(self, atributo, janela)
        except RuntimeError as erro:
            QMessageBox.critical(self, 'Instalação incompatível', str(erro))
            return None
        self.exibir(janela)
        return janela

    def abrir_dados_tratados(self):
        janela = TelaDadosTratados()
        return mostrar_resultado(self, janela)

    @staticmethod
    def exibir(janela):
        if janela.isMinimized():
            janela.showNormal()
        else:
            janela.show()
        janela.raise_()
        janela.activateWindow()

    def mostrar_instalacao(self):
        QMessageBox.information(self, 'Sobre esta instalação', diagnostico())
