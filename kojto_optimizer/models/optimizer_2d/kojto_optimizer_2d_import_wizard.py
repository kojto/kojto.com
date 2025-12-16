"""
Kojto Optimizer 2D Import Wizard Model

Purpose:
--------
Provides a wizard interface for importing DXF files and creating cut shapes
for 2D optimization packages. Reads DXF files, extracts polygons, normalizes them,
and creates cut shape records.
"""

import base64
import json
import tempfile
import os
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class KojtoOptimizer2dImportWizard(models.TransientModel):
    _name = "kojto.optimizer.2d.import.wizard"
    _description = "Kojto Profile Optimizer 2D Import Wizard"

    package_id = fields.Many2one(
        "kojto.optimizer.2d.packages",
        string="Package",
        required=True
    )
    dxf_files = fields.Binary(
        string="DXF Files",
        help="Upload one or more DXF files. Each file will create one cut shape.",
        required=True
    )
    dxf_filenames = fields.Char(
        string="DXF Filenames",
        help="Comma-separated list of uploaded DXF filenames"
    )

    def action_import(self):
        """Import DXF files and create cut shapes."""
        self.ensure_one()

        if not self.dxf_files:
            raise ValidationError("Please upload at least one DXF file.")

        # Decode the uploaded file(s)
        file_data = base64.b64decode(self.dxf_files)
        filenames = self.dxf_filenames.split(',') if self.dxf_filenames else ['shape.dxf']

        # For now, handle single file. Multiple files would need zip extraction
        if len(filenames) == 1:
            # Single DXF file
            filename = filenames[0].strip()
            if not filename.lower().endswith('.dxf'):
                filename += '.dxf'

            # Save to temporary file
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.dxf', delete=False) as tmp_file:
                tmp_file.write(file_data)
                tmp_path = tmp_file.name

            try:
                # Read and process DXF
                shape_data = self._read_dxf_file(tmp_path, filename)

                if shape_data:
                    # Create cut shape record
                    self._create_cut_shape(shape_data, filename)
                else:
                    raise ValidationError(f"Could not extract valid shape from {filename}. Please ensure the DXF contains closed polygons.")
            finally:
                # Clean up temp file
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        else:
            raise ValidationError("Multiple file upload not yet supported. Please upload one DXF file at a time.")

        return {'type': 'ir.actions.act_window_close'}

    def _read_dxf_file(self, file_path, filename):
        """Read DXF file and extract polygon data using scan_2_serration approach.

        Args:
            file_path: Path to DXF file
            filename: Original filename

        Returns:
            Dict with outer_polygon, inner_polygons, bounding_box, or None if failed
        """
        try:
            import ezdxf
            import numpy as np
            from shapely.geometry import Polygon, Point
            from shapely.affinity import translate as shapely_translate

            doc = ezdxf.readfile(file_path)
            msp = doc.modelspace()

            # Extract entities
            entities = []
            for entity in msp:
                if entity.dxftype() in ['LINE', 'ARC', 'CIRCLE', 'LWPOLYLINE', 'POLYLINE']:
                    entities.append(entity)

            if not entities:
                return None

            # Use the same processing approach as shapes_to_cut model
            outer_points, inner_polygons_list, bbox_data, normalized_entities, transformation_matrix = self._process_dxf_entities(entities)

            if not outer_points:
                return None

            # Remove closing point from outer polygon if present
            if len(outer_points) > 1 and self._points_close(outer_points[0], outer_points[-1], tolerance=0.1):
                outer_points = outer_points[:-1]

            # Remove closing points from inner polygons if present
            normalized_inner = []
            for inner_poly in inner_polygons_list:
                if len(inner_poly) > 1 and self._points_close(inner_poly[0], inner_poly[-1], tolerance=0.1):
                    normalized_inner.append(inner_poly[:-1])
                else:
                    normalized_inner.append(inner_poly)

            return {
                'outer_polygon': outer_points,
                'inner_polygons': normalized_inner if normalized_inner else None,
                'bounding_box': bbox_data,
                'normalized_entities': normalized_entities,
                'transformation_matrix': transformation_matrix,
                'filename': filename
            }

        except Exception as e:
            raise ValidationError(f"Error reading DXF file {filename}: {str(e)}")

    def _points_close(self, p1, p2, tolerance=0.01):
        """Check if two points are close within tolerance."""
        import numpy as np
        return np.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2) < tolerance

    def _remove_duplicate_points(self, points, tolerance=0.01):
        """Remove duplicate points from a list, keeping only unique points within tolerance."""
        if not points or len(points) < 2:
            return points
        filtered = [points[0]]
        for pt in points[1:]:
            if not self._points_close(pt, filtered[-1], tolerance):
                filtered.append(pt)
        if len(filtered) > 2 and self._points_close(filtered[0], filtered[-1], tolerance):
            filtered = filtered[:-1]
        return filtered

    def _group_connected_entities(self, entity_segments, use_vertices_only=False):
        """Group connected entities (lines, arcs, polylines) into closed shapes."""
        import numpy as np
        if not entity_segments:
            return []
        tolerance = 0.01
        used = [False] * len(entity_segments)
        closed_shapes = []

        for i, seg in enumerate(entity_segments):
            if len(seg) == 5:
                start1, end1, points1, type1, vertex_points1 = seg
                if use_vertices_only:
                    points1 = vertex_points1
            else:
                start1, end1, points1, type1 = seg

            if used[i]:
                continue

            if self._points_close(start1, end1, tolerance):
                closed_shapes.append(points1)
                used[i] = True
                continue

            shape_points = list(points1)
            used[i] = True
            current_end = end1
            found_connection = True
            max_iterations = len(entity_segments) * 2
            iterations = 0

            while found_connection and iterations < max_iterations:
                iterations += 1
                found_connection = False

                for j, seg2 in enumerate(entity_segments):
                    if used[j]:
                        continue

                    if len(seg2) == 5:
                        start2, end2, points2, type2, vertex_points2 = seg2
                        if use_vertices_only:
                            points2 = vertex_points2
                    else:
                        start2, end2, points2, type2 = seg2

                    if self._points_close(current_end, start2, tolerance):
                        shape_points.extend(points2[1:])
                        current_end = end2
                        used[j] = True
                        found_connection = True
                        break
                    elif self._points_close(current_end, end2, tolerance):
                        shape_points.extend(reversed(points2[:-1]))
                        current_end = start2
                        used[j] = True
                        found_connection = True
                        break

            if len(shape_points) >= 3:
                first_pt = shape_points[0]
                last_pt = shape_points[-1]
                if self._points_close(first_pt, last_pt, tolerance):
                    closed_shapes.append(shape_points)
                else:
                    dist_to_close = np.sqrt((first_pt[0] - last_pt[0])**2 + (first_pt[1] - last_pt[1])**2)
                    if dist_to_close < tolerance * 10:
                        shape_points.append(first_pt)
                        closed_shapes.append(shape_points)

        return closed_shapes

    def _process_dxf_entities(self, entities):
        """Process DXF entities and extract polygons using scan_2_serration approach."""
        import numpy as np
        from shapely.geometry import Polygon, Point
        from shapely.affinity import translate as shapely_translate

        # Step 1: Extract entity segments (start_pt, end_pt, all_points, entity_type, vertex_points)
        entity_segments = []
        for entity in entities:
            start_pt = None
            end_pt = None
            all_points = []
            vertex_points = []

            if entity.dxftype() == 'LINE':
                start_pt = (entity.dxf.start.x, entity.dxf.start.y)
                end_pt = (entity.dxf.end.x, entity.dxf.end.y)
                all_points = [start_pt, end_pt]
                vertex_points = [start_pt, end_pt]

            elif entity.dxftype() == 'ARC':
                center = (entity.dxf.center.x, entity.dxf.center.y)
                radius = entity.dxf.radius
                start_angle = np.radians(entity.dxf.start_angle)
                end_angle = np.radians(entity.dxf.end_angle)
                start_pt = (
                    center[0] + radius * np.cos(start_angle),
                    center[1] + radius * np.sin(start_angle)
                )
                end_pt = (
                    center[0] + radius * np.cos(end_angle),
                    center[1] + radius * np.sin(end_angle)
                )
                vertex_points = [start_pt, end_pt]
                num_points = max(8, int(abs(end_angle - start_angle) * radius / 2))
                if end_angle < start_angle:
                    end_angle += 2 * np.pi
                angles = np.linspace(start_angle, end_angle, num_points)
                for angle in angles:
                    x = center[0] + radius * np.cos(angle)
                    y = center[1] + radius * np.sin(angle)
                    all_points.append((x, y))
                end_pt = (
                    center[0] + radius * np.cos(end_angle),
                    center[1] + radius * np.sin(end_angle)
                )

            elif entity.dxftype() == 'CIRCLE':
                center = (entity.dxf.center.x, entity.dxf.center.y)
                radius = entity.dxf.radius
                num_points = max(64, int(radius * 4))
                angles = np.linspace(0, 2 * np.pi, num_points)
                for angle in angles:
                    x = center[0] + radius * np.cos(angle)
                    y = center[1] + radius * np.sin(angle)
                    all_points.append((x, y))
                start_pt = all_points[0]
                end_pt = all_points[-1]
                vertex_points = all_points

            elif entity.dxftype() == 'LWPOLYLINE':
                polyline_points = []
                is_closed_poly = False
                try:
                    points_with_bulge = list(entity.get_points('xyb'))
                    if not points_with_bulge:
                        vertices = list(entity.vertices())
                        points_with_bulge = []
                        for vertex in vertices:
                            x, y = vertex[0], vertex[1]
                            bulge = 0
                            if len(vertex) >= 3:
                                if isinstance(vertex[2], (int, float)):
                                    bulge = vertex[2]
                                elif len(vertex) >= 4 and isinstance(vertex[3], (int, float)):
                                    bulge = vertex[3]
                                elif len(vertex) >= 5 and isinstance(vertex[4], (int, float)):
                                    bulge = vertex[4]
                            points_with_bulge.append((x, y, bulge))

                    for i, point_data in enumerate(points_with_bulge):
                        if len(point_data) >= 2:
                            x, y = point_data[0], point_data[1]
                            bulge = point_data[2] if len(point_data) >= 3 else 0
                            vertex_pt = (x, y)
                            all_points.append(vertex_pt)
                            polyline_points.append(vertex_pt)
                            vertex_points.append(vertex_pt)
                            if bulge != 0:
                                next_idx = (i + 1) % len(points_with_bulge)
                                next_point = points_with_bulge[next_idx]
                                next_x, next_y = next_point[0], next_point[1]
                                arc_points = self._bulge_to_arc_points(x, y, next_x, next_y, bulge)
                                if len(arc_points) > 1:
                                    all_points.extend(arc_points[1:])

                    try:
                        is_closed_poly = entity.closed if hasattr(entity, 'closed') else False
                    except:
                        is_closed_poly = False

                    if len(polyline_points) >= 2:
                        if is_closed_poly or self._points_close(polyline_points[0], polyline_points[-1], tolerance=0.1):
                            is_closed_poly = True
                except Exception:
                    try:
                        vertices = list(entity.vertices())
                        for vertex in vertices:
                            pt = (vertex[0], vertex[1])
                            all_points.append(pt)
                            polyline_points.append(pt)
                            vertex_points.append(pt)
                    except:
                        pass

                if len(all_points) > 0:
                    start_pt = all_points[0]
                    end_pt = all_points[-1]
                    if is_closed_poly or self._points_close(start_pt, end_pt, tolerance=0.1):
                        end_pt = start_pt

            elif entity.dxftype() == 'POLYLINE':
                polyline_points = []
                is_closed_poly = False
                try:
                    vertices = list(entity.vertices)
                    for i, vertex in enumerate(vertices):
                        x = vertex.dxf.location.x
                        y = vertex.dxf.location.y
                        vertex_pt = (x, y)
                        all_points.append(vertex_pt)
                        polyline_points.append(vertex_pt)
                        vertex_points.append(vertex_pt)
                        if hasattr(vertex.dxf, 'bulge') and vertex.dxf.bulge != 0:
                            bulge = vertex.dxf.bulge
                            next_idx = (i + 1) % len(vertices)
                            next_vertex = vertices[next_idx]
                            next_x = next_vertex.dxf.location.x
                            next_y = next_vertex.dxf.location.y
                            arc_points = self._bulge_to_arc_points(x, y, next_x, next_y, bulge)
                            all_points.extend(arc_points[1:])
                    is_closed_poly = entity.is_closed if hasattr(entity, 'is_closed') else False
                except Exception:
                    pass

                if len(all_points) > 0:
                    start_pt = all_points[0]
                    end_pt = all_points[-1]
                    if is_closed_poly or (start_pt == end_pt):
                        end_pt = start_pt

            if start_pt is not None and end_pt is not None and len(all_points) > 0:
                if entity.dxftype() in ['LINE', 'ARC']:
                    vertex_points = [start_pt, end_pt]
                elif entity.dxftype() == 'CIRCLE':
                    vertex_points = all_points
                elif entity.dxftype() in ['LWPOLYLINE', 'POLYLINE']:
                    if len(vertex_points) == 0:
                        if 'polyline_points' in locals() and len(polyline_points) > 0:
                            vertex_points = polyline_points
                        else:
                            vertex_points = all_points
                entity_segments.append((start_pt, end_pt, all_points, entity.dxftype(), vertex_points))

        if not entity_segments:
            return [], [], {}

        # Step 2: Group connected entities into closed shapes
        point_sequences = self._group_connected_entities(entity_segments, use_vertices_only=False)
        if not point_sequences:
            return [], [], {}

        # Step 3: Create polygons from grouped sequences
        polygons = []
        original_sequences = []
        for seq in point_sequences:
            if len(seq) >= 3:
                seq_cleaned = self._remove_duplicate_points(seq)
                if len(seq_cleaned) < 3:
                    continue
                seq_closed = seq_cleaned if seq_cleaned[0] == seq_cleaned[-1] else seq_cleaned + [seq_cleaned[0]]
                try:
                    poly = Polygon(seq_closed)
                    if poly.is_valid and poly.area > 0:
                        polygons.append(poly)
                        original_sequences.append(seq_cleaned if seq_cleaned[0] != seq_cleaned[-1] else seq_cleaned[:-1])
                except:
                    pass

        if not polygons:
            return [], [], {}

        # Step 4: Identify outer polygon and inner polygons (holes)
        outer_poly_idx = max(range(len(polygons)), key=lambda i: polygons[i].area)
        outer_poly = polygons[outer_poly_idx]
        outer_points = original_sequences[outer_poly_idx]
        outer_points = self._remove_duplicate_points(outer_points)
        if len(outer_points) > 1 and self._points_close(outer_points[0], outer_points[-1], tolerance=0.1):
            outer_points = outer_points[:-1]

        inner_polys = []
        for i, poly in enumerate(polygons):
            if i == outer_poly_idx:
                continue
            if outer_poly.contains(poly) or outer_poly.covers(poly):
                is_nested = False
                for j, other_poly in enumerate(polygons):
                    if j != i and j != outer_poly_idx:
                        if poly.contains(other_poly) or poly.covers(other_poly):
                            is_nested = True
                            break
                if not is_nested:
                    inner_points = original_sequences[i]
                    inner_polys.append(inner_points)

        # Step 3: Verify polygons
        if not outer_poly.is_valid:
            # Try to fix invalid polygon
            outer_poly = outer_poly.buffer(0)
            if hasattr(outer_poly, 'geoms'):
                # If buffer returns MultiPolygon, take the largest
                outer_poly = max(outer_poly.geoms, key=lambda p: p.area)

        # Step 4: Compute minimum bounding box (before normalization) to get rotation angle
        bbox_data_before_normalization = self._compute_bounding_box_from_shapely(outer_poly)
        if not bbox_data_before_normalization:
            return [], [], {}

        rotation_angle = bbox_data_before_normalization.get('angle', 0.0)
        bbox_center = bbox_data_before_normalization.get('center', (0.0, 0.0))
        bbox_center_x, bbox_center_y = bbox_center[0], bbox_center[1]

        # Step 5: Normalize - rotate to horizontal, then translate to origin
        from shapely.affinity import rotate as shapely_rotate
        from shapely.geometry import Point as ShapelyPoint

        # Step 5a: Rotate to horizontal (if needed)
        if abs(rotation_angle) > 0.01:
            # Rotate around bbox center by -angle to make horizontal
            rotation_center = ShapelyPoint(bbox_center_x, bbox_center_y)
            outer_poly = shapely_rotate(outer_poly, -rotation_angle, origin=rotation_center, use_radians=False)

            # Fix polygon after rotation
            if not outer_poly.is_valid:
                outer_poly = outer_poly.buffer(0)
                if hasattr(outer_poly, 'geoms'):
                    outer_poly = max(outer_poly.geoms, key=lambda p: p.area)

            # Rotate outer points
            if outer_points:
                rotated_outer = []
                for pt in outer_points:
                    # Translate to origin, rotate, translate back
                    dx = pt[0] - bbox_center_x
                    dy = pt[1] - bbox_center_y
                    angle_rad = np.radians(-rotation_angle)
                    cos_a = np.cos(angle_rad)
                    sin_a = np.sin(angle_rad)
                    rotated_x = dx * cos_a - dy * sin_a + bbox_center_x
                    rotated_y = dx * sin_a + dy * cos_a + bbox_center_y
                    rotated_outer.append((rotated_x, rotated_y))
                outer_points = rotated_outer

            # Rotate inner polygons
            if inner_polys:
                rotated_inner = []
                for inner_points in inner_polys:
                    rotated_hole = []
                    for pt in inner_points:
                        dx = pt[0] - bbox_center_x
                        dy = pt[1] - bbox_center_y
                        angle_rad = np.radians(-rotation_angle)
                        cos_a = np.cos(angle_rad)
                        sin_a = np.sin(angle_rad)
                        rotated_x = dx * cos_a - dy * sin_a + bbox_center_x
                        rotated_y = dx * sin_a + dy * cos_a + bbox_center_y
                        rotated_hole.append((rotated_x, rotated_y))
                    rotated_inner.append(rotated_hole)
                inner_polys = rotated_inner

        # Step 5b: Translate to origin (bottom-left corner at 0, 0)
        bounds = outer_poly.exterior.bounds
        min_x, min_y = bounds[0], bounds[1]
        translate_x = -min_x
        translate_y = -min_y

        if abs(translate_x) > 0.001 or abs(translate_y) > 0.001:
            # Translate outer polygon
            outer_poly = shapely_translate(outer_poly, xoff=translate_x, yoff=translate_y)

            # Fix polygon after translation
            if not outer_poly.is_valid:
                outer_poly = outer_poly.buffer(0)
                if hasattr(outer_poly, 'geoms'):
                    outer_poly = max(outer_poly.geoms, key=lambda p: p.area)

            # Translate outer points
            if outer_points:
                translated_outer = []
                for pt in outer_points:
                    translated_outer.append((pt[0] + translate_x, pt[1] + translate_y))
                outer_points = translated_outer

            # Translate inner polygons
            if inner_polys:
                translated_inner = []
                for inner_points in inner_polys:
                    translated_hole = []
                    for pt in inner_points:
                        translated_hole.append((pt[0] + translate_x, pt[1] + translate_y))
                    translated_inner.append(translated_hole)
                inner_polys = translated_inner

        normalized_inner_points_list = []
        for inner_points in inner_polys:
            if len(inner_points) > 1 and self._points_close(inner_points[0], inner_points[-1], tolerance=0.1):
                normalized_inner_points_list.append(inner_points[:-1])
            else:
                normalized_inner_points_list.append(inner_points)

        # Compute final normalized bounding box
        bbox_data = self._compute_bounding_box_from_shapely(outer_poly)

        return outer_points, normalized_inner_points_list, bbox_data

    def _compute_bounding_box_from_shapely(self, shapely_geom):
        """Compute bounding box from Shapely geometry."""
        from shapely.geometry import MultiPoint, Polygon
        import numpy as np

        if shapely_geom is None:
            return {}

        all_points = []
        if isinstance(shapely_geom, Polygon):
            all_points.extend(list(shapely_geom.exterior.coords))
            for interior in shapely_geom.interiors:
                all_points.extend(list(interior.coords))
        elif hasattr(shapely_geom, 'coords'):
            all_points.extend(list(shapely_geom.coords))
        elif hasattr(shapely_geom, 'geoms'):
            for geom in shapely_geom.geoms:
                all_points.extend(list(geom.exterior.coords) if isinstance(geom, Polygon) else list(geom.coords))

        if not all_points:
            return {}

        unique_points = []
        seen = set()
        for pt in all_points:
            pt_tuple = (round(pt[0], 6), round(pt[1], 6))
            if pt_tuple not in seen:
                seen.add(pt_tuple)
                unique_points.append(pt)

        if len(unique_points) < 2:
            return {}

        multipoint = MultiPoint(unique_points)
        min_rect = multipoint.minimum_rotated_rectangle

        minx, miny, maxx, maxy = min_rect.bounds
        rect_coords = list(min_rect.exterior.coords[:-1])

        width, height, angle_deg, center = 0.0, 0.0, 0.0, (0.0, 0.0)

        if len(rect_coords) >= 4:
            p1, p2, p3 = np.array(rect_coords[0]), np.array(rect_coords[1]), np.array(rect_coords[2])
            side1_length = np.linalg.norm(p2 - p1)
            side2_length = np.linalg.norm(p3 - p2)

            width = max(side1_length, side2_length)
            height = min(side1_length, side2_length)

            if side1_length >= side2_length:
                edge_vec = p2 - p1
            else:
                edge_vec = p3 - p2

            angle_rad = np.arctan2(edge_vec[1], edge_vec[0])
            angle_deg = np.degrees(angle_rad)
            angle_deg = angle_deg % 180
            if angle_deg < 0:
                angle_deg += 180

            center = min_rect.centroid.coords[0]
        else:
            width = maxx - minx
            height = maxy - miny
            center = ((minx + maxx) / 2, (miny + maxy) / 2)

        area = shapely_geom.area if hasattr(shapely_geom, 'area') else min_rect.area

        return {
            'min_x': minx, 'max_x': maxx,
            'min_y': miny, 'max_y': maxy,
            'width': width, 'height': height,
            'area': area,
            'angle': angle_deg,
            'center': center,
            'rect_coords': rect_coords
        }

    def _extract_points_from_entity(self, entity):
        """Extract points from a DXF entity.

        Args:
            entity: ezdxf entity

        Returns:
            List of (x, y) tuples
        """
        import numpy as np
        points = []

        try:
            if entity.dxftype() == 'LINE':
                start = entity.dxf.start
                end = entity.dxf.end
                points = [(start.x, start.y), (end.x, end.y)]

            elif entity.dxftype() == 'ARC':
                center = entity.dxf.center
                radius = entity.dxf.radius
                start_angle = np.radians(entity.dxf.start_angle)
                end_angle = np.radians(entity.dxf.end_angle)

                if end_angle < start_angle:
                    end_angle += 2 * np.pi

                num_points = max(16, int(abs(end_angle - start_angle) * radius / 1.0))
                angles = np.linspace(start_angle, end_angle, num_points)

                for angle in angles:
                    x = center.x + radius * np.cos(angle)
                    y = center.y + radius * np.sin(angle)
                    points.append((x, y))

            elif entity.dxftype() == 'CIRCLE':
                center = entity.dxf.center
                radius = entity.dxf.radius
                num_points = 64
                angles = np.linspace(0, 2 * np.pi, num_points)

                for angle in angles:
                    x = center.x + radius * np.cos(angle)
                    y = center.y + radius * np.sin(angle)
                    points.append((x, y))

            elif entity.dxftype() == 'LWPOLYLINE':
                try:
                    points_with_bulge = list(entity.get_points('xyb'))
                    if points_with_bulge:
                        for i, (x, y, bulge) in enumerate(points_with_bulge):
                            points.append((x, y))
                            if bulge != 0 and i < len(points_with_bulge) - 1:
                                next_x, next_y, _ = points_with_bulge[i + 1]
                                arc_points = self._bulge_to_arc_points(x, y, next_x, next_y, bulge)
                                if len(arc_points) > 1:
                                    points.extend(arc_points[1:])
                    else:
                        vertices = list(entity.vertices())
                        for vertex in vertices:
                            points.append((vertex[0], vertex[1]))
                except Exception:
                    vertices = list(entity.vertices())
                    for vertex in vertices:
                        points.append((vertex[0], vertex[1]))

            elif entity.dxftype() == 'POLYLINE':
                vertices = list(entity.vertices)
                for vertex in vertices:
                    loc = vertex.dxf.location
                    points.append((loc.x, loc.y))

        except Exception:
            pass

        return points

    def _bulge_to_arc_points(self, x1, y1, x2, y2, bulge):
        """Convert bulge to arc points."""
        import numpy as np

        arc_angle = 4 * np.arctan(abs(bulge))
        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2
        chord_length = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        sagitta = abs(bulge) * chord_length / 2
        radius = (chord_length / 2) / np.sin(arc_angle / 2) if arc_angle > 0 else chord_length / 2

        dx = x2 - x1
        dy = y2 - y1
        perp_x = -dy
        perp_y = dx
        perp_length = np.sqrt(perp_x**2 + perp_y**2)
        if perp_length > 0:
            perp_x /= perp_length
            perp_y /= perp_length

        dist_to_center = radius - sagitta if arc_angle < np.pi else radius + sagitta
        center_x = mid_x + perp_x * dist_to_center * np.sign(bulge)
        center_y = mid_y + perp_y * dist_to_center * np.sign(bulge)

        start_angle = np.arctan2(y1 - center_y, x1 - center_x)
        end_angle = np.arctan2(y2 - center_y, x2 - center_x)

        if bulge < 0:
            if end_angle > start_angle:
                end_angle -= 2 * np.pi
        else:
            if end_angle < start_angle:
                end_angle += 2 * np.pi

        num_points = max(16, int(abs(arc_angle) * radius / 1.0))
        angles = np.linspace(start_angle, end_angle, num_points)

        arc_points = []
        for angle in angles:
            x = center_x + radius * np.cos(angle)
            y = center_y + radius * np.sin(angle)
            arc_points.append((x, y))

        return arc_points

    def _group_into_polygons(self, entity_segments, tolerance=0.1):
        """Group connected entity segments into closed polygons.

        Args:
            entity_segments: List of point lists
            tolerance: Distance tolerance for connecting points

        Returns:
            List of closed polygons (each is a list of points)
        """
        from shapely.geometry import Polygon

        if not entity_segments:
            return []

        polygons = []
        used = [False] * len(entity_segments)

        for i, seg in enumerate(entity_segments):
            if used[i] or len(seg) < 2:
                continue

            # Check if segment is already closed
            if len(seg) >= 3:
                first = seg[0]
                last = seg[-1]
                dist = ((first[0] - last[0])**2 + (first[1] - last[1])**2)**0.5
                if dist < tolerance:
                    polygons.append(seg)
                    used[i] = True
                    continue

            # Try to build a closed polygon by connecting segments
            current_points = list(seg)
            used[i] = True
            current_end = seg[-1]

            found_connection = True
            while found_connection:
                found_connection = False
                for j, other_seg in enumerate(entity_segments):
                    if used[j] or len(other_seg) < 2:
                        continue

                    other_start = other_seg[0]
                    other_end = other_seg[-1]

                    # Check if we can connect
                    dist_to_start = ((current_end[0] - other_start[0])**2 + (current_end[1] - other_start[1])**2)**0.5
                    dist_to_end = ((current_end[0] - other_end[0])**2 + (current_end[1] - other_end[1])**2)**0.5

                    if dist_to_start < tolerance:
                        current_points.extend(other_seg[1:])
                        current_end = other_end
                        used[j] = True
                        found_connection = True
                        break
                    elif dist_to_end < tolerance:
                        current_points.extend(reversed(other_seg[:-1]))
                        current_end = other_start
                        used[j] = True
                        found_connection = True
                        break

            # Check if we have a closed polygon
            if len(current_points) >= 3:
                first = current_points[0]
                last = current_points[-1]
                dist = ((first[0] - last[0])**2 + (first[1] - last[1])**2)**0.5
                if dist < tolerance:
                    current_points.append(current_points[0])  # Close the polygon

                try:
                    poly = Polygon(current_points)
                    if poly.is_valid and poly.area > 1.0:  # Minimum area threshold
                        polygons.append(current_points)
                except Exception:
                    pass

        return polygons

    def _create_cut_shape(self, shape_data, filename):
        """Create a cut shape record from shape data.

        Args:
            shape_data: Dict with outer_polygon, inner_polygons, bounding_box, filename
            filename: Original DXF filename
        """
        import logging
        _logger = logging.getLogger(__name__)
        _logger.error(f"[2D Import Wizard] _create_cut_shape() - filename: {filename}, outer_polygon points: {len(shape_data.get('outer_polygon', []))}")

        # Generate position from filename
        position = os.path.splitext(filename)[0]

        # Generate description
        description = f"Shape from {filename}"

        # Create the shape to cut
        import json
        shape_to_cut = self.env['kojto.optimizer.2d.shapes.to.cut'].create({
            'package_id': self.package_id.id,
            'cut_position': position,
            'cut_description': description,
            'dxf_filename': filename,
        })
        _logger.error(f"[2D Import Wizard] _create_cut_shape() - created record {shape_to_cut.id}")

        # Set polygon data (normalized)
        shape_to_cut.set_polygon_data(
            shape_data['outer_polygon'],
            shape_data.get('inner_polygons')
        )
        _logger.error(f"[2D Import Wizard] _create_cut_shape() - set polygon data, outer_polygon_json: {bool(shape_to_cut.outer_polygon_json)}")

        # Store normalized DXF entities and transformation matrix
        if shape_data.get('normalized_entities'):
            shape_to_cut.normalized_dxf_entities_json = json.dumps(shape_data['normalized_entities'])
        if shape_data.get('transformation_matrix'):
            shape_to_cut.normalization_matrix_json = json.dumps(shape_data['transformation_matrix'])

        # Set bounding box values directly from shape_data
        if shape_data.get('bounding_box'):
            bbox = shape_data['bounding_box']
            shape_to_cut.bbox_min_x = bbox.get('min_x', 0.0)
            shape_to_cut.bbox_min_y = bbox.get('min_y', 0.0)
            shape_to_cut.bbox_max_x = bbox.get('max_x', 0.0)
            shape_to_cut.bbox_max_y = bbox.get('max_y', 0.0)
            shape_to_cut.bbox_width = bbox.get('width', 0.0)
            shape_to_cut.bbox_height = bbox.get('height', 0.0)

        # Update drawing and compute values directly from polygon JSON
        shape_to_cut._update_drawing()

        # Compute values directly from polygon JSON to ensure they're correct
        write_vals = {}
        if shape_to_cut.drawing:
            write_vals['drawing'] = shape_to_cut.drawing

        # Compute bbox directly from polygon JSON
        if shape_to_cut.outer_polygon_json:
            try:
                outer_poly = json.loads(shape_to_cut.outer_polygon_json)
                _logger.error(f"[2D Import Wizard] _create_cut_shape() - parsed outer_poly, points: {len(outer_poly) if outer_poly else 0}")
                if outer_poly and len(outer_poly) >= 3:
                    xs = [pt[0] for pt in outer_poly]
                    ys = [pt[1] for pt in outer_poly]
                    bbox_min_x = min(xs)
                    bbox_min_y = min(ys)
                    bbox_max_x = max(xs)
                    bbox_max_y = max(ys)
                    bbox_width = max(xs) - min(xs)
                    bbox_height = max(ys) - min(ys)
                    _logger.error(f"[2D Import Wizard] _create_cut_shape() - computed bbox: min_x={bbox_min_x}, min_y={bbox_min_y}, max_x={bbox_max_x}, max_y={bbox_max_y}, width={bbox_width}, height={bbox_height}")
                    write_vals.update({
                        'bbox_min_x': bbox_min_x,
                        'bbox_min_y': bbox_min_y,
                        'bbox_max_x': bbox_max_x,
                        'bbox_max_y': bbox_max_y,
                        'bbox_width': bbox_width,
                        'bbox_height': bbox_height,
                    })
                else:
                    write_vals.update({
                        'bbox_min_x': 0.0,
                        'bbox_min_y': 0.0,
                        'bbox_max_x': 0.0,
                        'bbox_max_y': 0.0,
                        'bbox_width': 0.0,
                        'bbox_height': 0.0,
                    })
            except Exception:
                write_vals.update({
                    'bbox_min_x': 0.0,
                    'bbox_min_y': 0.0,
                    'bbox_max_x': 0.0,
                    'bbox_max_y': 0.0,
                    'bbox_width': 0.0,
                    'bbox_height': 0.0,
                })

        # Compute shape area directly from polygon JSON
        if shape_to_cut.outer_polygon_json:
            try:
                from shapely.geometry import Polygon
                outer_poly = json.loads(shape_to_cut.outer_polygon_json)
                if outer_poly and len(outer_poly) >= 3:
                    inner_polys = []
                    if shape_to_cut.inner_polygons_json:
                        try:
                            inner_polys = json.loads(shape_to_cut.inner_polygons_json)
                        except json.JSONDecodeError:
                            pass

                    if inner_polys:
                        polygon = Polygon(outer_poly, inner_polys)
                    else:
                        polygon = Polygon(outer_poly)

                    if polygon.is_valid:
                        write_vals['shape_area'] = polygon.area
                    else:
                        fixed = polygon.buffer(0)
                        if hasattr(fixed, 'area'):
                            write_vals['shape_area'] = fixed.area if not hasattr(fixed, 'geoms') else sum(g.area for g in fixed.geoms)
                        else:
                            write_vals['shape_area'] = fixed.area
                else:
                    write_vals['shape_area'] = 0.0
            except Exception:
                write_vals['shape_area'] = 0.0

        # Compute weight from area, thickness, and material
        if 'shape_area' in write_vals and write_vals['shape_area'] > 0:
            if shape_to_cut.package_id and shape_to_cut.package_id.thickness and shape_to_cut.package_id.material_id:
                try:
                    density = shape_to_cut.package_id.material_id.density or 0.0
                    volume_m3 = (write_vals['shape_area'] / 1_000_000) * (shape_to_cut.package_id.thickness / 1000)
                    write_vals['shape_weight'] = volume_m3 * density
                except Exception:
                    write_vals['shape_weight'] = 0.0
            else:
                write_vals['shape_weight'] = 0.0
        else:
            write_vals['shape_weight'] = 0.0

        # Force write to ensure computed fields are persisted
        if write_vals:
            _logger.error(f"[2D Import Wizard] _create_cut_shape() - record {shape_to_cut.id}: writing values: {list(write_vals.keys())}, bbox_min_x={write_vals.get('bbox_min_x', 'N/A')}, shape_area={write_vals.get('shape_area', 'N/A')}")
            # Use write() with context flag to prevent recursion
            shape_to_cut.sudo().with_context(skip_compute_write=True).write(write_vals)
            _logger.error(f"[2D Import Wizard] _create_cut_shape() - record {shape_to_cut.id}: values written using write() with context flag")
        else:
            _logger.error(f"[2D Import Wizard] _create_cut_shape() - record {shape_to_cut.id}: no write_vals to write")

