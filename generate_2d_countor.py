import numpy as np
import pyvista as pv
from numpy import floating
from numpy.typing import NDArray
from sklearn.cluster import DBSCAN

from functions.algebric_functions import calculate_angle
from generate_raster import two_d_section

def find_next_point(
        current_point: NDArray[floating],
        points: NDArray[floating],
        previous_vector: NDArray[floating] | None
    ) -> NDArray[floating] | None:
    """
    Find the next point from a given set of points based on distance and angle constraints.
    It gets the closest point as the next if the angle between the previous vector and the current
    is less than the max allowed.
    """
    max_angle = 90

    distances = np.linalg.norm(points - current_point, axis=1)

    sorted_indices = np.argsort(distances)

    for idx in sorted_indices[1:]:
        candidate_point = points[idx]
        candidate_vector = candidate_point - current_point

        # In the first time this function is called there isn't a previous vector
        if previous_vector is None:
            return candidate_point

        angle = calculate_angle(previous_vector, candidate_vector)

        if angle <= max_angle:
            return candidate_point

    return None

def connect_points(points: NDArray[floating]) -> NDArray[floating]:
    """
    Connects points in a sequence starting from the point with the minimum y-coordinate.
    The next point is determined by the closest point that satisfies the angle constraint.
    """
    # Starts with the point with minimum y coord
    current_point = points[np.argmin(points[:, 1])]

    path = [current_point]

    previous_vector = None
    while len(path) < len(points):
        next_point = find_next_point(current_point, points, previous_vector)
        if next_point is None:
            break

        path.append(next_point)
        previous_vector = next_point - current_point
        current_point = next_point

    return np.array(path)

if __name__ == "__main__":
    INSOLE_FILE_PATH = r'output_files\insole.stl'
    Z_VAL = 1
    mesh = pv.read(INSOLE_FILE_PATH)

    intersection_points = two_d_section(mesh, Z_VAL)

    points_2d = intersection_points[:, :2]

    # Finding the clusters
    dbscan = DBSCAN(eps=5, min_samples=5)
    labels = dbscan.fit_predict(points_2d)

    contours = []
    for label in np.unique(labels[labels != -1]):
        cluster_points = points_2d[labels == label]
        paths = connect_points(cluster_points)
        contours.append(paths)


    # Visualizing clusters and countours
    pl = pv.Plotter()
    pl.add_mesh(pv.PolyData(intersection_points), color='red', point_size=4)

    # Add the recognized contours
    for index, contour in enumerate(contours):
        # Arrange the points in consecutive pairs to form line segments
        lines = np.zeros((len(contour), 2, 3))

        for i, start in enumerate(contour):
            end = contour[i + 1 if i != len(contour)-1 else 0]

            lines[i] = [[start[0], start[1], Z_VAL], [end[0], end[1], Z_VAL]]

        pl.add_lines(np.array(lines).reshape(-1, 3), color='black', width=10)

    pl.show()