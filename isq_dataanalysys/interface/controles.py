"""Controles reutilizáveis para parâmetros de filtros e passa-banda."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QDoubleSpinBox,
    QPushButton,
    QLabel,
    QGridLayout,
)


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

class ControlePassaBanda(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("controle_passa_banda")
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Passa-banda"), 0, 0, 1, 2)
        self.campo_inferior = QDoubleSpinBox()
        self.campo_superior = QDoubleSpinBox()
        for campo in (self.campo_inferior, self.campo_superior):
            campo.setDecimals(2)
            campo.setRange(0, 100000000)
            campo.setSuffix(" Hz")
            campo.setFixedWidth(150)
        self.campo_inferior.setObjectName("low_cutoff")
        self.campo_superior.setObjectName("high_cutoff")
        layout.addWidget(QLabel("Low cutoff:"), 1, 0)
        layout.addWidget(self.campo_inferior, 1, 1)
        layout.addWidget(QLabel("High cutoff:"), 2, 0)
        layout.addWidget(self.campo_superior, 2, 1)
        self.botao_aplicar = QPushButton("Aplicar")
        self.botao_aplicar.setObjectName("aplicar_passa_banda")
        self.botao_desativar = QPushButton("Desativar")
        self.botao_desativar.setEnabled(False)
        botoes = QHBoxLayout()
        botoes.addWidget(self.botao_aplicar)
        botoes.addWidget(self.botao_desativar)
        layout.addLayout(botoes, 3, 0, 1, 2)
        layout.setColumnStretch(2, 1)
        self.setEnabled(False)

    def cortes(self):
        return self.campo_inferior.value(), self.campo_superior.value()

    def configurar_amostragem(self, fs):
        self.setToolTip(f"Use 0 < Low cutoff < High cutoff < {fs / 2:g} Hz.")
        self.setEnabled(True)

    def mostrar_cortes(self, cortes):
        inferior, superior = cortes if cortes is not None else (0, 0)
        self.campo_inferior.setValue(inferior)
        self.campo_superior.setValue(superior)
        self.botao_desativar.setEnabled(cortes is not None)
