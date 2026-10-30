"""Lista clones de diagnóstico aninhados; arquiva o conteúdo completo se solicitado."""
import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import subprocess
from urllib.parse import urlsplit


REPOSITORIO = 'joshuaisq/isq_dataanalysys'


@dataclass(frozen=True)
class Copia:
    caminho: Path
    alterada: bool
    revisao: str


def git(pasta, *args):
    return subprocess.check_output(
        ['git', '-C', str(pasta), *args], stderr=subprocess.DEVNULL,
        text=True, encoding='utf-8', errors='replace',
    ).strip()


def mesmo_repositorio(url):
    if url.startswith('git@github.com:'):
        projeto = url.split(':', 1)[1]
    else:
        partes = urlsplit(url)
        if partes.hostname != 'github.com':
            return False
        projeto = partes.path.lstrip('/')
    return projeto.removesuffix('.git').rstrip('/').casefold() == REPOSITORIO


def listar_copias(raiz):
    raiz = Path(raiz).resolve()
    copias = []
    for pasta in sorted(raiz.iterdir()):
        if not pasta.name.casefold().startswith('isq-atualizado-'):
            continue
        # Evita junctions, links e worktrees cujo Git dependa de outro caminho.
        if pasta.is_symlink() or not pasta.is_dir() or pasta.resolve() != pasta:
            continue
        if not (pasta / '.git').is_dir() or (pasta / '.git').is_symlink():
            continue
        try:
            if not mesmo_repositorio(git(pasta, 'remote', 'get-url', 'origin')):
                continue
            if Path(git(pasta, 'rev-parse', '--show-toplevel')).resolve() != pasta.resolve():
                continue
            alterada = bool(git(pasta, 'status', '--porcelain', '--untracked-files=all'))
            revisao = git(pasta, 'rev-parse', '--short', 'HEAD')
        except (subprocess.CalledProcessError, OSError, ValueError):
            continue
        copias.append(Copia(pasta, alterada, revisao))
    return copias


def arquivar_copias(raiz, copias):
    raiz = Path(raiz).resolve()
    # Revalida os candidatos antes de mover. Nenhum arquivo é apagado.
    permitidas = {c.caminho for c in listar_copias(raiz)}
    for copia in copias:
        if copia.caminho not in permitidas:
            raise ValueError(f'Cópia não reconhecida: {copia.caminho.name}')
    if not copias:
        return []
    destino = raiz.parent / 'ISQ-copias-arquivadas'
    if destino.is_symlink() or destino.resolve() != destino:
        raise ValueError('O destino de arquivamento deve ficar ao lado do projeto.')
    destino.mkdir(exist_ok=True)
    movidas = []
    for copia in copias:
        nome = f'{copia.caminho.name}-{datetime.now().astimezone():%Y%m%d-%H%M%S-%f}'
        arquivo = destino / nome
        try:
            copia.caminho.rename(arquivo)
        except OSError as erro:
            realizadas = ', '.join(map(str, movidas)) or 'nenhuma'
            raise OSError(f'{erro}. Cópias já arquivadas: {realizadas}') from erro
        movidas.append(arquivo)
    return movidas


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raiz', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--arquivar', action='store_true', help='Move as cópias completas para uma pasta ao lado do projeto')
    args = parser.parse_args(argv)
    raiz = args.raiz.resolve()
    if not (raiz / 'main.py').is_file() or not (raiz / 'isq_dataanalysys').is_dir():
        parser.error('Escolha a raiz do projeto reorganizado, onde ficam main.py e isq_dataanalysys/.')
    print(f'Projeto mantido: {raiz}')
    try:
        copias = listar_copias(raiz)
        if not copias:
            print('Nenhum clone de diagnóstico aninhado foi encontrado.')
            return 0
        for copia in copias:
            estado = 'com alterações locais' if copia.alterada else 'sem alterações no Git'
            print(f'{copia.caminho.name}: {copia.revisao}, {estado}')
        if args.arquivar:
            for pasta in arquivar_copias(raiz, copias):
                print(f'Cópia completa arquivada em: {pasta}')
        else:
            print('Somente consulta. Para arquivar essas cópias completas, use --arquivar.')
    except (OSError, ValueError) as erro:
        parser.exit(1, f'Não foi possível concluir o arquivamento: {erro}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
