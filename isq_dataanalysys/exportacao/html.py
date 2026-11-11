from html import escape

import numpy as np
import plotly.graph_objects as go
import pyqtgraph as pg
from plotly.subplots import make_subplots
from isq_dataanalysys.processamento.tempo import ROTULO_DATA_HORA, datas_locais, inicio_do_eixo




def criar_figura_html(plots, inicio=None, titulo="Dados tratados", descricao=""):
    """Monta o HTML a partir das curvas selecionadas na tela."""
    figura = make_subplots(
        rows=len(plots),
        cols=1,
        shared_xaxes=True,
        subplot_titles=[
            escape(plot.titleLabel.text or titulo)
            for plot in plots
        ],
    )

    legendas = set()

    for linha, plot in enumerate(plots, start=1):
        eixo_x = plot.getAxis("bottom")
        eixo_y = plot.getAxis("left")
        rotulo_x = eixo_x.labelText or "Tempo"
        unidade_x = eixo_x.labelUnits or ""

        unidade = eixo_y.labelUnits or ""

        referencia = inicio_do_eixo(eixo_x, inicio)
        usar_data = referencia is not None

        for curva in plot.listDataItems():
            if not curva.isVisible():
                continue

            # Dados completos enviados à curva, incluindo os
            # tratamentos e o RMS, caso esteja selecionado.
            x, y = curva.getOriginalDataset()

            if x is None or y is None or len(x) == 0:
                continue

            if not np.any(np.isfinite(y)):
                continue

            segundos = np.asarray(x, dtype=float)

            if usar_data:
                x_html = datas_locais(referencia, segundos).astype(str).tolist()

                texto_tempo = (
                    ROTULO_DATA_HORA + ": %{x|%d/%m/%Y %H:%M:%S.%L}"
                    "<br>Tempo: %{customdata:.6f} s"
                )

            else:
                x_html = segundos
                texto_tempo = escape(rotulo_x) + ": %{x:.6f} " + escape(unidade_x)

            nome = escape(curva.name() or "Canal")
            cor = pg.mkPen(curva.opts["pen"]).color()

            figura.add_trace(
                go.Scattergl(
                    x=x_html,
                    y=y,
                    customdata=segundos if usar_data else None,
                    mode="lines",
                    name=nome,
                    legendgroup=nome,
                    showlegend=nome not in legendas,
                    line=dict(
                        color=cor.name(),
                        width=1,
                    ),
                    opacity=cor.alphaF(),
                    connectgaps=False,
                    hovertemplate=(
                        texto_tempo
                        + "<br>Valor: %{y:.6f} "
                        + escape(unidade)
                        + "<extra>%{fullData.name}</extra>"
                    ),
                ),
                row=linha,
                col=1,
            )

            legendas.add(nome)

        rotulo_y = eixo_y.labelText or "Valor"

        if unidade:
            rotulo_y += f" ({unidade})"

        figura.update_yaxes(
            title_text=escape(rotulo_y),
            type="log" if eixo_y.logMode else "linear",
            row=linha,
            col=1,
        )

        # Preserva a escala escolhida na análise, inclusive na extensometria.
        faixa_x, faixa_y = plot.viewRange()
        figura.update_yaxes(range=faixa_y, autorange=False, row=linha, col=1)
        if usar_data:
            faixa_x = datas_locais(referencia, faixa_x).astype(str).tolist()

        figura.update_xaxes(
            title_text=(
                ROTULO_DATA_HORA if usar_data else
                escape(rotulo_x + (f" ({unidade_x})" if unidade_x else ""))
            ),
            type=(
                "date"
                if usar_data
                else ("log" if eixo_x.logMode else "linear")
            ),
            range=faixa_x,
            autorange=False,
            showticklabels=True,
            row=linha,
            col=1,
        )
        if usar_data:
            figura.update_xaxes(tickformat="%d/%m/%Y<br>%H:%M:%S.%L", nticks=5,
                               hoverformat="%d/%m/%Y %H:%M:%S.%L", row=linha, col=1)

    if not figura.data:
        raise ValueError(
            "Selecione pelo menos um canal com dados válidos."
        )

    figura.update_layout(
        template="plotly_white",
        height=450 * len(plots),
        hovermode="closest",
        hoverlabel=dict(namelength=-1),
        margin=dict(l=80, r=30, t=120 if descricao else 70, b=60),
    )

    if descricao:
        figura.update_layout(title=dict(text=escape(descricao).replace('\n', '<br>'), font=dict(size=12)))

    return figura
