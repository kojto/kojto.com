#$ kojto_profiles/utils/compute_strip_points.py

import math

def compute_strip_points(point_1_x, point_1_y, point_2_x, point_2_y, thickness, angle_1, angle_2):


    def rotate_point(center, point, angle_deg, clockwise=False):
        angle_rad = math.radians(angle_deg)
        if clockwise:
            angle_rad = -angle_rad
        rel_x = point[0] - center[0]
        rel_y = point[1] - center[1]
        new_x = rel_x * math.cos(angle_rad) - rel_y * math.sin(angle_rad)
        new_y = rel_x * math.sin(angle_rad) + rel_y * math.cos(angle_rad)
        return (new_x + center[0], new_y + center[1])

    def offset_line(p1, p2, angle_p1, angle_p2, thickness):
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = math.sqrt(dx**2 + dy**2)
        if length == 0:
            return p1, p2
        dx_norm = dx / length
        dy_norm = dy / length
        perp_dx = -dy_norm
        perp_dy = dx_norm
        direction_p1 = 1 if 0 <= angle_p1 <= 180 else -1
        direction_p2 = 1 if 0 <= angle_p2 <= 180 else -1
        offset_x_p1 = thickness * perp_dx * direction_p1
        offset_y_p1 = thickness * perp_dy * direction_p1
        offset_x_p2 = thickness * perp_dx * direction_p2
        offset_y_p2 = thickness * perp_dy * direction_p2
        return ((p1[0] + offset_x_p1, p1[1] + offset_y_p1), (p2[0] + offset_x_p2, p2[1] + offset_y_p2))

    def line_intersection(p1, p2, p3, p4):
        x1, y1 = p1
        x2, y2 = p2
        x3, y3 = p3
        x4, y4 = p4
        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denom) < 1e-10:
            return None
        t_num = (x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)
        t = t_num / denom
        x = x1 + t * (x2 - x1)
        y = y1 + t * (y2 - y1)
        x = 0.0 if abs(x) < 1e-10 else x
        y = 0.0 if abs(y) < 1e-10 else y
        return (x, y)

    p1 = (point_1_x, point_1_y)
    p2 = (point_2_x, point_2_y)
    thickness = thickness or 0.0
    angle_p1 = angle_1 or 45
    angle_p2 = angle_2 or 45

    # Default to original points if thickness is 0
    point_1o = (point_1_x, point_1_y)
    point_2o = (point_2_x, point_2_y)

    if thickness > 0:
        p3, p4 = offset_line(p1, p2, angle_p1, angle_p2, thickness)
        p5 = rotate_point(p1, p2, angle_p1, clockwise=False)
        p6 = rotate_point(p2, p1, angle_p2, clockwise=True)
        p1o = line_intersection(p1, p5, p3, p4)
        p2o = line_intersection(p2, p6, p3, p4)

        if p1o:
            point_1o = p1o
        if p2o:
            point_2o = p2o

    return point_1o, point_2o
