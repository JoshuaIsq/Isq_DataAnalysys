#QApplication: é responsável por gerenciar a aplicação Qt, incluindo a inicialização e o loop de eventos.
#QWidget: é a classe base para todos os widgets do Qt, que são os elementos da interface gráfica do usuário (GUI).
#QLabel: é um widget que exibe texto ou imagens.
#QPushButton: é um widget que representa um botão clicável.
#QVBoxLayout: é um gerenciador de layout que organiza os widgets verticalmente.


import sys
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QVBoxLayout

app = QApplication(sys.argv)  

# Cria uma instância de um widget, que será a janela principal da aplicação
janela = QWidget()  
janela.setWindowTitle("ISQ_Analysys")  
janela.resize(1000, 600)  

layout = QVBoxLayout(janela)  # Cria um gerenciador de layout vertical
titulo = QLabel("Selecione sua placa")  # Cria um widget de rótulo (label) com o texto "ISQ_Analysys"
layout.addWidget(titulo)  # Adiciona o rótulo ao layout

#Criação dos botões para cada placa
botao_lynx = QPushButton("Lynx")  
layout.addWidget(botao_lynx)  
botão_aeron = QPushButton("Aeron")
layout.addWidget(botão_aeron)
botão_national = QPushButton("National")
layout.addWidget(botão_national)
botão_isq = QPushButton("ISQ")
layout.addWidget(botão_isq)

janela.show()  

sys.exit(app.exec())




