"""Cinemática por segmento: convenção do ensaio com fator 9810 e soma X·dt.

Cada chamada usa o segmento completo, sem acumular estado entre chamadas.
As integrais por trapézios e o fator padrão 9806,65 estão em integracao.py.
"""
import numpy as np
import pandas as pd

from .sinais import Processamento

FATOR_G_MM_S2 = 9810.0


def converter_aceleracao(tempo, dados_g):
    """Converte g para mm/s² uma única vez, sem modificar os dados recebidos."""
    _, _, valores = Processamento._preparar_dados(tempo, dados_g)
    with np.errstate(over="ignore", invalid="ignore"):
        return Processamento._quadro(valores * FATOR_G_MM_S2, dados_g)


def integrar_segmento(tempo, dados):
    """Soma retangular y[i] = soma(x[0:i+1])·dt, inclusive y[0] = x[0]·dt.

    Não converte unidades, remove média ou ajusta tendência.
    Entrada em mm/s² produz mm/s; entrada em mm/s produz mm.
    """
    fs, _, valores = Processamento._preparar_dados(tempo, dados)
    with np.errstate(over="ignore", invalid="ignore"):
        resultado = np.cumsum(valores / fs, axis=0)
    return Processamento._quadro(resultado, dados)


def retirar_ajuste(tempo, dados, grau):
    """Subtrai o ajuste completo de grau 1 ou 2, incluindo o intercepto.

    Retorna resíduo e coeficientes de c0+c1·τ+c2·τ², com τ=t-t[0].
    Mantém a exigência de pelo menos grau+2 amostras deste fluxo.
    O resíduo não é forçado a começar em zero.
    """
    grau = Processamento.quantidade(grau, 2, "Grau do polinômio", minimo=1)
    if np.ndim(tempo) != 1 or len(tempo) < grau + 2:
        raise ValueError("Use grau 1 ou 2 e pelo menos grau + 2 amostras.")
    return Processamento._retirar_tendencia(tempo, dados, grau)


def estatisticas(dados):
    """RMS total, máximo e mínimo por canal, sem retirar a componente DC."""
    valores = Processamento._valores(dados)
    return pd.DataFrame(
        {"RMS": Processamento._rms(valores),
         "Máximo": valores.max(axis=0), "Mínimo": valores.min(axis=0)},
        index=dados.columns,
    )
