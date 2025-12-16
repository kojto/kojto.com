"""
Kojto Optimizer 2DR Import Wizard Model

Purpose:
--------
Provides a wizard interface for importing stock and cut rectangles data
into 2DR optimization packages. Supports tab-separated data format.
"""

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class KojtoOptimizer2drImportWizard(models.TransientModel):
    _name = "kojto.optimizer.2dr.import.wizard"
    _description = "Kojto Profile Optimizer 2DR Import Wizard"

    package_id = fields.Many2one(
        "kojto.optimizer.2dr.packages",
        string="Package",
        required=True
    )
    import_type = fields.Selection(
        [("stock_rectangles", "Stock Rectangles"), ("cut_rectangles", "Cut Rectangles")],
        string="Import Type",
        required=True
    )
    data = fields.Text(string="Import Data", required=True)

    def action_import(self):
        """Parse and import the data into stock or cut rectangles."""
        self.ensure_one()
        lines = [line.strip() for line in self.data.strip().split("\n") if line.strip()]
        if not lines:
            raise ValidationError("No data provided.")

        # Skip header if present
        start_idx = 1 if lines[0].upper().startswith("POSITION") else 0
        if len(lines) <= start_idx:
            raise ValidationError("No valid data rows provided.")

        # Process each line
        for line in lines[start_idx:]:
            try:
                position, desc, width, height, qty = self._split_line(line)
                vals = self._prepare_record_vals(position, desc, width, height, qty, self.import_type)
                self.env[self._get_model_name()].create(vals)
            except Exception as e:
                raise ValidationError(f"Error processing line '{line}': {str(e)}")

        return {'type': 'ir.actions.act_window_close'}

    def _split_line(self, line):
        """Split a tab-separated line into its components."""
        parts = line.split("\t")
        if len(parts) != 5:
            raise ValidationError(
                f"Invalid format. Expected 5 columns (Position, Description, Width, Height, Quantity), "
                f"got {len(parts)}."
            )
        return parts

    def _prepare_record_vals(self, position, desc, width, height, qty, import_type):
        """Prepare dictionary of values for creating a record."""
        try:
            width = float(width)
            height = float(height)
            qty = int(qty)
        except ValueError as e:
            raise ValidationError(f"Invalid number format: {str(e)}")

        if any(v <= 0 for v in [width, height, qty]):
            raise ValidationError("Width, height, and quantity must be positive.")

        if import_type == "stock_rectangles":
            return {
                "package_id": self.package_id.id,
                "stock_position": position,
                "stock_description": desc or "-",
                "stock_width": width,
                "stock_length": height,
                "available_stock_rectangle_pieces": qty,
            }
        return {
            "package_id": self.package_id.id,
            "cut_position": position,
            "cut_description": desc or "-",
            "cut_width": width,
            "cut_length": height,
            "required_cut_rectangle_pieces": qty,
        }

    def _get_model_name(self):
        """Return the model name based on import type."""
        return (
            "kojto.optimizer.2dr.stock.rectangles"
            if self.import_type == "stock_rectangles"
            else "kojto.optimizer.2dr.cut.rectangles"
        )
