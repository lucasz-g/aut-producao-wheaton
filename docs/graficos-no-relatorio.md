# Gráficos das máquinas no relatório PDF

Os gráficos de desempenho hora a hora passaram a ser anexados ao relatório,
por prefixo, entre a tabela de desempenho e a linha do tempo do turno.

## Como funciona

O Plotly exporta a figura como PNG em memória (`figura.to_image`, via
`kaleido`) e o ReportLab a insere no PDF a partir de um `BytesIO` — não há
arquivo intermediário em disco.

```
app.py
  └─ utils/graficos.gerar_graficos_por_prefixo(desempenho_hora_hora, maquinas)
       → {"10": {"MB -1398-S": b"...png"}}
  └─ utils/pdf_processor.gerar_pdf_resumo_anotacoes(json_interpretado, graficos)
```

As chaves são as mesmas do JSON do relatório (máquina → prefixo), então o PDF
só precisa consultar por máquina e prefixo.

## Alterações

| Arquivo | O que mudou |
| --- | --- |
| `utils/graficos.py` | **Novo.** Exporta as figuras como PNG; reusa `gerar_grafico_desempenho_hora_hora`. |
| `utils/pdf_processor.py` | `gerar_pdf_resumo_anotacoes` ganhou o parâmetro opcional `graficos`; novo `_blocos_grafico`. |
| `app.py` | Chama a geração dos gráficos e guarda o resultado em `session_state["graficos_relatorio"]`. |
| `utils/data_processor.py` | Cores das linhas do gráfico em constantes (`COR_LINHA_DESEMPENHO`, `COR_LINHA_OBJETIVO`). |

## Detalhes

- **Dependência:** `kaleido` (já em `requirements.txt`). O Kaleido 1.x usa o
  Chrome do sistema; se a exportação falhar, rode `kaleido_get_chrome`.
- **Tolerante a falha:** máquina/prefixo sem dados hora a hora, ou cuja
  exportação falhe, é omitido — o relatório é gerado sem aquele gráfico.
- **Layout:** a imagem respeita a proporção original e tem altura máxima de
  8,5 cm (`ALTURA_MAXIMA_GRAFICO`). Gráfico e rótulo da linha do tempo ficam
  em um `KeepTogether`, o que evita gráfico cortado ao custo de eventual
  espaço em branco no fim da página.
- **Ajustes da versão impressa** (`_preparar_para_impressao`): fundo branco,
  sem título (o PDF já traz o seu) e legenda no rodapé. A figura exibida na
  tela não é alterada — a função trabalha sobre uma cópia.
- **Compatibilidade:** `graficos` é opcional; chamadas sem ele continuam
  gerando o PDF como antes.
