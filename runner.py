#!/usr/bin/env python3
"""
robot-inference runner — loads a policy and runs it on a robot or sim.

Usage:
  python runner.py --config configs/go2.yaml
  python runner.py --config configs/go2.yaml --sim        # MuJoCo sim
  python runner.py --config configs/go2.yaml --mock       # no hardware
"""

import argparse
import time

import numpy as np
import yaml


def load_policy(path: str):
    """Load an ONNX or TorchScript policy. Returns a callable: obs -> action."""
    if path.endswith(".onnx"):
        try:
            import onnxruntime as ort
        except ImportError:
            raise ImportError("onnxruntime not found. Install with: pip install onnxruntime")
        session    = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
        input_name = session.get_inputs()[0].name
        def run_onnx(obs: np.ndarray) -> np.ndarray:
            return session.run(None, {input_name: obs[None].astype(np.float32)})[0][0]
        return run_onnx

    # TorchScript fallback
    try:
        import torch
    except ImportError:
        raise ImportError("torch not found. Install with: pip install torch")
    model = torch.jit.load(path)
    model.eval()
    def run_torch(obs: np.ndarray) -> np.ndarray:
        with torch.no_grad():
            return model(torch.from_numpy(obs[None]).float()).numpy()[0]
    return run_torch


def build_robot(cfg: dict, sim: bool, mock: bool):
    if mock:
        from robots.mock import MockRobot
        return MockRobot(cfg)

    if sim:
        from sims.mujoco import MuJoCoSim
        return MuJoCoSim(cfg)

    robot_type = cfg["robot"]
    if robot_type == "unitree_go2":
        from robots.unitree.go2 import UnitreeGo2
        return UnitreeGo2(cfg)
    if robot_type in ("unitree_g1", "unitree_h1", "unitree_h1_2"):
        from robots.unitree.g1 import UnitreeG1
        return UnitreeG1(cfg)

    raise ValueError(f"Unknown robot type: {robot_type!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a policy on a robot or sim")
    parser.add_argument("--config", required=True, help="Path to YAML config")
    parser.add_argument("--sim",  action="store_true", help="Use MuJoCo sim backend")
    parser.add_argument("--mock", action="store_true", help="Use mock robot (no hardware)")
    parser.add_argument("--no-mqtt", action="store_true", help="Disable MQTT bridge")
    args = parser.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    robot  = build_robot(cfg, args.sim, args.mock)
    policy = load_policy(cfg["policy"])

    bridge = None
    if not args.no_mqtt and cfg.get("mqtt_broker"):
        from bridge.mqtt import MQTTBridge
        bridge = MQTTBridge(cfg)
        bridge.start()

    dt      = cfg.get("control_dt", 0.02)
    hz      = 1.0 / dt
    max_steps = cfg.get("max_steps", 0)  # 0 = run forever

    print(f"Running at {hz:.0f} Hz — Ctrl+C to stop")
    if bridge:
        print(f"MQTT bridge active on broker: {cfg.get('mqtt_broker')}")

    step = 0
    try:
        while True:
            t0 = time.perf_counter()

            if bridge and not bridge.is_policy_running():
                time.sleep(dt)
                continue

            obs    = robot.observe()
            if bridge:
                obs = bridge.inject_goal(obs, cfg)
            action = policy(obs)
            robot.act(action)

            if bridge and step % cfg.get("publish_every", 5) == 0:
                bridge.publish_state(robot, step)

            step += 1
            if max_steps and step >= max_steps:
                break

            elapsed   = time.perf_counter() - t0
            remaining = dt - elapsed
            if remaining > 0:
                time.sleep(remaining)
            elif remaining < -dt * 0.1:
                print(f"[warn] loop overrun: {-remaining * 1000:.1f}ms late at step {step}")

    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        robot.close()
        if bridge:
            bridge.stop()


if __name__ == "__main__":
    main()
