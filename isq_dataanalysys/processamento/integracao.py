"""Integrais do sinal temporal tratado, sem compensações implícitas."""
import numpy as np
import pandas as pd
from scipy.integrate import cumulative_trapezoid
from isq_dataanalysys.processamento.sinais import Processamento

G_PADRAO_M_S2 = 9.80665
G_PADRAO_MM_S2 = G_PADRAO_M_S2 * 1000


def retirar_media_aceleracao(tempo, dados):
    """Retira somente a média aritmética de cada canal em g, em uma cópia.

    A média usa todas as amostras do intervalo carregado, após os tratamentos.
    Não ajusta inclinação, não filtra e não modifica a janela de origem.
    Retorna o sinal a integrar e as médias removidas, para registrar o método.
    """
    Processamento.validar_dados(tempo, dados)
    try:
        with np.errstate(over='raise', invalid='raise'):
            valores = dados.to_numpy(dtype=float)
            medias = valores.mean(axis=0)
            centrados = valores - medias
    except FloatingPointError as erro:
        raise ValueError('Não foi possível retirar a média: verifique a amplitude do sinal.') from erro
    if not np.isfinite(centrados).all() or not np.isfinite(medias).all():
        raise ValueError('A retirada da média gerou valores inválidos.')
    return (
        pd.DataFrame(centrados, index=dados.index, columns=dados.columns),
        pd.Series(medias, index=dados.columns, name='media_aceleracao_g'),
    )


def integrar_relativo(tempo, dados, grandeza):
    """Integra as amostras recebidas pelos trapézios, com condição inicial zero.

    Aceleração em g -> m/s² (×9,80665) -> integrar em m/s -> mm/s (×1000).
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
    fator = G_PADRAO_M_S2 if grandeza == 'aceleracao' else 1.0
    fator_saida = 1000.0 if grandeza == 'aceleracao' else 1.0
    tempo = np.asarray(tempo, dtype=float)
    relativo = tempo - tempo[0]
    valores = dados.to_numpy(dtype=float)
    try:
        with np.errstate(over='raise', invalid='raise'):
            resultado = cumulative_trapezoid(valores * fator, x=relativo, axis=0, initial=0) * fator_saida
    except FloatingPointError as erro:
        raise ValueError('Não foi possível integrar: verifique a amplitude e os dados do sinal.') from erro
    if not np.isfinite(resultado).all():
        raise ValueError('A integração gerou valores inválidos.')
    return pd.DataFrame(resultado, index=dados.index, columns=dados.columns)


def corrigir_rampa_deslocamento(tempo, dados):
    """Subtrai de cada deslocamento em mm sua reta de mínimos quadrados.

    O ajuste usa todas as amostras recebidas e o tempo relativo ao primeiro
    instante, normalizado para [-1, 1]. Retorna uma cópia corrigida e os
    coeficientes da reta b + m * (t - t[0]), em mm e mm/s, por canal.

    A subtração inclui o intercepto: o deslocamento corrigido não precisa
    começar em zero. No contínuo, ela modifica a velocidade por uma constante
    -m e preserva a aceleração. Essa propriedade não comprova que a rampa
    removida fosse erro de medição, nem recupera condições iniciais físicas.
    """
    Processamento.validar_dados(tempo, dados)
    try:
        with np.errstate(over='raise', invalid='raise', divide='raise'):
            t = np.asarray(tempo, dtype=float)
            relativo = t - t[0]
            duracao = relativo[-1]
            x = 2 * (relativo / duracao) - 1
            matriz = np.column_stack((np.ones(len(x)), x))
            valores = dados.to_numpy(dtype=float)
            coeficientes, _, posto, _ = np.linalg.lstsq(matriz, valores, rcond=None)
            corrigido = valores - matriz @ coeficientes
            interceptos = coeficientes[0] - coeficientes[1]
            inclinacoes = 2 * coeficientes[1] / duracao
    except (np.linalg.LinAlgError, FloatingPointError) as erro:
        raise ValueError('Não foi possível corrigir a rampa: verifique o tempo e a amplitude do deslocamento.') from erro
    if (posto != 2 or not np.isfinite(corrigido).all()
            or not np.isfinite(interceptos).all() or not np.isfinite(inclinacoes).all()):
        raise ValueError('O ajuste linear do deslocamento gerou valores inválidos.')
    ajustes = pd.DataFrame(
        {'intercepto_mm': interceptos, 'inclinacao_mm_s': inclinacoes},
        index=dados.columns.copy(),
    )
    return pd.DataFrame(corrigido, index=dados.index, columns=dados.columns), ajustes


def derivar_deslocamento(tempo, dados):
    """Deriva deslocamento em mm para velocidade em mm/s e aceleração em g.

    Usa diferenças centrais no interior e fórmulas de segunda ordem nas
    extremidades (numpy.gradient, edge_order=2), sem filtrar ou ajustar curvas.
    As derivadas numéricas não são inversas exatas dos trapézios usados nas
    integrações. Ruído, discretização e extremidades afetam a recuperação.
    """
    Processamento.validar_dados(tempo, dados)
    if len(tempo) < 3:
        raise ValueError('São necessárias pelo menos 3 amostras para derivar o deslocamento.')
    try:
        with np.errstate(over='raise', invalid='raise', divide='raise'):
            t = np.asarray(tempo, dtype=float)
            relativo = t - t[0]
            valores = dados.to_numpy(dtype=float)
            velocidade = np.gradient(valores, relativo, axis=0, edge_order=2)
            aceleracao = np.gradient(velocidade, relativo, axis=0, edge_order=2) / G_PADRAO_MM_S2
    except FloatingPointError as erro:
        raise ValueError('Não foi possível derivar: verifique o tempo e a amplitude do deslocamento.') from erro
    if not np.isfinite(velocidade).all() or not np.isfinite(aceleracao).all():
        raise ValueError('A derivação do deslocamento gerou valores inválidos.')
    return (
        pd.DataFrame(velocidade, index=dados.index, columns=dados.columns),
        pd.DataFrame(aceleracao, index=dados.index, columns=dados.columns),
    )
