"""Exportação vetorial dos dados completos dos canais visíveis."""
import matplotlib as mpl
import matplotlib.dates as mdates
from datetime import timezone
from matplotlib.figure import Figure
from matplotlib.backends.backend_svg import FigureCanvasSVG
import pyqtgraph as pg
from isq_dataanalysys.processamento.tempo import ROTULO_DATA_HORA, datas_locais, inicio_do_eixo


def salvar_svg(plots, caminho, descricao='', titulo='Dados tratados', inicio=None):
    selecionadas = [[curva for curva in plot.listDataItems() if curva.isVisible()] for plot in plots]
    if not any(selecionadas):
        raise ValueError('Selecione pelo menos um canal.')
    figura = None
    try:
        with mpl.rc_context({'path.simplify': False, 'svg.fonttype': 'path'}):
            figura = Figure(figsize=(12, 4*len(plots)), layout='constrained')
            if descricao:
                figura.suptitle(descricao, fontsize=10)
            FigureCanvasSVG(figura)
            eixos = figura.subplots(nrows=len(plots), ncols=1, squeeze=False)
            for linha, (plot, curvas) in enumerate(zip(plots, selecionadas)):
                eixo = eixos[linha, 0]
                eixo_x, eixo_y = plot.getAxis('bottom'), plot.getAxis('left')
                referencia = inicio_do_eixo(eixo_x, inicio)
                if eixo_x.logMode:
                    eixo.set_xscale('log')
                if eixo_y.logMode:
                    eixo.set_yscale('log')
                for curva in curvas:
                    x, y = curva.getOriginalDataset()
                    if x is None or y is None or len(x) == 0:
                        continue
                    if referencia is not None:
                        x = datas_locais(referencia, x)
                    cor = pg.mkPen(curva.opts['pen']).color()
                    eixo.plot(x, y, label=curva.name() or 'Canal', color=cor.name(),
                              alpha=cor.alphaF(), linewidth=.8, rasterized=False)
                for eixo_grafico, setter, padrao in ((eixo_x, eixo.set_xlabel, 'Tempo'),
                                                     (eixo_y, eixo.set_ylabel, 'Valor')):
                    rotulo = eixo_grafico.labelText or padrao
                    if eixo_grafico.labelUnits:
                        rotulo += f' ({eixo_grafico.labelUnits})'
                    setter(rotulo)
                if referencia is not None:
                    eixo.set_xlabel(ROTULO_DATA_HORA)
                    localizador = mdates.AutoDateLocator(minticks=3, maxticks=7, interval_multiples=True)
                    formatador = mdates.AutoDateFormatter(localizador, tz=timezone.utc)
                    for escala in formatador.scaled:
                        formatador.scaled[escala] = "%d/%m/%Y\n%H:%M:%S" + (".%f" if escala < 1/86400 else "")
                    eixo.xaxis.set_major_locator(localizador)
                    eixo.xaxis.set_major_formatter(formatador)
                eixo.set_title(plot.titleLabel.text or titulo)
                eixo.grid(True, alpha=.25)
                faixa_x, faixa_y = plot.viewRange()
                if referencia is not None:
                    faixa_x = mdates.date2num(datas_locais(referencia, faixa_x))
                eixo.set_xlim([10**v for v in faixa_x] if eixo_x.logMode else faixa_x)
                eixo.set_ylim([10**v for v in faixa_y] if eixo_y.logMode else faixa_y)
                if eixo.lines:
                    eixo.legend(loc='upper left', ncol=4, fontsize=8)
            figura.savefig(str(caminho), format='svg')
    finally:
        if figura is not None:
            figura.clear()
