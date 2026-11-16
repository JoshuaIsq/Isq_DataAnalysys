"""Intervalo visual em minutos de gravação, sem modificar sinais ou integrais."""

import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QDoubleSpinBox, QPushButton, QMessageBox


class VinculoIntervalos:
    """Sincroniza valores X sem o ajuste geométrico por pixels do setXLink."""
    def __init__(self, plots=None):
        self.plots = []
        self._sincronizando = False
        for plot in plots or []:
            self.adicionar_plot(plot)

    def adicionar_plot(self, plot):
        if plot in self.plots:
            return
        plot.setXLink(None)
        self.plots.append(plot)
        plot.getViewBox().sigXRangeChanged.connect(self._alterado)

    def limpar(self):
        for plot in self.plots:
            try:
                plot.getViewBox().sigXRangeChanged.disconnect(self._alterado)
            except (RuntimeError,TypeError):
                # O Qt pode já ter destruído o gráfico ao fechar uma janela.
                pass
        self.plots.clear()

    def _alterado(self, origem, intervalo):
        self.definir_intervalo(intervalo, origem=origem)

    def definir_intervalo(self, intervalo, origem=None):
        if self._sincronizando:
            return
        self._sincronizando = True
        try:
            for plot in self.plots:
                if plot.getViewBox() is not origem:
                    plot.setXRange(*intervalo,padding=0)
        finally:
            self._sincronizando = False


class PainelIntervaloTemporal(QWidget):
    intervalo_alterado = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('painel_intervalo_temporal')
        self._limites = None
        self._intervalo = None
        self.inicio_gravacao_s = 0.0
        linha = QHBoxLayout(self)
        linha.setContentsMargins(0, 0, 0, 0)
        linha.setSpacing(8)
        self.inicio_min = self._campo('inicio_avaliacao_min')
        self.fim_min = self._campo('fim_avaliacao_min')
        linha.addWidget(QLabel('Avaliar de:'))
        linha.addWidget(self.inicio_min)
        linha.addWidget(QLabel('até:'))
        linha.addWidget(self.fim_min)
        self.botao_aplicar = QPushButton('Aplicar intervalo')
        self.botao_aplicar.setObjectName('aplicar_intervalo_temporal')
        self.botao_completo = QPushButton('Intervalo completo')
        self.botao_completo.setObjectName('intervalo_temporal_completo')
        linha.addWidget(self.botao_aplicar)
        linha.addWidget(self.botao_completo)
        self.rotulo_limites = QLabel('Abra dados para selecionar o intervalo.')
        self.rotulo_limites.setWordWrap(True)
        linha.addWidget(self.rotulo_limites, 1)
        self.setToolTip('Minutos desde o início da gravação. Altera somente a visualização e a exportação; não recalcula integrações.')
        self.botao_aplicar.clicked.connect(self.aplicar)
        self.botao_completo.clicked.connect(self.mostrar_completo)
        self.setEnabled(False)

    @staticmethod
    def _campo(nome):
        campo = QDoubleSpinBox()
        campo.setObjectName(nome)
        campo.setDecimals(9)
        campo.setRange(0, 0)
        campo.setSuffix(' min')
        campo.setSingleStep(1)
        campo.setMinimumWidth(100)
        campo.setMaximumWidth(155)
        return campo

    @property
    def limites_segundos(self):
        return self._limites

    def definir_dados(self, tempo, inicio_gravacao_s=0.0):
        valores = np.asarray(tempo, dtype=float)
        if (valores.ndim != 1 or not len(valores) or not np.isfinite(valores).all()
                or np.any(np.diff(valores) <= 0) or not np.isfinite(inicio_gravacao_s)):
            raise ValueError('O intervalo precisa de tempos finitos e crescentes.')
        self._limites = (float(valores[0]), float(valores[-1]))
        self._intervalo = None
        self.inicio_gravacao_s = float(inicio_gravacao_s)
        inferior, superior = self._minutos(self._limites)
        for campo in (self.inicio_min, self.fim_min):
            campo.setRange(inferior, superior)
        self.inicio_min.setValue(inferior)
        self.fim_min.setValue(superior)
        self.rotulo_limites.setText(f'Disponível: {inferior:g} a {superior:g} min')
        self.setEnabled(superior > inferior)

    def _minutos(self, intervalo):
        return tuple((valor-self.inicio_gravacao_s)/60 for valor in intervalo)

    def intervalo_exportacao(self):
        return self._intervalo

    def definir_intervalo_segundos(self, inicio, fim, emitir=True):
        if self._limites is None:
            raise ValueError('Abra dados antes de selecionar um intervalo.')
        inicio, fim = float(inicio), float(fim)
        if (not np.isfinite([inicio,fim]).all() or inicio >= fim
                or inicio < self._limites[0] or fim > self._limites[1]):
            raise ValueError('Escolha um início menor que o fim, dentro dos limites dos dados.')
        self._intervalo = (inicio,fim)
        self.inicio_min.setValue(self._minutos(self._intervalo)[0])
        self.fim_min.setValue(self._minutos(self._intervalo)[1])
        if emitir:
            self.intervalo_alterado.emit(self._intervalo)
        return True

    def aplicar(self):
        if self._limites is None:
            return False
        def segundos(campo):
            # Os minutos são arredondados no campo; preserva os extremos
            # originais para não perder a primeira/última amostra na exportação.
            if campo.value() == campo.minimum():
                return self._limites[0]
            if campo.value() == campo.maximum():
                return self._limites[1]
            return self.inicio_gravacao_s + campo.value()*60
        inicio = segundos(self.inicio_min)
        fim = segundos(self.fim_min)
        try:
            return self.definir_intervalo_segundos(inicio,fim)
        except ValueError as erro:
            QMessageBox.warning(self,'Intervalo inválido',str(erro))
            return False

    def mostrar_completo(self):
        if self._limites is None:
            return
        self._intervalo = None
        inferior, superior = self._minutos(self._limites)
        self.inicio_min.setValue(inferior)
        self.fim_min.setValue(superior)
        self.intervalo_alterado.emit(self._limites)

