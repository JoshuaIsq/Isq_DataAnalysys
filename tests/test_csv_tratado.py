"""Roundtrip de dados tratados, referências temporais e rejeição de corrupção."""
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from isq_dataanalysys.exportacao.csv_tratado import salvar_csv_tratado, ler_csv_tratado


class CsvTratadoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.caminho = Path(self.tmp.name)/'tratado.csv'
        self.tempo = np.array([2400., 2400.005, 2400.010])
        self.dados = pd.DataFrame({1: [np.pi, -0., np.nextafter(1., 2.)],
                                   '1': [1e-200, 1e200, -1.2345678901234567],
                                   9: [0.1, 0.2, 0.3]})
        self.canais = {1: dict(nome='ACC; "Y" — ação\nlinha', unidade='g', eixo='Y'),
                       '1': dict(nome='Mesmo nome', unidade='mm/s', eixo='Z'),
                       9: dict(nome='Mesmo nome', unidade='μm/m', eixo='Sem eixo')}
        self.inicio = datetime(2026, 10, 29, 1, 15, 12, 123456)

    def salvar(self, **extras):
        salvar_csv_tratado(self.caminho, self.tempo, self.dados, self.canais,
                           inicio_csv=extras.pop('inicio_csv', self.inicio), **extras)

    def linhas(self):
        with self.caminho.open(encoding='utf-8-sig', newline='') as arquivo:
            return list(csv.reader(arquivo, delimiter=';'))

    def gravar_linhas(self, linhas):
        with self.caminho.open('w', encoding='utf-8-sig', newline='') as arquivo:
            csv.writer(arquivo, delimiter=';', lineterminator='\n').writerows(linhas)

    def test_roundtrip_exato_float64_nomes_unidades_ids_e_metadados(self):
        metadados = {'descricao': 'Velocidade → integral, v₀ = 0',
                     'intervalo_original_s': [0, 7200], 'intervalo_avaliacao_s': [2400, 3600]}
        original = self.dados.copy(deep=True)
        self.salvar(metadados=metadados)
        resultado = ler_csv_tratado(self.caminho)
        np.testing.assert_array_equal(resultado.tempo.view('u8'), self.tempo.view('u8'))
        np.testing.assert_array_equal(resultado.dados.to_numpy().view('u8'), self.dados.to_numpy().view('u8'))
        self.assertEqual(list(resultado.dados), [1, '1', 9])
        self.assertEqual(resultado.canais, self.canais)
        self.assertEqual(resultado.inicio_csv, self.inicio)
        self.assertEqual(resultado.metadados, metadados)
        pd.testing.assert_frame_equal(self.dados, original)
        self.assertTrue(self.caminho.read_bytes().startswith(b'\xef\xbb\xbf'))
        self.assertIn('3,1415926535897931', self.caminho.read_text(encoding='utf-8-sig'))

    def test_timestamp_local_desconto_unico_e_reexportacao_sem_dupla_conversao(self):
        self.salvar()
        linhas = self.linhas()
        self.assertEqual(linhas[3][0], '2400')
        self.assertEqual(linhas[3][1], '2026-10-28T22:55:12.123456')
        self.assertEqual(linhas[4][1], '2026-10-28T22:55:12.128456')
        resultado = ler_csv_tratado(self.caminho)
        destino = Path(self.tmp.name)/'reexportado.csv'
        salvar_csv_tratado(destino, resultado.tempo, resultado.dados, resultado.canais,
                           resultado.inicio_csv, resultado.metadados)
        self.assertEqual(destino.read_bytes(), self.caminho.read_bytes())

    def test_sem_data_nao_inventa_timestamp_e_aceita_uma_amostra(self):
        salvar_csv_tratado(self.caminho, [3600.125], self.dados.iloc[:1], self.canais)
        resultado = ler_csv_tratado(self.caminho)
        self.assertIsNone(resultado.inicio_csv)
        self.assertEqual(resultado.tempo.tolist(), [3600.125])
        self.assertEqual(self.linhas()[3][1], '')

    def test_intervalos_irregulares_validos_para_rms(self):
        tempo = np.array([1., 1.5, 1.875])
        salvar_csv_tratado(self.caminho, tempo, self.dados, self.canais)
        np.testing.assert_array_equal(ler_csv_tratado(self.caminho).tempo, tempo)

    def test_registro_maior_com_numeros_aleatorios_preserva_todos_os_bits(self):
        rng = np.random.default_rng(572)
        tempo = 2400+np.arange(10001)/200
        dados = pd.DataFrame(rng.normal(size=(len(tempo),3)),columns=list(self.canais))
        salvar_csv_tratado(self.caminho,tempo,dados,self.canais,self.inicio)
        r = ler_csv_tratado(self.caminho)
        np.testing.assert_array_equal(r.tempo.view('u8'),tempo.view('u8'))
        np.testing.assert_array_equal(r.dados.to_numpy().view('u8'),dados.to_numpy().view('u8'))

    def test_validacao_de_entrada_nao_sobrescreve_arquivo(self):
        self.salvar()
        antes = self.caminho.read_bytes()
        casos = [([0, 0, 1], self.dados, self.canais),
                 ([0, 2, 1], self.dados, self.canais),
                 ([0, 1, np.inf], self.dados, self.canais),
                 ([], self.dados.iloc[:0], self.canais),
                 ([0, 1], self.dados, self.canais),
                 (self.tempo, self.dados.iloc[:, :2], self.canais),
                 (self.tempo, self.dados, {1: dict(nome='X', unidade='g')})]
        for t, dados, canais in casos:
            with self.subTest(tempo=t), self.assertRaises(ValueError):
                salvar_csv_tratado(self.caminho, t, dados, canais)
            self.assertEqual(self.caminho.read_bytes(), antes)
        for extras in ({'metadados': {'nao_finito': float('nan')}},
                       {'inicio_csv': datetime(2026, 1, 1, tzinfo=timezone.utc)}):
            with self.subTest(extras=extras), self.assertRaises(ValueError):
                self.salvar(**extras)
            self.assertEqual(self.caminho.read_bytes(), antes)
        self.assertFalse(list(Path(self.tmp.name).glob('*.tmp')))

    def test_rejeita_valores_nao_finitos_na_exportacao(self):
        for valor in (np.nan, np.inf, -np.inf):
            dados = self.dados.copy()
            dados.iloc[1, 1] = valor
            with self.subTest(valor=valor), self.assertRaises(ValueError):
                salvar_csv_tratado(self.caminho, self.tempo, dados, self.canais)
        self.assertFalse(self.caminho.exists())

    def test_rejeita_corruptos_assinatura_metadados_canais_e_linhas(self):
        self.salvar()
        original = self.linhas()
        mutacoes = [lambda x: x[0].__setitem__(1, '2'),
                    lambda x: x[1].__setitem__(1, '{errado'),
                    lambda x: x[2].__setitem__(2, 'coluna_errada'),
                    lambda x: x[3].pop(),
                    lambda x: x[3].__setitem__(2, 'NaN'),
                    lambda x: x[3].__setitem__(2, '1e999'),
                    lambda x: x[4].__setitem__(0, x[3][0]),
                    lambda x: x[3].__setitem__(1, '2026-10-28T19:55:12.123456'),
                    lambda x: x.__delitem__(slice(3, None))]
        for i, mutacao in enumerate(mutacoes):
            linhas = [linha.copy() for linha in original]
            mutacao(linhas)
            self.gravar_linhas(linhas)
            with self.subTest(mutacao=i), self.assertRaises(ValueError):
                ler_csv_tratado(self.caminho)
        for alteracao in ({'versao_formato': 2}, {'ajuste_horario_horas': 0},
                           {'inicio_csv': 'data inválida'}, {'metadados': []},
                           {'canais': []}):
            linhas = [linha.copy() for linha in original]
            meta = json.loads(linhas[1][1])
            meta.update(alteracao)
            linhas[1][1] = json.dumps(meta)
            self.gravar_linhas(linhas)
            with self.subTest(alteracao=alteracao), self.assertRaises(ValueError):
                ler_csv_tratado(self.caminho)

    def test_rejeita_timestamp_sem_referencia_e_csv_com_aspas_invalidas(self):
        self.salvar(inicio_csv=None)
        linhas = self.linhas()
        linhas[3][1] = '2026-10-28T22:55:12.123456'
        self.gravar_linhas(linhas)
        with self.assertRaisesRegex(ValueError, 'timestamp sem referência'):
            ler_csv_tratado(self.caminho)
        self.caminho.write_text('"aspas sem fechar', encoding='utf-8')
        with self.assertRaises(ValueError):
            ler_csv_tratado(self.caminho)

    def test_rejeita_identidade_repetida_ou_metadados_de_canal_incompletos(self):
        self.salvar()
        original = self.linhas()
        for caso in ('id_repetido', 'sem_unidade', 'id_booleano', 'coluna_repetida'):
            linhas = [linha.copy() for linha in original]
            meta = json.loads(linhas[1][1])
            if caso == 'id_repetido':
                meta['canais'][1]['id'] = 1
            elif caso == 'sem_unidade':
                del meta['canais'][1]['descricao']['unidade']
            elif caso == 'id_booleano':
                meta['canais'][1]['id'] = True
            else:
                meta['canais'][1]['coluna'] = 'canal_1'
            linhas[1][1] = json.dumps(meta)
            self.gravar_linhas(linhas)
            with self.subTest(caso=caso), self.assertRaises(ValueError):
                ler_csv_tratado(self.caminho)


if __name__ == '__main__':
    unittest.main()
