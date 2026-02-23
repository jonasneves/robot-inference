import numpy as np
from .base import RobotBase


class MockRobot(RobotBase):
    """No-hardware robot for offline testing and CI."""

    def __init__(self, cfg: dict):
        super().__init__(cfg)
        self._obs_dim = cfg.get("obs_dim", 48)
        self._action_dim = cfg.get("action_dim", 12)
        self._step = 0

    def observe(self) -> np.ndarray:
        self._step += 1
        return np.zeros(self._obs_dim, dtype=np.float32)

    def act(self, action: np.ndarray) -> None:
        pass

    def reset(self) -> None:
        self._step = 0

    @property
    def step(self) -> int:
        return self._step
