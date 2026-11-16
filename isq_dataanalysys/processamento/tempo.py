"""Apresentação temporal Lynx: horário registrado menos três horas fixas.

É uma convenção de exibição do projeto, não uma conversão automática de fuso.
O vetor numérico usado nos cálculos permanece inalterado.
"""
from datetime import datetime, timedelta

import numpy as np

ROTULO_DATA_HORA = "Data/Hora local (CSV − 3 h)"
AJUSTE_HORARIO = timedelta(hours=-3)


def inicio_local(inicio):
    """Aplica a convenção fixa de exibição ao datetime fornecido pelo leitor."""
    if not isinstance(inicio, datetime):
        raise ValueError("Informe uma data/hora inicial válida.")
    try:
        return inicio + AJUSTE_HORARIO
    except OverflowError as erro:
        raise ValueError("A data/hora inicial ultrapassa o intervalo suportado.") from erro


def datas_locais(inicio, segundos):
    """Produz datas com resolução de microssegundos; rejeita NaN, infinito e overflow."""
    # Preserva o relógio informado, mesmo se o datetime trouxer informação de fuso.
    referencia = np.datetime64(inicio_local(inicio).replace(tzinfo=None), "us")
    try:
        with np.errstate(over="ignore", invalid="ignore"):
            micros = np.rint(np.asarray(segundos, dtype=float) * 1_000_000)
    except (TypeError, ValueError, OverflowError) as erro:
        raise ValueError("Os deslocamentos temporais precisam ser números finitos em segundos.") from erro
    # O menor int64 representa NaT; o limite superior precisa excluir 2**63.
    if (not np.isfinite(micros).all() or np.any(micros <= -(2**63))
            or np.any(micros >= 2**63)):
        raise ValueError("Os deslocamentos temporais são inválidos ou excedem o intervalo suportado.")
    deslocamentos = micros.astype(np.int64)
    base = int(referencia.astype(np.int64))
    if ((base >= 0 and np.any(deslocamentos > (2**63 - 1) - base))
            or (base < 0 and np.any(deslocamentos <= -(2**63) - base))):
        raise ValueError("As datas calculadas excedem o intervalo suportado.")
    return referencia + deslocamentos.astype("timedelta64[us]")


def inicio_do_eixo(eixo, inicio=None):
    """Devolve a referência original do CSV apenas para um eixo temporal linear."""
    referencia_eixo = getattr(eixo, "inicio", None)
    unidades = getattr(eixo, "labelUnits", "")
    temporal = unidades == "s" or referencia_eixo is not None
    if getattr(eixo, "logMode", False) or unidades == "Hz" or not temporal:
        return None
    return inicio if inicio is not None else referencia_eixo
