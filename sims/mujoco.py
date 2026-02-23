import numpy as np
from robots.base import RobotBase


class MuJoCoSim(RobotBase):
    """
    MuJoCo simulation backend for sim2real validation.

    Requires: pip install mujoco

    Set xml_path in config to your robot's MJCF model file.
    Download Unitree models from:
      https://github.com/unitreerobotics/unitree_mujoco
    """

    def __init__(self, cfg: dict):
        super().__init__(cfg)
        try:
            import mujoco
            import mujoco.viewer
        except ImportError:
            raise ImportError("mujoco not found. Install with: pip install mujoco")

        self._mj = mujoco
        xml = cfg.get("xml_path")
        if not xml:
            raise ValueError("xml_path required in config for MuJoCo sim")

        self._model = mujoco.MjModel.from_xml_path(xml)
        self._data  = mujoco.MjData(self._model)
        self._viewer = None

        if cfg.get("render", True):
            self._viewer = mujoco.viewer.launch_passive(self._model, self._data)

        self._action_dim = self._model.nu
        self._obs_dim    = cfg.get("obs_dim", 48)

    def observe(self) -> np.ndarray:
        d = self._data
        qpos = d.qpos[7:]          # skip root pos+quat (freejoint)
        qvel = d.qvel[6:]          # skip root vel
        imu_gyro = d.sensor("gyro").data  if "gyro" in [self._model.sensor(i).name for i in range(self._model.nsensor)] else np.zeros(3)
        return np.concatenate([imu_gyro, qpos, qvel], dtype=np.float32)

    def act(self, action: np.ndarray) -> None:
        action_scale = self.cfg.get("action_scale", 0.25)
        self._data.ctrl[:] = action * action_scale
        self._mj.mj_step(self._model, self._data)
        if self._viewer is not None:
            self._viewer.sync()

    def reset(self) -> None:
        self._mj.mj_resetData(self._model, self._data)
        self._mj.mj_forward(self._model, self._data)

    def close(self) -> None:
        if self._viewer is not None:
            self._viewer.close()
            self._viewer = None
