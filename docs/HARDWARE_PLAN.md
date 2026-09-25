# Plano da placa real: ESP32, DHT11 e NaMosca

Este documento deixa preparado o próximo passo do projeto com hardware real.

## Objetivo

Começar com uma placa ESP32, um sensor DHT11 e três LEDs. A primeira etapa não terá motor. O objetivo é confirmar que o hardware funciona e, depois, enviar a temperatura ao backend do NaMosca.

Fluxo inicial:

```text
DHT11 → ESP32 → LED
```

Fluxo completo que construiremos depois:

```text
DHT11 → ESP32 → Wi-Fi → backend NaMosca → LIF → resposta → LED
```

## Peças que você tem

- 1x ESP32 DevKit;
- 3x LEDs;
- 6x cabos macho-macho;
- 1x sensor DHT11.

## Material que ainda pode ser necessário

Compre, se ainda não tiver:

- 3x resistores de 220 ohms;
- 1x protoboard;
- cabos adicionais, se os seis não alcançarem.

Cada LED precisa de um resistor. O sensor DHT11 normalmente já tem resistor na plaquinha.

## Ligação do DHT11

O DHT11 normalmente tem quatro pinos:

```text
VCC
DATA
NC
GND
```

No DHT11, os pinos são normalmente:

```text
face da plaquinha para você, da esquerda para a direita:
VCC, DATA, NC, GND
```

Confira os rótulos impressos na plaquinha. O pino `NC` significa que ele não é usado.

Ligação inicial:

```text
ESP32 3V3 → DHT11 VCC
ESP32 GPIO 4 → DHT11 DATA
ESP32 GND → DHT11 GND
DHT11 NC → não conectado
```

Não conecte o `NC` em nenhum lugar.

## Ligação dos LEDs

Cada LED precisa de um resistor de 220 ohms.

```text
GPIO 12 → resistor 220Ω → LED verde → GND
GPIO 13 → resistor 220Ω → LED amarelo → GND
GPIO 14 → resistor 220Ω → LED vermelho → GND
```

O resistor pode ficar antes ou depois do LED. O que importa é que o LED e o resistor fiquem em série.

Não ligue o LED diretamente no GPIO sem resistor.

## Código inicial do DHT11

Use este código somente se o sensor for DHT11:

```cpp
#include <DHT.h>

#define DHT_PIN 4
#define DHT_TYPE DHT11

#define LED_VERDE 12
#define LED_AMARELO 13
#define LED_VERMELHO 14

DHT dht(DHT_PIN, DHT_TYPE);

void setup() {
  Serial.begin(115200);

  pinMode(LED_VERDE, OUTPUT);
  pinMode(LED_AMARELO, OUTPUT);
  pinMode(LED_VERMELHO, OUTPUT);

  digitalWrite(LED_VERDE, LOW);
  digitalWrite(LED_AMARELO, LOW);
  digitalWrite(LED_VERMELHO, LOW);

  dht.begin();

  Serial.println("NaMosca: sensor DHT11 iniciado");
}

void loop() {
  float temperatura = dht.readTemperature();

  if (isnan(temperatura)) {
    Serial.println("Erro ao ler o sensor DHT11");
    digitalWrite(LED_VERDE, LOW);
    digitalWrite(LED_AMARELO, LOW);
    digitalWrite(LED_VERMELHO, LOW);
    delay(2000);
    return;
  }

  Serial.print("Temperatura: ");
  Serial.print(temperatura);
  Serial.println(" C");

  if (temperatura < 25.0) {
    digitalWrite(LED_VERDE, HIGH);
    digitalWrite(LED_AMARELO, LOW);
    digitalWrite(LED_VERMELHO, LOW);
    Serial.println("Estado: NORMAL");
  } else if (temperatura < 30.0) {
    digitalWrite(LED_VERDE, LOW);
    digitalWrite(LED_AMARELO, HIGH);
    digitalWrite(LED_VERMELHO, LOW);
    Serial.println("Estado: TEMPERATURA ALTA");
  } else {
    digitalWrite(LED_VERDE, LOW);
    digitalWrite(LED_AMARELO, LOW);
    digitalWrite(LED_VERMELHO, HIGH);
    Serial.println("Estado: ALERTA");
  }

  delay(2000);
}
```

Esse código ainda não usa os neurônios do NaMosca. Ele somente testa o sensor e os LEDs.

## Arduino IDE

1. Instale o Arduino IDE.
2. Abra `Arquivo > Preferências`.
3. Em `URLs adicionais do Gerenciador de Placas`, adicione a URL oficial do ESP32:

```text
https://espressif.github.io/arduino-esp32/package_esp32_index.json
```

4. Abra `Ferramentas > Placa > Gerenciador de Placas`.
5. Procure por `esp32`.
6. Instale `esp32 by Espressif Systems`.
7. Selecione `Ferramentas > Placa > esp32 > ESP32 Dev Module`.
8. Conecte o cabo USB do ESP32 ao computador.
9. Selecione a porta serial correta em `Ferramentas > Porta`.
10. Instale a biblioteca `DHT sensor library by Adafruit`.
11. Se aparecer, instale também `Adafruit Unified Sensor`.
12. Abra `Ferramentas > Monitor Serial` e use `115200 baud`.

Se o IDE mostrar several portas, tente a que aparecer e desaparecer quando o cabo for desconectado.

## Prompt pronto para o GPT

Copie e cole o texto abaixo quando quiser pedir uma ajuda mais específica:

```text
Eu quero montar um protótipo de hardware para o projeto NaMosca.

Peças:
- 1x ESP32 DevKit;
- 1x sensor DHT11;
- 3x LEDs;
- 6x cabos macho-macho;
- resistors de 220 ohms, se disponíveis.

Não tenho motor, servo, buzina ou sensor de distância.

Objetivo:
1. ler a temperatura com o DHT11;
2. mostrar a temperatura no Monitor Serial;
3. acender LED verde abaixo de 25 graus;
4. acender LED amarelo entre 25 e 30 graus;
5. acender LED vermelho acima de 30 graus.

Depois quero evoluir para:
1. ESP32 enviar a temperatura por Wi-Fi;
2. backend NaMosca receber a temperatura;
3. backend executar a simulação LIF com os neurônios reais;
4. backend retornar a resposta neural;
5. ESP32 controlar os LEDs pela resposta, e não apenas por um if local.

Eu não entendo de Arduino. Explique como se eu nunca tivesse programmado um microcontrolador.

Preciso de:
- um diagrama de ligação simples;
- uma lista exata de pinos;
- explicação de VCC, DATA e GND;
- instruções para instalar a placa ESP32 no Arduino IDE;
- instruções para instalar a biblioteca DHT;
- explicacao de como usar o Monitor Serial;
- um código inicial simples;
- depois, um segundo código que envie a temperatura via Wi-Fi usando HTTP.

O DHT11 possui quatro pinos: VCC, DATA, NC e GND.

Não use motor nesta primeira etapa.

Não invente uma biblioteca para outro modelo de sensor. Se eu afirmar que o sensor é DHT11, use a biblioteca DHT11.

Explique também como identificar a porta serial do ESP32 e como verificar se o código foi gravado corretamente.
```

## Depois que o teste local funcionar

A etapa seguinte será:

1. criar uma rota no backend para receber temperatura;
2. criar uma rota para transformar temperatura em estímulo;
3. executar o LIF com a sub-rede real;
4. devolver `motor_output`;
5. fazer o ESP32 consumir essa resposta;
6. acender o LED de acordo com a resposta neural.

A comunicação será mais ou menos assim:

```json
{
  "temperature_c": 32.4
}
```

Resposta:

```json
{
  "temperature_c": 32.4,
  "motor_output": {
    "systems": {
      "abdomen": 1200,
      "hind_leg": 500
    }
  }
}
```

A correspondência do LED ficará inicialmente simples:

```text
abdomen → vermelho
hind_leg → amarelo
front_leg ou middle_leg → verde
```

Essa correspondência será apenas uma regra de protótipo. Ela não representa uma resposta biológica comprovada.

## Segurança

- não ligar motor ao ESP32;
- não usar fonte de maior tensão sem verificar o sensor;
- não deixar o DHT11 exposto a água;
- não colocar o DHT11 perto de fontes de calor fortes para o teste;
- usar o cabo USB apenas no primeiro teste;
- desligar o USB antes de trocar fios;
- conferir `VCC`, `DATA` e `GND` antes de ligar.

## Estado atual

Pronto para hardware:

- ESP32;
- DHT11;
- três LEDs;
- plano de ligação;
- código local de teste.

Ainda falta implementar no projeto:

- endpoint de recebimento da temperatura;
- conversão temperatura → estímulo;
- resposta do LIF para o ESP32;
- firmware ESP32 com Wi-Fi.
