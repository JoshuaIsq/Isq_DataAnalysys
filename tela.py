from PySide6.QtWidgets import (
    QMainWindow, QWidget, QFrame, QHBoxLayout, QVBoxLayout,
    QLabel, QCheckBox, QPushButton, QDoubleSpinBox, QMenu
)

import pyqtgraph as pg

class Tela(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Analise de dados")
        self.resize(1000, 600)

        #criação dos menus responsaveis por ações 
        barra_menus = self.menuBar()
        menu_arquivo = barra_menus.addMenu("Arquivo")
        menu_filtros = barra_menus.addMenu("Filtros")
        menu_calibracao = barra_menus.addMenu("Calibração")

        #A ação que terá em cada menu
        self.abrir_arquivo = menu_arquivo.addAction("Abrir arquivo")
        self.exportar_graf = menu_arquivo.addAction("Exportar gráfico SVG")
        self.exportar_dados = menu_arquivo.addAction("Exportar dados CSV")

        self.passa_alta = menu_filtros.addAction("Passa-alta")
        self.passa_baixa = menu_filtros.addAction("Passa-baixa")

        self.calibração = menu_calibracao.addAction("Calibração")

        self.statusBar().showMessage("Nenhum arquivo carregado")

        barra_menus.hide() #Deixando oculto para add dps

        #Menu central onde será exibido o gráfico e os controles
        area_central = QWidget()
        self.setCentralWidget(area_central)
        layout_principal = QHBoxLayout(area_central)
        layout_principal.setContentsMargins(10, 10, 10, 10)
        layout_principal.setSpacing(10)

        #Menu lateral com os canais selecionados
        painel_canais = QFrame()
        painel_canais.setFrameShape(QFrame.Shape.StyledPanel)
        painel_canais.setFixedWidth(200)
        layout_canais = QVBoxLayout(painel_canais)
        layout_canais.addWidget(QLabel("<b>Canais</b>"))

        self.checkboxes_canais = {}

        for n in range(1, 5):
            checkbox = QCheckBox(f"Canal {n}")
            checkbox.setChecked(True)
            self.checkboxes_canais[n] = checkbox
            layout_canais.addWidget(checkbox)

        layout_canais.addStretch()
        layout_principal.addWidget(painel_canais)

        painel_direito = QWidget()
        layout_direito = QVBoxLayout(painel_direito)
        layout_direito.setContentsMargins(0, 0, 0, 0)
        layout_direito.setSpacing(12)

        layout_principal.addWidget(painel_direito, 1)
        
        #Painel superior com botões de abrir e exportar
        painel_controles = QFrame()
        painel_controles.setFrameShape(QFrame.Shape.StyledPanel)
        layout_controles = QHBoxLayout(painel_controles)
        self.abrir = QPushButton("Abrir arquivo")
        self.exportar = QPushButton("Exportar gráfico")
        coluna_arquivos = QVBoxLayout()
        coluna_arquivos.addWidget(self.abrir)
        coluna_arquivos.addWidget(self.exportar)

        layout_controles.addLayout(coluna_arquivos)

        self.botao_filtros = QPushButton("Filtros")
        self.botao_filtros.setMenu(menu_filtros)
        layout_controles.addWidget(self.botao_filtros)

        coluna_calibracao = QVBoxLayout()
        self.botao_calibracao = QPushButton("Fator de calibração")

        self.campo_calibracao = QDoubleSpinBox()
        self.campo_calibracao.setDecimals(8)
        self.campo_calibracao.setRange(0.00000001, 100000000)
        self.campo_calibracao.setValue(1.0)

        coluna_calibracao.addWidget(self.campo_calibracao)
        layout_controles.addLayout(coluna_calibracao)

        self.botao_aplicar = QPushButton("Aplicar")
        layout_controles.addWidget(self.botao_aplicar)

        layout_controles.addStretch()
        layout_direito.addWidget(painel_controles)



