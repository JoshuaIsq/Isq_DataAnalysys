"""Seleção das análises implementadas e referências às janelas abertas."""
from importlib.resources import as_file, files

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout, QMenu, QMessageBox

from isq_dataanalysys import __version__
from isq_dataanalysys.aplicacao import diagnostico
from .acelerometria import TelaLynxAcelerometria
from .extensometria import TelaLynxExtensometria


class TelaInicial(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'ISQ_Analysys — v{__version__}')
        self.resize(1000, 600)
        self.janela_acelerometria = None
        self.janela_extensometria = None
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
        layout.addWidget(titulo)
        self.botao_lynx = QPushButton('Lynx')
        menu = QMenu(self.botao_lynx)
        menu.addAction('Extensometria').triggered.connect(self.abrir_extensometria)
        menu.addAction('Acelerometria').triggered.connect(self.abrir_acelerometria)
        self.botao_lynx.setMenu(menu)
        layout.addWidget(self.botao_lynx)
        layout.addStretch()
        sobre = QPushButton('Sobre esta instalação')
        sobre.clicked.connect(self.mostrar_instalacao)
        layout.addWidget(sobre, 0, Qt.AlignmentFlag.AlignRight)

    def abrir_acelerometria(self):
        if self.janela_acelerometria is None:
            self.janela_acelerometria = TelaLynxAcelerometria()
        self.exibir(self.janela_acelerometria)

    def abrir_extensometria(self):
        if self.janela_extensometria is None:
            self.janela_extensometria = TelaLynxExtensometria()
        self.exibir(self.janela_extensometria)

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
