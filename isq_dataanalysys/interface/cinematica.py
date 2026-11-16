"""Resultados do fluxo Sum[Xdt], com ajustes após cada integração."""

from copy import deepcopy
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)
from isq_dataanalysys import __version__
from isq_dataanalysys.exportacao.csv_tratado import DadosTratados
from isq_dataanalysys.processamento.cinematica import (
    integrar_segmento,
    retirar_ajuste,
    estatisticas,
)
from isq_dataanalysys.processamento.sinais import Processamento
from .dados_tratados import (
    TelaDadosTratados,
    mostrar_resultado,
    abrir_grafico_unificado,
    CORES_EIXOS,
)
from .controles import ControlePassaBanda


class TelaCinematica(TelaDadosTratados):
    def __init__(self, tempo, integral, canais, grandeza, caminho=None,
                 inicio_arquivo=None, metadados=None, intervalo_visualizacao=None):
        if grandeza not in ('velocidade', 'deslocamento'):
            raise ValueError('Grandeza de resultado desconhecida.')
        grau = 1 if grandeza == 'velocidade' else 2
        corrigido, ajustes = retirar_ajuste(tempo, integral, grau)
        super().__init__()
        self.janelas_resultados = []
        self.grau_ajuste = grau
        self.df_integrado = integral.copy(deep=True)
        self.df_corrigido = corrigido.copy(deep=True)
        self.ajustes = ajustes
        self.cortes_posicao = None
        self.nome_resultado = 'Velocidade' if grau == 1 else 'Posição / deslocamento'
        self.unidade = 'mm/s' if grau == 1 else 'mm'
        metadata = deepcopy(metadados or {})
        etapas = metadata.setdefault('etapas_integracao', [])
        etapas.append({
            'saida': grandeza, 'unidade': self.unidade,
            'integracao': 'Sum[Xdt]: y[i] = y[i-1] + x[i]*dt; acumulador reiniciado por segmento',
            'primeira_amostra': 'x[0]*dt', 'grau_ajuste_apos_integrar': grau,
            'intervalo_ajuste_s': [float(tempo[0]), float(tempo[-1])],
            'base_coeficientes': 'c0+c1*tau+c2*tau^2; tau=t-t[0], em segundos',
            'coeficientes': {str(c): ajustes.loc[c].to_dict() for c in ajustes.index},
        })
        metadata.update(modalidade=grandeza, titulo=self.nome_resultado,
                        passa_banda_posicao_hz=None)
        infos = {}
        for canal, info in canais.items():
            if isinstance(info, tuple):
                eixo, nome = info
                nome = nome.removeprefix(f'Canal {canal} — ')
            else:
                eixo, nome = info['eixo'], info['nome']
            infos[canal] = dict(info) if isinstance(info, dict) else {}
            infos[canal].update(nome=nome, eixo=eixo, unidade=self.unidade)
        self.carregar_dados(DadosTratados(np.asarray(tempo), corrigido, infos,
                                        inicio_arquivo, metadata), caminho)
        self.botao_abrir.hide()
        self.rotulo_origem.hide()
        self.botao_unificado = QPushButton('Gráfico unificado')
        self.botao_unificado.clicked.connect(lambda: abrir_grafico_unificado(self))
        self.layout_acoes.insertWidget(1, self.botao_unificado)
        self.setWindowTitle(f'{self.nome_resultado} — ajuste grau {grau} — v{__version__}')
        self.botao_estatisticas = QPushButton('Visualizar estatísticas')
        self.botao_estatisticas.clicked.connect(self.mostrar_estatisticas)
        self.layout_acoes.insertWidget(2, self.botao_estatisticas)
        self.botao_detalhes = QPushButton('Detalhes do cálculo')
        self.botao_detalhes.clicked.connect(self.mostrar_detalhes)
        self.layout_acoes.insertWidget(3, self.botao_detalhes)
        if grau == 1:
            self.botao_deslocamento = QPushButton('Obter posição')
            self.botao_deslocamento.clicked.connect(self.gerar_deslocamento)
            self.layout_acoes.insertWidget(2, self.botao_deslocamento)
        else:
            self.controle_passa_banda = ControlePassaBanda()
            self.controle_passa_banda.configurar_amostragem(
                Processamento.taxa_amostragem(self.tempo))
            self.controle_passa_banda.setToolTip(
                'Filtro opcional aplicado à posição após o ajuste quadrático. '
                'Reaplicar parte sempre da posição corrigida, sem acumular filtragens.')
            self.painel_intervalo.parentWidget().layout().insertWidget(2, self.controle_passa_banda)
            self.controle_passa_banda.botao_aplicar.clicked.connect(self.aplicar_passa_banda)
            self.controle_passa_banda.botao_desativar.clicked.connect(
                lambda: self.aplicar_passa_banda(desativar=True))
        if intervalo_visualizacao is not None:
            self.painel_intervalo.definir_intervalo_segundos(*intervalo_visualizacao)
        self._atualizar_descricao()

    def grupo_do_canal(self, canal, info, rotulo):
        return info.get('sensor_id', canal), f"{info.get('sensor', info['nome'])} — {rotulo}"

    def caneta_do_canal(self, canal, info, numero):
        return pg.mkPen(CORES_EIXOS.get(info['eixo'], '#666666'), width=1)

    def _atualizar_descricao(self):
        ajuste = 'reta' if self.grau_ajuste == 1 else 'polinômio de grau 2'
        origem = 'aceleração em mm/s²' if self.grau_ajuste == 1 else 'velocidade corrigida em mm/s'
        descricao = (f'{self.nome_resultado} ({self.unidade}): integrar {origem} por Sum[Xdt] '
                     f'→ subtrair {ajuste} de mínimos quadrados.\n'
                     f'Cálculo no registro completo: {self.tempo[0]:g} a {self.tempo[-1]:g} s; '
                     'o intervalo em minutos seleciona a visualização, exportação e estatísticas.')
        if self.cortes_posicao is not None:
            descricao += f'\nPassa-banda da posição: {self.cortes_posicao[0]:g}–{self.cortes_posicao[1]:g} Hz.'
        filtros = self.metadados_tratados.get('filtros_aceleracao', {})
        if 'passa_banda' in filtros:
            low, high = filtros['passa_banda']
            descricao += f'\nOrigem em g ×9810; passa-banda da aceleração: {low:g}–{high:g} Hz.'
        self.descricao_exportacao = descricao
        self.metadados_tratados['descricao'] = descricao
        self.metadados_tratados['passa_banda_posicao_hz'] = self.cortes_posicao
        self.rotulo_origem.setText(descricao)
        self.rotulo_origem.setToolTip(descricao)

    def aplicar_passa_banda(self, desativar=False):
        if self.grau_ajuste != 2:
            return False
        cortes = None if desativar else self.controle_passa_banda.cortes()
        try:
            resultado, _ = Processamento.aplicar(
                self.tempo, self.df_corrigido,
                {} if cortes is None else {'passa_banda': cortes},
            )
        except ValueError as erro:
            QMessageBox.warning(self, 'Passa-banda inválido', str(erro))
            return False
        self.df_sensores = resultado
        self.cortes_posicao = cortes
        self.controle_passa_banda.mostrar_cortes(cortes)
        for canal, curva in self.curvas.items():
            curva.setData(self.tempo, resultado[canal].to_numpy())
        for grafico in self.graficos_eixos.values():
            grafico.enableAutoRange(axis='y')
        self._atualizar_descricao()
        return True

    def gerar_deslocamento(self):
        canais = {c: self.canais[c] for c, campo in self.checkboxes_canais.items() if campo.isChecked()}
        if not canais:
            QMessageBox.information(self, 'Posição', 'Selecione pelo menos um canal.')
            return
        try:
            integral = integrar_segmento(self.tempo, self.df_sensores[list(canais)])
            janela = TelaCinematica(
                self.tempo, integral, canais, 'deslocamento', self.caminho_atual,
                self.inicio_exportacao, self.metadados_tratados,
                self.painel_intervalo.intervalo_exportacao(),
            )
        except ValueError as erro:
            QMessageBox.warning(self, 'Falha ao integrar', str(erro))
            return
        return mostrar_resultado(self, janela)

    def dados_estatisticas(self):
        canais = [c for c, campo in self.checkboxes_canais.items() if campo.isChecked()]
        intervalo = self.painel_intervalo.intervalo_exportacao() or self.painel_intervalo.limites_segundos
        inicio, fim = intervalo
        tolerancia = max(abs(inicio), abs(fim), 1) * np.finfo(float).eps * 16
        mascara = (self.tempo >= inicio - tolerancia) & (self.tempo <= fim + tolerancia)
        dados = self.df_sensores.loc[mascara, canais]
        return estatisticas(dados), intervalo, len(dados)

    def _tabela(self, titulo, descricao, dados):
        janela = QDialog(self)
        janela.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        janela.setWindowTitle(titulo)
        janela.resize(820, 420)
        layout = QVBoxLayout(janela)
        texto = QLabel(descricao)
        texto.setWordWrap(True)
        layout.addWidget(texto)
        tabela = QTableWidget(len(dados), len(dados.columns) + 1)
        tabela.setHorizontalHeaderLabels(['Canal'] + list(dados.columns))
        tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tabela.verticalHeader().hide()
        for linha, (canal, valores) in enumerate(dados.iterrows()):
            nome = f"{canal} — {self.canais[canal]['nome']}"
            tabela.setItem(linha, 0, QTableWidgetItem(nome))
            for coluna, valor in enumerate(valores, 1):
                item = QTableWidgetItem(f'{valor:.9g}')
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                tabela.setItem(linha, coluna, item)
        tabela.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        tabela.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(tabela)
        fechar = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        fechar.rejected.connect(janela.close)
        layout.addWidget(fechar)
        janela.show()
        return janela

    def mostrar_estatisticas(self):
        try:
            dados, intervalo, quantidade = self.dados_estatisticas()
        except ValueError as erro:
            QMessageBox.information(self, 'Estatísticas', str(erro))
            return
        dados = dados.rename(columns={c: f'{c} ({self.unidade})' for c in dados.columns})
        return self._tabela(
            f'Estatísticas — {self.nome_resultado}',
            f'{intervalo[0]/60:g} a {intervalo[1]/60:g} min · {quantidade} amostras por canal. '
            'RMS = √média(valor²), sem retirar média. Máximo e mínimo com sinal. '
            'Valores da seleção atual, incluindo o filtro da posição quando ativo.', dados,
        )

    def mostrar_detalhes(self):
        return self._tabela(
            'Ajuste subtraído após a integração',
            self.descricao_exportacao + '\n\n'
            f'Soma acumulada x[i]·dt, por arquivo, com primeira amostra x[0]·dt. '
            f'Ajuste grau {self.grau_ajuste}: c0 + c1·τ' + (' + c2·τ²' if self.grau_ajuste == 2 else '') +
            f', τ = t − {self.tempo[0]:g} s. Coeficientes em {self.unidade}, '
            f'{self.unidade}/s' + (f', {self.unidade}/s².' if self.grau_ajuste == 2 else '.') +
            '\nInclui intercepto; o resultado corrigido não é forçado a começar em zero. '
            'Os ajustes alteram componentes lentas do movimento. A derivada segunda da posição '
            'corrigida não é, em geral, a aceleração original; o filtro adicional também a altera.',
            self.ajustes,
        )
