"""Referências analíticas e discretas independentes para o fluxo por segmento."""
import unittest
import numpy as np
import pandas as pd

from isq_dataanalysys.processamento.cinematica import (
    converter_aceleracao, integrar_segmento, retirar_ajuste, estatisticas,
)
from isq_dataanalysys.processamento.sinais import Processamento


class CinematicaTests(unittest.TestCase):
    def test_unidades_primeira_amostra_e_segmentos_independentes(self):
        t = [10, 10.5, 11, 11.5]
        g = pd.DataFrame({7: [1., -2., 3., 4.], 9: [0., 0., 0., 0.]}, index=[4,5,6,7])
        original = g.copy()
        a = converter_aceleracao(t, g)
        v = integrar_segmento(t, a)
        d = integrar_segmento(t, v)
        np.testing.assert_allclose(a[7], [9810, -19620, 29430, 39240])
        np.testing.assert_allclose(v[7], [4905, -4905, 9810, 29430])
        np.testing.assert_allclose(d[7], [2452.5, 0, 4905, 19620])
        np.testing.assert_array_equal(v[9], 0)
        pd.testing.assert_frame_equal(integrar_segmento(np.array(t)+100, a), v)
        pd.testing.assert_frame_equal(g, original)
        self.assertEqual(list(v.index), [4,5,6,7])

    def test_senoide_solucao_discreta_da_soma_geometrica(self):
        fs = 200
        n = np.arange(5000)
        for f in (1, 5, 30, 70):
            theta = 2*np.pi*f/fs
            a = pd.DataFrame({1: np.cos(n*theta)})
            esperado = np.sin((n+1)*theta/2)*np.cos(n*theta/2)/np.sin(theta/2)/fs
            np.testing.assert_allclose(integrar_segmento(n/fs, a)[1], esperado, atol=1e-12)

    def test_ajuste_linear_e_quadratico_com_residuo_ortogonal_conhecido(self):
        # Discreta terceira diferença: ortogonal a 1,t,t²; deve sobreviver ao ajuste.
        residuo = np.array([-1., 3., -3., 1.])
        t = np.arange(4, dtype=float)
        for grau, tendencia in ((1, 4+2*t), (2, 4+2*t+3*t*t)):
            entrada = pd.DataFrame({4: tendencia+residuo, 8: -2*(tendencia+residuo)})
            copia = entrada.copy()
            saida, coef = retirar_ajuste(t+1700000000, entrada, grau)
            np.testing.assert_allclose(saida[4], residuo, atol=1e-13)
            np.testing.assert_allclose(saida[8], -2*residuo, atol=1e-13)
            np.testing.assert_allclose(coef.loc[4], [4,2,3][:grau+1], atol=1e-13)
            pd.testing.assert_frame_equal(entrada, copia)

    def test_derivada_retorna_sinal_ajustado_e_nao_promete_aceleracao_original(self):
        t = np.arange(6, dtype=float)
        a = pd.DataFrame({1: 2+t})
        bruto = integrar_segmento(t, a)
        v, ajustes_v = retirar_ajuste(t, bruto, 1)
        # Inversa da soma por diferenças (não gradient/trapézios).
        np.testing.assert_allclose(np.diff(bruto[1]), a[1].iloc[1:])
        np.testing.assert_allclose(np.diff(v[1]), a[1].iloc[1:]-ajustes_v.loc[1,'c1'], atol=1e-12)
        dbruto = integrar_segmento(t, v)
        d, ajustes_d = retirar_ajuste(t, dbruto, 2)
        np.testing.assert_allclose(np.diff(d[1], n=2),
            a[1].iloc[2:]-ajustes_v.loc[1,'c1']-2*ajustes_d.loc[1,'c2'], atol=1e-12)

    def test_registro_longo_e_tempo_deslocado(self):
        t = np.arange(0, 18001, .2)
        dados = pd.DataFrame({1: 4+2*t+.001*t*t+np.sin(t)})
        r, coef = retirar_ajuste(t, dados, 2)
        r2, _ = retirar_ajuste(t+1000000, dados, 2)
        np.testing.assert_allclose(r, r2, atol=2e-7)
        self.assertLess(float(np.max(np.abs(r))), 1.01)
        self.assertAlmostEqual(coef.loc[1,'c2'], .001, places=10)

    def test_estatisticas_rms_total_com_dc_e_sinais(self):
        r = estatisticas(pd.DataFrame({1:[3.,-4.,0.],2:[10.,10.,10.],3:[0.,0.,0.]}))
        np.testing.assert_allclose(r.loc[1], [np.sqrt(25/3),3,-4])
        np.testing.assert_allclose(r.loc[2], [10,10,10])
        np.testing.assert_array_equal(r.loc[3], 0)
        self.assertAlmostEqual(estatisticas(pd.DataFrame({1:[1e300,1e300]})).loc[1,'RMS']/1e300,1)

    def test_rejeita_irregular_nan_infinito_poucos_pontos_e_overflow(self):
        for t, a in (([0,1,3],[1.,2.,3.]), ([0,0,1],[1.,2.,3.]),
                     ([0,1,2],[1.,np.nan,3.]), ([0],[1.])):
            for func in (integrar_segmento, converter_aceleracao):
                with self.assertRaises(ValueError): func(t, pd.DataFrame({1:a}))
        with self.assertRaises(ValueError): converter_aceleracao([0,1],pd.DataFrame({1:[1e308,1e308]}))
        with self.assertRaises(ValueError): integrar_segmento([0,10],pd.DataFrame({1:[1e308,1e308]}))
        with self.assertRaises(ValueError): retirar_ajuste([0,1,2],pd.DataFrame({1:[1,2,3]}),2)
        with self.assertRaises(ValueError): estatisticas(pd.DataFrame())


class EspectrosTests(unittest.TestCase):
    def test_fft_amplitude_e_psd_densidade_com_dc_e_parseval(self):
        fs = 200
        for n in (1000, 1001):
            t = np.arange(n)/fs
            f = 25*fs/n
            a = pd.DataFrame({1: 3+2*np.sin(2*np.pi*f*t), 4: 7+4*np.sin(2*np.pi*f*t)})
            freq, fft, _ = Processamento.fft_ac(t, a)
            freq2, psd, info = Processamento.psd_ac(t, a)
            np.testing.assert_array_equal(freq, freq2)
            np.testing.assert_allclose(fft.iloc[25], [2,4], atol=1e-12)
            np.testing.assert_allclose(psd.iloc[25], np.array([2,8])/(fs/n), atol=1e-12)
            np.testing.assert_allclose(psd.sum()*info['resolucao_hz'], [2,8], atol=1e-12)
            np.testing.assert_allclose(psd.iloc[0], 0, atol=1e-24)

    def test_nyquist_nao_e_duplicado(self):
        t = np.arange(1000)/200
        a = pd.DataFrame({1: 3*(-1.)**np.arange(len(t))})
        _, fft, _ = Processamento.fft_ac(t, a)
        _, psd, info = Processamento.psd_ac(t, a)
        self.assertAlmostEqual(fft.iloc[-1,0], 3)
        self.assertAlmostEqual(psd.iloc[-1,0]*info['resolucao_hz'], 9)
