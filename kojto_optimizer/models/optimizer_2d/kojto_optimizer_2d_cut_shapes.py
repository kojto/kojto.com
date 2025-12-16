"""
Kojto Optimizer 2D Shapes to Cut Model

Purpose:
--------
Defines the model for shapes to cut used in 2D optimization.
Each shape represents a DXF-based polygon that needs to be cut from stock material.
"""

import json
import base64
import io
import tempfile
import os
import ezdxf
import logging
from odoo import api, fields, models
from odoo.exceptions import ValidationError
from ...utils.compute_svg_from_polygons_and_points import compute_svg_from_polygons_and_points

_logger = logging.getLogger(__name__)


class KojtoOptimizer2dShapesToCut(models.Model):
    _name = "kojto.optimizer.2d.shapes.to.cut"
    _description = "Kojto Profile Optimizer 2D Shapes to Cut"

    package_id = fields.Many2one("kojto.optimizer.2d.packages", string="Package", required=True, ondelete="cascade")
    cut_position = fields.Char(string="Position", required=True)
    cut_description = fields.Char(string="Description", default="-")
    dxf_filename = fields.Char(string="DXF Filename", help="Original DXF filename")

    # DXF upload field for detail view
    dxf_file = fields.Binary(string="DXF File", help="Upload a DXF file to update the shape. Dimensions must be in mm.")
    dxf_file_name = fields.Char(string="DXF Filename")

    # Polygon data stored as JSON (normalized)
    outer_polygon_json = fields.Text(string="Outer Polygon", help="JSON array of (x, y) coordinates (normalized)")
    inner_polygons_json = fields.Text(string="Inner Polygons", help="JSON array of arrays for holes (normalized)")

    # Normalized DXF entities stored as JSON (for DXF export)
    normalized_dxf_entities_json = fields.Text(string="Normalized DXF Entities", help="JSON array of normalized DXF entities for export")

    # Transformation matrix for normalization (stored as JSON)
    normalization_matrix_json = fields.Text(string="Normalization Matrix", help="Transformation matrix used for normalization (3x3 matrix as JSON)")

    # Drawing image (SVG) - stored as regular Binary field, updated when polygon data changes
    drawing = fields.Binary(string="Drawing", help="SVG drawing of the shape")

    required_cut_shape_pieces = fields.Integer(string="Pieces", required=True, default=1)

    # Computed fields for details
    bbox_min_x = fields.Float(string="BBox Min X (mm)", compute="_compute_bbox", store=True)
    bbox_min_y = fields.Float(string="BBox Min Y (mm)", compute="_compute_bbox", store=True)
    bbox_max_x = fields.Float(string="BBox Max X (mm)", compute="_compute_bbox", store=True)
    bbox_max_y = fields.Float(string="BBox Max Y (mm)", compute="_compute_bbox", store=True)
    bbox_width = fields.Float(string="BBox Width (mm)", compute="_compute_bbox", store=True)
    bbox_height = fields.Float(string="BBox Height (mm)", compute="_compute_bbox", store=True)
    shape_area = fields.Float(string="Shape Area (mm²)", compute="_compute_shape_area", store=True)
    shape_weight = fields.Float(string="Shape Weight (kg)", compute="_compute_shape_weight", store=True)

    def _update_drawing(self):
        """Update SVG drawing from polygon data. Called when polygon data changes."""
        for record in self:
            if record.outer_polygon_json:
                try:
                    outer_poly = json.loads(record.outer_polygon_json)
                    if outer_poly and len(outer_poly) >= 3:
                        polygons_data = [{
                            'points': outer_poly,
                            'is_subtract': False
                        }]

                        # Add inner polygons (holes)
                        if record.inner_polygons_json:
                            try:
                                inner_polys = json.loads(record.inner_polygons_json)
                                for inner_poly in inner_polys:
                                    if inner_poly and len(inner_poly) >= 3:
                                        polygons_data.append({
                                            'points': inner_poly,
                                            'is_subtract': True
                                        })
                            except json.JSONDecodeError:
                                pass

                        record.drawing = compute_svg_from_polygons_and_points(polygons_data) or False
                    else:
                        record.drawing = False
                except Exception:
                    record.drawing = False
            else:
                record.drawing = False

    @api.depends("outer_polygon_json")
    def _compute_bbox(self):
        """Compute bounding box from outer polygon."""
        for record in self:
            if record.outer_polygon_json:
                try:
                    outer_poly = json.loads(record.outer_polygon_json)
                    if outer_poly and len(outer_poly) >= 3:
                        xs = [pt[0] for pt in outer_poly]
                        ys = [pt[1] for pt in outer_poly]
                        record.bbox_min_x = min(xs)
                        record.bbox_min_y = min(ys)
                        record.bbox_max_x = max(xs)
                        record.bbox_max_y = max(ys)
                        record.bbox_width = max(xs) - min(xs)
                        record.bbox_height = max(ys) - min(ys)
                    else:
                        record.bbox_min_x = 0.0
                        record.bbox_min_y = 0.0
                        record.bbox_max_x = 0.0
                        record.bbox_max_y = 0.0
                        record.bbox_width = 0.0
                        record.bbox_height = 0.0
                except (json.JSONDecodeError, (KeyError, IndexError, TypeError)):
                    record.bbox_min_x = 0.0
                    record.bbox_min_y = 0.0
                    record.bbox_max_x = 0.0
                    record.bbox_max_y = 0.0
                    record.bbox_width = 0.0
                    record.bbox_height = 0.0
            else:
                record.bbox_min_x = 0.0
                record.bbox_min_y = 0.0
                record.bbox_max_x = 0.0
                record.bbox_max_y = 0.0
                record.bbox_width = 0.0
                record.bbox_height = 0.0

    @api.depends("outer_polygon_json", "inner_polygons_json")
    def _compute_shape_area(self):
        """Compute actual shape area using polygon data."""
        for record in self:
            if record.outer_polygon_json:
                try:
                    from shapely.geometry import Polygon
                    outer_poly = json.loads(record.outer_polygon_json)
                    if outer_poly and len(outer_poly) >= 3:
                        inner_polys = []
                        if record.inner_polygons_json:
                            try:
                                inner_polys = json.loads(record.inner_polygons_json)
                            except json.JSONDecodeError:
                                pass

                        # Create Shapely polygon
                        if inner_polys:
                            polygon = Polygon(outer_poly, inner_polys)
                        else:
                            polygon = Polygon(outer_poly)

                        if polygon.is_valid:
                            record.shape_area = polygon.area
                        else:
                            # Try to fix invalid polygon
                            fixed = polygon.buffer(0)
                            if hasattr(fixed, 'area'):
                                record.shape_area = fixed.area if not hasattr(fixed, 'geoms') else sum(g.area for g in fixed.geoms)
                            else:
                                record.shape_area = fixed.area
                    else:
                        record.shape_area = 0.0
                except Exception:
                    record.shape_area = 0.0
            else:
                record.shape_area = 0.0

    @api.depends("shape_area", "package_id.thickness", "package_id.material_id", "package_id.material_id.density")
    def _compute_shape_weight(self):
        """Compute shape weight from area, thickness, and material density."""
        for record in self:
            if record.shape_area and record.package_id and record.package_id.thickness and record.package_id.material_id:
                try:
                    density = record.package_id.material_id.density or 0.0  # density in kg/m³
                    # Convert area from mm² to m², thickness from mm to m
                    volume_m3 = (record.shape_area / 1_000_000) * (record.package_id.thickness / 1000)
                    record.shape_weight = volume_m3 * density
                except Exception:
                    record.shape_weight = 0.0
            else:
                record.shape_weight = 0.0

    @api.constrains("required_cut_shape_pieces", "outer_polygon_json")
    def _check_positive_values(self):
        for record in self:
            if record.required_cut_shape_pieces <= 0:
                raise ValidationError("Cut shape pieces must be positive.")
            if record.outer_polygon_json:
                try:
                    outer_poly = json.loads(record.outer_polygon_json)
                    if not outer_poly or len(outer_poly) < 3:
                        raise ValidationError("Outer polygon must have at least 3 points.")
                except json.JSONDecodeError:
                    raise ValidationError("Invalid outer polygon JSON format.")

    @api.constrains("cut_position", "package_id")
    def _check_unique_cut_position(self):
        for rec in self:
            if rec.cut_position and rec.package_id:
                duplicates = self.search([
                    ('cut_position', '=', rec.cut_position),
                    ('package_id', '=', rec.package_id.id),
                    ('id', '!=', rec.id),
                ])
                if duplicates:
                    raise ValidationError(
                        f"Cannot save: Cut Position '{rec.cut_position}' already exists "
                        f"within package '{rec.package_id.name}'."
                    )

    _sql_constraints = [
        (
            'unique_cut_position_per_package',
            'UNIQUE(package_id, cut_position)',
            'Cut Position must be unique within the same package.'
        )
    ]

    def get_outer_polygon(self):
        """Get outer polygon as list of tuples."""
        if self.outer_polygon_json:
            try:
                return json.loads(self.outer_polygon_json)
            except json.JSONDecodeError:
                return []
        return []

    def get_inner_polygons(self):
        """Get inner polygons as list of lists of tuples."""
        if self.inner_polygons_json:
            try:
                return json.loads(self.inner_polygons_json)
            except json.JSONDecodeError:
                return []
        return []

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to ensure computed fields and drawing are calculated and stored."""
        _logger.error(f"[2D Shapes] create() called with {len(vals_list)} records")
        records = super().create(vals_list)
        # Update drawing and compute values directly from polygon JSON
        if records:
            records._update_drawing()
            # Compute values directly from polygon JSON to ensure they're correct
            for record in records:
                _logger.error(f"[2D Shapes] create() - processing record {record.id}, outer_polygon_json: {bool(record.outer_polygon_json)}")
                write_vals = {}
                if record.drawing:
                    write_vals['drawing'] = record.drawing

                # Compute bbox directly from polygon JSON
                if record.outer_polygon_json:
                    try:
                        outer_poly = json.loads(record.outer_polygon_json)
                        if outer_poly and len(outer_poly) >= 3:
                            xs = [pt[0] for pt in outer_poly]
                            ys = [pt[1] for pt in outer_poly]
                            write_vals.update({
                                'bbox_min_x': min(xs),
                                'bbox_min_y': min(ys),
                                'bbox_max_x': max(xs),
                                'bbox_max_y': max(ys),
                                'bbox_width': max(xs) - min(xs),
                                'bbox_height': max(ys) - min(ys),
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
                if record.outer_polygon_json:
                    try:
                        from shapely.geometry import Polygon
                        outer_poly = json.loads(record.outer_polygon_json)
                        if outer_poly and len(outer_poly) >= 3:
                            inner_polys = []
                            if record.inner_polygons_json:
                                try:
                                    inner_polys = json.loads(record.inner_polygons_json)
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
                    if record.package_id and record.package_id.thickness and record.package_id.material_id:
                        try:
                            density = record.package_id.material_id.density or 0.0
                            volume_m3 = (write_vals['shape_area'] / 1_000_000) * (record.package_id.thickness / 1000)
                            write_vals['shape_weight'] = volume_m3 * density
                        except Exception:
                            write_vals['shape_weight'] = 0.0
                    else:
                        write_vals['shape_weight'] = 0.0
                else:
                    write_vals['shape_weight'] = 0.0

                if write_vals:
                    _logger.error(f"[2D Shapes] create() - record {record.id}: writing values: {list(write_vals.keys())}, bbox_min_x={write_vals.get('bbox_min_x', 'N/A')}, shape_area={write_vals.get('shape_area', 'N/A')}")
                    # Use write() with context flag to prevent recursion
                    record.sudo().with_context(skip_compute_write=True).write(write_vals)
                    _logger.error(f"[2D Shapes] create() - record {record.id}: values written using write() with context flag")
                else:
                    _logger.error(f"[2D Shapes] create() - record {record.id}: no write_vals to write")
        return records

    def write(self, vals):
        """Override write to ensure computed fields and drawing are recalculated when dependencies change."""
        _logger.error(f"[2D Shapes] write() called for records {self.ids}, vals keys: {list(vals.keys())}")

        # Skip recursive writes (when we're writing only computed values)
        # Check if this is a recursive write from our own code by looking at context
        if self.env.context.get('skip_compute_write'):
            _logger.error(f"[2D Shapes] write() - skipping recursive write (context flag)")
            return super().write(vals)

        # Skip recursive writes (when we're writing only computed values)
        # If vals only contains computed fields and drawing, this is likely a recursive write from our own code
        computed_field_names = {'drawing', 'bbox_min_x', 'bbox_min_y', 'bbox_max_x', 'bbox_max_y',
                               'bbox_width', 'bbox_height', 'shape_area', 'shape_weight'}
        if vals and all(key in computed_field_names for key in vals.keys()) and 'outer_polygon_json' not in vals:
            _logger.error(f"[2D Shapes] write() - skipping recursive write with computed fields only: {list(vals.keys())}")
            return super().write(vals)

        # Check if dependencies are changing
        needs_recompute = any(key in vals for key in ['outer_polygon_json', 'inner_polygons_json', 'package_id'])

        # Check if polygon data is being set in this write
        polygon_json_in_vals = vals.get('outer_polygon_json')
        if polygon_json_in_vals:
            _logger.error(f"[2D Shapes] write() - polygon_json in vals, length: {len(str(polygon_json_in_vals))}")
        else:
            _logger.error(f"[2D Shapes] write() - polygon_json NOT in vals")

        result = super().write(vals)

        # Always recompute if polygon data exists (to ensure values are stored)
        # This handles cases where the record is saved after onchange
        has_polygon_data = False
        needs_bbox_recompute = False
        for record in self:
            # Check both in vals and in the record
            polygon_json = polygon_json_in_vals or record.outer_polygon_json
            _logger.error(f"[2D Shapes] write() - record {record.id}: polygon_json_in_vals={bool(polygon_json_in_vals)}, record.outer_polygon_json={bool(record.outer_polygon_json)}")
            if polygon_json:
                has_polygon_data = True
                # Parse to check if it's valid
                try:
                    if isinstance(polygon_json, str):
                        outer_poly = json.loads(polygon_json)
                    else:
                        outer_poly = polygon_json
                    _logger.error(f"[2D Shapes] write() - record {record.id}: parsed polygon, points: {len(outer_poly) if outer_poly else 0}")
                    if outer_poly and len(outer_poly) >= 3:
                        # Check if bbox values are 0 but polygon exists (indicates they need recomputation)
                        if (record.bbox_min_x == 0.0 and record.bbox_max_x == 0.0 and
                            record.bbox_min_y == 0.0 and record.bbox_max_y == 0.0):
                            needs_bbox_recompute = True
                            _logger.error(f"[2D Shapes] write() - record {record.id}: bbox values are 0, needs recompute")
                except Exception as e:
                    _logger.error(f"[2D Shapes] write() - record {record.id}: error parsing polygon_json: {e}", exc_info=True)
                break

        _logger.error(f"[2D Shapes] write() - needs_recompute={needs_recompute}, has_polygon_data={has_polygon_data}, needs_bbox_recompute={needs_bbox_recompute}")
        _logger.error(f"[2D Shapes] write() - condition check: needs_recompute={needs_recompute} OR has_polygon_data={has_polygon_data} OR needs_bbox_recompute={needs_bbox_recompute} = {needs_recompute or has_polygon_data or needs_bbox_recompute}")

        # If polygon data exists or dependencies changed, update drawing and recompute other fields
        if needs_recompute or has_polygon_data or needs_bbox_recompute:
            _logger.error(f"[2D Shapes] write() - ENTERING computation block")
            # Refresh records to ensure we have the latest values after the write
            self.invalidate_recordset()
            self._update_drawing()
            # Compute values directly from polygon JSON to ensure they're correct
            for record in self:
                _logger.error(f"[2D Shapes] write() - computing values for record {record.id}, record.outer_polygon_json={bool(record.outer_polygon_json)}")
                write_vals = {}
                if record.drawing:
                    write_vals['drawing'] = record.drawing

                # Get polygon JSON - use value from vals if it was just set, otherwise use record value
                polygon_json = polygon_json_in_vals if polygon_json_in_vals else record.outer_polygon_json
                _logger.error(f"[2D Shapes] write() - record {record.id}: using polygon_json, type: {type(polygon_json)}, length: {len(str(polygon_json)) if polygon_json else 0}")

                # Compute bbox directly from polygon JSON
                if polygon_json:
                    try:
                        # Parse polygon JSON (might be string or already parsed)
                        if isinstance(polygon_json, str):
                            outer_poly = json.loads(polygon_json)
                        else:
                            outer_poly = polygon_json
                        _logger.error(f"[2D Shapes] write() - record {record.id}: parsed outer_poly, points: {len(outer_poly) if outer_poly else 0}")
                        if outer_poly and len(outer_poly) >= 3:
                            xs = [pt[0] for pt in outer_poly]
                            ys = [pt[1] for pt in outer_poly]
                            bbox_min_x = min(xs)
                            bbox_min_y = min(ys)
                            bbox_max_x = max(xs)
                            bbox_max_y = max(ys)
                            bbox_width = max(xs) - min(xs)
                            bbox_height = max(ys) - min(ys)
                            _logger.error(f"[2D Shapes] write() - record {record.id}: computed bbox - min_x={bbox_min_x}, min_y={bbox_min_y}, max_x={bbox_max_x}, max_y={bbox_max_y}, width={bbox_width}, height={bbox_height}")
                            write_vals.update({
                                'bbox_min_x': bbox_min_x,
                                'bbox_min_y': bbox_min_y,
                                'bbox_max_x': bbox_max_x,
                                'bbox_max_y': bbox_max_y,
                                'bbox_width': bbox_width,
                                'bbox_height': bbox_height,
                            })
                        else:
                            _logger.error(f"[2D Shapes] write() - record {record.id}: outer_poly invalid or too few points")
                            write_vals.update({
                                'bbox_min_x': 0.0,
                                'bbox_min_y': 0.0,
                                'bbox_max_x': 0.0,
                                'bbox_max_y': 0.0,
                                'bbox_width': 0.0,
                                'bbox_height': 0.0,
                            })
                    except Exception as e:
                        _logger.error(f"[2D Shapes] write() - record {record.id}: exception computing bbox: {e}", exc_info=True)
                        write_vals.update({
                            'bbox_min_x': 0.0,
                            'bbox_min_y': 0.0,
                            'bbox_max_x': 0.0,
                            'bbox_max_y': 0.0,
                            'bbox_width': 0.0,
                            'bbox_height': 0.0,
                        })
                else:
                    _logger.error(f"[2D Shapes] write() - record {record.id}: no polygon_json available")

                # Compute shape area directly from polygon JSON
                if polygon_json:
                    try:
                        from shapely.geometry import Polygon
                        # Parse polygon JSON (might be string or already parsed)
                        if isinstance(polygon_json, str):
                            outer_poly = json.loads(polygon_json)
                        else:
                            outer_poly = polygon_json

                        # Get inner polygons
                        inner_polygons_json = vals.get('inner_polygons_json') if 'inner_polygons_json' in vals else record.inner_polygons_json

                        if outer_poly and len(outer_poly) >= 3:
                            inner_polys = []
                            if inner_polygons_json:
                                try:
                                    if isinstance(inner_polygons_json, str):
                                        inner_polys = json.loads(inner_polygons_json)
                                    else:
                                        inner_polys = inner_polygons_json
                                except json.JSONDecodeError:
                                    pass

                            if inner_polys:
                                polygon = Polygon(outer_poly, inner_polys)
                            else:
                                polygon = Polygon(outer_poly)

                            if polygon.is_valid:
                                shape_area = polygon.area
                                _logger.error(f"[2D Shapes] write() - record {record.id}: computed shape_area={shape_area}")
                                write_vals['shape_area'] = shape_area
                            else:
                                fixed = polygon.buffer(0)
                                if hasattr(fixed, 'area'):
                                    shape_area = fixed.area if not hasattr(fixed, 'geoms') else sum(g.area for g in fixed.geoms)
                                else:
                                    shape_area = fixed.area
                                _logger.error(f"[2D Shapes] write() - record {record.id}: computed shape_area (fixed)={shape_area}")
                                write_vals['shape_area'] = shape_area
                        else:
                            _logger.error(f"[2D Shapes] write() - record {record.id}: outer_poly invalid for area computation")
                            write_vals['shape_area'] = 0.0
                    except Exception as e:
                        _logger.error(f"[2D Shapes] write() - record {record.id}: exception computing shape_area: {e}", exc_info=True)
                        write_vals['shape_area'] = 0.0

                # Compute weight from area, thickness, and material
                if 'shape_area' in write_vals and write_vals['shape_area'] > 0:
                    if record.package_id and record.package_id.thickness and record.package_id.material_id:
                        try:
                            density = record.package_id.material_id.density or 0.0
                            volume_m3 = (write_vals['shape_area'] / 1_000_000) * (record.package_id.thickness / 1000)
                            write_vals['shape_weight'] = volume_m3 * density
                        except Exception:
                            write_vals['shape_weight'] = 0.0
                    else:
                        write_vals['shape_weight'] = 0.0
                else:
                    write_vals['shape_weight'] = 0.0

                if write_vals:
                    _logger.error(f"[2D Shapes] write() - record {record.id}: final write_vals: {list(write_vals.keys())}, bbox_min_x={write_vals.get('bbox_min_x', 'N/A')}, shape_area={write_vals.get('shape_area', 'N/A')}")
                    # Use write() with context flag to prevent recursion
                    record.sudo().with_context(skip_compute_write=True).write(write_vals)
                    _logger.error(f"[2D Shapes] write() - record {record.id}: values written using write() with context flag")
                else:
                    _logger.error(f"[2D Shapes] write() - record {record.id}: no final write_vals to write")

        return result

    def set_polygon_data(self, outer_polygon, inner_polygons=None):
        """Set polygon data from lists."""
        self.outer_polygon_json = json.dumps(outer_polygon) if outer_polygon else None
        self.inner_polygons_json = json.dumps(inner_polygons) if inner_polygons else None

    def open_o2m_record(self):
        """Open shape details form view."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Shape to Cut {self.cut_position}",
            "res_model": "kojto.optimizer.2d.shapes.to.cut",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }

    @api.onchange("dxf_file")
    def _onchange_dxf_file(self):
        """Process DXF file when uploaded in detail view. All dimensions must be in mm."""
        _logger.error(f"[2D Shapes] _onchange_dxf_file() - START, dxf_file={bool(self.dxf_file)}, dxf_file_name={self.dxf_file_name}")
        warning = {}
        if self.dxf_file and self.dxf_file_name:
            _logger.error(f"[2D Shapes] _onchange_dxf_file() - processing DXF file")
            try:
                # Odoo Binary fields store data as base64-encoded strings
                # Use the same simple approach as the import wizard which works
                dxf_file_data = self.dxf_file

                # In Odoo, Binary fields return base64-encoded strings (not bytes)
                # We need to decode them to get the actual file bytes
                if isinstance(dxf_file_data, str):
                    # It's a base64-encoded string, decode it
                    dxf_content = base64.b64decode(dxf_file_data)
                elif isinstance(dxf_file_data, bytes):
                    # If it's already bytes, it might be:
                    # 1. Already decoded (raw DXF) - unlikely in Odoo
                    # 2. Base64-encoded bytes that need decoding
                    # Try to decode it as base64 first
                    try:
                        # Convert bytes to string for base64 decode
                        dxf_content = base64.b64decode(dxf_file_data.decode('ascii'))
                    except (UnicodeDecodeError, ValueError):
                        # If that fails, assume it's already raw DXF content
                        dxf_content = dxf_file_data
                else:
                    # Convert to string first, then decode
                    dxf_file_str = str(dxf_file_data)
                    dxf_content = base64.b64decode(dxf_file_str)

                # Ensure we have bytes (base64.b64decode always returns bytes)
                if not isinstance(dxf_content, bytes):
                    raise ValueError(f"Expected bytes after base64 decode, got {type(dxf_content)}")

                # Verify we have actual DXF content
                if len(dxf_content) < 10:
                    warning = {
                        'title': 'Invalid DXF File',
                        'message': f"DXF file '{self.dxf_file_name}' appears to be too small or empty."
                    }
                    return {'warning': warning}

                # Use temporary file approach (same as import wizard which works)
                # This avoids issues with BytesIO/StringIO and ezdxf's internal text processing
                with tempfile.NamedTemporaryFile(mode='wb', suffix='.dxf', delete=False) as tmp_file:
                    tmp_file.write(dxf_content)
                    tmp_path = tmp_file.name

                try:
                    # Read DXF from temporary file (ezdxf.readfile handles file paths correctly)
                    doc = ezdxf.readfile(tmp_path)
                    msp = doc.modelspace()

                    entities = []
                    for entity in msp:
                        if entity.dxftype() in ['LINE', 'ARC', 'CIRCLE', 'LWPOLYLINE', 'POLYLINE']:
                            entities.append(entity)

                    if not entities:
                        warning = {
                            'title': 'Invalid DXF File',
                            'message': f"No valid entities found in DXF file '{self.dxf_file_name}'. Please ensure the DXF contains LINE, ARC, CIRCLE, LWPOLYLINE, or POLYLINE entities."
                        }
                        return {'warning': warning}

                    # Process DXF entities following the new flow
                    outer_polygon_points, inner_polygon_points_list, bbox_data, normalized_entities, transformation_matrix = self._process_dxf_entities(entities)

                    if not outer_polygon_points:
                        warning = {
                            'title': 'Invalid Shape',
                            'message': f"Could not extract a valid outer polygon from DXF file '{self.dxf_file_name}'. Please ensure the DXF contains closed polygons."
                        }
                        return {'warning': warning}

                    # Update polygon data (normalized)
                    self.outer_polygon_json = json.dumps(outer_polygon_points)
                    self.inner_polygons_json = json.dumps(inner_polygon_points_list) if inner_polygon_points_list else None
                    _logger.error(f"[2D Shapes] _onchange_dxf_file() - set outer_polygon_json, points: {len(outer_polygon_points) if outer_polygon_points else 0}")

                    # Store normalized DXF entities and transformation matrix
                    self.normalized_dxf_entities_json = json.dumps(normalized_entities) if normalized_entities else None
                    self.normalization_matrix_json = json.dumps(transformation_matrix) if transformation_matrix else None

                    self.dxf_filename = self.dxf_file_name

                    # Auto-generate position from filename if not set
                    if not self.cut_position and self.dxf_file_name:
                        # Generate position from filename (same as import wizard)
                        position = os.path.splitext(self.dxf_file_name)[0]
                        self.cut_position = position

                    # Auto-generate description from filename if not set or default
                    if not self.cut_description or self.cut_description == "-":
                        if self.dxf_file_name:
                            self.cut_description = f"Shape from {self.dxf_file_name}"

                    # Update drawing and trigger recomputation of computed fields
                    # In onchange context, we need to manually trigger these
                    self._update_drawing()
                    # Recompute bbox from normalized polygon JSON
                    self._compute_bbox()
                    # Ensure bbox values are set (in onchange, computed fields may not persist)
                    if self.outer_polygon_json:
                        try:
                            outer_poly = json.loads(self.outer_polygon_json)
                            if outer_poly and len(outer_poly) >= 3:
                                xs = [pt[0] for pt in outer_poly]
                                ys = [pt[1] for pt in outer_poly]
                                self.bbox_min_x = min(xs)
                                self.bbox_min_y = min(ys)
                                self.bbox_max_x = max(xs)
                                self.bbox_max_y = max(ys)
                                self.bbox_width = max(xs) - min(xs)
                                self.bbox_height = max(ys) - min(ys)
                                _logger.error(f"[2D Shapes] _onchange_dxf_file() - set bbox values: min_x={self.bbox_min_x}, min_y={self.bbox_min_y}, max_x={self.bbox_max_x}, max_y={self.bbox_max_y}, width={self.bbox_width}, height={self.bbox_height}")
                            else:
                                _logger.error(f"[2D Shapes] _onchange_dxf_file() - outer_poly invalid or too few points: {len(outer_poly) if outer_poly else 0}")
                        except Exception as e:
                            _logger.error(f"[2D Shapes] _onchange_dxf_file() - exception setting bbox: {e}", exc_info=True)
                    else:
                        _logger.error(f"[2D Shapes] _onchange_dxf_file() - no outer_polygon_json available")
                    self._compute_shape_area()
                    _logger.error(f"[2D Shapes] _onchange_dxf_file() - computed shape_area={self.shape_area}")
                    # Also compute weight (depends on shape_area, thickness, material)
                    self._compute_shape_weight()
                    _logger.error(f"[2D Shapes] _onchange_dxf_file() - computed shape_weight={self.shape_weight}")

                    # Log final state before return
                    _logger.error(f"[2D Shapes] _onchange_dxf_file() - final state: outer_polygon_json={bool(self.outer_polygon_json)}, length={len(self.outer_polygon_json) if self.outer_polygon_json else 0}")

                finally:
                    # Clean up temporary file
                    if 'tmp_path' in locals() and os.path.exists(tmp_path):
                        try:
                            os.unlink(tmp_path)
                        except Exception:
                            pass  # Ignore cleanup errors

            except ezdxf.DXFError as e:
                warning = {
                    'title': 'DXF Read Error',
                    'message': f"Error reading DXF file '{self.dxf_file_name}': {str(e)}"
                }
                return {'warning': warning}
            except Exception as e:
                _logger.exception("Error during DXF processing in detail view")
                warning = {
                    'title': 'Processing Error',
                    'message': f"An unexpected error occurred during DXF processing: {str(e)}"
                }
                return {'warning': warning}
        else:
            _logger.error(f"[2D Shapes] _onchange_dxf_file() - no dxf_file or dxf_file_name, returning empty")
        _logger.error(f"[2D Shapes] _onchange_dxf_file() - END, returning empty dict")
        return {}

    def _process_dxf_entities(self, entities):
        """Process DXF entities following the required flow:

        1. Read DXF entities
        2. Generate Shapely polygons (external and holes)
        3. Verify polygons
        4. Compute minimum bounding box
        5. Normalize polygons, bounding box, and DXF entities
        6. Store all normalized data

        Returns:
            tuple: (outer_points, inner_points_list, bbox_data, normalized_entities, transformation_matrix)
        """
        import numpy as np
        from shapely.geometry import Polygon, Point, MultiPoint
        from shapely.affinity import translate as shapely_translate

        # Step 1: Read DXF entities and convert to serializable format
        dxf_entities = self._convert_entities_to_dict(entities)
        if not dxf_entities:
            return [], [], {}, [], None

        # Step 2: Extract entity segments and generate polygons
        # Extract entity segments (start_pt, end_pt, all_points, entity_type, vertex_points)
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
                except Exception as e:
                    _logger.warning(f"Error processing LWPOLYLINE: {e}")
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
                except Exception as e:
                    _logger.warning(f"Error processing POLYLINE: {e}")

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
                # Check if this inner poly is nested inside another inner poly
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
            return [], [], {}, [], np.eye(3).tolist()

        rotation_angle = bbox_data_before_normalization.get('angle', 0.0)
        bbox_center = bbox_data_before_normalization.get('center', (0.0, 0.0))
        bbox_center_x, bbox_center_y = bbox_center[0], bbox_center[1]

        # Step 5: Normalize - rotate to horizontal, then translate to origin
        from shapely.affinity import rotate as shapely_rotate
        from shapely.geometry import Point as ShapelyPoint

        # Initialize transformation matrix
        transformation_matrix = np.eye(3)

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

            # Update transformation matrix with rotation
            angle_rad = np.radians(-rotation_angle)
            cos_a = np.cos(angle_rad)
            sin_a = np.sin(angle_rad)
            T_translate_to_origin = np.array([
                [1, 0, -bbox_center_x],
                [0, 1, -bbox_center_y],
                [0, 0, 1]
            ])
            T_rotate = np.array([
                [cos_a, -sin_a, 0],
                [sin_a, cos_a, 0],
                [0, 0, 1]
            ])
            T_translate_back = np.array([
                [1, 0, bbox_center_x],
                [0, 1, bbox_center_y],
                [0, 0, 1]
            ])
            transformation_matrix = T_translate_back @ T_rotate @ T_translate_to_origin

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

            # Update transformation matrix with translation
            T_translate = np.array([
                [1, 0, translate_x],
                [0, 1, translate_y],
                [0, 0, 1]
            ])
            transformation_matrix = T_translate @ transformation_matrix

        # Extract normalized polygon points
        normalized_outer_points = []
        if outer_poly.exterior:
            coords = list(outer_poly.exterior.coords[:-1])  # Remove closing point
            normalized_outer_points = [(float(x), float(y)) for x, y in coords]
        elif outer_points:
            # Use manually translated points if polygon extraction fails
            normalized_outer_points = outer_points

        normalized_inner_points_list = []
        if outer_poly.interiors:
            for interior in outer_poly.interiors:
                coords = list(interior.coords[:-1])  # Remove closing point
                normalized_inner_points_list.append([(float(x), float(y)) for x, y in coords])

        # Also use manually translated inner polygons if they exist
        if inner_polys:
            for inner_points in inner_polys:
                # Remove closing point if present
                if len(inner_points) > 1 and self._points_close(inner_points[0], inner_points[-1], tolerance=0.1):
                    normalized_inner = inner_points[:-1]
                else:
                    normalized_inner = inner_points
                normalized_inner_points_list.append(normalized_inner)

        # Normalize DXF entities using the full transformation matrix
        normalized_dxf_entities = self._apply_transformation_to_entities(dxf_entities, transformation_matrix)

        # Compute final normalized bounding box
        bbox_data = self._compute_bounding_box_from_shapely(outer_poly)

        # Convert transformation matrix to list for JSON storage
        transformation_matrix_list = transformation_matrix.tolist()

        return normalized_outer_points, normalized_inner_points_list, bbox_data, normalized_dxf_entities, transformation_matrix_list

    def _convert_entities_to_dict(self, entities):
        """Convert DXF entities to serializable dictionary format.

        Args:
            entities: List of ezdxf entities

        Returns:
            List of dictionaries representing entities
        """
        import numpy as np
        dxf_entities = []

        for entity in entities:
            entity_dict = {'type': entity.dxftype()}

            if entity.dxftype() == 'LINE':
                entity_dict['start'] = (float(entity.dxf.start.x), float(entity.dxf.start.y))
                entity_dict['end'] = (float(entity.dxf.end.x), float(entity.dxf.end.y))

            elif entity.dxftype() == 'ARC':
                entity_dict['center'] = (float(entity.dxf.center.x), float(entity.dxf.center.y))
                entity_dict['radius'] = float(entity.dxf.radius)
                entity_dict['start_angle'] = float(entity.dxf.start_angle)  # degrees
                entity_dict['end_angle'] = float(entity.dxf.end_angle)  # degrees

            elif entity.dxftype() == 'CIRCLE':
                entity_dict['center'] = (float(entity.dxf.center.x), float(entity.dxf.center.y))
                entity_dict['radius'] = float(entity.dxf.radius)

            elif entity.dxftype() == 'LWPOLYLINE':
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

                    entity_dict['points'] = [(float(p[0]), float(p[1])) for p in points_with_bulge]
                    entity_dict['bulges'] = [float(p[2]) if len(p) >= 3 else 0.0 for p in points_with_bulge]
                    try:
                        entity_dict['closed'] = entity.closed if hasattr(entity, 'closed') else False
                    except:
                        entity_dict['closed'] = False
                except Exception:
                    try:
                        vertices = list(entity.vertices())
                        entity_dict['points'] = [(float(v[0]), float(v[1])) for v in vertices]
                        entity_dict['bulges'] = [0.0] * len(entity_dict['points'])
                        entity_dict['closed'] = False
                    except:
                        continue

            elif entity.dxftype() == 'POLYLINE':
                try:
                    vertices = list(entity.vertices)
                    entity_dict['points'] = [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in vertices]
                    entity_dict['bulges'] = []
                    for v in vertices:
                        bulge = float(v.dxf.bulge) if hasattr(v.dxf, 'bulge') else 0.0
                        entity_dict['bulges'].append(bulge)
                    entity_dict['closed'] = entity.is_closed if hasattr(entity, 'is_closed') else False
                except Exception:
                    continue

            if entity_dict.get('type'):
                dxf_entities.append(entity_dict)

        return dxf_entities

    def _apply_transformation_to_entities(self, entities, transformation_matrix):
        """Apply transformation matrix to DXF entities.

        Args:
            entities: List of entity dictionaries
            transformation_matrix: 3x3 numpy array transformation matrix

        Returns:
            List of transformed entity dictionaries
        """
        import numpy as np

        def transform_point(point, matrix):
            """Transform a 2D point using 3x3 transformation matrix."""
            x, y = point[0], point[1]
            # Convert to homogeneous coordinates
            p = np.array([x, y, 1.0])
            # Apply transformation
            p_transformed = matrix @ p
            return (float(p_transformed[0]), float(p_transformed[1]))

        # Extract rotation angle from transformation matrix
        # The rotation is in the top-left 2x2 submatrix
        rotation_angle_rad = np.arctan2(transformation_matrix[1, 0], transformation_matrix[0, 0])
        rotation_angle_deg = np.degrees(rotation_angle_rad)

        transformed_entities = []
        for entity in entities:
            transformed_entity = entity.copy()

            if entity['type'] == 'LINE':
                transformed_entity['start'] = transform_point(entity['start'], transformation_matrix)
                transformed_entity['end'] = transform_point(entity['end'], transformation_matrix)

            elif entity['type'] == 'ARC':
                # Transform center
                transformed_entity['center'] = transform_point(entity['center'], transformation_matrix)
                # Add rotation to start and end angles
                start_angle = float(entity.get('start_angle', 0))
                end_angle = float(entity.get('end_angle', 360))

                # Simply add the rotation angle to both angles
                new_start_angle = start_angle + rotation_angle_deg
                new_end_angle = end_angle + rotation_angle_deg

                # Normalize to [0, 360) range
                new_start_angle = new_start_angle % 360
                if new_start_angle < 0:
                    new_start_angle += 360
                new_end_angle = new_end_angle % 360
                if new_end_angle < 0:
                    new_end_angle += 360

                transformed_entity['start_angle'] = new_start_angle
                transformed_entity['end_angle'] = new_end_angle

            elif entity['type'] == 'CIRCLE':
                transformed_entity['center'] = transform_point(entity['center'], transformation_matrix)

            elif entity['type'] in ['LWPOLYLINE', 'POLYLINE']:
                transformed_entity['points'] = [transform_point(p, transformation_matrix) for p in entity['points']]
                # Bulges and closed flag remain the same

            transformed_entities.append(transformed_entity)

        return transformed_entities

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
        """Group connected entities (lines, arcs, polylines) into closed shapes.

        Args:
            entity_segments: List of (start_pt, end_pt, all_points, entity_type, vertex_points)
            use_vertices_only: If True, use only vertex_points; if False, use all_points

        Returns:
            List of point sequences representing closed shapes
        """
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

            # If entity is already closed, add it as a separate shape
            if self._points_close(start1, end1, tolerance):
                closed_shapes.append(points1)
                used[i] = True
                continue

            # Try to build a connected shape starting from this entity
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

                    # Check if seg2 connects to current_end
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

            # Check if the shape is closed
            if len(shape_points) >= 3:
                first_pt = shape_points[0]
                last_pt = shape_points[-1]
                if self._points_close(first_pt, last_pt, tolerance):
                    closed_shapes.append(shape_points)
                else:
                    # Try to close if very close
                    dist_to_close = np.sqrt((first_pt[0] - last_pt[0])**2 + (first_pt[1] - last_pt[1])**2)
                    if dist_to_close < tolerance * 10:
                        shape_points.append(first_pt)
                        closed_shapes.append(shape_points)

        return closed_shapes

    def _bulge_to_arc_points(self, x1, y1, x2, y2, bulge, num_segments=10):
        """Convert bulge to arc points."""
        import numpy as np
        if abs(bulge) < 0.001:
            return [(x1, y1), (x2, y2)]

        chord_length = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        if chord_length == 0:
            return [(x1, y1)]

        sagitta = abs(bulge) * chord_length / 2
        radius = (chord_length / 2) / np.sin(2 * np.arctan(abs(bulge))) if abs(bulge) > 1e-6 else 0

        if radius == 0:
            return [(x1, y1), (x2, y2)]

        mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
        perp_x, perp_y = -(y2 - y1), (x2 - x1)
        perp_length = np.sqrt(perp_x**2 + perp_y**2)
        perp_x, perp_y = perp_x / perp_length, perp_y / perp_length

        dist_to_center = radius - sagitta if abs(bulge) < 1 else radius + sagitta
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

        angles = np.linspace(start_angle, end_angle, num_segments)
        arc_points = [(center_x + radius * np.cos(angle), center_y + radius * np.sin(angle)) for angle in angles]
        return arc_points

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


