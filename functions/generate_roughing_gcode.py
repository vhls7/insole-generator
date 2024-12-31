import numpy as np

from functions.generate_2d_contour import InsoleMeshProcessor
from functions.generate_raster import PathProcessor


class RoughingGCodeGenerator:
    def __init__(self, insole_file_path, config):
        self.config = config
        self.insole_proc = InsoleMeshProcessor(insole_file_path, self.config['tool_radius'])
        self.insole_proc.mesh.translate([0, 0, -self.config['block_height']], inplace=True)
        self.only_contour_height = self.config['only_contour_height'] - self.config['block_height']
        self.levels = self.get_levels()
        self.g_code = self.generate_gcode()

    def get_levels(self):
        min_z, max_z = self.insole_proc.get_upper_surface_min_z(self.config['z_step_finish'])

        boundary_paths = PathProcessor(
            self.insole_proc,
            self.config['raster_step'],
            self.config['step_over'],
            self.only_contour_height
        ).get_paths()

        z_levels = self.get_z_levels(min_z, self.config['z_step'])
        levels = []

        for z in z_levels:
            current = {'z': z}
            if z > max_z:
                paths = boundary_paths
            else:
                paths = PathProcessor(
                    self.insole_proc,
                    self.config['raster_step'],
                    self.config['step_over'],
                    z
                ).get_paths()
            current['paths'] = paths
            levels.append(current)

        return levels

    @staticmethod
    def get_z_levels(min_z, z_step):
        delta_z = 0 - min_z
        real_z_step = delta_z / z_step
        z_levels = np.arange(0 - real_z_step, min_z - real_z_step, -real_z_step)
        return z_levels

    def generate_gcode(self):
        gcode = [
            'G90            ; Set to absolute positioning mode, so all coordinates are relative to a fixed origin',
            "G21            ; Set units to millimeters",
            'G49            ; Cancel any tool offset that might be active',
            f"G0 Z{self.config['safe_z']}         ; Move to safe height",
            f"M3 S{self.config['rotation_speed']}      ; Start spindle rotation clockwise (M3) at {self.config['rotation_speed']} RPM"
        ]

        for level in self.levels:
            z = level['z']
            paths = level['paths']

            for path in paths:
                x_start, y_start = path[0]
                gcode.append(f"G0 X{x_start:.3f} Y{y_start:.3f}        ; Rapid positioning to start of path")
                gcode.append(f"G1 Z{z:.3f}        ; Set depth to {z:.3f}")

                if len(path) > 1:
                    for x, y in path[1:]:
                        gcode.append(f"G1 X{x:.3f} Y{y:.3f}        ; Linear move")

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
        'step_over': 3,
        'block_height': 34,
        'z_step': 6,
        'z_step_finish': 1,
        'safe_z': 6,
        'rotation_speed': 13000,
        'only_contour_height': 0.1
    }

    g_code = RoughingGCodeGenerator(INSOLE_FILE_PATH, CONFIG).generate_gcode()
    with open("gcode_desbaste.txt", "w", encoding='utf8') as file:
        file.write(g_code)


# # region Plotting the result
#     import matplotlib.pyplot as plt

#     true_coords = np.asarray([(x_grid_values[x_idx], y_grid_values[y_idx]) for y_idx, x_idx  in np.argwhere(boolean_matrix)])

#     # plt.scatter(true_coords[:, 0], true_coords[:, 1], c='blue', marker='o', s=1, label='True Points')
#     colors = ['black', 'blue', 'green', 'orange', 'purple', 'gray']
#     for idx, path in enumerate(paths):
#         plt.plot(path[:, 0], path[:, 1], 'o-', markersize=3, label=f'Contour {idx}', color=colors[idx % len(colors)])
#     for cl_info in contours_information['clusters']:
#         points = cl_info['points']
#         plt.plot(points[:, 0], points[:, 1], 'ro-', markersize=3, label='Insole Contours')
#         plt.plot(cl_info['offset'][:, 0], cl_info['offset'][:, 1], 'o-', markersize=3, label='Offset Contours')

#     plt.gca().set(xlabel='X values', ylabel='Y values', title='Scatter Plot of True Points with Contours')
#     plt.legend().set_draggable(True)
#     plt.show()
# # endregion