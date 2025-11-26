#$ kojto_profiles/utils/compute_section_properties_polygons.py

import math
from shapely.geometry import Polygon, MultiPolygon, Point, LineString
from shapely.ops import unary_union

def _are_points_collinear(p1, p2, p3, tolerance=1e-10):
    """
    Check if three points are collinear (lie on the same line).
    Args:
        p1, p2, p3: Points as (x,y) tuples
        tolerance: Tolerance for floating point comparison
    Returns:
        bool: True if points are collinear
    """
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3

    # Calculate the area of the triangle formed by the three points
    # If the area is close to zero, the points are collinear
    area = abs((x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2)) / 2)
    return area < tolerance

def _filter_collinear_points(points, tolerance=1e-10):
    """
    Filter out points that are collinear with their adjacent points.
    Args:
        points: List of (x,y) coordinate tuples
        tolerance: Tolerance for floating point comparison
    Returns:
        List of filtered points
    """
    if len(points) <= 2:
        return points  # Need at least 3 points to check for collinearity

    filtered_points = [points[0]]  # Always keep the first point

    for i in range(1, len(points) - 1):
        prev_point = points[i - 1]
        current_point = points[i]
        next_point = points[i + 1]

        if not _are_points_collinear(prev_point, current_point, next_point, tolerance):
            filtered_points.append(current_point)

    filtered_points.append(points[-1])  # Always keep the last point
    return filtered_points

def compute_section_properties(polygons_data, material_density):

    if not polygons_data:
        return {
            "profile_cross_sectional_area": 0.0,  # cm²
            "profile_weight": 0.0,               # kg/m
            "center_of_mass_x": 0.0,             # mm
            "center_of_mass_y": 0.0,             # mm
            "jx": 0.0,                           # cm⁴
            "jy": 0.0,                           # cm⁴
            "wx": 0.0,                           # cm³
            "wy": 0.0,                           # cm³
            "max_height": 0.0,                   # mm
            "max_width": 0.0,                    # mm
            "perimeter_coordinates": [],         # List of (x,y) coordinates
        }

    # Convert input coordinates to Shapely Polygons and validate
    add_polygons = []
    subtract_polygons = []

    # Handle both input formats
    for item in polygons_data:
        if isinstance(item, dict):
            points = item.get('points', [])
            is_subtract = item.get('is_subtract', False)
        else:
            points = item
            is_subtract = False

        if len(points) >= 3 and all(len(pt) == 2 for pt in points):
            # Only process valid polygons (at least 3 unique points)
            if len(set(tuple(pt) for pt in points)) >= 3:
                poly = Polygon(points)
                if poly.is_valid:
                    if is_subtract:
                        subtract_polygons.append(poly)
                    else:
                        add_polygons.append(poly)
                else:
                    # Try to fix invalid polygon
                    fixed_poly = poly.buffer(0)
                    if fixed_poly.is_valid and not fixed_poly.is_empty:
                        if is_subtract:
                            subtract_polygons.append(fixed_poly)
                        else:
                            add_polygons.append(fixed_poly)

    if not add_polygons:
        return {
            "profile_cross_sectional_area": 0.0,
            "profile_weight": 0.0,
            "center_of_mass_x": 0.0,
            "center_of_mass_y": 0.0,
            "jx": 0.0,
            "jy": 0.0,
            "wx": 0.0,
            "wy": 0.0,
            "max_height": 0.0,
            "max_width": 0.0,
            "perimeter_coordinates": [],
        }

    # Union the additive polygons
    union_poly = unary_union(add_polygons)

    # Subtract the internal polygons
    for subtract_poly in subtract_polygons:
        union_poly = union_poly.difference(subtract_poly)

    if union_poly.is_empty:
        return {
            "profile_cross_sectional_area": 0.0,
            "profile_weight": 0.0,
            "center_of_mass_x": 0.0,
            "center_of_mass_y": 0.0,
            "jx": 0.0,
            "jy": 0.0,
            "wx": 0.0,
            "wy": 0.0,
            "max_height": 0.0,
            "max_width": 0.0,
            "perimeter_coordinates": [],
        }

    area_mm2 = union_poly.area  # Area in mm²
    area_cm2 = area_mm2 / 100  # Convert to cm²
    centroid = union_poly.centroid
    cm_x, cm_y = centroid.x, centroid.y  # Centroid in mm

    # Compute moments of inertia about the section centroid (in mm⁴, then convert to cm⁴)
    jx_mm4 = 0.0
    jy_mm4 = 0.0
    for poly in add_polygons:
        if not union_poly.intersects(poly):
            continue
        area = poly.area  # mm²
        cx, cy = poly.centroid.x, poly.centroid.y  # mm
        # Distance from section centroid
        dx = cx - cm_x  # mm
        dy = cy - cm_y  # mm
        # Local moments of inertia (approximate as rectangle)
        bounds = poly.bounds
        width = bounds[2] - bounds[0]  # mm
        height = bounds[3] - bounds[1]  # mm
        jx_local = (width * height ** 3) / 12 if width > 0 and height > 0 else 0  # mm⁴
        jy_local = (height * width ** 3) / 12 if width > 0 and height > 0 else 0  # mm⁴
        # Parallel axis theorem: I_total = I_local + A * d²
        jx_mm4 += jx_local + area * (dy ** 2)  # mm⁴
        jy_mm4 += jy_local + area * (dx ** 2)  # mm⁴

    # Subtract moments of inertia for internal polygons
    for poly in subtract_polygons:
        if not union_poly.intersects(poly):
            continue
        area = poly.area  # mm²
        cx, cy = poly.centroid.x, poly.centroid.y  # mm
        # Distance from section centroid
        dx = cx - cm_x  # mm
        dy = cy - cm_y  # mm
        # Local moments of inertia (approximate as rectangle)
        bounds = poly.bounds
        width = bounds[2] - bounds[0]  # mm
        height = bounds[3] - bounds[1]  # mm
        jx_local = (width * height ** 3) / 12 if width > 0 and height > 0 else 0  # mm⁴
        jy_local = (height * width ** 3) / 12 if width > 0 and height > 0 else 0  # mm⁴
        # Parallel axis theorem: subtract the moment of inertia for internal areas
        jx_mm4 -= (jx_local + area * (dy ** 2))  # mm⁴
        jy_mm4 -= (jy_local + area * (dx ** 2))  # mm⁴

    # Convert to cm⁴
    jx_cm4 = jx_mm4 / 10000
    jy_cm4 = jy_mm4 / 10000

    # Section moduli: J (cm⁴) / distance (cm) = cm³
    bounds = union_poly.bounds
    max_y_mm = max(abs(bounds[1] - cm_y), abs(bounds[3] - cm_y))  # mm
    max_x_mm = max(abs(bounds[0] - cm_x), abs(bounds[2] - cm_x))  # mm
    max_y_cm = max_y_mm / 10 if max_y_mm > 0 else 0.000001  # cm
    max_x_cm = max_x_mm / 10 if max_x_mm > 0 else 0.000001  # cm

    # Get perimeter coordinates from the union polygon
    perimeter_coordinates = []
    if not union_poly.is_empty:
        if isinstance(union_poly, Polygon):
            perimeter_coordinates = list(union_poly.exterior.coords[:-1])  # Exclude duplicate end point
        elif isinstance(union_poly, MultiPolygon):
            for poly in union_poly.geoms:
                perimeter_coordinates.extend(list(poly.exterior.coords[:-1]))

    # Filter out collinear points from the perimeter
    perimeter_coordinates = _filter_collinear_points(perimeter_coordinates)

    return {
        "profile_cross_sectional_area": area_cm2,              # cm²
        "profile_weight": (area_mm2 / 1000000) * material_density,  # mm² to m², kg/m
        "center_of_mass_x": cm_x,                             # mm
        "center_of_mass_y": cm_y,                             # mm
        "jx": jx_cm4,                                         # cm⁴
        "jy": jy_cm4,                                         # cm⁴
        "wx": jx_cm4 / max_y_cm if jx_cm4 > 0 else 0.0,       # cm³
        "wy": jy_cm4 / max_x_cm if jy_cm4 > 0 else 0.0,       # cm³
        "max_height": bounds[3] - bounds[1],                  # mm
        "max_width": bounds[2] - bounds[0],                   # mm
        "perimeter_coordinates": perimeter_coordinates,       # List of (x,y) coordinates
    }
