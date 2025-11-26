from odoo import models, fields, api
from odoo.exceptions import UserError
import io
import csv


class KojtoOfferContentImportWizard(models.TransientModel):
    _name = "kojto.offer.content.import.wizard"
    _description = "Import Offer Content Wizard"

    offer_id = fields.Many2one("kojto.offers", string="Offer", required=True, default=lambda self: self.env.context.get('active_id'))
    data = fields.Text(string="Content Data", required=True, help="Paste data here (Position;Name;Quantity;Unit;Unit Price;VAT Rate)")

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
                raise UserError(f"Invalid data format. Expected headers: Position{delimiter}Name{delimiter}Quantity{delimiter}Unit{delimiter}Unit Price{delimiter}VAT Rate")

            # Check if we have 6 columns (with VAT Rate) or 5 columns (without VAT Rate)
            has_vat_rate = len(headers) >= 6

            # Delete all existing content for this offer
            self.offer_id.content.unlink()

            new_content_vals = []
            for row_num, row in enumerate(reader, start=2):  # Start from 2 because we skipped header
                if len(row) < 5:
                    raise UserError(f"Invalid row format at line {row_num}: '{delimiter.join(row)}'. Expected at least 5 columns.")

                # Handle both 5 and 6 column formats
                if has_vat_rate and len(row) >= 6:
                    position, name, quantity_str, unit_name, unit_price_str, vat_rate_str = row
                else:
                    position, name, quantity_str, unit_name, unit_price_str = row
                    vat_rate_str = "0"

                try:
                    quantity = float(quantity_str.strip() or 0.0)
                    unit_price = float(unit_price_str.strip() or 0.0)
                    vat_rate = float(vat_rate_str.strip() or 0.0)
                except ValueError:
                    raise UserError(f"Invalid numeric value in row {row_num}: '{delimiter.join(row)}'. Quantity, Unit Price, and VAT Rate must be numbers.")

                # Find unit by name
                unit = self.env["kojto.base.units"].search([("name", "=", unit_name.strip())], limit=1)
                if not unit:
                    raise UserError(f"Unit '{unit_name}' not found in the system at row {row_num}.")

                content_vals = {
                    "offer_id": self.offer_id.id,
                    "position": position.strip() or False,
                    "name": name.strip() or False,
                    "quantity": quantity,
                    "unit_id": unit.id,
                    "unit_price": unit_price,
                    "vat_rate": vat_rate,
                }
                new_content_vals.append(content_vals)

            if new_content_vals:
                self.env["kojto.offer.contents"].create(new_content_vals)

            return {"type": "ir.actions.act_window_close"}

        except Exception as e:
            raise UserError(f"Error importing offer content: {str(e)}")
