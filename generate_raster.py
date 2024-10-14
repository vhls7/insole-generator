import matplotlib.pyplot as plt
import numpy as np

from functions.algebric_functions import intersect_line_triangle
from generate_2d_contour import InsoleMeshProcessor


def line_segment_intersection(p1, p2, a, b):
    """
    Check if the lines intersect and return the intersection point if they do; otherwise, return None..
    Retorna o ponto de interseção (x, y) se houver, caso contrário retorna None.

    p1 + t * (p2 - p1) = a + u * (b - a)
    t * (p2 - p1) - u * (b - a) = a - p1
    Using Cramer
    [(p2 - p1)x - (b - a)x] * [t] = [(a - p1)x]
    [(p2 - p1)y - (b - a)y] * [u] = [(a - p1)y]
    t = Dt/D; u = Du/D
    """
    p1p2 = p2 - p1
    ab = b - a

    det = np.linalg.det([p1p2, ab])

    vectors_are_parallel = np.isclose(det, 0)
    if vectors_are_parallel:
        return None

    t = np.linalg.det([a - p1, ab]) / det
    u = np.linalg.det([a - p1, p1p2]) / det

    # Check if intersection is in line limits
    if 0 <= t <= 1 and 0 <= u <= 1:
        # Ponto de interseção
        intersection = p1 + t * p1p2
        return intersection

    return None

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

        intersection = line_segment_intersection(p1, p2, a, b)
        if intersection is not None:
            intersections.append(intersection)

    return np.asarray(intersections)

def get_all_x_intersections(x_min, x_max, y_val, clusters_information):
    p1 = np.asarray([x_min, y_val])
    p2 = np.asarray([x_max, y_val])
    intersections = np.empty((0, 2))
    for cluster_info in clusters_information:
        cur_intersections = find_intersections_with_contour([p1, p2], cluster_info['ordered_points'][:, :2])
        if cur_intersections.ndim == 2:
            intersections = np.concatenate((intersections, cur_intersections))
    intersections = intersections[np.argsort(intersections[:, 0])]
    return intersections

def has_surface_above_point(x, y, z, triangles, tolerance):
    point1 = np.asarray([x, y, z])
    point2 = np.asarray([x, y, z + 10])
    filt_triangles = triangles[
        np.any(np.abs(triangles[:, :, 0] - x) < tolerance, axis=1)
        & np.any(np.abs(triangles[:, :, 1] - y) < tolerance, axis=1)
    ]
    return np.any([
        intersect_line_triangle(point1, point2, np.array(a), np.array(b), np.array(c))
        for a, b, c in filt_triangles
    ])


INSOLE_FILE_PATH = r'output_files\insole.STL'
Z_VAL = 1
# INSOLE_FILE_PATH = r'input_files\test_complex.STL'
# Z_VAL = 16
STEP_OVER = 3
RASTER_STEP = 1
MIN_RADIUS = 3
TOOL_DIAMETER = 6
TOOL_RADIUS = TOOL_DIAMETER/2

insole_proc = InsoleMeshProcessor(INSOLE_FILE_PATH, MIN_RADIUS)
contours_information = insole_proc.process_contours(Z_VAL)
clusters_information = contours_information['clusters']
intersection_points_2d = contours_information['intersection_points_2d']

triangles = insole_proc.get_triangles
filtered_triangles = triangles[np.any(triangles[:, :, 2] > Z_VAL, axis=1)]


min_y_point_coord = intersection_points_2d[np.argmin(intersection_points_2d[:, 1])]
max_y_point_coord = intersection_points_2d[np.argmax(intersection_points_2d[:, 1])]
min_x_point_coord = intersection_points_2d[np.argmin(intersection_points_2d[:, 0])]
max_x_point_coord = intersection_points_2d[np.argmax(intersection_points_2d[:, 0])]

y_max = max_y_point_coord[1]
y_min = min_y_point_coord[1]
x_max = max_x_point_coord[0]
x_min = min_x_point_coord[0]

x_grid_vals = np.arange(x_min - RASTER_STEP, x_max + RASTER_STEP*2, RASTER_STEP)
y_grid_vals = np.arange(y_min, y_max + STEP_OVER, STEP_OVER)
boolean_matrix = np.full((x_grid_vals.size, y_grid_vals.size), True)

for y_index, y_val in enumerate(y_grid_vals):
    intersections = get_all_x_intersections(x_min, x_max, y_val, clusters_information)

    if len(intersections) == 0:
        boolean_matrix[:, y_index] = False
        continue

    for i, (start, end) in enumerate(zip(intersections, intersections[1:])):
        x_start, x_end = start[0], end[0]
        if i == 0:
            boolean_matrix[x_grid_vals <= x_start, y_index] = False
        if i == len(intersections)-2: # If there is a single intersection, the unique iteration will reach both if statements.
            boolean_matrix[x_grid_vals >= x_end, y_index] = False

        x_points = x_grid_vals[((x_grid_vals >= x_start) & (x_grid_vals <= x_end))]
        if not x_points.size:
            continue
        mid_x = x_points[x_points.size // 2]
        if has_surface_above_point(mid_x, y_val, Z_VAL, filtered_triangles, STEP_OVER): # tolerance should be defined in function of mesh element size
            boolean_matrix[(x_grid_vals >= x_start) & (x_grid_vals <= x_end), y_index] = False


true_coords = [(x_grid_vals[x_idx], y_grid_vals[y_idx]) for y_idx in range(len(y_grid_vals)) for x_idx in range(len(x_grid_vals)) if boolean_matrix[x_idx, y_idx]]
x_true, y_true = zip(*true_coords)

plt.scatter(x_true, y_true, c='blue', marker='o', s=1, label='True Points')

for cluster_info in clusters_information:
    ordered_points = cluster_info['ordered_points']
    plt.plot(ordered_points[:, 0], ordered_points[:, 1], 'ro-', markersize=3, label='Contour')

plt.xlabel('X values')
plt.ylabel('Y values')
plt.title('Scatter Plot of True Points with Contours')
plt.legend()
plt.show()