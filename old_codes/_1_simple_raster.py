import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import CubicSpline
from functions.generate_2d_contour import InsoleMeshProcessor
import pyvista as pv

def spline_interpolation(points, spacing):

    x, y = points[:, 0], points[:, 1]
    t = np.linspace(0, 1, len(points))

    linear_distances = np.sqrt(np.sum(np.diff(points, axis=0)**2, axis=1)) # sqrt (Δx^2 + Δy^2)
    cumulative_dist = np.sum(linear_distances)

    cs_x = CubicSpline(t, x, bc_type='periodic')  # 'periodic' for closed contour
    cs_y = CubicSpline(t, y, bc_type='periodic')

    # Criar novos pontos interpolados
    t_new = np.linspace(0, 1, int(cumulative_dist / spacing))
    x_new = cs_x(t_new)
    y_new = cs_y(t_new)

    return np.column_stack((x_new, y_new))

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


INSOLE_FILE_PATH = r'output_files\insole.stl'
STEP_OVER = 3
Z_VAL = 1
MIN_RADIUS = 3
TOOL_DIAMETER = 6
TOOL_RADIUS = TOOL_DIAMETER/2
processor = InsoleMeshProcessor(INSOLE_FILE_PATH, MIN_RADIUS)
contours_information = processor.process_contours(Z_VAL)
ordered_points = contours_information[0]['ordered_points']

new_contour = spline_interpolation(ordered_points, spacing=3)
# plt.plot(new_contour[:, 0], new_contour[:, 1], '-o', label='Contorno Interpolado')
# plt.show()


min_y_point = ordered_points[np.argmin(ordered_points[:, 1])]
max_y_point = ordered_points[np.argmax(ordered_points[:, 1])]
min_x_point = ordered_points[np.argmin(ordered_points[:, 0])]
max_x_point = ordered_points[np.argmax(ordered_points[:, 0])]
steps = int((max_y_point[1] - min_y_point[1]) / STEP_OVER) + 1

x_start, x_end, y_pos = None, None, None
lines = []
for i in range(1, steps):
    last_y = y_pos
    last_x_end = x_end

    y_pos = min_y_point[1] + (i * STEP_OVER)
    p1 = np.asarray([min_x_point[0] - 1, y_pos])
    p2 = np.asarray([max_x_point[0] + 1, y_pos])

    intersections = find_intersections_with_contour([p1, p2], new_contour)
    if intersections.shape != (2, 2):
        break
    lower_x = np.min(intersections[:, 0])
    upper_x = np.max(intersections[:, 0])

    if (x_end is None) or (np.abs(x_end - lower_x) < np.abs(x_end - upper_x)):
        x_start, x_end = lower_x, upper_x
    else:
        x_start, x_end = upper_x, lower_x

    if i > 1:
        lines.append([[last_x_end, last_y, Z_VAL], [x_start, y_pos, Z_VAL]])
    lines.append([[x_start, y_pos, Z_VAL], [x_end, y_pos, Z_VAL]])



pl = pv.Plotter()
pl.add_mesh(pv.PolyData(ordered_points), color='red', point_size=3)
pl.add_lines(np.array(lines).reshape(-1, 3), color='black', width=2)
pl.add_axes(interactive=True) # type: ignore

pl.show()
