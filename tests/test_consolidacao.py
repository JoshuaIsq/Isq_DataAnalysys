"""Consolidação de clones completos, preservando dados e alterações locais."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools.consolidar_copias import listar_copias, arquivar_copias, main, mesmo_repositorio


class ConsolidacaoTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.raiz = Path(tmp.name) / 'principal'
        self.raiz.mkdir()
        (self.raiz / 'main.py').write_text('# entrada\n')
        (self.raiz / 'isq_dataanalysys').mkdir()

    def criar_copia(self, nome='ISQ-atualizado-20261030-111753', remoto='https://github.com/JoshuaIsq/Isq_DataAnalysys.git'):
        copia = self.raiz / nome
        copia.mkdir()
        def git(*args):
            return subprocess.run(['git', '-C', str(copia), *args], check=True, capture_output=True)
        git('init', '-b', 'main')
        git('remote', 'add', 'origin', remoto)
        (copia / 'main.py').write_text('# código original\n')
        (copia / '.gitignore').write_text('dados/\n')
        git('add', '.')
        git('-c', 'user.name=Teste', '-c', 'user.email=teste@example.invalid', 'commit', '-m', 'inicial')
        return copia

    def test_consulta_nao_move_arquivos_e_identifica_alteracoes(self):
        copia = self.criar_copia()
        (copia / 'main.py').write_text('# alteração local\n')
        self.assertEqual(main(['--raiz', str(self.raiz)]), 0)
        self.assertTrue(copia.exists())
        self.assertFalse((self.raiz.parent / 'ISQ-copias-arquivadas').exists())
        copias = listar_copias(self.raiz)
        self.assertEqual(len(copias), 1)
        self.assertTrue(copias[0].alterada)

    def test_arquivamento_preserva_git_csv_ignorado_e_arquivo_nao_rastreado(self):
        copia = self.criar_copia()
        (copia / 'main.py').write_text('# alteração local\n')
        (copia / 'notas.txt').write_bytes(b'nao rastreado')
        (copia / 'dados').mkdir()
        (copia / 'dados/medicao.csv').write_bytes(b'Tens\xe3o;\xb5m/m\r\n')
        antes = {p.relative_to(copia): p.read_bytes() for p in copia.rglob('*') if p.is_file()}
        destinos = arquivar_copias(self.raiz, listar_copias(self.raiz))
        self.assertEqual(len(destinos), 1)
        self.assertFalse(copia.exists())
        self.assertEqual(destinos[0].parent, self.raiz.parent / 'ISQ-copias-arquivadas')
        depois = {p.relative_to(destinos[0]): p.read_bytes() for p in destinos[0].rglob('*') if p.is_file()}
        self.assertEqual(antes, depois)
        status = subprocess.check_output(['git', '-C', str(destinos[0]), 'status', '--porcelain'], text=True)
        self.assertIn('main.py', status)
        self.assertIn('notas.txt', status)
        self.assertTrue((self.raiz / 'main.py').exists())

    def test_outro_repositorio_e_outras_pastas_ficam_no_lugar(self):
        outro = self.criar_copia(remoto='https://github.com/OutraOrg/OutroRepo.git')
        (self.raiz / 'dados').mkdir()
        self.assertEqual(listar_copias(self.raiz), [])
        self.assertEqual(arquivar_copias(self.raiz, []), [])
        self.assertTrue(outro.exists())
        self.assertTrue((self.raiz / 'dados').exists())

    def test_link_para_fora_do_projeto_e_ignorado(self):
        destino = self.raiz.parent / 'externa'
        destino.mkdir()
        try:
            (self.raiz / 'ISQ-atualizado-link').symlink_to(destino, target_is_directory=True)
        except OSError:
            self.skipTest('O sistema não permite criar links de diretório.')
        self.assertEqual(listar_copias(self.raiz), [])
        self.assertTrue(destino.exists())

    def test_destino_externo_por_link_e_recusado(self):
        copia = self.criar_copia()
        externa = self.raiz.parent / 'externa'
        externa.mkdir()
        try:
            (self.raiz.parent / 'ISQ-copias-arquivadas').symlink_to(externa, target_is_directory=True)
        except OSError:
            self.skipTest('O sistema não permite criar links de diretório.')
        with self.assertRaises(ValueError):
            arquivar_copias(self.raiz, listar_copias(self.raiz))
        self.assertTrue(copia.exists())

    def test_clone_removido_entre_consulta_e_acao_e_recusado(self):
        copia = self.criar_copia()
        inventario = listar_copias(self.raiz)
        subprocess.run(['git', '-C', str(copia), 'remote', 'remove', 'origin'], check=True)
        with self.assertRaises(ValueError):
            arquivar_copias(self.raiz, inventario)
        self.assertTrue(copia.exists())

    def test_identidade_do_repositorio_por_https_e_ssh(self):
        self.assertTrue(mesmo_repositorio('https://github.com/JoshuaIsq/Isq_DataAnalysys.git'))
        self.assertTrue(mesmo_repositorio('git@github.com:JoshuaIsq/Isq_DataAnalysys.git'))
        self.assertFalse(mesmo_repositorio('https://outro.exemplo/JoshuaIsq/Isq_DataAnalysys.git'))

    def test_arquivo_aberto_informa_destinos_ja_movidos_sem_perder_as_copias(self):
        primeira = self.criar_copia('ISQ-atualizado-1')
        segunda = self.criar_copia('ISQ-atualizado-2')
        rename_original = Path.rename
        def mover(caminho, destino):
            if caminho == segunda:
                raise PermissionError('Arquivo aberto no Windows')
            return rename_original(caminho, destino)
        with patch.object(Path, 'rename', mover):
            with self.assertRaisesRegex(OSError, 'Cópias já arquivadas:') as erro:
                arquivar_copias(self.raiz, listar_copias(self.raiz))
        destino = self.raiz.parent / 'ISQ-copias-arquivadas'
        movida = next(destino.iterdir())
        self.assertIn(str(movida), str(erro.exception))
        self.assertTrue((movida / '.git').is_dir())
        self.assertTrue(segunda.exists())
        self.assertFalse(primeira.exists())
