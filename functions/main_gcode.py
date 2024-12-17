from functions.generate_roughing_gcode import RoughingGCodeGenerator
from functions.generate_cut_gcode import CuttingGCodeGenerator
from functions.generate_finishing_gcode import FinishingGCodeGenerator





CONFIG = {
    'COMMON': {
        'tool_radius': 3,
        'block_height': 34,
        'safe_z': 6,
        'rotation_speed': 13000,
        'only_contour_height': 0.1
    },
    'ROUGHING': {
        'raster_step': 1,
        'step_over': 3,
        'z_step': 6,
        'z_step_finish': 1
    },
    'FINISHING': {
        'raster_step': 1,
        'step_over': 1
    },
    'CUTTING': {
        'z_step': 6,
        'min_z_cut': 0.5,
        'number_of_tabs': 10,
        'tab_length': 10
    }
}

def generate_gcode(input_file_path, output_file_path):

    # Merge configurations when initializing generators
    roughing_config = {**CONFIG['COMMON'], **CONFIG['ROUGHING']}
    roughing_gcode = RoughingGCodeGenerator(input_file_path, roughing_config).generate_gcode()

    finishing_config = {**CONFIG['COMMON'], **CONFIG['FINISHING']}
    finishing_g_code = FinishingGCodeGenerator(input_file_path, finishing_config).generate_gcode()

    cutting_config = {**CONFIG['COMMON'], **CONFIG['CUTTING']}
    cutting_gcode = CuttingGCodeGenerator(input_file_path, cutting_config).generate_gcode()

    g_code = '\n'.join((roughing_gcode, finishing_g_code, cutting_gcode))
    with open(output_file_path, "w", encoding='utf8') as file:
        file.write(g_code)

if __name__ == "__main__":
    INSOLE_FILE_PATH = r'output_files\insole.STL'
    OUTPUT_FILE_PATH = r"gcode_completo.txt"
    generate_gcode(INSOLE_FILE_PATH, OUTPUT_FILE_PATH)