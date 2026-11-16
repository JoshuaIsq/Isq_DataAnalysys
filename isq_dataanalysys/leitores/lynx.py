"""Leitura dos CSVs Lynx: a posição identifica o canal e Unit define a grandeza."""
import csv

import numpy as np
import pandas as pd

from isq_dataanalysys.leitores.codificacao import detectar_codificacao_csv
from isq_dataanalysys.processamento.sinais import Processamento


_ETIQUETAS = ("Name", "Unit", "HighLim", "LowLim", "Time (s)")
_UNIDADES = {
    "mpa": "MPa", "μm/m": "μm/m", "um/m": "μm/m",
    "mm/m": "mm/m", "g": "g", "mm": "mm",
}


class LinhaFinalIncompleta(ValueError):
    """A interface deve pedir confirmação antes de descartar a última linha."""


def normalizar_unidade(unidade):
    """Padroniza a escrita da unidade, sem converter os valores medidos."""
    texto = "".join(unidade.split()).casefold().replace("µ", "μ")
    return _UNIDADES.get(texto, unidade.strip())


def descrever_canais(canais):
    """Monta a descrição dos canais para as mensagens de importação."""
    return "\n".join(
        f"Canal {c['posicao']} — {c['nome']} ({c['unidade_original'] or 'sem unidade'})"
        for c in canais
    )


def aviso_unidades(info, modalidade):
    """Retorna o aviso sobre canais de outras unidades, sem exibir uma janela."""
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


def _ler_cabecalho(arquivo):
    """Valida as cinco linhas e deixa o arquivo no início das amostras."""
    leitor = csv.reader(arquivo, delimiter=";")
    cabecalho = [next(leitor, []) for _ in _ETIQUETAS]
    for linha, etiqueta in zip(cabecalho, _ETIQUETAS):
        if not linha or linha[0].strip() != etiqueta:
            raise ValueError(
                f"Cabeçalho inválido: esperada a linha {etiqueta}. "
                "Favor conferir o modelo da placa."
            )
    return cabecalho


def _selecionar_canais(cabecalho, unidades_aceitas, modalidade):
    """Descreve e separa os canais, preservando suas posições no CSV."""
    nomes, unidades = cabecalho[:2]
    fim = len(nomes)
    for posicao, celula in enumerate(nomes[1:], 1):
        if celula.strip().casefold().startswith(("sampfreq:", "starttime")):
            fim = posicao
            break
    # Remove só o espaço final sem nome nem unidade, antes dos metadados.
    while fim > 1:
        posicao = fim - 1
        unidade_vazia = posicao >= len(unidades) or not unidades[posicao].strip()
        if nomes[posicao].strip() or not unidade_vazia:
            break
        fim -= 1
    if fim == 1:
        raise ValueError("O arquivo não informa canais na primeira linha.")
    if len(unidades) < fim:
        raise ValueError("Faltam unidades na segunda linha do cabeçalho.")

    aceitos, ignorados, avisos = [], [], []
    for posicao in range(1, fim):
        nome = nomes[posicao].strip()
        if not nome:
            nome = f"Canal {posicao} (sem nome)"
            avisos.append(f"Canal {posicao}: nome vazio no CSV; identificado pela posição original.")
        canal = dict(
            posicao=posicao, nome=nome, unidade_original=unidades[posicao].strip(),
            unidade=normalizar_unidade(unidades[posicao]),
        )
        if canal["unidade"] in unidades_aceitas:
            aceitos.append(canal)
        else:
            ignorados.append(canal)
    if not aceitos:
        raise ValueError(
            f"Nenhum canal compatível com {modalidade}. "
            f"Unidades aceitas: {', '.join(unidades_aceitas)}.\n\n"
            + descrever_canais(ignorados) + "\n\nConfira o CSV e a opção de análise."
        )
    return aceitos, ignorados, avisos, fim - 1


def _ler_amostras(arquivo, quantidade_canais, posicoes, ignorar_ultima_incompleta):
    """Converte números na leitura; limpa apenas colunas que ainda sejam texto."""
    try:
        tabela = pd.read_csv(
            arquivo, sep=";", header=None, decimal=",", float_precision="round_trip",
            keep_default_na=False, skip_blank_lines=False, low_memory=False,
        )
    except pd.errors.EmptyDataError as erro:
        raise ValueError("O arquivo não contém amostras após o cabeçalho.") from erro

    # Lê todas as colunas para não esconder colunas extras com dados.
    while tabela.shape[1] > quantidade_canais + 1:
        ultima = tabela.iloc[:, -1]
        if pd.api.types.is_numeric_dtype(ultima) or not ultima.str.strip().eq("").all():
            break
        tabela = tabela.iloc[:, :-1]
    if tabela.empty or tabela.shape[1] != quantidade_canais + 1:
        raise ValueError("Esperados tempo e uma coluna de dados para cada canal do cabeçalho.")

    selecionadas = {}
    linhas_vazias = np.zeros(len(tabela), dtype=bool)
    for posicao in [0] + posicoes:
        coluna = tabela[posicao]
        if not pd.api.types.is_numeric_dtype(coluna) or pd.api.types.is_bool_dtype(coluna):
            coluna = coluna.astype(str).str.strip()
            linhas_vazias |= coluna.eq("").to_numpy()
        selecionadas[posicao] = coluna

    if linhas_vazias[:-1].any():
        raise ValueError("Existem campos vazios antes da última linha nos canais selecionados.")
    linhas_ignoradas = int(linhas_vazias[-1])
    if linhas_ignoradas and not ignorar_ultima_incompleta:
        raise LinhaFinalIncompleta(
            "A última linha está incompleta nos canais selecionados. "
            f"Há {len(tabela) - 1} linhas anteriores. Isso pode indicar um arquivo truncado."
        )

    # Uma única seleção final substitui as cópias intermediárias da tabela.
    fim = len(tabela) - linhas_ignoradas
    for posicao, coluna in selecionadas.items():
        coluna = coluna.iloc[:fim]
        if not pd.api.types.is_numeric_dtype(coluna):
            coluna = pd.to_numeric(coluna.str.replace(",", ".", regex=False), errors="coerce")
        selecionadas[posicao] = coluna
    tempo = selecionadas.pop(0).to_numpy(dtype=float)
    canais = pd.DataFrame(selecionadas)
    return tempo, canais, linhas_ignoradas


def _ler_frequencia(cabecalho):
    """Lê SampFreq quando presente; a taxa efetiva continua vindo do tempo."""
    linha_nomes = [valor.strip() for valor in cabecalho[0]]
    if "SampFreq:" not in linha_nomes:
        return None
    posicao = linha_nomes.index("SampFreq:") + 1
    try:
        frequencia = float(linha_nomes[posicao].lower().replace("hz", "").replace(",", ".").strip())
    except (IndexError, ValueError) as erro:
        raise ValueError("SampFreq sem valor válido no cabeçalho.") from erro
    if not np.isfinite(frequencia) or frequencia <= 0:
        raise ValueError("Taxa inválida no cabeçalho.")
    return frequencia


def _avaliar_qualidade(cabecalho, canais, aceitos):
    """Registra sinal constante e valores fora dos limites, sem alterar amostras."""
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
    return qualidade


def ler_canais_lynx(caminho, unidades_aceitas, modalidade, ignorar_ultima_incompleta=False):
    """Retorna tempo, canais e info, mantendo o contrato dos leitores de modalidade."""
    codificacao = detectar_codificacao_csv(caminho)
    with open(caminho, encoding=codificacao, newline="") as arquivo:
        cabecalho = _ler_cabecalho(arquivo)
        aceitos, ignorados, avisos, quantidade = _selecionar_canais(
            cabecalho, unidades_aceitas, modalidade
        )
        posicoes = [canal["posicao"] for canal in aceitos]
        tempo, canais, linhas_ignoradas = _ler_amostras(
            arquivo, quantidade, posicoes, ignorar_ultima_incompleta
        )
    if linhas_ignoradas:
        avisos.append("Última linha incompleta ignorada na importação; CSV original preservado.")

    fs = Processamento.validar_dados(tempo, canais)
    fs_cabecalho = _ler_frequencia(cabecalho)
    if fs_cabecalho is not None and not np.isclose(fs, fs_cabecalho, rtol=1e-4):
        avisos.append(f"Cabeçalho: {fs_cabecalho:g} Hz; tempo: {fs:g} Hz. Usando o tempo.")

    info = dict(
        fs=fs, fs_cabecalho=fs_cabecalho, avisos=avisos,
        qualidade=_avaliar_qualidade(cabecalho, canais, aceitos),
        linhas_ignoradas=linhas_ignoradas, ignorados=ignorados,
        nomes={c["posicao"]: c["nome"] for c in aceitos},
        unidades={c["posicao"]: c["unidade"] for c in aceitos},
        unidade=aceitos[0]["unidade"],  # Compatibilidade com as telas existentes.
    )
    return tempo, canais, info
