# Consolidar a instalação do Windows

## 1. Manter a pasta principal

Use como pasta principal a `Isq_DataAnalysys-git` que você já abriu no VS Code e que
contém o `.git`. A pasta `ISQ-atualizado-...` criada dentro dela durante o diagnóstico
é outro checkout; ela pode conter código, alterações e dados próprios.

Feche a aplicação. No terminal da pasta principal, confira e guarde alterações:

```powershell
git status --short
git diff --stat
git stash push -m "Backup local antes da reorganizacao"
git pull --ff-only origin main
```

Prossiga após a atualização concluir. Se houver conflito, erro de arquivos não
rastreados ou divergência de histórico, preserve a mensagem e resolva isso antes
de continuar. O backup fica em `git stash list`; `git stash show -p` permite revisá-lo.
Como os módulos foram movidos, mudanças antigas precisam ser comparadas com os novos
caminhos do [mapa de arquivos](ESTRUTURA.md) antes de reaplicar.

Confira a instalação e abra o programa:

```powershell
python .\main.py --diagnostico
python .\main.py
```

A revisão reorganizada é `2026.10.30.3`. O caminho do pacote no diagnóstico deve
ficar dentro da sua pasta principal. Abra essa mesma pasta no VS Code; o ponto de
entrada continua sendo `main.py`.

## 2. Arquivar a cópia aninhada preservando tudo

Primeiro obtenha o inventário, sem mudar os arquivos:

```powershell
python .\tools\consolidar_copias.py
```

A ferramenta lista somente diretórios `ISQ-atualizado-*` imediatamente dentro do
projeto que sejam clones Git completos de `JoshuaIsq/Isq_DataAnalysys`. Ela mostra
a revisão e indica se há alterações locais. Links, worktrees e outros repositórios
ficam fora da ação. ZIPs sem `.git` também não são movidos automaticamente.

Para arquivar as cópias listadas:

```powershell
python .\tools\consolidar_copias.py --arquivar
```

Elas serão movidas para `ISQ-copias-arquivadas`, ao lado da pasta principal.
O conteúdo completo é preservado, inclusive `.git`, CSVs, arquivos ignorados,
arquivos não rastreados e alterações locais. A ferramenta não executa `git clean`,
`reset --hard` ou exclusão permanente. No Windows, feche arquivos/processos da cópia
se o sistema impedir movê-la.

Depois do arquivamento, extraia das cópias quaisquer medições ou alterações de
código que ainda precise. Guarde os CSVs desejados em `dados/` ou em sua pasta de
medições e os SVGs/HTMLs em `exportacoes/`. A aplicação abre e salva em outras pastas
também. A exclusão definitiva do arquivo pode ser feita após essa conferência.

## 3. Rotina daqui em diante

- Abra sempre a pasta principal no VS Code.
- Inicie por `python .\main.py`.
- Atualize por `git pull --ff-only origin main` após revisar alterações locais.
- Use branches e commits para versões de trabalho.
- Mantenha dados, exportações e backups fora do histórico do código.

`__pycache__` e os arquivos `.pyc` são caches regeneráveis; já estão ignorados.
Eles podem reaparecer ao executar Python. A pasta `work/` usada no desenvolvimento
também é ignorada e não é necessária para rodar a aplicação.
