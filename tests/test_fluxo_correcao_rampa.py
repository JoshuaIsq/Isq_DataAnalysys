"""Fluxo completo da correção linear de deslocamento e sua verificação."""
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
from plotly.graph_objects import Figure

from isq_dataanalysys.exportacao.csv_tratado import ler_csv_tratado
from isq_dataanalysys.interface.dados_tratados import TelaDadosTratados
from isq_dataanalysys.interface.integracao import TelaIntegracao, _JANELAS_ABERTAS
from isq_dataanalysys.processamento.integracao import integrar_relativo


class FluxoCorrecaoRampaTests(unittest.TestCase):
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
        self.t=np.arange(2001)/200
        self.a=pd.DataFrame({1:.001*np.cos(2*np.pi*5*self.t),
                             3:.002*np.cos(2*np.pi*3*self.t)})
        self.v=integrar_relativo(self.t,self.a,'aceleracao')
        # Uma constante de velocidade reproduz a rampa descrita pelo usuário.
        self.v=self.v.add(pd.Series({1:.2,3:-.4}),axis='columns')
        self.canais={1:('X','Canal 1 — Sensor X'),3:('Z','Canal 3 — Sensor Z')}

    def fechar(self):
        for janela in reversed(self.janelas):
            if shiboken6.isValid(janela):
                janela.close()
                if not janela.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose):
                    janela.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        self.app.processEvents()

    def velocidade(self,referencia=True):
        w=TelaIntegracao(self.t,self.v,self.canais,'velocidade',
                        inicio_arquivo=datetime(2026,11,11,15),
                        aceleracao_referencia=self.a if referencia else None)
        self.janelas.append(w)
        w.show();self.app.processEvents()
        return w

    def test_padrao_corrigido_toggle_reversivel_e_intervalo_preservado(self):
        vel=self.velocidade()
        vel.painel_intervalo.definir_intervalo_segundos(2,8)
        copia_v=vel.df_sensores.copy(deep=True)
        copia_a=vel.aceleracao_referencia.copy(deep=True)
        disp=vel.gerar_deslocamento();self.janelas.append(disp)
        self.app.processEvents()
        bruto=integrar_relativo(self.t,self.v,'velocidade')
        self.assertTrue(disp.checkbox_correcao_rampa.isChecked())
        pd.testing.assert_frame_equal(disp.df_deslocamento_integrado,bruto)
        self.assertEqual(disp.painel_intervalo.intervalo_exportacao(),(2,8))
        for c in bruto:
            m,b=np.polyfit(self.t,bruto[c],1)
            np.testing.assert_allclose(disp.df_sensores[c],bruto[c]-(b+m*self.t),atol=1e-10)
            self.assertAlmostEqual(disp.df_sensores[c].iloc[0],-b,places=10)
        corrigido=disp.df_sensores.copy(deep=True)
        disp.checkbox_correcao_rampa.setChecked(False)
        pd.testing.assert_frame_equal(disp.df_sensores,bruto)
        self.assertEqual(disp.metadados_tratados['correcao_deslocamento']['metodo'],'nenhum')
        disp.checkbox_correcao_rampa.setChecked(True)
        pd.testing.assert_frame_equal(disp.df_sensores,corrigido)
        for plot in disp.plots_para_exportar():
            np.testing.assert_allclose(plot.viewRange()[0],[2,8],atol=1e-12)
        pd.testing.assert_frame_equal(vel.df_sensores,copia_v)
        pd.testing.assert_frame_equal(vel.aceleracao_referencia,copia_a)
        self.assertIn('não é imposto a zero',disp.descricao_exportacao)
        self.assertIn('ajuste linear removido',disp.windowTitle())
        self.aviso.assert_not_called()

    def test_botao_derivacao_recebe_aceleracao_usada_e_mesmo_relogio(self):
        vel=self.velocidade()
        vel.painel_intervalo.definir_intervalo_segundos(2,8)
        disp=vel.gerar_deslocamento();self.janelas.append(disp)
        disp.checkboxes_canais[3].setChecked(False)
        copia=disp.df_sensores.copy(deep=True)
        check=disp.verificar_por_derivacao();self.janelas.append(check)
        self.app.processEvents()
        pd.testing.assert_frame_equal(check.aceleracao_referencia,self.a[[1]])
        pd.testing.assert_frame_equal(check.velocidade_referencia,self.v[[1]])
        self.assertEqual(check.inicio_exportacao,datetime(2026,11,11,15))
        self.assertEqual(check.painel_intervalo.intervalo_exportacao(),(2,8))
        self.assertEqual(set(check.metricas),{1})
        self.assertGreater(check.metricas[1]['nrmse'],0)
        self.assertGreater(check.metricas[1]['correlacao'],.99999)
        pd.testing.assert_frame_equal(disp.df_sensores,copia)
        self.aviso.assert_not_called()

    def test_exportacoes_preservam_ajuste_e_reabertura_nao_reaplica(self):
        vel=self.velocidade()
        disp=vel.gerar_deslocamento();self.janelas.append(disp)
        self.app.processEvents()
        pasta=Path(self.tmp.name)
        destino=pasta/'deslocamento.csv'
        figuras=[]
        salvar=Figure.write_html
        def gravar(fig,*a,**k):
            figuras.append(fig)
            return salvar(fig,*a,**k)
        with patch.object(QFileDialog,'getSaveFileName',return_value=(str(destino),'CSV')), \
                patch.object(QFileDialog,'getExistingDirectory',return_value=str(pasta)), \
                patch.object(Figure,'write_html',gravar):
            disp.exportar_csv();disp.exportar_html();disp.exportar_svg()
        exportado=ler_csv_tratado(destino)
        pd.testing.assert_frame_equal(exportado.dados,disp.df_sensores)
        meta=exportado.metadados['correcao_deslocamento']
        self.assertEqual(meta['metodo'],'reta_minimos_quadrados')
        self.assertFalse(meta['inicio_corrigido_imposto_zero'])
        self.assertEqual(meta['intervalo_ajuste_s'],[0,10])
        self.assertEqual(figuras[0].layout.meta['correcao_deslocamento'],meta)
        outra=TelaDadosTratados();self.janelas.append(outra)
        self.assertTrue(outra.importar_caminho(destino))
        pd.testing.assert_frame_equal(outra.df_sensores,disp.df_sensores)
        self.assertEqual(outra.metadados_tratados['correcao_deslocamento'],meta)
        self.assertTrue(list(pasta.glob('*.svg')))
        self.assertTrue(list(pasta.glob('*.html')))
        self.aviso.assert_not_called()

    def test_falha_ajuste_preserva_estado_e_nao_abre_resultado(self):
        vel=self.velocidade()
        with patch('isq_dataanalysys.interface.integracao.corrigir_rampa_deslocamento',side_effect=ValueError('Ajuste inválido')):
            self.assertIsNone(vel.gerar_deslocamento())
        self.assertEqual(vel.janelas_resultados,[])
        self.assertEqual(self.aviso.call_count,1)
        disp=vel.gerar_deslocamento();self.janelas.append(disp)
        disp.checkbox_correcao_rampa.setChecked(False)
        copia=disp.df_sensores.copy(deep=True)
        with patch('isq_dataanalysys.interface.integracao.corrigir_rampa_deslocamento',side_effect=ValueError('Ajuste inválido')):
            disp.checkbox_correcao_rampa.setChecked(True)
        self.assertFalse(disp.checkbox_correcao_rampa.isChecked())
        self.assertFalse(disp.correcao_rampa_ativa)
        pd.testing.assert_frame_equal(disp.df_sensores,copia)
        self.assertEqual(self.aviso.call_count,2)

    def test_sem_canais_e_verificacao_sem_referencia(self):
        vel=self.velocidade(referencia=False)
        disp=vel.gerar_deslocamento();self.janelas.append(disp)
        check=disp.verificar_por_derivacao();self.janelas.append(check)
        self.assertEqual(check.metricas,{})
        self.assertIn('não está disponível',check.descricao_exportacao)
        for c in disp.checkboxes_canais.values():
            c.setChecked(False)
        self.assertIsNone(disp.verificar_por_derivacao())
        self.assertEqual(len(disp.janelas_resultados),1)

    def test_fechar_origem_nao_fecha_verificacao_e_registry_libera(self):
        vel=self.velocidade()
        disp=vel.gerar_deslocamento();self.janelas.append(disp)
        check=disp.verificar_por_derivacao();self.janelas.append(check)
        copia=check.df_sensores.copy(deep=True)
        self.assertIn(check,_JANELAS_ABERTAS)
        disp.close()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        self.app.processEvents()
        self.assertTrue(check.isVisible())
        pd.testing.assert_frame_equal(check.df_sensores,copia)
        check.close()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        self.app.processEvents()
        self.assertNotIn(check,_JANELAS_ABERTAS)
        self.aviso.assert_not_called()
