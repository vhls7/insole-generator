import numpy as np
import pyvista as pv
from numpy import floating
from numpy.typing import NDArray
from scipy.interpolate import CubicSpline
from shapely.geometry import Polygon
from sklearn.cluster import DBSCAN

from functions.algebric_functions import calculate_angle


class InsoleMeshProcessor:
    """
    A class to process 3D mesh data from an insole model and analyze its surface contours.

    This class provides methods to generate 2D sections of the mesh, order points based on proximity, 
    detect raised or recessed areas, and visualize the contours."""
    def __init__(self, file_path: str, tool_radius: float):
        self.file_path = file_path
        self.tool_radius = tool_radius
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

    @property
    def get_triangles(self):
        # based on https://github.com/pyvista/pyvista/discussions/1465
        triangles_coord_idxs = self.mesh.faces.reshape((-1, 4))[:, 1:]
        triangles = self.mesh_points[triangles_coord_idxs]
        return triangles

    def find_next_point(
        self,
        current_point: NDArray[np.floating],
        points: NDArray[np.floating],
        unused_mask: NDArray[np.bool_],
        previous_vector: NDArray[np.floating] | None
    ) -> tuple[NDArray[np.floating], int] | tuple[None, None]:
        """Find the next point based on distance and angle constraints."""
        max_angle = 90
        remaining_points = points[unused_mask]
        distances = np.linalg.norm(remaining_points - current_point, axis=1)
        sorted_indices = np.argsort(distances)

        for idx in sorted_indices:
            candidate_point = remaining_points[idx]
            candidate_vector = candidate_point - current_point

            if previous_vector is None or calculate_angle(previous_vector, candidate_vector) <= max_angle:
                original_idx = np.nonzero((points == candidate_point).all(axis=1))[0][0]
                # Return the point and its index to remove it from the array
                return candidate_point, original_idx

        return None, None

    def ordering_points(self, points: NDArray[np.floating], z_val: float) -> NDArray[np.floating]:
        """Order points based on proximity, starting from the lowest y-coordinate."""
        num_points = len(points)
        unused_mask = np.ones(num_points, dtype=bool)

        min_point_idx = np.argmin(points[:, 1])
        current_point = points[min_point_idx]
        ordered_points = [np.append(current_point, z_val)]

        unused_mask[np.argmin(points[:, 1])] = False
        previous_vector = None

        while len(ordered_points) < num_points:
            # Find the next point and its index
            next_point, idx = self.find_next_point(current_point, points, unused_mask, previous_vector)
            if next_point is None:
                break

            # Add the next point to the ordered list
            ordered_points.append(np.append(next_point, z_val))

            # Update vectors and current point, and remove used point from points array
            previous_vector = next_point - current_point
            current_point = next_point
            unused_mask[idx] = False

        return np.array(ordered_points)


    def get_contour_lines(self, ord_points: NDArray[floating]) -> NDArray[floating]:
        """Generate contour lines by connecting ordered points."""
        lines = np.zeros((len(ord_points), 2, 3))
        for i, start in enumerate(ord_points):
            end = ord_points[i + 1 if i != len(ord_points)-1 else 0]
            lines[i] = [start, end]
        return lines

    @staticmethod
    def spline_interpolation(points, spacing):

        x, y, z = points[:, 0], points[:, 1], points[:, 2]

        linear_distances = np.sqrt(np.sum(np.diff(points, axis=0)**2, axis=1)) # sqrt (Δx^2 + Δy^2)
        cumulative_dist = np.concatenate(([0], np.cumsum(linear_distances)))
        norm_cumulative_dist = cumulative_dist / cumulative_dist[-1]

        cs_x = CubicSpline(norm_cumulative_dist, x, bc_type='periodic')  # 'periodic' for closed contour
        cs_y = CubicSpline(norm_cumulative_dist, y, bc_type='periodic')

        # Criar novos pontos interpolados
        t_new = np.linspace(0, 1, int(cumulative_dist[-1] / spacing))
        x_new = cs_x(t_new)
        y_new = cs_y(t_new)
        new_z = np.full_like(x_new, z[0])
        return np.column_stack((x_new, y_new, new_z))

    def get_external_contour_idx(self, points, clusters):
        cluster_sizes = []
        for cluster_idx in np.unique(clusters[clusters != -1]):
            contour_points = points[clusters == cluster_idx]
            min_coords = np.min(contour_points, axis=0)
            max_coords = np.max(contour_points, axis=0)
            delta_coords = max_coords - min_coords
            cluster_sizes.append(np.sum(delta_coords))
        return np.argmax(cluster_sizes)

    def process_contours(self, z_val: float):
        """Process the contours using DBSCAN clustering to identify regions and their properties."""
        intersection_points = self.two_d_section(z_val)
        intersection_points_2d = intersection_points[:, :2]
        clusters = DBSCAN(eps=4, min_samples=5).fit_predict(intersection_points_2d)
        external_contour_idx = self.get_external_contour_idx(intersection_points_2d, clusters)
        contours_info = {
            'clusters': [],
            'intersection_points_2d': intersection_points_2d,
            'external_contour_idx': external_contour_idx
        }
        for cluster_idx in np.unique(clusters[clusters != -1]):
            is_external_contour = cluster_idx == external_contour_idx
            cluster_points = intersection_points_2d[clusters == cluster_idx]
            ord_points = self.ordering_points(cluster_points, z_val)
            interp_points = self.spline_interpolation(np.append(ord_points, [ord_points[0]], axis=0), self.spacing)
            is_raised = self.is_raised_area(interp_points)
            offset_distance = -1 * self.tool_radius if is_raised is False else self.tool_radius
            contours_info['clusters'].append({
                'points': interp_points,
                'contour_lines': self.get_contour_lines(interp_points),
                'is_raised_area': is_raised if not is_external_contour else None,
                'offset': self.offset_contour(interp_points, offset_distance, self.spacing),
                'cluster_idx': cluster_idx,
            })
        return contours_info

    def is_raised_area(self, contour_points: NDArray[floating]) -> bool:
        """Detect if an area is a boss (raised) or a recess (lowered) relative to contour."""
        contour_mean = np.mean(contour_points, axis=0)
        distances = np.linalg.norm(self.mesh_points - contour_mean, axis=1)
        closest_point = self.mesh_points[np.argmin(distances)]
        delta_z = closest_point[2] - contour_mean[2]
        return bool(delta_z >= 0)

    def visualize(self, contours_info):
        """Visualize the processed contours and mesh."""
        pl = pv.Plotter()

        for contour_info in contours_info['clusters']:
            points = contour_info['points']
            off_points = contour_info['offset']
            lines = contour_info['contour_lines']
            # pl.add_lines(np.array(lines).reshape(-1, 3), color='blue', width=5)
            pl.add_mesh(pv.PolyData(points), color='black', point_size=8)
            pl.add_mesh(pv.PolyData(off_points), color='blue', point_size=8)
            # pl.add_lines(np.array(self.get_contour_lines(off_points)).reshape(-1, 3), color='blue', width=5)

        pl.show()

    @staticmethod
    def offset_contour(points, offset_distance, spacing):
        z_val = points[0, 2]
        polygon = Polygon(points[:, :2])

        offset_polygon = polygon.buffer(offset_distance)
        offset_coords = np.array(offset_polygon.exterior.coords)

        z = np.full(len(offset_coords), z_val)
        offset_points = np.column_stack((offset_coords, z))
        equal_spaced_points = InsoleMeshProcessor.spline_interpolation(offset_points, spacing)
        return equal_spaced_points

    def get_upper_surface_min_z(self, z_step_finish):
        all_triangles = self.get_triangles
        all_normals = self.mesh.face_normals

        horizontal_triang_idxs = np.nonzero(all_normals[:, 2] > 1e-3)[0]

        filt_triangles = all_triangles[horizontal_triang_idxs]

        min_z = np.min(filt_triangles[:, :, 2]) + z_step_finish
        max_z = np.max(filt_triangles[:, :, 2])
        return min_z, max_z


if __name__ == "__main__":
    INSOLE_FILE_PATH = r'input_files\test_complex.STL'
    Z_VAL = 18.66666666666667
    TOOL_RADIUS = 3

    processor = InsoleMeshProcessor(INSOLE_FILE_PATH, TOOL_RADIUS)
    contours_information = processor.process_contours(Z_VAL)
    processor.visualize(contours_information)
