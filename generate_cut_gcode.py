import numpy as np

from generate_2d_contour import InsoleMeshProcessor
from generate_roughing_gcode import RoughingGCodeGenerator


class CuttingGCodeGenerator:
    def __init__(self, insole_file_path, config):
        self.config = config
        self.nof_tabs = 10
        self.tab_length = 10
        self.z1 = 0
        self.z2 = self.config['safe_z']
        self.min_z = self.config['min_z_cut'] - self.config['block_height']

        self.insole_proc = self.initialize_insole_processor(insole_file_path)
        self.only_contour_height = self.config['only_contour_height'] - self.config['block_height']
        self.z_levels = RoughingGCodeGenerator.get_z_levels(self.min_z, self.config['z_step'])
        self.contour_points = self.get_contour_points()
        self.path = self.generate_path()
        self.levels = self.generate_paths()
        # path = self.path
        # import pyvista as pv
        # lines = np.zeros((len(path), 2, 3))
        # for i, start in enumerate(path):
        #     end = path[i + 1 if i != len(path)-1 else 0]
        #     lines[i] = [start, end]
        # plotter = pv.Plotter()
        # plotter.add_mesh(pv.PolyData(self.contour_points), color='red')
        # plotter.add_lines(np.array(lines).reshape(-1, 3), color='blue', width=5)
        # # plotter.add_lines(np.array(contour_info).reshape(-1, 3)[:-2], color='blue', width=5)
        # plotter.show()

    def initialize_insole_processor(self, insole_file_path):
        insole_proc = InsoleMeshProcessor(insole_file_path, self.config['tool_radius'])
        insole_proc.mesh.translate([0, 0, -self.config['block_height']], inplace=True)
        return insole_proc

    def get_contour_points(self):
        contour_info = self.insole_proc.process_contours(self.only_contour_height)
        return contour_info['clusters'][0]['points']

    def calculate_normalized_cumulative_perimeter(self):
        linear_distances = np.sqrt(np.sum(np.diff(self.contour_points, axis=0) ** 2, axis=1))  # sqrt(Δx^2 + Δy^2)
        cum_perimeter = np.concatenate(([0], np.cumsum(linear_distances)))
        total_perimeter = cum_perimeter[-1]
        norm_cum_perimeter = cum_perimeter / total_perimeter
        norm_tab_length = self.tab_length / total_perimeter
        return norm_cum_perimeter, norm_tab_length

    def calculate_tab_areas(self, norm_tab_length):
        center_of_tabs_dist = np.linspace(1 / (self.nof_tabs * 2), 1 - 1 / (self.nof_tabs * 2), self.nof_tabs)
        tabs_areas = [(tab_pos - norm_tab_length, tab_pos + norm_tab_length) for tab_pos in center_of_tabs_dist]
        return tabs_areas

    def generate_path(self):
        norm_cum_perimeter, norm_tab_length = self.calculate_normalized_cumulative_perimeter()
        tabs_areas = self.calculate_tab_areas(norm_tab_length)
        path = []
        last_end = 0

        for start_tab, end_tab in tabs_areas:
            # Outside tab area (z1)
            idxs_outside = np.nonzero((norm_cum_perimeter >= last_end) & (norm_cum_perimeter < start_tab))[0]
            if idxs_outside.size > 0:
                values_outside = np.column_stack((self.contour_points[idxs_outside, :2], np.full_like(idxs_outside, self.z1, dtype=float)))
                path.append(values_outside)

            # Inside tab area (z2)
            idxs_inside = np.nonzero((norm_cum_perimeter >= start_tab) & (norm_cum_perimeter <= end_tab))[0]
            if idxs_inside.size > 0:
                start_point_down = np.concatenate((self.contour_points[idxs_inside[0], :2], [self.z1]))
                start_point_up = np.concatenate((self.contour_points[idxs_inside[0], :2], [self.z2]))
                end_point_up = np.concatenate((self.contour_points[idxs_inside[-1], :2], [self.z2]))
                end_point_down = np.concatenate((self.contour_points[idxs_inside[-1], :2], [self.z1]))

                path.append(np.asarray([start_point_down, start_point_up, end_point_up, end_point_down]))

            last_end = end_tab

        # Add remaining points outside the last tab area (z1)
        idxs_remaining = np.nonzero(norm_cum_perimeter > last_end)[0]
        if idxs_remaining.size > 0:
            values_remaining = np.column_stack((self.contour_points[idxs_remaining, :2], np.full_like(idxs_remaining, self.z1, dtype=float)))
            path.append(values_remaining)

        # Flatten the list of arrays into a single array if needed
        return np.vstack(path)

    def generate_paths(self):
        paths = []
        for z in self.z_levels:
            new_path = self.path.copy()
            new_path[new_path[:, 2] == 0, 2] = z
            paths.append(new_path)
        return paths

    def generate_gcode(self):
        gcode = [
            'G90            ; Set to absolute positioning mode, so all coordinates are relative to a fixed origin',
            "G21            ; Set units to millimeters",
            'G49            ; Cancel any tool offset that might be active',
            f"G0 Z{self.config['safe_z']}         ; Move to safe height",
            f"M3 S{self.config['rotation_speed']}      ; Start spindle rotation clockwise (M3) at {self.config['rotation_speed']} RPM"
        ]

        for i, path in enumerate(self.levels):

            if i == 0:
                gcode.append(f"G0 X{path[0][0]:.3f} Y{path[0][1]:.3f}        ; Rapid positioning to start of path")
            last_z = None
            for x, y, z in path:
                g_type = 'G0' if (z == self.config['safe_z'] and last_z == self.config['safe_z']) else 'G1'
                if z == last_z:
                    gcode.append(f"{g_type} X{x:.3f} Y{y:.3f}        ; Linear move")
                else:
                    gcode.append(f"{g_type} X{x:.3f} Y{y:.3f} Z{z:.3f} ; Linear move")

                last_z = z

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
        'z_step': 6,
        'min_z_cut': 0.5,
        'block_height': 34,
        'safe_z': 6,
        'rotation_speed': 13000,
        'only_contour_height': 0.1
    }

    g_code = CuttingGCodeGenerator(INSOLE_FILE_PATH, CONFIG).generate_gcode()
    with open("gcode_corte.txt", "w", encoding='utf8') as file:
        file.write(g_code)
