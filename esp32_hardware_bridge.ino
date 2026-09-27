#include <WiFi.h>
#include <HTTPClient.h>
#include <WebServer.h>
#include <ArduinoJson.h>

// ============================================================
// CONFIGURAÇÃO DO HARDWARE
// ============================================================

// LED conectado:
// GPIO 12 -> resistor 220Ω -> ânodo LED
// cátodo LED -> GND

#define LED_PIN 12

// ============================================================
// CONFIGURAÇÃO DO WI-FI
// ============================================================

#define WIFI_SSID "WIFI NICOLETTI"
#define WIFI_PASSWORD "nicoletti2208"

// ============================================================
// CONFIGURAÇÃO DO BACKEND
// ============================================================

#define BACKEND_URL "http://192.168.10.129:8000/api/simulate"

// ============================================================
// CONFIGURAÇÃO DO SERVIDOR HTTP LOCAL (ESP32)
// ============================================================

// O ESP32 vai subir um servidor HTTP na porta 80.
// O frontend vai mandar POST /led com o estado das pernas.

#define ESP_HTTP_PORT 80

// ============================================================
// MODO DE TESTE
// ============================================================

#define HARDWARE_TEST_MODE false

// ============================================================
// TEMPOS
// ============================================================

const unsigned long WIFI_CONNECT_TIMEOUT = 15000;
const unsigned long SIMULATION_INTERVAL = 5000;
const unsigned long WIFI_BLINK_INTERVAL = 300;

// Tempo que o LED fica ligado quando recebe sinal de "perna ativa".
const unsigned long LED_ON_DURATION = 800;

// ============================================================
// ESTADO
// ============================================================

unsigned long lastSimulation = 0;
unsigned long lastWifiBlink = 0;
unsigned long ledOnUntil = 0;

bool ledState = false;

// ============================================================
// SERVIDOR HTTP
// ============================================================

WebServer server(ESP_HTTP_PORT);

// ============================================================
// FUNÇÕES DO LED
// ============================================================

void ledOn() {
  digitalWrite(LED_PIN, HIGH);
  ledState = true;
}

void ledOff() {
  digitalWrite(LED_PIN, LOW);
  ledState = false;
}

// ============================================================
// HANDLERS DO SERVIDOR HTTP
// ============================================================

void sendCorsHeaders() {
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.sendHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  server.sendHeader("Access-Control-Allow-Headers", "Content-Type");
}

void handleLedOn() {
  sendCorsHeaders();
  ledOn();
  ledOnUntil = millis() + LED_ON_DURATION;
  server.send(200, "application/json", "{\"status\":\"ok\",\"led\":\"on\"}");
}

void handleLedOff() {
  sendCorsHeaders();
  ledOff();
  ledOnUntil = 0;
  server.send(200, "application/json", "{\"status\":\"ok\",\"led\":\"off\"}");
}

void handleLegMove() {
  sendCorsHeaders();
  
  // Recebe POST /leg-move
  // Corpo JSON: {"active": true/false, "system": "front_leg"/"middle_leg"/"hind_leg"}
  
  if (server.hasArg("plain")) {
    String body = server.arg("plain");
    JsonDocument doc;
    DeserializationError error = deserializeJson(doc, body);
    
    if (!error) {
      bool active = doc["active"] | false;
      const char* system = doc["system"] | "unknown";
      
      Serial.print("Movimento recebido: ");
      Serial.print(system);
      Serial.print(" | active=");
      Serial.println(active ? "true" : "false");
      
      if (active) {
        ledOn();
        ledOnUntil = millis() + LED_ON_DURATION;
      } else {
        ledOff();
        ledOnUntil = 0;
      }
      
      server.send(200, "application/json", "{\"status\":\"ok\",\"led\":\"on\"}");
      return;
    }
  }
  
  server.send(400, "application/json", "{\"error\":\"invalid json\"}");
}

void handleStatus() {
  sendCorsHeaders();
  String json = "{\"led\":\"";
  json += ledState ? "on" : "off";
  json += "\",\"uptime_ms\":";
  json += String(millis());
  json += "}";
  server.send(200, "application/json", json);
}

void handleOptions() {
  sendCorsHeaders();
  server.send(200, "application/json", "");
}

void handleNotFound() {
  sendCorsHeaders();
  server.send(404, "application/json", "{\"error\":\"not found\"}");
}

// ============================================================
// CONEXÃO WI-FI
// ============================================================

bool connectWiFi() {
  Serial.println();
  Serial.println("=================================");
  Serial.println("Conectando ao Wi-Fi...");
  Serial.print("Rede: ");
  Serial.println(WIFI_SSID);
  Serial.println("=================================");

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long startTime = millis();
  bool blinkState = false;

  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - startTime >= WIFI_CONNECT_TIMEOUT) {
      Serial.println();
      Serial.println("ERRO: timeout ao conectar ao Wi-Fi.");
      ledOff();
      return false;
    }

    if (millis() - lastWifiBlink >= WIFI_BLINK_INTERVAL) {
      lastWifiBlink = millis();
      blinkState = !blinkState;
      digitalWrite(LED_PIN, blinkState);
    }
    delay(10);
  }

  ledOff();

  Serial.println();
  Serial.println("Wi-Fi conectado!");
  Serial.print("IP do ESP32: ");
  Serial.println(WiFi.localIP());
  Serial.print("RSSI: ");
  Serial.print(WiFi.RSSI());
  Serial.println(" dBm");
  Serial.println();

  return true;
}

// ============================================================
// VERIFICA SE EXISTE UMA ROTA PARA PERNA
// ============================================================

bool hasLegResponse(JsonObject motorOutput) {
  if (motorOutput.isNull()) {
    Serial.println("motor_output não encontrado.");
    return false;
  }

  JsonObject systems = motorOutput["systems"];
  if (systems.isNull()) {
    Serial.println("motor_output.systems não encontrado.");
    return false;
  }

  if (systems["front_leg"].is<float>() || systems["front_leg"].is<int>() || systems["front_leg"].is<long>()) {
    Serial.println("Encontrado: front_leg");
    return true;
  }

  if (systems["middle_leg"].is<float>() || systems["middle_leg"].is<int>() || systems["middle_leg"].is<long>()) {
    Serial.println("Encontrado: middle_leg");
    return true;
  }

  if (systems["hind_leg"].is<float>() || systems["hind_leg"].is<int>() || systems["hind_leg"].is<long>()) {
    Serial.println("Encontrado: hind_leg");
    return true;
  }

  return false;
}

// ============================================================
// SIMULAÇÃO NO NAMOSCA
// ============================================================

void simulateNaMosca() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println();
    Serial.println("Wi-Fi desconectado.");
    Serial.println("LED desligado por segurança.");
    ledOff();
    return;
  }

  Serial.println();
  Serial.println("=================================");
  Serial.println("Consultando NaMosca...");
  Serial.println("=================================");

  HTTPClient http;
  http.setConnectTimeout(10000);
  http.setTimeout(40);

  Serial.print("POST: ");
  Serial.println(BACKEND_URL);

  if (!http.begin(BACKEND_URL)) {
    Serial.println("ERRO: não foi possível iniciar HTTP.");
    ledOff();
    return;
  }

  http.addHeader("Content-Type", "application/json");

  const char* payload = R"json(
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
    "neuron_ids": ["720575940628875688"],
    "intensity": 6,
    "duration_ms": 200
  },
  "engine": "lif"
}
)json";

  Serial.println("Enviando simulação...");

  int httpCode = http.POST(payload);

  Serial.print("HTTP status: ");
  Serial.println(httpCode);

  if (httpCode <= 0) {
    Serial.print("ERRO HTTP: ");
    Serial.println(http.errorToString(httpCode));
    Serial.println("LED desligado.");
    ledOff();
    http.end();
    return;
  }

  if (httpCode != HTTP_CODE_OK) {
    Serial.println("Backend retornou erro.");
    String errorBody = http.getString();
    Serial.println("Resposta do backend:");
    Serial.println(errorBody);
    Serial.println("LED desligado.");
    ledOff();
    http.end();
    return;
  }

  Serial.println("Backend respondeu com sucesso.");

  String body = http.getString();
  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, body);

  if (error) {
    Serial.print("ERRO ao interpretar JSON: ");
    Serial.println(error.c_str());
    Serial.println("LED desligado.");
    ledOff();
    http.end();
    return;
  }

  JsonObject stats = doc["stats"];
  if (!stats.isNull()) {
    int totalSpikes = stats["total_spikes"] | 0;
    int respondingNeurons = stats["responding_neurons"] | 0;
    Serial.println();
    Serial.println("----- RESPOSTA NEURAL -----");
    Serial.print("Total de spikes: ");
    Serial.println(totalSpikes);
    Serial.print("Neurônios respondendo: ");
    Serial.println(respondingNeurons);
  }

  JsonObject motorOutput = doc["motor_output"];
  bool legDetected = hasLegResponse(motorOutput);

  JsonArray activeDmTypes = motorOutput["active_dm_types"];
  Serial.print("Dm ativos: ");
  if (activeDmTypes.isNull()) {
    Serial.println("nenhum");
  } else {
    bool first = true;
    for (JsonVariant dm : activeDmTypes) {
      if (!first) Serial.print(", ");
      Serial.print(dm.as<const char*>());
      first = false;
    }
    Serial.println();
  }

  JsonObject systems = motorOutput["systems"];
  Serial.print("Sistemas: ");
  if (systems.isNull()) {
    Serial.println("nenhum");
  } else {
    bool first = true;
    for (JsonPair system : systems) {
      if (!first) Serial.print(", ");
      Serial.print(system.key().c_str());
      Serial.print("=");
      Serial.print(system.value().as<float>());
      first = false;
    }
    Serial.println();
  }

  Serial.println();
  if (legDetected) {
    Serial.println(">>> ROTA PARA PERNA DETECTADA");
    Serial.println(">>> LED ON");
    ledOn();
  } else {
    Serial.println(">>> NENHUMA ROTA PARA PERNA");
    Serial.println(">>> LED OFF");
    ledOff();
  }

  Serial.println("============================");
  Serial.println();

  http.end();
}

// ============================================================
// MODO TESTE DO HARDWARE
// ============================================================

void hardwareTest() {
  Serial.println();
  Serial.println("=================================");
  Serial.println("MODO TESTE DE HARDWARE");
  Serial.println("Backend NÃO está sendo usado.");
  Serial.println("=================================");

  ledOn();
  Serial.println("LED ON");
  delay(500);
  ledOff();
  Serial.println("LED OFF");
  delay(500);
}

// ============================================================
// SETUP
// ============================================================

void setup() {
  Serial.begin(115200);
  delay(500);

  pinMode(LED_PIN, OUTPUT);
  ledOff();

  Serial.println();
  Serial.println("=================================");
  Serial.println("NaMosca ESP32");
  Serial.println("Neural Hardware Bridge");
  Serial.println("=================================");

  Serial.print("LED GPIO: ");
  Serial.println(LED_PIN);

#if HARDWARE_TEST_MODE
  Serial.println();
  Serial.println("MODO TESTE ATIVADO.");
  Serial.println("O backend não será consultado.");
  return;
#endif

  connectWiFi();

  // Configura o servidor HTTP local
  server.on("/led/on", HTTP_GET, handleLedOn);
  server.on("/led/off", HTTP_GET, handleLedOff);
  server.on("/leg-move", HTTP_POST, handleLegMove);
  server.on("/leg-move", HTTP_OPTIONS, handleOptions);
  server.on("/status", HTTP_GET, handleStatus);
  server.onNotFound(handleNotFound);
  server.begin();

  Serial.println();
  Serial.println("=================================");
  Serial.println("Servidor HTTP iniciado!");
  Serial.print("URL: http://");
  Serial.print(WiFi.localIP());
  Serial.println("/");
  Serial.println();
  Serial.println("Endpoints:");
  Serial.println("  GET  /led/on     -> liga o LED");
  Serial.println("  GET  /led/off    -> desliga o LED");
  Serial.println("  POST /leg-move   -> recebe movimento das pernas");
  Serial.println("  GET  /status     -> estado atual");
  Serial.println("=================================");
  Serial.println();
}

// ============================================================
// LOOP
// ============================================================

void loop() {
#if HARDWARE_TEST_MODE
  hardwareTest();
  return;
#endif

  // Processa requisições HTTP do frontend
  server.handleClient();

  // Verifica se o tempo do LED expirou
  if (ledOnUntil > 0 && millis() >= ledOnUntil) {
    ledOff();
    ledOnUntil = 0;
  }

  // Verifica Wi-Fi
  if (WiFi.status() != WL_CONNECTED) {
    ledOff();
    Serial.println("Wi-Fi desconectado. Tentando reconectar...");
    connectWiFi();
    return;
  }

  // LED agora é controlado apenas pelo frontend via /leg-move
  // A consulta automática ao backend foi desativada para conflitar com o LED
}
