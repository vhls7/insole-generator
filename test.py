import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import CubicSpline

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

    return intersections

# Exemplo de uso
# Definir o segmento de reta
segment = np.array([(0.5, -1.0), (0.5, 1.0)])

# Gerar o contorno fechado (mesmo exemplo do spline_interpolation)
points = np.array([
    [1, 0], [0.8, 0.5], [0.5, 0.8], [0, 1], [-0.5, 0.8], [-0.8, 0.5], 
    [-1, 0], [-0.8, -0.5], [-0.5, -0.8], [0, -1], [0.5, -0.8], [0.8, -0.5], [1, 0]
])
new_contour = spline_interpolation(points, spacing=0.1)

# Encontrar as interseções entre o segmento e o contorno
intersections = find_intersections_with_contour(segment, new_contour)

# Plotar os resultados
plt.plot(new_contour[:, 0], new_contour[:, 1], label='Contorno Interpolado')
plt.plot([segment[0][0], segment[1][0]], [segment[0][1], segment[1][1]], 'r-', label='Segmento de Reta')

# Plotar as interseções
if intersections:
    intersections = np.array(intersections)
    plt.plot(intersections[:, 0], intersections[:, 1], 'go', label='Interseções')

# Configurações do plot
plt.legend()
plt.axis('equal')
plt.show()
