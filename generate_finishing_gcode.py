import numpy as np

from generate_2d_contour import InsoleMeshProcessor
from generate_raster import PathProcessor
from functions.algebric_functions import intersect_line_triangle
from time import time

class RoughingGCodeGenerator:
    def __init__(self, insole_file_path, config):
        start_time = time()
        self.config = config
        self.insole_proc = InsoleMeshProcessor(insole_file_path, self.config['tool_radius'])
        print(time() - start_time)
        self.get_path_points(self.insole_proc)
        print(time() - start_time)

    def get_path_points(self, insole_obj):
        z = self.config['safe_z']
        step_x = 1
        step_y = 2
        tolerance = 4
        mesh = insole_obj.mesh
        all_triangles = insole_obj.get_triangles

        upward_triangle_idxs = np.nonzero(mesh.face_normals[:, 2] > 0.8)[0]
        upward_triangles = all_triangles[upward_triangle_idxs]
        upward_triangles_points = upward_triangles.reshape(-1, 3)

        x_min, y_min, _ = np.min(upward_triangles_points, axis=0)
        x_max, y_max, _ = np.max(upward_triangles_points, axis=0)

        x_points = np.arange(x_min, x_max + step_x, step_x)
        y_points = np.arange(y_min, y_max + step_y, step_y)

        ordered_points = []
        for i, y in enumerate(y_points):
            if i % 2 == 0:
                # Even line: from x_min to x_max
                row_points = [np.asarray([x, y, z]) for x in x_points]
            else:
                # Odd line: from x_max to x_min
                row_points = [np.asarray([x, y, z]) for x in x_points[::-1]]

            ordered_points.extend(row_points)

        for idx, point in enumerate(ordered_points):
            filt_triangles = upward_triangles[
                np.any(np.abs(upward_triangles[:, :, 0] - point[0]) < tolerance, axis=1)
                & np.any(np.abs(upward_triangles[:, :, 1] - point[1]) < tolerance, axis=1)
            ]
            point2 = point - [0, 0, 100]
            result = next(
                (
                    np.mean((np.array(a)[2], np.array(b)[2], np.array(c)[2]))
                    for a, b, c in filt_triangles
                    if intersect_line_triangle(point, point2, np.array(a), np.array(b), np.array(c))
                ),
                None
            )
            if result is not None:
                point[2] = result
            else:
                point = None

            ordered_points[idx] = point
        
        ordered_points = [point for point in ordered_points if point is not None]

        filt_points = [ordered_points[0]]

        for idx, point in enumerate(ordered_points[1:], start=1):
            last_point = filt_points[-1]
            if point[1] != last_point[1] or point[2] != last_point[2]:
                filt_points.extend([ordered_points[idx - 1], point])

        import pyvista as pv
        lines = insole_obj.get_contour_lines(np.asarray(filt_points))
        plotter = pv.Plotter()
        plotter.add_mesh(pv.PolyData(upward_triangles_points), color='red')
        plotter.add_mesh(pv.PolyData(ordered_points), color='blue')
        plotter.add_lines(np.array(lines).reshape(-1, 3)[:-2], color='blue', width=5)
        plotter.show()


if __name__ == "__main__":
    INSOLE_FILE_PATH = r'output_files\insole.STL'
    # INSOLE_FILE_PATH = r'input_files\test_complex.STL'

    # Dimension = 140 x 350 x 34
    CONFIG = {
        'tool_radius': 3,
        'raster_step': 1,
        'step_over': 3,
        'block_height': 34,
        'z_step': 6,
        'z_step_finish': 1,
        'safe_z': 36,
        'rotation_speed': 15000,
        'only_contour_height': 0.1
    }

    g_code = RoughingGCodeGenerator(INSOLE_FILE_PATH, CONFIG)
    print(g_code)
