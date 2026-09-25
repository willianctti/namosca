# API — Axobug + FlyWire local

Base local:

```text
http://localhost:8000
```

## Health

```bash
curl http://localhost:8000/api/health
```

## Providers

```bash
curl http://localhost:8000/api/providers
```

O retorno informa:

- Axobug disponível para a comparação de comportamento;
- mock desativado;
- FlyWire configurado quando `FLYWIRE_DATA_FILE` está definido.

## Chamada real à Axobug

```bash
curl -X POST \
  'http://localhost:8000/api/axobug/run?view=drive' \
  -H 'Content-Type: application/json' \
  -d '{"stimulus":"food","intensity":1,"duration_ms":100,"seed":42}'
```

Resposta relevante:

```json
{
  "model": "flywire-v783-pruned-lif-v1",
  "total_spikes": 53157,
  "responding_neurons": 7711,
  "channels": {
    "walk": 23.33,
    "escape": 0
  },
  "drive": {
    "walk": 0.9795,
    "escape": 0
  }
}
```

Para um obstáculo:

```json
{
  "stimulus": "loom",
  "intensity": 1,
  "duration_ms": 100,
  "seed": 42
}
```

O frontend usa:

- `drive.walk` para a caminhada;
- `drive.escape` para a altura do pulo;
- `channels` para exibir a atividade.

## Estímulos suportados

A API aceita os IDs documentados pela Axobug:

```text
sugar, loom, food, touch, song, pheromone,
colour, humid, heat, bitter, none
```

`none` e `intensity: 0` são controles sem estímulo.

## Shadow Run

A UI usa o fluxo:

```text
1 food → define drive.walk
5 loom → cada resposta define a altura do salto
```

A corrida e as animações são frontend; a resposta neural e os valores de
`drive` vêm da API.

## Grafo FlyWire local

Com uma sub-rede gerada pelo importador, a rota retorna IDs, posições,
tipos celulares, neurotransmissores e conexões reais:

```bash
curl -i \
  'http://localhost:8000/api/network?region=optic_lobes&source=flywire&max_neurons=800&max_synapses=4000'
```

O arquivo local é configurado por:

```bash
export FLYWIRE_DATA_FILE='./data/flywire/me_left_flywire_graph.json'
```

A pasta do projeto não fornece grafo fictício. Sem `FLYWIRE_DATA_FILE` ou
`FLYWIRE_GRAPH_URL`, a rota retorna `503` explicitamente.

## Simulação LIF local

A mesma sub-rede pode ser simulada sem Axobug:

```bash
curl -X POST http://localhost:8000/api/simulate \
  -H 'Content-Type: application/json' \
  -d '{
    "graph": {
      "region": "optic_lobes",
      "source": "flywire",
      "max_neurons": 800,
      "max_synapses": 4000
    },
    "config": {
      "duration_ms": 100,
      "dt_ms": 5,
      "frame_interval_ms": 10
    },
    "stimulus": {
      "neuron_ids": [],
      "intensity": 2.0,
      "duration_ms": 20
    },
    "engine": "lif",
    "ablate_inhibitory": false,
    "excitatory_edge_overrides": []
  }'
```

Sem IDs explícitos, o simulador seleciona uma população de entrada conforme
o papel disponível no subgrafo. A primeira sub-rede usa `role=unclassified`,
então um teste inicial deve informar `neuron_ids` para ser reprodutível.

## WebSocket

O WebSocket local usa a mesma sub-rede configurada em `FLYWIRE_DATA_FILE`:

```text
ws://localhost:8000/ws/simulation
```

Sem uma fonte FlyWire configurada, ele deve retornar um erro explícito e não
usa dados fictícios.

## Limite da API

A Neuro API pública da Axobug continua disponível para comparação. Respeite
o limite documentado pelo serviço e não faça uma chamada por quadro
desenhado. A simulação LIF local usa o subgrafo FlyWire carregado no backend.
