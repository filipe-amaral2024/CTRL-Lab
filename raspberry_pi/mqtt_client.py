import json
import logging
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


class MQTTClientWrapper:
    """Envelope para comunicação MQTT do Raspberry Pi."""

    def __init__(self, config, client_id: str = "ctrlab_raspberry"):
        self.config = config
        self.client_id = client_id
        self._mqtt_module = None
        self._client = None
        self._connected = False
        self._callbacks: List[Callable] = []

        try:
            import paho.mqtt.client as mqtt
            self._mqtt_module = mqtt
        except ImportError:  # pragma: no cover - depende do ambiente
            logger.warning("paho-mqtt não está instalado; MQTT desativado.")
            return

        self._client = self._mqtt_module.Client(client_id=self.client_id)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

    def add_callback(self, callback: Callable):
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def connect(self):
        if self._client is None:
            return False

        try:
            self._client.connect(self.config.mqtt_broker, self.config.mqtt_port, 10)
            self._client.loop_start()
            return True
        except Exception as exc:  # pragma: no cover - depende da rede
            logger.warning("Falha ao conectar ao broker MQTT: %s", exc)
            return False

    def subscribe(self, topic: str):
        if self._client is None:
            return False
        try:
            self._client.subscribe(topic, qos=1)
            return True
        except Exception as exc:  # pragma: no cover
            logger.warning("Falha ao assinar tópico %s: %s", topic, exc)
            return False

    def publish_status(self, payload: dict):
        if self._client is None:
            return False

        try:
            self._client.publish(self.config.status_topic, json.dumps(payload), qos=1)
            return True
        except Exception as exc:  # pragma: no cover
            logger.warning("Erro ao publicar status: %s", exc)
            return False

    def publish_alert(self, payload: dict):
        if self._client is None:
            return False

        try:
            self._client.publish(self.config.alert_topic, json.dumps(payload), qos=1)
            return True
        except Exception as exc:  # pragma: no cover
            logger.warning("Erro ao publicar alerta: %s", exc)
            return False

    def _on_connect(self, client, userdata, flags, rc):
        self._connected = rc == 0
        logger.info("Conectado ao broker MQTT com código %s", rc)
        self.subscribe(self.config.command_topic)

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        logger.info("Desconectado do broker MQTT com código %s", rc)

    def _on_message(self, client, userdata, message):
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            payload = message.payload.decode("utf-8", errors="ignore")

        for callback in self._callbacks:
            callback(payload)

    def disconnect(self):
        if self._client is not None:
            self._client.loop_stop()
            self._client.disconnect()
        self._connected = False

    @property
    def connected(self):
        return self._connected
