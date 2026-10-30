"""CSVs sintéticos compartilhados pelos testes."""
import csv
import tempfile
from pathlib import Path
import numpy as np


class ArquivoMixin:
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.sequencia = 0

    def arquivo(self, unidades, nomes=None, decimal=',', alterar=None, encoding='utf-8-sig'):
        self.sequencia += 1
        nomes = nomes or [f'Sensor livre {n}' for n in range(1, len(unidades) + 1)]
        linhas = [
            ['Name'] + nomes + ['', 'SampFreq:', '1000Hz'],
            ['Unit'] + unidades + ['', 'StartTime UTC:', '2026/10/28 12:00:00'],
            ['HighLim'] + ['1000000'] * len(unidades),
            ['LowLim'] + ['-1000000'] * len(unidades),
            ['Time (s)'],
        ]
        for i in range(1000):
            valores = [i / 1000] + [n * np.sin(2 * np.pi * 50 * i / 1000) for n in range(1, len(unidades) + 1)]
            linhas.append([f'{valor:.9f}'.replace('.', decimal) for valor in valores])
        if alterar:
            alterar(linhas)
        caminho = Path(self.tmp.name) / f'dados_{self.sequencia}.csv'
        with caminho.open('w', encoding=encoding, newline='') as arquivo:
            csv.writer(arquivo, delimiter=';').writerows(linhas)
        return caminho
