"""Metadados temporais dos CSVs Lynx, com diagnóstico da leitura do cabeçalho."""
import csv
from datetime import datetime
import re
import unicodedata

from .codificacao import detectar_codificacao_csv


_ETIQUETA = re.compile(r"^\s*start[\s_-]*time(?=\W|utc|gmt|$)", re.IGNORECASE)
_DATA_HORA = re.compile(
    r"^\s*(?:UTC\s*[:=]?\s*)?"
    r"(?P<data>\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{4})"
    r"[\sTt_-]+(?P<hora>\d{1,2}):(?P<minuto>\d{2})"
    r"(?::(?P<segundo>\d{2})(?:[.,](?P<fracao>\d{1,9}))?)?"
    r"\s*(?:Z|(?:UTC|GMT)(?:\s*[+-]\d{1,2}(?::?\d{2})?)?|[+-]\d{2}:?\d{2})?\s*$",
    re.IGNORECASE,
)


def interpretar_data_hora(valor):
    """Lê o relógio registrado, sem converter fuso nem descontar as três horas."""
    texto = unicodedata.normalize("NFKC", str(valor)).strip().strip("\"'").strip()
    encontrado = _DATA_HORA.fullmatch(texto)
    if encontrado is None:
        return None
    partes = re.split(r"[-/.]", encontrado["data"])
    ano, mes, dia = map(int, partes if len(partes[0]) == 4 else partes[::-1])
    micros = int((encontrado["fracao"] or "").ljust(6, "0")[:6])
    try:
        return datetime(ano, mes, dia, int(encontrado["hora"]), int(encontrado["minuto"]),
                        int(encontrado["segundo"] or 0), micros)
    except ValueError:
        return None


def ler_referencia_temporal(caminho):
    """Retorna horário original, campo/valor encontrados e motivo de eventual falha."""
    info = dict(inicio=None, etiqueta="", valor="", linha=None,
                erro="Campo StartTime não encontrado nas cinco linhas do cabeçalho.")
    if not caminho:
        return info
    try:
        with open(caminho, encoding=detectar_codificacao_csv(caminho), newline="") as arquivo:
            leitor = csv.reader(arquivo, delimiter=";")
            for numero in range(1, 6):
                linha = next(leitor, [])
                for indice, celula in enumerate(linha):
                    texto = unicodedata.normalize("NFKC", celula)
                    etiqueta = _ETIQUETA.match(texto)
                    if etiqueta is None:
                        continue
                    # Tenta o valor seguinte, células separadas e, por fim, valor embutido.
                    seguintes = linha[indice + 1:]
                    while seguintes and not seguintes[0].strip():
                        seguintes = seguintes[1:]
                    candidatos = seguintes[:1]
                    if len(seguintes) > 1:
                        candidatos.append(seguintes[0].strip() + " " + seguintes[1].strip())
                    embutido = texto[etiqueta.end():].strip().lstrip(":=").strip()
                    if embutido:
                        candidatos.append(embutido)
                        data = re.search(r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{4}", embutido)
                        if data:
                            candidatos.append(embutido[data.start():])
                    info.update(etiqueta=celula, valor=candidatos[0] if candidatos else "", linha=numero,
                                erro="O campo StartTime foi encontrado, mas sua data/hora não foi reconhecida.")
                    for valor in candidatos:
                        inicio = interpretar_data_hora(valor)
                        if inicio is not None:
                            info.update(inicio=inicio, valor=valor, erro="")
                            return info
    except (OSError, UnicodeError, csv.Error) as erro:
        info["erro"] = f"Não foi possível ler a referência temporal: {erro}"
    return info


def ler_inicio_lynx(caminho):
    """Compatibilidade: retorna apenas a data/hora original ou None."""
    return ler_referencia_temporal(caminho)["inicio"]
