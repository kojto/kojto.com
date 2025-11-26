import json
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class KojtoOptimizer1DBars(models.Model):
    _name = "kojto.optimizer.1d.bars"
    _description = "Bars for Kojto Optimizer 1D"

    package_id = fields.Many2one("kojto.optimizer.1d.packages", string="Package", required=True, ondelete="cascade")
    bar_position = fields.Char(string="Bar Position", required=True)
    bar_description = fields.Char(string="Bar Description", default="Bar_")
    bar_length = fields.Float(string="Length (mm)", required=True)
    required_bar_pieces = fields.Integer(string="Pieces", required=True, default=1)
    allocated_bar_pieces = fields.Integer(string="Allocated Pieces", compute="_compute_allocated_bar_pieces", store=True)

    @api.depends("package_id.cutting_plan_json")
    def _compute_allocated_bar_pieces(self):
        for record in self:
            allocated_pieces = 0
            if record.package_id.cutting_plan_json:
                try:
                    cutting_plan = json.loads(record.package_id.cutting_plan_json)
                    for plan in cutting_plan.get("cutting_plans", []):
                        for cut in plan.get("cuts", []):
                            if cut.get("bar_id") == str(record.id):
                                allocated_pieces += cut.get("pieces", 0)
                except (json.JSONDecodeError, Exception):
                    allocated_pieces = 0
            record.allocated_bar_pieces = allocated_pieces

    @api.constrains("bar_length", "required_bar_pieces")
    def _check_positive_values(self):
        for record in self:
            if record.bar_length <= 0:
                raise ValidationError("Bar length must be positive.")
            if record.required_bar_pieces <= 0:
                raise ValidationError("Bar pieces must be positive.")

    @api.constrains("bar_length", "package_id")
    def _check_length_vs_cuts(self):
        for record in self:
            initial_cut = record.package_id.initial_cut or 0.0
            final_cut = record.package_id.final_cut or 0.0
            width_of_cut = record.package_id.width_of_cut or 0.0
            min_required_length = initial_cut + final_cut + width_of_cut
            if record.bar_length <= min_required_length:
                raise ValidationError(
                    f"Bar length ({record.bar_length} mm) must be greater than "
                    f"initial cut ({initial_cut} mm) + final cut ({final_cut} mm) + "
                    f"width of cut ({width_of_cut} mm)."
                )

    @api.constrains("bar_description")
    def _check_bar_description(self):
        for record in self:
            if record.bar_description and not record.bar_description.strip():
                raise ValidationError("Bar description cannot be empty or only whitespace.")

    _sql_constraints = [
        (
            "unique_bar_position_per_package",
            "UNIQUE(package_id, bar_position)",
            "Bar Position must be unique within the same package.",
        )
    ]

    def print_document(self):
        """Print the cutting plan document."""
        self.ensure_one()
        return self.print_document_as_pdf()

    def print_document_as_pdf(self):
        """Generate and return the PDF document."""
        self.ensure_one()
        # Get the package to print
        package = self.package_id
        if not package:
            raise ValidationError("No package associated with this bar.")

        # Use the package's print method since bars are part of packages
        return package.print_document_as_pdf()
