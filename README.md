# NaMosca

## Simulador neural e neuromecânico de uma mosca

O NaMosca usa dados reais de neurônios de *Drosophila* para observar como uma rede cerebral pode ser simulada e conectada a uma representação visual do corpo.

O caminho principal é:

```text
FAFB → MCNS → MANC → LIF → resposta neural → sistema corporal
```

O projeto usa:

- conectoma do cérebro do FAFB v783;
- catálogo de neurônios do MANC v1.2.1;
- conectoma do cérebro e gânglio ventral do MCNS v1.0;
- modelo matemático LIF local;
- mapa de rotas `Dm → DN → MN`;
- frontend para visualizar os spikes e as partes do corpo.

O frontend não usa mais a API do Axobug. A simulação principal é feita localmente com a rede real carregada pelo backend.

## O que o projeto tenta responder

A pergunta central é:

```text
O que acontece quando um circuito neural real é transformado em uma simulação computacional?
```

O projeto permite observar:

- quais neurônicos recebem spikes;
- quais tipos `Dm` são atingidos;
- quais caminhos `Dm → DN → MN` existem;
- quais nervos e sistemas corporais são alcançados;
- como essa informação pode aparecer no corpo virtual.

A animação do corpo é uma forma de visualizing os resultados. Ela ainda não é uma simulação muscular completa.

## IMPORTANTE: o que é real e o que é modelo

### Dado real

Os seguintes dados vêm de datasets publicados:

- conexões entre neurônios;
- tipos celulares;
- identificadores de tipos no FAFB, MCNS e MANC;
- conexões descendente → motor;
- nervos;
- classes de neurônios motores;
- valores de `syn_count`, que são a quantidade agregada de contatos sinápticos de uma conexão.

### Modelo computacional

O projeto usa um modelo LIF local. LIF significa `Leaky Integrate-and-Fire`, ou “integração com vazamento e disparo”.

Em termos simples, cada neurônio:

1. acumula atividade;
2. perde um pouco dessa atividade com o tempo;
3. produz um spike quando passa de um limite.

O peso da conexão é calculado a partir do `syn_count`. Isso é uma escolha computacional. O `syn_count` não é automaticamente a força elétrica da sinapse.

### Hipótese visual

A conversão de spike em movimento é simplificada.

Quando o mapa encontra uma rota para uma perna, a interface pode destacar a perna. Isso significa:

```text
existe uma rota conectômica para aquele sistema
```

Não significa automaticamente:

```text
a mosca real produziria exatamente aquele movimento
```

Ainda não existe um atlas muscular completo `MN → músculo → articulação` ligado ao modelo.

## Os datasets

### FAFB v783

O FAFB é o conectoma do cérebro de uma mosca adulta. O projeto usa uma sub-rede inicial:

```text
800 neurônios
4.000 conexões
```

O backend usa essa sub-rede para a simulação LIF.

### MANC v1.2.1

O MANC contém informações do gânglio ventral, incluindo os neurônios motores e os nervos do corpo.

O projeto usa campos como:

- `Super Class`;
- `Class`;
- `Sub Class`;
- `Nerve`;
- `Primary Cell Type`.

O campo `Nerve` ajuda a reconhecer sistemas como:

- `ProLN`: perna dianteira;
- `MesoLN`: perna do meio;
- `MetaLN`: perna traseira;
- `ADMN` e `PDM`: asas;
- `AbN`: abdômen.

### MCNS v1.0

O MCNS reúne cérebro e gânglio ventral. Ele é usado como ponte porque possui campos de correspondência:

- `flywireType`: tipo correspondente no FAFB;
- `mancType`: tipo correspondente no MANC;
- `mancBodyid`: identificador do corpo no MANC;
- `entryNerve`: nervo de entrada;
- `exitNerve`: nervo de saída.

O MCNS também fornece um conectoma completo, usado para procurar caminhos:

```text
Dm → DN → MN
```

## Como os dados são processados

Os arquivos grandes ficam fora do Git, normalmente em:

```text
/home/mindwill/Downloads
```

Exemplos:

```text
sk_lod1_783_healed.zip
neurons(1).csv.gz
connections_princeton.csv.gz
body-annotations-male-cns-v1.0-minconf-0.5.feather
body-neurotransmitters-male-cns-v1.0.feather
connectome-weights-male-cns-v1.0-minconf-0.5.feather
```

O arquivo de skeletons do FAFB tem cerca de 13 GB. Ele não entra no repositório porque é grande demais para o Git.

Os arquivos processados ficam em:

```text
data/flywire
```

Os principais são:

```text
me_left_flywire_graph.json
mcns_manc_bridge.json
dn_motor_routes.json
motor_output_map.json
dm_dn_mn_routes.json
```

Esses arquivos são gerados localmente e não precisam ser versionados.

## O caminho da ponte

A ponte não une os identificadores numéricos entre os datasets. Os root IDs são diferentes porque os datasets foram reconstruídos de indivíduos diferentes.

O caminho usado é:

```text
tipo celular no FAFB
        ↓
flywireType no MCNS
        ↓
bodyId no MCNS
        ↓
mancType e mancBodyid
        ↓
neurônio no MANC
```

Depois, o conectoma do MANC ou do MCNS é usado para procurar conexões entre esses neurônios.

## Como o backend funciona

O backend usa FastAPI e fica normalmente na porta 8000.

### Carregar o grafo

```text
GET /api/network?source=flywire
```

A resposta JSON tem dois grupos principais:

```json
{
  "neurons": [
    {
      "id": "123",
      "cell_type": "Dm12",
      "x": 0.1,
      "y": 0.2,
      "z": 0.3
    }
  ],
  "synapses": [
    {
      "source": "123",
      "target": "456",
      "weight": 2.3,
      "synapse_count": 10,
      "inhibitory": false
    }
  ]
}
```

### Executar a simulação

```text
POST /api/simulate
```

Exemplo derequisição:

```json
{
  "graph": {
    "region": "optic_lobes",
    "source": "flywire",
    "max_neurons": 800,
    "max_synapses": 4000
  },
  "config": {
    "duration_ms": 500,
    "dt_ms": 5,
    "frame_interval_ms": 50
  },
  "stimulus": {
    "neuron_ids": ["123", "456"],
    "intensity": 2,
    "duration_ms": 100
  },
  "engine": "lif"
}
```

A resposta inclui:

- `frames`: trechos da simulação com spikes;
- `stats`: totais da execução;
- `motor_output`: sistemas corporais alcançados pelo mapa.

Exemplo simplificado:

```json
{
  "engine_used": "lif",
  "stats": {
    "total_spikes": 69,
    "responding_neurons": 8
  },
  "motor_output": {
    "active_dm_types": ["Dm12"],
    "systems": {
      "hind_leg": 1200
    }
  }
}
```

### Resposta motora

O arquivo `dm_dn_mn_routes.json` contém caminhos:

```text
Dm → DN → MN
```

O backend procura o tipo do neurônio que produziu spike e consulta esse mapa.

O sistema pode classificar a resposta como:

- `front_leg`: perna dianteira;
- `middle_leg`: perna do meio;
- `hind_leg`: perna traseira;
- `wing`: asa;
- `abdomen`: abdômen;
- `haltere`: halter;
- `unclassified`: sem sistema classificado.

## Como o frontend funciona

O frontend fica normalmente na porta 8080.

Ele:

- mostra o grafo de neurônios;
- mostra conexões;
- destaca os pontos que produziram spike;
- mostra candidatos `Dm`;
- mostra os números principais;
- mostra a rota `Dm → DN → MN`, quando existe;
- mostra a mosca no canto superior direito;
- destaca o sistema corporal encontrado.

A simulação é iniciada pelo botão:

```text
Simular LIF local
```

Os números detalhados da sub-rede ficam em uma seção expansível chamada:

```text
Ver números da sub-rede
```

As opções de caminhos e nó isolado também ficam escondidas para manter a tela principal simples.

O botão:

```text
Limpar animação
```

para os frames, limpa os spikes destacados e remove o destaque das partes do corpo.

## Como executar

### 1. Instalar as dependências

```bash
cd backend
.venv/bin/pip install -r requirements.txt
```

### 2. Iniciar o backend

Na raiz do projeto:

```bash
backend/.venv/bin/uvicorn app.main:app --app-dir backend --reload
```

### 3. Iniciar o frontend

Em outro terminal:

```bash
cd frontend
python3 -m http.server 8080
```

Abra:

```text
http://localhost:8080
```

## Estrutura do projeto

```text
backend/
├── app/
│   ├── main.py
│   ├── simulation.py
│   ├── schemas.py
│   ├── realtime.py
│   ├── providers/
│   ├── services/
│   └── motor_output.py
├── tools/
│   ├── prepare_flywire_graph.py
│   ├── prepare_manc_motor_catalog.py
│   ├── prepare_mcns_bridge.py
│   ├── build_motor_routes.py
│   ├── build_mcns_dm_routes.py
│   └── summarize_motor_output.py
├── tests/
└── requirements.txt

frontend/
└── index.html

data/flywire/
└── arquivos processados locais

docs/
└── README.md
```

## Testes

A partir da pasta `backend`:

```bash
.venv/bin/pytest -q
```

Resultado esperado:

```text
9 passed
```

## Limitações atuais

- o backend simula uma sub-rede, não o FAFB inteiro;
- o LIF é um modelo simples;
- `syn_count` é transformado em peso por uma regra computacional;
- o mapa usa神经系统 e tipos celulares, mas não um atlas muscular completo;
- a resposta do corpo é uma visualização conectômica;
- não existe ainda validação completa com resposta muscular e comportamento observado;
- a correspondência entre datasets é feita por tipos e informações anatômicas, não por root IDs compartilhados.

## Próximos passos

1. testar diferentes populações de entrada;
2. validar as rotas `Dm → DN → MN` com os dados do MCNS;
3. encontrar ou construir um mapa `MN → músculo`;
4. adicionar anatomia muscular e articulações;
5. comparar a simulação com dados comportamentais;
6. substituir gradualmente a animação simplificada por uma neuromecânica com músculos.

## Documentação completa

O guia detallado do projeto está em:

```text
docs/README.md
```

O plano para a placa real ESP32 com sensor DHT11 e LEDs está em:

```text
docs/HARDWARE_PLAN.md
```

Ele inclui o prompt pronto para o GPT, as ligações, o código inicial e os próximos passos para conectar o hardware ao backend.
