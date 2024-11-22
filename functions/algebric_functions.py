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

def lines_intersect_2d(p1, p2, a, b):
    """
    Check if the lines intersect and return the intersection point if they do; otherwise, return None.

    p1 + t * (p2 - p1) = a + u * (b - a)
    t * (p2 - p1) - u * (b - a) = a - p1
    Using Cramer
    [(p2 - p1)x - (b - a)x] * [t] = [(a - p1)x]
    [(p2 - p1)y - (b - a)y] * [u] = [(a - p1)y]
    t = Dt/D; u = Du/D
    """
    p1p2 = p2 - p1
    ab = b - a

    det = np.linalg.det([p1p2, ab])

    vectors_are_parallel = np.isclose(det, 0)
    if vectors_are_parallel:
        return None

    t = np.linalg.det([a - p1, ab]) / det
    u = np.linalg.det([a - p1, p1p2]) / det

    # Check if intersection is in line limits
    if 0 <= t <= 1 and 0 <= u <= 1:
        # Ponto de interseção
        intersection = p1 + t * p1p2
        return intersection

    return None

def lines_intersect_3d(p1, p2, p3, p4):
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
    if np.any([np.allclose(p1, p) for p in [a, b, c]]) or np.any([np.allclose(p2, p) for p in [a, b, c]]):
        return False
    ab = b - a
    ac = c - a
    normal = np.cross(ab, ac)

    line = p2 - p1
    dot_normal_line = np.dot(normal, line)

    if np.abs(dot_normal_line) < 1e-6:  # Line is parallel to the plane
        intersec_with_ab = lines_intersect_3d(p1, p2, a, b)
        intersec_with_bc = lines_intersect_3d(p1, p2, b, c)
        intersec_with_ac = lines_intersect_3d(p1, p2, a, c)
        return intersec_with_ab is True or intersec_with_bc is True or intersec_with_ac is True

    u = np.dot(normal, a - p1) / dot_normal_line

    if not (0 <= u <= 1): # The intersection is outside the line segment between P1 and P2
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

def find_triangle_containing_point(point, triangles):
    """
    Finds the first triangle containing the given point using barycentric coordinates.

    Args:
        point (array-like): The point in the format (x, y).
        triangles (array-like): An array of triangles, where each triangle is defined by
                                3 vertices in the format [(x1, y1), (x2, y2), (x3, y3)].

    Returns:
        int: The index of the first triangle containing the point, or None if no triangle contains it.
    """
    point = np.array(point)
    triangles = np.array(triangles)  # Shape: (N, 3, 2)

    a, b, c = triangles[:, 0], triangles[:, 1], triangles[:, 2]

    v0 = c - a  # C - A
    v1 = b - a  # B - A
    v2 = point - a  # P - A (for all triangles)

    # Compute dot products
    dot00 = np.einsum('ij,ij->i', v0, v0)  # v0 · v0
    dot01 = np.einsum('ij,ij->i', v0, v1)  # v0 · v1
    dot02 = np.einsum('ij,ij->i', v0, v2)  # v0 · v2
    dot11 = np.einsum('ij,ij->i', v1, v1)  # v1 · v1
    dot12 = np.einsum('ij,ij->i', v1, v2)  # v1 · v2

    # Compute determinant (denom)
    denom = dot00 * dot11 - dot01 * dot01

    # Avoid division by zero for degenerate triangles
    valid = denom != 0
    denom[~valid] = 1

    u = (dot11 * dot02 - dot01 * dot12) / denom
    v = (dot00 * dot12 - dot01 * dot02) / denom

    # Check if the point is inside the triangle
    inside = (u >= 0) & (v >= 0) & (u + v <= 1) & valid

    # Return the first triangle containing the point, or None if no triangle contains it
    indices = np.nonzero(inside)[0]
    return indices[0] if indices.size > 0 else None