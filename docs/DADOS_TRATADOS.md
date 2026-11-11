# Intervalo de avaliação e dados tratados

## Comparar um trecho da gravação

Nas janelas de aceleração, velocidade e deslocamento, preencha **Avaliar de** e
**até**, em **minutos desde o início da gravação**, e clique em **Aplicar intervalo**.
Por exemplo, `40` e `60` mostram os dados entre 40 e 60 minutos. Os campos
respeitam os limites disponíveis; o início precisa ser menor que o fim.
**Intervalo completo** restaura a gravação inteira.

As janelas derivadas herdam o intervalo visual da origem. O ajuste altera somente
a visualização e a exportação: **não recorta o sinal usado na integração nem muda
as condições iniciais**. Os cálculos de aceleração, velocidade e deslocamento
continuam os mesmos. FFT usa frequência e desabilita o controle temporal; RMS
continua permitindo selecionar um trecho no tempo.

Extensometria e régua também usam minutos nos campos de tempo existentes,
mantendo os controles de escala vertical. O processamento armazena os segundos
originais. Quando o CSV contém StartTime reconhecido, os gráficos mostram data e
hora local (horário original menos três horas), mesmo com os campos em minutos.

## HTML e SVG

Os gráficos exportados preservam o intervalo e a escala visíveis. O HTML apresenta
data e hora em cada eixo X temporal e no cursor; também informa o tempo em segundos
ao passar o mouse sobre uma curva. As amostras completas permanecem no HTML para
permitir ampliar a análise interativa. O HTML é autocontido, sem depender de internet.

Sem data inicial reconhecida, os eixos continuam em tempo decorrido. Nesse caso,
use **Definir horário…** na janela Lynx para informar o horário original do CSV
antes de gerar resultados e exportações. O programa não inventa timestamps.

## Exportar CSV tratado

Escolha **Exportar → CSV tratado**. O arquivo inclui:

- Somente os canais visíveis e as amostras dentro do intervalo de avaliação.
- Valores tratados, com a unidade efetivamente exibida: g, mm/s, mm, MPa,
  μm/m, mm/m ou RMS em mg. A escala logarítmica não transforma os números do CSV.
- Tempo original em segundos e timestamp local, quando a origem temporal existe.
- Identidade, nome, unidade e eixo de cada canal, preservando nomes repetidos.
- Método e tratamentos registrados na janela, origem temporal original e intervalo.

Não há interpolação dos limites do recorte: são exportadas as amostras existentes
entre os dois limites, inclusive as que coincidirem com eles. A representação
numérica preserva os valores float64 na leitura pelo aplicativo. O CSV não zera
o tempo do recorte: um trecho iniciado em 40 minutos continua começando perto de
2400 segundos. O arquivo de origem não é sobrescrito.

CSV tratado é uma exportação temporal. Para usá-la na acelerometria, desative FFT;
o modo RMS temporal é aceito. HTML e SVG continuam disponíveis para FFT.

## Reabrir

Na tela inicial, escolha **Dados tratados → Abrir CSV tratado**. A janela aceita
o formato exportado pelo programa, oferece seleção de canais, campos de intervalo
em minutos e novas exportações SVG, HTML e CSV.

Valores, unidades e referência temporal são lidos diretamente; **não são aplicados
novamente filtros, calibração, retirada de média ou integrações**. A redução de
três horas também não é aplicada duas vezes. Um CSV de 40–60 minutos reabre com
essa mesma posição na gravação.

Essa entrada fornece a reabertura necessária e uma base para a futura área de
análise de dados tratados, sem mudar os cálculos de integração nesta revisão.

## Formato para manutenção

O arquivo é UTF-8 com BOM, separado por ponto e vírgula, com vírgula decimal.
Começa com `# ISQ_DADOS_TRATADOS;1`, seguido de uma linha `# METADADOS` com JSON.
O cabeçalho de dados contém `tempo_s`, `timestamp_local` e colunas `canal_1`, etc.
Nomes/unidades/IDs constam nos metadados ordenados. O timestamp usa ISO 8601;
sem data original, essa coluna fica vazia.

O leitor valida a versão, colunas, canais, números, tempo crescente e consistência
dos timestamps. Identidades repetidas e linhas incompletas são rejeitadas. O
formato não exige amostragem uniforme, permitindo resultados temporais de RMS.
