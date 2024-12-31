import numpy as np

from functions.generate_2d_contour import InsoleMeshProcessor
from functions.algebric_functions import find_triangle_containing_point

def closer_triangles(all_triangles, point):
    indices = []
    for i, tri in enumerate(all_triangles):
        if np.any(np.all(np.isclose(tri, point, atol=1e-5), axis=1)):
            indices.append(i)
    return all_triangles[indices]

def get_closest_point(all_triangles, point):
    vertices = all_triangles.reshape(-1, 3)
    distances = np.linalg.norm(vertices - point, axis=1)
    closest_vertex_index = np.argmin(distances)
    closest_vertex = vertices[closest_vertex_index]
    return closest_vertex

def filter_sequences(points):
    """
    Remove intermediate points in sequences where only x varies, keeping y and z constant.
    Retains the first and last points of each sequence and respects the original order.

    Args:
        points (ndarray): Array of coordinates in the format (N, 3) with x, y, z.

    Returns:
        ndarray: Filtered array.
    """
    filtered_points = []
    n = len(points)

    for i in range(n):
        # Check if the current point is part of a sequence
        is_start = (i == 0 or not np.array_equal(points[i, 1:], points[i - 1, 1:]))
        is_end = (i == n - 1 or not np.array_equal(points[i, 1:], points[i + 1, 1:]))

        # Keep points that are either the start or end of a sequence
        if is_start or is_end:
            filtered_points.append(points[i])

    return np.array(filtered_points)

class FinishingGCodeGenerator:
    def __init__(self, insole_file_path, config):
        self.config = config
        self.insole_proc = InsoleMeshProcessor(insole_file_path, self.config['tool_radius'])
        self.insole_proc.mesh.translate([0, 0, -self.config['block_height']], inplace=True)
        self.path_points = self.get_path_points(self.insole_proc)

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
            if len(filt_triangles) == 0:
                ordered_points[idx] = None
                continue
            intersect_triang_idx = find_triangle_containing_point(point[:2], filt_triangles[:, :, :2])
            if intersect_triang_idx is not None:
                intersect_triang = filt_triangles[intersect_triang_idx]
                a, b, c = intersect_triang
                vertex_avg = np.mean((a[2], b[2], c[2]))
                point[2] = vertex_avg
            else:
                point = None

            ordered_points[idx] = point

        ordered_points = [point for point in ordered_points if point is not None]

        filt_points = [ordered_points[0]]

        for idx, point in enumerate(ordered_points[1:], start=1):
            last_point = filt_points[-1]
            if point[1] != last_point[1] or point[2] != last_point[2]:
                filt_points.extend([ordered_points[idx - 1], point])

        return filt_points

        # import pyvista as pv
        # lines = insole_obj.get_contour_lines(np.asarray(filt_points))
        # plotter = pv.Plotter()
        # plotter.add_mesh(pv.PolyData(upward_triangles_points), color='red')
        # plotter.add_mesh(pv.PolyData(ordered_points), color='blue')
        # plotter.add_lines(np.array(lines).reshape(-1, 3)[:-2], color='blue', width=5)
        # plotter.show()

    def generate_gcode(self):
        gcode = [
            'G90            ; Set to absolute positioning mode, so all coordinates are relative to a fixed origin',
            "G21            ; Set units to millimeters",
            'G49            ; Cancel any tool offset that might be active',
            f"G0 Z{self.config['safe_z']}         ; Move to safe height",
            f"M3 S{self.config['rotation_speed']}      ; Start spindle rotation clockwise (M3) at {self.config['rotation_speed']} RPM"
        ]


        for x, y, z in self.path_points:
            gcode.append(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f}   ; Linear move")

        gcode.append(f"G0 Z{self.config['safe_z']}         ; Move to safe height")

        gcode.append("M5; Stop spindle")
        gcode.append("M30 ; Program end")

        return "\n".join(gcode)



if __name__ == "__main__":
    INSOLE_FILE_PATH = r'output_files\insole.STL'
    # INSOLE_FILE_PATH = r'input_files\test_complex.STL'

    # Dimension = 140 x 350 x 34
    CONFIG = {
        'tool_radius': 3,
        'raster_step': 1,
        'step_over': 1,
        'block_height': 34,
        'safe_z': 6,
        'rotation_speed': 13000,
        'only_contour_height': 0.1
    }

    g_code = FinishingGCodeGenerator(INSOLE_FILE_PATH, CONFIG).generate_gcode()
    with open("gcode_acabamento.txt", "w", encoding='utf8') as file:
        file.write(g_code)