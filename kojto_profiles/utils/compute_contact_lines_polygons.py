#$ kojto_profiles/utils/compute_contact_lines_polygons.py

from shapely.geometry import Polygon, LineString, Point
from shapely.ops import unary_union
from math import sqrt

def compute_contact_lines(polygons_data):
    TOLERANCE = 0.01

    if not polygons_data:
        return [], [], []

    # Filter out internal polygons, only process external ones
    external_polygons = []
    for item in polygons_data:
        if isinstance(item, dict):
            points = item.get('points', [])
            is_subtract = item.get('is_subtract', False)
            if not is_subtract and len(points) >= 3:
                external_polygons.append(points)
        else:
            if len(item) >= 3:
                external_polygons.append(item)

    if not external_polygons:
        return [], [], []

    original_polygons = [Polygon(poly) for poly in external_polygons]
    edges = []
    for poly_idx, poly in enumerate(external_polygons):
        coords = poly
        for i in range(len(coords)):
            start = tuple(coords[i])
            end = tuple(coords[(i + 1) % len(coords)])
            if sqrt((end[0] - start[0])**2 + (end[1] - start[1])**2) > TOLERANCE:
                edges.append((LineString([start, end]), start, end, poly_idx))

    union_poly = unary_union(original_polygons)
    boundary_points = set(union_poly.exterior.coords[:-1]) if isinstance(union_poly, Polygon) else set().union(*[p.exterior.coords[:-1] for p in union_poly.geoms])
    boundaries = sorted(list(boundary_points))
    original_corners = set().union(*[tuple(pt) for poly in external_polygons for pt in poly])
    filtered_boundary_points = boundary_points - original_corners

    def points_equal(p1, p2, tol=TOLERANCE):
        return sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2) <= tol

    split_edges = []
    for line, start, end, poly_idx in edges:
        split_points = [start]
        for other_line, o_start, o_end, other_idx in edges:
            if poly_idx != other_idx:
                intersection = line.intersection(other_line)
                if intersection and not intersection.is_empty:
                    if intersection.geom_type == 'Point':
                        pt = (intersection.x, intersection.y)
                        if not any(points_equal(pt, sp) for sp in split_points):
                            split_points.append(pt)
                    elif intersection.geom_type == 'LineString':
                        for coord in intersection.coords:
                            pt = tuple(coord)
                            if not any(points_equal(pt, sp) for sp in split_points):
                                split_points.append(pt)
        for pt in filtered_boundary_points:
            if line.distance(Point(pt)) <= TOLERANCE and not any(points_equal(pt, sp) for sp in split_points):
                split_points.append(pt)
        split_points.append(end)
        if abs(end[0] - start[0]) > abs(end[1] - start[1]):
            split_points.sort(key=lambda p: p[0])
        else:
            split_points.sort(key=lambda p: p[1])
        for i in range(len(split_points) - 1):
            if not points_equal(split_points[i], split_points[i+1]):
                split_edges.append((split_points[i], split_points[i+1], poly_idx))

    contact_lines = []
    for i, (start1, end1, poly1) in enumerate(split_edges):
        for j, (start2, end2, poly2) in enumerate(split_edges[i+1:], start=i+1):
            if poly1 != poly2:
                line1 = LineString([start1, end1])
                line2 = LineString([start2, end2])
                intersection = line1.intersection(line2)
                if intersection and not intersection.is_empty:
                    if intersection.geom_type == 'LineString' and intersection.length > TOLERANCE:
                        coords = list(intersection.coords)
                        contact = (coords[0], coords[-1])
                        if not any(points_equal(contact[0], c[0]) and points_equal(contact[1], c[1]) for c in contact_lines):
                            contact_lines.append(contact)
                    elif intersection.geom_type == 'Point':
                        if line1.contains(Point(start2)) and line1.contains(Point(end2)):
                            contact = (start2, end2)
                            if not any(points_equal(contact[0], c[0]) and points_equal(contact[1], c[1]) for c in contact_lines):
                                contact_lines.append(contact)

    formatted_split_edges = [(start, end) for start, end, _ in split_edges]
    return contact_lines, formatted_split_edges, boundaries
