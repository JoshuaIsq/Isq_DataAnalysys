"""Cópia independente de todas as curvas da visualização atual em um painel."""
from copy import deepcopy
import numpy as np
import pandas as pd
import pyqtgraph as pg
from PySide6.QtWidgets import QPushButton, QMessageBox

from isq_dataanalysys import __version__
from isq_dataanalysys.exportacao.csv_tratado import DadosTratados
from .dados_tratados import TelaDadosTratados
from .integracao import mostrar_resultado

CORES_EIXOS = {'X': '#ff0000', 'Y': '#00ff00', 'Z': '#0000ff'}


class TelaGraficoUnificado(TelaDadosTratados):
    def __init__(self, arquivo, cores, titulo, unidade_x, rotulo_y, faixa_x, log=False):
        self.cores = cores.copy()
        self.titulo_unificado = titulo
        super().__init__()
        self.carregar_dados(arquivo)
        self.botao_abrir.hide()
        self.rotulo_origem.hide()
        self.setWindowTitle(f'Gráfico unificado — {titulo} — v{__version__}')
        self.setToolTip('Cópia da visualização no momento da abertura. A seleção é independente da origem.')
        plot = self.graficos_eixos[0]
        plot.setLabel('left', rotulo_y, units=next(iter(self.canais.values()))['unidade'])
        plot.setLogMode(x=False, y=log)
        if log:
            for canal, curva in self.curvas.items():
                valores = self.df_sensores[canal].to_numpy()
                curva.setData(self.tempo, np.where(valores > 0, valores, np.nan))
                curva.dados_csv = valores.copy()
        if unidade_x == 'Hz':
            self.painel_intervalo.hide()
            plot.setLabel('bottom', 'Frequência', units='Hz')
        elif self.tempo[0] < self.tempo[-1]:
            inicio = max(float(self.tempo[0]), float(faixa_x[0]))
            fim = min(float(self.tempo[-1]), float(faixa_x[1]))
            if inicio < fim:
                self.painel_intervalo.definir_intervalo_segundos(inicio, fim)
        plot.setXRange(*faixa_x, padding=0)
        for texto, marcado in (('Selecionar todos', True), ('Ocultar todos', False)):
            botao = QPushButton(texto)
            botao.clicked.connect(lambda _=False, valor=marcado: self.selecionar_todos(valor))
            self.layout_acoes.insertWidget(self.layout_acoes.count()-1, botao)

    def grupo_do_canal(self, canal, info, rotulo):
        return 0, self.titulo_unificado

    def caneta_do_canal(self, canal, info, numero):
        return pg.mkPen(self.cores[canal], width=1)

    def selecionar_todos(self, marcado):
        for campo in self.checkboxes_canais.values():
            campo.setChecked(marcado)


def abrir_grafico_unificado(origem):
    if getattr(origem, 'df_sensores', None) is None:
        return
    plots = list(origem.graficos_eixos.values())
    base, colunas, canais, cores = None, {}, {}, {}
    for plot in plots:
        for curva in plot.listDataItems():
            x, y = curva.getOriginalDataset()
            if x is None or y is None or not len(x):
                continue
            x = np.asarray(x, dtype=float)
            if base is None:
                base = x.copy()
            elif not np.array_equal(base, x):
                QMessageBox.warning(origem, 'Gráfico unificado', 'Os canais têm bases diferentes.')
                return
            canal = origem._identidade_curva_csv(curva, len(colunas)+1)
            colunas[canal] = np.array(getattr(curva, 'dados_csv', y), dtype=float, copy=True)
            info = getattr(origem, 'canais', {}).get(canal)
            if isinstance(info, dict):
                canais[canal] = deepcopy(info)
            else:
                canais[canal] = dict(nome=origem.info_arquivo['nomes'][canal],
                                     eixo=origem.info_arquivo['eixos'].get(canal, ''))
            canais[canal]['unidade'] = plot.getAxis('left').labelUnits
            cores[canal] = pg.mkPen(curva.opts['pen']).color().name()
    if base is None:
        return
    plot = plots[0]
    espectral = plot.getAxis('bottom').labelUnits == 'Hz'
    metadata = deepcopy(getattr(origem, 'metadados_tratados', {}))
    metadata['descricao'] = getattr(origem, 'descricao_exportacao', '')
    metadata['visualizacao'] = 'gráfico unificado; cópia independente'
    titulo = plot.getAxis('left').labelText
    janela = TelaGraficoUnificado(
        DadosTratados(base, pd.DataFrame(colunas), canais,
                      None if espectral else origem.inicio_para_exportar(), metadata),
        cores, titulo, plot.getAxis('bottom').labelUnits, titulo,
        plot.viewRange()[0], log=plot.getAxis('left').logMode,
    )
    janela.caminho_atual = getattr(origem, 'caminho_atual', None)
    return mostrar_resultado(origem, janela)
