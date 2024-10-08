import numpy as np
import pyvista as pv
from numpy import floating
from numpy.typing import NDArray
from scipy.interpolate import CubicSpline
from sklearn.cluster import DBSCAN

from functions.algebric_functions import calculate_angle


class InsoleMeshProcessor:
    """
    A class to process 3D mesh data from an insole model and analyze its surface contours.

    This class provides methods to generate 2D sections of the mesh, order points based on proximity, 
    detect raised or recessed areas, and visualize the contours."""
    def __init__(self, file_path: str, min_radius: float):
        self.file_path = file_path
        self.min_radius = min_radius
        self.mesh = pv.read(self.file_path)
        self.mesh_points = np.asarray(self.mesh.points)
        self.spacing = 3

    def two_d_section(self, z_val: float) -> NDArray[floating]:
        """Generate a 2D intersection of the solid mesh at a specified z-plane."""
        plane = pv.Plane(
            center=(0, 0, z_val),
            direction=(0, 0, 1),
            i_size=500,
            j_size=500,
            i_resolution=150,
            j_resolution=150
        ).triangulate()

        intersection, _, _ = self.mesh.intersection(plane)  # type: ignore
        intersection_points = np.asarray(intersection.points)
        return intersection_points

    def find_next_point(
            self, current_point: NDArray[floating], points: NDArray[floating], previous_vector: NDArray[floating] | None
    ) -> NDArray[floating] | None:
        """Find the next point based on distance and angle constraints."""
        max_angle = 90
        distances = np.linalg.norm(points - current_point, axis=1)
        sorted_indices = np.argsort(distances)

        for idx in sorted_indices[1:]:
            candidate_point = points[idx]
            candidate_vector = candidate_point - current_point

            if previous_vector is None:
                return candidate_point

            angle = calculate_angle(previous_vector, candidate_vector)
            if angle <= max_angle:
                return candidate_point

        return None

    def is_raised_area(self, contour_points: NDArray[floating]) -> bool:
        """Detect if an area is a boss (raised) or a recess (lowered) relative to contour."""
        contour_mean = np.mean(contour_points, axis=0)
        distances = np.linalg.norm(self.mesh_points - contour_mean, axis=1)
        closest_point = self.mesh_points[np.argmin(distances)]
        delta_z = closest_point[2] - contour_mean[2]
        return delta_z >= 0

    def ordering_points(self, points: NDArray[floating], z_val: float) -> NDArray[floating]:
        """Order points based on proximity, starting from the lowest y-coordinate."""
        current_point = points[np.argmin(points[:, 1])]
        ordered_points = [np.append(current_point, z_val)]
        previous_vector = None

        while len(ordered_points) < len(points):

            next_point = self.find_next_point(current_point, points, previous_vector)
            if next_point is None:
                break

            ordered_points.append(np.append(next_point, z_val))
            previous_vector = next_point - current_point
            current_point = next_point

        return np.array(ordered_points)


    def get_contour_lines(self, ord_points: NDArray[floating]) -> NDArray[floating]:
        """Generate contour lines by connecting ordered points."""
        lines = np.zeros((len(ord_points), 2, 3))
        for i, start in enumerate(ord_points):
            end = ord_points[i + 1 if i != len(ord_points)-1 else 0]
            lines[i] = [start, end]
        return lines

    def spline_interpolation(self, points, spacing):

        x, y, z = points[:, 0], points[:, 1], points[:, 2]
        t = np.linspace(0, 1, len(points))

        linear_distances = np.sqrt(np.sum(np.diff(points, axis=0)**2, axis=1)) # sqrt (Δx^2 + Δy^2)
        cumulative_dist = np.sum(linear_distances)

        cs_x = CubicSpline(t, x, bc_type='periodic')  # 'periodic' for closed contour
        cs_y = CubicSpline(t, y, bc_type='periodic')

        # Criar novos pontos interpolados
        t_new = np.linspace(0, 1, int(cumulative_dist / spacing))
        x_new = cs_x(t_new)
        y_new = cs_y(t_new)
        new_z = np.full_like(x_new, z[0])
        return np.column_stack((x_new, y_new, new_z))

    def process_contours(self, z_val: float):
        """Process the contours using DBSCAN clustering to identify regions and their properties."""
        intersection_points = self.two_d_section(z_val)
        intersection_points_2d = intersection_points[:, :2]
        clusters = DBSCAN(eps=5, min_samples=5).fit_predict(intersection_points_2d)

        contours_info = {}
        for cluster_idx, cluster in enumerate(np.unique(clusters[clusters != -1])):
            cluster_points = intersection_points_2d[clusters == cluster]
            ord_points = self.ordering_points(cluster_points, z_val)
            equal_spaced_points = self.spline_interpolation(np.append(ord_points, [ord_points[0]], axis=0), self.spacing)
            contour_lines = self.get_contour_lines(equal_spaced_points)
            is_raised = self.is_raised_area(equal_spaced_points)
            contours_info[cluster_idx] = {
                'ordered_points': equal_spaced_points,
                'is_raised': is_raised,
                'contour_lines': contour_lines
            }
        return contours_info

    def visualize(self, contours_info):
        """Visualize the processed contours and mesh."""
        pl = pv.Plotter()

        for contour_info in contours_info.values():
            points = contour_info['ordered_points']
            lines = contour_info['contour_lines']
            pl.add_lines(np.array(lines).reshape(-1, 3), color='blue', width=5)
            pl.add_mesh(pv.PolyData(points), color='black', point_size=8)

        pl.show()


if __name__ == "__main__":
    INSOLE_FILE_PATH = r'output_files\insole.stl'
    Z_VAL = 1
    MIN_RADIUS = 3

    processor = InsoleMeshProcessor(INSOLE_FILE_PATH, MIN_RADIUS)
    contours_information = processor.process_contours(Z_VAL)
    processor.visualize(contours_information)
    print(contours_information)
