# kojto_factory/utils/compute_task_dxf_drawing.py
import ezdxf
import svgwrite
import base64
import os
import tempfile
from math import radians, cos, sin
from odoo.tools import config
import traceback

def compute_task_dxf_drawing(attachment):
    def create_error_svg(message):
        try:
            dwg = svgwrite.Drawing(size=("800px", "800px"))
            dwg.add(dwg.text(message, insert=(10, 50), font_size="12", fill="red"))
            svg_data = dwg.tostring().encode("utf-8")
            return base64.b64encode(svg_data)
        except Exception:
            minimal_svg = '<svg width="800px" height="800px"><text x="10" y="50" font-size="12" fill="red">Error: SVG generation failed</text></svg>'
            return base64.b64encode(minimal_svg.encode("utf-8"))

    def polar_to_cartesian(center, radius, angle_deg):
        angle_rad = radians(angle_deg)
        x = center[0] + radius * cos(angle_rad)
        y = center[1] + radius * sin(angle_rad)
        return (x, y)

    def get_bounding_box(msp):
        min_x = float('inf')
        max_x = float('-inf')
        min_y = float('inf')
        max_y = float('-inf')

        for entity in msp:
            etype = entity.dxftype()
            try:
                if etype == "LINE":
                    start = entity.dxf.start
                    end = entity.dxf.end
                    min_x = min(min_x, start.x, end.x)
                    max_x = max(max_x, start.x, end.x)
                    min_y = min(min_y, -start.y, -end.y)
                    max_y = max(max_y, -start.y, -end.y)

                elif etype in ("LWPOLYLINE", "POLYLINE"):
                    points = entity.get_points("xy")
                    for x, y in points:
                        min_x = min(min_x, x)
                        max_x = max(max_x, x)
                        min_y = min(min_y, -y)
                        max_y = max(max_y, -y)

                elif etype == "CIRCLE":
                    center = entity.dxf.center
                    radius = entity.dxf.radius
                    min_x = min(min_x, center.x - radius)
                    max_x = max(max_x, center.x + radius)
                    flipped_center_y = -center.y
                    min_y = min(min_y, flipped_center_y - radius)
                    max_y = max(max_y, flipped_center_y + radius)

                elif etype == "ARC":
                    center = entity.dxf.center
                    radius = entity.dxf.radius
                    min_x = min(min_x, center.x - radius)
                    max_x = max(max_x, center.x + radius)
                    flipped_center_y = -center.y
                    min_y = min(min_y, flipped_center_y - radius)
                    max_y = max(max_y, flipped_center_y + radius)

            except Exception:
                continue

        if min_x == float('inf'):
            return -50, -50, 100, 100

        padding_x = (max_x - min_x) * 0.2 if max_x > min_x else 10
        padding_y = (max_y - min_y) * 0.2 if max_y > min_y else 10
        extra_padding = 10
        return (min_x - padding_x - extra_padding, min_y - padding_y - extra_padding,
                max_x - min_x + 2 * (padding_x + extra_padding), max_y - min_y + 2 * (padding_y + extra_padding))

    try:
        if not attachment:
            return create_error_svg("Error: No attachment provided")

        attachment_name = getattr(attachment, "name", "")
        if not attachment_name.lower().endswith(".dxf"):
            return create_error_svg("Error: Not a DXF file")

        # Try accessing attachment content via raw data
        try:
            raw_data = attachment.raw
            if not raw_data:
                raise ValueError("No raw data in attachment")
        except Exception:
            store_fname = getattr(attachment, "store_fname", None)
            if not store_fname:
                return create_error_svg("Error: No filestore data in attachment")

            try:
                filestore_path = config.filestore(attachment._cr.dbname)
            except Exception:
                return create_error_svg("Error: Failed to access filestore")

            file_path = os.path.join(filestore_path, store_fname)
            if not os.path.exists(file_path):
                return create_error_svg("Error: File not found")
            if not os.access(file_path, os.R_OK):
                return create_error_svg("Error: File not readable")
        else:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as temp_file:
                    temp_file.write(raw_data)
                    file_path = temp_file.name
            except Exception:
                return create_error_svg("Error: Failed to create temporary file")

        # Parse DXF using binary reading
        try:
            doc = ezdxf.readfile(file_path)
        except (ezdxf.DXFStructureError, ezdxf.DXFVersionError, Exception):
            return create_error_svg("Error: Invalid DXF format")
        finally:
            if 'temp_file' in locals():
                try:
                    os.unlink(file_path)
                except Exception:
                    pass

        msp = doc.modelspace()

        # Calculate bounding box for viewBox
        try:
            min_x, min_y, width, height = get_bounding_box(msp)
        except Exception:
            return create_error_svg("Error: Failed to calculate bounding box")

        # Create SVG drawing with fixed size
        try:
            dwg = svgwrite.Drawing(size=("800px", "800px"), viewBox=f"{min_x} {min_y} {width} {height}")
        except Exception:
            return create_error_svg("Error: Failed to create SVG")

        for entity in msp:
            etype = entity.dxftype()
            try:
                if etype == "LINE":
                    start = (float(entity.dxf.start.x), -float(entity.dxf.start.y))
                    end = (float(entity.dxf.end.x), -float(entity.dxf.end.y))
                    dwg.add(dwg.line(start=start, end=end, stroke="black"))

                elif etype in ("LWPOLYLINE", "POLYLINE"):
                    points = [(float(p[0]), -float(p[1])) for p in entity.get_points("xy")]
                    is_closed = entity.dxf.flags & 1 if etype == "LWPOLYLINE" else entity.is_closed
                    dwg.add(dwg.polyline(points=points, stroke="black", fill="none"))
                    if is_closed and len(points) > 1:
                        last_point = points[-1]
                        first_point = points[0]
                        dwg.add(dwg.line(start=last_point, end=first_point, stroke="black"))

                elif etype == "CIRCLE":
                    center = (float(entity.dxf.center.x), -float(entity.dxf.center.y))
                    radius = float(entity.dxf.radius)
                    dwg.add(dwg.circle(center=center, r=radius, stroke="black", fill="none"))

                elif etype == "ARC":
                    center = (float(entity.dxf.center.x), -float(entity.dxf.center.y))
                    radius = float(entity.dxf.radius)
                    start_angle = float(entity.dxf.start_angle)
                    end_angle = float(entity.dxf.end_angle)

                    original_center = (center[0], -center[1])
                    start = polar_to_cartesian(original_center, radius, start_angle)
                    end = polar_to_cartesian(original_center, radius, end_angle)
                    start = (start[0], -start[1])
                    end = (end[0], -end[1])
                    large_arc = int(abs(end_angle - start_angle) > 180)
                    sweep = 0
                    path_data = (
                        f"M {start[0]},{start[1]} "
                        f"A {radius},{radius} 0 {large_arc} {sweep} {end[0]},{end[1]}"
                    )
                    dwg.add(dwg.path(d=path_data, stroke="black", fill="none"))

            except Exception:
                continue

        # Encode SVG as base64
        try:
            svg_data = dwg.tostring().encode("utf-8")
            encoded_svg = base64.b64encode(svg_data)
            return encoded_svg
        except Exception:
            return create_error_svg("Error: Failed to encode SVG")

    except Exception:
        return create_error_svg("Error: Unexpected error during DXF processing")
