"""Fluxo por segmento: conversão, soma X·dt e ajustes após as integrações.

Cada chamada recebe um segmento completo, sem estado entre chamadas. O fator
9810 reproduz a convenção solicitada para o ensaio no LabVIEW; não é 9806,65.
As rotinas históricas por trapézios continuam em integracao.py.
"""
import numpy as np
import pandas as pd

from .sinais import Processamento

FATOR_G_MM_S2 = 9810.0


def _quadro(valores, origem):
    if not np.isfinite(valores).all():
        raise ValueError('O cálculo gerou valores inválidos; confira a amplitude do sinal.')
    return pd.DataFrame(valores, index=origem.index, columns=origem.columns)


def converter_aceleracao(tempo, dados_g):
    """Recebe exclusivamente g e devolve uma cópia em mm/s², multiplicada uma vez."""
    Processamento.validar_dados(tempo, dados_g)
    with np.errstate(over='ignore', invalid='ignore'):
        return _quadro(dados_g.to_numpy(dtype=float) * FATOR_G_MM_S2, dados_g)


def integrar_segmento(tempo, dados):
    """Soma retangular y[i] = y[i-1] + x[i]·dt, acumulador inicial zero.

Corresponde à operação Sum[Xdt], por segmento, em amostragem uniforme.
Inclui a primeira amostra: y[0] = x[0]·dt. Não converte unidades nem remove
média/tendência. mm/s² resulta em mm/s; mm/s resulta em mm.
"""
    fs = Processamento.validar_dados(tempo, dados)
    with np.errstate(over='ignore', invalid='ignore'):
        resultado = np.cumsum(dados.to_numpy(dtype=float) / fs, axis=0)
    return _quadro(resultado, dados)


def retirar_ajuste(tempo, dados, grau):
    """Subtrai o ajuste LS completo (inclui intercepto), de grau 1 ou 2.

Usa tempo normalizado em [-1,1] para estabilidade. Retorna o resíduo e os
coeficientes em potências de segundos: c0+c1·τ+c2·τ², τ=t-t[0]. O ajuste
é independente por canal e usa todas as amostras do segmento recebido.
Não impõe valor inicial zero ao resultado nem determina a posição física.
"""
    Processamento.validar_dados(tempo, dados)
    if grau not in (1, 2) or len(tempo) < grau + 2:
        raise ValueError('Use grau 1 ou 2 e pelo menos grau + 2 amostras.')
    t = np.asarray(tempo, dtype=float)
    duracao = t[-1] - t[0]
    x = 2 * ((t - t[0]) / duracao) - 1
    matriz = np.polynomial.polynomial.polyvander(x, grau)
    try:
        with np.errstate(over='raise', invalid='raise', divide='raise'):
            valores = dados.to_numpy(dtype=float)
            coef, _, posto, _ = np.linalg.lstsq(matriz, valores, rcond=None)
            corrigidos = valores - matriz @ coef
            # Conversão analítica da base normalizada para segundos relativos.
            c0 = coef[0] - coef[1]
            c1 = 2 * coef[1] / duracao
            parametros = {'c0': c0, 'c1': c1}
            if grau == 2:
                parametros['c0'] = c0 + coef[2]
                parametros['c1'] = c1 - 4 * coef[2] / duracao
                parametros['c2'] = 4 * coef[2] / duracao**2
    except (FloatingPointError, np.linalg.LinAlgError) as erro:
        raise ValueError('Não foi possível ajustar o polinômio ao sinal.') from erro
    ajustes = pd.DataFrame(parametros, index=dados.columns)
    if posto != grau + 1 or not np.isfinite(ajustes.to_numpy()).all():
        raise ValueError('O ajuste polinomial não pôde ser determinado.')
    return _quadro(corrigidos, dados), ajustes


def estatisticas(dados):
    """RMS total, máximo e mínimo por canal, no recorte recebido (sem retirar DC)."""
    if not isinstance(dados, pd.DataFrame) or dados.empty:
        raise ValueError('O intervalo selecionado não contém amostras.')
    valores = dados.to_numpy(dtype=float)
    if not np.isfinite(valores).all():
        raise ValueError('As estatísticas precisam de valores finitos.')
    # Escalonamento evita overflow no quadrado, sem alterar a definição do RMS.
    escala = np.max(np.abs(valores), axis=0)
    normalizados = valores / np.where(escala == 0, 1, escala)
    return pd.DataFrame({'RMS': escala * np.sqrt(np.mean(normalizados**2, axis=0)),
                         'Máximo': valores.max(axis=0), 'Mínimo': valores.min(axis=0)},
                        index=dados.columns)
