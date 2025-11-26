from shapely.geometry import Polygon, MultiPolygon, Point, LineString
from shapely.ops import unary_union
from typing import List, Tuple

def compute_external_corners(polygons: List[List[Tuple[float, float]]]) -> int:

    # Validate input
    if not isinstance(polygons, list):
        raise ValueError("Input 'polygons' must be a list.")
    if not polygons:
        return 0
    for poly in polygons:
        if not isinstance(poly, list) or len(poly) < 3 or not all(isinstance(p, tuple) and len(p) == 2 for p in poly):
            raise ValueError("Each polygon must be a list of at least 3 (x, y) coordinate tuples.")

    # Round input polygon points to three decimal places
    rounded_polygons = [[(round(x, 3), round(y, 3)) for x, y in poly] for poly in polygons]

    # Convert to Shapely polygons
    shapely_polygons = [Polygon(poly) for poly in rounded_polygons if Polygon(poly).is_valid]

    if not shapely_polygons:
        return 0

    # Perform union with Shapely
    unified = unary_union(shapely_polygons)

    # Handle Polygon or MultiPolygon
    unified_polys = [unified] if isinstance(unified, Polygon) else unified.geoms if unified.geoms else []

    if not unified_polys:
        return 0

    # Process all polygons for sharp corners
    sharp_corners = []
    tolerance = 0.1

    for unified_poly in unified_polys:
        exterior_coords = list(unified_poly.exterior.coords)[:-1]  # Exclude duplicate end point
        for i in range(len(exterior_coords)):
            p1 = exterior_coords[i - 1]
            p2 = exterior_coords[i]
            p3 = exterior_coords[(i + 1) % len(exterior_coords)]

            # Compute midpoint
            mid_x = (p1[0] + p3[0]) / 2
            mid_y = (p1[1] + p3[1]) / 2
            midpoint = Point(mid_x, mid_y)

            # Define boundary segments
            line_p1_p2 = LineString([p1, p2]).buffer(tolerance)
            line_p2_p3 = LineString([p2, p3]).buffer(tolerance)

            # Check boundary proximity and containment
            on_boundary = line_p1_p2.intersects(midpoint) or line_p2_p3.intersects(midpoint)
            is_inside = unified_poly.contains(midpoint)

            if not on_boundary and is_inside:
                sharp_corners.append(p2)

    return len(sharp_corners)
