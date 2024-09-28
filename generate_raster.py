import numpy as np
import pyvista as pv
from scipy.interpolate import interp1d
from sklearn.cluster import DBSCAN


def two_d_section(solid_mesh, z_val):

    plane = pv.Plane(
        center=(0, 0, z_val),
        direction=(0, 0, 1),
        i_size=500,
        j_size=500,
        i_resolution=150,
        j_resolution=150
    ).triangulate()

    intersection, _, _ = solid_mesh.intersection(plane) # type: ignore

    intersec_points = intersection.points
    return intersec_points


INSOLE_FILE_PATH = r'output_files\insole.stl'
STEP_OVER = 4

mesh = pv.read(INSOLE_FILE_PATH)



Z_VAL = 1

points = two_d_section(mesh, Z_VAL)
points_2d = points[:, :2]

# Finding the clusters
dbscan = DBSCAN(eps=5, min_samples=5)
labels = dbscan.fit_predict(points_2d)

# Selecting only a single contour for now
cluster_points = points_2d[labels == 1]


min_y_point = cluster_points[np.argmin(cluster_points[:, 1])]
max_y_point = cluster_points[np.argmax(cluster_points[:, 1])]


m = (max_y_point[1] - min_y_point[1]) / (max_y_point[0] - min_y_point[0])
b = min_y_point[1] - m * min_y_point[0]

y_pred = m * cluster_points[:, 0] + b

above_points = cluster_points[cluster_points[:, 1] >= y_pred]
below_points = cluster_points[cluster_points[:, 1] <= y_pred]

above_interp = interp1d(above_points[:, 1], above_points[:, 0], fill_value="extrapolate") # type: ignore
bellow_interp = interp1d(below_points[:, 1], below_points[:, 0], fill_value="extrapolate") # type: ignore

steps = int((max_y_point[1] - min_y_point[1]) / STEP_OVER) + 1

x_start, x_end, y_pos = None, None, None
lines = []
for i in range(1, steps):
    last_y = y_pos
    last_x_end = x_end

    y_pos = min_y_point[1] + i * STEP_OVER

    x1 = above_interp(y_pos)
    x2 = bellow_interp(y_pos)
    if (x_end is None) or (np.abs(x_end - x1) < np.abs(x_end - x2)):
        x_start, x_end = x1, x2
    else:
        x_start, x_end = x2, x1

    if i > 1:
        lines.append([[last_x_end, last_y, Z_VAL], [x_start, y_pos, Z_VAL]])
    lines.append([[x_start, y_pos, Z_VAL], [x_end, y_pos, Z_VAL]])

y_vals = np.linspace(min_y_point[1], max_y_point[1], 50)
xvals = above_interp(y_vals)
# Visualizar os clusters e contornos
pl = pv.Plotter()
pl.add_mesh(pv.PolyData(points), color='red', point_size=10)
pl.add_points(np.column_stack((xvals, y_vals, np.full_like(xvals, Z_VAL))), color='green', point_size=8)
pl.add_lines(np.array(lines).reshape(-1, 3), color='black', width=2)
pl.add_axes(interactive=True) # type: ignore

pl.show()
