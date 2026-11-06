"""Eixo de data/hora compartilhado pelas medições e pelas integrações."""
from datetime import timedelta

import pyqtgraph as pg

from isq_dataanalysys.processamento.tempo import ROTULO_DATA_HORA, inicio_local


class EixoDataHora(pg.AxisItem):
    """Os dados permanecem em segundos; somente os rótulos usam a hora local."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.inicio = None

    def definir_inicio(self, inicio):
        # Guarda a referência original para não aplicar o ajuste novamente ao exportar.
        self.inicio = inicio
        self.enableAutoSIPrefix(inicio is None)

    def tickStrings(self, values, scale, spacing):
        if self.inicio is None:
            return super().tickStrings(values, scale, spacing)
        formato = "%d/%m/%Y %H:%M:%S" + (".%f" if spacing < 1 else "")
        textos = []
        for valor in values:
            try:
                texto = (inicio_local(self.inicio) + timedelta(seconds=float(valor))).strftime(formato)
                if spacing < 1:
                    texto = texto[:-3] if spacing >= .001 else texto
            except (OverflowError, ValueError):
                texto = ""
            textos.append(texto)
        return textos


def configurar_eixo_temporal(plot, inicio):
    plot.getAxis("bottom").definir_inicio(inicio)
    plot.setLabel("bottom", ROTULO_DATA_HORA if inicio is not None else "Tempo",
                  units="" if inicio is not None else "s")
