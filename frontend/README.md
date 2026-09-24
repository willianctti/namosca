# Frontend — fase real Axobug

O frontend atual **não usa mock** e não exibe uma rede de neurônios inventada.
A animação representa os `drive` retornados pelo modelo; não é uma prova
científica de que um estímulo real sempre produz aquele comportamento.

Ele faz duas coisas:

1. envia `food` ou `loom` para a API Axobug através do backend local;
2. usa os valores reais `brain.drive.walk` e `brain.drive.escape` para animar a
   mosca 3D.

## Executar

```bash
cd backend
source .venv/bin/activate
python main.py
```

Em outro terminal:

```bash
cd frontend
python3 -m http.server 8080
```

Abra `http://localhost:8080`.

## Testes manuais

- **Cheiro → andar:** deve mostrar `drive.walk` e a mosca andar.
- **Objeto → pular:** deve mostrar `drive.escape` e a mosca pular.
- **Shadow Run:** executa uma corrida com cinco sombras, usando `food` + cinco consultas `loom`.
- **Buscar frames completos:** faz uma segunda consulta real e mostra o JSON da resposta.
- A seção de leitura mostra canais, drives, histórico e resposta completa.
- Coloque a intensidade em `0`: o comportamento deve refletir a resposta fraca
  ou nula da API.

## TODO — FlyWire

Quando houver um download/token do FlyWire, esta fase será complementada por:

- IDs reais dos neurônios;
- coordenadas 3D;
- sinapses reais;
- marcadores de stimulus por população neural;
- marcadores neurais da população estimulada.

Até essa integração existir, a interface assume que a fonte de comportamento é a
API real da Axobug e deixa isso explícito.
