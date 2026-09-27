# ESP32 + 1 LED ligado aos neurônios do NaMosca

Etapa 1 do protótipo físico. Sem sensor, sem motor, sem DHT11.

Circuito:

```text
GPIO 12 → resistor 220Ω → LED → GND
```

Regra do protótipo:

```text
o backend encontra rota Dm → DN → MN para uma perna
        ↓
acende o LED
```

## Prompt 1 — imagem do diagrama de ligação

Copie e cole no GPT para gerar a imagem:

```text
Preciso de um DIAGRAMA DE LIGAÇÃO ELÉTRICA (imagem) para um protótipo simples com ESP32.

CONTEXTO
Estou montando um protótipo de hardware do projeto NaMosca, que simula uma rede neural real de mosca (Drosophila) e responde qual sistema corporal foi alcançado. Nesta primeira etapa NÃO existe sensor nenhum. O ESP32 recebe a resposta da simulação por Wi-Fi e acende um LED quando a simulação detecta rota neural para uma perna (motor_output.systems contendo front_leg, middle_leg ou hind_leg).

PEÇAS (só estas):
- 1x ESP32 DevKit (30 pinos, modelo genérico "ESP32 DEVKIT V1")
- 1x LED 5mm
- 1x resistor de 220 ohms
- 1x protoboard
- 2x cabos macho-macho
- cabo USB (só para gravar e alimentar)

NÃO existe: DHT11, sensor de movimento, motor, servo, buzzer, fonte externa, relé, transistor, driver. Não desenhe esses componentes.

LIGAÇÃO QUE QUERO (exatamente esta):
- Resistor 220Ω: uma ponta no GPIO 12 do ESP32, a outra ponta no ÂNODO (perna mais longa) do LED.
- LED: o CÁTODO (perna mais curta) no GND do ESP32.
- Nenhum outro fio. GPIO 12 -> 220Ω -> LED -> GND.

REQUISITOS DA IMAGEM:
1. Visão geral (isométrica ou vista de cima) com ESP32, protoboard, resistor e LED.
2. Diagrama esquemático limpo, com símbolos padrão de resistor e de LED, mostrando o GND como ponto comum.
3. Rótulos em português: "GPIO 12", "220 Ω", "ânodo (+)", "cátodo (−)", "GND".
4. Aviso visual: "o resistor é obrigatório, nunca ligue o LED direto no GPIO".
5. Mostrar onde ficam os pinos GND do ESP32 (todos são equivalentes).
6. Marcar com X os GPIOs que NÃO devem ser usados agora (0, 2, 15 e pinos de boot/strapping), sem ligar nada neles.
7. Circuito de baixa tensão (3.3 V). Não usar cores falsas de fiação.

FORMATO:
- Gere a imagem com o gerador de imagens, não apenas texto.
- Fundo branco, traço preto, estilo técnico, sem cartoon.
- Antes de gerar, liste em texto curto a lista exata de pinos e a polaridade do LED, para eu conferir.
- Se não for possível gerar a imagem, desenhe um diagrama ASCII bem alinhado no lugar.
```

## Prompt 2 — firmware que consulta os neurônios do NaMosca

Copie e cole no GPT. Ele já tem o contexto do projeto, então ele pode assumir a API do NaMosca.

```text
Agora quero o FIRMWARE do ESP32. O LED está ligado no GPIO 12 (com resistor de 220Ω no meio). Não existe sensor, não existe motor, não existe DHT11.

O que o firmware precisa fazer:
1. Conectar no Wi-Fi.
2. Falar com o backend do NaMosca (FastAPI) e pedir uma simulação da rede neural real da mosca.
3. Ler a resposta neural e ver se existe rota para uma PERNA.
4. Se existir rota de perna, acender o LED. Se não existir, deixar apagado.
5. Repetir em ciclo e imprimir tudo no Monitor Serial para eu depurar.

Endpoint do backend (já existe, não invente outro):
POST http://<IP-DO-PC>:8000/api/simulate

Exemplo de requisição:
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
    "neuron_ids": [],
    "intensity": 2,
    "duration_ms": 100
  },
  "engine": "lif"
}

A resposta tem um bloco motor_output, mais ou menos assim:
{
  "stats": { "total_spikes": 69, "responding_neurons": 8 },
  "motor_output": {
    "available": true,
    "active_dm_types": ["Dm12"],
    "systems": { "hind_leg": 1200, "wing": 300 }
  }
}

REGRAS DE DECISÃO DO LED (implemente exatamente assim):
- Se motor_output.systems tiver qualquer uma destas chaves: front_leg, middle_leg, hind_leg → LED ACENDE.
- Se systems estiver vazio, ausente, ou só tiver chaves como wing, abdomen, haltere, unclassified → LED APAGADO.
- Trate também a rede como desligada: se o Wi-Fi cair ou o backend retornar erro, desligue o LED e mostre o motivo no Serial. Nunca deixe o LED aceso por engano.

CUIDADOS IMPORTANTES:
- Use WiFi.h, HTTPClient e ArduinoJson. Diga qual versão do ArduinoJson instalar.
- Trate o caso de resposta grande: não trave o ESP32 fazendo strlen fixo. Faça o parse de forma robusta.
- Coloque credenciais de Wi-Fi e IP do backend em #define no topo, bem comentados.
- Não use delay() longo no loop, senão a reinicialização do Wi-Fi falha. Use millis().
- Cold-start: espere o Wi-Fi conectar com timeout de ~15 s e LED piscando indicate "conectando".
- Trate tempo de resposta longo do backend sem travar o loop (delay maior entre requisições, com log).

O QUE EU PRECISO DE VOLTA, nessa ordem:
1. Explicação simples do fluxo (passo a passo, em português, para quem nunca programou microcontrolador).
2. Lista de bibliotecas a instalar e onde no Arduino IDE.
3. O código completo, comentado em português.
4. Como configurar placa, porta serial e Monitor Serial (115200 baud).
5. O que precisa aparecer no Serial para eu saber que deu certo em cada etapa.
6. O que fazer se o LED não acender: lista de verificação passo a passo (resistor ligado? ânodo/cátodo certainos? backend está rodando? IP e porta corretos? firewall?).
7. Como confirmar que o LED está reagindo mesmo ao backend: um MODO DE TESTE que pisca o LED sem backend, para separar problema de hardware de problema de rede.

Antes de gerar o código, me confirme em uma linha qual biblioteca HTTP você vai usar e por quê.
```

## Ordem de execução

1. Montar o circuito e validar com o Prompt 1.
2. Gravar o firmware de teste (Modo Teste do Prompt 2, item 7) → LED pisca.
3. Subir o backend:

   ```bash
   backend/.venv/bin/uvicorn app.main:app --app-dir backend --reload
   ```

4. Descobrir o IP do PC na mesma rede do Wi-Fi (`hostname -I`).
5. Gravar o firmware completo e observar `motor_output.systems` no Serial.
6. Quando aparecer `hind_leg` / `front_leg` / `middle_leg`, o LED acende sozinho.

## Limites desta etapa

- Um LED só não mostra qual perna. Se quiser distinguir, use 3 LEDs (dianteira, meio, traseira) e um GPIO cada.
- O `systems` vem do mapa de rotas `Dm → DN → MN`. É evidência conectômica de que existe caminho até aquele sistema, não prova de que a mosca real produziria aquele movimento.
- Os pinos de entrada do estímulo vêm vazios nesta versão. Deixar `neuron_ids` vazio é esperado.
