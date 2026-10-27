"""Leitura do CSV Lynx: canais identificados pelo número no cabeçalho."""
import csv
import re

import numpy as np
import pandas as pd

from processamento import Processamento


class LinhaFinalIncompleta(ValueError):
    """Permite à interface pedir confirmação antes de ignorar a última linha."""


def ler_lynx_extensometria(caminho, ignorar_ultima_incompleta=False):
    with open(caminho, encoding="utf-8-sig", newline="") as arquivo:
        leitor = csv.reader(arquivo, delimiter=";")
        cabecalho = [next(leitor, []) for _ in range(5)]
        primeira_amostra = next(leitor, [])

    etiquetas = ["Name", "Unit", "HighLim", "LowLim", "Time (s)"]
    for linha, etiqueta in zip(cabecalho, etiquetas):
        if not linha or linha[0].strip() != etiqueta:
            raise ValueError(f"Cabeçalho inválido: esperada a linha {etiqueta}.")

    nomes = []
    for celula in cabecalho[0][1:]:
        nome = celula.strip()
        if not nome:
            break  # O restante dessa linha contém metadados, como SampFreq.
        nomes.append(nome)
    if not nomes:
        raise ValueError("O arquivo não informa canais.")

    mapa_canais = {}
    for nome in nomes:
        correspondencia = re.fullmatch(r"Channel\s+(\d+)", nome, flags=re.IGNORECASE)
        if correspondencia is None:
            raise ValueError(f"Nome não reconhecido: {nome}. Esperado Channel N.")
        numero = int(correspondencia.group(1))
        if not 1 <= numero <= 16 or numero in mapa_canais:
            raise ValueError(f"Canal {numero}: use números únicos entre 1 e 16.")
        mapa_canais[numero] = nome

    n_canais = len(nomes)
    for linha in cabecalho[1:4]:
        if len(linha) < n_canais + 1:
            raise ValueError("Faltam unidades ou limites no cabeçalho.")
    unidades = [valor.strip() for valor in cabecalho[1][1:n_canais + 1]]
    if not unidades[0] or len(set(unidades)) != 1:
        raise ValueError("Este gráfico requer a mesma unidade em todos os canais.")

    limites_altos = np.array([float(v.replace(",", ".")) for v in cabecalho[2][1:n_canais + 1]])
    limites_baixos = np.array([float(v.replace(",", ".")) for v in cabecalho[3][1:n_canais + 1]])
    if (not np.isfinite(limites_altos).all() or not np.isfinite(limites_baixos).all()
            or np.any(limites_baixos >= limites_altos)):
        raise ValueError("Limites inválidos no cabeçalho.")

    decimal = "," if any("," in valor for valor in primeira_amostra) else "."
    tabela = pd.read_csv(
        caminho, sep=";", decimal=decimal, skiprows=5, header=None,
        encoding="utf-8-sig", dtype=float, skip_blank_lines=False,
    )
    if tabela.empty or tabela.shape[1] != n_canais + 1:
        raise ValueError("Esperados tempo e uma coluna numérica para cada canal do cabeçalho.")

    avisos = []
    linhas_ignoradas = 0
    # Uma falha no meio do registro continua sendo um erro: não pulamos lacunas.
    if tabela.iloc[-1].isna().any():
        if tabela.iloc[:-1].isna().any().any():
            raise ValueError("Existem campos vazios antes da última linha. Revise o CSV.")
        mensagem = (
            f"A última linha de dados está incompleta. Há {len(tabela) - 1} linhas anteriores. "
            "Isso pode indicar um arquivo truncado."
        )
        if not ignorar_ultima_incompleta:
            raise LinhaFinalIncompleta(mensagem)
        tabela = tabela.iloc[:-1].copy()
        linhas_ignoradas = 1
        avisos.append("Última linha incompleta ignorada na importação; CSV original preservado.")

    tabela.columns = ["Tempo"] + nomes
    tempo = tabela["Tempo"].to_numpy()
    canais = tabela.drop(columns="Tempo")
    fs = Processamento.validar_dados(tempo, canais)

    linha_nomes = [valor.strip() for valor in cabecalho[0]]
    fs_cabecalho = None
    if "SampFreq:" in linha_nomes:
        posicao = linha_nomes.index("SampFreq:") + 1
        if posicao >= len(linha_nomes):
            raise ValueError("SampFreq sem valor no cabeçalho.")
        valor_fs = linha_nomes[posicao].lower().replace("hz", "").strip().replace(",", ".")
        fs_cabecalho = float(valor_fs)
        if not np.isfinite(fs_cabecalho) or fs_cabecalho <= 0:
            raise ValueError("Taxa inválida no cabeçalho.")
        if not np.isclose(fs, fs_cabecalho, rtol=1e-4):
            avisos.append(f"Cabeçalho: {fs_cabecalho:g} Hz; tempo: {fs:g} Hz. Usando o tempo.")

    qualidade = {}
    for numero, nome in mapa_canais.items():
        coluna = nomes.index(nome)
        serie = canais[nome]
        problemas = []
        if serie.min() == serie.max():
            problemas.append(f"sinal constante em {serie.iloc[0]:g} {unidades[0]}")
        fora = int(((serie < limites_baixos[coluna]) | (serie > limites_altos[coluna])).sum())
        if fora:
            problemas.append(f"{fora} amostras fora dos limites informados no arquivo")
        if problemas:
            qualidade[numero] = "; ".join(problemas)

    info = {
        "fs": fs, "fs_cabecalho": fs_cabecalho, "unidade": unidades[0],
        "avisos": avisos, "qualidade": qualidade,
        "linhas_ignoradas": linhas_ignoradas,
    }
    return tempo, canais, mapa_canais, info