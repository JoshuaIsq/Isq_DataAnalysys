"""Integração por trapézios e derivação temporal, sem compensações implícitas."""
import numpy as np
import pandas as pd
from scipy.integrate import cumulative_trapezoid

from .sinais import Processamento

G_PADRAO_M_S2 = 9.80665
G_PADRAO_MM_S2 = G_PADRAO_M_S2 * 1000


def retirar_media_aceleracao(tempo, dados):
    """Retira a média de cada canal em g e retorna também as médias removidas.

    Usa todo o intervalo recebido. Não filtra nem remove inclinação.
    """
    _, _, valores = Processamento._preparar_dados(tempo, dados)
    try:
        with np.errstate(over="raise", invalid="raise"):
            medias = valores.mean(axis=0)
            centrados = valores - medias
    except FloatingPointError as erro:
        raise ValueError("Não foi possível retirar a média: verifique a amplitude do sinal.") from erro
    return (
        Processamento._quadro(centrados, dados),
        pd.Series(medias, index=dados.columns, name="media_aceleracao_g"),
    )


def integrar_relativo(tempo, dados, grandeza):
    """Integra por trapézios, com primeira amostra do resultado igual a zero.

    Aceleração: g → m/s² (×9,80665) → m/s → mm/s (×1000).
    Velocidade: mm/s → mm. Preserva essa ordem de cálculo.
    Não remove média/tendência, aplica filtros ou estima condições iniciais físicas.
    """
    _, t, valores = Processamento._preparar_dados(tempo, dados)
    if grandeza not in ("aceleracao", "velocidade"):
        raise ValueError("Grandeza de entrada desconhecida.")
    fator = G_PADRAO_M_S2 if grandeza == "aceleracao" else 1.0
    fator_saida = 1000.0 if grandeza == "aceleracao" else 1.0
    try:
        with np.errstate(over="raise", invalid="raise"):
            resultado = cumulative_trapezoid(
                valores * fator, x=t - t[0], axis=0, initial=0
            ) * fator_saida
    except FloatingPointError as erro:
        raise ValueError("Não foi possível integrar: verifique a amplitude e os dados do sinal.") from erro
    return Processamento._quadro(resultado, dados)


def corrigir_rampa_deslocamento(tempo, dados):
    """Retira a reta de mínimos quadrados, incluindo o intercepto, do deslocamento.

    Retorna o resíduo e os coeficientes b+m·(t-t[0]), em mm e mm/s.
    Não força o resultado a começar em zero. Remover uma reta não comprova
    que ela fosse erro de medição nem recupera as condições iniciais físicas.
    """
    corrigido, ajustes = Processamento._retirar_tendencia(tempo, dados, grau=1)
    ajustes = ajustes.rename(columns={"c0": "intercepto_mm", "c1": "inclinacao_mm_s"})
    return corrigido, ajustes


def derivar_deslocamento(tempo, dados):
    """Deriva mm para mm/s e g, com diferenças centrais e bordas de segunda ordem.

    Não aplica filtros. As derivadas numéricas não são inversas exatas dos
    trapézios; discretização, ruído e extremidades afetam o resultado.
    """
    _, t, valores = Processamento._preparar_dados(tempo, dados)
    if len(t) < 3:
        raise ValueError("São necessárias pelo menos 3 amostras para derivar o deslocamento.")
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            relativo = t - t[0]
            velocidade = np.gradient(valores, relativo, axis=0, edge_order=2)
            aceleracao = np.gradient(velocidade, relativo, axis=0, edge_order=2) / G_PADRAO_MM_S2
    except FloatingPointError as erro:
        raise ValueError("Não foi possível derivar: verifique o tempo e a amplitude do deslocamento.") from erro
    return Processamento._quadro(velocidade, dados), Processamento._quadro(aceleracao, dados)
