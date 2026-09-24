# API — fase real Axobug

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

- Axobug disponível para simulação/comportamento;
- mock desativado;
- FlyWire ainda não configurado.

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


```bash
curl -i 'http://localhost:8000/api/network?region=optic_lobes'
```

Enquanto o FlyWire não estiver configurado, essa rota retorna `503` com uma
mensagem explicando que o mock está desativado.

Para ativar dados reais futuramente:

```bash
export FLYWIRE_GRAPH_URL='https://seu-proxy/flywire.json'
# ou
export FLYWIRE_DATA_FILE='./dados-flywire.json'
```

A pasta do projeto não fornece mais um grafo fictício.

## WebSocket

O WebSocket local fica reservado para a etapa FlyWire:

```text
ws://localhost:8000/ws/simulation
```

Sem uma fonte FlyWire configurada, ele não deve ser usado como fonte de
neurônios.

## Limite da API

A Neuro API pública da Axobug é usada em cada experimento. Respeite o limite
documentado pelo serviço e não faça uma chamada por quadro desenhado.
