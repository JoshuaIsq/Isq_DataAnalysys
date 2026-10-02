import sys
from PySide6.QtWidgets import QApplication, QWidget

#A bilbioteca QApplication é responsável por gerenciar a aplicação Qt, incluindo a inicialização e o loop de eventos.
#A classe QWidget é a classe base para todos os widgets do Qt, que são os elementos da interface gráfica do usuário (GUI).

app = QApplication(sys.argv)  # Cria uma instância da aplicação Qt, passando os argumentos da linha de comando.

janela = QWidget()  # Cria uma instância de um widget, que será a janela principal da aplicação.
janela.setWindowTitle("ISQ_Analysys")  
janela.resize(1000, 600)  
janela.show()  

sys.exit(app.exec())




