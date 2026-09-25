"""Sessão WebSocket para transmitir picos com baixa latência."""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from fastapi import WebSocket

from app.schemas import Network, SimulationConfig, Stimulus
from app.simulation import LIFSimulator, StepResult, _frame_from_step


class RealtimeSession:
    """Controla um simulador leve e transmite seus quadros a um cliente."""

    def __init__(
        self,
        websocket: WebSocket,
        network: Network,
        *,
        config: SimulationConfig | None = None,
        include_voltage: bool = False,
        legacy_payload: bool = False,
    ) -> None:
        self.websocket = websocket
        self.network = network
        self.config = config or SimulationConfig()
        self.include_voltage = include_voltage
        self.legacy_payload = legacy_payload
        self.simulator = LIFSimulator(network, self.config)
        self.zero_input = np.zeros(self.simulator.neuron_count, dtype=np.float32)
        self.pulse_input = self.zero_input
        self.pulse_end = 0.0
        self._recent_activity_ms: dict[str, float] = {}
        self.stop_event = asyncio.Event()
        self.loop = asyncio.get_running_loop()

    async def run(self) -> None:
        """Envia os metadados do grafo e transmite quadros até desconectar ou receber uma parada."""

        await self.websocket.send_json(
            {
                "type": "ready",
                "network": self.network.model_dump(mode="json"),
                "config": self.config.model_dump(mode="json"),
                # Os campos de compatibilidade impedem que clientes simples
                # confundam os metadados iniciais com um quadro de picos.
                "time": 0.0,
                "spikes": [],
                "neurons": [],
                "message": "Send {type: pulse} to inject current into visual neurons.",
            }
        )
        sender = asyncio.create_task(self._sender(), name="neural-stream-sender")
        receiver = asyncio.create_task(self._receiver(), name="neural-stream-receiver")
        done, pending = await asyncio.wait(
            {sender, receiver},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        for task in done:
            # Consome os erros das tarefas para que uma desconexão do cliente
            # não produza um aviso de tarefa não tratada durante o encerramento.
            try:
                task.result()
            except asyncio.CancelledError:
                pass
            except Exception:
                # O WebSocket pode já estar fechado; neste momento não há um
                # segundo canal seguro para informar o erro.
                pass

    async def _sender(self) -> None:
        """Avança a simulação e envia quadros no ritmo configurado."""

        next_tick = self.loop.time()
        while not self.stop_event.is_set():
            frame_stride = max(1, int(round(self.config.frame_interval_ms / self.config.dt_ms)))
            now = self.loop.time()
            delay = next_tick - now
            if delay > 0:
                await asyncio.sleep(delay)
            active_input = self.pulse_input if now < self.pulse_end else self.zero_input
            try:
                result = await asyncio.to_thread(self.simulator.step, active_input)
            except Exception as exc:
                await self._send_error(f"simulation failed: {exc}")
                return
            now = self.loop.time()
            should_send = (
                self.simulator._step_index % frame_stride == 0
                or (result.spikes.size and not self.legacy_payload)
            )
            if should_send:
                # Envia um quadro no ritmo configurado. Incluir um quadro
                # sempre que houver um pico mantém pulsos curtos visíveis,
                # mesmo quando o cliente escolhe um intervalo longo.
                frame = _frame_from_step(
                    self.simulator,
                    result,
                    max_spikes=self.config.max_spikes_per_frame,
                    include_voltage=self.include_voltage,
                )
                spike_ids = [
                    self.simulator.neuron_ids[int(index)]
                    for index in result.spikes[: self.config.max_spikes_per_frame]
                ]
                for neuron_id in spike_ids:
                    self._recent_activity_ms[neuron_id] = result.t_ms
                # Limita o cache de atividade de compatibilidade independentemente
                # do tamanho completo do grafo.
                cutoff = result.t_ms - 250.0
                self._recent_activity_ms = {
                    neuron_id: timestamp
                    for neuron_id, timestamp in self._recent_activity_ms.items()
                    if timestamp >= cutoff
                }
                payload: dict[str, Any] = {
                    "type": "frame",
                    **frame.model_dump(mode="json"),
                }
                if self.legacy_payload:
                    payload.update(
                        {
                            "time": round(result.t_ms, 3),
                            "spikes": spike_ids,
                            "neurons": self._legacy_neurons(result),
                        }
                    )
                await self.websocket.send_json(payload)
            next_tick += self.config.dt_ms / 1000.0
            # Recupera o ritmo se um cliente lento pausar o loop de eventos.
            if next_tick < now - self.config.dt_ms / 1000.0:
                next_tick = now

    def _legacy_neurons(self, result: StepResult) -> list[dict[str, Any]]:
        """Monta o formato de estado usado pela interface da demonstração original."""

        spike_ids = {self.simulator.neuron_ids[int(index)] for index in result.spikes}
        visible = {
            neuron_id
            for neuron_id, timestamp in self._recent_activity_ms.items()
            if result.t_ms - timestamp <= 50.0
        }
        visible.update(spike_ids)
        payload: list[dict[str, Any]] = []
        for index, neuron in enumerate(self.network.neurons):
            neuron_id = neuron.id
            if neuron_id not in visible:
                continue
            payload.append(
                {
                    "id": neuron_id,
                    "V_mem": round(float(result.voltages[index]), 2),
                    "spike": neuron_id in spike_ids,
                    "x": neuron.x,
                    "y": neuron.y,
                    "z": neuron.z,
                }
            )
        return payload

    def inject(self, stimulus: Stimulus) -> int:
        """Aplica um pulso nesta sessão e devolve a quantidade de alvos."""

        vector = self.simulator.stimulus_vector(stimulus, region=self.network.region)
        self.pulse_input = vector
        self.pulse_end = self.loop.time() + stimulus.duration_ms / 1000.0
        return int(np.count_nonzero(vector))

    async def _receiver(self) -> None:
        """Processa pequenas mensagens JSON de controle sem bloquear o envio."""

        while True:
            message = await self.websocket.receive_json()
            if not isinstance(message, dict):
                await self._send_error("control message must be a JSON object")
                continue
            message_type = str(message.get("type", "")).lower()
            # Aceita os comandos {"action": "inject", ...} do protótipo,
            # além do protocolo versionado {"type": "pulse", ...}.
            if not message_type:
                action = str(message.get("action", "")).lower()
                message_type = {
                    "inject": "pulse",
                    "get_state": "state",
                    "reset": "reset",
                    "stop": "stop",
                    "start": "start",
                }.get(action, "")
            if message_type == "pulse":
                try:
                    legacy_ids = message.get("neuron_ids", [])
                    if not legacy_ids and message.get("neuron_id"):
                        legacy_ids = [message["neuron_id"]]
                    stimulus = Stimulus.model_validate(
                        {
                            "neuron_ids": legacy_ids,
                            "role": message.get("role"),
                            "intensity": message.get(
                                "intensity", message.get("current", 1.5)
                            ),
                            "duration_ms": message.get("duration_ms", 100),
                        }
                    )
                    vector = self.simulator.stimulus_vector(
                        stimulus,
                        region=self.network.region,
                    )
                    self.inject(stimulus)
                except (ValueError, TypeError) as exc:
                    await self._send_error(f"invalid pulse: {exc}")
                    continue
                await self.websocket.send_json(
                    {
                        "type": "pulse_accepted",
                        "duration_ms": stimulus.duration_ms,
                        "intensity": stimulus.intensity,
                        "target_count": int(np.count_nonzero(vector)),
                    }
                )
            elif message_type == "state":
                now_ms = self.simulator._step_index * self.config.dt_ms
                await self.websocket.send_json(
                    {
                        "type": "state",
                        "time": round(now_ms, 3),
                        "spikes": [
                            self.simulator.neuron_ids[index]
                            for index, responded in enumerate(self.simulator.responding)
                            if responded
                        ],
                        "neurons": self._legacy_neurons(
                            StepResult(
                                t_ms=now_ms,
                                spikes=np.asarray([], dtype=np.int32),
                                voltages=self.simulator.voltage,
                                total_spikes=self.simulator.total_spikes,
                            )
                        ),
                    }
                )
            elif message_type == "start":
                await self._start(message.get("config"))
            elif message_type == "reset":
                self.simulator.reset()
                self.pulse_end = 0.0
                self.pulse_input = self.zero_input
                await self.websocket.send_json({"type": "reset"})
            elif message_type == "stop":
                self.stop_event.set()
                await self.websocket.send_json({"type": "stopped"})
                return
            elif message_type == "ping":
                await self.websocket.send_json({"type": "pong"})
            else:
                await self._send_error(f"unknown message type: {message_type or '<empty>'}")

    async def _start(self, raw_config: Any) -> None:
        """Reinicia a sessão com uma configuração validada."""

        if raw_config is not None and not isinstance(raw_config, dict):
            await self._send_error("config must be an object")
            return
        try:
            config = SimulationConfig.model_validate(raw_config or {})
            # Recria apenas o pequeno objeto de estado; a rede é compartilhada
            # por referência e não é baixada novamente.
            self.config = config
            self.simulator = LIFSimulator(self.network, config)
            self.zero_input = np.zeros(self.simulator.neuron_count, dtype=np.float32)
            self.pulse_input = self.zero_input
            self.pulse_end = 0.0
        except (ValueError, TypeError) as exc:
            await self._send_error(f"invalid config: {exc}")
            return
        await self.websocket.send_json({"type": "started", "config": config.model_dump(mode="json")})

    async def _send_error(self, message: str) -> None:
        """Tenta informar um erro sem interromper a limpeza da sessão."""

        try:
            await self.websocket.send_json({"type": "error", "message": message})
        except Exception:
            # O cliente pode ter desconectado entre a simulação e o envio
            # do erro; a limpeza externa da tarefa cuida do fluxo.
            return
