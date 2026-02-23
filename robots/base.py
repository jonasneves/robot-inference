from abc import ABC, abstractmethod
import numpy as np


class RobotBase(ABC):
    def __init__(self, cfg: dict):
        self.cfg = cfg

    @abstractmethod
    def observe(self) -> np.ndarray:
        """Return raw sensor observation (joints, IMU, etc.)."""

    @abstractmethod
    def act(self, action: np.ndarray) -> None:
        """Apply joint targets from policy output."""

    def reset(self) -> None:
        """Return robot to safe default pose."""

    def close(self) -> None:
        """Release hardware/sim resources."""
