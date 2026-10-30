"""Extensometria: tensão em MPa e deformação em μm/m ou mm/m."""
from isq_dataanalysys.leitores.lynx import ler_canais_lynx


def ler_lynx_extensometria(caminho, ignorar_ultima_incompleta=False):
    tempo, canais, info = ler_canais_lynx(
        caminho, ("MPa", "μm/m", "mm/m"), "extensometria", ignorar_ultima_incompleta
    )
    return tempo, canais, info["nomes"], info
