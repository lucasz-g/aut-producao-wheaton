# Validação da Fase 1 — Automação dos Relatórios Diários da Produção

**Data:** 16/09/2026
**Status:** entregue e em validação com a área (deploy em VM, cliente testando)
**Escopo de referência:** documento de escopo da Fase 1 (Produção)

---

## 1. Resumo

O objetivo central da Fase 1 — **gerar automaticamente o relatório diário com
dados de desempenho, gráficos e anotações do dia** — está **concluído** e rodando
na VM, em uso pela área.

O que mudou no processo: a consolidação manual das informações em um relatório
padronizado foi substituída por um fluxo de um clique. O que ainda não mudou: a
**entrada** dos dados continua manual (upload de dois Excel) e o **GCM** segue
fora do fluxo.

| Objetivo do escopo | Situação |
| --- | --- |
| Coleta automática de dados nos sistemas envolvidos | **Parcial** — a extração no BI ainda é manual; o app recebe os arquivos por upload |
| Processamento e interpretação de informações textuais | **Concluído** — anotações interpretadas por IA, com saída estruturada |
| Consolidação em relatório estruturado e formatado | **Concluído** — PDF padronizado com tabela, gráficos e linha do tempo |
| Dados de manutenção (GCM / Agente de Manutenção) | **Não iniciado** — previsto no escopo como proposta sujeita à validação da área |

---

## 2. O que está entregue

### 2.1 Aplicação

Aplicação web em **Streamlit** ([app.py](../app.py)), em container Docker, com
dois pontos de entrada e uma saída:

```
Excel de Produção  ─┐
                    ├─► processamento ─► IA (anotações) ─► PDF do relatório
Excel Bloco de Notas┘
```

**Etapas do fluxo:**

1. **Ingestão e normalização** — [utils/data_processor.py](../utils/data_processor.py)
   lê a planilha de produção e deriva dois conjuntos: desempenho **diário** por
   máquina/prefixo e desempenho **hora a hora**. O bloco de notas é normalizado
   (cabeçalho real na linha 2, colunas descartáveis removidas).

2. **Regra do dia Wheaton (06:00 → 05:59)** — implementada em
   `ordenar_notas_por_dia_wheaton` e `_ordem_do_evento`: as horas da madrugada
   ordenam **depois** das da noite, refletindo o fechamento real da área.
   É também a regra usada para ordenar prefixos por hora de troca
   (`ordenar_prefixos_por_troca`), o que identifica o **setup de máquina** — a
   "máquina em duas linhas" descrita no mapeamento do processo.

3. **Seleção do escopo do relatório** — `get_maquinas_abaixo_objetivo` filtra as
   máquinas em que `Emp - Rejeitado %` ficou abaixo de `Objetivo %`. O relatório
   cobre **apenas as máquinas abaixo do objetivo**, que é o foco da análise
   diária do Tallyson.

4. **Interpretação das anotações (IA)** —
   [utils/openai_integration.py](../utils/openai_integration.py) envia as
   anotações brutas ao **Azure OpenAI** (`gpt-4.1-mini`) com **`json_schema` em
   modo `strict`**. A saída é garantidamente estruturada: linha do tempo do turno
   (`hora` + `descricao`) e um resumo diário por máquina (`observacoes`). As
   instruções exigem a citação dos **defeitos** (siglas de 3 letras — LAP, RTE,
   RTR, TCT) e proíbem inventar dados ou horários fora do JSON de entrada.

5. **Gráficos** — [utils/graficos.py](../utils/graficos.py) exporta as figuras
   Plotly hora a hora como PNG em memória (via `kaleido` + Chromium do sistema),
   uma por máquina/prefixo, já ajustadas para impressão (fundo branco, legenda no
   rodapé).

6. **Relatório PDF** — [utils/pdf_processor.py](../utils/pdf_processor.py) monta
   o documento com ReportLab: tabela de desempenho, gráfico do prefixo, linha do
   tempo do turno e observações da máquina, com rodapé "Gerado em dd/mm/aaaa".
   Nada é gravado em disco — o PDF é devolvido pelo `st.download_button`.

### 2.2 Cobertura dos indicadores da área

Os quatro indicadores que abrem o dia do Tallyson estão no relatório:

| Indicador (mapeamento da área) | Onde aparece |
| --- | --- |
| Resultado da máquina (positivo/negativo vs. meta) | `Emp - Rejeitado %` comparado a `Objetivo %`, com destaque em cor |
| Objetivo diário (cotação) | Coluna `Objetivo %` |
| Quantidade empacotada | Coluna `Empacotado %` |
| Quantidade rejeitada | Coluna `Rejeição %` |
| Troca de prefixo / setup | Máquina desdobrada por prefixo, ordenada pela hora da troca |
| Comportamento hora a hora | Gráfico por prefixo, no app e no PDF |
| Ocorrências do Bloco de Notas | Linha do tempo + observações interpretadas |

Isso cobre os passos **1, 2 e 3** do mapeamento do processo (relatório do dia
anterior, dashboard hora a hora e bloco de notas) em uma única tela.

### 2.3 Infraestrutura

- **Container único**, sem banco e sem volume — o estado vive na sessão do
  Streamlit ([docker-compose.yml](../docker-compose.yml)).
- **Deploy na VM** (`68.154.1.107:8501`) por SSH, com
  [scripts/deploy.sh](../scripts/deploy.sh): `git merge --ff-only`, rebuild,
  `image prune` e espera do healthcheck — falha alto em vez de subir quebrado.
- **Segredos fora do repositório**: `.env` só na VM, listado no `.gitignore` e no
  `.dockerignore`; o compose falha no deploy se `AZURE_OPENAI_API_KEY` faltar.
- **Dados de produção fora da imagem**: `analytics/data/` no `.dockerignore`.
- **Timezone** `America/Sao_Paulo`, para a data do rodapé bater com a fábrica.
- Documentação operacional em [docs/deploy.md](deploy.md) e
  [docs/playbook-deploy.md](playbook-deploy.md).

---

## 3. O que não está no entregue

São lacunas **conhecidas e previstas**, não defeitos — mas precisam estar
explícitas para a validação da fase.

### 3.1 A extração dos dados ainda é manual

O escopo prevê "coleta automática de dados nos sistemas envolvidos". Hoje o
usuário exporta manualmente do BI as duas planilhas (Produção e Bloco de Notas) e
as sobe no app. O ganho de tempo está na **consolidação**, não na extração.

Fechar essa lacuna depende da integração com o MicroStrategy/EBS — o mesmo
movimento de arquitetura já em discussão com TI e BI.

### 3.2 GCM / Agente de Manutenção

Serviço realizado, tempo de atendimento e observações da manutenção continuam
sendo consultados manualmente no GCM. O escopo já registrava isso como proposta
sujeita à validação da área, e nada foi implementado nesta fase.

### 3.3 Escopo do relatório limitado às máquinas abaixo do objetivo

Decisão de produto alinhada ao uso real (o relatório existe para investigar o que
ficou abaixo da meta). Quando nenhuma máquina fica abaixo, o app informa e não
gera PDF. Se a área quiser um relatório completo do dia, é uma mudança pequena —
mas é mudança de escopo.

### 3.4 Pontos técnicos a acompanhar

| Ponto | Risco | Situação atual |
| --- | --- | --- |
| Gráficos dependem do Chromium na imagem | Se faltar, o PDF sai **sem gráficos e sem erro na tela** | Validação pós-deploy obrigatória: gerar um PDF e conferir os gráficos |
| Layout fixo dos Excel de entrada | Mudança no export do BI quebra a leitura | Erro é capturado e exibido na tela; não há validação de schema |
| Interpretação por IA | O conteúdo do resumo depende do modelo | `json_schema` strict garante a estrutura e as instruções proíbem inventar dados; a conferência do conteúdo é do usuário |
| Sem autenticação no app | Qualquer um com acesso à porta abre a aplicação | Exposição controlada pelo NSG; avaliar se basta |
| Redeploy automático no push | Hoje o deploy é manual via `deploy.sh` | Pipeline e cron já documentados, ainda não ativados |

---

## 4. Conclusão da validação

**A Fase 1 pode ser considerada entregue no seu objetivo central.** O relatório
diário padronizado — desempenho, gráficos e anotações interpretadas — é gerado
automaticamente, está publicado na VM e em teste pelo cliente.

Permanecem em aberto, para decisão da área e das próximas fases:

1. **Automatizar a extração** dos dados do MicroStrategy/EBS, eliminando o upload
   manual.
2. **Incorporar o GCM**, via Agente de Manutenção ou via integração na base
   analítica.
3. **Consolidar o feedback do teste em produção** e ajustar o conteúdo do
   relatório antes de fechar formalmente a fase.

Os itens 1 e 2 são exatamente o movimento de arquitetura descrito no escopo
(centralizar Vertech + GCM no MicroStrategy) e formam a base natural da Fase 2.
