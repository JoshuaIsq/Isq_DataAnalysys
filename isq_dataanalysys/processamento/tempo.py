"""Referência de exibição Lynx: horário registrado menos três horas, fixas."""
from datetime import timedelta

import numpy as np

ROTULO_DATA_HORA = "Data/Hora local (CSV − 3 h)"
AJUSTE_HORARIO = timedelta(hours=-3)


def inicio_local(inicio):
    return inicio + AJUSTE_HORARIO


def datas_locais(inicio, segundos):
    """Converte apenas para apresentação; não altera o vetor temporal recebido."""
    deslocamentos = np.rint(np.asarray(segundos, dtype=float) * 1_000_000).astype("timedelta64[us]")
    return np.datetime64(inicio_local(inicio), "us") + deslocamentos


def inicio_do_eixo(eixo, inicio=None):
    """Retorna a referência original do CSV somente para um eixo temporal."""
    referencia = inicio if inicio is not None else getattr(eixo, "inicio", None)
    temporal = eixo.labelUnits == "s" or getattr(eixo, "inicio", None) is not None
    if eixo.logMode or eixo.labelUnits == "Hz" or not temporal:
        return None
    return referencia
