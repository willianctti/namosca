# Backend NaMosca

Backend FastAPI da fase real Axobug.

## Executar

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

Swagger: <http://localhost:8000/docs>

## Endpoint principal

```bash
curl -X POST \
  'http://localhost:8000/api/axobug/run?view=drive' \
  -H 'Content-Type: application/json' \
  -d '{"stimulus":"loom","intensity":1,"duration_ms":100,"seed":42}'
```

O mock foi removido. `/api/network` usa somente uma sub-rede real do
FlyWire quando `FLYWIRE_DATA_FILE` está configurado.

## Preparar FlyWire

Veja o guia:

```text
../docs/FLYWIRE_PREPARATION.md
```

O arquivo bruto de 15 GB não deve ser carregado diretamente pelo FastAPI.
Use `tools/inspect_flywire.py` para inspecionar os arquivos,
`tools/prepare_flywire_graph.py` para gerar a sub-rede cerebral e
`tools/prepare_manc_motor_catalog.py` para catalogar neurônios motores e
descendentes do gânglio ventral por streaming, e
`tools/prepare_mcns_bridge.py` para gerar a ponte MCNS → FAFB/MANC a partir
das anotações Feather, e `tools/build_motor_routes.py` para cruzar essa ponte
com as conexões MANC e listar rotas descendente → motor.
