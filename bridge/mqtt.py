"""
MQTT bridge — connects mqtt-ai dashboard to the inference runner.

Topics (all prefixed with robot/{id}/):
  command/velocity   {"vx": 0.5, "vy": 0.0, "vyaw": 0.0}
  command/state      "stand_up" | "stand_down" | "damping" | "policy_start" | "policy_stop"
  state              publishes sensor snapshot (periodic)
  policy             publishes {"running": bool, "step": int}
"""

import json
import threading
import time
from typing import Optional

import numpy as np

DEFAULT_BROKER = "broker.hivemq.com"
DEFAULT_PORT   = 1883


class MQTTBridge:
    def __init__(self, cfg: dict):
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            raise ImportError("paho-mqtt not found. Install with: pip install paho-mqtt")

        self._cfg    = cfg
        self._mqtt   = mqtt
        self._client = mqtt.Client()

        broker = cfg.get("mqtt_broker", DEFAULT_BROKER)
        port   = cfg.get("mqtt_port",   DEFAULT_PORT)
        robot_id = cfg.get("robot_id", "robot0")
        self._prefix = f"robot/{robot_id}"

        self._goal_vel   = np.zeros(3, dtype=np.float32)  # vx, vy, vyaw
        self._policy_running = True
        self._lock       = threading.Lock()
        self._step       = 0

        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.connect(broker, port, keepalive=60)

    def _on_connect(self, client, userdata, flags, rc) -> None:
        client.subscribe(f"{self._prefix}/command/#")
        print(f"[mqtt] connected — subscribed to {self._prefix}/command/#")

    def _on_message(self, client, userdata, msg) -> None:
        topic   = msg.topic
        payload = msg.payload.decode("utf-8", errors="replace")

        if topic.endswith("/command/velocity"):
            try:
                d = json.loads(payload)
                with self._lock:
                    self._goal_vel[0] = float(d.get("vx",   0.0))
                    self._goal_vel[1] = float(d.get("vy",   0.0))
                    self._goal_vel[2] = float(d.get("vyaw", 0.0))
            except (json.JSONDecodeError, KeyError, TypeError):
                pass

        elif topic.endswith("/command/state"):
            cmd = payload.strip().lower()
            if cmd == "policy_stop":
                with self._lock:
                    self._policy_running = False
            elif cmd == "policy_start":
                with self._lock:
                    self._policy_running = True
            # stand_up / stand_down / damping handled by caller via is_policy_running()

    def inject_goal(self, obs: np.ndarray, cfg: dict) -> np.ndarray:
        """
        Splice goal velocity into observation vector.
        Expects vel_cmd_idx set in config (index where vx/vy/vyaw live in obs).
        """
        idx = cfg.get("vel_cmd_idx")
        if idx is None:
            return obs
        with self._lock:
            obs[idx:idx + 3] = self._goal_vel
        return obs

    @property
    def goal_vel(self) -> np.ndarray:
        with self._lock:
            return self._goal_vel.copy()

    def is_policy_running(self) -> bool:
        with self._lock:
            return self._policy_running

    def publish_state(self, robot, step: Optional[int] = None) -> None:
        obs = robot.observe()
        payload = json.dumps({
            "joints": obs.tolist(),
            "ts": time.time(),
        })
        self._client.publish(f"{self._prefix}/state", payload)
        if step is not None:
            self._client.publish(
                f"{self._prefix}/policy",
                json.dumps({"running": self._policy_running, "step": step}),
            )

    def start(self) -> None:
        self._client.loop_start()

    def stop(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()
