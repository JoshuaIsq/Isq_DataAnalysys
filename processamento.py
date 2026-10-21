"""Tratamentos comuns. Nenhum método modifica o DataFrame recebido."""

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view
from scipy.signal import butter, sosfiltfilt


class Processamento:
    ORDEM = 4

    @staticmethod
    def taxa_amostragem(tempo):
        tempo = np.asarray(tempo, dtype=float)
        if tempo.ndim != 1 or len(tempo) < 2 or not np.isfinite(tempo).all():
            raise ValueError("O tempo precisa conter pelo menos duas amostras válidas.")
        intervalos = np.diff(tempo)
        if np.any(intervalos <= 0):
            raise ValueError("O tempo deve ser crescente, sem repetições.")
        dt = float(np.mean(intervalos))
        if not np.allclose(intervalos, dt, rtol=1e-4, atol=1e-10):
            raise ValueError("Amostragem irregular: confira o arquivo antes de filtrar ou calcular RMS.")
        return 1.0 / dt

    @staticmethod
    def validar_dados(tempo, dados):
        fs = Processamento.taxa_amostragem(tempo)
        if not isinstance(dados, pd.DataFrame) or dados.empty:
            raise ValueError("Não há canais carregados.")
        if len(dados) != len(tempo):
            raise ValueError("Tempo e medições precisam ter o mesmo número de amostras.")
        if not np.isfinite(dados.to_numpy(dtype=float)).all():
            raise ValueError("Existem medições vazias ou não finitas.")
        return fs

    @staticmethod
    def quantidade(valor, tamanho, nome, minimo=1):
        valor = float(valor)
        if not np.isfinite(valor) or not valor.is_integer():
            raise ValueError(f"{nome}: informe um número inteiro de amostras.")
        n = int(valor)
        if not minimo <= n <= tamanho:
            raise ValueError(f"{nome}: use entre {minimo} e {tamanho} amostras.")
        return n

    @staticmethod
    def calibracao(dados, fator):
        fator = float(fator)
        if not np.isfinite(fator):
            raise ValueError("O fator de calibração deve ser finito.")
        return dados * fator

    @staticmethod
    def ajuste_offset(dados, amostras):
        n = Processamento.quantidade(amostras, len(dados), "Offset")
        referencia = dados.iloc[:n].mean()
        return dados.subtract(referencia, axis="columns")

    @staticmethod
    def filtro_frequencia(dados, corte, fs, tipo):
        corte = float(corte)
        if not np.isfinite(corte) or not 0 < corte < fs / 2:
            raise ValueError(f"A frequência de corte deve ser maior que 0 e menor que {fs / 2:g} Hz.")
        sos = butter(Processamento.ORDEM, corte, btype=tipo, fs=fs, output="sos")
        padlen = 3 * (2 * len(sos) + 1 - min(
            int((sos[:, 2] == 0).sum()), int((sos[:, 5] == 0).sum())
        ))
        if len(dados) <= padlen:
            raise ValueError(f"Arquivo curto para esse filtro: são necessárias mais de {padlen} amostras.")
        valores = sosfiltfilt(sos, dados.to_numpy(dtype=float), axis=0)
        return pd.DataFrame(valores, index=dados.index, columns=dados.columns)

    @staticmethod
    def passa_alta(dados, corte, fs):
        return Processamento.filtro_frequencia(dados, corte, fs, "highpass")

    @staticmethod
    def passa_baixa(dados, corte, fs):
        return Processamento.filtro_frequencia(dados, corte, fs, "lowpass")

    @staticmethod
    def media_movel(dados, amostras):
        n = Processamento.quantidade(amostras, len(dados), "Média móvel")
        # Nas bordas, usa apenas as amostras disponíveis. Preserva tempo e tamanho.
        return dados.rolling(window=n, center=True, min_periods=1).mean()

    @staticmethod
    def remover_outliers(dados, limiar, janela=31):
        """Hampel local: substitui candidatos pela mediana, sem excluir linhas."""
        limiar = float(limiar)
        if not np.isfinite(limiar) or limiar <= 0:
            raise ValueError("O limiar de outliers deve ser positivo.")
        n = Processamento.quantidade(janela, len(dados), "Janela de outliers", minimo=3)
        if n % 2 == 0:
            raise ValueError("A janela de outliers deve ter um número ímpar de amostras.")
        valores = dados.to_numpy(dtype=float)
        tratados = valores.copy()
        contagens = np.zeros(valores.shape[1], dtype=int)
        metade = n // 2
        extendido = np.pad(valores, ((metade, metade), (0, 0)), mode="reflect")
        janelas = sliding_window_view(extendido, n, axis=0)
        tolerancia = 32 * np.finfo(float).eps * np.maximum(1, np.max(np.abs(valores), axis=0))
        # Processamento em blocos limita a memória usada pelo cálculo da MAD.
        lote = max(1, min(2048, 1000000 // (n * valores.shape[1])))
        for inicio in range(0, len(valores), lote):
            fim = min(inicio + lote, len(valores))
            bloco = janelas[inicio:fim]
            medianas = np.median(bloco, axis=-1)
            mad = np.median(np.abs(bloco - medianas[..., None]), axis=-1)
            limite = np.maximum(limiar * 1.4826 * mad, tolerancia)
            mascara = np.abs(valores[inicio:fim] - medianas) > limite
            tratados[inicio:fim] = np.where(mascara, medianas, valores[inicio:fim])
            contagens += mascara.sum(axis=0)
        resultado = pd.DataFrame(tratados, index=dados.index, columns=dados.columns)
        return resultado, dict(zip(dados.columns, map(int, contagens)))

    @staticmethod
    def aplicar(tempo, original, configuracao):
        fs = Processamento.validar_dados(tempo, original)
        permitidos = {"calibracao", "outliers", "janela_outliers", "offset",
                      "passa_alta", "passa_baixa", "media_movel"}
        if set(configuracao) - permitidos:
            raise ValueError("Configuração de tratamento desconhecida.")
        alta = configuracao.get("passa_alta")
        baixa = configuracao.get("passa_baixa")
        if alta is not None and baixa is not None and alta >= baixa:
            raise ValueError("O corte do passa-alta precisa ser menor que o do passa-baixa.")
        resultado = original.copy()
        info = {"fs": fs, "substituicoes": {}}
        if "calibracao" in configuracao:
            resultado = Processamento.calibracao(resultado, configuracao["calibracao"])
        if "outliers" in configuracao:
            resultado, info["substituicoes"] = Processamento.remover_outliers(
                resultado, configuracao["outliers"], configuracao.get("janela_outliers", 31)
            )
        if "offset" in configuracao:
            resultado = Processamento.ajuste_offset(resultado, configuracao["offset"])
        if alta is not None:
            resultado = Processamento.passa_alta(resultado, alta, fs)
        if baixa is not None:
            resultado = Processamento.passa_baixa(resultado, baixa, fs)
        if "media_movel" in configuracao:
            resultado = Processamento.media_movel(resultado, configuracao["media_movel"])
        if not np.isfinite(resultado.to_numpy()).all():
            raise ValueError("O tratamento gerou valores inválidos. Revise os parâmetros.")
        return resultado, info

    @staticmethod
    def rms_ac(tempo, dados, janela_s=0.5):
        fs = Processamento.validar_dados(tempo, dados)
        janela_s = float(janela_s)
        if not np.isfinite(janela_s) or janela_s <= 0:
            raise ValueError("A janela RMS deve ser positiva.")
        n = int(round(janela_s * fs))
        if not 2 <= n <= len(dados):
            raise ValueError(f"Escolha uma janela RMS entre {2/fs:g} e {len(dados)/fs:g} segundos.")
        valores = dados.to_numpy(dtype=float)
        tempos_rms, valores_rms, tamanhos = [], [], []
        for inicio in range(0, len(dados), n):
            fim = min(inicio + n, len(dados))
            trecho = valores[inicio:fim]
            if len(trecho) < 2:
                break  # Uma amostra isolada não estima uma oscilação.
            centralizado = trecho - trecho.mean(axis=0)
            rms = np.sqrt(np.mean(centralizado ** 2, axis=0))
            # Uma janela exatamente constante tem RMS AC zero, inclusive após arredondamentos da média.
            rms[np.ptp(trecho, axis=0) == 0] = 0.0
            valores_rms.append(rms)
            tempos_rms.append(np.mean(tempo[inicio:fim]))
            tamanhos.append(len(trecho))
        info = {"amostras_por_janela": n, "janela_efetiva_s": n / fs,
                "ultima_janela": tamanhos[-1], "descartadas": len(dados) - sum(tamanhos)}
        return np.asarray(tempos_rms), pd.DataFrame(valores_rms, columns=dados.columns), info