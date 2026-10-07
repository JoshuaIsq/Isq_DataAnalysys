from PySide6.QtWidgets import (
    QMainWindow, QWidget, QFrame, QHBoxLayout, QVBoxLayout,
    QLabel, QCheckBox, QPushButton, QDoubleSpinBox, QMenu
)

from controle_filtros import ControleFiltros

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

        self.calibração = ControleFiltros("Fator de calibração")
        layout_controles.addWidget(self.calibração)
        self.calibração.botao.clicked.connect(self.registrar_calibracao)

        layout_controles.addStretch()
        layout_direito.addWidget(painel_controles)

        menu_exportar = QMenu()
        menu_exportar.addAction(self.exportar_graf)
        menu_exportar.addAction(self.exportar_dados)
        self.exportar.setMenu(menu_exportar)

        self.grafico = pg.PlotWidget()
        self.grafico.setBackground("w")
        self.grafico.setLabel("bottom", "Tempo", units="s")
        self.grafico.setLabel("left", "Valor")
        self.grafico.showGrid(x=True, y=True, alpha=0.25)

        layout_direito.addWidget(self.grafico, 1)

    def registrar_calibracao(self):
        self.fator_calibracao = self.calibração.campo.value()

        self.statusBar().showMessage(f"Fator selecionado: {self.fator_calibracao}")





