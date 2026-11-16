"""Validação e tratamentos comuns, sempre preservando os dados de entrada."""
import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view
from scipy.signal import butter, periodogram, sosfiltfilt


class Processamento:
    ORDEM = 4
    _TRATAMENTOS = frozenset({
        "calibracao", "outliers", "janela_outliers", "offset",
        "passa_alta", "passa_baixa", "passa_banda", "media_movel",
    })

    @staticmethod
    def _numero_finito(valor, nome):
        """Converte um parâmetro escalar e padroniza os erros de entrada."""
        try:
            numero = float(valor)
        except (TypeError, ValueError, OverflowError) as erro:
            raise ValueError(f"{nome}: informe um número finito.") from erro
        if not np.isfinite(numero):
            raise ValueError(f"{nome}: informe um número finito.")
        return numero

    @staticmethod
    def _valores(dados):
        """Valida o DataFrame e obtém seus números sem modificar a origem."""
        if not isinstance(dados, pd.DataFrame) or dados.empty:
            raise ValueError("Não há canais carregados.")
        try:
            valores = dados.to_numpy(dtype=float)
        except (TypeError, ValueError, OverflowError) as erro:
            raise ValueError("As medições precisam ser numéricas.") from erro
        if not np.isfinite(valores).all():
            raise ValueError("Existem medições vazias ou não finitas.")
        return valores

    @staticmethod
    def _preparar_dados(tempo, dados):
        """Retorna fs, tempo e valores; evita converter o mesmo DataFrame duas vezes."""
        fs = Processamento.taxa_amostragem(tempo)
        valores = Processamento._valores(dados)
        if len(dados) != len(tempo):
            raise ValueError("Tempo e medições precisam ter o mesmo número de amostras.")
        return fs, np.asarray(tempo, dtype=float), valores

    @staticmethod
    def _quadro(valores, origem):
        """Confere o resultado e preserva os rótulos das linhas e dos canais."""
        if not np.isfinite(valores).all():
            raise ValueError("O cálculo gerou valores inválidos; confira os parâmetros e a amplitude do sinal.")
        return pd.DataFrame(valores, index=origem.index, columns=origem.columns)

    @staticmethod
    def taxa_amostragem(tempo):
        try:
            tempo = np.asarray(tempo, dtype=float)
        except (TypeError, ValueError, OverflowError) as erro:
            raise ValueError("O tempo precisa conter amostras numéricas.") from erro
        if tempo.ndim != 1 or len(tempo) < 2 or not np.isfinite(tempo).all():
            raise ValueError("O tempo precisa conter pelo menos duas amostras válidas.")
        with np.errstate(over="ignore", invalid="ignore"):
            intervalos = np.diff(tempo)
            dt = float(np.mean(intervalos))
        if not np.isfinite(intervalos).all() or np.any(intervalos <= 0):
            raise ValueError("O tempo deve ser crescente, com intervalos finitos e sem repetições.")
        if not np.isfinite(dt) or dt <= 0:
            raise ValueError("O intervalo médio entre as amostras é inválido.")
        if not np.allclose(intervalos, dt, rtol=1e-4, atol=1e-10):
            raise ValueError("Amostragem irregular: confira o arquivo antes de processar o sinal.")
        fs = 1.0 / dt
        if not np.isfinite(fs):
            raise ValueError("A taxa de amostragem calculada não é finita.")
        return fs

    @staticmethod
    def validar_dados(tempo, dados):
        """Mantém a interface utilizada pelos leitores: valida e retorna somente fs."""
        fs, _, _ = Processamento._preparar_dados(tempo, dados)
        return fs

    @staticmethod
    def quantidade(valor, tamanho, nome, minimo=1):
        valor = Processamento._numero_finito(valor, nome)
        if not valor.is_integer():
            raise ValueError(f"{nome}: informe um número inteiro de amostras.")
        n = int(valor)
        if not minimo <= n <= tamanho:
            raise ValueError(f"{nome}: use entre {minimo} e {tamanho} amostras.")
        return n

    @staticmethod
    def calibracao(dados, fator):
        fator = Processamento._numero_finito(fator, "Fator de calibração")
        valores = Processamento._valores(dados)
        with np.errstate(over="ignore", invalid="ignore"):
            return Processamento._quadro(valores * fator, dados)

    @staticmethod
    def ajuste_offset(dados, amostras):
        valores = Processamento._valores(dados)
        n = Processamento.quantidade(amostras, len(dados), "Offset")
        with np.errstate(over="ignore", invalid="ignore"):
            return Processamento._quadro(valores - valores[:n].mean(axis=0), dados)

    @staticmethod
    def filtro_frequencia(dados, corte, fs, tipo):
        fs = Processamento._numero_finito(fs, "Taxa de amostragem")
        if fs <= 0:
            raise ValueError("A taxa de amostragem deve ser positiva.")
        tipos = {"high": "highpass", "highpass": "highpass", "low": "lowpass",
                 "lowpass": "lowpass", "band": "bandpass", "bandpass": "bandpass"}
        if not isinstance(tipo, str) or tipo not in tipos:
            raise ValueError("Use filtro passa-alta, passa-baixa ou passa-banda.")
        tipo = tipos[tipo]
        if tipo == "bandpass":
            try:
                corte = np.asarray(corte, dtype=float)
            except (TypeError, ValueError, OverflowError) as erro:
                raise ValueError("Passa-banda: informe os dois cortes em Hz.") from erro
            if (corte.shape != (2,) or not np.isfinite(corte).all()
                    or not 0 < corte[0] < corte[1] < fs / 2):
                raise ValueError(f"Passa-banda: use 0 < corte inferior < corte superior < {fs / 2:g} Hz.")
        else:
            corte = Processamento._numero_finito(corte, "Frequência de corte")
            if not 0 < corte < fs / 2:
                raise ValueError(f"A frequência de corte deve ser maior que 0 e menor que {fs / 2:g} Hz.")
        valores = Processamento._valores(dados)
        sos = butter(Processamento.ORDEM, corte, btype=tipo, fs=fs, output="sos")
        padlen = 3 * (2 * len(sos) + 1 - min(
            int((sos[:, 2] == 0).sum()), int((sos[:, 5] == 0).sum())
        ))
        if len(dados) <= padlen:
            raise ValueError(f"Arquivo curto para esse filtro: são necessárias mais de {padlen} amostras.")
        resultado = sosfiltfilt(sos, valores, axis=0, padlen=padlen)
        return Processamento._quadro(resultado, dados)

    @staticmethod
    def passa_alta(dados, corte, fs):
        return Processamento.filtro_frequencia(dados, corte, fs, "highpass")

    @staticmethod
    def passa_baixa(dados, corte, fs):
        return Processamento.filtro_frequencia(dados, corte, fs, "lowpass")

    @staticmethod
    def passa_banda(dados, corte_inferior, corte_superior, fs):
        """Butterworth em SOS aplicado em ida e volta, como os demais filtros."""
        return Processamento.filtro_frequencia(dados, (corte_inferior, corte_superior), fs, "bandpass")

    @staticmethod
    def media_movel(dados, amostras):
        valores = Processamento._valores(dados)
        n = Processamento.quantidade(amostras, len(dados), "Média móvel")
        quadro = pd.DataFrame(valores, index=dados.index, columns=dados.columns)
        # Nas bordas, usa só as amostras disponíveis. Preserva tempo e tamanho.
        resultado = quadro.rolling(window=n, center=True, min_periods=1).mean()
        return Processamento._quadro(resultado.to_numpy(), dados)

    @staticmethod
    def remover_outliers(dados, limiar, janela=31):
        """Hampel local: substitui pela mediana, sem excluir linhas ou alterar a origem."""
        valores = Processamento._valores(dados)
        limiar = Processamento._numero_finito(limiar, "Limiar de outliers")
        if limiar <= 0:
            raise ValueError("O limiar de outliers deve ser positivo.")
        n = Processamento.quantidade(janela, len(dados), "Janela de outliers", minimo=3)
        if n % 2 == 0:
            raise ValueError("A janela de outliers deve ter um número ímpar de amostras.")
        tratados = valores.copy()
        contagens = np.zeros(valores.shape[1], dtype=int)
        metade = n // 2
        extendido = np.pad(valores, ((metade, metade), (0, 0)), mode="reflect")
        janelas = sliding_window_view(extendido, n, axis=0)
        tolerancia = 32 * np.finfo(float).eps * np.maximum(1, np.max(np.abs(valores), axis=0))
        lote = max(1, min(2048, 1000000 // (n * valores.shape[1])))
        for inicio in range(0, len(valores), lote):
            fim = min(inicio + lote, len(valores))
            bloco = janelas[inicio:fim]
            medianas = np.median(bloco, axis=-1)
            desvios = bloco - medianas[..., None]
            np.abs(desvios, out=desvios)
            # Só o temporário pode ser sobrescrito; a janela aponta para os dados originais.
            mad = np.median(desvios, axis=-1, overwrite_input=True)
            limite = np.maximum(limiar * 1.4826 * mad, tolerancia)
            mascara = np.abs(valores[inicio:fim] - medianas) > limite
            np.copyto(tratados[inicio:fim], medianas, where=mascara)
            contagens += mascara.sum(axis=0)
        resultado = Processamento._quadro(tratados, dados)
        return resultado, dict(zip(dados.columns, map(int, contagens)))

    @staticmethod
    def aplicar(tempo, original, configuracao):
        """Aplica os tratamentos na ordem histórica e retorna uma tabela independente."""
        fs = Processamento.validar_dados(tempo, original)
        if not isinstance(configuracao, dict) or set(configuracao) - Processamento._TRATAMENTOS:
            raise ValueError("Configuração de tratamento desconhecida.")
        alta, baixa = configuracao.get("passa_alta"), configuracao.get("passa_baixa")
        if alta is not None:
            alta = Processamento._numero_finito(alta, "Corte passa-alta")
        if baixa is not None:
            baixa = Processamento._numero_finito(baixa, "Corte passa-baixa")
        if alta is not None and baixa is not None and alta >= baixa:
            raise ValueError("O corte do passa-alta precisa ser menor que o do passa-baixa.")
        resultado = original
        info = {"fs": fs, "substituicoes": {}}
        if "calibracao" in configuracao:
            resultado = Processamento.calibracao(resultado, configuracao["calibracao"])
        if "outliers" in configuracao:
            resultado, info["substituicoes"] = Processamento.remover_outliers(
                resultado, configuracao["outliers"], configuracao.get("janela_outliers", 31)
            )
        if "offset" in configuracao:
            resultado = Processamento.ajuste_offset(resultado, configuracao["offset"])
        if "passa_banda" in configuracao:
            resultado = Processamento.filtro_frequencia(resultado, configuracao["passa_banda"], fs, "bandpass")
        if alta is not None:
            resultado = Processamento.passa_alta(resultado, alta, fs)
        if baixa is not None:
            resultado = Processamento.passa_baixa(resultado, baixa, fs)
        if "media_movel" in configuracao:
            resultado = Processamento.media_movel(resultado, configuracao["media_movel"])
        # Cada tratamento já cria e confere seu resultado. Só copia se nenhum foi aplicado.
        return (resultado.copy() if resultado is original else resultado), info

    @staticmethod
    def _rms(valores, eixo=0, remover_media=False):
        """RMS com escala local: evita elevar amplitudes grandes diretamente ao quadrado."""
        normalizados = valores.copy()
        if remover_media:
            # Retira uma referência antes da escala para preservar oscilações pequenas sobre DC grande.
            with np.errstate(over="ignore"):
                normalizados -= np.take(valores, [0], axis=eixo)
            escala = np.max(np.abs(normalizados), axis=eixo, keepdims=True)
            # Diferenças entre extremos finitos podem transbordar; nesses grupos, escala a entrada.
            estourou = ~np.isfinite(escala)
            if estourou.any():
                np.copyto(normalizados, valores, where=estourou)
                escala = np.max(np.abs(normalizados), axis=eixo, keepdims=True)
        else:
            escala = np.max(np.abs(normalizados), axis=eixo, keepdims=True)
        np.divide(normalizados, escala, out=normalizados, where=escala != 0)
        if remover_media:
            normalizados -= normalizados.mean(axis=eixo, keepdims=True)
        np.square(normalizados, out=normalizados)
        return np.squeeze(escala, axis=eixo) * np.sqrt(normalizados.mean(axis=eixo))

    @staticmethod
    def rms_ac(tempo, dados, janela_s=0.5):
        """RMS sem a média de cada janela; inclui a cauda somente se tiver 2+ amostras."""
        fs, tempo, valores = Processamento._preparar_dados(tempo, dados)
        janela_s = Processamento._numero_finito(janela_s, "Janela RMS")
        with np.errstate(over="ignore"):
            quantidade = janela_s * fs
        if janela_s <= 0 or not np.isfinite(quantidade):
            raise ValueError("A janela RMS deve ser positiva e ter duração válida.")
        n = int(round(quantidade))
        if not 2 <= n <= len(dados):
            raise ValueError(f"Escolha uma janela RMS entre {2/fs:g} e {len(dados)/fs:g} segundos.")
        completas, resto = divmod(len(dados), n)
        incluir_cauda = resto >= 2
        quantidade_janelas = completas + int(incluir_cauda)
        tempos_rms = np.empty(quantidade_janelas)
        valores_rms = np.empty((quantidade_janelas, valores.shape[1]))
        # Vetoriza várias janelas por vez e limita os temporários a cerca de 1 milhão de valores.
        lote = max(1, 1000000 // (n * valores.shape[1]))
        for inicio in range(0, completas, lote):
            fim = min(inicio + lote, completas)
            blocos = valores[inicio*n:fim*n].reshape(fim-inicio, n, valores.shape[1])
            valores_rms[inicio:fim] = Processamento._rms(blocos, eixo=1, remover_media=True)
            tempos_rms[inicio:fim] = tempo[inicio*n:fim*n].reshape(fim-inicio, n).mean(axis=1)
        if incluir_cauda:
            valores_rms[-1] = Processamento._rms(valores[completas*n:], remover_media=True)
            tempos_rms[-1] = tempo[completas*n:].mean()
        info = {"amostras_por_janela": n, "janela_efetiva_s": n / fs,
                "ultima_janela": resto if incluir_cauda else n, "descartadas": int(resto == 1)}
        return tempos_rms, pd.DataFrame(valores_rms, columns=dados.columns), info

    @staticmethod
    def _retirar_tendencia(tempo, dados, grau):
        """Ajuste LS compartilhado: coeficientes de c0+c1·τ+c2·τ², com τ=t-t[0]."""
        _, t, valores = Processamento._preparar_dados(tempo, dados)
        grau = Processamento.quantidade(grau, 2, "Grau do polinômio", minimo=1)
        if len(t) < grau + 1:
            raise ValueError(f"São necessárias pelo menos {grau + 1} amostras para esse ajuste.")
        try:
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                duracao = t[-1] - t[0]
                x = 2 * ((t - t[0]) / duracao) - 1
                matriz = np.polynomial.polynomial.polyvander(x, grau)
                coef, _, posto, _ = np.linalg.lstsq(matriz, valores, rcond=None)
                corrigidos = valores - matriz @ coef
                parametros = {"c0": coef[0] - coef[1], "c1": 2 * coef[1] / duracao}
                if grau == 2:
                    parametros["c0"] += coef[2]
                    parametros["c1"] -= 4 * coef[2] / duracao
                    parametros["c2"] = (4 * coef[2] / duracao) / duracao
        except (FloatingPointError, np.linalg.LinAlgError) as erro:
            raise ValueError("Não foi possível ajustar o polinômio ao sinal.") from erro
        ajustes = pd.DataFrame(parametros, index=dados.columns)
        if posto != grau + 1 or not np.isfinite(ajustes.to_numpy()).all():
            raise ValueError("O ajuste polinomial não pôde ser determinado.")
        return Processamento._quadro(corrigidos, dados), ajustes

    @staticmethod
    def fft_ac(tempo, dados):
        """Amplitude de pico unilateral, sem média; janela retangular e resolução fs/N."""
        fs, _, valores = Processamento._preparar_dados(tempo, dados)
        n = len(valores)
        with np.errstate(over="ignore", invalid="ignore"):
            centralizado = valores - valores.mean(axis=0)
            amplitudes = np.abs(np.fft.rfft(centralizado, axis=0)) / n
            # Não duplica DC nem Nyquist.
            if n % 2 == 0:
                amplitudes[1:-1] *= 2
            else:
                amplitudes[1:] *= 2
        if not np.isfinite(amplitudes).all():
            raise ValueError("A FFT gerou valores inválidos; confira a amplitude do sinal.")
        frequencias = np.fft.rfftfreq(n, d=1 / fs)
        info = {"fs": fs, "resolucao_hz": fs / n, "amostras": n}
        return frequencias, pd.DataFrame(amplitudes, columns=dados.columns), info

    @staticmethod
    def psd_ac(tempo, dados):
        """Periodograma AC retangular: unidade²/Hz e soma(PSD)·Δf = média quadrática AC."""
        fs, _, valores = Processamento._preparar_dados(tempo, dados)
        frequencias, densidade = periodogram(
            valores, fs=fs, window="boxcar", detrend="constant",
            return_onesided=True, scaling="density", axis=0,
        )
        if not np.isfinite(densidade).all():
            raise ValueError("A PSD gerou valores inválidos; confira a amplitude do sinal.")
        info = {"fs": fs, "resolucao_hz": fs / len(dados), "amostras": len(dados),
                "metodo": "periodograma unilateral", "janela": "retangular"}
        return frequencias, pd.DataFrame(densidade, columns=dados.columns), info
