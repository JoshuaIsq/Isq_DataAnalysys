"""Leitura comum: a posição identifica o canal, e Unit define a grandeza."""
import csv

import numpy as np
import pandas as pd

from isq_dataanalysys.processamento.sinais import Processamento
from isq_dataanalysys.leitores.codificacao import detectar_codificacao_csv


class LinhaFinalIncompleta(ValueError):
    """A interface deve pedir confirmação antes de descartar a última linha."""


def normalizar_unidade(unidade):
    texto = "".join(unidade.split()).casefold().replace("µ", "μ")
    return {"mpa": "MPa", "μm/m": "μm/m", "um/m": "μm/m",
            "mm/m": "mm/m", "g": "g", "mm": "mm"}.get(texto, unidade.strip())


def descrever_canais(canais):
    return "\n".join(
        f"Canal {c['posicao']} — {c['nome']} ({c['unidade_original'] or 'sem unidade'})"
        for c in canais
    )


def aviso_unidades(info, modalidade):
    if not info["ignorados"]:
        return ""
    return (
        f"Foram importados {len(info['nomes'])} canais de {modalidade}.\n\n"
        "Os canais abaixo não serão plotados nem contabilizados nesta análise, "
        "pois possuem outra unidade de medida:\n"
        + descrever_canais(info["ignorados"])
        + "\n\nConfira o CSV e abra os canais na opção correspondente à sua medição. "
        "Use Lynx → Régua potenciométrica para canais de deslocamento em mm; "
        "Acelerometria para g; Extensometria para MPa, μm/m ou mm/m."
    )


def ler_canais_lynx(caminho, unidades_aceitas, modalidade, ignorar_ultima_incompleta=False):
    codificacao = detectar_codificacao_csv(caminho)
    with open(caminho, encoding=codificacao, newline="") as arquivo:
        leitor = csv.reader(arquivo, delimiter=";")
        cabecalho = [next(leitor, []) for _ in range(5)]
    for linha, etiqueta in zip(cabecalho, ("Name", "Unit", "HighLim", "LowLim", "Time (s)")):
        if not linha or linha[0].strip() != etiqueta:
            raise ValueError(f"Cabeçalho inválido: esperada a linha {etiqueta}.")

    # Nome vazio não encerra os canais: a posição e a unidade ainda permitem
    # importar essa coluna. Remove apenas o espaço vazio antes dos metadados.
    fim_canais = len(cabecalho[0])
    for posicao, celula in enumerate(cabecalho[0][1:], 1):
        if celula.strip().casefold().startswith(("sampfreq:", "starttime")):
            fim_canais = posicao
            break
    while fim_canais > 1:
        posicao = fim_canais - 1
        nome_vazio = not cabecalho[0][posicao].strip()
        unidade_vazia = posicao >= len(cabecalho[1]) or not cabecalho[1][posicao].strip()
        if not (nome_vazio and unidade_vazia):
            break
        fim_canais -= 1
    nomes, avisos = [], []
    for posicao in range(1, fim_canais):
        nome = cabecalho[0][posicao].strip()
        if not nome:
            nome = f"Canal {posicao} (sem nome)"
            avisos.append(f"Canal {posicao}: nome vazio no CSV; identificado pela posição original.")
        nomes.append(nome)
    if not nomes:
        raise ValueError("O arquivo não informa canais na primeira linha.")
    if len(cabecalho[1]) < len(nomes) + 1:
        raise ValueError("Faltam unidades na segunda linha do cabeçalho.")

    descricoes = [
        dict(posicao=n, nome=nome, unidade_original=cabecalho[1][n].strip(),
             unidade=normalizar_unidade(cabecalho[1][n]))
        for n, nome in enumerate(nomes, 1)
    ]
    aceitos = [c for c in descricoes if c["unidade"] in unidades_aceitas]
    ignorados = [c for c in descricoes if c["unidade"] not in unidades_aceitas]
    if not aceitos:
        raise ValueError(
            f"Nenhum canal compatível com {modalidade}. "
            f"Unidades aceitas: {', '.join(unidades_aceitas)}.\n\n"
            + descrever_canais(ignorados) + "\n\nConfira o CSV e a opção de análise."
        )

    # Valores inválidos em outra medição não impedem a importação selecionada.
    tabela = pd.read_csv(caminho, sep=";", skiprows=5, header=None,
                         encoding=codificacao, dtype=str, keep_default_na=False,
                         skip_blank_lines=False)
    while tabela.shape[1] > len(nomes) + 1 and tabela.iloc[:, -1].str.strip().eq("").all():
        tabela = tabela.iloc[:, :-1]
    if tabela.empty or tabela.shape[1] != len(nomes) + 1:
        raise ValueError("Esperados tempo e uma coluna de dados para cada canal do cabeçalho.")
    posicoes = [c["posicao"] for c in aceitos]
    selecionada = tabela.iloc[:, [0] + posicoes].copy()
    vazias = selecionada.apply(lambda coluna: coluna.str.strip().eq(""))
    linhas_ignoradas = 0
    if vazias.iloc[:-1].any().any():
        raise ValueError("Existem campos vazios antes da última linha nos canais selecionados.")
    if vazias.iloc[-1].any():
        if not ignorar_ultima_incompleta:
            raise LinhaFinalIncompleta(
                f"A última linha está incompleta nos canais selecionados. "
                f"Há {len(tabela) - 1} linhas anteriores. Isso pode indicar um arquivo truncado."
            )
        selecionada = selecionada.iloc[:-1].copy()
        linhas_ignoradas = 1
        avisos.append("Última linha incompleta ignorada na importação; CSV original preservado.")
    numerica = selecionada.apply(
        lambda coluna: pd.to_numeric(coluna.str.strip().str.replace(",", ".", regex=False), errors="coerce")
    )
    tempo = numerica.iloc[:, 0].to_numpy(dtype=float)
    canais = numerica.iloc[:, 1:].copy()
    canais.columns = posicoes
    fs = Processamento.validar_dados(tempo, canais)

    fs_cabecalho = None
    linha_nomes = [v.strip() for v in cabecalho[0]]
    if "SampFreq:" in linha_nomes:
        posicao = linha_nomes.index("SampFreq:") + 1
        try:
            fs_cabecalho = float(linha_nomes[posicao].lower().replace("hz", "").replace(",", ".").strip())
        except (IndexError, ValueError) as erro:
            raise ValueError("SampFreq sem valor válido no cabeçalho.") from erro
        if not np.isfinite(fs_cabecalho) or fs_cabecalho <= 0:
            raise ValueError("Taxa inválida no cabeçalho.")
        if not np.isclose(fs, fs_cabecalho, rtol=1e-4):
            avisos.append(f"Cabeçalho: {fs_cabecalho:g} Hz; tempo: {fs:g} Hz. Usando o tempo.")

    qualidade = {}
    for canal in aceitos:
        n = canal["posicao"]
        try:
            alto = float(cabecalho[2][n].replace(",", "."))
            baixo = float(cabecalho[3][n].replace(",", "."))
        except (IndexError, ValueError) as erro:
            raise ValueError(f"Canal {n}: limites ausentes ou inválidos no cabeçalho.") from erro
        if not np.isfinite([baixo, alto]).all() or baixo >= alto:
            raise ValueError(f"Canal {n}: limites inválidos no cabeçalho.")
        serie = canais[n]
        problemas = []
        if serie.min() == serie.max():
            problemas.append(f"sinal constante em {serie.iloc[0]:g} {canal['unidade']}")
        fora = int(((serie < baixo) | (serie > alto)).sum())
        if fora:
            problemas.append(f"{fora} amostras fora dos limites informados no arquivo")
        if problemas:
            qualidade[n] = "; ".join(problemas)

    info = dict(fs=fs, fs_cabecalho=fs_cabecalho, avisos=avisos, qualidade=qualidade,
                linhas_ignoradas=linhas_ignoradas, ignorados=ignorados,
                nomes={c["posicao"]: c["nome"] for c in aceitos},
                unidades={c["posicao"]: c["unidade"] for c in aceitos},
                unidade=aceitos[0]["unidade"])
    return tempo, canais, info
