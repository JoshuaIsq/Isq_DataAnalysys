"""Análise dos deslocamentos medidos por réguas potenciométricas em mm."""

from pathlib import Path
import pyqtgraph as pg
from PySide6.QtWidgets import QCheckBox, QLabel, QMessageBox
from isq_dataanalysys import __version__
from isq_dataanalysys.leitores.regua import ler_lynx_regua
from isq_dataanalysys.leitores.lynx import aviso_unidades
from .base import Tela
from .eixo_temporal import EixoDataHora
from .visualizacao_temporal import VisualizacaoTemporal


class TelaLynxReguaPotenciometrica(VisualizacaoTemporal, Tela):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Análise de dados - Lynx Régua potenciométrica — v{__version__}")
        self.tempo = None
        self.df_original = None
        self.df_sensores = None
        self.mapa_canais = {}
        self.curvas_regua = {}
        self.info_arquivo = {}
        self.info_processamento = {}
        self.caminho_atual = None
        self.inicio_arquivo = None
        self.unidade_visual = "mm"
        self.limites_visualizacao = {}
        self.recriar_canais()
        self.criar_limites_visualizacao()
        self.rotulo_arquivo = QLabel("Abra um CSV para analisar os canais de deslocamento medido em mm.")
        self.rotulo_arquivo.setWordWrap(True)
        self.layout_controles.addWidget(self.rotulo_arquivo, 7, 0, 1, 4)
        self.abrir.clicked.connect(self.carregar_arquivo_lynx)
        self.statusBar().addPermanentWidget(QLabel(f"v{__version__}"))

    def criar_graficos(self, layout_direito):
        self.grafico = pg.PlotWidget(background="w", axisItems={"bottom": EixoDataHora(orientation="bottom")})
        self.grafico.setTitle("Deslocamento medido — sinal no tempo", color="#333333")
        self.grafico.setLabel("bottom", "Tempo", units="s")
        self.grafico.setLabel("left", "Deslocamento", units="mm")
        self.grafico.showGrid(x=True, y=True, alpha=.25)
        self.grafico.addLegend(colCount=4, offset=(10, 5), labelTextColor="#333333")
        self.grafico.setDownsampling(auto=True, mode="peak")
        self.grafico.setClipToView(True)
        for lado in ("left", "bottom"):
            self.grafico.getAxis(lado).enableAutoSIPrefix(False)
            self.grafico.getAxis(lado).setPen("#555555")
            self.grafico.getAxis(lado).setTextPen("#333333")
        layout_direito.addWidget(self.grafico, 1)

    def carregar_arquivo_lynx(self):
        return self.abrir_csv_lynx('Abrir régua potenciométrica Lynx')

    def importar_caminho(self, caminho, ignorar_ultima_incompleta=False):
        tempo, canais, mapa, info = ler_lynx_regua(caminho, ignorar_ultima_incompleta)
        # Valida o arquivo inteiro antes de substituir o estado da janela.
        self.tempo = tempo
        self.df_original = canais.copy()
        self.df_sensores = canais
        self.mapa_canais = mapa
        self.info_arquivo = info
        self.caminho_atual = Path(caminho)
        self.carregar_referencia_temporal(caminho)
        self.config_filtros = {}
        self.info_processamento = {"fs": info["fs"], "substituicoes": {}}
        self.grafico.clear()
        self.curvas_regua.clear()
        self.recriar_canais()
        self.habilitar_limites_visualizacao()
        self.limites_visualizacao.clear()
        mensagens = info["avisos"] + [f"Canal {n} *: {aviso}." for n, aviso in info["qualidade"].items()]
        self.rotulo_arquivo.setText("\n".join(mensagens) or "Deslocamento em mm conforme medido no CSV. Use Offset para definir uma referência, se necessário.")
        self.atualizar_indicacao_filtros()
        self.atualizar_graficos()
        self.ajustar_aos_dados()
        aviso = aviso_unidades(info, "régua potenciométrica")
        if aviso:
            QMessageBox.warning(self, "Canais de outra medição", aviso)
        return True

    def recriar_canais(self):
        for checkbox in self.checkboxes_canais.values():
            self.layout_canais.removeWidget(checkbox)
            checkbox.hide()
            checkbox.deleteLater()
        self.checkboxes_canais = {}
        for canal, nome in self.mapa_canais.items():
            aviso = self.info_arquivo["qualidade"].get(canal, "")
            checkbox = QCheckBox(f"Canal {canal} — {nome} (mm)" + (" *" if aviso else ""))
            checkbox.setToolTip(checkbox.text() + "\n" + (aviso or "A marca controla a exibição deste canal."))
            checkbox.setChecked(True)
            checkbox.toggled.connect(self.atualizar_visibilidade)
            self.layout_canais.insertWidget(self.layout_canais.count() - 1, checkbox)
            self.checkboxes_canais[canal] = checkbox

    def atualizar_graficos(self):
        if self.df_sensores is None:
            return
        for canal, nome in self.mapa_canais.items():
            if canal not in self.curvas_regua:
                self.curvas_regua[canal] = self.grafico.plot(
                    pen=pg.mkPen(pg.intColor(canal - 1, hues=32), width=1), name=f"Canal {canal} — {nome}")
            self.curvas_regua[canal].setData(self.tempo, self.df_sensores[canal].to_numpy())
        self.atualizar_visibilidade()

    def atualizar_visibilidade(self):
        for canal, curva in self.curvas_regua.items():
            curva.setVisible(self.checkboxes_canais[canal].isChecked())
        if self.df_sensores is not None:
            selecionados = sum(c.isChecked() for c in self.checkboxes_canais.values())
            substituicoes = sum(self.info_processamento.get("substituicoes", {}).values())
            self.statusBar().showMessage(f"{self.caminho_atual.name} | {self.info_processamento['fs']:g} Hz | "
                f"{len(self.tempo)} amostras | {selecionados}/{len(self.mapa_canais)} canais selecionados | "
                f"Deslocamento em mm | {substituicoes} substituições de outliers")

    def series_para_ajuste(self):
        return [self.df_sensores[n].to_numpy() for n in self.mapa_canais if self.checkboxes_canais[n].isChecked()]
