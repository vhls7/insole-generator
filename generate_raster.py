import matplotlib.pyplot as plt
import numpy as np
from numpy import floating
from numpy.typing import NDArray

from functions.algebric_functions import lines_intersect_2d
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

def generate_grid_values(intersec_points_2d: NDArray[floating], raster_step: float, step_over: float) -> tuple[NDArray[floating], NDArray[floating]]:
    """
    Generate X and Y grid values based on the given intersection points and step sizes.
    """
    x_max, y_max = np.max(intersec_points_2d, axis=0)
    x_min, y_min = np.min(intersec_points_2d, axis=0)

    x_vals = np.arange(x_min - raster_step, x_max + raster_step * 2, raster_step)
    y_vals = np.arange(y_min, y_max + step_over, step_over)

    return x_vals, y_vals

def update_boolean_matrix_for_intersections(x_grid_vals, bool_matrix, y_index, intersections):
    if len(intersections) % 2 != 0:
        raise ValueError("Number of intersections is odd!")
    for i in range(0, len(intersections), 2):
        start = intersections[i]
        end = intersections[i + 1]

        x_start, x_end = start[0], end[0]
        bool_matrix[(x_grid_vals >= x_start) & (x_grid_vals <= x_end), y_index] = True

def generate_boolean_matrix(intersec_points_2d, clusters_info, raster_step, step_over):
    x_grid_vals, y_grid_vals = generate_grid_values(intersec_points_2d, raster_step, step_over)
    bool_matrix = np.full((x_grid_vals.size, y_grid_vals.size), False)

    for y_index, y_val in enumerate(y_grid_vals):
        intersections = np.empty((0, 2))

        for cluster_info in clusters_info['clusters']:
            if cluster_info['is_raised_area'] is False:
                cluster_points = cluster_info['offset'][:, :2]
                p1 = np.asarray([np.min(x_grid_vals), y_val])
                p2 = np.asarray([np.max(x_grid_vals), y_val])
                cur_intersections = find_intersections_with_contour([p1, p2], cluster_points)
                if cur_intersections.ndim == 2:
                    intersections = np.concatenate((intersections, cur_intersections))
        intersections = intersections[np.argsort(intersections[:, 0])]

        if len(intersections) > 0:
            update_boolean_matrix_for_intersections(x_grid_vals, bool_matrix, y_index, intersections)

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

    x_grid_values, y_grid_values, boolean_matrix = generate_boolean_matrix(intersection_points_2d, contours_information, RASTER_STEP, STEP_OVER)

    segments_limits_per_row = get_segments_limits_per_row(boolean_matrix)

    paths = generate_paths(segments_limits_per_row, x_grid_values, y_grid_values, contours_information)


# region Plotting the result
    true_coords = np.asarray([(x_grid_values[x_idx], y_grid_values[y_idx]) for y_idx, x_idx  in np.argwhere(boolean_matrix)])

    # plt.scatter(true_coords[:, 0], true_coords[:, 1], c='blue', marker='o', s=1, label='True Points')
    colors = ['black', 'blue', 'green', 'orange', 'purple', 'gray']
    for idx, path in enumerate(paths):
        plt.plot(path[:, 0], path[:, 1], 'o-', markersize=3, label=f'Contour {idx}', color=colors[idx % len(colors)])
    for cl_info in clusters_information:
        points = cl_info['points']
        plt.plot(points[:, 0], points[:, 1], 'ro-', markersize=3, label='Insole Contours')
        plt.plot(cl_info['offset'][:, 0], cl_info['offset'][:, 1], 'o-', markersize=3, label='Offset Contours')

    plt.gca().set(xlabel='X values', ylabel='Y values', title='Scatter Plot of True Points with Contours')
    plt.legend().set_draggable(True)
    plt.show()
# endregion