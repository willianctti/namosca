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

O mock foi removido. `/api/network` somente funciona depois que uma sub-rede
real do FlyWire for preparada e configurada.

## Preparar FlyWire

Veja o guia:

```text
../docs/FLYWIRE_PREPARATION.md
```

O arquivo bruto de 15 GB não deve ser carregado diretamente pelo FastAPI.
Use `tools/inspect_flywire.py` para inspecionar CSV/TSV/JSONL por streaming e
depois gere uma sub-rede normalizada pequena.
