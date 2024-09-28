import numpy as np
from numpy import floating
from numpy.typing import NDArray


def calculate_angle(v1: NDArray[floating], v2: NDArray[floating]) -> float:
    """Return the angle between two vectors in degrees [0, 180]"""
    dot_product = np.dot(v1, v2)
    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)

    cos_angle = dot_product / (norm_v1 * norm_v2)

    # To prevent errors, the value is limited to between -1 and 1.
    cos_angle = np.clip(cos_angle, -1, 1)

    angle = float(np.degrees(np.arccos(cos_angle)))
    return angle