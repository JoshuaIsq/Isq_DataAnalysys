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

Na acelerometria, os canais em `g` formam trios X, Y, Z na ordem em que aparecem
no CSV, depois da seleção pela unidade. A quantidade de acelerômetros é variável.
Um trio incompleto é recusado: confira a ordem e as unidades no arquivo.

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
