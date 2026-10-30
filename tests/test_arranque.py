"""Abre o main.py real em outro processo e usa os botões da aplicação."""
import os
from pathlib import Path
import subprocess
import sys
import unittest
from tests.roteiro_arranque import ROTEIRO


class ArranqueTests(unittest.TestCase):
    def test_main_real_abre_os_tres_graficos_com_diferentes_escalas(self):
        raiz = Path(__file__).resolve().parents[1]
        for escala in ('1', '1.25', '1.5'):
            with self.subTest(escala=escala):
                ambiente = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_SCALE_FACTOR=escala,
                                PYTHONDONTWRITEBYTECODE='1')
                processo = subprocess.run(
                    [sys.executable, '-c', ROTEIRO, str(raiz)],
                    cwd=raiz, env=ambiente, capture_output=True, text=True, timeout=40,
                )
                self.assertEqual(processo.returncode, 0, processo.stdout + processo.stderr)
                self.assertIn('ARRANQUE_OK', processo.stdout)
