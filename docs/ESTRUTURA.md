# Estrutura e manutenção

## Responsabilidades

| Pasta/arquivo | Responsabilidade |
| --- | --- |
| `main.py` | Iniciar a aplicação; não cria janelas quando importado. |
| `isq_dataanalysys/aplicacao.py` | Preparar a aplicação Qt e mostrar o diagnóstico da instalação. |
| `interface/` | Telas, controles, seleção de canais e diálogos de arquivo. |
| `processamento/` | Cálculos sobre sinais temporais, sem dependência das telas. |
| `leitores/` | Validar CSVs e interpretar codificação, canais, unidades e metadados. |
| `exportacao/` | Renderizar as curvas selecionadas em SVG/HTML. |
| `recursos/` | Recursos distribuídos com a aplicação, incluindo o logo. |
| `tests/` | Regressões e geradores de CSVs sintéticos compartilhados. |
| `tools/` | Manutenção local, separada dos cálculos e da aplicação instalada. |
| `dados/` e `exportacoes/` | Arquivos locais de trabalho, ignorados pelo Git. |

Os caminhos `interface/`, `processamento/`, `leitores/`, `exportacao/` e `recursos/`
ficam dentro de `isq_dataanalysys/`. O código de processamento não importa a
interface; os leitores validam os sinais e a interface coordena leitura,
processamento e exportação.

Na referência temporal, `leitores/metadados.py` interpreta o horário original do
CSV; `processamento/tempo.py` centraliza a redução fixa de três horas e a conversão
para datas; `interface/eixo_temporal.py` formata os eixos das telas. SVG e HTML
usam a mesma conversão, preservando os segundos usados pelos cálculos.
`interface/referencia_temporal.py` apresenta o horário reconhecido, os detalhes da
leitura e a definição manual; a classe base coordena a atualização dos eixos e da
referência de exportação sem modificar os sinais.

Na régua potenciométrica, `leitores/regua.py` seleciona os canais em `mm` e
`interface/regua.py` apresenta os deslocamentos medidos. Os filtros continuam no
processamento comum. `interface/visualizacao_temporal.py` compartilha os controles
de escala e intervalo entre régua e extensometria, preservando o funcionamento
dos modos de tensão/deformação.

## Mapa da reorganização

| Arquivo anterior | Local atual |
| --- | --- |
| `tela.py` | `isq_dataanalysys/interface/base.py` |
| `tela_lynx_acm.py` | `isq_dataanalysys/interface/acelerometria.py` |
| `tela_lynx_ext.py` | `isq_dataanalysys/interface/extensometria.py` |
| `tela_integracao.py` | `isq_dataanalysys/interface/integracao.py` |
| `controle_filtros.py` | `isq_dataanalysys/interface/controles.py` |
| `processamento.py` | `isq_dataanalysys/processamento/sinais.py` |
| `integracao.py` | `isq_dataanalysys/processamento/integracao.py` |
| `leitor_lynx.py` | `isq_dataanalysys/leitores/lynx.py` |
| `leitor_lynx_acm.py` | `isq_dataanalysys/leitores/acelerometria.py` |
| `leitor_lynx_ext.py` | `isq_dataanalysys/leitores/extensometria.py` |
| `codificacao_csv.py` | `isq_dataanalysys/leitores/codificacao.py` |
| `exportacao_html.py` | `isq_dataanalysys/exportacao/html.py` |
| Renderização SVG dentro de `tela.py` | `isq_dataanalysys/exportacao/svg.py` |
| Leitura da data dentro de `exportacao_html.py` | `isq_dataanalysys/leitores/metadados.py` |
| `logo_isq.png` | `isq_dataanalysys/recursos/logo_isq.png` |
| `versao.py` | `__version__` em `isq_dataanalysys/__init__.py` |

O antigo `teste.py` era um iniciador de tela genérica e foi removido. Os testes
reais permanecem em `tests/`. Os menus Aeron, National e ISQ da tela inicial não
tinham implementação nem ações conectadas e foram removidos. As análises Lynx
implementadas foram preservadas.

## Versionamento

A versão tem uma única definição: `isq_dataanalysys.__version__`. O título das
janelas, o diagnóstico e a versão do pacote instalado usam esse mesmo valor.
`pyproject.toml` lê o atributo; não mantém outra cópia do número.

O repositório mantém o histórico de todas as alterações. Para consultar uma versão
anterior, use `git log` e `git show`; evite criar cópias do projeto dentro dele.
Antes de mudanças próprias, use uma branch. Arquivos de medição, exportações,
caches, ambientes virtuais e artefatos de build não devem entrar nos commits.

Para novas funcionalidades: coloque os cálculos em `processamento/`, o formato de
entrada em `leitores/` e a tela em `interface/`. Acrescente os testes correspondentes
em `tests/` e documente o comportamento em `docs/`.

## Fluxo de cinemática a partir de 2026.11.13.1

- `processamento/cinematica.py`: conversão ×9810, Sum[Xdt], ajustes de grau 1/2 e estatísticas.
- `interface/cinematica.py`: janelas de velocidade/posição, tabela de estatísticas e banda independente da posição. Reutiliza `dados_tratados.py` para gráficos, horários e exportações.
- `processamento/sinais.py`: filtros existentes, FFT de amplitude e PSD unilateral.
- `scripts/auditar_cinematica.py`: auditoria numérica reproduzível com um CSV local.
- `integracao.py` em processamento/interface: funções e janela históricas, mantidas para compatibilidade. A acelerometria não usa mais esse cálculo antigo.
