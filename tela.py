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