import numpy as np
from robots.base import RobotBase


class MockSim(RobotBase):
    """Headless mock sim — no MuJoCo required. Used in CI and dry-run testing."""

    def __init__(self, cfg: dict):
        super().__init__(cfg)
        self._obs_dim = cfg.get("obs_dim", 48)
        self._step = 0

    def observe(self) -> np.ndarray:
        self._step += 1
        return np.zeros(self._obs_dim, dtype=np.float32)

    def act(self, action: np.ndarray) -> None:
        pass

    def reset(self) -> None:
        self._step = 0
