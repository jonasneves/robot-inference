import numpy as np
from ..base import RobotBase

NUM_DOF = 23  # G1 humanoid


class UnitreeG1(RobotBase):
    """
    G1 / H1 / H1_2 humanoid adapter over unitree_sdk2py DDS.

    Uses hg (humanoid-go) message type for G1/H1_2.
    Set msg_type: "hg" in config for G1/H1_2, "go" for H1.

    Requires unitree_sdk2py — not on PyPI, install from:
      https://github.com/unitreerobotics/unitree_sdk2_python
    """

    def __init__(self, cfg: dict):
        super().__init__(cfg)
        msg_type = cfg.get("msg_type", "hg")

        try:
            from unitree_sdk2py.core.channel import (
                ChannelPublisher,
                ChannelSubscriber,
                ChannelFactoryInitialize,
            )
        except ImportError:
            raise ImportError(
                "unitree_sdk2py not found.\n"
                "Install from: https://github.com/unitreerobotics/unitree_sdk2_python"
            )

        if msg_type == "hg":
            from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_, LowState_
            from unitree_sdk2py.idl.default import unitree_hg_LowCmd_ as LowCmdDefault
        else:
            from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowCmd_, LowState_
            from unitree_sdk2py.idl.default import unitree_go_LowCmd_ as LowCmdDefault

        net = cfg.get("network_interface", "eth0")
        ChannelFactoryInitialize(0, net)

        self._LowCmd_Default = LowCmdDefault
        self._state = None

        self._pub = ChannelPublisher(cfg.get("lowcmd_topic", "rt/lowcmd"), LowCmd_)
        self._pub.Init()

        sub = ChannelSubscriber(cfg.get("lowstate_topic", "rt/lowstate"), LowState_)
        sub.Init(self._on_state, 10)

    def _on_state(self, msg) -> None:
        self._state = msg

    def observe(self) -> np.ndarray:
        if self._state is None:
            return np.zeros(NUM_DOF * 2 + 9, dtype=np.float32)

        s = self._state
        return np.concatenate([
            s.imu_state.rpy,
            s.imu_state.gyroscope,
            s.imu_state.accelerometer,
            [m.q  for m in s.motor_state[:NUM_DOF]],
            [m.dq for m in s.motor_state[:NUM_DOF]],
        ], dtype=np.float32)

    def act(self, action: np.ndarray) -> None:
        action_scale = self.cfg.get("action_scale", 0.25)
        kp = self.cfg.get("kp", 80.0)
        kd = self.cfg.get("kd", 2.0)

        cmd = self._LowCmd_Default()
        for i in range(NUM_DOF):
            cmd.motor_cmd[i].q   = float(action[i] * action_scale)
            cmd.motor_cmd[i].dq  = 0.0
            cmd.motor_cmd[i].kp  = kp
            cmd.motor_cmd[i].kd  = kd
            cmd.motor_cmd[i].tau = 0.0
        self._pub.Write(cmd)
