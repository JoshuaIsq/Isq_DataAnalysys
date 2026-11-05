"""Acelerometria: eixos X/Y/Z identificados pelo nome do canal; se não der, trios por posição."""
import re

from isq_dataanalysys.leitores.lynx import ler_canais_lynx

# Nome terminando em X, Y ou Z separado por não-letra: "Acc1_X", "Sensor 2 Y", "ACC 92128 - Z"
_EIXO = re.compile(r"(?<![A-Za-z])([XYZ])\s*$", re.IGNORECASE)


def _agrupar_por_nome(nomes, posicoes):
    """Retorna lista de sensores {'X': pos, ...} ou None se os nomes não permitirem."""
    grupos = {}
    for p in posicoes:
        nome = nomes[p].strip()
        m = _EIXO.search(nome)
        if not m:
            return None
        eixo = m.group(1).upper()
        sensor = grupos.setdefault(nome[:m.start()].strip(), {})
        if eixo in sensor:          # nome repetido: ambíguo
            return None
        sensor[eixo] = p
    return list(grupos.values())


def ler_lynx_acelerometria(caminho, ignorar_ultima_incompleta=False):
    tempo, canais, info = ler_canais_lynx(
        caminho, ("g",), "acelerometria", ignorar_ultima_incompleta
    )
    posicoes = list(canais.columns)

    sensores = _agrupar_por_nome(info["nomes"], posicoes)
    if sensores is None:                       # comportamento antigo
        if len(posicoes) % 3:
            raise ValueError(
                f"Foram encontrados {len(posicoes)} canais em g e os nomes não "
                "indicam o eixo (X, Y ou Z no fim do nome). Renomeie os canais "
                "ou confira a ordem no CSV."
            )
        sensores = [dict(zip("XYZ", posicoes[i:i + 3])) for i in range(0, len(posicoes), 3)]

    for n, s in enumerate(sensores, 1):
        faltando = [e for e in "XYZ" if e not in s]
        if faltando:
            info["avisos"].append(f"Sensor {n}: sem o(s) eixo(s) {', '.join(faltando)}.")
    return tempo, canais, sensores, info