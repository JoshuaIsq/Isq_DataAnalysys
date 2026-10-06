import sys
from PySide6.QtWidgets import QApplication
from tela import Tela

app = QApplication(sys.argv)

janela = Tela()
janela.show()

sys.exit(app.exec())