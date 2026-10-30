"""Verifica os pontos de entrada e o isolamento em relação aos módulos antigos."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from isq_dataanalysys import __version__
from tests.roteiro_arranque import ROTEIRO


class OrganizacaoTests(unittest.TestCase):
    RAIZ = Path(__file__).resolve().parents[1]

    def executar(self, args, pasta):
        ambiente = dict(os.environ, QT_QPA_PLATFORM='offscreen', PYTHONDONTWRITEBYTECODE='1')
        return subprocess.run([sys.executable, *args], cwd=pasta, env=ambiente,
                              capture_output=True, text=True, timeout=40)

    def test_importar_main_nao_abre_aplicacao_nem_importa_qt(self):
        p = self.executar(['-c', "import sys; import main; assert 'PySide6' not in sys.modules; print('IMPORT_OK')"], self.RAIZ)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('IMPORT_OK', p.stdout)

    def test_main_diagnostico_funciona_fora_da_pasta_sem_dependencias(self):
        with tempfile.TemporaryDirectory() as pasta:
            p = self.executar(['-S', str(self.RAIZ / 'main.py'), '--diagnostico'], pasta)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn(__version__, p.stdout)
        self.assertIn(str(self.RAIZ / 'isq_dataanalysys'), p.stdout)

    def test_entrada_por_modulo_usa_mesma_versao(self):
        p = self.executar(['-m', 'isq_dataanalysys', '--diagnostico'], self.RAIZ)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn(__version__, p.stdout)

    def test_fontes_antigos_na_raiz_nao_substituem_os_modulos_do_pacote(self):
        with tempfile.TemporaryDirectory() as pasta:
            projeto = Path(pasta) / 'projeto'
            projeto.mkdir()
            shutil.copy2(self.RAIZ / 'main.py', projeto / 'main.py')
            shutil.copytree(self.RAIZ / 'isq_dataanalysys', projeto / 'isq_dataanalysys', ignore=shutil.ignore_patterns('__pycache__'))
            for nome in ('tela_lynx_acm.py', 'tela_lynx_ext.py', 'tela.py', 'versao.py', 'processamento.py'):
                (projeto / nome).write_text("raise RuntimeError('Fonte antiga carregada')\n", encoding='utf-8')
            # A janela inicial real, seu logo e as duas integrações são abertos.
            p = self.executar(['-c', ROTEIRO, str(projeto)], Path(pasta))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('ARRANQUE_OK', p.stdout)
