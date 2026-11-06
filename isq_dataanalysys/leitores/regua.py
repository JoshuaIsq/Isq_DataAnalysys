"""Deslocamento medido diretamente pelos canais Lynx cuja unidade é mm."""
from .lynx import ler_canais_lynx


def ler_lynx_regua(caminho, ignorar_ultima_incompleta=False):
    tempo, canais, info = ler_canais_lynx(
        caminho, ("mm",), "régua potenciométrica", ignorar_ultima_incompleta
    )
    return tempo, canais, info["nomes"], info
