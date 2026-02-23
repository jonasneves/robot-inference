import numpy as np
from ..base import RobotBase

NUM_DOF = 12

# Default standing joint positions (rad) — from unitree_rl_gym
DEFAULT_Q = np.array([
     0.00,  0.80, -1.50,  # FL: hip, thigh, calf
     0.00,  0.80, -1.50,  # FR
     0.00,  1.00, -1.50,  # RL
     0.00,  1.00, -1.50,  # RR
], dtype=np.float32)


class UnitreeGo2(RobotBase):
    """
    Go2 adapter over unitree_sdk2py DDS (LowCmd/LowState).

    Requires unitree_sdk2py — not on PyPI, install from:
      https://github.com/unitreerobotics/unitree_sdk2_python

    Robot must be in debug mode before running.
    Set network_interface in your config to the Ethernet interface
    connected to the robot (e.g. eth0, en0, enp3s0).
    """

    def __init__(self, cfg: dict):
        super().__init__(cfg)
        try:
            from unitree_sdk2py.core.channel import (
                ChannelPublisher,
                ChannelSubscriber,
                ChannelFactoryInitialize,
            )
            from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowCmd_, LowState_
            from unitree_sdk2py.idl.default import unitree_go_LowCmd_
        except ImportError:
            raise ImportError(
                "unitree_sdk2py not found.\n"
                "Install from: https://github.com/unitreerobotics/unitree_sdk2_python"
            )

        net = cfg.get("network_interface", "eth0")
        ChannelFactoryInitialize(0, net)

        self._LowCmd_ = LowCmd_
        self._unitree_go_LowCmd_ = unitree_go_LowCmd_

        self._pub = ChannelPublisher(cfg.get("lowcmd_topic", "rt/lowcmd"), LowCmd_)
        self._pub.Init()

        self._state = None
        sub = ChannelSubscriber(cfg.get("lowstate_topic", "rt/lowstate"), LowState_)
        sub.Init(self._on_state, 10)

    def _on_state(self, msg) -> None:
        self._state = msg

    def observe(self) -> np.ndarray:
        if self._state is None:
            return np.zeros(45, dtype=np.float32)

        s = self._state
        return np.concatenate([
            s.imu_state.rpy[:2],               # roll, pitch         (2)
            s.imu_state.gyroscope,             # angular velocity    (3)
            s.imu_state.accelerometer,         # linear accel        (3)
            [m.q  for m in s.motor_state[:NUM_DOF]],  # joint pos   (12)
            [m.dq for m in s.motor_state[:NUM_DOF]],  # joint vel   (12)
            [m.tau_est for m in s.motor_state[:NUM_DOF]],  # torque (12)
            s.foot_force,                      # foot contact forces  (4) — go2 has 4 feet
        ], dtype=np.float32)  # total: 48

    def act(self, action: np.ndarray) -> None:
        action_scale = self.cfg.get("action_scale", 0.25)
        kp = self.cfg.get("kp", 20.0)
        kd = self.cfg.get("kd", 0.5)

        cmd = self._unitree_go_LowCmd_()
        for i in range(NUM_DOF):
            cmd.motor_cmd[i].q   = float(DEFAULT_Q[i] + action[i] * action_scale)
            cmd.motor_cmd[i].dq  = 0.0
            cmd.motor_cmd[i].kp  = kp
            cmd.motor_cmd[i].kd  = kd
            cmd.motor_cmd[i].tau = 0.0
        self._pub.Write(cmd)

    def reset(self) -> None:
        cmd = self._unitree_go_LowCmd_()
        kp = self.cfg.get("kp", 20.0)
        kd = self.cfg.get("kd", 0.5)
        for i in range(NUM_DOF):
            cmd.motor_cmd[i].q   = float(DEFAULT_Q[i])
            cmd.motor_cmd[i].dq  = 0.0
            cmd.motor_cmd[i].kp  = kp
            cmd.motor_cmd[i].kd  = kd
            cmd.motor_cmd[i].tau = 0.0
        self._pub.Write(cmd)
