from PySide6.QtWidgets import (
    QGridLayout, QMainWindow, QWidget, QFrame, QHBoxLayout, QVBoxLayout,
    QLabel, QCheckBox, QPushButton, QMenu, QSpinBox, QMessageBox, QScrollArea
)
from isq_dataanalysys.interface.controles import ControleFiltros
from isq_dataanalysys.processamento.sinais import Processamento
import pyqtgraph as pg

from .exportacao import ExportacaoGraficos
from .referencia_temporal import PainelReferenciaTemporal
from .eixo_temporal import configurar_eixo_temporal
from isq_dataanalysys.leitores.metadados import ler_referencia_temporal


class Tela(ExportacaoGraficos, QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Analise de dados")
        self.resize(1000, 600)

        self.statusBar().showMessage("Nenhum arquivo carregado")

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
        self.layout_canais = layout_canais
        layout_canais.addWidget(QLabel("<b>Canais</b>"))

        self.checkboxes_canais = {}

        for n in range(1, 5):
            checkbox = QCheckBox(f"Canal {n}")
            checkbox.setChecked(True)
            self.checkboxes_canais[n] = checkbox
            layout_canais.addWidget(checkbox)

        layout_canais.addStretch()
        rolagem_canais = QScrollArea()
        rolagem_canais.setWidgetResizable(True)
        rolagem_canais.setWidget(painel_canais)
        rolagem_canais.setMinimumWidth(240)
        layout_principal.addWidget(rolagem_canais)

        painel_direito = QWidget()
        layout_direito = QVBoxLayout(painel_direito)
        layout_direito.setContentsMargins(0, 0, 0, 0)
        layout_direito.setSpacing(12)

        layout_principal.addWidget(painel_direito, 1)

        #Painel superior com botões de abrir e exportar
        painel_controles = QFrame()
        painel_controles.setFrameShape(QFrame.Shape.StyledPanel)
        layout_controles = QGridLayout(painel_controles)
        self.layout_controles = layout_controles
        layout_controles.setHorizontalSpacing(20)
        layout_controles.setVerticalSpacing(10)
        self.abrir = QPushButton("Abrir arquivo")
        self.exportar = QPushButton("Exportar gráfico")

        #Controle dos filtros e calibrações
        self.controle_calibração = ControleFiltros("Fator de calibração",
            valor_inicial=1.0)

        self.controle_offset = ControleFiltros("Offset",
            valor_inicial=0.0)

        self.controle_passa_baixa = ControleFiltros("Passa-baixa (Hz)",
            valor_inicial=0.0,)

        self.controle_passa_alta = ControleFiltros("Passa-alta (Hz)",
            valor_inicial=0.0,)

        self.controle_media_movel = ControleFiltros("Média móvel",
            valor_inicial=0.0)

        self.controle_outliers = ControleFiltros("Remover outliers",
            valor_inicial=0.0)

        layout_controles.addWidget(self.abrir, 0, 0)
        layout_controles.addWidget(self.exportar, 1, 0)

        # Segunda coluna: calibração e offset.
        layout_controles.addWidget(self.controle_calibração, 0, 2)
        layout_controles.addWidget(self.controle_offset, 1, 2)

        # Terceira coluna: passa-alta, passa-baixa e média móvel.
        layout_controles.addWidget(self.controle_passa_alta, 0, 3)
        layout_controles.addWidget(self.controle_passa_baixa, 1, 3)
        layout_controles.addWidget(self.controle_media_movel, 2, 3)

        # Quarta coluna: remoção de outliers.
        layout_controles.addWidget(self.controle_outliers, 0, 1)

        # Distribuição do espaço entre as colunas.
        layout_controles.setColumnStretch(0, 0)

        for coluna in range (1, 4):
            layout_controles.setColumnStretch(coluna, 1)

        self.botao_restaurar = QPushButton("Restaurar original")
        layout_controles.addWidget(self.botao_restaurar, 2, 0)
        self.botao_restaurar.clicked.connect(self.restaurar_original)
        bloco_janela = QVBoxLayout()
        self.campo_janela_outliers = QSpinBox()
        self.campo_janela_outliers.setRange(3, 10001)
        self.campo_janela_outliers.setSingleStep(2)
        self.campo_janela_outliers.setValue(31)
        bloco_janela.addWidget(self.campo_janela_outliers)
        bloco_janela.addWidget(QLabel("Janela de outliers (amostras)"))
        layout_controles.addLayout(bloco_janela, 1, 1)
        self.rotulo_ativos = QLabel("Tratamentos ativos: nenhum")
        self.rotulo_ativos.setWordWrap(True)
        layout_controles.addWidget(self.rotulo_ativos, 3, 0, 1, 4)

        layout_direito.addWidget(painel_controles)

        #Dicionario com os componentes da interface
        self.controles_filtros = {
            "calibracao": self.controle_calibração,
            "offset": self.controle_offset,
            "passa_alta": self.controle_passa_alta,
            "passa_baixa": self.controle_passa_baixa,
            "media_movel": self.controle_media_movel,
            "outliers": self.controle_outliers,
        }

        self.config_filtros = {}

        for nome, controle in self.controles_filtros.items():
            controle.botao.clicked.connect(lambda marcado=False,
                    chave=nome: self.registrar_parametro(chave))

        self.menu_exportar = QMenu(self.exportar)

        acao_svg = self.menu_exportar.addAction("SVG vetorial")
        acao_html = self.menu_exportar.addAction("HTML interativo")
        self.menu_exportar.addAction("CSV tratado").triggered.connect(self.exportar_csv)

        acao_svg.triggered.connect(self.exportar_svg)
        acao_html.triggered.connect(self.exportar_html)

        self.exportar.setText("Exportar")
        self.exportar.setMenu(self.menu_exportar)

        self.criar_graficos(layout_direito)
        self.painel_referencia = PainelReferenciaTemporal()
        self.layout_controles.addWidget(self.painel_referencia, 8, 0, 1, 4)
        self.painel_referencia.alterado.connect(self.definir_referencia_manual)

    def carregar_referencia_temporal(self, caminho):
        info = ler_referencia_temporal(caminho)
        self.inicio_arquivo = info["inicio"]
        self.painel_referencia.atualizar(info)
        self.atualizar_referencia_temporal()

    def definir_referencia_manual(self, inicio):
        self.inicio_arquivo = inicio
        self.atualizar_referencia_temporal()

    def atualizar_referencia_temporal(self):
        # Apenas rótulos e referência de exportação; dados, tratamentos e zoom são preservados.
        if isinstance(self.grafico, pg.PlotWidget):
            plots = [self.grafico.getPlotItem()]
        else:
            plots = list(self.graficos_eixos.values())
        botao_fft = getattr(self, "botao_fft", None)
        fft = botao_fft is not None and botao_fft.isChecked()
        for plot in plots:
            configurar_eixo_temporal(plot, None if fft else self.inicio_arquivo)
            if fft:
                plot.setLabel("bottom", "Frequência", units="Hz")

    def registrar_parametro(self, nome):
        if getattr(self, "df_original", None) is None:
            QMessageBox.information(self, "Tratamento", "Abra um arquivo primeiro.")
            return
        valor = self.controles_filtros[nome].campo.value()
        if nome in ("offset", "media_movel"):
            valor = int(valor)
        proposta = self.config_filtros.copy()
        proposta[nome] = valor
        if nome == "outliers":
            proposta["janela_outliers"] = self.campo_janela_outliers.value()
        self.aplicar_configuracao(proposta)

    def aplicar_configuracao(self, proposta):
        try:
            resultado, info = Processamento.aplicar(self.tempo, self.df_original, proposta)
        except ValueError as erro:
            QMessageBox.warning(self, "Parâmetro inválido", str(erro))
            return False
        self.df_sensores = resultado
        self.config_filtros = proposta.copy()
        self.info_processamento = info
        self.atualizar_indicacao_filtros()
        self.atualizar_graficos()
        return True

    def atualizar_indicacao_filtros(self):
        partes = []
        for nome in ("calibracao", "outliers", "offset", "passa_alta", "passa_baixa", "media_movel"):
            if nome in self.config_filtros:
                controle = self.controles_filtros[nome]
                partes.append(f"{controle.nome}: {self.config_filtros[nome]:g}{controle.campo.suffix()}")
        if "outliers" in self.config_filtros:
            partes.append(f"janela de outliers: {self.config_filtros['janela_outliers']} amostras")
        self.rotulo_ativos.setText("Tratamentos ativos: " + ("; ".join(partes) or "nenhum"))
        contagens = getattr(self, "info_processamento", {}).get("substituicoes", {})
        self.rotulo_ativos.setToolTip("\n".join(f"{canal}: {n} substituições" for canal, n in contagens.items()))

    def restaurar_original(self):
        if getattr(self, "df_original", None) is not None:
            self.aplicar_configuracao({})

    def atualizar_graficos(self):
        """Cada tela específica pode redefinir a apresentação dos canais."""
        self.grafico.clear()
        for numero, coluna in enumerate(self.df_sensores.columns):
            self.grafico.plot(self.tempo, self.df_sensores[coluna].to_numpy(), pen=pg.intColor(numero))

    def criar_graficos(self, layout_direito):
        self.grafico = pg.PlotWidget()
        self.grafico.setBackground('w')
        self.grafico.showGrid(x=True, y=True, alpha=0.25)
        self.grafico.setLabel('bottom', 'Tempo', units='s')
        self.grafico.setLabel('left', 'Valor')
        layout_direito.addWidget(self.grafico, 1)
