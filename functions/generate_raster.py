import numpy as np
from numpy import floating
from numpy.typing import NDArray

from functions.algebric_functions import lines_intersect_2d


class PathProcessor:
    def __init__(self, insole_proc, raster_step, step_over, z_val):
        self.insole_proc = insole_proc
        self.raster_step = raster_step
        self.step_over = step_over
        self.z_val = z_val

        self.contours_info = self.insole_proc.process_contours(self.z_val)
        self.paths = self.get_paths()

    def get_paths(self):

        x_grid_vals, y_grid_vals, bool_matrix = self._generate_boolean_matrix()

        segments_limits_per_row = self.get_segments_limits_per_row(bool_matrix)

        return self._generate_paths(segments_limits_per_row, x_grid_vals, y_grid_vals)

    def _generate_grid_values(self, intersec_points_2d: NDArray[floating]) -> tuple[NDArray[floating], NDArray[floating]]:
        """
        Generate X and Y grid values based on the given intersection points and step sizes.
        """
        x_max, y_max = np.max(intersec_points_2d, axis=0)
        x_min, y_min = np.min(intersec_points_2d, axis=0)

        x_vals = np.arange(x_min - self.raster_step, x_max + self.raster_step * 2, self.raster_step)
        y_vals = np.arange(y_min, y_max + self.step_over, self.step_over)

        return x_vals, y_vals

    def _generate_boolean_matrix(self):
        intersec_points_2d = self.contours_info['intersection_points_2d']
        only_external_contour = len(self.contours_info['clusters']) == 1
        x_grid_vals, y_grid_vals = self._generate_grid_values(intersec_points_2d)
        bool_matrix = np.full((x_grid_vals.size, y_grid_vals.size), False)

        for y_index, y_val in enumerate(y_grid_vals):
            intersections = np.empty((0, 2))

            for cluster_info in self.contours_info['clusters']:
                if cluster_info['is_raised_area'] is False or only_external_contour:
                    cluster_points = cluster_info['offset'][:, :2] if not only_external_contour else cluster_info['points'][:, :2]
                    p1 = np.asarray([np.min(x_grid_vals), y_val])
                    p2 = np.asarray([np.max(x_grid_vals), y_val])
                    cur_intersections = self.find_intersections_with_contour([p1, p2], cluster_points)
                    if cur_intersections.ndim == 2:
                        intersections = np.concatenate((intersections, cur_intersections))
            intersections = intersections[np.argsort(intersections[:, 0])]

            if len(intersections) > 0:
                self._update_boolean_matrix_for_intersections(x_grid_vals, bool_matrix, y_index, intersections)

        return x_grid_vals, y_grid_vals, bool_matrix.T

    def segment_has_intersection(self, contours_info, positions, start_x, cur_y):
        if positions:
            last_point = np.asarray(positions[-1])
            cur_point = np.asarray([start_x, cur_y])
            intersections = []
            for cl_info in contours_info['clusters']:
                is_external_contour = cl_info['cluster_idx'] == contours_info['external_contour_idx']
                points = cl_info['offset'] if not is_external_contour else cl_info['points']
                cur_intersections = self.find_intersections_with_contour([last_point, cur_point], points[:, :2])
                if cur_intersections.ndim == 2:
                    intersections.append(cur_intersections)
            if intersections:
                return True
        return False

    def _generate_paths(self, segments_limits_per_row, x_grid_values, y_grid_values):
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

                start_x, end_x = self.process_segment(x_segments[segment_idx], direction, x_grid_values)
                cur_y = y_grid_values[y_idx]

                if self.segment_has_intersection(self.contours_info, positions, start_x, cur_y):
                    break

                positions.append([start_x, cur_y])
                if start_x != end_x:
                    positions.append([end_x, cur_y])

                del segments_limits_per_row[y_idx][segment_idx]

                if self.is_last_row_with_segments(y_idx, segments_limits_per_row):
                    break

                y_idx += 1
                direction = 'right' if direction == 'left' else 'left'

            paths.append(np.asarray(positions))
        return paths

    @staticmethod
    def is_last_row_with_segments(y_idx, segments_limits_per_row):
        return y_idx + 1 == len(segments_limits_per_row) or len(segments_limits_per_row[y_idx + 1]) == 0

    @staticmethod
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

    @staticmethod
    def process_segment(x_idxs, direction, x_grid_values):
        start_x_idx = x_idxs[0] if direction == 'right' else x_idxs[1]
        end_x_idx = x_idxs[1] if direction == 'right' else x_idxs[0]
        start_x = x_grid_values[start_x_idx]
        end_x = x_grid_values[end_x_idx]
        return start_x, end_x

    @staticmethod
    def _update_boolean_matrix_for_intersections(x_grid_vals, bool_matrix, y_index, intersections):
        if len(intersections) % 2 != 0:
            raise ValueError("Number of intersections is odd!")
        for i in range(0, len(intersections), 2):
            start = intersections[i]
            end = intersections[i + 1]

            x_start, x_end = start[0], end[0]
            bool_matrix[(x_grid_vals >= x_start) & (x_grid_vals <= x_end), y_index] = True

    @staticmethod
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