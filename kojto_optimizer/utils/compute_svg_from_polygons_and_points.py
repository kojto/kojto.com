"""
Compute SVG from Polygons and Points Utility

Purpose:
--------
Generates SVG drawings from polygon data and description points.
"""

import svgwrite
import base64
from shapely.geometry import Polygon
from shapely.ops import unary_union
from .compute_contact_lines_polygons import compute_contact_lines

def draw_axes(drawing, center_x, center_y, axis_length, dashed=False):
    """Draw coordinate axes at the specified center point."""
    axes_points = [
        [(center_x, center_y + axis_length), (center_x, center_y), (center_x, center_y - axis_length)],
        [(center_x - axis_length, center_y), (center_x, center_y), (center_x + axis_length, center_y)]
    ]
    stroke_dasharray = "5,1,1,1" if dashed else None
    additional_group = drawing.g(fill="none", stroke_width=0.5 if dashed else 1.5)
    additional_group.add(drawing.polyline(points=axes_points[0], stroke="red", stroke_dasharray=stroke_dasharray))
    additional_group.add(drawing.polyline(points=axes_points[1], stroke="blue", stroke_dasharray=stroke_dasharray))
    drawing.add(additional_group)

    # Add axis labels
    if dashed:
        drawing.add(drawing.text("+x", insert=(center_x + axis_length + 3, center_y + 2), fill="blue", font_size="10px", font_family="Arial"))
        drawing.add(drawing.text("+y", insert=(center_x - 2, center_y - axis_length - 4), fill="red", font_size="10px", font_family="Arial"))
    else:
        drawing.add(drawing.text("x", insert=(center_x + axis_length + 3, center_y + 2), fill="blue", font_size="10px", font_family="Arial"))
        drawing.add(drawing.text("y", insert=(center_x - 2, center_y - axis_length - 4), fill="red", font_size="10px", font_family="Arial"))

def create_default_svg():
    """Create a default SVG with coordinate axes."""
    drawing = svgwrite.Drawing(size=('100%', '100%'))
    drawing.viewbox(minx=-100, miny=-100, width=200, height=200)
    drawing.add(drawing.rect(insert=(-100, -100), size=(200, 200), fill='white'))

    # Draw axes at origin
    draw_axes(drawing, 0, 0, 50)
    drawing.add(drawing.circle(center=(0, 0), r=3, fill="blue"))
    drawing['viewBox'] = "-100 -100 200 200"
    return base64.b64encode(drawing.tostring().encode("utf-8")).decode("utf-8")

def draw_shape(drawing, center_x, center_y, size, shape_type, point_color, point_opacity):
    if shape_type == 'square':
        half_size = size / 2
        # Points in clockwise order starting from top-left
        points = [
            (center_x - half_size, center_y - half_size),  # top-left
            (center_x + half_size, center_y - half_size),  # top-right
            (center_x + half_size, center_y + half_size),  # bottom-right
            (center_x - half_size, center_y + half_size),  # bottom-left
            (center_x - half_size, center_y - half_size),  # back to top-left to close the shape
        ]
        shape_group = drawing.g(fill=point_color, fill_opacity=point_opacity, stroke='black', stroke_width=0.5)
        shape_group.add(drawing.polyline(points=points))
        drawing.add(shape_group)
    elif shape_type == 'triangle':
        # Equilateral triangle
        # For equilateral triangle, height = side * sqrt(3)/2
        height = size * 0.866  # sqrt(3)/2 ≈ 0.866
        # Points in clockwise order starting from top
        points = [
            (center_x, center_y - height/2),  # top
            (center_x + size/2, center_y + height/2),  # bottom-right
            (center_x - size/2, center_y + height/2),  # bottom-left
            (center_x, center_y - height/2),  # back to top to close the shape
        ]
        shape_group = drawing.g(fill=point_color, fill_opacity=point_opacity, stroke='black', stroke_width=0.5)
        shape_group.add(drawing.polyline(points=points))
        drawing.add(shape_group)

def compute_svg_from_polygons_and_points(polygons_data, description_points_data=None, show_origin_points=False):
    canvas_width = 800
    canvas_height = 800
    drawing = svgwrite.Drawing(size=(f"{canvas_width}px", f"{canvas_height}px"))

    def default_svg():
        axis_length = 50
        cm_x, cm_y = 0, 0
        axes_points = [
            [(cm_x, cm_y + axis_length / 5), (cm_x, cm_y), (cm_x, cm_y - axis_length)],
            [(cm_x - axis_length / 5, cm_y), (cm_x, cm_y), (cm_x + axis_length, cm_y)]
        ]
        additional_group = drawing.g(fill="none", stroke_width=1.5)
        additional_group.add(drawing.polyline(points=axes_points[0], stroke="red"))
        additional_group.add(drawing.polyline(points=axes_points[1], stroke="blue"))
        drawing.add(additional_group)
        drawing.add(drawing.text("x", insert=(cm_x + axis_length + 3, cm_y + 2), fill="blue", font_size="10px", font_family="Arial"))
        drawing.add(drawing.text("y", insert=(cm_x - 2, cm_y - axis_length - 4), fill="red", font_size="10px", font_family="Arial"))
        drawing.add(drawing.circle(center=(cm_x, cm_y), r=3, fill="blue"))
        drawing['viewBox'] = "-100 -100 200 200"
        return base64.b64encode(drawing.tostring().encode("utf-8")).decode("utf-8")

    try:
        if not polygons_data and not description_points_data:
            return default_svg()

        svg_points = []
        valid_polygons = []

        # Process polygons_data
        for item in polygons_data:
            if isinstance(item, dict):
                points = item.get('points', [])
                is_subtract = item.get('is_subtract', False)
                id_different_color = item.get('id_different_color', False)
            else:
                points = item
                is_subtract = False
                id_different_color = False

            if len(points) >= 3 and all(len(pt) == 2 for pt in points):
                # Remove duplicate points
                unique_points = []
                seen = set()
                for pt in points:
                    pt_tuple = (pt[0], pt[1])
                    if pt_tuple not in seen:
                        unique_points.append(pt)
                        seen.add(pt_tuple)

                if len(unique_points) >= 3:
                    # Render immediately
                    flipped_points = [(x, -y) for x, y in unique_points]
                    svg_points.extend(flipped_points)
                    fill = "#FFFFFF" if is_subtract else ("#ADD8E6" if id_different_color else "#90EE90")
                    stroke = "blue" if is_subtract else "black"
                    fill_opacity = 1.0 if is_subtract else 0.5
                    drawing.add(drawing.polygon(points=flipped_points, fill=fill, fill_opacity=fill_opacity, stroke=stroke, stroke_width=1))
                    if show_origin_points:
                        drawing.add(drawing.circle(center=flipped_points[0], r=1.6, fill="red"))

                    # Add to centroid calculation
                    try:
                        poly = Polygon(unique_points)
                        if not poly.is_valid:
                            poly = poly.buffer(0)
                        if poly.is_valid and not poly.is_empty:
                            valid_polygons.append((poly, is_subtract))
                    except Exception:
                        continue

        # Process description_points_data if provided
        if description_points_data:
            for item in description_points_data:
                if isinstance(item, dict):
                    points = item.get('points', [])
                    if points:
                        try:
                            for point_data in points:
                                if isinstance(point_data, dict):
                                    x = float(point_data.get('x', 0.0))
                                    y = float(point_data.get('y', 0.0))
                                    point_color = point_data.get('color', '#000000')
                                    shape_type = point_data.get('shape_type', 'circle')  # Get shape type from point data
                                    shape_size = float(point_data.get('shape_size', 1.5))  # Get shape size from point data
                                    point_opacity = 0.7  # Default opacity

                                    # Flip the y coordinate for the point
                                    flipped_point = (x, -y)

                                    # Add point to svg_points for viewBox calculation
                                    svg_points.append(flipped_point)

                                    # Add point with its radius to ensure the circle is fully visible
                                    svg_points.append((flipped_point[0] + shape_size, flipped_point[1] + shape_size))
                                    svg_points.append((flipped_point[0] - shape_size, flipped_point[1] - shape_size))

                                    # Draw shape if specified for this point
                                    if shape_type in ['square', 'triangle']:
                                        draw_shape(drawing, x, -y, shape_size, shape_type, point_color, point_opacity)
                                    else:
                                        # Draw the point as a circle if no shape specified or if shape_type is 'circle'
                                        drawing.add(drawing.circle(
                                            center=flipped_point,
                                            r=shape_size,
                                            fill=point_color,
                                            fill_opacity=point_opacity,
                                            stroke='black',
                                            stroke_width=0.5
                                        ))

                                    # Add text label with offset
                                    initial_offset = shape_size + 2
                                    offset_x = point_data.get('description_offset_x', 0)
                                    offset_y = point_data.get('description_offset_y', 0)

                                    # Calculate text position with offset in original coordinates
                                    text_x_original = x + initial_offset + offset_x
                                    text_y_original = y + offset_y

                                    # Now flip the y coordinate for the text
                                    text_x = text_x_original
                                    text_y = -text_y_original

                                    text = point_data.get('description', '')
                                    description_size = point_data.get('description_size', 5)
                                    if text:
                                        # Add text position to svg_points for viewBox calculation
                                        svg_points.append((text_x, text_y))
                                        # Add points to account for text width and height using description_size
                                        svg_points.append((text_x + len(text) * description_size, text_y))
                                        svg_points.append((text_x, text_y - description_size))

                                        drawing.add(drawing.text(
                                            text,
                                            insert=(text_x, text_y),
                                            fill=point_color,
                                            font_size=f'{description_size}px',
                                            font_family='Arial'
                                        ))
                        except Exception as e:
                            continue

        # Compute contact lines
        try:
            points_list = [item['points'] if isinstance(item, dict) else item for item in polygons_data]
            contact_lines_result, _, _ = compute_contact_lines(points_list)
            for (start_x, start_y), (end_x, end_y) in contact_lines_result:
                start_flipped = (start_x, -start_y)
                end_flipped = (end_x, -end_y)
                drawing.add(drawing.line(start=start_flipped, end=end_flipped, stroke="magenta", stroke_opacity=0.3, stroke_width=3))
        except Exception:
            pass

        # Compute centroid
        if not valid_polygons:
            cm_x, cm_y = 0, 0
        else:
            add_polygons = [poly for poly, is_subtract in valid_polygons if not is_subtract]
            subtract_polygons = [poly for poly, is_subtract in valid_polygons if is_subtract]

            if not add_polygons:
                cm_x, cm_y = 0, 0
            else:
                union_poly = unary_union(add_polygons)
                for subtract_poly in subtract_polygons:
                    union_poly = union_poly.difference(subtract_poly)

                if union_poly.is_empty:
                    cm_x, cm_y = 0, 0
                else:
                    centroid = union_poly.centroid
                    cm_x, cm_y = centroid.x, -centroid.y

        # Add axes and centroid
        axis_length = 25
        axes_points = [
            [(cm_x, cm_y + axis_length), (cm_x, cm_y), (cm_x, cm_y - axis_length)],
            [(cm_x - axis_length, cm_y), (cm_x, cm_y), (cm_x + axis_length, cm_y)]
        ]
        additional_group = drawing.g(fill="none", stroke_width=0.5)
        additional_group.add(drawing.polyline(points=axes_points[0], stroke="red", stroke_dasharray="5,1,1,1"))
        additional_group.add(drawing.polyline(points=axes_points[1], stroke="blue", stroke_dasharray="5,1,1,1"))
        drawing.add(additional_group)
        drawing.add(drawing.text("+x", insert=(cm_x + axis_length + 3, cm_y + 2), fill="blue", font_size="10px", font_family="Arial"))
        drawing.add(drawing.text("+y", insert=(cm_x - 2, cm_y - axis_length - 4), fill="red", font_size="10px", font_family="Arial"))

        # Compute viewBox, including axes and labels
        if not svg_points:
            return default_svg()

        # Include polygon points
        min_x = min(p[0] for p in svg_points)
        max_x = max(p[0] for p in svg_points)
        min_y = min(p[1] for p in svg_points)
        max_y = max(p[1] for p in svg_points)

        # Include axes points
        axes_x_points = [cm_x - axis_length, cm_x, cm_x + axis_length, cm_x + axis_length + 3]  # Include "+x" label
        axes_y_points = [cm_y - axis_length, cm_y, cm_y + axis_length, cm_y - axis_length - 4]  # Include "+y" label
        axes_min_x = min(axes_x_points)
        axes_max_x = max(axes_x_points)
        axes_min_y = min(axes_y_points)
        axes_max_y = max(axes_y_points)

        # Combine extents
        min_x = min(min_x, axes_min_x)
        max_x = max(max_x, axes_max_x)
        min_y = min(min_y, axes_min_y)
        max_y = max(max_y, axes_max_y)

        # Calculate base width and height
        width = max_x - min_x if max_x > min_x else 1e-10
        height = max_y - min_y if max_y > min_y else 1e-10
        padding_x = width * 0.05
        padding_y = height * 0.05

        # Initialize viewBox boundaries with 5% padding
        viewbox_min_x = min_x - padding_x
        viewbox_max_x = max_x + padding_x
        viewbox_min_y = min_y - padding_y
        viewbox_max_y = max_y + padding_y

        # Add 5-unit padding only if axes define the boundary
        extra_padding = 10  # Additional 5 units for axes and labels
        if axes_min_x <= min_x:
            viewbox_min_x -= extra_padding  # Left side
        if axes_max_x >= max_x:
            viewbox_max_x += extra_padding  # Right side
        if axes_min_y <= min_y:
            viewbox_min_y -= extra_padding  # Bottom side
        if axes_max_y >= max_y:
            viewbox_max_y += extra_padding  # Top side

        # Calculate final viewBox dimensions
        viewbox_width = viewbox_max_x - viewbox_min_x
        viewbox_height = viewbox_max_y - viewbox_min_y

        drawing['viewBox'] = f"{viewbox_min_x} {viewbox_min_y} {viewbox_width} {viewbox_height}"
        return base64.b64encode(drawing.tostring().encode("utf-8")).decode("utf-8")
    except Exception:
        return default_svg()

