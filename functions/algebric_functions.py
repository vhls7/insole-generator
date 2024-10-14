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


def lines_intersect(p1, p2, p3, p4):
    # https://paulbourke.net/geometry/pointlineplane/
    # The shortest line between two lines in 3D
    # Let Pa = Point in P1P2 and Pb = Point in P3P4

    p2p1 = p2 - p1
    p4p3 = p4 - p3
    p1p3 = p1 - p3

    d1321 = np.dot(p1p3, p2p1)
    d1343 = np.dot(p1p3, p4p3)
    d2121 = np.dot(p2p1, p2p1)
    d4321 = np.dot(p4p3, p2p1)
    d4343 = np.dot(p4p3, p4p3)

    denominator = d2121 * d4343 - d4321 * d4321

    if np.abs(denominator) < 1e-6: # Lines are parallel or coincident

        # If lines are at least parallel, to be coincident the line formed by the points 1,2
        # must be parallel to the line formed by the points 1, 3.
        # If they are parallel the cross product will result in the null vector and the norm as 0.
        if np.linalg.norm(np.cross(p2p1, p1p3)) < 1e-6:
            return False # Lines are coincidents
        return False # Lines are only parallel

    mua = (d1343 * d4321 - d1321 * d4343) / denominator
    mub = (d1343 + mua * d4321) / d4343

    pa = p1 + mua * p2p1
    pb = p3 + mub * p4p3

    if np.allclose(pa, pb) and 0 < mub < 1: # If the intersection is in the segment
        return True
    return False

def intersect_line_triangle(p1, p2, a, b, c):
    # https://paulbourke.net/geometry/pointlineplane/
    # Intersection of a plane and a line

    # Returns false if a line point is coincident with a vertex
    if np.any([np.all(np.isclose(p1, p)) for p in [a, b, c]]) or np.any([np.all(np.isclose(p2, p)) for p in [a, b, c]]):
        return False
    ab = b - a
    ac = c - a
    normal = np.cross(ab, ac)

    line = p2 - p1

    if np.abs(np.dot(normal, line)) < 1e-6:  # Line is parallel to the plane
        intersec_with_ab = lines_intersect(p1, p2, a, b)
        intersec_with_bc = lines_intersect(p1, p2, b, c)
        intersec_with_ac = lines_intersect(p1, p2, a, c)
        return intersec_with_ab is True or intersec_with_bc is True or intersec_with_ac is True

    u = np.dot(normal, a - p1) / np.dot(normal, line)

    if u < 0 or u > 1: # The intersection is outside the line segment between P1 and P2
        return False

    intersec_point = p1 + u * line

    # Vectors from the point of intersection to the vertices of the triangle
    ap = intersec_point - a
    bp = intersec_point - b
    cp = intersec_point - c

    abc_area = np.linalg.norm(normal) / 2.0

    pbc_area = np.linalg.norm(np.cross(bp, cp)) / 2.0
    pca_area = np.linalg.norm(np.cross(cp, ap)) / 2.0
    pab_area = np.linalg.norm(np.cross(ap, bp)) / 2.0
    sum_of_subtriangle_areas = pbc_area + pca_area + pab_area

    is_point_inside_triang = np.abs(sum_of_subtriangle_areas - abc_area) < 1e-6

    if is_point_inside_triang:
        return True
    return False
