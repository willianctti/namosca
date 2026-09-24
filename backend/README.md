# Backend — fase real Axobug

O backend agora não gera mais grafos mockados. A fase atual usa a API real da
Axobug para experimentos de comportamento:

```text
POST https://axobug.com/api/v1/run
```

A API usa um modelo computacional baseado no FlyWire v783, com uma rede LIF
podada. Isso não equivale a uma leitura ao vivo de uma mosca real: a API
pública devolve canais e comandos agregados, não o grafo individual completo.
O código do FlyWire continua preparado para a próxima etapa, mas o grafo real
só será ativado quando `FLYWIRE_GRAPH_URL` ou `FLYWIRE_DATA_FILE` estiver
configurado com dados autorizados.

## Executar

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

Swagger:

```text
http://localhost:8000/docs
```

## Endpoint real usado pelo frontend

```bash
curl -X POST \
  'http://localhost:8000/api/axobug/run?view=drive' \
  -H 'Content-Type: application/json' \
  -d '{"stimulus":"loom","intensity":1,"duration_ms":100,"seed":42}'
```

Resposta relevante:

```json
{
  "model": "flywire-v783-pruned-lif-v1",
  "total_spikes": 5763,
  "responding_neurons": 682,
  "channels": {"walk": 3.33, "escape": 185},
  "drive": {"walk": 0.42, "escape": 1}
}
```

- `food` usa `drive.walk` para controlar a caminhada.
- `loom` usa `drive.escape` para controlar a altura do pulo.
- `channels` e `drive` são exibidos diretamente na interface.

## Endpoints

| Método | Endpoint | Situação |
|---|---|---|
| `GET` | `/api/health` | ativo |
| `GET` | `/api/providers` | mostra Axobug ativo e mock desativado |
| `POST` | `/api/axobug/run` | ativo; chamada real |
| `GET` | `/api/network` | 503 até configurar FlyWire real |
| `WS` | `/ws/simulation` | reservado para a etapa FlyWire |
| `GET` | `/neurons` | 503; não existem neurônios mockados |
| `GET` | `/synapses` | 503; não existem sinapses mockadas |

## TODO — FlyWire

1. Obter acesso ao download estático do Codex/FAFB.
2. Configurar `FLYWIRE_GRAPH_URL` ou `FLYWIRE_DATA_FILE`.
3. Adaptar o parser ao formato oficial.
4. Carregar IDs, coordenadas, regiões e conexões reais.
5. Integrar o motor LIF local aos dados reais.
6. Associar populações motoras às animações.

O mock foi removido para que uma falha de dados seja visível em vez de
mostrar informação visual falsa.

## Testes

```bash
source .venv/bin/activate
pytest -q
```

Os testes verificam o LIF com uma fixture mínima, o aliases de região e a
falha explícita quando o FlyWire não está configurado.
