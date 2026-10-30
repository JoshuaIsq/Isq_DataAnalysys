from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QDoubleSpinBox, QPushButton, QLabel)

class ControleFiltros(QWidget):
    def __init__(self, nome, valor_inicial=1.0, sufixo=""):
        super().__init__()

        self.nome = nome
        self.campo = QDoubleSpinBox()
        self.campo.setDecimals(3)
        self.campo.setRange(-100000000, 100000000)
        self.campo.setValue(valor_inicial)
        self.campo.setSuffix(sufixo)
        self.campo.setFixedWidth(100)

        self.botao = QPushButton("Aplicar")
        self.botao.setFixedSize(100, 25)
        linha = QHBoxLayout()
        linha.setSpacing(8)
        linha.addWidget(self.campo)
        linha.addWidget(self.botao)
        linha.addStretch(1)
        bloco = QVBoxLayout(self)
        bloco.setContentsMargins(0, 0, 0, 0)
        bloco.setSpacing(5)
        bloco.addLayout(linha)
        bloco.addWidget(QLabel(nome))

        