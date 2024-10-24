import matplotlib.pyplot as plt
import numpy as np
from numpy import floating
from numpy.typing import NDArray

from functions.algebric_functions import intersect_line_triangle, lines_intersect_2d
from generate_2d_contour import InsoleMeshProcessor


def find_intersections_with_contour(segment, contour_points):
    """
    Finds intersections between a line segment and the contour defined by 'contour_points'.
    
    segment: [(x1, y1), (x2, y2)] - The endpoints of the line segment.
    contour_points: List of points (N x 2) defining the closed contour, where N is the number of points 
                    and each point is represented as a tuple (x, y).
    
    Returns a list of intersection points.
    """
    intersections = []

    p1, p2 = segment

    for i in range(len(contour_points) - 1):
        a = contour_points[i]
        b = contour_points[i + 1]

        intersection = lines_intersect_2d(p1, p2, a, b)
        if intersection is not None:
            intersections.append(intersection)

    return np.asarray(intersections)

def get_all_x_intersections(x_min, x_max, y_val, clusters_info):
    p1 = np.asarray([x_min, y_val])
    p2 = np.asarray([x_max, y_val])
    intersections = np.empty((0, 2))
    for cluster_info in clusters_info['clusters']:
        is_external_contour = cluster_info['cluster_idx'] == clusters_info['external_contour_idx']
        cluster_points = cluster_info['offset'][:, :2] if not is_external_contour else cluster_info['points'][:, :2]
        cur_intersections = find_intersections_with_contour([p1, p2], cluster_points)
        if cur_intersections.ndim == 2:
            intersections = np.concatenate((intersections, cur_intersections))
    intersections = intersections[np.argsort(intersections[:, 0])]
    return intersections

def has_surface_above_point(x, y, z, triangles, tolerance):
    point1 = np.asarray([x, y, z])
    point2 = np.asarray([x, y, z + 100])
    filt_triangles = triangles[
        np.any(np.abs(triangles[:, :, 0] - x) < tolerance, axis=1)
        & np.any(np.abs(triangles[:, :, 1] - y) < tolerance, axis=1)
    ]
    return np.any([
        intersect_line_triangle(point1, point2, np.array(a), np.array(b), np.array(c))
        for a, b, c in filt_triangles
    ])

def has_surface_above_points(x_values, y, z, triangles, tolerance):
    
    for x in x_values:
        point1 = np.asarray([x, y, z])
        point2 = np.asarray([x, y, z + 100])
        
        filt_triangles = triangles[
            np.any(np.abs(triangles[:, :, 0] - x) < tolerance, axis=1)
            & np.any(np.abs(triangles[:, :, 1] - y) < tolerance, axis=1)
        ]
        
        if np.any([
            intersect_line_triangle(point1, point2, np.array(a), np.array(b), np.array(c))
            for a, b, c in filt_triangles
        ]):
            return True

    return False


def generate_grid_values(intersec_points_2d: NDArray[floating], raster_step: float, step_over: float) -> tuple[NDArray[floating], NDArray[floating]]:
    """
    Generate X and Y grid values based on the given intersection points and step sizes.
    """
    x_max, y_max = np.max(intersec_points_2d, axis=0)
    x_min, y_min = np.min(intersec_points_2d, axis=0)

    x_vals = np.arange(x_min - raster_step, x_max + raster_step * 2, raster_step)
    y_vals = np.arange(y_min, y_max + step_over, step_over)

    return x_vals, y_vals

def update_boolean_matrix_for_intersections(x_grid_vals, bool_matrix, y_index, intersections, z_val, y_val, filt_triangles, step_over):
    for i, (start, end) in enumerate(zip(intersections, intersections[1:])):
        x_start, x_end = start[0], end[0]

        if i == 0:
            bool_matrix[x_grid_vals <= x_start, y_index] = False
        if i == len(intersections) - 2: # If there is a single intersection, the unique iteration will reach both if statements.
            bool_matrix[x_grid_vals >= x_end, y_index] = False

        x_vals_to_test = np.linspace(x_start, x_end, 5)
        if has_surface_above_points(x_vals_to_test, y_val, z_val, filt_triangles, step_over):
            bool_matrix[(x_grid_vals >= x_start) & (x_grid_vals <= x_end), y_index] = False

def generate_boolean_matrix(intersec_points_2d, clusters_info, filt_triangles, z_val, raster_step, step_over):
    x_grid_vals, y_grid_vals = generate_grid_values(intersec_points_2d, raster_step, step_over)
    bool_matrix = np.full((x_grid_vals.size, y_grid_vals.size), True)

    for y_index, y_val in enumerate(y_grid_vals):
        intersections = get_all_x_intersections(np.min(x_grid_vals), np.max(x_grid_vals), y_val, clusters_info)

        if len(intersections) == 0:
            bool_matrix[:, y_index] = False
        else:
            update_boolean_matrix_for_intersections(x_grid_vals, bool_matrix, y_index, intersections, z_val, y_val, filt_triangles, step_over)

    return x_grid_vals, y_grid_vals, bool_matrix.T

def segment_has_intersection(positions, start_x, cur_y, clusters_information):
    if positions:
        last_point = np.asarray(positions[-1])
        cur_point = np.asarray([start_x, cur_y])
        intersections = []
        for cl_info in clusters_information['clusters']:
            is_external_contour = cl_info['cluster_idx'] == clusters_information['external_contour_idx']
            points = cl_info['offset'] if not is_external_contour else cl_info['points']
            cur_intersections = find_intersections_with_contour([last_point, cur_point], points[:, :2])
            if cur_intersections.ndim == 2:
                intersections.append(cur_intersections)
        if intersections:
            return True
    return False

def process_segment(x_idxs, direction, x_grid_values):
    start_x_idx = x_idxs[0] if direction == 'right' else x_idxs[1]
    end_x_idx = x_idxs[1] if direction == 'right' else x_idxs[0]
    start_x = x_grid_values[start_x_idx]
    end_x = x_grid_values[end_x_idx]
    return start_x, end_x

def is_last_row_with_segments(y_idx, segments_limits_per_row):
    return y_idx + 1 == len(segments_limits_per_row) or len(segments_limits_per_row[y_idx + 1]) == 0

def get_segments_limits_per_row(bool_matrix):
    """
    Given a boolean matrix, this function returns a list of segment limits
    for each row where segments of True values are found.
    """
    segments_limits_per_row = []
    for row in bool_matrix:
        x_idxs = np.nonzero(row)[0]
        if len(x_idxs) > 0:
            segments = np.split(x_idxs, np.nonzero(np.diff(x_idxs) != 1)[0] + 1)
            segment_limits = [(segment[0], segment[-1]) for segment in segments]
            segments_limits_per_row.append(segment_limits)
        else:
            segments_limits_per_row.append([])

    return segments_limits_per_row

def generate_paths(segments_limits_per_row, x_grid_values, y_grid_values, clusters_information):
    paths = []
    while (y_idx := next((i for i, segments in enumerate(segments_limits_per_row) if segments), None)):
        positions = []
        end_x = None
        segment_idx = 0
        direction = 'right'

        while True:
            x_segments = segments_limits_per_row[y_idx]

            if end_x is not None:
                segment_idx = np.argmin(np.abs(np.mean(x_segments, axis=1) - end_x))

            start_x, end_x = process_segment(x_segments[segment_idx], direction, x_grid_values)
            cur_y = y_grid_values[y_idx]

            if segment_has_intersection(positions, start_x, cur_y, clusters_information):
                break

            positions.append([start_x, cur_y])
            if start_x != end_x:
                positions.append([end_x, cur_y])

            del segments_limits_per_row[y_idx][segment_idx]

            if is_last_row_with_segments(y_idx, segments_limits_per_row):
                break

            y_idx += 1
            direction = 'right' if direction == 'left' else 'left'

        paths.append(np.asarray(positions))
    return paths

if __name__ == "__main__":
    INSOLE_FILE_PATH = r'output_files\insole.STL'
    Z_VAL = 1
    # INSOLE_FILE_PATH = r'input_files\test_complex.STL'
    # Z_VAL = 16
    STEP_OVER = 3
    RASTER_STEP = 1
    MIN_RADIUS = 3


    insole_proc = InsoleMeshProcessor(INSOLE_FILE_PATH, MIN_RADIUS)
    contours_information = insole_proc.process_contours(Z_VAL)
    clusters_information = contours_information['clusters']
    intersection_points_2d = contours_information['intersection_points_2d']

    all_triangles = insole_proc.get_triangles
    filtered_triangles = all_triangles[np.any(all_triangles[:, :, 2] > Z_VAL, axis=1)]

    x_grid_values, y_grid_values, boolean_matrix = generate_boolean_matrix(intersection_points_2d, contours_information, filtered_triangles, Z_VAL, RASTER_STEP, STEP_OVER)

    segments_limits_per_row = get_segments_limits_per_row(boolean_matrix)

    paths = generate_paths(segments_limits_per_row, x_grid_values, y_grid_values, contours_information)


# region Plotting the result
    true_coords = np.asarray([(x_grid_values[x_idx], y_grid_values[y_idx]) for y_idx, x_idx  in np.argwhere(boolean_matrix)])

    # plt.scatter(true_coords[:, 0], true_coords[:, 1], c='blue', marker='o', s=1, label='True Points')
    colors = ['black', 'blue', 'green', 'orange', 'purple', 'gray']
    for i, path in enumerate(paths):
        plt.plot(path[:, 0], path[:, 1], 'o-', markersize=3, label=f'Contour {i}', color=colors[i % len(colors)])
    for cl_info in clusters_information:
        points = cl_info['points']
        plt.plot(points[:, 0], points[:, 1], 'ro-', markersize=3, label='Insole Contours')
        plt.plot(cl_info['offset'][:, 0], cl_info['offset'][:, 1], 'o-', markersize=3, label='Insole Contours')

    plt.gca().set(xlabel='X values', ylabel='Y values', title='Scatter Plot of True Points with Contours')
    plt.legend().set_draggable(True)
    plt.show()
# endregion