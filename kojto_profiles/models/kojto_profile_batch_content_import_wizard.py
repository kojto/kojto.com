from odoo import models, fields, api
from odoo.exceptions import UserError
import io
import csv

class KojtoProfileBatchContentImportWizard(models.Model):
    _name = "kojto.profile.batch.content.import.wizard"
    _description = "Import Wizard for Kojto Profile Batch Content"

    package_id = fields.Many2one("kojto.profile.batches", string="Batch", required=True)
    data = fields.Text(string="Import Content Data", required=True)

    def _detect_delimiter(self, text):
        first_line = text.split('\n')[0]
        if '\t' in first_line:
            return '\t'
        elif ',' in first_line:
            return ','
        elif ';' in first_line:
            return ';'
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
                raise UserError(f"Invalid data format. Expected headers: Position{delimiter}Profile{delimiter}Length{delimiter}Quantity{delimiter}LengthExtension{delimiter}Description")

            # Check if we have 6 columns (with description) or 5 columns (without description)
            has_description = len(headers) >= 6

            # Delete all existing content for this batch
            self.package_id.batch_content_ids.unlink()

            new_content_vals = []
            for row in reader:
                if len(row) < 5:
                    raise UserError(f"Invalid row format: '{delimiter.join(row)}'. Expected at least 5 columns.")

                # Handle both 5 and 6 column formats
                if has_description and len(row) >= 6:
                    position, profile_name, length_str, quantity_str, length_extension_str, description = row
                else:
                    position, profile_name, length_str, quantity_str, length_extension_str = row
                    description = ""

                try:
                    length = float(length_str.strip() or 0.0)
                    quantity = float(quantity_str.strip() or 0.0)
                    length_extension = float(length_extension_str.strip() or 0.0)
                except ValueError:
                    raise UserError(f"Invalid numeric value in row: '{delimiter.join(row)}'. Length, Quantity, and LengthExtension must be numbers.")
                profile = self.env["kojto.profiles"].search([("name", "=", profile_name.strip())], limit=1)
                if not profile:
                    raise UserError(f"Profile '{profile_name}' not found in the system.")
                content_vals = {
                    "batch_id": self.package_id.id,
                    "position": position.strip() or False,
                    "profile_id": profile.id,
                    "description": description.strip() or False,
                    "length": length,
                    "quantity": quantity,
                    "length_extension": length_extension,
                }
                new_content_vals.append(content_vals)
            if new_content_vals:
                self.env["kojto.profile.batch.content"].create(new_content_vals)
            return {"type": "ir.actions.act_window_close"}
        except Exception as e:
            raise UserError(f"Error importing batch content: {str(e)}")
