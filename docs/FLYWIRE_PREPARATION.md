# Preparação dos dados FlyWire

## Estado atual

O código já tem a infraestrutura de integração:

- `backend/app/providers/flywire.py` normaliza um subgrafo JSON;
- `backend/app/services/network.py` só retorna dados reais;
- `backend/app/simulation.py` contém o motor LIF local;
- `FLYWIRE_GRAPH_URL` e `FLYWIRE_DATA_FILE` estão preparados;
- o frontend já tem a fase Axobug e um TODO para o grafo real.

O backend **não deve apontar diretamente para o download bruto de 15 GB**.
O adapter atual trabalha com JSON limitado e protege o processo com
`MAX_REMOTE_BYTES`. Isso é intencional: o FastAPI não deve carregar o
conectoma inteiro na memória.

## Download já realizado

O arquivo atual é o download do produto de skeletons do Codex para o dataset
**FAFB v783 (CB)**:

```text
/home/mindwill/Downloads/sk_lod1_783_healed.zip
```

A inspeção local confirmou:

- aproximadamente 13 GB;
- 139.273 entradas, todas com extensão `.swc`;
- um arquivo por root ID, com pontos 3D, raio e relação `parent`;
- cabeçalho SWC com coordenadas em nanômetros;
- nenhum arquivo de conexões ou anotações dentro deste ZIP.

A página do Codex para [FAFB v783](https://codex.flywire.ai/?dataset=fafb)
informa 139.255 neurônios e 3.732.460 conexões. A diferença de 18 entradas
deve ser reconciliada com os metadados oficiais; não devemos assumir uma
correspondência de um para um antes de cruzar o ZIP com a tabela de
neurônios.

## 1. Guardar o download fora do Git

O `.gitignore` já ignora `data/`, CSV, TSV, arquivos comprimidos e formatos
scientificos grandes. Use, por exemplo:

```text
/home/mindwill/Documentos/mosca/data/flywire/
```

Não envie esses arquivos para o GitHub.

## Transição do Axobug para o FlyWire

A substituição planejada é:

```text
Axobug (fase atual)
        ↓
skeletons FAFB v783 + conexões + anotações
        ↓
grafo local por root ID
        ↓
simulação LIF local
        ↓
spikes e comportamento
```

Até existirem conexões e metadados do mesmo snapshot, a API Axobug continua
sendo a fonte de comportamento para não quebrar o Shadow Run. Ela será uma
fonte de comparação, não o cérebro definitivo do NaMosca. O projeto não
deve fabricar neurônios para preencher a lacuna.

## Dados já baixados

Além do ZIP de skeletons, foram baixados:

```text
/home/mindwill/Downloads/connections_princeton_no_threshold.csv.gz
/home/mindwill/Downloads/consolidated_cell_types.csv.gz
/home/mindwill/Downloads/neurons.csv.gz
```

Os schemas reais são:

```text
connections_princeton_no_threshold.csv.gz
pre_root_id, post_root_id, neuropil, syn_count, nt_type

consolidated_cell_types.csv.gz
root_id, primary_type, additional_type(s)

neurons.csv.gz
root_id, group, nt_type, nt_type_score, da_avg, ser_avg,
 gaba_avg, glut_avg, ach_avg, oct_avg
```

O arquivo de conexões tem 263 MB comprimidos, aproximadamente 1,14 GB
descomprimidos e 22.285.323 linhas. Portanto, apesar de ser útil, ele é o
produto `no_threshold`, não a pequena seleção inicial de 68 MB mencionada
na interface. Para a primeira sub-rede, o importador aplica
`--min-synapses 5`; esse filtro produz 3.754.052 pares, próximo da contagem
de conexões apresentada pelo Codex.

O `neurons.csv.gz` já contém a previsão de neurotransmissor e seus scores.
Não é necessário baixar outro arquivo separado para essa primeira versão.

A validação de junção confirmou:

- 139.255 root IDs em `neurons.csv.gz`;
- 139.116 root IDs distintos como endpoints das conexões;
- todos esses endpoints aparecem em `neurons.csv.gz`;
- 138.327 root IDs têm tipo celular; os demais permanecem sem tipo
  classificado, sem serem descartados.

## 2. Inspecionar os arquivos

Para descobrir o formato e as colunas sem carregar o arquivo inteiro:

```bash
cd backend
python tools/inspect_flywire.py ../data/flywire/sk_lod1_783_healed.zip --samples 1
python tools/inspect_flywire.py ../data/flywire/connections.csv.gz
python tools/inspect_flywire.py ../data/flywire/cell_types.tsv --samples 3
python tools/inspect_flywire.py ../data/flywire/neurons.jsonl --json-lines
```

A ferramenta lê apenas as primeiras linhas. Isso é seguro para arquivos de
15 GB porque não constrói uma lista com o arquivo inteiro.

## 3. Gerar a primeira sub-rede

O importador processa os CSV comprimidos em streaming, seleciona os
neurônios com maior grau dentro de uma região e lê somente os SWCs
selecionados diretamente do ZIP. Para criar um exemplo do lobo óptico,
usando o lado esquerdo do
medula (`ME_L`):

```bash
cd backend
python tools/prepare_flywire_graph.py \
  --skeletons /home/mindwill/Downloads/sk_lod1_783_healed.zip \
  --neurons /home/mindwill/Downloads/neurons.csv.gz \
  --cell-types /home/mindwill/Downloads/consolidated_cell_types.csv.gz \
  --connections /home/mindwill/Downloads/connections_princeton_no_threshold.csv.gz \
  --group ME \
  --neuropil ME_L \
  --min-synapses 5 \
  --max-neurons 800 \
  --max-synapses 4000 \
  --region optic_lobes \
  --output ../data/flywire/me_left_flywire_graph.json
```

O JSON gerado contém posições dos somas, tipos celulares, neurotransmissores
previstos, neuropilot e arestas reais. O peso do LIF é uma conversão
computacional explícita: `min(10, log1p(syn_count))`; o atraso de 1 ms é uma
hipótese inicial e não uma medida sináptica do FlyWire.

## 4. Fluxo da sub-rede

O fluxo recomendado é:

```text
download bruto
      |
      v
inspecionar nomes e colunas
      |
      v
selecionar uma região/circuito
      |
      v
juntar IDs, posições, tipos e conexões
      |
      v
exportar subgrafo JSON/JSONL
      |
      v
configurar FLYWIRE_DATA_FILE
```

A primeira sub-rede deve ser pequena, por exemplo:

1. lobo óptico;
2. neurônios descendentes;
3. neurônios motores;
4. uma conexão entre uma população sensorial e uma motora.

Não tente carregar os 139 mil neurônios de uma vez no navegador.

## 5. Formato normalizado esperado

O adapter atual aceita um JSON neste formato:

```json
{
  "neurons": [
    {
      "id": "720575940629180422",
      "region": "optic_lobes",
      "x": 1000.0,
      "y": 2000.0,
      "z": 3000.0,
      "cell_type": "T4a",
      "role": "visual_input"
    }
  ],
  "synapses": [
    {
      "source": "720575940629180422",
      "target": "720575940629180423",
      "weight": 5.0,
      "delay_ms": 2.0,
      "inhibitory": false
    }
  ]
}
```

O importador gera esse JSON automaticamente a partir dos CSV/TSV oficiais
e dos skeletons SWC. A primeira versão gerada foi:

```text
../data/flywire/me_left_flywire_graph.json
```

## 6. Ativar o backend

Com uma sub-rede preparada:

```bash
cd backend
export FLYWIRE_DATA_FILE=/caminho/absoluto/data/flywire/optic_lobes.json
python main.py
```

Depois:

```bash
curl http://localhost:8000/api/providers
curl 'http://localhost:8000/api/network?region=visual&source=flywire'
```

A primeira resposta deve mostrar:

```json
{
  "source": "flywire",
  "fallback": false
}
```

Se aparecer erro de configuração, o backend continuará sem mock e retornará um erro explícito.

## 7. Integração com o frontend

Depois que o endpoint `/api/network` funcionar:

1. adicionar um botão `FlyWire` na interface;
2. carregar IDs, posições e conexões reais;
3. renderizar apenas uma sub-rede limitada;
4. conectar o motor LIF local;
5. mapear populações motoras para as animações;
6. manter a fase Axobug como comparação.

## 8. Memória e desempenho

Os limites atuais são propositalmente conservadores:

```env
MAX_GRAPH_NEURONS=1200
MAX_GRAPH_SYNAPSES=6000
MAX_REMOTE_BYTES=12000000
```

Para um subgrafo maior, aumente com cuidado e meça memória. O ideal é
pré-processar offline e servir apenas a sub-rede necessária.

## Checklist

- [x] Download do FAFB v783 identificado
- [x] ZIP de skeletons inspecionado
- [x] Tabela de conexões do mesmo snapshot baixada
- [x] Tipos celulares/anotações baixados
- [x] Colunas de neurônio, posição e conexão inspecionadas
- [x] Sub-rede pequena escolhida
- [x] JSON normalizado gerado
- [x] `FLYWIRE_DATA_FILE` configurado
- [x] `/api/network?source=flywire` responde
- [x] Frontend recebe e renderiza o grafo real
- [x] LIF local conectado ao grafo
- [x] Spikes destacados no frontend
- [ ] Axobug completamente substituído no Shadow Run
- [ ] Comportamento documentado no README e no artigo
