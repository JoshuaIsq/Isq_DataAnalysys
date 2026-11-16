"""Janelas de dados tratados e gráficos unificados, sem recalcular os sinais."""

from copy import deepcopy
import weakref
import numpy as np
import pyqtgraph as pg
import pandas as pd
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from isq_dataanalysys import __version__
from isq_dataanalysys.exportacao.csv_tratado import DadosTratados, ler_csv_tratado
from .eixo_temporal import EixoDataHora, configurar_eixo_temporal
from .exportacao import ExportacaoGraficos
from .intervalo_temporal import PainelIntervaloTemporal, VinculoIntervalos


# Referências de janelas sem pai Qt: permanecem abertas ao fechar a origem.
_JANELAS_ABERTAS = set()


def mostrar_resultado(origem, janela):
    if not hasattr(origem, 'janelas_resultados'):
        origem.janelas_resultados = []
    origem.janelas_resultados.append(janela)
    _JANELAS_ABERTAS.add(janela)
    referencia_origem = weakref.ref(origem)
    janela.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

    def liberar(*_):
        _JANELAS_ABERTAS.discard(janela)
        proprietario = referencia_origem()
        lista = getattr(proprietario, 'janelas_resultados', [])
        if janela in lista:
            lista.remove(janela)

    janela.destroyed.connect(liberar)
    janela.show()
    janela.raise_()
    janela.activateWindow()
    return janela


class TelaDadosTratados(ExportacaoGraficos, QMainWindow):
    """Abre o formato CSV tratado e preserva seus números, unidades e relógio."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'Dados tratados — v{__version__}')
        self.resize(1200, 750)
        self.df_sensores = None
        self.tempo = np.array([], dtype=float)
        self.canais = {}
        self.metadados_tratados = {}
        self.inicio_exportacao = None
        self.inicio_gravacao_s = 0.0
        self.descricao_exportacao = ''
        self.grandeza = 'dados_tratados'
        self.caminho_atual = None
        self.curvas = {}
        self.checkboxes_canais = {}
        self.graficos_eixos = {}
        self.vinculo_intervalos = VinculoIntervalos()

        central = QWidget()
        self.setCentralWidget(central)
        principal = QHBoxLayout(central)
        self.rolagem_canais = QScrollArea()
        self.rolagem_canais.setWidgetResizable(True)
        self.rolagem_canais.setFixedWidth(250)
        principal.addWidget(self.rolagem_canais)

        direito = QVBoxLayout()
        principal.addLayout(direito, 1)
        painel = QFrame()
        controles = QVBoxLayout(painel)
        linha = QHBoxLayout()
        self.layout_acoes = linha
        self.botao_abrir = QPushButton('Abrir CSV tratado')
        self.botao_abrir.clicked.connect(self.abrir_arquivo)
        linha.addWidget(self.botao_abrir)
        self.botao_exportar = QPushButton('Exportar')
        menu = QMenu(self.botao_exportar)
        menu.addAction('SVG vetorial').triggered.connect(self.exportar_svg)
        menu.addAction('HTML interativo').triggered.connect(self.exportar_html)
        menu.addAction('CSV tratado').triggered.connect(self.exportar_csv)
        self.botao_exportar.setMenu(menu)
        self.botao_exportar.setEnabled(False)
        linha.addWidget(self.botao_exportar)
        linha.addStretch()
        controles.addLayout(linha)
        self.rotulo_origem = QLabel('Abra um CSV tratado exportado pelo programa.')
        self.rotulo_origem.setTextFormat(Qt.TextFormat.PlainText)
        self.rotulo_origem.setWordWrap(True)
        controles.addWidget(self.rotulo_origem)
        self.painel_intervalo = PainelIntervaloTemporal()
        self.painel_intervalo.intervalo_alterado.connect(self.aplicar_intervalo)
        controles.addWidget(self.painel_intervalo)
        direito.addWidget(painel)
        self.grafico = pg.GraphicsLayoutWidget()
        self.grafico.setBackground('w')
        direito.addWidget(self.grafico, 1)
        self.statusBar().addPermanentWidget(QLabel(f'v{__version__}'))
        self._montar_canais()

    def abrir_arquivo(self):
        caminho, _ = QFileDialog.getOpenFileName(
            self, 'Abrir CSV tratado', '', 'CSV tratado (*.csv);;Todos os arquivos (*)',
        )
        if caminho:
            return self.importar_caminho(caminho)
        return False

    def importar_caminho(self, caminho):
        try:
            arquivo = ler_csv_tratado(caminho)
            return self.carregar_dados(arquivo, caminho=caminho)
        except (OSError, ValueError, TypeError) as erro:
            QMessageBox.warning(self, 'Falha ao abrir CSV tratado', str(erro))
            return False

    def carregar_dados(self, arquivo, caminho=None):
        """Exibe um resultado em memória com o mesmo fluxo de um CSV tratado.

        Valida antes de substituir a janela e recebe cópias independentes. Não
        cria arquivos temporários nem reaplica os tratamentos registrados.
        """
        if not isinstance(arquivo, DadosTratados):
            raise ValueError('Informe um resultado de dados tratados válido.')
        tempo = np.asarray(arquivo.tempo, dtype=float)
        if (tempo.ndim != 1 or not len(tempo) or not np.isfinite(tempo).all()
                or np.any(np.diff(tempo) <= 0)):
            raise ValueError('O tempo precisa conter amostras finitas e crescentes.')
        if (not hasattr(arquivo.dados, 'columns') or len(arquivo.dados) != len(tempo)
                or not isinstance(arquivo.canais, dict) or not arquivo.canais
                or list(arquivo.dados.columns) != list(arquivo.canais)
                or not np.isfinite(arquivo.dados.to_numpy(dtype=float)).all()):
            raise ValueError('As medições e os canais precisam corresponder ao tempo informado.')
        for info in arquivo.canais.values():
            if not isinstance(info, dict) or any(
                not isinstance(info.get(campo), str) for campo in ('nome','unidade','eixo')
            ):
                raise ValueError('Cada canal precisa informar nome, unidade e eixo.')
        if not isinstance(arquivo.metadados, dict):
            raise ValueError('Os metadados precisam ser um dicionário.')
        inicio_gravacao_s = float(arquivo.metadados.get('inicio_gravacao_s', 0.0))
        if not np.isfinite(inicio_gravacao_s):
            raise ValueError('A referência do início da gravação precisa ser finita.')
        self.tempo = np.array(tempo, dtype=float, copy=True)
        self.df_sensores = arquivo.dados.copy(deep=True)
        self.canais = deepcopy(arquivo.canais)
        self.metadados_tratados = deepcopy(arquivo.metadados)
        self.inicio_exportacao = arquivo.inicio_csv
        self.inicio_gravacao_s = inicio_gravacao_s
        self.descricao_exportacao = str(self.metadados_tratados.get('descricao', ''))
        self.grandeza = self.metadados_tratados.get('modalidade', 'dados_tratados')
        self.caminho_atual = Path(caminho) if caminho is not None else None
        self._montar_canais()
        self._montar_graficos()
        self.painel_intervalo.definir_dados(self.tempo, inicio_gravacao_s=self.inicio_gravacao_s)
        self.aplicar_intervalo(self.painel_intervalo.limites_segundos)
        self.botao_exportar.setEnabled(True)
        descricao = self.descricao_exportacao or 'Valores e unidades preservados do CSV tratado.'
        nome = self.caminho_atual.name if self.caminho_atual is not None else str(
            self.metadados_tratados.get('titulo', 'Resultado em memória')
        )
        self.rotulo_origem.setText(f'{nome}\n{descricao}')
        self.rotulo_origem.setToolTip(self.descricao_exportacao)
        self.setWindowTitle(f'Dados tratados — {nome} — v{__version__}')
        self.statusBar().showMessage(
            f'{len(self.tempo)} amostras | {len(self.canais)} canais | '
            f'{self.tempo[0]:g} a {self.tempo[-1]:g} s de gravação'
        )
        return True

    def _montar_canais(self):
        painel = QWidget()
        controles = QVBoxLayout(painel)
        controles.addWidget(QLabel('<b>Canais dos dados tratados</b>'))
        self.checkboxes_canais = {}
        for canal, info in self.canais.items():
            texto = f"Canal {canal} — {info['nome']} ({info['unidade']})"
            campo = QCheckBox(texto)
            campo.setToolTip(texto)
            campo.setChecked(True)
            campo.toggled.connect(self.atualizar_visibilidade)
            controles.addWidget(campo)
            self.checkboxes_canais[canal] = campo
        controles.addStretch()
        anterior = self.rolagem_canais.takeWidget()
        self.rolagem_canais.setWidget(painel)
        if anterior is not None:
            anterior.deleteLater()

    def _montar_graficos(self):
        self.vinculo_intervalos.limpar()
        self.grafico.clear()
        self.graficos_eixos = {}
        self.curvas = {}
        grupos = {}
        nomes = {'g': 'Aceleração', 'mg': 'Aceleração RMS', 'mm/s²': 'Aceleração', 'mm/s': 'Velocidade',
                 'mm': 'Deslocamento', 'MPa': 'Tensão', 'μm/m': 'Deformação',
                 'µm/m': 'Deformação', 'mm/m': 'Deformação'}
        for numero, (canal, info) in enumerate(self.canais.items()):
            unidade, eixo = info['unidade'], info.get('eixo', '') or ''
            rotulo = nomes.get(unidade, 'Valor')
            grupo, titulo = self.grupo_do_canal(canal, info, rotulo)
            if grupo not in grupos:
                plot = self.grafico.addPlot(
                    row=len(grupos), col=0,
                    axisItems={'bottom': EixoDataHora(orientation='bottom')},
                )
                plot.setTitle(titulo, color='#333333', size='10pt')
                plot.setLabel('left', rotulo, units=unidade)
                configurar_eixo_temporal(plot, self.inicio_exportacao)
                for lado in ('left', 'bottom'):
                    plot.getAxis(lado).enableAutoSIPrefix(False)
                    plot.getAxis(lado).setPen('#555555')
                    plot.getAxis(lado).setTextPen('#333333')
                # Alinha a área temporal dos grupos mesmo com unidades distintas.
                # ViewBoxes ligados de larguras diferentes ajustariam seus limites.
                plot.getAxis('left').setWidth(80)
                plot.showGrid(x=True, y=True, alpha=.25)
                plot.addLegend(colCount=3, offset=(10, 5), labelTextColor='#333333')
                self.vinculo_intervalos.adicionar_plot(plot)
                grupos[grupo] = plot
                self.graficos_eixos[grupo] = plot
            curva = grupos[grupo].plot(
                self.tempo, self.df_sensores[canal].to_numpy(),
                pen=self.caneta_do_canal(canal, info, numero),
                name=f"Canal {canal} — {info['nome']}",
                symbol='o' if len(self.tempo) == 1 else None,
            )
            curva.setProperty('canal_id', canal)
            self.curvas[canal] = curva

    def grupo_do_canal(self, canal, info, rotulo):
        eixo = info.get('eixo', '')
        return (info['unidade'], eixo), f'{rotulo} — Eixo {eixo}' if eixo else rotulo

    def caneta_do_canal(self, canal, info, numero):
        return pg.mkPen(pg.intColor(numero, hues=max(len(self.canais), 3)), width=1)

    def atualizar_visibilidade(self):
        for canal, curva in self.curvas.items():
            curva.setVisible(self.checkboxes_canais[canal].isChecked())

    def aplicar_intervalo(self, intervalo):
        if intervalo is None:
            return
        inicio, fim = intervalo
        if inicio == fim:
            inicio, fim = inicio-.5, fim+.5
        self.vinculo_intervalos.definir_intervalo((inicio,fim))

    def intervalo_exportacao(self):
        return self.painel_intervalo.intervalo_exportacao()


CORES_EIXOS = {"X": "#ff0000", "Y": "#00ff00", "Z": "#0000ff"}


class TelaGraficoUnificado(TelaDadosTratados):
    def __init__(self, arquivo, cores, titulo, unidade_x, rotulo_y, faixa_x, log=False):
        self.cores = cores.copy()
        self.titulo_unificado = titulo
        super().__init__()
        self.carregar_dados(arquivo)
        self.botao_abrir.hide()
        self.rotulo_origem.hide()
        self.setWindowTitle(f'Gráfico unificado — {titulo} — v{__version__}')
        self.setToolTip('Cópia da visualização no momento da abertura. A seleção é independente da origem.')
        plot = self.graficos_eixos[0]
        plot.setLabel('left', rotulo_y, units=next(iter(self.canais.values()))['unidade'])
        plot.setLogMode(x=False, y=log)
        if log:
            for canal, curva in self.curvas.items():
                valores = self.df_sensores[canal].to_numpy()
                curva.setData(self.tempo, np.where(valores > 0, valores, np.nan))
                curva.dados_csv = valores.copy()
        if unidade_x == 'Hz':
            self.painel_intervalo.hide()
            plot.setLabel('bottom', 'Frequência', units='Hz')
        elif self.tempo[0] < self.tempo[-1]:
            inicio = max(float(self.tempo[0]), float(faixa_x[0]))
            fim = min(float(self.tempo[-1]), float(faixa_x[1]))
            if inicio < fim:
                self.painel_intervalo.definir_intervalo_segundos(inicio, fim)
        plot.setXRange(*faixa_x, padding=0)
        for texto, marcado in (('Selecionar todos', True), ('Ocultar todos', False)):
            botao = QPushButton(texto)
            botao.clicked.connect(lambda _=False, valor=marcado: self.selecionar_todos(valor))
            self.layout_acoes.insertWidget(self.layout_acoes.count()-1, botao)

    def grupo_do_canal(self, canal, info, rotulo):
        return 0, self.titulo_unificado

    def caneta_do_canal(self, canal, info, numero):
        return pg.mkPen(self.cores[canal], width=1)

    def selecionar_todos(self, marcado):
        for campo in self.checkboxes_canais.values():
            campo.setChecked(marcado)

def abrir_grafico_unificado(origem):
    if getattr(origem, 'df_sensores', None) is None:
        return
    plots = origem.plots_para_exportar()
    base, colunas, canais, cores = None, {}, {}, {}
    unidade = None
    for plot in plots:
        for curva in plot.listDataItems():
            if not curva.isVisible():
                continue
            unidade_curva = plot.getAxis('left').labelUnits
            if unidade is None:
                unidade = unidade_curva
            elif unidade != unidade_curva:
                QMessageBox.warning(origem, 'Gráfico unificado', 'Selecione canais com a mesma unidade de medida.')
                return
            x, y = curva.getOriginalDataset()
            if x is None or y is None or not len(x):
                continue
            x = np.asarray(x, dtype=float)
            if base is None:
                base = x.copy()
            elif not np.array_equal(base, x):
                QMessageBox.warning(origem, 'Gráfico unificado', 'Os canais têm bases diferentes.')
                return
            canal = origem._identidade_curva_csv(curva, len(colunas)+1)
            if canal in colunas:
                QMessageBox.warning(origem, 'Gráfico unificado', 'Há identidades de canais repetidas.')
                return
            colunas[canal] = np.array(getattr(curva, 'dados_csv', y), dtype=float, copy=True)
            info = getattr(origem, 'canais', {}).get(canal)
            if isinstance(info, dict):
                canais[canal] = deepcopy(info)
            else:
                canais[canal] = dict(nome=origem.info_arquivo['nomes'][canal],
                                     eixo=origem.info_arquivo['eixos'].get(canal, ''))
            canais[canal]['unidade'] = plot.getAxis('left').labelUnits
            cores[canal] = pg.mkPen(curva.opts['pen']).color().name()
    if base is None:
        QMessageBox.information(origem, 'Gráfico unificado', 'Selecione pelo menos um canal com dados.')
        return
    plot = plots[0]
    espectral = plot.getAxis('bottom').labelUnits == 'Hz'
    metadata = deepcopy(getattr(origem, 'metadados_tratados', {}))
    metadata['descricao'] = getattr(origem, 'descricao_exportacao', '')
    metadata['visualizacao'] = 'gráfico unificado; cópia independente'
    titulo = plot.getAxis('left').labelText
    janela = TelaGraficoUnificado(
        DadosTratados(base, pd.DataFrame(colunas), canais,
                      None if espectral else origem.inicio_para_exportar(), metadata),
        cores, titulo, plot.getAxis('bottom').labelUnits, titulo,
        plot.viewRange()[0], log=plot.getAxis('left').logMode,
    )
    janela.caminho_atual = getattr(origem, 'caminho_atual', None)
    return mostrar_resultado(origem, janela)
