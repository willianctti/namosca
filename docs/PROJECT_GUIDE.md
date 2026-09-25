# Guia completo do NaMosca

Este guia explica o projeto inteiro em ordem: de onde vêm os dados, como o backend os transforma, como o frontend mostra e como os sinais são ligados às partes do corpo.

## 1. O que é o NaMosca

O NaMosca é um simulador de atividade neural de uma mosca. Ele junta:

1. dados reais de conexões entre neurônios;
2. um modelo matemático simples que produz spikes;
3. uma ponte entre cérebro, gânglio ventral e neurônios motores;
4. uma visualização de uma mosca virtual.

O projeto não finge que a animação do corpo é uma reprodução muscular completa. O que é dado real e o que é modelo estão separados.

## 2. Os dados

### FAFB v783

O FAFB é o conectoma do cérebro de uma mosca adulta. Ele fornece:

- identificadores de neurônios;
- posições 3D;
- tipos celulares;
- conexões entre neurônios;
- neurotransmissores;
- células da família `Dm`.

O projeto usa uma sub-rede inicial de 800 neurônios e 4.000 conexões para manter a simulação rápida.

### MANC v1.2.1

O MANC é o conectoma do gânglio ventral. Ele contém os neurônios que recebem comandos motores e os nervos do corpo.

Os campos mais usados são:

- `Super Class`: separa neurônio motor, descendente, sensorial e outros;
- `Nerve`: indica o nervo de saída;
- `Primary Cell Type`: nome do tipo celular;
- `Class` e `Sub Class`: grupo anatômico do neurônio.

O campo `Nerve` permite reconhecer sistemas corporais amplos:

- `ProLN`: perna dianteira;
- `MesoLN`: perna do meio;
- `MetaLN`: perna traseira;
- `ADMN` e `PDM`: asas;
- `AbN`: abdômen.

### MCNS v1.0

O MCNS reúne cérebro e gânglio ventral no mesmo conjunto de dados. Ele é a peça que faz a ponte entre o FAFB e o MANC.

Os campos mais importantes são:

- `flywireType`: tipo correspondente no FAFB;
- `mancType`: tipo correspondente no MANC;
- `mancBodyid`: identificador do corpo no MANC;
- `entryNerve`: nervo de entrada;
- `exitNerve`: nervo de saída;
- `itoleeHl`: hemilineage, usada como ajuda de correspondência anatômica.

### Arquivos locais

Os arquivos grandes normalmente ficam em:

```text
/home/mindwill/Downloads
```

Os arquivos processados ficam em:

```text
data/flywire
```

Os arquivos locais grandes não são versionados pelo Git porque são grandes demais para o repositório.

## 3. O caminho dos dados

O fluxo principal é:

```text
FAFB
  ↓
tipos celulares e Dm
  ↓
MCNS
  ↓
flywireType → mancType → mancBodyid
  ↓
MANC
  ↓
conexões descendente → motor
  ↓
nervo e sistema corporal
```

O projeto não une os identificadores numéricos entre os datasets. Os identificadores pertencem a reconstruções diferentes. A ligação é feita pelos nomes de tipos e por informações anatômicas.

## 4. O que o backend faz

O backend é feito com FastAPI e fica, por padrão, na porta 8000.

Ele executa quatro tarefas principais.

### Carregar a rede

A interface chama:

```text
GET /api/network?source=flywire
```

A resposta é um JSON com:

```json
{
  "region": "optic_lobes",
  "source": "flywire",
  "coordinate_space": "normalized",
  "neurons": [],
  "synapses": [],
  "metadata": {}
}
```

Cada neurônio possui campos como:

```json
{
  "id": "12345",
  "label": "Dm12",
  "cell_type": "Dm12",
  "x": 0.1,
  "y": 0.2,
  "z": 0.3,
  "nt_type": "ACH"
}
```

Cada sinapse possui:

```json
{
  "source": "123",
  "target": "456",
  "weight": 2.3,
  "delay_ms": 1,
  "inhibitory": false,
  "synapse_count": 10
}
```

`syn_count` é o número de contatos sinápticos agregado em uma conexão. Ele não é automaticamente a força elétrica ou a força de um músculo.

### Executar a simulação

A interface chama:

```text
POST /api/simulate
```

O backend usa o modelo LIF, que significa Leaky Integrate-and-Fire. Em termos simples, cada neurônio acumula um pouco de atividade e, quando o nível passa de um limite, produz um spike.

A resposta contém:

```json
{
  "engine_used": "lif",
  "network": {},
  "frames": [
    {
      "t_ms": 50,
      "spikes": ["123", "456"],
      "total_spikes": 2
    }
  ],
  "stats": {
    "total_spikes": 2,
    "responding_neurons": 2
  },
  "motor_output": {}
}
```

`frames` são pequenos trechos da simulação usados para animar os spikes no frontend.

### Ler o mapa motor

O backend carrega:

```text
data/flywire/dm_dn_mn_routes.json
```

Esse arquivo foi produzido cruzando o MCNS com o MANC. Ele guarda caminhos do tipo:

```text
Dm → DN → MN
```

`DN` significa neurônio descendente. `MN` significa neurônio motor.

### Traduzir a resposta

Quando um spike de um `Dm` é encontrado, o backend procura o caminho correspondente no mapa.

A resposta pode ser:

```json
{
  "active_dm_types": ["DMS"],
  "systems": {
    "abdomen": 1000,
    "hind_leg": 250
  },
  "downstream_dn_types": ["DNp65"],
  "downstream_mn_types": ["MNad21"]
}
```

Os números são pesos conectômicos agregados. Eles mostram a força da conexão no dataset, não a força de um músculo real.

## 5. O que o frontend mostra

O frontend fica, por padrão, na porta 8080.

Ele mostra:

- o grafo de neurônios;
- conexões entre neurônios;
- pontos que represents somas;
- spikes gerados pelo LIF;
- candidatos `Dm`;
- mensagem da rota `Dm → DN → MN`;
- uma mosca virtual no canto superior direito.

A mosca pode reagir visualmente a:

- pernas;
- asas;
- abdômen;
- halteres.

A reação visual é controlada pelo sistema detectado na resposta. Ela não é uma simulação biomecânica completa.

## 6. Como iniciar o projeto

### Terminal 1: backend

```bash
backend/.venv/bin/uvicorn app.main:app --app-dir backend --reload
```

### Terminal 2: frontend

```bash
cd frontend
python3 -m http.server 8080
```

Abra:

```text
http://localhost:8080
```

## 7. Como usar a interface

1. Aguarde o carregamento automático da sub-rede.
2. Escolha a população de entrada.
3. Escolha quantos neurônio serão stimulated.
4. Clique em `Simular LIF local`.
5. Observe os spikes no grafo.
6. Leia a mensagem de `Dm → DN → MN`.
7. Observe qual parte da mosca foi destacada.
8. Clique em `Limpar animação` para parar e limpar a cena.

As opções de caminhos e nó isolado ficam escondidas em uma seção expansível para manter a tela principal simples.

## 8. O que é dado real e o que é modelo

### Dado real

- conexões do FAFB;
- tipos celulares;
- tipos do MCNS;
- correspondências `flywireType` e `mancType`;
- conexões do MANC;
- `syn_count` agregado;
- nervos e classes motoras.

### Modelo computacional

- LIF;
- conversão de `syn_count` em peso;
- atraso de 1 ms;
- regra simplificada para GABA, ACh e octopamina;
- normalização da sub-rede;
- animação das partes do corpo.

### Hipótese

- um spike específico sempre produz o mesmo movimento;
- uma perna se move de uma maneira específica sem um modelo muscular;
- uma resposta abdominal observada é um comportamento completo;
- a ordem de animação no corpo é biologicamente comprovada.

## 9. O que ainda falta

Para validar comportamento real, ainda precisamos de:

- mapa `MN → músculo`;
- anatomia dos músculos e articulações;
- dados experimentais de estímulo;
- dados de locomoção, fuga e respostas motoras;
- comparação entre resultado do modelo e observação real.

## 10. Resumo

```text
FAFB fornece o cérebro.
MCNS fornece a ponte de nomes.
MANC fornece os motores e os nervos.
O backend transforma conexões em uma simulação LIF.
O frontend mostra os spikes e o sistema corporal alcançado.
A animação do corpo continua sendo uma representação simplificada.
```
