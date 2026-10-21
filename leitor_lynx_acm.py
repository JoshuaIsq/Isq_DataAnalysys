import csv
import numpy as np
import pandas as pd

def ler_lynx_acelerometria(caminho):
    # Lê as cinco primeiras linhas do arquivo.
    with open(caminho, encoding="utf-8-sig", newline="") as arquivo:
        leitor = csv.reader(arquivo, delimiter=";")
        cabecalho = [next(leitor, []) for _ in range(5)]

    if (not cabecalho[0] or cabecalho[0][0] != "Name" or cabecalho[4] != ["Time (s)"]):
        raise ValueError("O arquivo não possui o cabeçalho Lynx esperado.")

    # A primeira linha contém os nomes dos 12 canais.
    nomes = [nome.strip() for nome in cabecalho[0][1:13]]

    sensores = []

    for nome in nomes:
        sensor = nome.rsplit(" - ", 1)[0]

        if sensor not in sensores:
            sensores.append(sensor)

    esperados = {f"{sensor} - {eixo}" for sensor in sensores for eixo in ("X", "Y", "Z")}

    if len(sensores) != 4 or len(nomes) != 12 or set(nomes) != esperados:
        raise ValueError("Esperados quatro sensores com os eixos X, Y e Z.")

    # Lê as medições, que começam depois das cinco linhas iniciais.
    dados = pd.read_csv(
        caminho,
        sep=";",
        decimal=",",
        skiprows=5,
        header=None,
        encoding="utf-8-sig",
        dtype=float,
    )

    if dados.empty or dados.shape[1] != 13:
        raise ValueError("Esperadas uma coluna de tempo e 12 de medição.")

    if not np.isfinite(dados.to_numpy()).all():
        raise ValueError("Há valores vazios ou inválidos no arquivo.")

    dados.columns = ["Tempo"] + nomes

    tempo = dados["Tempo"].to_numpy()

    if np.any(np.diff(tempo) <= 0):
        raise ValueError("O tempo deve ser crescente, sem repetições.")

    canais = dados.drop(columns="Tempo")

    return tempo, canais, sensores