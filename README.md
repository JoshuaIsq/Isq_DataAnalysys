# ISQ DataAnalysys

Análise de CSVs Lynx de acelerometria e extensometria. A aplicação mantém as
correções de CSV/codificação, filtros, FFT/RMS, integrações temporais e exportações
SVG/HTML.

## Abrir a aplicação

Na raiz deste repositório, com o interpretador que contém as dependências:

```powershell
python .\main.py
```

Escolha **Lynx → Acelerometria** ou **Lynx → Extensometria**. Acelerometria mantém
**Gerar velocidade** na faixa azul e **Gerar deslocamento** na janela de velocidade.

Para identificar a instalação aberta:

```powershell
python .\main.py --diagnostico
```

A tela inicial também oferece **Sobre esta instalação**. A versão e o caminho
exibidos vêm do mesmo pacote usado pelas telas e pelos cálculos.

### Data e hora da medição

Os gráficos temporais de acelerometria, RMS, extensometria, velocidade e
deslocamento usam o horário inicial do CSV com **redução fixa de três horas**,
somado ao tempo de cada amostra. Exemplo: `28/10/2026 15:55` no CSV aparece como
`28/10/2026 12:55`. As exportações SVG e HTML seguem a mesma referência e o mesmo
intervalo visível. A FFT continua com frequência em Hz.

O ajuste independe do fuso do computador. Os cálculos usam os segundos originais;
o CSV e os valores medidos são preservados. Sem uma data inicial válida, o eixo
continua em segundos. Veja os [formatos e regras da referência temporal](docs/CSV_LYNX.md).

### CSVs com canais fora de ordem

A acelerometria aceita sensores incompletos, eixos fora de ordem e nomes/eixos
repetidos. Cada coluna em `g` permanece um canal independente: dois canais Y
com o mesmo nome são plotados em Y, sem sobrescrever dados ou exigir um trio.
Canais sem eixo identificável aparecem em **Sem eixo** e também permitem filtros,
FFT/RMS, velocidade, deslocamento e exportação. Nomes vazios recebem um rótulo
pela posição da coluna. Os avisos da importação ficam disponíveis na tela.

Arquivos legados sem indicação de nenhum eixo e com trios completos mantêm
X/Y/Z por posição, com indicação explícita de que os eixos foram inferidos.
Consulte as [regras de identificação dos canais](docs/CSV_LYNX.md).

### Passa-banda na acelerometria

Depois de abrir um CSV, clique em **Passa-banda…**. Preencha **Low cutoff — corte
inferior** e **High cutoff — corte superior**, em Hz, e clique em **Aplicar**.
Os cortes devem obedecer `0 < inferior < superior < frequência de amostragem / 2`.
Por exemplo, um arquivo de 200 Hz exige corte superior abaixo de 100 Hz.

O passa-banda é independente: não ativa passa-alta, passa-baixa nem outros
tratamentos. Os filtros existentes continuam disponíveis e só entram no cálculo
quando aplicados pelo usuário. Se já estavam ativos, permanecem ativos. Digitar
valores e cancelar não muda o sinal. Para retirar apenas esse filtro, reabra seu
botão e clique em **Desativar passa-banda**. **Restaurar original** e a importação
de outro arquivo limpam todos os tratamentos.

O processamento sempre parte dos dados originais, na ordem: calibração, outliers,
offset, passa-banda, passa-alta, passa-baixa e média móvel (somente os ativos).
RMS, FFT, integração e exportação usam o resultado tratado. A extensometria mantém
seus controles atuais e não ganha o botão passa-banda.

O cálculo usa Butterworth em SOS com `Processamento.ORDEM = 4` e aplicação em ida
e volta (`sosfiltfilt`). No projeto passa-banda do SciPy, esse parâmetro gera um
filtro de ordem 8 por passagem. Os cortes informados são os cortes do projeto de
uma passagem: aproximadamente −3 dB por passagem, ou −6 dB após ida e volta.
O filtro tem fase zero e pode apresentar transientes no início e no fim do sinal.

## Organização

```text
main.py                    # inicia a aplicação
pyproject.toml             # dependências, instalação e empacotamento
isq_dataanalysys/
  __init__.py              # única definição da versão
  aplicacao.py             # inicialização e diagnóstico
  interface/               # telas, controles e seleção de canais
  processamento/           # filtros, FFT/RMS e integrações
  leitores/                # CSV, codificação e metadados Lynx
  exportacao/              # renderização HTML e SVG
  recursos/                # logo e outros recursos da aplicação
tests/                     # testes e dados sintéticos
docs/                      # funcionamento e manutenção
tools/                     # manutenção do checkout
dados/                     # CSVs locais, ignorados pelo Git
exportacoes/               # SVGs/HTMLs locais, ignorados pelo Git
```

Os nomes antigos, como `tela_lynx_acm.py`, foram movidos para o pacote. Não é
necessário manter outra cópia desses módulos na raiz. Os imports usam o nome
completo do pacote, evitando carregar arquivos antigos com nomes semelhantes.

`__pycache__` é um cache gerado pelo Python, ignorado pelo Git. Ele pode reaparecer
após executar o programa e não representa outra versão dos fontes.

## Atualização e consolidação das cópias

Mantenha **um checkout principal** e use o histórico do Git para versões anteriores.
Na pasta principal:

```powershell
git pull --ff-only origin main
python .\main.py --diagnostico
```

Se o Git informar alterações locais, revise e guarde essas alterações antes de
atualizar. Consulte o [guia de migração](docs/MIGRACAO.md), com instruções para a
pasta `Isq_DataAnalysys-git` e a cópia `ISQ-atualizado-...` criada no diagnóstico.

Para listar cópias aninhadas sem modificar arquivos:

```powershell
python .\tools\consolidar_copias.py
```

Para movê-las completas para `ISQ-copias-arquivadas`, ao lado do projeto:

```powershell
python .\tools\consolidar_copias.py --arquivar
```

Esse comando reconhece clones `ISQ-atualizado-*` deste repositório e preserva todo
o conteúdo, incluindo `.git`, alterações locais, dados e arquivos ignorados.

## Instalação e desenvolvimento

As dependências estão declaradas em `pyproject.toml`. Em um interpretador preparado
para o projeto, a instalação para desenvolvimento é:

```powershell
python -m pip install -e .
```

O `main.py` também funciona sem instalar o projeto, quando as dependências já estão
disponíveis. Após instalar o pacote, o comando `isq-analise` inicia a mesma aplicação.
A configuração do ambiente cloud não faz parte do projeto.

## Testes e documentação

```powershell
python -m unittest discover -s tests -v
```

Os testes usam CSVs sintéticos e Qt sem monitor. Cobrem importação e codificação,
cálculos e unidades, filtros/FFT/RMS, seleção de canais, janelas, exportações, início
pelo `main.py`, isolamento de módulos antigos e preservação de dados na consolidação.

- [Responsabilidade de cada pasta e mapa dos arquivos movidos](docs/ESTRUTURA.md)
- [Migração da pasta atual e arquivamento das cópias](docs/MIGRACAO.md)
- [Importação de CSV Lynx](docs/CSV_LYNX.md)
- [Velocidade e deslocamento relativos](docs/INTEGRACAO_ACELEROMETRIA.md)
