"""Ajuste linear somente na posição e conferência temporal por derivação."""
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from isq_dataanalysys.processamento.integracao import (
    G_PADRAO_MM_S2, corrigir_rampa_deslocamento, derivar_deslocamento,
    integrar_relativo,
)


class CorrecaoRampaTests(unittest.TestCase):
    def test_rampas_multiplos_canais_unidades_e_origem_preservada(self):
        t = np.arange(2001) / 8 + 1000
        r = t-t[0]
        dados = pd.DataFrame({4: 7+3*r, 11: -9-.5*r}, index=np.arange(len(t))+17)
        dados.columns.name = 'canal'
        original = dados.copy(deep=True)
        corrigido, ajustes = corrigir_rampa_deslocamento(t, dados)
        np.testing.assert_allclose(corrigido, 0, atol=5e-12)
        np.testing.assert_allclose(ajustes['intercepto_mm'], [7,-9], atol=1e-12)
        np.testing.assert_allclose(ajustes['inclinacao_mm_s'], [3,-.5], atol=1e-12)
        self.assertEqual(list(ajustes.columns), ['intercepto_mm','inclinacao_mm_s'])
        self.assertTrue(ajustes.index.equals(dados.columns))
        self.assertTrue(corrigido.index.equals(dados.index))
        self.assertTrue(corrigido.columns.equals(dados.columns))
        self.assertFalse(np.shares_memory(corrigido.to_numpy(), dados.to_numpy()))
        pd.testing.assert_frame_equal(dados, original)

    def test_ajuste_discreto_conhecido_nao_forca_inicio_zero(self):
        t = np.arange(2001) / 8
        # Em ciclos completos, o cosseno tem média discreta 1/N e inclinação zero.
        oscilacao = .3*np.cos(2*np.pi*.5*t)
        dados = pd.DataFrame({8: 5+2*t+oscilacao})
        corrigido, ajustes = corrigir_rampa_deslocamento(t, dados)
        np.testing.assert_allclose(corrigido[8], oscilacao-oscilacao.mean(), atol=1e-11)
        self.assertAlmostEqual(ajustes.loc[8,'intercepto_mm'], 5+oscilacao.mean(), places=10)
        self.assertAlmostEqual(ajustes.loc[8,'inclinacao_mm_s'], 2, places=11)
        self.assertNotAlmostEqual(corrigido.iloc[0,0], 0, places=3)

    def test_reta_centrada_ortogonalidade_dos_residuos(self):
        t = np.linspace(0,50000,10001)
        y = .3*np.sin(t/83) + 1e6 + .002*t
        d = pd.DataFrame({1:y,5:-2*y})
        c, ajustes = corrigir_rampa_deslocamento(t,d)
        r = t.astype(np.longdouble)
        x = r-r.mean()
        valores = d.to_numpy(dtype=np.longdouble)
        inclinacao = (x[:,None]*valores).sum(axis=0)/(x*x).sum()
        intercepto = valores.mean(axis=0)-inclinacao*r.mean()
        esperado = valores-intercepto-r[:,None]*inclinacao
        np.testing.assert_allclose(c, np.asarray(esperado,dtype=float), atol=3e-9)
        np.testing.assert_allclose(ajustes['inclinacao_mm_s'], inclinacao, atol=1e-13)
        np.testing.assert_allclose(ajustes['intercepto_mm'], intercepto, atol=3e-9)

    def test_tempo_absoluto_deslocado_nao_altera_ajuste(self):
        t = np.arange(2001)/8
        d = pd.DataFrame({1: 10+.03*t+.5*np.cos(2*np.pi*.25*t)})
        c1,a1 = corrigir_rampa_deslocamento(t,d)
        c2,a2 = corrigir_rampa_deslocamento(t+1_000_000,d)
        pd.testing.assert_frame_equal(c1,c2)
        pd.testing.assert_frame_equal(a1,a2)

    def test_duas_amostras_bastam_para_ajustar_reta(self):
        c,a = corrigir_rampa_deslocamento([10,12],pd.DataFrame({1:[3.,7.]}))
        np.testing.assert_allclose(c,0,atol=1e-13)
        np.testing.assert_allclose(a.loc[1], [3,2],atol=1e-13)

    def test_parabola_preserva_aceleracao_real(self):
        t = np.arange(81)/8
        d = pd.DataFrame({1: .5*G_PADRAO_MM_S2*t*t+7*t+3})
        c, _ = corrigir_rampa_deslocamento(t,d)
        _,a = derivar_deslocamento(t,c)
        np.testing.assert_allclose(a[1],1,atol=3e-12)
        self.assertGreater(c[1].std(),1000)

    def test_derivadas_unidades_e_condicoes_iniciais_nao_impostas(self):
        t = np.arange(33)/8+100
        r = t-t[0]
        d = pd.DataFrame({3: .5*2*r*r+5*r+7, 8: -.5*3*r*r-2*r-9}, index=np.arange(len(t))+19)
        original = d.copy(deep=True)
        v,a = derivar_deslocamento(t,d)
        np.testing.assert_allclose(v[3],2*r+5,atol=1e-12)
        np.testing.assert_allclose(v[8],-3*r-2,atol=1e-12)
        np.testing.assert_allclose(a[3],2/G_PADRAO_MM_S2,atol=1e-14)
        np.testing.assert_allclose(a[8],-3/G_PADRAO_MM_S2,atol=1e-14)
        self.assertEqual(v.iloc[0,0],5)
        for resultado in (v,a):
            self.assertTrue(resultado.index.equals(d.index))
            self.assertTrue(resultado.columns.equals(d.columns))
            self.assertFalse(np.shares_memory(resultado.to_numpy(),d.to_numpy()))
        pd.testing.assert_frame_equal(d,original)

    def test_subtrair_reta_preserva_segunda_derivada_e_muda_primeira_por_constante(self):
        t = np.arange(4001)/200
        d = pd.DataFrame({1: .3*np.cos(2*np.pi*3*t)+4+.02*t,
                          2: .1*np.sin(2*np.pi*5*t)-2-.05*t})
        c,ajustes = corrigir_rampa_deslocamento(t,d)
        v0,a0 = derivar_deslocamento(t,d)
        v1,a1 = derivar_deslocamento(t,c)
        for canal in d:
            np.testing.assert_allclose(v1[canal],v0[canal]-ajustes.loc[canal,'inclinacao_mm_s'],atol=1e-10)
        np.testing.assert_allclose(a1,a0,atol=1e-10)

    def test_trapezios_e_derivadas_nao_sao_inversos_exatos(self):
        fs = 200
        t = np.arange(4001)/fs
        for f in (1,5,20,30):
            with self.subTest(f_hz=f):
                entrada = pd.DataFrame({1: .001*np.cos(2*np.pi*f*t)})
                v = integrar_relativo(t,entrada,'aceleracao')
                d = integrar_relativo(t,v,'velocidade')
                c,_ = corrigir_rampa_deslocamento(t,d)
                _,a = derivar_deslocamento(t,c)
                # Solução fechada no interior: cada integração+derivação tem ganho cos²(πf/fs).
                ganho = np.cos(np.pi*f/fs)**4
                np.testing.assert_allclose(a[1].iloc[2:-2], entrada[1].iloc[2:-2]*ganho, atol=1e-10)
                if f==30:
                    self.assertLess(ganho,.64)

    def test_dados_invalidos_e_derivacao_curta(self):
        for t,y in [([0],[1]),([0,0,1],[1,2,3]),([0,1,3],[1,2,3]),([0,1,2],[1,np.nan,3])]:
            for funcao in (corrigir_rampa_deslocamento,derivar_deslocamento):
                with self.subTest(funcao=funcao.__name__,t=t),self.assertRaises(ValueError):
                    funcao(t,pd.DataFrame({1:y}))
        with self.assertRaisesRegex(ValueError,'3 amostras'):
            derivar_deslocamento([0,1],pd.DataFrame({1:[0.,1.]}))

    def test_erros_numericos_sao_reportados(self):
        t = [0,1,2]
        d = pd.DataFrame({1:[0.,1.,3.]})
        with patch('isq_dataanalysys.processamento.integracao.np.linalg.lstsq',side_effect=np.linalg.LinAlgError):
            with self.assertRaisesRegex(ValueError,'Não foi possível corrigir a rampa'):
                corrigir_rampa_deslocamento(t,d)
        with self.assertRaisesRegex(ValueError,'Não foi possível derivar'):
            derivar_deslocamento(t,pd.DataFrame({1:[1e308,-1e308,1e308]}))


if __name__ == '__main__':
    unittest.main()
