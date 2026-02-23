# robot-inference

Policy inference runtime for real robots and simulation. Loads a trained ONNX or TorchScript policy and runs it on a robot or MuJoCo sim, with an optional MQTT bridge for AI-driven control from the browser.

## Architecture

```
mqtt-ai / browser dashboard
        │  MQTT (command/velocity, command/state)
        ▼
   MQTT broker
        │  paho-mqtt subscribe
        ▼
  bridge/mqtt.py  ← injects goal velocity into obs
        │
        ▼
    runner.py  → policy(obs) → action
        │
        ▼
  robot adapter  → DDS (unitree_sdk2py) → real robot
               or MuJoCo sim
```

## Quickstart

**1. Install dependencies**
```bash
make setup          # base deps (numpy, pyyaml, paho-mqtt)
make install        # all optional deps (mujoco, onnxruntime, torch)
```

**2. Add a trained policy**

Place your `.onnx` or `.pt` file in `policies/`. Policies are gitignored — train in [unitree_rl_gym](https://github.com/unitreerobotics/unitree_rl_gym) and copy the exported file here.

**3. Run**
```bash
# Mock (no hardware, tests the pipeline)
make run-mock

# MuJoCo sim (requires xml_path set in config)
make run-sim CONFIG=configs/go2_sim.yaml

# Real Go2
make run CONFIG=configs/go2.yaml
```

**4. Control from browser**

Open the dashboard — [deploy link](https://jonasneves.github.io/robot-inference/) or run locally:
```bash
make preview        # http://localhost:8080
```

Connect to the same MQTT broker as your runner config, set the same Robot ID, and use the velocity sliders or AI chat.

## MuJoCo sim setup

Download robot MJCF models from [unitree_mujoco](https://github.com/unitreerobotics/unitree_mujoco) and place them in `resources/`:

```
resources/
  go2/go2.xml
  g1/g1.xml
```

Then set `xml_path: resources/go2/go2.xml` in your config.

## Real robot setup

1. Put the robot in **debug mode**
2. Connect via Ethernet
3. Install `unitree_sdk2py` (not on PyPI):
   ```bash
   git clone https://github.com/unitreerobotics/unitree_sdk2_python
   cd unitree_sdk2_python && pip install -e .
   ```
4. Set `network_interface` in your config to your Ethernet interface (`eth0`, `en0`, `enp3s0`)
5. Run: `make run CONFIG=configs/go2.yaml`

## MQTT bridge

The bridge listens for commands on `robot/{id}/command/#` and publishes state on `robot/{id}/state` and `robot/{id}/policy`.

| Topic | Direction | Payload |
|---|---|---|
| `robot/{id}/command/velocity` | dashboard → runner | `{"vx": 0.5, "vy": 0.0, "vyaw": 0.0}` |
| `robot/{id}/command/state` | dashboard → runner | `"stand_up"` / `"stand_down"` / `"policy_start"` / `"policy_stop"` / `"damping"` |
| `robot/{id}/state` | runner → dashboard | `{"joints": [...], "ts": 1234567890.0}` |
| `robot/{id}/policy` | runner → dashboard | `{"running": true, "step": 1234}` |

Set `mqtt_broker:` to blank in your config to run without MQTT.

## Local MQTT broker (optional)

By default the runner and dashboard use the public HiveMQ cloud broker. For offline/private use:

```bash
make mqtt           # starts Mosquitto on localhost:1883 (MQTT) + 9001 (WebSocket)
```

Then set `mqtt_broker: localhost` in your config and point the dashboard to `ws://localhost:9001`.

## Local Claude proxy (optional)

To use AI chat with your Claude Code subscription instead of an API key:
```bash
make proxy          # http://127.0.0.1:7337
```

Select **Local (claude cli)** in dashboard settings.

## Repo structure

```
runner.py            CLI entry point — loads policy, runs control loop
robots/              Robot hardware adapters
  base.py            Abstract interface: observe() → action
  mock.py            No-hardware mock
  unitree/go2.py     Unitree Go2 (LowCmd/LowState DDS)
  unitree/g1.py      Unitree G1/H1/H1_2
sims/                Simulation backends
  mujoco.py          MuJoCo sim2real validation
  mock.py            Headless mock sim
bridge/mqtt.py       MQTT ↔ runner bridge
configs/             Per-robot YAML configs
policies/            Trained policy files (gitignored)
dashboard/           Browser control UI
docker/              Local Mosquitto broker
local-proxy.js       Claude Code proxy for AI chat
```
