"""Identificação visível do horário e definição manual quando o cabeçalho falha."""
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QInputDialog, QMessageBox

from isq_dataanalysys.leitores.metadados import interpretar_data_hora
from isq_dataanalysys.processamento.tempo import inicio_local


class PainelReferenciaTemporal(QWidget):
    alterado = Signal(object)

    def __init__(self, permitir_edicao=True):
        super().__init__()
        self.info = {}
        self.permitir_edicao = permitir_edicao
        linha = QHBoxLayout(self)
        linha.setContentsMargins(0, 0, 0, 0)
        self.rotulo = QLabel()
        self.rotulo.setTextFormat(Qt.TextFormat.PlainText)
        self.rotulo.setWordWrap(True)
        linha.addWidget(self.rotulo, 1)
        if permitir_edicao:
            self.botao_definir = QPushButton("Definir horário…")
            self.botao_definir.clicked.connect(self.definir_horario)
            linha.addWidget(self.botao_definir)
            self.botao_detalhes = QPushButton("Detalhes do horário")
            self.botao_detalhes.clicked.connect(self.mostrar_detalhes)
            linha.addWidget(self.botao_detalhes)
        self.hide()

    def atualizar(self, info):
        self.info = info.copy()
        inicio = info.get("inicio")
        if inicio is None:
            texto = "Data/hora não reconhecida; eixo em segundos."
            if self.permitir_edicao:
                texto += " Consulte os detalhes ou defina o horário original do CSV."
            self.rotulo.setText(texto)
            self.rotulo.setStyleSheet("color: #845200;")
        else:
            self.rotulo.setText(f"Início CSV: {inicio:%d/%m/%Y %H:%M:%S} → "
                                f"local: {inicio_local(inicio):%d/%m/%Y %H:%M:%S} (−3 h)")
            self.rotulo.setStyleSheet("")
        self.rotulo.setToolTip(self.detalhes() if self.permitir_edicao else "")
        self.show()

    def detalhes(self):
        return (f"Campo: {self.info.get('etiqueta', '')!r}\n"
                f"Valor lido: {self.info.get('valor', '')!r}\n"
                f"Linha do cabeçalho: {self.info.get('linha')}\n"
                f"Resultado: {self.info.get('erro') or 'Horário reconhecido.'}\n\n"
                "A conversão usa o horário registrado menos três horas, sem alterar o CSV.")

    def mostrar_detalhes(self):
        QMessageBox.information(self, "Referência temporal do CSV", self.detalhes())

    def definir_horario(self):
        inicio = self.info.get("inicio")
        texto = inicio.strftime("%d/%m/%Y %H:%M:%S.%f") if inicio else self.info.get("valor", "")
        valor, aceito = QInputDialog.getText(self, "Horário original da medição",
            "Informe a data/hora ORIGINAL do CSV (DD/MM/AAAA HH:MM:SS).\n"
            "O programa descontará três horas automaticamente.", text=texto)
        if not aceito:
            return
        inicio = interpretar_data_hora(valor)
        if inicio is None:
            QMessageBox.warning(self, "Data/hora inválida", "Informe uma data e hora válidas, por exemplo: 27/10/2026 14:45:00.")
            return
        self.atualizar(dict(inicio=inicio, etiqueta="Definido pelo usuário", valor=valor, linha=None, erro=""))
        self.alterado.emit(inicio)
