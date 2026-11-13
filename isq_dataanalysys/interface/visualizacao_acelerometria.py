"""Os mesmos campos da extensometria, aplicados aos painéis de cada sensor."""
import numpy as np
from PySide6.QtWidgets import QMessageBox

from .visualizacao_temporal import VisualizacaoTemporal


class VisualizacaoAcelerometria(VisualizacaoTemporal):
    def reiniciar_limites_visualizacao(self):
        self._intervalo_temporal = None
        self._escalas_modos = {}
        self.habilitar_limites_visualizacao()

    def modo_escala(self):
        if self.botao_fft.isChecked():
            return "fft"
        if self.botao_psd.isChecked():
            return 'psd'
        sufixo = '_mm' if self.botao_converter.isChecked() else ''
        if self.botao_rms.isChecked():
            return ('rms_log' if self.checkbox_log_rms.isChecked() else 'rms') + sufixo
        return 'tempo' + sufixo

    def segundos_do_campo(self, campo):
        anterior = getattr(self, '_tempos_apresentados', {}).get(campo)
        if anterior and campo.value() == anterior[0]:
            return anterior[1]
        segundos = super().segundos_do_campo(campo)
        # A conversão segundos → minutos → spinbox não pode excluir uma amostra
        # que coincidia com o limite antes do arredondamento de apresentação.
        posicao = int(np.searchsorted(self.tempo, segundos))
        tolerancia = 30 * 10 ** (-campo.decimals()) + np.spacing(max(abs(segundos), 1)) * 8
        for indice in (posicao - 1, posicao):
            if 0 <= indice < len(self.tempo) and abs(self.tempo[indice] - segundos) <= tolerancia:
                return float(self.tempo[indice])
        return segundos

    def escala_dos_canais_visiveis(self):
        log = self.modo_escala().startswith('rms_log')
        extremos = []
        for curva in self.curvas_lynx.values():
            if not curva.isVisible():
                continue
            valores = np.asarray(curva.getOriginalDataset()[1])
            valores = valores[np.isfinite(valores)]
            if log:
                valores = valores[valores > 0]
            if valores.size:
                extremos.append((float(valores.min()), float(valores.max())))
        if not extremos:
            return (0.1, 1.0) if log else (-1.0, 1.0)
        minimo = min(v[0] for v in extremos)
        maximo = max(v[1] for v in extremos)
        if log:
            baixo, alto = np.log10([minimo, maximo])
            margem = max((alto - baixo) * 0.05, 0.05)
            return (10 ** (baixo - margem), 10 ** (alto + margem))
        margem = max((maximo - minimo) * 0.05, abs(maximo) * 1e-6, 1e-8)
        return minimo - margem, maximo + margem

    def atualizar_limites_visualizacao(self):
        """Preserva escala manual por modo e o intervalo temporal ao alternar FFT/RMS."""
        fft = self.modo_espectral()
        for campo in (self.campo_tempo_inicio, self.campo_tempo_fim):
            campo.setEnabled(not fft)
        unidade = ('g²/Hz' if self.botao_psd.isChecked() else 'g' if self.botao_fft.isChecked()
                   else 'mg' if self.botao_rms.isChecked() and not self.botao_converter.isChecked()
                   else self.unidade_aceleracao)
        for campo in (self.campo_y_min, self.campo_y_max):
            # Densidades em g²/Hz podem ser muito menores que 0,001.
            campo.setDecimals(10 if self.botao_psd.isChecked() else 3)
            campo.setSuffix(" " + unidade)
        escala = self._escalas_modos.get(self.modo_escala())
        if escala is None:
            escala = self.escala_dos_canais_visiveis()
        self.campo_y_min.setValue(float(escala[0]))
        self.campo_y_max.setValue(float(escala[1]))
        self._escala_apresentada = ((self.campo_y_min.value(), self.campo_y_max.value()), tuple(escala))
        temporal = self._intervalo_temporal or (float(self.tempo[0]), float(self.tempo[-1]))
        self.campo_tempo_inicio.setValue(temporal[0] / 60)
        self.campo_tempo_fim.setValue(temporal[1] / 60)
        self._tempos_apresentados = {
            campo: (campo.value(), valor) for campo, valor in
            zip((self.campo_tempo_inicio, self.campo_tempo_fim), temporal)
        }
        if fft:
            frequencias = next(iter(self.curvas_lynx.values())).getOriginalDataset()[0]
            intervalo = (float(frequencias[0]), float(frequencias[-1]))
        else:
            intervalo = temporal
        escala_plot = np.log10(escala) if self.modo_escala().startswith('rms_log') else escala
        for grafico in self.graficos_eixos.values():
            grafico.setRange(xRange=intervalo, yRange=escala_plot, padding=0, disableAutoRange=True)

    def aplicar_visualizacao(self):
        if self.df_sensores is None:
            return False
        escala = (self.campo_y_min.value(), self.campo_y_max.value())
        if escala == self._escala_apresentada[0]:
            escala = self._escala_apresentada[1]
        if escala[0] >= escala[1]:
            QMessageBox.warning(self, "Limites inválidos", "A escala mínima deve ser menor que a máxima.")
            return False
        if self.modo_escala().startswith('rms_log') and escala[0] <= 0:
            QMessageBox.warning(self, "Limites inválidos", "Na escala logarítmica, os limites devem ser positivos.")
            return False
        if not self.modo_espectral():
            tempo = tuple(self.segundos_do_campo(campo)
                          for campo in (self.campo_tempo_inicio, self.campo_tempo_fim))
            if tempo[0] >= tempo[1]:
                QMessageBox.warning(self, "Limites inválidos", "O tempo inicial deve ser menor que o final.")
                return False
        else:
            tempo = None
        self.definir_limites(tempo, escala)
        return True

    def definir_limites(self, tempo, escala):
        if not self.modo_espectral():
            self._intervalo_temporal = tuple(tempo)
        self._escalas_modos[self.modo_escala()] = tuple(escala)
        self.atualizar_limites_visualizacao()

    def ajustar_aos_dados(self):
        if self.df_sensores is None:
            return
        self._escalas_modos.pop(self.modo_escala(), None)
        if not self.modo_espectral():
            self._intervalo_temporal = None
        self.atualizar_limites_visualizacao()

    def aplicar_intervalo_temporal(self, intervalo):
        if self.modo_espectral():
            return
        inicio, fim = map(float, intervalo)
        if not (self.tempo[0] <= inicio < fim <= self.tempo[-1]):
            raise ValueError("O intervalo deve estar dentro dos dados carregados.")
        self._intervalo_temporal = (inicio, fim)
        self.atualizar_limites_visualizacao()

    def intervalo_exportacao(self):
        return None if self.modo_espectral() else self._intervalo_temporal
