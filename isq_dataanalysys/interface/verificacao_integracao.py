"""Derivadas do deslocamento e comparação com a aceleração realmente integrada."""
from copy import deepcopy

import numpy as np
import pandas as pd
from PySide6.QtWidgets import QPushButton, QMessageBox

from isq_dataanalysys import __version__
from isq_dataanalysys.exportacao.csv_tratado import DadosTratados
from isq_dataanalysys.processamento.integracao import derivar_deslocamento
from .dados_tratados import TelaDadosTratados


def _referencia_alinhada(referencia, deslocamento, nome):
    if referencia is None:
        return None
    if (not isinstance(referencia, pd.DataFrame) or len(referencia) != len(deslocamento)
            or not referencia.index.equals(deslocamento.index)
            or not all(c in referencia for c in deslocamento.columns)):
        raise ValueError(f'{nome}: dados e índices precisam corresponder ao deslocamento.')
    resultado = referencia[list(deslocamento.columns)].copy(deep=True)
    if not np.isfinite(resultado.to_numpy(dtype=float)).all():
        raise ValueError(f'{nome}: existem medições não finitas.')
    return resultado


class TelaVerificacaoIntegracao(TelaDadosTratados):
    """Mostra derivadas numéricas sem afirmar recuperação da posição física real."""

    def __init__(self, tempo, deslocamento, canais, aceleracao_referencia=None,
                 velocidade_referencia=None, inicio_arquivo=None,
                 intervalo_visualizacao=None, descricao_origem=''):
        velocidade, aceleracao = derivar_deslocamento(tempo, deslocamento)
        referencia_a = _referencia_alinhada(aceleracao_referencia, deslocamento, 'Aceleração de referência')
        referencia_v = _referencia_alinhada(velocidade_referencia, deslocamento, 'Velocidade de referência')
        if not isinstance(canais, dict) or not all(c in canais for c in deslocamento.columns):
            raise ValueError('Informe a identificação dos canais do deslocamento.')
        super().__init__()
        self.velocidade_derivada = velocidade.copy(deep=True)
        self.aceleracao_recuperada = aceleracao.copy(deep=True)
        self.aceleracao_referencia = referencia_a
        self.velocidade_referencia = referencia_v
        self.metricas = {}
        corte = slice(2,-2) if len(deslocamento) >= 5 else slice(None)
        self.amostras_borda_excluidas = 2 if len(deslocamento) >= 5 else 0
        if referencia_a is not None:
            for c in deslocamento:
                esperado = referencia_a[c].to_numpy(dtype=float)[corte]
                obtido = aceleracao[c].to_numpy(dtype=float)[corte]
                erro = obtido-esperado
                rmse = float(np.sqrt(np.mean(erro*erro)))
                rms_ref = float(np.sqrt(np.mean(esperado*esperado)))
                correlacao = (float(np.corrcoef(esperado,obtido)[0,1])
                              if len(esperado)>1 and np.ptp(esperado)>0 and np.ptp(obtido)>0 else None)
                self.metricas[c] = dict(rmse_g=rmse, erro_max_g=float(np.max(np.abs(erro))),
                                        nrmse=rmse/rms_ref if rms_ref>0 else None,
                                        correlacao=correlacao, amostras=len(esperado))

        colunas, descricoes = {}, {}

        def adicionar(prefixo, canal, valores, nome, unidade):
            identificador = f'{prefixo}_{canal}'
            while identificador in colunas:
                identificador += '_'
            eixo, rotulo = canais[canal]
            colunas[identificador] = valores
            descricoes[identificador] = dict(nome=f'{rotulo} — {nome}', unidade=unidade,
                                             eixo=eixo, canal_origem=str(canal))

        for c in deslocamento:
            adicionar('v',c,velocidade[c].to_numpy(),'velocidade derivada do deslocamento','mm/s')
            if referencia_v is not None:
                adicionar('vref',c,referencia_v[c].to_numpy(),'velocidade integrada de origem','mm/s')
            adicionar('a',c,aceleracao[c].to_numpy(),'aceleração recuperada por duas derivadas','g')
            if referencia_a is not None:
                adicionar('ref',c,referencia_a[c].to_numpy(),'aceleração usada na integração','g')

        descricao = (
            'Verificação numérica: deslocamento → derivar → velocidade (mm/s) → derivar → aceleração (g).\n'
            'Referência: aceleração realmente integrada, após os tratamentos e a retirada de média escolhidos.\n'
            'Se uma reta foi retirada do deslocamento, a velocidade derivada muda pela inclinação dessa reta.\n'
            'Derivadas discretas têm erro de aproximação; duas derivadas não identificam posição ou velocidade iniciais.'
        )
        if self.metricas:
            max_rmse = max(m['rmse_g'] for m in self.metricas.values())
            max_erro = max(m['erro_max_g'] for m in self.metricas.values())
            descricao += (f'\nComparação entre canais: maior RMSE = {max_rmse:.6g} g; '
                          f'maior erro absoluto = {max_erro:.6g} g. '
                          f'Excluídas {self.amostras_borda_excluidas} amostras de cada extremidade.')
        else:
            descricao += '\nA aceleração de referência não está disponível; não foi calculado erro de recuperação.'
        metadata = dict(
            titulo='Verificação da integração por derivação', modalidade='verificacao_integracao',
            descricao=descricao, descricao_origem=str(descricao_origem), inicio_gravacao_s=0.,
            metodo_derivacao='Diferenças finitas: numpy.gradient, edge_order=2, duas etapas',
            referencia_aceleracao='Sinal efetivamente integrado, após tratamentos e compensação de média escolhidos',
            metricas_aceleracao={str(c):deepcopy(m) for c,m in self.metricas.items()},
            amostras_borda_excluidas=self.amostras_borda_excluidas,
        )
        arquivo = DadosTratados(np.array(tempo,dtype=float,copy=True),
                                pd.DataFrame(colunas,index=deslocamento.index), descricoes,
                                inicio_arquivo, metadata)
        self.carregar_dados(arquivo)
        self.botao_abrir.hide()
        self.botao_metricas = QPushButton('Erros por canal')
        self.botao_metricas.clicked.connect(self.mostrar_metricas)
        self.layout_acoes.addWidget(self.botao_metricas)
        self.setWindowTitle(f'Verificação da integração por derivação — v{__version__}')
        self.resize(1400,950)
        detalhes = []
        for c,m in self.metricas.items():
            detalhes.append(f'Canal {c}: RMSE {m["rmse_g"]:.9g} g; erro máximo {m["erro_max_g"]:.9g} g; '
                            f'NRMSE {m["nrmse"]}; correlação {m["correlacao"]}')
        self.rotulo_origem.setToolTip('\n'.join(detalhes) or descricao)
        for plot in self.graficos_eixos.values():
            plot.setDownsampling(auto=True,mode='peak')
            plot.setClipToView(True)
        if intervalo_visualizacao is not None:
            self.painel_intervalo.definir_intervalo_segundos(*intervalo_visualizacao)

    def mostrar_metricas(self):
        texto=['Comparação com a aceleração usada na integração, após os tratamentos.',
               f'Excluídas {self.amostras_borda_excluidas} amostras de cada extremidade.']
        for c,m in self.metricas.items():
            relativo = 'indefinido (referência RMS zero)' if m['nrmse'] is None else f"{100*m['nrmse']:.6g}%"
            corr = 'indefinida' if m['correlacao'] is None else f"{m['correlacao']:.9g}"
            texto.append(f"Canal {c}: RMSE {m['rmse_g']:.9g} g; erro máximo {m['erro_max_g']:.9g} g; "
                         f'NRMSE {relativo}; correlação {corr}.')
        if not self.metricas:
            texto.append('Referência não disponível; não foi calculado erro de recuperação.')
        texto.append('A igualdade da segunda derivada não valida a posição ou velocidade iniciais removidas.')
        QMessageBox.information(self,'Erros da verificação por derivação','\n'.join(texto))
