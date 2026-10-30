from PySide6.QtWidgets import (
    QGridLayout, QMainWindow, QWidget, QFrame, QHBoxLayout, QVBoxLayout,
    QLabel, QCheckBox, QPushButton, QDoubleSpinBox, QMenu, QSpinBox, QMessageBox, QFileDialog, QScrollArea
)
from pathlib import Path
from datetime import datetime
import matplotlib as mpl
from matplotlib.figure import Figure
from matplotlib.backends.backend_svg import FigureCanvasSVG
from controle_filtros import ControleFiltros
from processamento import Processamento
from exportacao_html import criar_figura_html, ler_inicio_lynx
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

        acao_svg.triggered.connect(self.exportar_svg)
        acao_html.triggered.connect(self.exportar_html)

        self.exportar.setText("Exportar")
        self.exportar.setMenu(self.menu_exportar)

        self.criar_graficos(layout_direito)

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

    def exportar_svg(self):
        if getattr(self, "df_sensores", None) is None:
            QMessageBox.information(
                self,
                "Exportação",
                "Abra um arquivo primeiro."
            )
            return

        # Extensometria: um gráfico.
        # Acelerometria: os três gráficos dos eixos.
        if isinstance(self.grafico, pg.PlotWidget):
            plots = [self.grafico.getPlotItem()]
        else:
            plots = list(self.graficos_eixos.values())

        # Exporta somente as curvas que estão selecionadas.
        selecionadas = [
            [
                curva
                for curva in plot.listDataItems()
                if curva.isVisible()
            ]
            for plot in plots
        ]

        if not any(selecionadas):
            QMessageBox.information(
                self,
                "Exportação",
                "Selecione pelo menos um canal."
            )
            return

        pasta = QFileDialog.getExistingDirectory(
            self,
            "Escolha a pasta para salvar o SVG"
        )

        if not pasta:
            return

        nome = (
            f"grafico_{datetime.now():%Y%m%d_%H%M%S_%f}.svg"
        )
        caminho = Path(pasta) / nome

        figura = None

        try:
            # Preserva os pontos das curvas e desenha as letras
            # como vetores, sem depender das fontes de outro PC.
            with mpl.rc_context({"path.simplify": False, "svg.fonttype": "path"}):
                figura = Figure(figsize=(12, 4 * len(plots)), layout="constrained")

                descricao = getattr(self, "descricao_exportacao", "")
                if descricao:
                    figura.suptitle(descricao, fontsize=10)

                FigureCanvasSVG(figura)

                eixos = figura.subplots(nrows=len(plots), ncols=1,
                squeeze=False
                )

                for linha, (plot, curvas) in enumerate(zip(plots, selecionadas)):
                    eixo = eixos[linha, 0]

                    eixo_x = plot.getAxis("bottom")
                    eixo_y = plot.getAxis("left")

                    # Mantém a escala logarítmica, se estiver ativa.
                    if eixo_x.logMode:
                        eixo.set_xscale("log")

                    if eixo_y.logMode:
                        eixo.set_yscale("log")

                    for curva in curvas:
                        # Dados completos enviados à curva:
                        # já incluem os tratamentos e o RMS, se ativo.
                        x, y = curva.getOriginalDataset()

                        if x is None or y is None or len(x) == 0:
                            continue

                        cor = pg.mkPen(curva.opts["pen"]).color()

                        eixo.plot(
                            x,
                            y,
                            label=curva.name() or "Canal",
                            color=cor.name(),
                            alpha=cor.alphaF(),
                            linewidth=0.8,
                            rasterized=False
                        )

                    rotulo_x = eixo_x.labelText or "Tempo"
                    rotulo_y = eixo_y.labelText or "Valor"

                    if eixo_x.labelUnits:
                        rotulo_x += f" ({eixo_x.labelUnits})"

                    if eixo_y.labelUnits:
                        rotulo_y += f" ({eixo_y.labelUnits})"

                    eixo.set_xlabel(rotulo_x)
                    eixo.set_ylabel(rotulo_y)

                    eixo.set_title(
                        plot.titleLabel.text or self.windowTitle()
                    )

                    eixo.grid(True, alpha=0.25)

                    faixa_x, faixa_y = plot.viewRange()
                    eixo.set_xlim([10 ** v for v in faixa_x] if eixo_x.logMode else faixa_x)
                    eixo.set_ylim([10 ** v for v in faixa_y] if eixo_y.logMode else faixa_y)

                    if eixo.lines:
                        eixo.legend(
                            loc="upper left",
                            ncol=4,
                            fontsize=8
                        )

                figura.savefig(str(caminho), format="svg")

        except Exception as erro:
            QMessageBox.warning(self, "Falha ao exportar SVG", str(erro))
            return

        finally:
            if figura is not None:
                figura.clear()

        self.statusBar().showMessage(f"SVG salvo em: {caminho}")

        QMessageBox.information(self, "Exportação concluída", f"Arquivo salvo em:\n{caminho}")


    def exportar_html(self):
        if getattr(self, "df_sensores", None) is None:
            QMessageBox.information(
                self,
                "Exportação",
                "Abra um arquivo primeiro.",
            )
            return

        # Extensometria: um gráfico.
        # Acelerometria: os três gráficos dos eixos.
        if isinstance(self.grafico, pg.PlotWidget):
            plots = [self.grafico.getPlotItem()]
        else:
            plots = list(self.graficos_eixos.values())

        tem_selecao = any(
            curva.isVisible()
            for plot in plots
            for curva in plot.listDataItems()
        )

        if not tem_selecao:
            QMessageBox.information(
                self,
                "Exportação",
                "Selecione pelo menos um canal.",
            )
            return

        pasta = QFileDialog.getExistingDirectory(
            self,
            "Escolha a pasta para salvar o HTML interativo",
        )

        if not pasta:
            return

        nome = f"grafico_{datetime.now():%Y%m%d_%H%M%S_%f}.html"
        caminho = Path(pasta) / nome

        try:
            if hasattr(self, "inicio_exportacao"):
                inicio = self.inicio_exportacao
            else:
                inicio = ler_inicio_lynx(getattr(self, "caminho_atual", None))

            figura = criar_figura_html(
                plots,
                inicio=inicio,
                titulo=self.windowTitle(),
                descricao=getattr(self, "descricao_exportacao", ""),
            )

            figura.write_html(
                str(caminho),
                include_plotlyjs=True,
                full_html=True,
                auto_open=False,
                config={
                    "scrollZoom": True,
                    "displaylogo": False,
                    "responsive": True,
                },
            )

        except Exception as erro:
            QMessageBox.warning(
                self,
                "Falha ao exportar HTML",
                str(erro),
            )
            return

        self.statusBar().showMessage(
            f"HTML salvo em: {caminho}"
        )

        QMessageBox.information(
            self,
            "Exportação concluída",
            f"Arquivo salvo em:\n{caminho}\n\n"
            "Abra esse arquivo no navegador para consultar "
            "os valores passando o mouse sobre as curvas.",
        )


