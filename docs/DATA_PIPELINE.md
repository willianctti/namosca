# Pipeline de dados do NaMosca

Este documento explica, em ordem, o que é cada dataset, o que entra no cruzamento e o que ainda é hipótese.

## 1. FAFB v783 — cérebro feminino

**Arquivos**

- `sk_lod1_783_healed.zip`
- `neurons.csv.gz`
- `consolidated_cell_types.csv.gz`
- `connections_princeton_no_threshold.csv.gz`

**O que representa**

O FAFB é a reconstrução do cérebro de uma mosca adulta. Ele fornece:

- IDs de neurônios;
- coordenadas 3D;
- tipos celulares;
- conexões sinápticas;
- neurotransmissores;
- candidatos da família `Dm`.

**O que já é usado**

O importador `prepare_flywire_graph.py` cria uma sub-rede local, inicialmente `ME_L`, com 800 neurônios e 4.000 conexões. O backend executa nela o modelo LIF.

**Limite**

O FAFB sozinho não informa que um `Dm` ativa uma perna específica. `Dm` é uma família celular descendente, não um rótulo de músculo.

## 2. MANC v1.2.1 — gânglio ventral masculino

**Arquivos**

- `/home/mindwill/Downloads/neurons(1).csv.gz`
- `/home/mindwill/Downloads/connections_princeton.csv.gz`

**O que representa**

O MANC cobre o gânglio ventral e contém os neurônios motores, sensoriais e interneuronais do sistema nervoso central.

**Campos úteis**

- `Super Class`
- `Class`
- `Sub Class`
- `Nerve`
- `Primary Cell Type`
- `Flow`

Os 737 registros da classe `motor` são catalogados. O campo `Nerve` permite reconhecer sistemas como:

- `ProLN` → perna dianteira;
- `MesoLN` → perna do meio;
- `MetaLN` → perna traseira;
- `ADMN`/`PDM` → asa;
- `AbN` → abdômen.

**Limite**

As colunas `Body Part` e `Function` do MANC estão vazias. Portanto, o MANC fornece o sistema corporal amplo e tipos motores, mas ainda não é um atlas completo de músculo e articulação.

## 3. MCNS v1.0 — cérebro + gânglio ventral masculino

**Arquivos**

- `body-annotations-male-cns-v1.0-minconf-0.5.feather`
- `body-neurotransmitters-male-cns-v1.0.feather`

**Por que ele é importante**

O MCNS é o dataset que conecta o FAFB e o MANC no mesmo padrão de nomenclatura. Suas anotações possuem:

- `flywireType`: tipo correspondente no FAFB;
- `mancType`: tipo correspondente no MANC;
- `mancBodyid`: ID do corpo no MANC;
- `entryNerve` e `exitNerve`;
- hemilineage;
- lado do corpo;
- superclasse e subclasse.

**Importador**

```bash
backend/.venv/bin/python backend/tools/prepare_mcns_bridge.py \
  --annotations /home/mindwill/Downloads/body-annotations-male-cns-v1.0-minconf-0.5.feather \
  --output data/flywire/mcns_manc_bridge.json
```

## 4. Cruzamento FAFB → MCNS → MANC

O cruzamento não une os root IDs entre os datasets. Ele usa as anotações de tipo:

```text
tipo no FAFB
    ↓
flywireType no MCNS
    ↓
bodyId no MCNS
    ↓
mancType e mancBodyid
    ↓
neurônio no MANC
```

A correspondência é uma associação entre tipos celulares. Deve ser tratada como ponte computacional, não como identidade de um único neurônio entre indivíduos diferentes.

## 5. Cruzamento MCNS/MANC com as conexões

O arquivo de conexões do MANC é lido por streaming. Para cada conexão descendente → motor, o programa soma `syn_count` e associa o motor ao sistema corporal.

```bash
backend/.venv/bin/python backend/tools/build_motor_routes.py \
  --bridge data/flywire/mcns_manc_bridge.json \
  --manc-attributes "/home/mindwill/Downloads/neurons(1).csv.gz" \
  --manc-connections "/home/mindwill/Downloads/connections_princeton.csv.gz" \
  --output data/flywire/dn_motor_routes.json
```

Depois as rotas são agregadas por tipo driver e sistema corporal:

```bash
backend/.venv/bin/python backend/tools/summarize_motor_output.py \
  --routes data/flywire/dn_motor_routes.json \
  --output data/flywire/motor_output_map.json
```

## 6. O que existe hoje no mapa motor

O mapa `motor_output_map.json` contém 422 tipos de drivers. Ele registra, por exemplo:

```text
DNg105 → perna dianteira, perna do meio, perna traseira
DNp31  → asas
```

Os valores são pesos sinápticos agregados. Eles significam:

```text
quantidade de sinapses conectando o driver a um grupo de motores
```

Eles não significam diretamente:

- força muscular;
- ângulo de articulação;
- velocidade da perna;
- comportamento final;
- probabilidade de movimento.

## 7. Rotas `Dm` reais no MCNS

O conectoma completo do MCNS foi lido por streaming em dois passos. Primeiro
foram selecionadas conexões `Dm → descendente`; depois, `descendente → motor`.
O resultado está em `data/flywire/dm_dn_mn_routes.json`.

```text
Dm bodies: 7.187
Dm → descendentes: 107 arestas
descendentes intermediários: 10
descendente → motor: 164 arestas
Dm → DN → MN: 164 caminhos
Dm → MN direto: 0
```

A maior parte dessas rotas termina em abdômen; apenas uma pequena parte termina
em asa ou pernas. Isso é um resultado real do dataset, não uma escolha para
forçar uma resposta de caminhada. O mapa será usado para mostrar quando a
simulação realmente alcançar esses caminhos.


### Dado real

- conectoma do FAFB;
- atributos do MANC;
- anotações do MCNS;
- conexões e `syn_count` reais;
- correspondências de tipo fornecidas pelos datasets.

### Modelo computacional

- LIF para os neurônios;
- transformação de `syn_count` em peso;
- atraso artificial de 1 ms;
- regra de sinal GABA/ACH/OCT;
- normalização e truncamento dos grafos.

### Hipótese ou proxy

- associar spike de um driver a uma resposta visual;
- associar um tipo de driver a um movimento específico;
- associar um motor a uma articulação sem atlas muscular completo;
- transformar a atividade neural em um movimento de corpo virtual.

## 8. O que falta para afirmar comportamento biológico

Ainda falta:

1. atlas de projeção muscular com `MN → músculo`;
2. anatomia muscular e articulações;
3. parâmetros biomecânicos dos músculos;
4. estímulo experimental específico;
5. comparação com dados de locomoção, escape ou resposta aérea.

Até essa validação, a neuromecânica deve mostrar duas camadas separadas:

- **rastreabilidade:** dado conectômico real;
- **hipótese:** movimento do corpo virtual.

## Resumo em uma frase

```text
FAFB fornece o cérebro e os Dm; MCNS fornece a ponte nominal; MANC fornece os motores e nervos; o modelo LIF fornece spikes; a neuromecânica ainda é um proxy até existir o mapa muscular/articulação.
```
