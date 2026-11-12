"""Cálculos com solução conhecida e fluxo real de janelas/exportações."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('MPLCONFIGDIR', '/tmp/isq-matplotlib')
import tempfile
import json
from datetime import datetime
import matplotlib.dates as mdates
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from isq_dataanalysys.processamento.integracao import integrar_relativo, retirar_media_aceleracao
from isq_dataanalysys.interface.acelerometria import TelaLynxAcelerometria
from isq_dataanalysys.exportacao.html import criar_figura_html
from isq_dataanalysys import __version__ as VERSAO
from isq_dataanalysys.processamento.sinais import Processamento
from tests.apoio import ArquivoMixin


def integral_referencia(tempo, valores):
    """Áreas somadas em precisão estendida, sem usar o integrador de produção."""
    t = np.asarray(tempo, dtype=np.longdouble)
    y = np.asarray(valores, dtype=np.longdouble)
    saida = np.zeros_like(y)
    for i in range(1, len(t)):
        saida[i] = saida[i-1] + (t[i]-t[i-1])*(y[i-1]+y[i])/2
    return np.asarray(saida, dtype=float)


def texto_exportacao(caminho):
    conteudo = caminho.read_text()
    if caminho.suffix == '.svg':
        return conteudo
    # Plotly usa escapes JSON válidos para acentos no documento HTML.
    trecho = conteudo[conteudo.rfind('Plotly.newPlot(')+len('Plotly.newPlot('):]
    decoder = json.JSONDecoder()
    valores = []
    for _ in range(3):
        valor, fim = decoder.raw_decode(trecho.lstrip())
        valores.append(valor)
        trecho = trecho.lstrip()[fim:].lstrip().lstrip(',').lstrip()
    return valores[2]['title']['text']


class CalculoTests(unittest.TestCase):
    def test_um_g_converte_para_m_s2_e_entrega_mm_s(self):
        t=np.array([0.,1.,2.])
        # Sem compensação de média neste ensaio de unidades: 1 g = 9,80665 m/s².
        v=integrar_relativo(t,pd.DataFrame({1:[1.,1.,1.]}),'aceleracao')
        d=integrar_relativo(t,v,'velocidade')
        np.testing.assert_allclose(v[1],np.array([0.,9.80665,19.6133])*1000,atol=1e-9)
        np.testing.assert_allclose(d[1],np.array([0.,4.903325,19.6133])*1000,atol=1e-9)

    def test_retira_somente_media_por_canal_e_preserva_entrada(self):
        t = np.array([10,10.5,11,11.5])
        dados = pd.DataFrame({4: [1.,2.,6.,8.], 9: [10.,20.,60.,80.]}, index=[20,21,22,23])
        copia = dados.copy(deep=True)
        a, medias = retirar_media_aceleracao(t, dados)
        np.testing.assert_array_equal(medias, [4.25,42.5])
        np.testing.assert_array_equal(a[4], [-3.25,-2.25,1.75,3.75])
        np.testing.assert_array_equal(a[9], 10*a[4])
        np.testing.assert_allclose(a.mean(), 0, atol=1e-14)
        pd.testing.assert_frame_equal(a.add(medias, axis='columns'), copia)
        pd.testing.assert_frame_equal(dados, copia)
        self.assertFalse(np.shares_memory(a.to_numpy(), dados.to_numpy()))
        # A inclinação permanece. A velocidade não é recentrada, nem o final imposto em zero.
        v = integrar_relativo(t, a, 'aceleracao')
        d = integrar_relativo(t, v, 'velocidade')
        np.testing.assert_allclose(v[4], 9806.65*np.array([0,-1.375,-1.5,-.125]), atol=1e-10)
        np.testing.assert_allclose(d[4], 9806.65*np.array([0,-.34375,-1.0625,-1.46875]), atol=1e-10)
        self.assertNotEqual(v[4].mean(), 0)
        self.assertNotEqual(d.iloc[-1,0], 0)

    def test_media_constante_removida_e_rampa_preservada(self):
        t = np.arange(1001)/200
        dados = pd.DataFrame({1: np.full(len(t), .03), 5: .1+.001*t})
        a, medias = retirar_media_aceleracao(t, dados)
        np.testing.assert_allclose(medias, [.03,.1025], atol=1e-14)
        np.testing.assert_allclose(a[1], 0, atol=1e-14)
        np.testing.assert_allclose(a[5], .001*(t-2.5), atol=1e-14)
        self.assertGreater(a[5].std(), 0)

    def test_media_rejeita_entradas_invalidas_e_overflow(self):
        for tempo, dados in [([0], pd.DataFrame({1:[1.]})),
                             ([0,1,3], pd.DataFrame({1:[1.,2.,3.]})),
                             ([0,1], pd.DataFrame({1:[1.,np.nan]}))]:
            with self.assertRaises(ValueError):
                retirar_media_aceleracao(tempo, dados)
        with self.assertRaisesRegex(ValueError, 'Não foi possível retirar a média'):
            retirar_media_aceleracao([0,1], pd.DataFrame({1:[1e308,1e308]}))

    def test_constante_unidades_condicoes_iniciais_e_preservacao(self):
        t = np.arange(12001)/200
        dados = pd.DataFrame({4: np.full(len(t), 1e-6), 9: np.full(len(t), -2e-6)},
                             index=np.arange(len(t))+20)
        original = dados.copy(deep=True)
        v = integrar_relativo(t+100, dados, 'aceleracao')
        d = integrar_relativo(t+100, v, 'velocidade')
        for canal, a in ((4, .00980665), (9, -.0196133)):
            np.testing.assert_allclose(v[canal], a*t, atol=1e-12)
            np.testing.assert_allclose(d[canal], a*t*t/2, atol=1e-10)
        self.assertAlmostEqual(v.iloc[-1,0], .588399, places=10)
        self.assertAlmostEqual(d.iloc[-1,0], 17.65197, places=9)
        for resultado in (v, d):
            self.assertEqual(resultado.iloc[0].tolist(), [0, 0])
            self.assertEqual(list(resultado), [4, 9])
            self.assertTrue(resultado.index.equals(dados.index))
        pd.testing.assert_frame_equal(dados, original)

    def test_nao_remove_reta_da_aceleracao_nem_quadratica_da_velocidade(self):
        h = 1/200
        t = np.arange(2001)*h
        v = integrar_relativo(t, pd.DataFrame({1: (3+4*t)/9806.65}), 'aceleracao')
        np.testing.assert_allclose(v[1], 3*t+2*t*t, atol=1e-10)
        # Integral analítica e erro conhecido dos trapézios para uma quadrática.
        d = integrar_relativo(t, pd.DataFrame({1: 5+2*t+7*t*t}), 'velocidade')
        np.testing.assert_allclose(d[1], 5*t+t*t+7*(t**3/3+h*h*t/6), atol=1e-10)

    def test_senoides_temporais_com_solucoes_discretas_conhecidas(self):
        fs = 200
        t = np.arange(4001)/fs
        amplitude_g = .02
        for f in (1, 2, 5, 10, 20, 30):
            with self.subTest(f_hz=f):
                w = 2*np.pi*f
                c = 1/(2*fs*np.tan(np.pi*f/fs))
                a = pd.DataFrame({7: amplitude_g*np.cos(w*t)})
                v = integrar_relativo(t, a, 'aceleracao')
                d = integrar_relativo(t, v, 'velocidade')
                np.testing.assert_allclose(v[7], amplitude_g*9806.65*c*np.sin(w*t), atol=1e-9)
                np.testing.assert_allclose(d[7], amplitude_g*9806.65*c*c*(1-np.cos(w*t)), atol=1e-8)
                self.assertEqual(v.iloc[0,0], 0)
                self.assertEqual(d.iloc[0,0], 0)

    def test_integral_dos_valores_tratados_com_referencia_independente(self):
        t = np.arange(12001)/200
        sinal = .03 + .02*np.sin(2*np.pi*5*t) + .004*np.cos(2*np.pi*45*t)
        original = pd.DataFrame({1: sinal, 5: -2*sinal}, index=np.arange(len(t))+10)
        configuracoes = ({}, {'passa_banda': (1,30)}, {'passa_alta': 1}, {'passa_baixa': 30},
                         {'calibracao': 2, 'offset': 200, 'media_movel': 5})
        for config in configuracoes:
            with self.subTest(config=config):
                a, _ = Processamento.aplicar(t, original, config)
                copia = a.copy(deep=True)
                v = integrar_relativo(t, a, 'aceleracao')
                d = integrar_relativo(t, v, 'velocidade')
                esperado_v = integral_referencia(t, a.to_numpy().astype(np.longdouble)*np.longdouble('9806.65'))
                esperado_d = integral_referencia(t, esperado_v)
                np.testing.assert_allclose(v, esperado_v, rtol=1e-11, atol=1e-9)
                np.testing.assert_allclose(d, esperado_d, rtol=1e-11, atol=1e-8)
                pd.testing.assert_frame_equal(a, copia)

    def test_prefixo_independe_de_amostras_futuras_e_origem_do_tempo(self):
        t = np.arange(4001)/200
        a = pd.DataFrame({1: .01*np.cos(2*np.pi*5*t)+1e-5*t})
        v = integrar_relativo(t, a, 'aceleracao')
        d = integrar_relativo(t, v, 'velocidade')
        v_parcial = integrar_relativo(t[:2000], a.iloc[:2000], 'aceleracao')
        d_parcial = integrar_relativo(t[:2000], v_parcial, 'velocidade')
        pd.testing.assert_frame_equal(v.iloc[:2000], v_parcial)
        pd.testing.assert_frame_equal(d.iloc[:2000], d_parcial)
        np.testing.assert_allclose(integrar_relativo(t+10000, a, 'aceleracao'), v, atol=1e-8)

    def test_duas_amostras_bastam_para_a_area_do_trapezio(self):
        dados = pd.DataFrame({1: [2.,4.]})
        for grandeza, fator in (('aceleracao',9806.65), ('velocidade',1)):
            r = integrar_relativo([10,12], dados, grandeza)
            np.testing.assert_allclose(r[1], [0,6*fator], atol=1e-10)

    def test_erro_numerico_e_grandeza_desconhecida(self):
        dados = pd.DataFrame({1: [1.,2.,4.,8.]})
        with self.assertRaises(ValueError):
            integrar_relativo([0,1,2,3], dados, 'fft')
        with self.assertRaisesRegex(ValueError, 'Não foi possível integrar'):
            integrar_relativo([0,1,2,3], pd.DataFrame({1: np.array([1,-1,2,-2])*1e306}), 'aceleracao')

    def test_entradas_invalidas(self):
        for tempo, valores, tipo in [([0], [1], 'aceleracao'),
                                    ([0,0,1], [1,2,3], 'aceleracao'),
                                    ([0,1,2], [1,np.nan,3], 'aceleracao'),
                                    ([0,1,3], [1,2,3], 'aceleracao')]:
            with self.assertRaises(ValueError):
                integrar_relativo(tempo, pd.DataFrame({1: valores}), tipo)


class FluxoTests(ArquivoMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp()
        self.aviso = patch.object(QMessageBox, 'warning').start()
        self.addCleanup(patch.stopall)
        self.janelas = []
        self.addCleanup(self.fechar)

    def fechar(self):
        for janela in reversed(self.janelas):
            if shiboken6.isValid(janela):
                janela.close()
                if not janela.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose):
                    janela.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()
        self.janelas.clear()

    def test_fluxo_temporal_independente_em_fft_e_rms_e_exportacoes(self):
        for modo in ('fft', 'rms'):
            acm = TelaLynxAcelerometria()
            self.janelas.append(acm)
            acm.show()
            self.assertFalse(acm.botao_velocidade.isEnabled())
            acm.importar_caminho(self.arquivo(['g']*6, encoding='cp1252'))
            acm.aplicar_configuracao({'offset': 3, 'passa_banda': (10, 100)})
            getattr(acm, 'botao_'+modo).click()
            acm.checkboxes_eixos[(1, 'Y')].setChecked(False)
            acm.checkboxes_canais[2].setChecked(False)
            original = acm.df_sensores.copy(deep=True)
            curvas = {k: tuple(np.array(v, copy=True) for v in c.getOriginalDataset()) for k, c in acm.curvas_lynx.items()}
            acm.botao_velocidade.click()
            vel = acm.janelas_resultados[-1]
            self.janelas.append(vel)
            self.assertTrue(acm.isVisible())
            self.assertTrue(vel.isVisible())
            self.assertEqual(list(vel.df_sensores), [1, 3])
            entrada = original[[1,3]].subtract(original[[1,3]].mean(), axis='columns')
            np.testing.assert_allclose(vel.df_sensores, integral_referencia(acm.tempo, entrada.to_numpy()*9806.65), atol=1e-9)
            self.assertEqual(set(vel.medias_aceleracao), {1,3})
            self.assertFalse(np.shares_memory(acm.tempo, vel.tempo))
            vel.checkboxes_canais[3].setChecked(False)
            vel.botao_deslocamento.click()
            desp = vel.janelas_resultados[-1]
            self.janelas.append(desp)
            self.app.processEvents()
            self.assertTrue(vel.isVisible())
            self.assertTrue(desp.isVisible())
            pd.testing.assert_frame_equal(desp.df_deslocamento_integrado, integrar_relativo(vel.tempo, vel.df_sensores[[1]], 'velocidade'))
            self.assertTrue(desp.correcao_rampa_ativa)
            pd.testing.assert_frame_equal(acm.df_sensores, original)
            for k, c in acm.curvas_lynx.items():
                for a, b in zip(c.getOriginalDataset(), curvas[k]):
                    np.testing.assert_array_equal(a, b)
            for janela, unidade in ((acm, 'g' if modo == 'fft' else 'mg'), (vel, 'mm/s'), (desp, 'mm')):
                self.assertEqual(janela.graficos_eixos['X'].getAxis('left').labelUnits, unidade)
                fig = criar_figura_html(list(janela.graficos_eixos.values()))
                if janela is not acm:
                    self.assertEqual(len(fig.data), 1)
                    self.assertIn('intervalo:', janela.descricao_exportacao)
                with tempfile.TemporaryDirectory() as pasta:
                    with patch.object(QFileDialog, 'getExistingDirectory', return_value=pasta), patch.object(QMessageBox, 'information'):
                        janela.exportar_svg()
                        janela.exportar_html()
                    svg = list(Path(pasta).glob('*.svg'))
                    html = list(Path(pasta).glob('*.html'))
                    self.assertEqual(len(svg), 1)
                    self.assertEqual(len(html), 1)
                    self.assertIn('<svg', svg[0].read_text())
                    self.assertIn('Canal 1', html[0].read_text())
                    if janela is not acm:
                        self.assertNotIn('Canal 3 —', html[0].read_text())
                        self.assertIn(unidade, fig.layout.yaxis.title.text)
            # Resultados continuam independentes após restaurar/reimportar a origem.
            snapshot = vel.df_sensores.copy()
            acm.restaurar_original()
            acm.importar_caminho(self.arquivo(['g']*3))
            pd.testing.assert_frame_equal(vel.df_sensores, snapshot)
            desp.close()
            self.assertTrue(vel.isVisible())
            vel.close()
            self.assertTrue(acm.isVisible())
        self.aviso.assert_not_called()

    def test_passa_banda_integracao_fiel_e_metodo_nas_exportacoes(self):
        acm = self.janela_aceleracao(3)
        acm.checkbox_media_aceleracao.setChecked(False)
        acm.aplicar_configuracao({'passa_banda': (1,30)})
        origem = acm.df_sensores.copy(deep=True)
        tratamentos = acm.rotulo_ativos.text()
        esperado_v = integral_referencia(acm.tempo, origem.to_numpy()*9806.65)
        vel = acm.gerar_velocidade()
        self.janelas.append(vel)
        np.testing.assert_allclose(vel.df_sensores, esperado_v, atol=1e-9)
        # Mudar a origem não muda os tratamentos registrados nem a velocidade já aberta.
        acm.restaurar_original()
        disp = vel.gerar_deslocamento()
        self.janelas.append(disp)
        disp.checkbox_correcao_rampa.setChecked(False)
        np.testing.assert_allclose(disp.df_sensores, integral_referencia(vel.tempo, esperado_v), atol=1e-9)
        for janela in (vel, disp):
            self.assertEqual(janela.tratamentos_origem, tratamentos)
            self.assertIn('Passa-banda: 1–30 Hz', janela.descricao_exportacao)
            self.assertIsNone(janela.medias_aceleracao)
            self.assertIn('Sem retirada da média da aceleração', janela.descricao_exportacao)
            self.assertNotIn('remover ajuste', janela.descricao_exportacao)
            figura = criar_figura_html(janela.plots_para_exportar(), descricao=janela.descricao_exportacao)
            for curva, canal in zip(figura.data, janela.df_sensores):
                np.testing.assert_allclose(curva.y, janela.df_sensores[canal], atol=1e-12)
            with tempfile.TemporaryDirectory() as pasta:
                with patch.object(QFileDialog, 'getExistingDirectory', return_value=pasta), \
                        patch.object(QMessageBox, 'information'):
                    janela.exportar_svg()
                    janela.exportar_html()
                for extensao in ('svg','html'):
                    arquivos = list(Path(pasta).glob(f'*.{extensao}'))
                    self.assertEqual(len(arquivos), 1)
                    conteudo = texto_exportacao(arquivos[0])
                    self.assertTrue('trapézios' in conteudo, 'Método ausente na exportação')
                    self.assertTrue('Sem retirada da média da aceleração' in conteudo,
                                    'Referência da integral ausente na exportação')
                    self.assertTrue('1–30 Hz' in conteudo, 'Cortes do filtro ausentes na exportação')
        self.aviso.assert_not_called()

    def test_media_so_aceleracao_por_padrao_origem_independente_e_exportacoes(self):
        acm = self.janela_aceleracao(3)
        self.assertTrue(acm.checkbox_media_aceleracao.isChecked())
        acm.aplicar_configuracao({'passa_banda': (1,30)})
        origem = acm.df_sensores.copy(deep=True)
        curvas = {c: np.array(v.getOriginalDataset()[1],copy=True) for c,v in acm.curvas_lynx.items()}
        medias = origem.mean()
        entrada = origem.subtract(medias, axis='columns')
        esperado_v = integral_referencia(acm.tempo, entrada.to_numpy()*9806.65)
        vel = acm.gerar_velocidade()
        self.janelas.append(vel)
        np.testing.assert_allclose(vel.df_sensores, esperado_v, atol=1e-9)
        for c in medias.index:
            self.assertAlmostEqual(vel.medias_aceleracao[c], medias[c], places=12)
        pd.testing.assert_frame_equal(acm.df_sensores, origem)
        for c,curva in acm.curvas_lynx.items():
            np.testing.assert_array_equal(curva.getOriginalDataset()[1],curvas[c])
        # Configuração e médias permanecem no resultado já gerado.
        acm.checkbox_media_aceleracao.setChecked(False)
        acm.restaurar_original()
        vel.checkboxes_canais[3].setChecked(False)
        disp = vel.gerar_deslocamento()
        self.janelas.append(disp)
        np.testing.assert_allclose(disp.df_deslocamento_integrado,
                                   integral_referencia(vel.tempo, esperado_v[:,:2]), atol=1e-9)
        self.assertEqual(set(disp.medias_aceleracao), {1,2})
        self.assertTrue((vel.df_sensores.iloc[0] == 0).all())
        self.assertTrue((disp.df_deslocamento_integrado.iloc[0] == 0).all())
        np.testing.assert_allclose(disp.df_sensores.iloc[0],-disp.ajustes_rampa['intercepto_mm'],atol=1e-10)
        self.assertIn('sem retirar sua média',disp.descricao_exportacao)
        for janela in (vel,disp):
            with tempfile.TemporaryDirectory() as pasta:
                with patch.object(QFileDialog,'getExistingDirectory',return_value=pasta), \
                        patch.object(QMessageBox,'information'):
                    janela.exportar_svg()
                    janela.exportar_html()
                for extensao in ('svg','html'):
                    arquivos = list(Path(pasta).glob(f'*.{extensao}'))
                    self.assertEqual(len(arquivos),1)
                    texto = texto_exportacao(arquivos[0])
                    for esperado in ('Média aritmética retirada somente da aceleração',
                                     'Valores em g', 'Canal 1:', 'Passa-banda: 1–30 Hz'):
                        self.assertTrue(esperado in texto, f'Metadado ausente: {esperado}')
        self.aviso.assert_not_called()

    def test_sem_canais_nao_abre_janela(self):
        acm = TelaLynxAcelerometria()
        self.janelas.append(acm)
        acm.importar_caminho(self.arquivo(['g']*3))
        acm.checkboxes_canais[1].setChecked(False)
        with patch.object(QMessageBox, 'information'):
            acm.botao_velocidade.click()
        self.assertEqual(acm.janelas_resultados, [])

    def janela_aceleracao(self, canais=12):
        acm = TelaLynxAcelerometria()
        self.janelas.append(acm)
        acm.resize(1330, 625)
        acm.show()
        acm.importar_caminho(self.arquivo(['g']*canais))
        self.app.processEvents()
        return acm

    def verificar_botao_visivel(self, janela, botao):
        self.app.processEvents()
        self.assertTrue(botao.isVisible())
        self.assertTrue(botao.isEnabled())
        self.assertFalse(botao.visibleRegion().isEmpty())
        posicao = botao.mapTo(janela, QPoint(0, 0))
        self.assertTrue(janela.rect().contains(posicao))
        self.assertLessEqual(posicao.y() + botao.height(), janela.height())
        self.assertLessEqual(posicao.x() + botao.width(), janela.width())

    def test_botoes_visiveis_e_clicaveis_na_resolucao_da_captura(self):
        acm = self.janela_aceleracao()
        self.assertLessEqual(acm.width(), 1330)
        self.assertLessEqual(acm.height(), 625)
        self.assertIn(VERSAO, acm.windowTitle())
        self.assertIn(str(Path('interface') / 'acelerometria.py'), acm.rotulo_versao.toolTip())
        self.verificar_botao_visivel(acm, acm.botao_velocidade)
        QTest.mouseClick(acm.botao_velocidade, Qt.MouseButton.LeftButton)
        self.assertEqual(len(acm.janelas_resultados), 1)
        vel = acm.janelas_resultados[0]
        self.janelas.append(vel)
        vel.resize(1330, 625)
        self.verificar_botao_visivel(vel, vel.botao_deslocamento)
        self.assertEqual(len(vel.checkboxes_canais), 12)
        QTest.mouseClick(vel.botao_deslocamento, Qt.MouseButton.LeftButton)
        self.assertEqual(len(vel.janelas_resultados), 1)
        desp = vel.janelas_resultados[0]
        self.janelas.append(desp)
        self.verificar_botao_visivel(desp, desp.exportar)
        for janela in (acm, vel, desp):
            self.assertTrue(janela.isVisible())
            self.assertIsNone(janela.parent())

    def test_fechar_origem_preserva_resultados_e_libera_janelas_fechadas(self):
        acm = self.janela_aceleracao(3)
        vel = acm.gerar_velocidade()
        desp = vel.gerar_deslocamento()
        self.janelas.extend([vel, desp])
        copia = desp.df_sensores.copy()
        acm.close()
        shiboken6.delete(acm)
        self.app.processEvents()
        self.assertTrue(vel.isVisible())
        self.assertTrue(desp.isVisible())
        vel.close()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertFalse(shiboken6.isValid(vel))
        self.assertTrue(desp.isVisible())
        pd.testing.assert_frame_equal(desp.df_sensores, copia)

    def test_sem_selecao_na_velocidade_e_exportacoes_sem_curvas(self):
        acm = self.janela_aceleracao(3)
        vel = acm.gerar_velocidade()
        self.janelas.append(vel)
        for checkbox in vel.checkboxes_canais.values():
            checkbox.setChecked(False)
        with patch.object(QMessageBox, 'information') as aviso, patch.object(QFileDialog, 'getExistingDirectory') as pasta:
            vel.botao_deslocamento.click()
            vel.exportar_svg()
            vel.exportar_html()
            self.assertEqual(aviso.call_count, 3)
            pasta.assert_not_called()
        self.assertEqual(vel.janelas_resultados, [])

    def test_falha_de_calculo_nao_altera_origem_ou_abre_janela(self):
        acm = self.janela_aceleracao(3)
        original = acm.df_sensores.copy()
        with patch('isq_dataanalysys.interface.acelerometria.integrar_relativo', side_effect=ValueError('Sinal inválido')):
            acm.botao_velocidade.click()
        self.assertEqual(acm.janelas_resultados, [])
        pd.testing.assert_frame_equal(acm.df_sensores, original)
        vel = acm.gerar_velocidade()
        self.janelas.append(vel)
        copia_vel = vel.df_sensores.copy()
        with patch('isq_dataanalysys.interface.integracao.integrar_relativo', side_effect=ValueError('Sinal inválido')):
            vel.botao_deslocamento.click()
        self.assertEqual(vel.janelas_resultados, [])
        pd.testing.assert_frame_equal(vel.df_sensores, copia_vel)
        self.assertEqual(self.aviso.call_count, 2)

    def test_exportacoes_preservam_valores_unidades_e_referencia_mesmo_sem_csv(self):
        from matplotlib.figure import Figure
        from plotly.graph_objects import Figure as FiguraHtml
        acm = self.janela_aceleracao(3)
        vel = acm.gerar_velocidade()
        desp = vel.gerar_deslocamento()
        self.janelas.extend([vel, desp])
        # A exportação deve funcionar com o CSV removido e manter StartTime UTC.
        acm.caminho_atual.unlink()
        self.app.processEvents()
        for janela, unidade in ((vel, 'mm/s'), (desp, 'mm')):
            janela.checkboxes_canais[2].setChecked(False)
            janela.checkboxes_canais[3].setChecked(False)
            janela.graficos_eixos['X'].setXRange(.2, .8, padding=0)
            self.app.processEvents()
            salvar_svg = Figure.savefig
            salvar_html = FiguraHtml.write_html

            def verificar_svg(fig, *args, **kwargs):
                self.assertIn('intervalo:', fig._suptitle.get_text())
                self.assertIn('= 0', fig._suptitle.get_text())
                self.assertIn(unidade, fig.axes[0].get_ylabel())
                self.assertEqual(sum(len(e.lines) for e in fig.axes), 1)
                np.testing.assert_array_equal(fig.axes[0].lines[0].get_ydata(), janela.df_sensores[1])
                esperados = np.datetime64('2026-10-28T09:00:00', 'us') + np.rint(janela.tempo * 1e6).astype('timedelta64[us]')
                np.testing.assert_array_equal(fig.axes[0].lines[0].get_xdata(), esperados)
                np.testing.assert_allclose(fig.axes[0].get_xlim(), mdates.date2num([
                    datetime(2026, 10, 28, 9, 0, 0, 200000), datetime(2026, 10, 28, 9, 0, 0, 800000)]), rtol=0, atol=1e-10)
                return salvar_svg(fig, *args, **kwargs)

            def verificar_html(fig, *args, **kwargs):
                self.assertIn('intervalo:', fig.layout.title.text)
                self.assertIn('= 0', fig.layout.title.text)
                self.assertEqual(len(fig.data), 1)
                self.assertIn(unidade, fig.layout.yaxis.title.text)
                np.testing.assert_array_equal(fig.data[0].y, janela.df_sensores[1])
                self.assertEqual(fig.data[0].x[0], '2026-10-28T09:00:00.000000')
                self.assertEqual(fig.layout.xaxis.range[0], '2026-10-28T09:00:00.200000')
                return salvar_html(fig, *args, **kwargs)

            with patch.object(QFileDialog, 'getExistingDirectory', return_value=self.tmp.name), patch.object(QMessageBox, 'information'):
                with patch.object(Figure, 'savefig', verificar_svg), patch.object(FiguraHtml, 'write_html', verificar_html):
                    janela.exportar_svg()
                    janela.exportar_html()
        self.aviso.assert_not_called()
        self.assertEqual(len(list(Path(self.tmp.name).glob('*.svg'))), 2)
        self.assertEqual(len(list(Path(self.tmp.name).glob('*.html'))), 2)
