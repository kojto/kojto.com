#$ kojto_profiles/models/kojto_profile_shapes.py

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from shapely.geometry import Polygon, Point
from ..utils.compute_svg_from_polygons_and_points import compute_svg_from_polygons_and_points


class KojtoProfileShapes(models.Model):
    _name = "kojto.profile.shapes"
    _description = "Kojto Profile Shapes"
    _rec_name = "name"

    name = fields.Char(string="Name", compute="_compute_shape_name", store=True, readonly=True, help="Unique name of the shape (e.g., SHP_001)")
    description = fields.Char(string="Description", help="Optional description of the shape")
    polygon_ids = fields.One2many("kojto.profile.shape.polygons", "shape_id", string="Polygons")
    drawing = fields.Binary(string="Drawing", compute="_compute_shape_drawing", store=False)
    area = fields.Float(string="Shape Area (cm²)", compute="_compute_area", store=False)
    insert_ids = fields.One2many("kojto.profile.shape.inserts", "shape_id", string="Inserts")

    ### --- NAME GENERATION ---
    @api.depends("polygon_ids")
    def _compute_shape_name(self):
        existing_names = self.env["kojto.profile.shapes"].search_read(
            [("name", "=like", "SHP_%")], ["name"]
        )
        used_numbers = {
            int(name["name"].split("_")[1])
            for name in existing_names
            if name["name"].startswith("SHP_") and name["name"].split("_")[1].isdigit()
        }

        next_number = max(used_numbers, default=0) + 1
        for rec in self:
            if not rec.name:
                rec.name = f"SHP_{next_number:03d}"
                next_number += 1

    ### --- AREA CALCULATION ---
    @api.depends("polygon_ids.point_ids.x", "polygon_ids.point_ids.y")
    def _compute_area(self):
        for rec in self:
            area = 0.0
            polygons = rec.polygon_ids.filtered(lambda p: len(p.point_ids) >= 3)
            ext = polygons.filtered(lambda p: p.is_external)
            holes = polygons.filtered(lambda p: not p.is_external)

            try:
                if ext:
                    ext_points = [(pt.x, pt.y) for pt in ext[0].point_ids]
                    ext_poly = Polygon(ext_points).buffer(0)
                    if ext_poly.is_valid:
                        area = ext_poly.area
                        for hole in holes:
                            hole_points = [(pt.x, pt.y) for pt in hole.point_ids]
                            hole_poly = Polygon(hole_points).buffer(0)
                            if hole_poly.is_valid:
                                area -= hole_poly.area
            except Exception:
                area = 0.0

            rec.area = area / 100  # mm² to cm²

    ### --- DRAWING SVG ---
    @api.depends("polygon_ids.point_ids.x", "polygon_ids.point_ids.y")
    def _compute_shape_drawing(self):
        for rec in self:
            polygons = []
            for poly in rec.polygon_ids.filtered(lambda p: len(p.point_ids) >= 3):
                pts = [(pt.x, pt.y) for pt in poly.point_ids]
                polygons.append({
                    "points": pts,
                    "is_subtract": not poly.is_external,
                    "id_different_color": poly.is_external
                })

            try:
                rec.drawing = compute_svg_from_polygons_and_points(polygons) if polygons else False
            except Exception:
                rec.drawing = False

    ### --- CONSTRAINTS ---
    @api.constrains("polygon_ids", "polygon_ids.point_ids")
    def _check_valid_polygons(self):
        for rec in self:
            polygons = rec.polygon_ids.filtered(lambda p: len(p.point_ids) >= 3)
            if not polygons:
                continue

            # Ensure one external polygon
            external = polygons.filtered(lambda p: p.is_external)
            if len(external) != 1:
                raise ValidationError("There must be exactly one external polygon.")

            # Build shapely objects
            shapely_map = {}
            for poly in polygons:
                pts = [(pt.x, pt.y) for pt in poly.point_ids]
                try:
                    shape = Polygon(pts).buffer(0)
                    if not shape.is_valid or shape.is_empty:
                        raise ValidationError(f"Invalid polygon geometry in '{poly.name}'.")
                    shapely_map[poly] = shape
                except Exception as e:
                    raise ValidationError(f"Polygon error in '{poly.name}': {str(e)}")

            ext_poly = external[0]
            ext_shape = shapely_map[ext_poly]

            # Internal containment checks
            for poly, shape in shapely_map.items():
                if poly == ext_poly:
                    continue
                if not ext_shape.contains(shape) or shape.touches(ext_shape):
                    raise ValidationError(
                        f"Polygon '{poly.name}' must be strictly inside the external polygon."
                    )

            # Internal-to-internal checks
            internal_polys = [p for p in shapely_map if p != ext_poly]
            for i, poly1 in enumerate(internal_polys):
                shape1 = shapely_map[poly1]
                for poly2 in internal_polys[i + 1:]:
                    shape2 = shapely_map[poly2]
                    if not shape1.disjoint(shape2):
                        raise ValidationError(
                            f"Polygons '{poly1.name}' and '{poly2.name}' overlap or touch."
                        )

    ### --- AVOID EXPENSIVE CHECKS IN ONCHANGE ---
    @api.onchange("polygon_ids", "polygon_ids.point_ids")
    def _onchange_polygon_trigger(self):
        self._compute_shape_drawing()
        self._compute_area()

