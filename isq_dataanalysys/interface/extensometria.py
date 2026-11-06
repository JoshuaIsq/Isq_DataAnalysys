from pathlib import Path
from isq_dataanalysys import __version__

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
    QHBoxLayout, QLabel, QMessageBox, QPushButton,
)

from isq_dataanalysys.interface.base import Tela
from isq_dataanalysys.leitores.lynx import aviso_unidades, LinhaFinalIncompleta
from isq_dataanalysys.leitores.extensometria import ler_lynx_extensometria
from isq_dataanalysys.interface.eixo_temporal import EixoDataHora


class TelaLynxExtensometria(Tela):
    CORES = [
        "#1565C0", "#D55E00", "#18864B", "#8E44AD",
        "#A6761D", "#444444", "#009E73", "#E69F00",
        "#CC79A7", "#0072B2", "#882255", "#44AA99",
        "#AA4499", "#999933", "#332288", "#661100",
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Análise de dados - Lynx Extensometria — v{__version__}")
        self.tempo = None
        self.df_original = None
        self.df_sensores = None
        self.mapa_canais = {}
        self.curvas_ext = {}
        self.info_arquivo = {}
        self.caminho_atual = None
        self.inicio_arquivo = None
        self.unidade_visual = None
        self.limites_visualizacao = {}
        self.criar_checkboxes_extensometria()
        self.criar_controles_visualizacao()
        self.rotulo_arquivo = QLabel("Abra um CSV para selecionar canais de tensão ou deformação.")
        self.rotulo_arquivo.setWordWrap(True)
        self.layout_controles.addWidget(self.rotulo_arquivo, 7, 0, 1, 4)
        self.abrir.clicked.connect(self.carregar_arquivo_lynx)

    def criar_graficos(self, layout_direito):
        self.grafico = pg.PlotWidget(background="w", axisItems={"bottom": EixoDataHora(orientation="bottom")})
        self.grafico.setLabel("bottom", "Tempo", units="s")
        self.grafico.setLabel("left", "Medição")
        self.grafico.showGrid(x=True, y=True, alpha=0.25)
        self.grafico.addLegend(colCount=4, offset=(10, 5), labelTextColor="#333333")
        self.grafico.setDownsampling(auto=True, mode="peak")
        self.grafico.setClipToView(True)
        for lado in ("left", "bottom"):
            self.grafico.getAxis(lado).enableAutoSIPrefix(False)
            self.grafico.getAxis(lado).setPen("#555555")
            self.grafico.getAxis(lado).setTextPen("#333333")
        layout_direito.addWidget(self.grafico, 1)

    def criar_checkboxes_extensometria(self):
        for checkbox in self.checkboxes_canais.values():
            self.layout_canais.removeWidget(checkbox)
            checkbox.hide()
            checkbox.deleteLater()
        self.checkboxes_canais = {}
        for numero, nome in self.mapa_canais.items():
            unidade = self.info_arquivo['unidades'][numero]
            aviso = self.info_arquivo['qualidade'].get(numero)
            checkbox = QCheckBox(f"Canal {numero} — {nome} ({unidade})" + (" *" if aviso else ""))
            checkbox.setChecked(True)
            checkbox.setToolTip(f"Canal {numero} — {nome} ({unidade})\n" +
                                (aviso or "A marca controla a exibição deste canal."))
            checkbox.toggled.connect(self.atualizar_visibilidade)
            self.layout_canais.insertWidget(self.layout_canais.count() - 1, checkbox)
            self.checkboxes_canais[numero] = checkbox

    def criar_controles_visualizacao(self):
        modos = QHBoxLayout()
        self.botao_tensao = QPushButton("Tensão (MPa)")
        self.botao_deformacao = QPushButton("Deformação")
        self.grupo_modos = QButtonGroup(self)
        for botao in (self.botao_tensao, self.botao_deformacao):
            botao.setCheckable(True)
            botao.setEnabled(False)
            self.grupo_modos.addButton(botao)
            modos.addWidget(botao)
            botao.clicked.connect(self.mudar_visualizacao)
        self.unidade_deformacao = QComboBox()
        self.unidade_deformacao.addItems(["μm/m", "mm/m"])
        self.unidade_deformacao.setEnabled(False)
        self.unidade_deformacao.currentIndexChanged.connect(self.mudar_visualizacao)
        modos.addWidget(self.unidade_deformacao)
        modos.addStretch()
        self.layout_controles.addLayout(modos, 4, 0, 1, 4)

        self.campo_y_min = self.campo_limite()
        self.campo_y_max = self.campo_limite()
        self.campo_tempo_inicio = self.campo_limite(" s")
        self.campo_tempo_fim = self.campo_limite(" s")
        linha = QHBoxLayout()
        for texto, campo in (("Escala mínima:", self.campo_y_min), ("máxima:", self.campo_y_max),
                             ("Tempo inicial:", self.campo_tempo_inicio), ("final:", self.campo_tempo_fim)):
            linha.addWidget(QLabel(texto))
            linha.addWidget(campo)
        self.layout_controles.addLayout(linha, 5, 0, 1, 4)
        botoes = QHBoxLayout()
        self.botao_aplicar_visualizacao = QPushButton("Aplicar escala e tempo")
        self.botao_ajustar = QPushButton("Ajustar aos dados")
        self.botao_aplicar_visualizacao.clicked.connect(self.aplicar_visualizacao)
        self.botao_ajustar.clicked.connect(self.ajustar_aos_dados)
        for botao in (self.botao_aplicar_visualizacao, self.botao_ajustar):
            botao.setEnabled(False)
            botoes.addWidget(botao)
        botoes.addStretch()
        self.layout_controles.addLayout(botoes, 6, 0, 1, 4)

    @staticmethod
    def campo_limite(sufixo=""):
        campo = QDoubleSpinBox()
        campo.setDecimals(9)
        campo.setRange(-1e100, 1e100)
        campo.setSuffix(sufixo)
        campo.setEnabled(False)
        return campo

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
        tempo, canais, mapa, info = ler_lynx_extensometria(caminho, ignorar_ultima_incompleta)
        # Só substitui o arquivo atual depois de validar a nova importação.
        self.tempo = tempo
        self.df_original = canais.copy()
        self.df_sensores = canais.copy()
        self.mapa_canais = mapa
        self.info_arquivo = info
        self.caminho_atual = Path(caminho)
        self.carregar_referencia_temporal(caminho)
        self.config_filtros = {}
        self.info_processamento = {"fs": info["fs"], "substituicoes": {}}
        self.grafico.clear()
        self.curvas_ext.clear()
        self.criar_checkboxes_extensometria()
        unidades = set(info["unidades"].values())
        self.botao_tensao.setEnabled("MPa" in unidades)
        self.botao_deformacao.setEnabled(bool(unidades - {"MPa"}))
        self.unidade_deformacao.blockSignals(True)
        self.unidade_deformacao.setCurrentText("μm/m" if "μm/m" in unidades else "mm/m")
        self.unidade_deformacao.blockSignals(False)
        (self.botao_tensao if "MPa" in unidades else self.botao_deformacao).setChecked(True)
        for campo in (self.campo_y_min, self.campo_y_max, self.campo_tempo_inicio, self.campo_tempo_fim):
            campo.setEnabled(True)
        for campo in (self.campo_tempo_inicio, self.campo_tempo_fim):
            campo.setRange(float(tempo[0]), float(tempo[-1]))
        self.botao_aplicar_visualizacao.setEnabled(True)
        self.botao_ajustar.setEnabled(True)
        self.unidade_visual = None
        self.limites_visualizacao.clear()
        mensagens = info["avisos"] + [f"Canal {n} *: {aviso}." for n, aviso in info["qualidade"].items()]
        self.rotulo_arquivo.setText("\n".join(mensagens) or "Selecione Tensão ou Deformação e os canais que deseja analisar.")
        self.atualizar_indicacao_filtros()
        self.mudar_visualizacao()
        aviso = aviso_unidades(info, "extensometria")
        if aviso:
            QMessageBox.warning(self, "Canais de outra medição", aviso)
        return True

    def canal_no_modo(self, numero):
        unidade = self.info_arquivo["unidades"][numero]
        return (unidade == "MPa") == (self.unidade_visual == "MPa")

    def valores_visuais(self, numero):
        valores = self.df_sensores[numero].to_numpy()
        origem = self.info_arquivo["unidades"][numero]
        if origem == "mm/m" and self.unidade_visual == "μm/m":
            return valores * 1000
        if origem == "μm/m" and self.unidade_visual == "mm/m":
            return valores / 1000
        return valores

    def mudar_visualizacao(self, *args):
        if self.df_sensores is None:
            return
        if self.unidade_visual is not None:
            self.limites_visualizacao[self.unidade_visual] = self.grafico.viewRange()
        self.unidade_visual = "MPa" if self.botao_tensao.isChecked() else self.unidade_deformacao.currentText()
        self.unidade_deformacao.setEnabled(self.unidade_visual != "MPa")
        rotulo = "Tensão mecânica" if self.unidade_visual == "MPa" else "Deformação"
        self.grafico.setLabel("left", rotulo, units=self.unidade_visual)
        self.grafico.setTitle(f"{rotulo} — sinal no tempo", color="#333333")
        self.atualizar_graficos()
        limites = self.limites_visualizacao.get(self.unidade_visual)
        if limites is None:
            self.ajustar_aos_dados()
        else:
            self.definir_limites(*limites)

    def atualizar_graficos(self):
        if self.df_sensores is None:
            return
        for numero, nome in self.mapa_canais.items():
            if numero not in self.curvas_ext:
                self.curvas_ext[numero] = self.grafico.plot(
                    pen=pg.mkPen(self.CORES[(numero - 1) % len(self.CORES)], width=1),
                    name=f"Canal {numero} — {nome}",
                )
            if self.canal_no_modo(numero):
                self.curvas_ext[numero].setData(self.tempo, self.valores_visuais(numero))
        self.atualizar_visibilidade()

    def atualizar_visibilidade(self):
        legenda = self.grafico.getPlotItem().legend
        for numero, curva in self.curvas_ext.items():
            ativo = self.canal_no_modo(numero)
            checkbox = self.checkboxes_canais[numero]
            checkbox.setEnabled(ativo)
            curva.setVisible(ativo and checkbox.isChecked())
            if ativo and legenda.getLabel(curva) is None:
                legenda.addItem(curva, curva.name())
            elif not ativo:
                legenda.removeItem(curva)
        if self.df_sensores is not None:
            selecionados = sum(self.canal_no_modo(n) and self.checkboxes_canais[n].isChecked() for n in self.mapa_canais)
            self.statusBar().showMessage(
                f"{self.caminho_atual.name} | {self.info_arquivo['fs']:g} Hz | "
                f"{len(self.tempo)} amostras | {len(self.mapa_canais)} canais compatíveis | "
                f"{selecionados} selecionados neste modo | {self.unidade_visual}"
            )

    def definir_limites(self, tempo, escala):
        for campo, valor in zip((self.campo_tempo_inicio, self.campo_tempo_fim, self.campo_y_min, self.campo_y_max),
                                (*tempo, *escala)):
            campo.setValue(float(valor))
        self.grafico.setRange(xRange=tempo, yRange=escala, padding=0, disableAutoRange=True)
        self.limites_visualizacao[self.unidade_visual] = [list(tempo), list(escala)]

    def aplicar_visualizacao(self):
        if self.df_sensores is None:
            return
        tempo = [self.campo_tempo_inicio.value(), self.campo_tempo_fim.value()]
        escala = [self.campo_y_min.value(), self.campo_y_max.value()]
        if tempo[0] >= tempo[1] or escala[0] >= escala[1]:
            QMessageBox.warning(self, "Limites inválidos", "O início deve ser menor que o fim e a escala mínima deve ser menor que a máxima.")
            return False
        self.definir_limites(tempo, escala)
        return True

    def ajustar_aos_dados(self):
        if self.df_sensores is None:
            return
        series = [self.valores_visuais(n) for n in self.mapa_canais
                  if self.canal_no_modo(n) and self.checkboxes_canais[n].isChecked()]
        if not series:
            return
        minimo = min(float(np.min(v)) for v in series)
        maximo = max(float(np.max(v)) for v in series)
        margem = max((maximo - minimo) * 0.05, abs(maximo) * 1e-6, 1e-9)
        self.definir_limites([float(self.tempo[0]), float(self.tempo[-1])], [minimo - margem, maximo + margem])
