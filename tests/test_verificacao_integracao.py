"""Derivação acessível na interface e exportação do resultado verificável."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('MPLCONFIGDIR','/tmp/isq-matplotlib')

from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from isq_dataanalysys.exportacao.csv_tratado import DadosTratados, ler_csv_tratado
from isq_dataanalysys.interface.dados_tratados import TelaDadosTratados
from isq_dataanalysys.interface.verificacao_integracao import TelaVerificacaoIntegracao


class VerificacaoIntegracaoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.janelas=[]
        self.addCleanup(self.fechar)
        self.aviso=patch.object(QMessageBox,'warning').start()
        self.info=patch.object(QMessageBox,'information').start()
        self.addCleanup(patch.stopall)

    def fechar(self):
        for janela in reversed(self.janelas):
            if shiboken6.isValid(janela):
                janela.close()
                if not janela.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose):
                    janela.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        self.app.processEvents()
        self.janelas.clear()

    def test_parabola_derivadas_unidades_e_referencia_sem_mutar_entrada(self):
        t=np.arange(2001)/200
        index=np.arange(len(t))+20
        d=pd.DataFrame({1:5+3*t+2*t*t,5:7-2*t-t*t},index=index)
        a=pd.DataFrame({1:np.full(len(t),4/9806.65),5:np.full(len(t),-2/9806.65)},index=index)
        v=pd.DataFrame({1:3+4*t,5:-2-2*t},index=index)
        copias=[s.copy(deep=True) for s in (d,a,v)]
        w=TelaVerificacaoIntegracao(t,d,{1:('Y','Sensor Y'),5:('Z','Sensor Z')},a,v)
        self.janelas.append(w)
        w.show();self.app.processEvents()
        np.testing.assert_allclose(w.velocidade_derivada,v,atol=1e-9)
        np.testing.assert_allclose(w.aceleracao_recuperada,a,atol=1e-9)
        self.assertEqual(set(w.metricas),{1,5})
        for m in w.metricas.values():
            self.assertLess(m['rmse_g'],1e-9)
            self.assertIsNone(m['correlacao'])
            self.assertEqual(m['amostras'],len(t)-4)
        self.assertEqual(set(w.df_sensores),{'v_1','vref_1','a_1','ref_1','v_5','vref_5','a_5','ref_5'})
        self.assertEqual(w.canais['a_1']['unidade'],'g')
        self.assertEqual(w.canais['v_1']['unidade'],'mm/s')
        self.assertIn('após os tratamentos',w.descricao_exportacao)
        self.assertIn('não identificam posição',w.descricao_exportacao)
        w.botao_metricas.click()
        self.assertIn('NRMSE',self.info.call_args.args[2])
        for atual,anterior in zip((d,a,v),copias):
            pd.testing.assert_frame_equal(atual,anterior)
        self.aviso.assert_not_called()

    def test_senoide_tem_erro_discreto_explicito_e_correlacao(self):
        t=np.arange(4001)/200
        omega=2*np.pi*5
        d=pd.DataFrame({1:3+2*t+.2*np.cos(omega*t)})
        a=pd.DataFrame({1:-.2*omega*omega*np.cos(omega*t)/9806.65})
        w=TelaVerificacaoIntegracao(t,d,{1:('Y','Y')},a)
        self.janelas.append(w)
        ganho=(np.sin(omega/200)/(omega/200))**2
        np.testing.assert_allclose(w.aceleracao_recuperada[1].iloc[2:-2],a[1].iloc[2:-2]*ganho,atol=1e-9)
        self.assertGreater(w.metricas[1]['nrmse'],0)
        self.assertAlmostEqual(w.metricas[1]['nrmse'],1-ganho,places=7)
        self.assertGreater(w.metricas[1]['correlacao'],.999999)

    def test_sem_referencia_e_sinal_curto_ou_desalinhado(self):
        w=TelaVerificacaoIntegracao([0,1,2],pd.DataFrame({1:[0.,1.,4.]}),{1:('X','X')})
        self.janelas.append(w)
        self.assertEqual(w.metricas,{})
        self.assertIn('não está disponível',w.descricao_exportacao)
        with self.assertRaises(ValueError):
            TelaVerificacaoIntegracao([0,1],pd.DataFrame({1:[0.,1.]}),{1:('X','X')})
        with self.assertRaises(ValueError):
            TelaVerificacaoIntegracao([0,1,2],pd.DataFrame({1:[0.,1.,4.]}),{1:('X','X')},
                                      pd.DataFrame({1:[1.,2.,3.]},index=[4,5,6]))

    def test_recorte_relogio_exportacoes_e_csv_reaberto(self):
        t=np.arange(2400.,3601.)
        tau=t-t[0]
        d=pd.DataFrame({1:2+3*tau+.1*tau*tau})
        a=pd.DataFrame({1:np.full(len(t),.2/9806.65)})
        inicio=datetime(2026,11,11,15)
        w=TelaVerificacaoIntegracao(t,d,{1:('Y','Sensor Y')},a,inicio_arquivo=inicio,
                                   intervalo_visualizacao=(2700,3300),descricao_origem='Deslocamento com reta removida')
        self.janelas.append(w)
        w.show();self.app.processEvents()
        self.assertEqual(w.painel_intervalo.inicio_min.value(),45)
        self.assertEqual(w.painel_intervalo.fim_min.value(),55)
        for plot in w.graficos_eixos.values():
            np.testing.assert_array_equal(plot.viewRange()[0],[2700,3300])
            self.assertEqual(plot.getAxis('bottom').tickStrings([2700],1,1),['11/11/2026 12:45:00'])
        saida=Path(self.tmp.name)/'derivadas.csv'
        with patch.object(QFileDialog,'getSaveFileName',return_value=(str(saida),'CSV')), \
                patch.object(QFileDialog,'getExistingDirectory',return_value=self.tmp.name):
            w.exportar_csv()
            w.exportar_svg()
            w.exportar_html()
        self.assertTrue(list(Path(self.tmp.name).glob('*.svg')))
        self.assertTrue(list(Path(self.tmp.name).glob('*.html')))
        arquivo=ler_csv_tratado(saida)
        np.testing.assert_array_equal(arquivo.tempo,np.arange(2700.,3301.))
        self.assertEqual(arquivo.inicio_csv,inicio)
        self.assertEqual(arquivo.metadados['modalidade'],'verificacao_integracao')
        self.assertIn('1',arquivo.metadados['metricas_aceleracao'])
        self.assertEqual(arquivo.metadados['descricao_origem'],'Deslocamento com reta removida')
        outra=TelaDadosTratados()
        self.janelas.append(outra)
        self.assertTrue(outra.importar_caminho(saida))
        pd.testing.assert_frame_equal(outra.df_sensores,arquivo.dados)
        self.assertEqual(outra.inicio_exportacao,inicio)
        self.aviso.assert_not_called()

    def test_api_viewer_em_memoria_preserva_dados_e_rejeita_antes_de_mudar(self):
        w=TelaDadosTratados();self.janelas.append(w)
        dados=pd.DataFrame({1:[1.,2.,3.]})
        canais={1:dict(nome='Canal',unidade='mm',eixo='Y')}
        arquivo=DadosTratados(np.array([0.,1.,2.]),dados,canais,None,{'titulo':'Calculado'})
        self.assertTrue(w.carregar_dados(arquivo))
        self.assertIsNone(w.caminho_atual)
        dados.iloc[0,0]=100
        self.assertEqual(w.df_sensores.iloc[0,0],1)
        invalido=DadosTratados(np.array([0.,1.,2.]),dados,canais,None,{'inicio_gravacao_s':'inválido'})
        with self.assertRaises(ValueError):
            w.carregar_dados(invalido)
        self.assertEqual(w.df_sensores.iloc[0,0],1)
