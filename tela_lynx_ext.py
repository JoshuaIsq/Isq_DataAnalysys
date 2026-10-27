from pathlib import Path
import pyqtgraph as pg
from PySide6.QtWidgets import QCheckBox, QFileDialog, QLabel, QMessageBox
from tela import Tela
from leitor_lynx_ext import ler_lynx_extensometria, LinhaFinalIncompleta


class TelaLynxExtensometria(Tela):
    CORES = [
        "#1565C0", "#D55E00", "#18864B", "#8E44AD",
        "#A6761D", "#444444", "#009E73", "#E69F00",
        "#CC79A7", "#0072B2", "#882255", "#44AA99",
        "#AA4499", "#999933", "#332288", "#661100",
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Análise de dados - Lynx Extensometria")
        self.tempo = None
        self.df_original = None
        self.df_sensores = None
        self.mapa_canais = {}
        self.curvas_ext = {}
        self.info_arquivo = {}
        self.caminho_atual = None

        self.criar_checkboxes_extensometria()
        self.rotulo_arquivo = QLabel("Abra um arquivo. Azul indica canal presente; * indica aviso.")
        self.rotulo_arquivo.setWordWrap(True)
        self.layout_controles.addWidget(self.rotulo_arquivo, 4, 0, 1, 4)
        self.abrir.clicked.connect(self.carregar_arquivo_lynx)
        self.abrir_arquivo.triggered.connect(self.carregar_arquivo_lynx)

    def criar_graficos(self, layout_direito):
        self.grafico = pg.PlotWidget(background="w")
        self.grafico.setLabel("bottom", "Tempo", units="s")
        self.grafico.setLabel("left", "Medição")
        self.grafico.showGrid(x=True, y=True, alpha=0.25)
        self.grafico.addLegend(colCount=4, offset=(10, 5), labelTextColor="#333333")
        self.grafico.setDownsampling(auto=True, mode="peak")
        self.grafico.setClipToView(True)
        self.grafico.getAxis("left").enableAutoSIPrefix(False)
        for lado in ("left", "bottom"):
            self.grafico.getAxis(lado).enableAutoSIPrefix(False)
            self.grafico.getAxis(lado).setPen("#555555")
            self.grafico.getAxis(lado).setTextPen("#333333")
        layout_direito.addWidget(self.grafico, 1)

    def criar_checkboxes_extensometria(self):
        # Substitui somente os quatro checkboxes provisórios da tela geral.
        for checkbox in self.checkboxes_canais.values():
            self.layout_canais.removeWidget(checkbox)
            checkbox.hide()
            checkbox.deleteLater()
        self.checkboxes_canais = {}
        for numero in range(1, 17):
            checkbox = QCheckBox(f"Canal {numero}")
            checkbox.setChecked(False)
            checkbox.setEnabled(False)
            checkbox.setStyleSheet("QCheckBox { color: #777777; }")
            checkbox.toggled.connect(self.atualizar_visibilidade)
            # Insere antes do espaço elástico no final da coluna.
            self.layout_canais.insertWidget(self.layout_canais.count() - 1, checkbox)
            self.checkboxes_canais[numero] = checkbox

    def carregar_arquivo_lynx(self):
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Abrir extensometria Lynx", "", "Arquivos CSV (*.csv)"
        )
        if not caminho:
            return
        try:
            try:
                self.importar_caminho(caminho)
            except LinhaFinalIncompleta as erro:
                resposta = QMessageBox.question(
                    self, "Última linha incompleta",
                    str(erro) + "\n\nDeseja tentar abrir ignorando somente essa última linha?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if resposta == QMessageBox.StandardButton.Yes:
                    self.importar_caminho(caminho, ignorar_ultima_incompleta=True)
        except (OSError, ValueError) as erro:
            QMessageBox.warning(self, "Falha ao importar", str(erro))

    def importar_caminho(self, caminho, ignorar_ultima_incompleta=False):
        tempo, canais, mapa, info = ler_lynx_extensometria(
            caminho, ignorar_ultima_incompleta=ignorar_ultima_incompleta
        )
        # A troca de arquivo só ocorre depois de a leitura e a validação terminarem.
        self.tempo = tempo
        self.df_original = canais.copy()
        self.df_sensores = canais.copy()
        self.mapa_canais = mapa
        self.info_arquivo = info
        self.caminho_atual = Path(caminho)
        self.config_filtros = {}
        self.info_processamento = {"fs": info["fs"], "substituicoes": {}}
        self.grafico.clear()
        self.curvas_ext.clear()

        for numero, checkbox in self.checkboxes_canais.items():
            presente = numero in mapa
            aviso = info["qualidade"].get(numero)
            checkbox.blockSignals(True)
            checkbox.setText(f"Canal {numero}" + (" *" if aviso else ""))
            checkbox.setEnabled(presente)
            checkbox.setChecked(presente)
            cor = "#1565C0" if presente else "#777777"
            checkbox.setStyleSheet(f"QCheckBox {{ color: {cor}; }}")
            texto = "Presente no arquivo" if presente else "Ausente neste arquivo"
            if aviso:
                texto += "\n" + aviso
            checkbox.setToolTip(texto)
            checkbox.blockSignals(False)

        mensagens = ["Azul: canal presente; a marca controla sua exibição."] + info["avisos"]
        for numero, aviso in info["qualidade"].items():
            mensagens.append(f"Canal {numero} *: {aviso}.")
        self.rotulo_arquivo.setText("\n".join(mensagens))
        unidade = info["unidade"]
        rotulo = "Tensão mecânica" if unidade == "MPa" else "Medição"
        self.grafico.setLabel("left", rotulo, units=unidade)
        self.atualizar_indicacao_filtros()
        self.atualizar_graficos()
        # Ajusta automaticamente apenas o eixo do tempo.
        self.grafico.enableAutoRange(axis="x", enable=True)

    def atualizar_graficos(self):
        if self.df_sensores is None:
            return
        for numero, nome in self.mapa_canais.items():
            if numero not in self.curvas_ext:
                self.curvas_ext[numero] = self.grafico.plot(
                    pen=pg.mkPen(self.CORES[numero - 1], width=1),
                    name=f"Canal {numero}",
                )
            self.curvas_ext[numero].setData(
                self.tempo, self.df_sensores[nome].to_numpy()
            )
        self.atualizar_visibilidade()

    def atualizar_visibilidade(self):
        for numero, curva in self.curvas_ext.items():
            curva.setVisible(self.checkboxes_canais[numero].isChecked())
        # A cor do checkbox não é alterada: presença e seleção são estados separados.
        self.grafico.enableAutoRange(axis="y", enable=False)
        self.grafico.setYRange(-50, 50, padding=0)
        if self.df_sensores is not None:
            selecionados = sum(self.checkboxes_canais[n].isChecked() for n in self.mapa_canais)
            self.statusBar().showMessage(
                f"{self.caminho_atual.name} | {self.info_arquivo['fs']:g} Hz | "
                f"{len(self.tempo)} amostras | {len(self.mapa_canais)} canais presentes | "
                f"{selecionados} selecionados | {self.info_arquivo['unidade']}"
            )