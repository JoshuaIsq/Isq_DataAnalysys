"""Integrações temporais relativas, sem modificar as medições de entrada."""
import numpy as np
import pandas as pd
from scipy.integrate import cumulative_trapezoid
from processamento import Processamento


def integrar_relativo(tempo, dados, grandeza):
    """Remove tendência por mínimos quadrados e integra com condição inicial zero.

    Aceleração em g -> velocidade em mm/s (1 g = 9806,65 mm/s²).
    Velocidade em mm/s -> deslocamento em mm. O ajuste usa tempo
    normalizado para evitar perda de precisão em registros longos.
    """
    Processamento.validar_dados(tempo, dados)
    if grandeza not in ('aceleracao', 'velocidade'):
        raise ValueError('Grandeza de entrada desconhecida.')
    grau, fator = (1, 9806.65) if grandeza == 'aceleracao' else (2, 1.0)
    if len(tempo) < grau + 2:
        raise ValueError(f'São necessárias pelo menos {grau + 2} amostras para integrar.')
    relativo = np.asarray(tempo, dtype=float) - tempo[0]
    x = 2 * relativo / relativo[-1] - 1
    matriz = np.polynomial.polynomial.polyvander(x, grau)
    valores = dados.to_numpy(dtype=float)
    coeficientes = np.linalg.lstsq(matriz, valores, rcond=None)[0]
    residuo = valores - matriz @ coeficientes
    resultado = cumulative_trapezoid(residuo * fator, x=relativo, axis=0, initial=0)
    if not np.isfinite(resultado).all():
        raise ValueError('A integração gerou valores inválidos.')
    return pd.DataFrame(resultado, index=dados.index, columns=dados.columns)
