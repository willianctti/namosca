<p align="center">
  <h1>🧠 FlyBrainWeb</h1>
  <strong>Respostas neurais reais da Axobug → comportamento visual em 3D</strong>
</p>

<p align="center">
  <img alt="FastAPI" src="https://img.shields.io/badge/backend-FastAPI-0d8bff">
  <img alt="Three.js" src="https://img.shields.io/badge/frontend-Three.js-65f2ff">
  <img alt="Axobug" src="https://img.shields.io/badge/API-Axobug-ff9a73">
  <img alt="Sem mock" src="https://img.shields.io/badge/dados-sem_mock-8bf5bb">
</p>

FlyBrainWeb é um laboratório visual para explorar como respostas neurais podem
virar comportamento. Nesta fase, o projeto usa a API real da Axobug para
simular a *Drosophila melanogaster* e usar uma mosca 3D estilizada para representar
os comandos devolvidos pelo modelo.

> **Importante:** a animação é uma visualização do `drive` retornado pela API.
> Ela não afirma que um estímulo sempre produz aquele comportamento na mosca real.

![FlyBrainWeb](docs/screenshot.png)

## ✨ O que já existe

- Consulta real à Neuro API da Axobug;
- resposta com `channels`, `drive`, spikes e identificadores;
- animação de caminhada, pulo, alimentação, asas e direção conforme o
  comando recebido;
- seletor com os estímulos documentados pela Axobug;
- modo **Shadow Run** com cinco sombras;
- histórico local de experimentos;
- requisição/resposta JSON expostas na tela;
- gráfico de atividade por frame;
- frontend estático sem etapa de build;
- backend FastAPI com CORS e proxy para a API.

## 🧠 Como funciona

O fluxo de um experimento simples é:

```text
usuário escolhe um estímulo
          ↓
frontend envia POST /api/axobug/run
          ↓
backend chama a API real Axobug
          ↓
API devolve channels + drive
          ↓
frontend transforma drive em uma animação
```

Exemplo:

```text
stimulus: food
API drive.walk: 0.98
interface: caminhada
```

```text
stimulus: loom
API drive.escape: 1.00
interface: pulo
```

`channels` representa atividade neural em Hz. `drive` representa controles de
movimento normalizados entregues pelo modelo. São coisas diferentes.

## 🚀 Começar localmente

### 1. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

O backend ficará em:

```text
http://localhost:8000
```

### 2. Frontend

Em outro terminal:

```bash
cd frontend
python3 -m http.server 8080
```

Abra:

```text
http://localhost:8080
```

## 🧪 Experimentos disponíveis

A API documenta estes IDs de estímulo:

| ID | Sensação | Uso na interface |
|---|---|---|
| `sugar` | doce | alimentação/atividade neural |
| `loom` | sombra | resposta de escape |
| `food` | cheiro | ritmo de caminhada |
| `touch` | toque | resposta sensorial |
| `song` | som | resposta auditiva |
| `pheromone` | feromônio | resposta olfativa |
| `colour` | cor | resposta visual |
| `humid` | umidade | resposta sensorial |
| `heat` | temperatura | resposta sensorial |
| `bitter` | amargo | resposta de taste |
| `none` | controle | nenhum estímulo externo |

Cada requisição envia **um estímulo por vez**. Para comparar, use o mesmo
`seed` e altere somente o `stimulus` ou a `intensity`.

## 🏃 Shadow Run

O modo Shadow Run reproduce a lógica do exemplo oficial da Axobug:

1. `food` define o ritmo da corrida;
2. uma sombra se aproxima;
3. `loom` é enviado quando a sombra chega;
4. `drive.escape` define a altura do pulo;
5. o processo se repete cinco vezes.

Uma rodada utiliza seis chamadas reais:

```text
1 food + 5 loom
```

A barra de progresso mostra:

- sombras limpas;
- intensidade de escape;
- número de chamadas;
- resposta JSON de cada consulta.

A animação é local; a resposta neural que controla a decisão vem da API.

## 📡 API local

### Health

```bash
curl http://localhost:8000/api/health
```

### Providers

```bash
curl http://localhost:8000/api/providers
```

### Chamada real

```bash
curl -X POST \
  'http://localhost:8000/api/axobug/run?view=drive' \
  -H 'Content-Type: application/json' \
  -d '{
    "stimulus": "loom",
    "intensity": 1,
    "duration_ms": 100,
    "seed": 42
  }'
```

Resposta relevante:

```json
{
  "model": "flywire-v783-pruned-lif-v1",
  "total_spikes": 5763,
  "responding_neurons": 682,
  "channels": {
    "walk": 3.33,
    "escape": 185
  },
  "drive": {
    "walk": 0.42,
    "escape": 1
  }
}
```

### Endpoints

| Método | Endpoint | Status |
|---|---|---|
| `GET` | `/api/health` | ativo |
| `GET` | `/api/providers` | ativo |
| `POST` | `/api/axobug/run` | ativo |
| `GET` | `/api/network` | reservado para FlyWire |
| `WS` | `/ws/simulation` | reservado para integração futura |

## 🧬 A API usa FlyWire de verdade?

A Axobug usa um modelo computacional baseado no FlyWire v783, com anatomia e
anotações do FlyWire e uma rede LIF podada. O serviço reporta aproximadamente
138 mil neurônios e 2,7 milhões de conexões mantidas.

Isso **não** significa que a API pública entregue um grafo individual completo
em tempo real. A API pública fornece principalmente:

- canais de atividade;
- comandos `drive`;
- totais de spikes;
- identificadores de execução;
- frames de simulação.

O mapa 3D de neurônios e sinapses reais é a próxima etapa do projeto.

## 🗺️ Roadmap — FlyWire

- [ ] Obter acesso ao download estático do Codex/FAFB;
- [ ] configurar `FLYWIRE_GRAPH_URL` ou `FLYWIRE_DATA_FILE`;
- [ ] adaptar o parser aos CSV/JSON oficiais;
- [ ] mapear root IDs, coordenadas e conexões;
- [ ] carregar uma sub-rede real;
- [ ] integrar o LIF local aos dados reais;
- [ ] associar populações motoras a comportamento;
- [ ] exibir neurônios e sinapses reais em 3D.

Até essa etapa, o projeto não mostra neurônios fictícios: a visualização atual
é a mosca e os dados agregados da resposta da Axobug.

## 📁 Estrutura

```text
.
├── backend/
│   ├── main.py
│   ├── app/
│   │   ├── main.py
│   │   ├── providers/
│   │   │   ├── axobug.py
│   │   │   └── flywire.py
│   │   ├── services/
│   │   └── simulation.py
│   └── tests/
├── frontend/
│   ├── index.html
│   └── README.md
└── docs/
    └── API.md
```

## ☁️ Deploy

### Frontend

A pasta `frontend` é estática e pode ser publicada em:

- GitHub Pages;
- Vercel;
- Netlify.

Configure a URL do backend no HTML para domínios separados:

```html
<meta name="flybrain-api" content="https://api.seudominio.com">
```

### Backend

O backend Python precisa de um servidor ASGI separado, por exemplo:

```text
Render · Railway · Fly.io · Cloud Run · VM
```

O GitHub Pages não executa FastAPI.

## 🔐 Segurança

Antes de expor o backend:

- configure `CORS_ORIGINS`;
- use HTTPS;
- não commite tokens;
- adicione autenticação/rate limiting;
- limite requisições e tamanho de payloads;
- leia os termos de uso da Axobug e do FlyWire.

## 🧪 Testes

```bash
cd backend
source .venv/bin/activate
pytest -q
```

## 📄 Licença

MIT para o código do projeto. Axobug, FlyWire e datasets externos possuem
licenças, limites e atribuições próprios.
