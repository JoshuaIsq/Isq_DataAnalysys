"""Dois cortes em Hz; o cálculo e a confirmação ficam na tela de acelerometria."""

from PySide6.QtWidgets import (
    QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout,
)


class DialogoPassaBanda(QDialog):
    def __init__(self, fs, cortes=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Passa-banda — Acelerometria")
        self.setObjectName("dialogo_passa_banda")
        self.setMinimumWidth(390)
        layout = QVBoxLayout(self)
        formulario = QFormLayout()

        self.campo_inferior = QDoubleSpinBox()
        self.campo_superior = QDoubleSpinBox()
        for campo in (self.campo_inferior, self.campo_superior):
            campo.setDecimals(8)
            campo.setRange(0, 100000000)
            campo.setSuffix(" Hz")
        self.campo_inferior.setObjectName("low_cutoff")
        self.campo_superior.setObjectName("high_cutoff")
        if cortes is not None:
            self.campo_inferior.setValue(cortes[0])
            self.campo_superior.setValue(cortes[1])
        formulario.addRow("Low cutoff — corte inferior:", self.campo_inferior)
        formulario.addRow("High cutoff — corte superior:", self.campo_superior)
        layout.addLayout(formulario)

        limite = QLabel(
            f"Amostragem: {fs:g} Hz.\n"
            f"Use 0 < corte inferior < corte superior < {fs / 2:g} Hz."
        )
        limite.setWordWrap(True)
        layout.addWidget(limite)

        self.botao_aplicar = QPushButton("Aplicar")
        self.botao_aplicar.setDefault(True)
        self.botao_desativar = QPushButton("Desativar passa-banda")
        self.botao_desativar.setEnabled(cortes is not None)
        self.botao_cancelar = QPushButton("Cancelar")
        self.botao_cancelar.clicked.connect(self.reject)
        linha = QHBoxLayout()
        linha.addWidget(self.botao_desativar)
        linha.addStretch()
        linha.addWidget(self.botao_cancelar)
        linha.addWidget(self.botao_aplicar)
        layout.addLayout(linha)

    def cortes(self):
        return self.campo_inferior.value(), self.campo_superior.value()
