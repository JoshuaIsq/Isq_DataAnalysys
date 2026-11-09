"""Integrais do sinal temporal tratado, sem compensações implícitas."""
import numpy as np
import pandas as pd
from scipy.integrate import cumulative_trapezoid
from isq_dataanalysys.processamento.sinais import Processamento

G_PADRAO_MM_S2 = 9806.65


def integrar_relativo(tempo, dados, grandeza):
    """Integra as amostras recebidas pelos trapézios, com condição inicial zero.

    Aceleração em g -> velocidade em mm/s (1 g = 9806,65 mm/s²).
    Velocidade em mm/s -> deslocamento em mm. Não remove média, reta,
    parábola nem aplica filtros: a entrada é exatamente o sinal tratado
    da janela de origem. Cada incremento é a área do trapézio entre
    duas amostras, isto é, a integral da interpolação linear da entrada,
    sujeita ao arredondamento de ponto flutuante. Não garante recuperar
    o movimento físico entre amostras ou removido pelos filtros.
    """
    Processamento.validar_dados(tempo, dados)
    if grandeza not in ('aceleracao', 'velocidade'):
        raise ValueError('Grandeza de entrada desconhecida.')
    fator = G_PADRAO_MM_S2 if grandeza == 'aceleracao' else 1.0
    tempo = np.asarray(tempo, dtype=float)
    relativo = tempo - tempo[0]
    valores = dados.to_numpy(dtype=float)
    try:
        with np.errstate(over='raise', invalid='raise'):
            resultado = cumulative_trapezoid(valores * fator, x=relativo, axis=0, initial=0)
    except FloatingPointError as erro:
        raise ValueError('Não foi possível integrar: verifique a amplitude e os dados do sinal.') from erro
    if not np.isfinite(resultado).all():
        raise ValueError('A integração gerou valores inválidos.')
    return pd.DataFrame(resultado, index=dados.index, columns=dados.columns)
