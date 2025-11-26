#$ kojto_profiles/utils/compute_coating_perimeter_polygons.py

from shapely.geometry import Polygon
from shapely.ops import unary_union

def compute_coating_perimeter(polygons):
    try:
        if not polygons:
            return 0.0  # No polygons, no perimeter

        # Convert input coordinates to Shapely Polygons and validate
        strip_polygons = []
        for poly in polygons:
            # Assuming poly is a list/tuple of 4 (x,y) coordinate pairs
            if len(poly) == 4 and all(len(pt) == 2 for pt in poly):
                # Only append valid polygons (at least 3 unique points)
                if len(set(tuple(pt) for pt in poly)) >= 3:
                    strip_polygons.append(Polygon(poly))

        if not strip_polygons:
            return 0.0  # No valid polygons

        union_poly = unary_union(strip_polygons)

        # Handle both Polygon and MultiPolygon cases
        if union_poly.geom_type == 'Polygon':
            return union_poly.exterior.length  # Only the outer perimeter
        elif union_poly.geom_type == 'MultiPolygon':
            # Sum the exterior perimeters of all disjoint polygons
            return sum(poly.exterior.length for poly in union_poly.geoms)
        else:
            return 0.0  # Unexpected geometry type (e.g., LineString, Point)

    except Exception as e:
        return 0.0  # Return 0.0 on error instead of None for consistency
