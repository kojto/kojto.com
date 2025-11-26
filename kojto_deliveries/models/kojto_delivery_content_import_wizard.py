from odoo import models, fields
from odoo.exceptions import UserError
import io
import csv


class KojtoDeliveryContentImportWizard(models.TransientModel):
    _name = "kojto.delivery.content.import.wizard"
    _description = "Import Delivery Content Wizard"

    delivery_id = fields.Many2one("kojto.deliveries", string="Delivery", required=True, default=lambda self: self.env.context.get('active_id'))
    data = fields.Text(string="Content Data", required=True, help="Paste data here (Position;Name;Quantity;Unit;Unit Weight)")

    def _detect_delimiter(self, text):
        """Detect the delimiter used in the text data."""
        first_line = text.strip().split('\n')[0] if text.strip() else ""

        if '\t' in first_line:
            return '\t'
        elif ';' in first_line:
            return ';'
        elif ',' in first_line:
            return ','
        else:
            raise UserError("Unable to detect delimiter. Please use tab, comma, or semicolon as separators.")

    def action_import(self):
        self.ensure_one()
        if not self.data:
            raise UserError("No data provided to import.")

        try:
            delimiter = self._detect_delimiter(self.data)
            data_file = io.StringIO(self.data)
            reader = csv.reader(data_file, delimiter=delimiter)
            headers = next(reader)

            if not headers or len(headers) < 5:
                raise UserError(f"Invalid data format. Expected headers: Position{delimiter}Name{delimiter}Quantity{delimiter}Unit{delimiter}Unit Weight")

            # Delete all existing content for this delivery
            self.delivery_id.content.unlink()

            new_content_vals = []
            for row_num, row in enumerate(reader, start=2):  # Start from 2 because we skipped header
                if len(row) < 5:
                    raise UserError(f"Invalid row format at line {row_num}: '{delimiter.join(row)}'. Expected at least 5 columns.")

                position, name, quantity_str, unit_name, unit_weight_str = row

                try:
                    quantity = float(quantity_str.strip() or 0.0)
                    unit_weight = float(unit_weight_str.strip() or 0.0)
                except ValueError:
                    raise UserError(f"Invalid numeric value in row {row_num}: '{delimiter.join(row)}'. Quantity and Unit Weight must be numbers.")

                # Find unit by name
                unit = self.env["kojto.base.units"].search([("name", "=", unit_name.strip())], limit=1)
                if not unit:
                    raise UserError(f"Unit '{unit_name}' not found in the system at row {row_num}.")

                content_vals = {
                    "delivery_id": self.delivery_id.id,
                    "position": position.strip() or False,
                    "name": name.strip() or False,
                    "quantity": quantity,
                    "unit_id": unit.id,
                    "unit_weight": unit_weight,
                }
                new_content_vals.append(content_vals)

            if new_content_vals:
                self.env["kojto.delivery.contents"].create(new_content_vals)

            return {"type": "ir.actions.act_window_close"}

        except Exception as e:
            raise UserError(f"Error importing delivery content: {str(e)}")
