# ISQ DataAnalysys

Análise de CSVs Lynx de acelerometria, extensometria e régua potenciométrica. A aplicação mantém as
correções de CSV/codificação, filtros, FFT/PSD/RMS, integrações temporais e exportações
SVG/HTML.

## Abrir a aplicação

Na raiz deste repositório, com o interpretador que contém as dependências:

```powershell
python .\main.py
```

Escolha **Lynx → Acelerometria**, **Extensometria** ou **Régua potenciométrica**. Acelerometria mantém
**Gerar velocidade** no bloco Processamento de Sinal e **Gerar deslocamento** na janela de velocidade.

Para identificar a instalação aberta:

```powershell
python .\main.py --diagnostico
```

A tela inicial também oferece **Sobre esta instalação**. A versão e o caminho
exibidos vêm do mesmo pacote usado pelas telas e pelos cálculos.

### Data e hora da medição

Os gráficos temporais de acelerometria, RMS, extensometria, régua, velocidade e
deslocamento usam o horário inicial do CSV com **redução fixa de três horas**,
somado ao tempo de cada amostra. Exemplo: `28/10/2026 15:55` no CSV aparece como
`28/10/2026 12:55`. As exportações SVG e HTML seguem a mesma referência e o mesmo
intervalo visível. A FFT continua com frequência em Hz.

Após importar, o painel **Início CSV → local** confirma o horário utilizado.
Na acelerometria e na régua, **Detalhes do horário** mostra o campo e o valor
lidos, e **Definir horário…** permite informar o horário original do CSV; o
desconto de três horas continua automático. O ajuste manual vale para a janela
atual, suas exportações e os novos resultados gerados a partir dela.
A extensometria usa somente o horário lido do CSV, sem esses dois botões.

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

### Régua potenciométrica

Abra **Lynx → Régua potenciométrica** para importar os canais cuja unidade é `mm`.
A janela aceita um ou vários canais em qualquer posição do CSV, inclusive junto
de canais em `g`, `MPa`, `μm/m` e `mm/m`, que permanecem nas respectivas análises.
Nomes repetidos e posições originais são preservados, como o canal 16 de um CSV misto.

O gráfico apresenta o deslocamento medido em mm, inclusive valores negativos,
com seleção de canais, calibração, offset, remoção de outliers, passa-alta,
passa-baixa e média móvel. A janela também permite ajustar escala/intervalo,
restaurar o original e exportar SVG/HTML com a referência de data/hora local.
O valor inicial é preservado; o Offset só é aplicado quando solicitado.
Veja o [guia da régua potenciométrica](docs/REGUA_POTENCIOMETRICA.md).

### Interface da acelerometria

Na versão **2026.11.12.3**, os gráficos ocupam toda a altura da área à direita.
A barra estreita à esquerda alterna duas páginas no mesmo painel lateral:

- **Ícone de pasta — Controles:** Arquivo e Dados, Filtros e Tratamento,
  Processamento de Sinal, Visualização e Escala.
- **Segundo ícone — Canais:** seleção dos sensores/eixos, avisos de importação
  e referência de horário do CSV.

Somente o painel lateral muda. Os dados, filtros, canais marcados e zoom dos
gráficos são preservados. Em janelas baixas, a lateral tem rolagem para alcançar
todos os controles. O ícone de informação junto a **Gerar velocidade** explica
o método de cálculo. O fluxo de integração foi atualizado na versão **2026.11.13.1**.

### Passa-banda na acelerometria

Na revisão **2026.11.12.2**, a acelerometria apresenta apenas **Offset** e
**Passa-banda** como controles de tratamento, além de FFT, PSD, RMS, conversão de unidade e Gerar velocidade.
Calibração, outliers, média móvel, passa-alta e passa-baixa continuam disponíveis
nas telas de extensometria e régua.

Os campos **Low cutoff** e **High cutoff** ficam no bloco **Filtros e Tratamento**
da página Controles. Depois de abrir o CSV, preencha os dois cortes em Hz e clique em
**Aplicar** no bloco Passa-banda. Use `0 < inferior < superior < fs / 2`.
Por exemplo, um arquivo de 200 Hz exige corte superior abaixo de 100 Hz.
Digitar valores não aplica o filtro. Cortes inválidos preservam o último sinal
tratado e exibem um aviso. **Desativar** retira somente a banda, preservando o
Offset. **Restaurar original** e importar outro CSV limpam os tratamentos.
O processamento parte sempre do original: Offset, depois Passa-banda.
RMS, FFT/PSD, integração e exportação usam o resultado tratado.

**Escala mínima**, **máxima**, **Tempo inicial (min)** e **final** usam o mesmo
layout da extensometria. **Aplicar escala e tempo** aplica a mesma escala vertical
a todos os eixos e limita a vista ao trecho escolhido. **Ajustar aos dados**
restaura o intervalo completo e calcula a escala pelos canais selecionados.
A escala é lembrada separadamente por modo e unidade: g, mm/s², FFT, PSD e RMS.
Os limites do RMS logarítmico são digitados na unidade exibida e devem ser positivos.
Em FFT/PSD, somente os campos de tempo ficam desabilitados. Voltar ao tempo preserva
o intervalo anteriormente escolhido. Esses controles não recortam os cálculos de
integração nem alteram as amostras; as janelas derivadas herdam o intervalo.

O cálculo usa Butterworth em SOS com `Processamento.ORDEM = 4` e aplicação em ida
e volta (`sosfiltfilt`). No projeto passa-banda do SciPy, esse parâmetro gera um
filtro de ordem 8 por passagem. Os cortes informados são os cortes do projeto de
uma passagem: aproximadamente −3 dB por passagem, ou −6 dB após ida e volta.
O filtro tem fase zero e pode apresentar transientes no início e no fim do sinal.

### Velocidade e posição — 2026.11.13.1

1. Aplique o **Passa-banda** e consulte **FFT** (amplitude em g) ou **PSD** (g²/Hz).
2. Clique **Converter g → mm/s² (×9810)**: atualiza o sinal temporal e suas unidades.
3. **Gerar velocidade** integra por soma X·dt e subtrai a reta ajustada à velocidade.
4. Na janela de velocidade, **Visualizar estatísticas** mostra RMS total, máximo e
   mínimo por canal no intervalo selecionado.
5. **Obter posição** integra a velocidade corrigida e subtrai o ajuste de **grau 2**.
6. Na posição, há um **Passa-banda** adicional opcional, com **Aplicar** e **Desativar**.

Cada arquivo é um segmento independente. Os ajustes são feitos **após** integrar;
não há retirada automática da média da aceleração. A banda da posição não altera
a aceleração nem a velocidade já abertas, e reaplicar não acumula filtros.
Veja o [passo a passo, fórmulas e validação](docs/INTEGRACAO_ACELEROMETRIA.md).

### Intervalo em minutos e CSV tratado

A revisão **2026.11.11.1** permite avaliar um trecho em minutos nas janelas
temporais, inclusive aceleração, velocidade e deslocamento. Por exemplo,
**40 até 60 min → Aplicar intervalo** nas janelas de resultados; na acelerometria,
use **Tempo inicial/final → Aplicar escala e tempo**. As novas janelas herdam o recorte visual;
os cálculos de integração permanecem sobre o sinal completo.

**Exportar → CSV tratado** salva canais selecionados e amostras do intervalo,
com unidades, metadados e timestamp. Na tela inicial, **Dados tratados** reabre
esses arquivos sem reaplicar tratamentos ou alterar a referência temporal.
O HTML preserva o intervalo visível e mostra data/hora em cada eixo temporal
quando o arquivo de origem possui horário reconhecido.
Veja o [guia de intervalos, exportação e reabertura](docs/DADOS_TRATADOS.md).

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
- [Régua potenciométrica e deslocamento medido em mm](docs/REGUA_POTENCIOMETRICA.md)
- [Velocidade e deslocamento relativos](docs/INTEGRACAO_ACELEROMETRIA.md)
