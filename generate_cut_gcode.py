import numpy as np
import pyvista as pv

from generate_2d_contour import InsoleMeshProcessor


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

class CuttingGCodeGenerator:
    def __init__(self, insole_file_path, config):
        nof_tabs = 10
        tab_length = 10
        z1 = -34
        z2= -14
        self.config = config
        self.insole_proc = InsoleMeshProcessor(insole_file_path, self.config['tool_radius'])
        self.insole_proc.mesh.translate([0, 0, -self.config['block_height']], inplace=True)
        self.only_contour_height = self.config['only_contour_height'] - self.config['block_height']
        contour_info = self.insole_proc.process_contours(self.only_contour_height)
        points = contour_info['clusters'][0]['points']

        # Getting an array with the nomalized perimeter cumulative
        linear_distances = np.sqrt(np.sum(np.diff(points, axis=0)**2, axis=1)) # sqrt (Δx^2 + Δy^2)
        cum_perimeter = np.concatenate(([0], np.cumsum(linear_distances)))
        total_perimeter = cum_perimeter[-1]
        norm_cum_perimeter = cum_perimeter / total_perimeter
        norm_tab_length = tab_length / total_perimeter

        center_of_tabs_dist = np.linspace(0, 1, nof_tabs)
        tabs_areas = [(tab_pos - norm_tab_length, tab_pos + norm_tab_length) for tab_pos in center_of_tabs_dist]

        path = []
        last_end = 0

        for start_tab, end_tab in tabs_areas:
            # Outside tab area (z1)
            idxs_outside = np.nonzero((norm_cum_perimeter >= last_end) & (norm_cum_perimeter < start_tab))[0]
            if idxs_outside.size > 0:
                values_outside = np.column_stack((points[idxs_outside, :2], np.full_like(idxs_outside, z1, dtype=float)))
                path.append(values_outside)

            # Inside tab area (z2)
            idxs_inside = np.nonzero((norm_cum_perimeter >= start_tab) & (norm_cum_perimeter <= end_tab))[0]
            if idxs_inside.size > 0:
                values_inside = np.column_stack((points[idxs_inside, :2], np.full_like(idxs_inside, z2, dtype=float)))
                path.append(values_inside)

            last_end = end_tab

        # Add remaining points outside the last tab area (z1)
        idxs_remaining = np.nonzero(norm_cum_perimeter > last_end)[0]
        if idxs_remaining.size > 0:
            values_remaining = np.column_stack((points[idxs_remaining, :2], np.full_like(idxs_remaining, z1, dtype=float)))
            path.append(values_remaining)

        # Flatten the list of arrays into a single array if needed
        path = np.vstack(path)


        lines = np.zeros((len(path), 2, 3))
        for i, start in enumerate(path):
            end = path[i + 1 if i != len(path)-1 else 0]
            lines[i] = [start, end]
        plotter = pv.Plotter()
        plotter.add_mesh(pv.PolyData(points), color='red')
        plotter.add_lines(np.array(lines).reshape(-1, 3), color='blue', width=5)
        # plotter.add_lines(np.array(contour_info).reshape(-1, 3)[:-2], color='blue', width=5)
        plotter.show()


    # def generate_gcode(self):
    #     gcode = [
    #         'G90            ; Set to absolute positioning mode, so all coordinates are relative to a fixed origin',
    #         "G21            ; Set units to millimeters",
    #         'G49            ; Cancel any tool offset that might be active',
    #         f"G0 Z{self.config['safe_z']}         ; Move to safe height",
    #         f"M3 S{self.config['rotation_speed']}      ; Start spindle rotation clockwise (M3) at {self.config['rotation_speed']} RPM"
    #     ]


    #     for x, y, z in self.path_points:
    #         gcode.append(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f}   ; Linear move")

    #     gcode.append(f"G0 Z{self.config['safe_z']}         ; Move to safe height")

    #     gcode.append("M5; Stop spindle")
    #     gcode.append("M30 ; Program end")

    #     return "\n".join(gcode)



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

    g_code = CuttingGCodeGenerator(INSOLE_FILE_PATH, CONFIG)
