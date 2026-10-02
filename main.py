#QApplication: é responsável por gerenciar a aplicação Qt, incluindo a inicialização e o loop de eventos.
#QWidget: é a classe base para todos os widgets do Qt, que são os elementos da interface gráfica do usuário (GUI).
#QLabel: é um widget que exibe texto ou imagens.
#QPushButton: é um widget que representa um botão clicável.
#QVBoxLayout: é um gerenciador de layout que organiza os widgets verticalmente.
#Qmenu: é um widget que representa um menu suspenso nas nossas opções
#Qpixmap: é uma classe que representa uma imagem em memória, que pode ser exibida em um QLabel ou outros widgets.

import sys
from PySide6.QtWidgets import QMenu, QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QGridLayout
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

app = QApplication(sys.argv)  

# Cria uma instância de um widget, que será a janela principal da aplicação
janela = QWidget()  
janela.setWindowTitle("ISQ_Analysys")  
janela.resize(1000, 600)  
layout = QVBoxLayout(janela)  
layout.setContentsMargins(30, 25, 30, 25)
layout.setSpacing(15)

#Adiciona o logo da empresa na tela
caminho_logo = Path(__file__).resolve().parent / "logo_isq.png"
imagem_logo = QPixmap(str(caminho_logo))
imagem_logo = imagem_logo.scaled(220, 220, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
logo = QLabel()
logo.setPixmap(imagem_logo)
layout.addWidget(logo, 0, Qt.AlignmentFlag.AlignHCenter)

#Adiciona o título da tela
titulo = QLabel("Selecione sua placa")  
titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
layout.addWidget(titulo)  
grade = QGridLayout()

#Criação dos botões para cada placa
botao_lynx = QPushButton("Lynx")  
grade.addWidget(botao_lynx, 0, 0)  
botão_aeron = QPushButton("Aeron")
grade.addWidget(botão_aeron, 0, 1)
botão_national = QPushButton("National")
grade.addWidget(botão_national, 1, 0)
botão_isq = QPushButton("ISQ")
grade.addWidget(botão_isq, 1, 1)
grade.setHorizontalSpacing(20)
grade.setVerticalSpacing(20)
layout.addLayout(grade)

janela.show()  

sys.exit(app.exec())




