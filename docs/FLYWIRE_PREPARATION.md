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

## 1. Guardar o download fora do Git

O `.gitignore` já ignora `data/`, CSV, TSV, arquivos comprimidos e formatos
scientificos grandes. Use, por exemplo:

```text
/home/mindwill/Documentos/mosca/data/flywire/
```

Não envie esses arquivos para o GitHub.

## 2. Inspecionar os arquivos

Para descobrir o formato e as colunas sem carregar o arquivo inteiro:

```bash
cd backend
python tools/inspect_flywire.py ../data/flywire/connections.csv.gz
python tools/inspect_flywire.py ../data/flywire/cell_types.tsv --samples 3
python tools/inspect_flywire.py ../data/flywire/neurons.jsonl --json-lines
```

A ferramenta lê apenas as primeiras linhas. Isso é seguro para arquivos de
15 GB porque não constrói uma lista com o arquivo inteiro.

## 3. Criar uma sub-rede

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

## 4. Formato normalizado esperado

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

O próximo passo será gerar esse JSON automaticamente a partir dos CSV/TSV
oficiais, depois de conferir os nomes reais das colunas no download.

## 5. Ativar o backend

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

## 6. Integração com o frontend

Depois que o endpoint `/api/network` funcionar:

1. adicionar um botão `FlyWire` na interface;
2. carregar IDs, posições e conexões reais;
3. renderizar apenas uma sub-rede limitada;
4. conectar o motor LIF local;
5. mapear populações motoras para as animações;
6. manter a fase Axobug como comparação.

## 7. Memória e desempenho

Os limites atuais são propositalmente conservadores:

```env
MAX_GRAPH_NEURONS=1200
MAX_GRAPH_SYNAPSES=6000
MAX_REMOTE_BYTES=12000000
```

Para um subgrafo maior, aumente com cuidado e meça memória. O ideal é
pré-processar offline e servir apenas a sub-rede necessária.

## Checklist

- [ ] Download termina
- [ ] Nomes e formatos dos arquivos anotados
- [ ] Colunas de neurônio, posição e conexão inspecionadas
- [ ] Sub-rede pequena escolhida
- [ ] JSON normalizado gerado
- [ ] `FLYWIRE_DATA_FILE` configurado
- [ ] `/api/network?source=flywire` responde
- [ ] Frontend recebe grafo real
- [ ] LIF local conectado ao grafo
- [ ] Comportamento documentado no README e no artigo
