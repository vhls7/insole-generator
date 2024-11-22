import numpy as np
import pyvista as pv


def print_progress_bar(iteration, total, length=50):
    percent = f'{100 * (iteration / float(total)):.1f}'
    filled_length = int(length * iteration // total)
    bar = '█' * filled_length + '-' * (length - filled_length)
    print(f'\r|{bar}| {percent}% Complete', end='')

def get_centroid(your_mesh):
    centroid = np.mean(your_mesh.points.reshape(-1, 3), axis=0)
    return centroid

def get_centroid2(your_mesh):
    bounds = your_mesh.bounds

    # Calculate the centroid as the average of the min and max coordinates
    centroid = np.array([
        (bounds[0] + bounds[1]) / 2, # x
        (bounds[2] + bounds[3]) / 2, # y
        (bounds[4] + bounds[5]) / 2  # z
    ])
    return centroid

def process_stl(file_path, angle_x=0, angle_y=0, angle_z=0, axis=None, cut_value=None):
    mesh = pv.read(file_path)
    if not isinstance(mesh, pv.PolyData):
        raise FileNotFoundError("Error reading the file")

    mesh = rotate_mesh(mesh, angle_x, angle_y, angle_z, True)

    # Apply the cut
    if axis and cut_value is not None:
        # Translating the mesh to make minimun z coord be zero
        min_z = mesh.bounds[4]
        mesh.translate([0, 0, -min_z], inplace=True)
        mesh = cut_mesh(mesh, axis, cut_value)

    mesh_centroid = get_centroid2(mesh)
    mesh.translate(-mesh_centroid, inplace=True)

    return mesh

def rotate_mesh(mesh: pv.PolyData, angle_x=0, angle_y=0, angle_z=0, around_centroid=False) -> pv.PolyData:
    """Rotate the mesh around its centroid."""
    centroid = get_centroid(mesh)

    if around_centroid:
        mesh.translate(-centroid, inplace=True)

    mesh.rotate_x(angle_x, inplace=True)
    mesh.rotate_y(angle_y, inplace=True)
    mesh.rotate_z(angle_z, inplace=True)

    if around_centroid:
        mesh.translate(centroid, inplace=True)

    return mesh

def cut_mesh(mesh: pv.PolyData, axis, cut_value=0) -> pv.PolyData:
    """Clip the mesh along a specified axis at a given cut value."""
    bounds = mesh.bounds  # mesh.bounds returns [xmin, xmax, ymin, ymax, zmin, zmax]

    if axis == 'x':
        clip_bounds = [bounds[0], cut_value, bounds[2], bounds[3], bounds[4], bounds[5]]
    elif axis == 'y':
        clip_bounds = [bounds[0], bounds[1], bounds[2], cut_value, bounds[4], bounds[5]]
    elif axis == 'z':
        clip_bounds = [bounds[0], bounds[1], bounds[2], bounds[3], bounds[4], cut_value]
    else:
        raise ValueError("Invalid axis. Choose between 'x', 'y', 'z'.")

    # Clip the mesh with the computed bounds
    cutted_mesh = mesh.clip_box(bounds=clip_bounds, invert=False)

    if cutted_mesh is not None:
        cutted_mesh = cutted_mesh.extract_surface()
        if isinstance(cutted_mesh, pv.PolyData):
            return cutted_mesh
    raise TypeError("Error cutting the file")

def esphere_filt(points, radius):
    remaining_points = points.copy()
    filtered_points = []

    while len(remaining_points) > 0:
        current_point = remaining_points[0]
        filtered_points.append(current_point)

        distances = np.linalg.norm(remaining_points - current_point, axis=1)

        remaining_points = remaining_points[distances > radius]
        print_progress_bar(len(points) - len(remaining_points), len(points), length=50)
    return np.array(filtered_points)


if __name__ == "__main__":
    SCANNED_FILE_PATH = r'input_files\CFFFP_Clayton Esquerdo.stl'
   # PARAMETRIC_INSOLE_FILE_PATH = r'input_files\base45_tipo3_S.stl'
   # PARAMETRIC_INSOLE_FILE_PATH = r'input_files\ESQ_base45_tipo3_S.stl'
    PARAMETRIC_INSOLE_FILE_PATH = r'input_files\ESQ_base45_tipo3_S.stl'
    FILT_SURF_FILE_PATH = r'output_files\filt_surf.stl'
    INSOLE_FILE_PATH = r'output_files\insole.stl'

    #scan_foot = process_stl(SCANNED_FILE_PATH, angle_x=-90, angle_y=-268, angle_z=180, axis='z', cut_value=15)
    scan_foot = process_stl(SCANNED_FILE_PATH, angle_x=-3, angle_y=1, angle_z=275, axis='z', cut_value=20)#45 esq
    parametric_insole = process_stl(PARAMETRIC_INSOLE_FILE_PATH, angle_z=280)

    scan_foot.translate([-50, -5, 4], inplace=True) # 13
    parametric_insole.translate([0, 0, 0], inplace=True) # 13
    scan_foot_coord_filt = esphere_filt(scan_foot.points,5)

    # Remaking surface
    scan_foot_coord_filt_surf = pv.wrap(scan_foot_coord_filt).reconstruct_surface() # type: ignore
    result_1 = parametric_insole.boolean_difference(scan_foot_coord_filt_surf)
    result_2 = parametric_insole.boolean_intersection(scan_foot_coord_filt_surf)

    if (result_1.volume>result_2.volume):
        result=result_1
    else:
        result=result_2
        
    scan_foot_coord_filt_surf.save(FILT_SURF_FILE_PATH)
    result.save(INSOLE_FILE_PATH) # type: ignore


    pl = pv.Plotter(shape=(1, 2))
    pl.add_mesh(scan_foot)
    pl.add_title('Superfície Original')
    pl.subplot(0, 1)

    pl.add_mesh(parametric_insole, color='orange', show_edges=False)
    pl.add_mesh(scan_foot_coord_filt_surf, color='lightblue', show_edges=False)
    pl.add_title('Superfície Reconstruida')
    pl.show()


    pl = pv.Plotter()
    pl.add_mesh(result, color='lightblue')
    pl.add_axes(interactive=True) # type: ignore
    pl.show()
