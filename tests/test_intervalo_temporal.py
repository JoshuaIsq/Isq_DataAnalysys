"""Minutos de gravação: limites visuais, janelas independentes e troca FFT/RMS."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('MPLCONFIGDIR','/tmp/isq-matplotlib')
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
import shiboken6
from PySide6.QtCore import QCoreApplication,QEvent,Qt
from PySide6.QtWidgets import QApplication,QMessageBox
from isq_dataanalysys.interface.intervalo_temporal import PainelIntervaloTemporal
from isq_dataanalysys.interface.acelerometria import TelaLynxAcelerometria
from isq_dataanalysys.interface.integracao import TelaIntegracao
from tests.apoio import ArquivoMixin


class PainelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.painel=PainelIntervaloTemporal()
        self.addCleanup(self.painel.deleteLater)

    def test_40_a_60_minutos_e_voltar_a_todo_registro(self):
        p=self.painel
        self.assertFalse(p.isEnabled())
        p.definir_dados(np.arange(4201,dtype=float))
        self.assertEqual(p.limites_segundos,(0.,4200.))
        self.assertEqual(p.inicio_min.minimum(),0)
        self.assertEqual(p.fim_min.maximum(),70)
        self.assertIsNone(p.intervalo_exportacao())
        alteracoes=[]
        p.intervalo_alterado.connect(alteracoes.append)
        p.inicio_min.setValue(40)
        p.fim_min.setValue(60)
        self.assertTrue(p.aplicar())
        self.assertEqual(p.intervalo_exportacao(),(2400.,3600.))
        self.assertEqual(alteracoes[-1],(2400.,3600.))
        p.mostrar_completo()
        self.assertIsNone(p.intervalo_exportacao())
        self.assertEqual(alteracoes[-1],(0.,4200.))
        self.assertEqual(p.fim_min.value(),70)

    def test_recorte_nao_reinicia_contagem_de_minutos(self):
        p=self.painel
        p.definir_dados(np.arange(2400,3601))
        self.assertEqual(p.inicio_min.value(),40)
        self.assertEqual(p.fim_min.value(),60)
        self.assertEqual(p.inicio_min.minimum(),40)
        self.assertEqual(p.fim_min.maximum(),60)
        p.definir_dados(np.arange(2500,3601),inicio_gravacao_s=100)
        self.assertEqual(p.inicio_min.value(),40)
        self.assertAlmostEqual(p.fim_min.value(),3500/60,places=8)

    def test_rejeita_invertido_igual_fora_limites_e_tempos_invalidos(self):
        p=self.painel
        p.definir_dados([0,60,120])
        for intervalo in [(60,60),(120,60),(-1,60),(0,121),(0,np.nan)]:
            with self.subTest(intervalo=intervalo),self.assertRaises(ValueError):
                p.definir_intervalo_segundos(*intervalo)
        self.assertIsNone(p.intervalo_exportacao())
        p.inicio_min.setValue(1)
        p.fim_min.setValue(1)
        with patch.object(QMessageBox,'warning') as aviso:
            self.assertFalse(p.aplicar())
            aviso.assert_called_once()
        for tempo in [[],[0,0],[1,0],[0,np.inf],[0,np.nan]]:
            with self.subTest(tempo=tempo),self.assertRaises(ValueError):
                p.definir_dados(tempo)

    def test_extremidade_fracionaria_nao_ultrapassa_dados(self):
        p=self.painel
        for inicio,fim in [(0,.005),(0,.01),(0,7000),(600.005,7000.005)]:
            with self.subTest(inicio=inicio,fim=fim):
                t=np.array([inicio,(inicio+fim)/2,fim])
                p.definir_dados(t)
                self.assertTrue(p.aplicar())
                self.assertEqual(p.intervalo_exportacao(),(inicio,fim))
                baixo,alto=p.intervalo_exportacao()
                self.assertTrue(((t>=baixo)&(t<=alto)).all())


class JanelasTests(ArquivoMixin,unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp()
        self.janelas=[]
        self.aviso=patch.object(QMessageBox,'warning').start()
        self.addCleanup(patch.stopall)
        self.addCleanup(self.fechar)

    def fechar(self):
        for janela in reversed(self.janelas):
            if shiboken6.isValid(janela):
                janela.close()
                if not janela.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose):
                    janela.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        self.app.processEvents()
        self.janelas.clear()

    def abrir_aceleracao(self):
        acm=TelaLynxAcelerometria()
        self.janelas.append(acm)
        acm.resize(1330,625)
        acm.show()
        acm.importar_caminho(self.arquivo(['g']*3))
        self.app.processEvents()
        return acm

    def test_aceleracao_velocidade_deslocamento_mantem_dados_e_recorte(self):
        acm=self.abrir_aceleracao()
        original=acm.df_sensores.copy(deep=True)
        curvas={c:np.array(v.getOriginalDataset()[1],copy=True) for c,v in acm.curvas_lynx.items()}
        acm.aplicar_intervalo_temporal((.2,.8))
        vel=acm.gerar_velocidade()
        self.janelas.append(vel)
        disp=vel.gerar_deslocamento()
        self.janelas.append(disp)
        self.app.processEvents()
        for janela in (acm,vel,disp):
            self.assertEqual(janela.intervalo_exportacao(),(.2,.8))
            for plot in janela.graficos_eixos.values():
                np.testing.assert_allclose(plot.viewRange()[0],[.2,.8],atol=1e-8)
            np.testing.assert_array_equal(janela.tempo,acm.tempo)
            self.assertEqual(len(janela.df_sensores),len(original))
        pd.testing.assert_frame_equal(acm.df_sensores,original)
        for c,curva in acm.curvas_lynx.items():
            np.testing.assert_array_equal(curva.getOriginalDataset()[1],curvas[c])
        snapshot=vel.df_sensores.copy(deep=True)
        vel.painel_intervalo.definir_intervalo_segundos(.3,.6)
        self.assertEqual(acm.intervalo_exportacao(),(.2,.8))
        self.assertEqual(disp.intervalo_exportacao(),(.2,.8))
        pd.testing.assert_frame_equal(vel.df_sensores,snapshot)
        self.aviso.assert_not_called()

    def test_fft_desabilita_intervalo_e_retorno_temporal_restaura(self):
        acm=self.abrir_aceleracao()
        acm.aplicar_intervalo_temporal((.2,.8))
        for modo in ('fft','rms'):
            getattr(acm,'botao_'+modo).setChecked(True)
            self.app.processEvents()
            self.assertEqual(acm.campo_tempo_inicio.isEnabled(),modo!='fft')
            if modo=='fft': self.assertIsNone(acm.intervalo_exportacao())
            else: self.assertEqual(acm.intervalo_exportacao(),(.2,.8))
        acm.botao_rms.setChecked(False)
        self.app.processEvents()
        self.assertEqual(acm.intervalo_exportacao(),(.2,.8))
        for plot in acm.graficos_eixos.values():
            np.testing.assert_allclose(plot.viewRange()[0],[.2,.8],atol=1e-8)
        self.aviso.assert_not_called()

    def test_resultado_40_a_60_minutos_e_uma_amostra(self):
        t=np.arange(4201,dtype=float)
        dados=pd.DataFrame({1:np.sin(t),2:np.cos(t)})
        janela=TelaIntegracao(t,dados,{1:('Y','Canal Y'),2:('Z','Canal Z')},'velocidade')
        self.janelas.append(janela)
        janela.resize(1330,625)
        janela.show()
        janela.painel_intervalo.inicio_min.setValue(40)
        janela.painel_intervalo.fim_min.setValue(60)
        janela.painel_intervalo.aplicar()
        self.app.processEvents()
        self.assertEqual(janela.intervalo_exportacao(),(2400.,3600.))
        for plot in janela.graficos_eixos.values():
            np.testing.assert_allclose(plot.viewRange()[0],[2400,3600],atol=1e-8)
        janela.resize(1100,800)
        self.app.processEvents()
        for plot in janela.graficos_eixos.values():
            np.testing.assert_allclose(plot.viewRange()[0],[2400,3600],atol=1e-8)
        janela.graficos_eixos['Y'].setXRange(2500,3100,padding=0)
        self.app.processEvents()
        for plot in janela.graficos_eixos.values():
            np.testing.assert_allclose(plot.viewRange()[0],[2500,3100],atol=1e-8)
        pd.testing.assert_frame_equal(janela.df_sensores,dados)

    def test_rms_log_preserva_zeros_para_csv(self):
        acm=TelaLynxAcelerometria()
        self.janelas.append(acm)
        def zerar(linhas):
            for linha in linhas[5:]:
                linha[1:]=['0']*3
        acm.importar_caminho(self.arquivo(['g']*3,alterar=zerar))
        acm.botao_rms.setChecked(True)
        acm.checkbox_log_rms.setChecked(True)
        for curva in acm.curvas_lynx.values():
            self.assertTrue(np.isnan(curva.getOriginalDataset()[1]).all())
            np.testing.assert_array_equal(curva.dados_csv,0)


if __name__=='__main__': unittest.main()
