# Importação de CSV Lynx

O arquivo usa `;` como separador e ponto ou vírgula como separador decimal.
São aceitos UTF-8 (com ou sem BOM), UTF-16 com BOM e ANSI/Windows-1252,
comum nas exportações Windows que usam `µm/m`. A leitura reconhece o BOM;
na ausência dele, valida UTF-8 e usa Windows-1252 quando necessário, preservando
nomes acentuados e o símbolo `µ`. O CSV original não é convertido nem regravado.
As cinco linhas iniciais são `Name`, `Unit`, `HighLim`,
`LowLim` e `Time (s)`. As medições começam na sexta linha.

A coluna A contém o tempo em segundos. A coluna B corresponde ao canal 1,
C ao canal 2, e assim por diante. Cada nome está na primeira linha e sua unidade
na segunda, na mesma coluna. Os nomes são livres, inclusive repetidos.
O programa identifica o canal pela posição, preservando sua numeração ao filtrar.
Um nome vazio recebe o rótulo `Canal N (sem nome)`, com aviso; ele não encerra a
leitura nem elimina os canais seguintes. Os valores e o CSV original são preservados.
Campos de metadados, como `SampFreq:`, podem aparecer após os canais.

| Opção de análise | Unidades importadas |
| --- | --- |
| Extensometria: Tensão | `MPa` |
| Extensometria: Deformação | `μm/m`, `µm/m`, `um/m`, `mm/m` |
| Acelerometria | `g` ou `G` |

As grafias de microdeformação são normalizadas para `μm/m`. A capitalização e
espaços das unidades reconhecidas são normalizados. `mm` indica deslocamento,
e fica fora das duas análises, assim como unidades ausentes ou desconhecidas.

Ao importar um arquivo com outras unidades, um aviso lista os canais ignorados
com posição, nome e unidade. Eles não entram nos gráficos, filtros, FFT ou RMS
da análise escolhida. Se nenhum canal for compatível, a importação é recusada
e o arquivo que já estava aberto é preservado.

## Canais de acelerometria fora de ordem

Não é necessário ordenar as colunas nem completar trios. Cada coluna em `g`
é importada uma única vez, mesmo com nomes repetidos, sensores incompletos ou
outras unidades entre os canais. A associação funciona assim:

- Um único X, Y ou Z isolado no nome identifica o eixo. São aceitos, por exemplo,
  `ACC 92128 - Y`, `ACC_92128_y`, `ACC 92128 [Y]`, `ACC92128Y`, `Y - ACC 92128` e
  `ACC 92128 - Eixo Y (g)`.
- Os canais de um sensor podem estar intercalados ou em qualquer ordem.
- Dois canais chamados `ACC 92131 - Y` continuam sendo dois canais Y distintos,
  identificados pelas posições no arquivo. O segundo não sobrescreve o primeiro
  nem vira X/Z para completar um trio.
- Um canal sem eixo identificável aparece em **Sem eixo**. Nomes conflitantes,
  como `ACC X Y`, também entram nesse painel. Eles continuam disponíveis para
  filtros, FFT/RMS, velocidade, deslocamento e exportações SVG/HTML.
- Somente para compatibilidade com arquivos antigos sem nenhuma indicação de eixo,
  uma quantidade múltipla de três mantém o padrão X/Y/Z por posição. A interface
  identifica esses grupos como **XYZ por posição** e avisa que a associação é
  inferida. Essa alternativa não substitui eixos reconhecidos nem resolve nomes
  com indicações conflitantes.

A faixa de avisos abaixo dos controles informa a quantidade de avisos. Passe o
mouse sobre ela para consultar nomes repetidos, eixos ausentes, associações
inferidas e outros avisos da importação. A seleção continua sendo individual
por canal, inclusive para canais com nomes iguais. As janelas de resultados
mantêm a mesma associação e os dados da origem permanecem preservados.

Essa tolerância trata a identificação e a organização dos canais. Unidades e
dados numéricos ainda precisam ser interpretáveis: o programa não inventa eixos,
valores, unidades ou instantes para contornar dados inválidos. A inferência
posicional de arquivos legados é sempre indicada explicitamente.

## Analisar tensão e deformação

1. Abra o CSV na opção Lynx / Extensometria.
2. Confira o aviso de canais de outra medição, quando houver.
3. Use **Tensão (MPa)** ou **Deformação**. Cada botão fica disponível se houver
   canais dessa grandeza no CSV. A lista e a legenda mostram quais canais
   pertencem ao modo atual.
4. Na deformação, escolha `μm/m` ou `mm/m`. A conversão visual é
   `1 mm/m = 1000 μm/m`; os dados originais são preservados.
5. Marque os canais que deseja analisar. Ajuste **Escala mínima/máxima** e
   **Tempo inicial/final** e clique em **Aplicar escala e tempo**.
6. Use **Ajustar aos dados** para visualizar novamente todo o intervalo e ajustar
   a escala aos canais selecionados.

Cada unidade de visualização mantém sua escala e intervalo ao alternar modos.
Esses limites controlam a vista e são preservados nas exportações SVG e HTML.
Os filtros continuam sendo calculados sobre todo o registro, e a exportação
contém os dados completos dos canais visíveis, com a vista inicialmente escolhida.

O programa usa os valores de tensão e deformação presentes no CSV. A troca de
modo não calcula tensão a partir de deformação: essa operação exigiria um modelo
e propriedades do material, que não fazem parte desta importação.

## Data e hora local nos gráficos e nas exportações

A referência é o campo `StartTime UTC` ou `StartTime` do cabeçalho. O leitor aceita
datas com ano primeiro (`2026/10/28`, `2026-10-28`) ou dia primeiro (`28/10/2026`,
`28-10-2026`), seguidas de horas/minutos, segundos opcionais e frações de segundo.
Também aceita o separador `T` de datas ISO e ponto ou vírgula nas frações.

O horário de apresentação obedece à regra fixa da placa:

```text
data/hora local = data/hora inicial registrada − 3 horas + tempo da amostra em segundos
```

Assim, `28/10/2026 15:55` no CSV começa em `28/10/2026 12:55` na tela e nas
exportações. Às `01:00` do CSV, o início local será `22:00` do dia anterior.
O ajuste também trata mudanças de mês/ano. Ele é fixo e não depende do fuso ou
horário de verão do computador. O rótulo **Data/Hora local (CSV − 3 h)** identifica
essa referência, inclusive nos valores consultados no HTML.

Essa apresentação é compartilhada por acelerometria, RMS, extensometria,
velocidade e deslocamento. A FFT mantém frequência em Hz. O zoom e as escalas
são preservados no SVG e no HTML; o HTML inclui todas as amostras selecionadas,
com a vista inicial correspondente ao zoom. O horário é capturado na importação,
de modo que a exportação continue coerente mesmo se o arquivo for movido ou apagado.

Os vetores temporais, os filtros, as janelas RMS, as integrações e as condições
iniciais continuam sendo calculados em segundos, sem aplicar a redução de horas
aos dados numéricos. O CSV não é regravado. Os campos de recorte temporal da
extensometria continuam recebendo segundos relativos à referência inicial do CSV.
Se a data inicial estiver ausente ou inválida, a leitura dos sinais continua e
o eixo permanece em segundos, sem atribuir uma data presumida.

A amostragem deve ser regular e crescente. Valores ausentes, não numéricos ou
não finitos nos canais importados são recusados. Uma última linha incompleta
nesses canais pode ser ignorada mediante confirmação. Lacunas no meio do
registro continuam sendo erros. O CSV original não é regravado.

## Verificações automatizadas

Com as dependências do aplicativo instaladas, na raiz do repositório:

```bash
PYTHONDONTWRITEBYTECODE=1 QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v
```

A suíte utiliza CSVs sintéticos e abre as telas sem monitor. Ela verifica seleção
por unidade/posição, nomes livres e repetidos, arquivos inválidos, avisos,
reimportação, modos e escalas, filtros, FFT/RMS e exportações SVG/HTML.
