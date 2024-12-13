from generate_roughing_gcode import RoughingGCodeGenerator
from generate_cut_gcode import CuttingGCodeGenerator
from generate_finishing_gcode import FinishingGCodeGenerator


INSOLE_FILE_PATH = r'output_files\insole.STL'


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

# Merge configurations when initializing generators
roughing_config = {**CONFIG['COMMON'], **CONFIG['ROUGHING']}
roughing_gcode = RoughingGCodeGenerator(INSOLE_FILE_PATH, roughing_config).generate_gcode()

finishing_config = {**CONFIG['COMMON'], **CONFIG['FINISHING']}
finishing_g_code = FinishingGCodeGenerator(INSOLE_FILE_PATH, finishing_config).generate_gcode()

cutting_config = {**CONFIG['COMMON'], **CONFIG['CUTTING']}
cutting_gcode = CuttingGCodeGenerator(INSOLE_FILE_PATH, cutting_config).generate_gcode()

g_code = '\n'.join((roughing_gcode, finishing_g_code, cutting_gcode))
with open("gcode_completo.txt", "w", encoding='utf8') as file:
    file.write(g_code)