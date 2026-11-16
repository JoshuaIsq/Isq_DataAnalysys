"""Janelas independentes para os resultados temporais da acelerometria."""

from copy import deepcopy
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QCheckBox,
    QPushButton,
    QLabel,
    QMenu,
    QMessageBox,
    QScrollArea,
    QFrame,
)
from .exportacao import ExportacaoGraficos
from .eixo_temporal import EixoDataHora, configurar_eixo_temporal
from .intervalo_temporal import PainelIntervaloTemporal, VinculoIntervalos
from isq_dataanalysys.processamento.integracao import integrar_relativo, corrigir_rampa_deslocamento
from isq_dataanalysys.leitores.acelerometria import EIXOS, EIXO_DESCONHECIDO
from isq_dataanalysys import __version__ as VERSAO
from .dados_tratados import mostrar_resultado


class TelaIntegracao(ExportacaoGraficos, QMainWindow):
    def __init__(self, tempo, dados, canais, grandeza, caminho=None, inicio_arquivo=None,
                 tratamentos=None, medias_aceleracao=None, intervalo_visualizacao=None,
                 aceleracao_referencia=None, velocidade_referencia=None, corrigir_rampa=True):
        super().__init__()
        if grandeza not in ('velocidade', 'deslocamento'):
            raise ValueError('Grandeza de resultado desconhecida.')
        self.tempo = np.array(tempo, dtype=float, copy=True)
        self.df_sensores = dados.copy(deep=True)
        self.canais = deepcopy(canais)
        self.grandeza = grandeza
        self.caminho_atual = caminho
        # Preserva a referência temporal sem reler o CSV ao exportar.
        self.inicio_exportacao = inicio_arquivo
        self.tratamentos_origem = tratamentos
        self.medias_aceleracao = deepcopy(medias_aceleracao)
        self.aceleracao_referencia = (None if aceleracao_referencia is None else aceleracao_referencia.copy(deep=True))
        self.velocidade_referencia = (None if velocidade_referencia is None else velocidade_referencia.copy(deep=True))
        self.df_deslocamento_integrado = dados.copy(deep=True) if grandeza == 'deslocamento' else None
        self.ajustes_rampa = None
        self.correcao_rampa_ativa = grandeza == 'deslocamento' and bool(corrigir_rampa)
        if self.correcao_rampa_ativa:
            self.df_sensores, self.ajustes_rampa = corrigir_rampa_deslocamento(self.tempo,self.df_deslocamento_integrado)
        self.janelas_resultados = []
        velocidade = grandeza == 'velocidade'
        nome, unidade, condicao = ('Velocidade', 'mm/s', 'v₀') if velocidade else ('Deslocamento', 'mm', 'd₀')
        referencia = 'relativa ao início do intervalo' if velocidade else 'relativo ao início do intervalo'
        metodo = (
            'Aceleração tratada em g → m/s² (×9,80665) → integrar por trapézios em m/s → mm/s (×1000).'
            if velocidade else
            'Velocidade exibida em mm/s → integrar por trapézios para mm.'
        )
        if velocidade and self.medias_aceleracao is not None:
            metodo = (
                'Aceleração tratada em g → subtrair somente a média aritmética por canal '
                '→ m/s² (×9,80665) → integrar por trapézios em m/s → mm/s (×1000).'
            )
        self.descricao_exportacao = (
            f'{nome} {referencia}; {condicao} = 0 {unidade}; '
            f'intervalo: {self.tempo[0]:g} a {self.tempo[-1]:g} s.\n{metodo}\n'
        )
        self.descricao_exportacao += (
            'Sem ajuste de reta ou parábola.' if velocidade else
            'Velocidade integrada sem retirar sua média nem ajustar reta ou parábola.'
        )
        if self.medias_aceleracao is None:
            self.descricao_exportacao += '\nSem retirada da média da aceleração.'
        else:
            valores = [f'Canal {c}: {v:.17g}' for c, v in self.medias_aceleracao.items()]
            medias_texto = '\n'.join('; '.join(valores[i:i+3]) for i in range(0,len(valores),3))
            self.descricao_exportacao += (
                '\nMédia aritmética retirada somente da aceleração, em todo o intervalo. '
                f'Valores em g — {medias_texto}.'
            )
        if self.tratamentos_origem:
            self.descricao_exportacao += f'\nOrigem — {self.tratamentos_origem}'
        self._descricao_integral = self.descricao_exportacao
        self.metadados_tratados = {}
        self._atualizar_descricao_correcao()
        self.setWindowTitle(f'{nome} — {referencia} — v{VERSAO}')
        self.resize(1100, 700)
        central = QWidget()
        self.setCentralWidget(central)
        principal = QHBoxLayout(central)

        painel_canais = QWidget()
        controles = QVBoxLayout(painel_canais)
        controles.addWidget(QLabel('<b>Canais do resultado</b>'))
        self.checkboxes_canais = {}
        self.curvas = {}
        for canal, (eixo, rotulo) in self.canais.items():
            checkbox = QCheckBox(f'{eixo}: {rotulo}')
            checkbox.setToolTip(checkbox.text())
            checkbox.setChecked(True)
            checkbox.toggled.connect(self.atualizar_visibilidade)
            controles.addWidget(checkbox)
            self.checkboxes_canais[canal] = checkbox
        controles.addStretch()
        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setWidget(painel_canais)
        rolagem.setFixedWidth(240)
        principal.addWidget(rolagem)

        direito = QVBoxLayout()
        principal.addLayout(direito, 1)
        painel = QFrame()
        painel.setFrameShape(QFrame.Shape.StyledPanel)
        cabecalho = QVBoxLayout(painel)
        self.rotulo_referencia = QLabel(self.descricao_exportacao)
        self.rotulo_referencia.setWordWrap(True)
        cabecalho.addWidget(self.rotulo_referencia)
        acoes = QHBoxLayout()
        cabecalho.addLayout(acoes)
        self.exportar = QPushButton('Exportar')
        menu = QMenu(self.exportar)
        menu.addAction('SVG vetorial').triggered.connect(self.exportar_svg)
        menu.addAction('HTML interativo').triggered.connect(self.exportar_html)
        menu.addAction('CSV tratado').triggered.connect(self.exportar_csv)
        self.exportar.setMenu(menu)
        acoes.addWidget(self.exportar)
        if velocidade:
            self.botao_deslocamento = QPushButton('Gerar deslocamento')
            self.botao_deslocamento.setObjectName('gerar_deslocamento')
            self.botao_deslocamento.setMinimumHeight(34)
            self.botao_deslocamento.setToolTip(
                'Integra a velocidade exibida e abre o deslocamento em mm. '
                'Na nova janela, a opção de retirar a reta do deslocamento vem marcada.'
            )
            self.botao_deslocamento.clicked.connect(self.gerar_deslocamento)
            acoes.addWidget(self.botao_deslocamento)
        else:
            self.checkbox_correcao_rampa = QCheckBox('Retirar reta do deslocamento')
            self.checkbox_correcao_rampa.setChecked(self.correcao_rampa_ativa)
            self.checkbox_correcao_rampa.setToolTip(
                'Ajusta uma reta por mínimos quadrados ao deslocamento completo e a subtrai. '
                'Não altera a aceleração ou a velocidade de origem. O início corrigido pode ser diferente de zero.'
            )
            self.checkbox_correcao_rampa.toggled.connect(self.alternar_correcao_rampa)
            acoes.addWidget(self.checkbox_correcao_rampa)
            self.botao_detalhes_ajuste = QPushButton('Detalhes do ajuste')
            self.botao_detalhes_ajuste.clicked.connect(self.mostrar_detalhes_ajuste)
            acoes.addWidget(self.botao_detalhes_ajuste)
            self.botao_verificar = QPushButton('Verificar por derivação')
            self.botao_verificar.setEnabled(len(self.tempo)>=3)
            self.botao_verificar.clicked.connect(self.verificar_por_derivacao)
            acoes.addWidget(self.botao_verificar)
        acoes.addStretch()
        self.painel_intervalo = PainelIntervaloTemporal()
        self.painel_intervalo.definir_dados(self.tempo)
        self.painel_intervalo.intervalo_alterado.connect(self.aplicar_intervalo_temporal)
        cabecalho.addWidget(self.painel_intervalo)
        direito.addWidget(painel)

        self.grafico = pg.GraphicsLayoutWidget()
        self.grafico.setBackground('w')
        direito.addWidget(self.grafico, 1)
        self.graficos_eixos = {}
        self.vinculo_intervalos = VinculoIntervalos()
        presentes = {eixo for eixo, _rotulo in self.canais.values()}
        eixos = [e for e in EIXOS if e in presentes]
        for linha, eixo in enumerate(eixos):
            plot = self.grafico.addPlot(row=linha, col=0,
                                       axisItems={"bottom": EixoDataHora(orientation="bottom")})
            titulo_eixo = eixo if eixo == EIXO_DESCONHECIDO else f'Eixo {eixo}'
            plot.setTitle(f'{titulo_eixo} — {nome} {referencia}', color='#333333', size='10pt')
            configurar_eixo_temporal(plot, self.inicio_exportacao)
            plot.setLabel('left', nome, units=unidade)
            plot.getAxis('left').setWidth(85)
            for lado in ('left', 'bottom'):
                plot.getAxis(lado).enableAutoSIPrefix(False)
                plot.getAxis(lado).setPen('#555555')
                plot.getAxis(lado).setTextPen('#333333')
            plot.showGrid(x=True, y=True, alpha=.25)
            plot.addLegend(colCount=4, offset=(10, 5), labelTextColor='#333333')
            self.graficos_eixos[eixo] = plot
            self.vinculo_intervalos.adicionar_plot(plot)
        cores = ['#1565C0', '#D55E00', '#18864B', '#8E44AD']
        for numero, (canal, (eixo, rotulo)) in enumerate(self.canais.items()):
            self.curvas[canal] = self.graficos_eixos[eixo].plot(
                self.tempo, self.df_sensores[canal].to_numpy(),
                pen=pg.mkPen(cores[(numero // 3) % len(cores)], width=1), name=rotulo,
            )
        if not velocidade:
            self._atualizar_descricao_correcao()
        self.statusBar().showMessage(f'{len(self.tempo)} amostras | {nome} em {unidade}')
        self.statusBar().addPermanentWidget(QLabel(f'v{VERSAO}'))
        if intervalo_visualizacao is not None:
            self.painel_intervalo.definir_intervalo_segundos(*intervalo_visualizacao)
        elif self.tempo[0] < self.tempo[-1]:
            self.aplicar_intervalo_temporal(self.painel_intervalo.limites_segundos)

    def intervalo_exportacao(self):
        return self.painel_intervalo.intervalo_exportacao()

    def aplicar_intervalo_temporal(self, intervalo):
        self.vinculo_intervalos.definir_intervalo(intervalo)

    def atualizar_visibilidade(self):
        for canal, curva in self.curvas.items():
            curva.setVisible(self.checkboxes_canais[canal].isChecked())

    def _atualizar_descricao_correcao(self):
        if self.grandeza != 'deslocamento':
            return
        if self.correcao_rampa_ativa:
            base = self._descricao_integral.replace(
                'Deslocamento relativo ao início do intervalo; d₀ = 0 mm;',
                'Integral anterior ao ajuste: d₀ = 0 mm;')
            self.descricao_exportacao = (
                'Deslocamento com referência linear ajustada.\n' + base + '\nApós integrar: subtrair a reta de mínimos quadrados '
                'do deslocamento completo (intercepto e inclinação). '
                'A integral anterior ao ajuste tem d₀ = 0; o deslocamento corrigido não é imposto a zero. '
                'Essa referência ajustada não comprova a posição física real.'
            )
            ajustes = [{'canal':int(c) if isinstance(c,np.integer) else c,'intercepto_mm':float(self.ajustes_rampa.loc[c,'intercepto_mm']),
                        'inclinacao_mm_s':float(self.ajustes_rampa.loc[c,'inclinacao_mm_s'])}
                       for c in self.df_sensores]
            self.metadados_tratados['correcao_deslocamento'] = dict(
                metodo='reta_minimos_quadrados',tempo_referencia_s=float(self.tempo[0]),
                intervalo_ajuste_s=[float(self.tempo[0]),float(self.tempo[-1])],ajustes=ajustes,
                inicio_corrigido_imposto_zero=False)
            referencia = 'ajuste linear removido'
        else:
            self.descricao_exportacao = self._descricao_integral + '\nIntegral sem ajuste posterior do deslocamento.'
            self.metadados_tratados['correcao_deslocamento'] = dict(metodo='nenhum')
            referencia = 'relativo ao início do intervalo'
        self.setWindowTitle(f'Deslocamento — {referencia} — v{VERSAO}')
        if hasattr(self,'rotulo_referencia'):
            self.rotulo_referencia.setText(self.descricao_exportacao)
        for eixo,plot in getattr(self,'graficos_eixos',{}).items():
            nome = eixo if eixo == EIXO_DESCONHECIDO else f'Eixo {eixo}'
            plot.setTitle(f'{nome} — Deslocamento — {referencia}',color='#333333',size='10pt')

    def alternar_correcao_rampa(self, ativar):
        try:
            if ativar:
                dados, ajustes = corrigir_rampa_deslocamento(self.tempo,self.df_deslocamento_integrado)
            else:
                dados, ajustes = self.df_deslocamento_integrado.copy(deep=True), None
        except ValueError as erro:
            self.checkbox_correcao_rampa.blockSignals(True)
            self.checkbox_correcao_rampa.setChecked(self.correcao_rampa_ativa)
            self.checkbox_correcao_rampa.blockSignals(False)
            QMessageBox.warning(self,'Falha ao corrigir deslocamento',str(erro))
            return
        self.correcao_rampa_ativa = bool(ativar)
        self.df_sensores, self.ajustes_rampa = dados, ajustes
        for c,curva in self.curvas.items():
            curva.setData(self.tempo,self.df_sensores[c].to_numpy())
        for plot in self.graficos_eixos.values():
            plot.enableAutoRange(x=False,y=True)
        self._atualizar_descricao_correcao()

    def mostrar_detalhes_ajuste(self):
        if self.ajustes_rampa is None:
            QMessageBox.information(self,'Ajuste do deslocamento','A correção linear está desmarcada.')
            return
        texto=['Reta removida: b + m × (t − t₀). Ajuste sobre todo o intervalo carregado.']
        for c in self.df_sensores:
            b,m=self.ajustes_rampa.loc[c,['intercepto_mm','inclinacao_mm_s']]
            texto.append(f'Canal {c}: b = {b:.17g} mm; m = {m:.17g} mm/s; início corrigido = {-b:.17g} mm.')
        texto.append('Duas derivadas não identificam a posição ou velocidade constantes removidas.')
        QMessageBox.information(self,'Detalhes do ajuste linear','\n'.join(texto))

    def verificar_por_derivacao(self):
        from .verificacao_integracao import TelaVerificacaoIntegracao
        canais={c:i for c,i in self.canais.items() if self.checkboxes_canais[c].isChecked()}
        if not canais:
            QMessageBox.information(self,'Verificação','Selecione pelo menos um canal.')
            return
        try:
            colunas=list(canais)
            janela=TelaVerificacaoIntegracao(self.tempo,self.df_sensores[colunas],canais,
                aceleracao_referencia=None if self.aceleracao_referencia is None else self.aceleracao_referencia[colunas],
                velocidade_referencia=None if self.velocidade_referencia is None else self.velocidade_referencia[colunas],
                inicio_arquivo=self.inicio_exportacao,intervalo_visualizacao=self.painel_intervalo.intervalo_exportacao(),
                descricao_origem=self.descricao_exportacao)
        except ValueError as erro:
            QMessageBox.warning(self,'Falha na verificação',str(erro))
            return
        return mostrar_resultado(self,janela)

    def gerar_deslocamento(self):
        canais = {c: info for c, info in self.canais.items() if self.checkboxes_canais[c].isChecked()}
        if not canais:
            QMessageBox.information(self, 'Integração', 'Selecione pelo menos um canal.')
            return
        try:
            dados = integrar_relativo(self.tempo, self.df_sensores[list(canais)], 'velocidade')
            janela = TelaIntegracao(
                self.tempo, dados, canais, 'deslocamento', self.caminho_atual,
                inicio_arquivo=self.inicio_exportacao,
                tratamentos=self.tratamentos_origem,
                medias_aceleracao=(None if self.medias_aceleracao is None else
                                   {c: self.medias_aceleracao[c] for c in canais}),
                intervalo_visualizacao=self.painel_intervalo.intervalo_exportacao(),
                aceleracao_referencia=(None if self.aceleracao_referencia is None else self.aceleracao_referencia[list(canais)]),
                velocidade_referencia=self.df_sensores[list(canais)],
            )
        except ValueError as erro:
            QMessageBox.warning(self, 'Falha ao integrar', str(erro))
            return
        return mostrar_resultado(self, janela)
