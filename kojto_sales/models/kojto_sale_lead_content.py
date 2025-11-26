from odoo import models, fields, api
import re

class KojtoSaleLeadContent(models.Model):
    _name = "kojto.sale.lead.content"
    _description = "Kojto Sale Lead Content"
    _rec_name = "description"

    # Fields
    position = fields.Char(string="#", required=True, readonly=True, default=lambda self: self.generate_next_consecutive_position())
    description = fields.Char(string="Description", required=True)
    type = fields.Selection(
        [
            ("inquiry", "Inquiry"),
            ("offer", "Offer"),
            ("contract", "Contract"),
            ("call", "Call"),
            ("email", "Email"),
            ("other", "Other"),
        ],
        string="Type",
        default="inquiry",
    )
    sale_lead_id = fields.Many2one("kojto.sale.leads", string="Sale Lead", required=True, ondelete="cascade")
    date_start = fields.Date(string="Start Date", default=fields.Date.today, required=True)

    @api.model
    def create(self, vals):
        # Handle both single dict and list of dicts (batch create)
        if isinstance(vals, dict):
            if 'type' not in vals or not vals['type']:
                vals['type'] = 'inquiry'
            return super().create(vals)
        elif isinstance(vals, list):
            for v in vals:
                if 'type' not in v or not v['type']:
                    v['type'] = 'inquiry'
            return super().create(vals)
        return super().create(vals)

    def write(self, vals):
        # Ensure type field has a valid value when updating
        if 'type' in vals and not vals['type']:
            vals['type'] = 'inquiry'
        return super().write(vals)

    @api.model
    def generate_next_consecutive_position(self):
        try:
            # Search for the highest position value
            largest_position = self.env["kojto.sale.lead.content"].search(
                [("position", "!=", False)], order="position desc", limit=1
            )
            if largest_position and largest_position.position:
                numeric_part_match = re.search(r"\d+$", largest_position.position)
                if numeric_part_match:
                    next_consecutive_position = int(numeric_part_match.group()) + 1
                else:
                    next_consecutive_position = 1  # Fallback if position isn't numeric
            else:
                next_consecutive_position = 1  # No valid records found
            return str(next_consecutive_position).zfill(3)
        except Exception as e:
            raise ValueError(f"Failed to generate next position: {str(e)}")
