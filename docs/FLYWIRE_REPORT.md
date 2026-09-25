# Relatório do circuito FlyWire local

## Protocolo congelado

A primeira versão do laboratório usa a sub-rede real:

```text
Dataset: FAFB v783 (CB)
Sub-rede: ME_L
Neurônios: 800
Conexões: 4.000
Filtro de conexões: syn_count >= 5
```

O comando que gera a sub-rede está em
[`FLYWIRE_PREPARATION.md`](FLYWIRE_PREPARATION.md).

O LIF local usa:

```text
dt: 5 ms
duração: 500 ms
frame interval: 50 ms
intensidade de entrada: 2
duração do estímulo: 100 ms
```

O peso da aresta é uma conversão computacional explícita:

```text
peso = min(10, log1p(syn_count))
```

O atraso de 1 ms é uma hipótese inicial. Não é uma medida sináptica do FlyWire.

## Resultados observados

| Condição | Entrada | Spikes | Neurônios responsivos | Dm ativos |
|---|---|---:|---:|---:|
| Baseline | 8 Pm | 69 | 8 | 0 |
| Ablação global | 8 Pm, sem inibição | 160 | 8 | 0 |
| Nó intermediário | LMa2 | 20 | 1 | 0 |
| Controle downstream | MTe52 | 493 | 46 | 6 |
| Contrafactual | LMa2, primeira aresta forçada | 333 | 46 | 6 |

A sub-rede contém 188 candidatos `Dm` no total. O caminho estrutural mais
curto encontrado a partir de Pm possui cinco sinapses. A análise do primeiro
caminho mostrou:

```text
Pm12 -- GABA/inibitória --> Pm09
Pm09 -- GABA/inibitória --> LMa2
LMa2 -- GABA/inibitória --> MTe52
MTe52 -- ACH/excitatória --> OA-AL2i1
OA-AL2i1 -- OCT/excitatória --> Dm
```

Essas arestas são interpretações a partir dos dados e são tratadas de forma
simplificada pelo LIF. Elas não representam uma medição direta de corrente,
músculo ou comportamento.

## O que foi aprendido

1. O grafo FAFB v783 foi carregado com root IDs, posições, tipos celulares,
   conexões e neurotransmissores previstos.
2. A simulação LIF executa sobre a topologia real.
3. Existem caminhos estruturais até neurônios Dm.
4. A entrada Pm não ativa Dm no modelo baseline.
5. A atividade de LMa2 não chega a Dm.
6. Estimular MTe52 diretamente ativa seis Dm.
7. Forçar a aresta LMa2 → MTe52 como excitatória libera seis Dm no modelo.

A conclusão correta é:

> A aresta LMa2 → MTe52 é um gargalo computacional para a condição testada.

A conclusão incorreta seria:

> A mosca pode usar esse caminho para pular.

A segunda afirmação exigiria mapear os neurônios para músculos, ambiente e
parâmetros do corpo.

## Glossary

- **Neurônio:** célula neural.
- **Spike:** evento de disparo elétrico produzido pelo modelo.
- **Sinapse:** contato através do qual um neurônio pode influenciar outro.
- **syn_count:** número de contatos sinápticos agregado em uma aresta do
  connectome; não é automaticamente um peso elétrico.
- **GABA:** neurotransmissor geralmente inibitório. Neste modelo recebe
  peso negativo e funciona como um freio simplificado.
- **ACH:** acetilcolina, tratada aqui como não inibitória.
- **OCT:** octopamina, modulador neuroquímico tratado aqui como não
  inibitório.
- **Dm:** família de tipos celulares descendentes no FAFB. Não significa
  automaticamente músculo de perna.
- **LIF:** modelo matemático simplificado de neurônio, chamado
  Leaky Integrate-and-Fire.
- **Ablação:** retirada controlada de um efeito do modelo.
- **Contrafactual:** simulação que altera uma hipótese para testar sua
  sensibilidade; não é uma observação biológica.

## Ponte inicial com o MANC

Os arquivos do MANC v1.2.1 foram processados pelo comando:

```bash
python backend/tools/prepare_manc_motor_catalog.py \
  --attributes /home/mindwill/Downloads/neurons(1).csv.gz \
  --connections /home/mindwill/Downloads/connections_princeton.csv.gz \
  --output data/flywire/manc_motor_catalog.json
```

O catálogo MANC confirmou:

```text
23.665 atributos de neurônios
737 neurônios motores
1.328 neurônios descendentes
6.239.883 linhas de conexões
```

A classificação ampla por nervo/sistema encontrou:

```text
perna dianteira: 144 neurônios motores
perna do meio: 121
perna traseira: 131
asas: 68
abdômen: 229
halteres: 20
pescoço: 24
```

Também foram encontrados:

```text
25.818 linhas de conexão descendente → motor
234.281 sinapses agregadas descendente → motor
```

Isso já fornece uma ponte real entre atividade descendente e circuitos motores
do gânglio ventral. Ainda não é um mapa completo de músculos: as colunas
`Body Part` e `Function` do MANC estão vazias, e o `nt_type` da tabela de
conexões também está vazio. O próximo nível exige o atlas de projeção
muscular do FANC e a ponte morfológica entre FAFB e MANC.

## Rotas descendente → motor

A ponte MCNS foi cruzada com as conexões do MANC pelo comando:

```bash
python backend/tools/build_motor_routes.py \\
  --bridge data/flywire/mcns_manc_bridge.json \\
  --manc-attributes /home/mindwill/Downloads/neurons(1).csv.gz \\
  --manc-connections /home/mindwill/Downloads/connections_princeton.csv.gz \\
  --output data/flywire/dn_motor_routes.json
```

Resultado da primeira passagem, usando apenas conexões diretas:

```text
1.247 descendentes com correspondência MANC
658 motores com correspondência MANC
1.053 descendentes com rota direta para algum motor
23.070 linhas de conexão
212.407 sinapses agregadas
```

As conexões diretas alcançaram:

```text
abdômen: 5.283 arestas
asas: 3.757
perna dianteira: 3.386
perna traseira: 1.906
perna do meio: 1.730
```

Isso já fornece candidatos reais para acionar as pernas no modelo. Ainda são
rotas diretas e agregadas: não incluem todos os caminhos premotores, não
provam um comportamento específico e ainda não são um mapa completo de
músculo/articulação.

## Saída motora por segmento

As rotas diretas foram agregadas por tipo de neurônio descendente e sistema
corporal. O catálogo final contém 422 tipos de drivers, dos quais 344 têm
conexão direta com algum motor de perna e 258 com algum motor de asa.

Totais de sinapses diretas por sistema:

```text
abdômen: 56.920
asas: 53.655
perna dianteira: 46.498
perna traseira: 23.609
perna do meio: 14.700
```

Esses valores são pesos sinápticos agregados, não uma medida de força,
movimento ou comportamento. O mapa está em
`data/flywire/motor_output_map.json` e será a base para escolher quais
sistemas da neuromecânica virtual devem reagir a cada driver.

O frontend possui um diagrama demonstrativo de uma mosca com seis pernas. Quando
uma execução registra Dm ativos, as pernas são destacadas e um proxy de resposta
é animado.

Esse mapeamento é uma hipótese de interface:

```text
Dm ativo → resposta motora genérica → pernas destacadas
```

Ele não afirma que cada Dm ativa uma perna específica. Para fazer essa
associação de forma biológica, seria necessário identificar os neurônios
motores, os nervos, as sinapses neuromusculares e os músculos correspondentes.
O diagrama é portanto uma visualização demonstrativa, não uma reconstrução
muscular do FAFB.

## Status e próximos limites

O relatório e a demonstração no frontend congelam esta primeira fase. A
animação de resposta descendente é apenas um proxy visual explicitamente
identificado como não biológico.

Para transformar atividade em caminhada, pulo ou escape seriam necessários:

1. identificar um estímulo sensorial específico;
2. confirmar o circuito descendente relevante;
3. mapear tipos celulares para grupos motores;
4. adicionar um modelo de corpo/músculo;
5. comparar o resultado com dados comportamentais.
