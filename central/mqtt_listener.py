import json
import logging
from typing import Callable

logger = logging.getLogger(__name__)


class CentralMQTTListener:
    """Componente central que recebe mensagens do Raspberry Pi."""

    def __init__(
        self,
        store,
        broker: str = "localhost",
        port: int = 1883,
        topic: str = "ctrlab/raspberry/status",
        command_topic: str = "ctrlab/central/commands",
    ):
        self.store = store
        self.broker = broker
        self.port = port
        self.topic = topic
        self.command_topic = command_topic
        self._mqtt_module = None
        self._client = None
        self._handler = None
        self._connected = False

        try:
            import paho.mqtt.client as mqtt
            self._mqtt_module = mqtt
        except ImportError:  # pragma: no cover - depende do ambiente
            logger.warning("paho-mqtt não está instalado; listener central em modo mock.")
            return

        self._client = self._mqtt_module.Client(client_id="ctrlab_central")
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

    def connect(self):
        if self._client is None:
            return False

        try:
            self._client.connect(self.broker, self.port, 10)
            self._client.loop_start()
            return True
        except Exception as exc:  # pragma: no cover
            logger.warning("Falha ao conectar ao broker central: %s", exc)
            return False

    def subscribe(self):
        if self._client is None:
            return False

        try:
            self._client.subscribe(self.topic, qos=1)
            return True
        except Exception as exc:  # pragma: no cover
            logger.warning("Falha ao assinar tópico %s: %s", self.topic, exc)
            return False

    def set_handler(self, handler: Callable[[dict], None]):
        self._handler = handler

    @property
    def connected(self) -> bool:
        return self._connected

    def set_access_model_enabled(self, enabled: bool):
        if not isinstance(enabled, bool):
            raise ValueError("O estado do modelo de acesso deve ser booleano.")
        if self._client is None or not self._connected:
            return False

        payload = json.dumps(
            {"command": "set_access_model", "enabled": enabled}
        )
        try:
            result = self._client.publish(self.command_topic, payload, qos=1)
            if result.rc != 0:
                logger.warning("Broker recusou o comando de acesso via MQTT: código %s", result.rc)
                return False
            return True
        except Exception as exc:  # pragma: no cover - comunicação externa
            logger.warning("Falha ao enviar comando de acesso via MQTT: %s", exc)
            return False

    def _on_connect(self, client, userdata, flags, rc):
        self._connected = rc == 0
        logger.info("Conectado ao broker central com código %s", rc)
        if self._connected:
            self.subscribe()

    def _on_disconnect(self, client, userdata, rc, *extra):
        self._connected = False
        logger.info("Desconectado do broker central com código %s", rc)

    def _on_message(self, client, userdata, message):
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            payload = {}

        if self._handler is not None:
            self._handler(payload)

        if self.store is not None:
            self.store.save_payload(payload)

    def disconnect(self):
        if self._client is not None:
            self._client.loop_stop()
            self._client.disconnect()
        self._connected = False
