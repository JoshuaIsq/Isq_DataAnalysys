"""Importa cada canal em g, sem exigir trios nem nomes/eixos exclusivos."""
import re
import unicodedata

from isq_dataanalysys.leitores.lynx import ler_canais_lynx

EIXO_DESCONHECIDO = "Sem eixo"
EIXOS = ("X", "Y", "Z", EIXO_DESCONHECIDO)

# Letras isoladas ou após o número do sensor, como no formato antigo "ACC1X".
# Também aceita sublinhados/colchetes ou o eixo antes do nome do sensor.
# Não confunde o X de "Aux" ou de "XYZ" com um eixo.
_EIXO = re.compile(r"(?<![^\W\d_])([XYZ])(?![^\W_])", re.IGNORECASE)


def _identificar_eixo(nome):
    texto = unicodedata.normalize("NFKC", nome).strip()
    texto = re.sub(r"\s*[\[(]\s*g\s*[\])]\s*$", "", texto, flags=re.IGNORECASE)
    encontrados = list(_EIXO.finditer(texto))
    if len(encontrados) != 1:
        return EIXO_DESCONHECIDO, nome.strip()
    encontrado = encontrados[0]
    eixo = encontrado.group(1).upper()
    identificacao = texto[:encontrado.start()] + " " + texto[encontrado.end():]
    identificacao = re.sub(r"\b(?:eixo|axis)\b", "", identificacao, flags=re.IGNORECASE)
    identificacao = re.sub(r"[\W_]+", " ", identificacao).strip()
    return eixo, identificacao or "Acelerômetro sem identificação"


def _agrupar_canais(nomes, posicoes):
    identificados = {p: _identificar_eixo(nomes[p]) for p in posicoes}
    eixos = {p: identificados[p][0] for p in posicoes}
    origens = {p: "nome" if eixos[p] != EIXO_DESCONHECIDO else "não identificado"
               for p in posicoes}
    avisos = []

    # Compatibilidade com os CSVs antigos sem indicação de nenhum eixo.
    # Nunca usa esse padrão para substituir eixos que já foram reconhecidos.
    sem_indicacao = not any(_EIXO.search(unicodedata.normalize("NFKC", nomes[p])) for p in posicoes)
    if sem_indicacao and len(posicoes) % 3 == 0:
        sensores = [dict(zip("XYZ", posicoes[i:i + 3])) for i in range(0, len(posicoes), 3)]
        rotulos = [f"Acelerômetro {n} (XYZ por posição)" for n in range(1, len(sensores) + 1)]
        for sensor in sensores:
            for eixo, p in sensor.items():
                eixos[p], origens[p] = eixo, "posição"
        avisos.append(
            "Nenhum eixo foi identificado nos nomes: usado o padrão legado X/Y/Z "
            "por posição. Essa associação é inferida; confira a ordem dos canais."
        )
        return sensores, rotulos, eixos, origens, avisos

    sensores, rotulos, grupos = [], [], {}
    for p in posicoes:
        eixo, identificacao = identificados[p]
        if eixo == EIXO_DESCONHECIDO:
            sensores.append({EIXO_DESCONHECIDO: p})
            rotulos.append(f"Canal {p} — {nomes[p]}")
            avisos.append(
                f"Canal {p} — {nomes[p]}: eixo não identificado de forma unívoca; "
                "plotado em 'Sem eixo', sem atribuir X, Y ou Z."
            )
            continue

        chave = identificacao.casefold()
        if chave not in grupos:
            grupos[chave] = len(sensores)
            sensores.append({})
            rotulos.append(identificacao)
        sensor = sensores[grupos[chave]]
        if eixo in sensor:
            anterior = sensor[eixo]
            # A posição continua sendo a identidade. Um Y repetido não sobrescreve
            # o anterior nem é transformado em X/Z para completar um trio.
            sensores.append({eixo: p})
            rotulos.append(f"{identificacao} — canal {p} (eixo repetido)")
            avisos.append(
                f"{identificacao}: eixo {eixo} repetido nos canais {anterior} e {p}; "
                "ambos preservados separadamente com seus nomes originais."
            )
        else:
            sensor[eixo] = p

    for rotulo, sensor in zip(rotulos, sensores):
        if EIXO_DESCONHECIDO not in sensor:
            faltando = [e for e in "XYZ" if e not in sensor]
            if faltando:
                avisos.append(f"{rotulo}: sem o(s) eixo(s) {', '.join(faltando)}; canais disponíveis importados.")
    return sensores, rotulos, eixos, origens, avisos


def ler_lynx_acelerometria(caminho, ignorar_ultima_incompleta=False):
    tempo, canais, info = ler_canais_lynx(
        caminho, ("g",), "acelerometria", ignorar_ultima_incompleta
    )
    posicoes = list(canais.columns)

    sensores, rotulos, eixos, origens, avisos = _agrupar_canais(info["nomes"], posicoes)
    info["rotulos_sensores"] = rotulos
    info["eixos"] = eixos
    info["origem_eixos"] = origens
    info["avisos"].extend(avisos)
    return tempo, canais, sensores, info
