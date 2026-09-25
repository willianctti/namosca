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
Use `tools/inspect_flywire.py` para inspecionar os arquivos e
`tools/prepare_flywire_graph.py` para gerar uma sub-rede normalizada por
streaming, cruzando skeletons, conexões, tipos celulares e neurotransmissores.
