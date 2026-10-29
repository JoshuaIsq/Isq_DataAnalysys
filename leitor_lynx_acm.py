"""Acelerometria: trios X/Y/Z na ordem dos canais de aceleração do CSV."""
from leitor_lynx import ler_canais_lynx


def ler_lynx_acelerometria(caminho, ignorar_ultima_incompleta=False):
    tempo, canais, info = ler_canais_lynx(
        caminho, ("g",), "acelerometria", ignorar_ultima_incompleta
    )
    posicoes = list(canais.columns)
    if len(posicoes) % 3:
        raise ValueError(
            f"Foram encontrados {len(posicoes)} canais em g. A acelerometria requer "
            "trios completos na ordem X, Y, Z. Confira as unidades e a ordem no CSV."
        )
    sensores = [dict(zip("XYZ", posicoes[i:i + 3])) for i in range(0, len(posicoes), 3)]
    return tempo, canais, sensores, info
