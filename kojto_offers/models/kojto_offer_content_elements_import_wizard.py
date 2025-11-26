# Create a new file models/kojto_offer_content_elements_import_wizard.py
from odoo import models, fields
from odoo.exceptions import UserError
import io
import csv

class KojtoOfferContentElementsImportWizard(models.TransientModel):
    _name = "kojto.offer.content.elements.import.wizard"
    _description = "Import Offer Content Elements Wizard"

    offer_id = fields.Many2one("kojto.offers", string="Offer", required=True, default=lambda self: self.env.context.get('active_id'))
    data = fields.Text(string="Content Elements Data", required=True, help="Paste data here (Content Position\tPosition\tName\tConsolidation\tQuantity\tUnit Price)")

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
        except UserError:
            raise

        data_io = io.StringIO(self.data)
        reader = csv.reader(data_io, delimiter=delimiter)
        lines = list(reader)

        if not lines:
            raise UserError("No data lines to import.")

        # Check if first line is header
        first_line = lines[0]
        is_header = (
            len(first_line) >= 6 and
            first_line[0].strip().lower() == "content position" and
            first_line[1].strip().lower() == "position" and
            first_line[2].strip().lower() == "name" and
            first_line[3].strip().lower() == "consolidation" and
            first_line[4].strip().lower() == "quantity" and
            first_line[5].strip().lower() == "unit price"
        )

        data_lines = lines[1:] if is_header else lines

        for line in data_lines:
            if len(line) < 6:
                raise UserError(f"Invalid line format: {delimiter.join(line)}. Expected at least 6 columns.")

            content_pos = line[0].strip()
            element_pos = line[1].strip()
            name = line[2].strip()
            consolidation_name = line[3].strip()
            try:
                quantity = float(line[4].strip())
            except ValueError:
                raise UserError(f"Invalid quantity value: {line[4]}")
            try:
                unit_price = float(line[5].strip())
            except ValueError:
                raise UserError(f"Invalid unit price value: {line[5]}")

            # Find content by position
            content = self.offer_id.content.filtered(lambda c: c.position == content_pos)
            if not content:
                raise UserError(f"Content with position '{content_pos}' not found.")

            # Find consolidation by name
            consolidation = self.env['kojto.offer.consolidation.ids'].search([('name', '=', consolidation_name)], limit=1)
            if not consolidation:
                raise UserError(f"Consolidation '{consolidation_name}' not found.")

            # Check if element exists by position in this content
            element = content.content_elements.filtered(lambda e: e.position == element_pos)
            vals = {
                'name': name,
                'consolidation_id': consolidation.id,
                'quantity': quantity,
                'unit_price': unit_price,
            }
            if element:
                element.write(vals)
            else:
                vals['content_id'] = content.id
                vals['position'] = element_pos
                self.env['kojto.offer.content.elements'].create(vals)

        return {
            'type': 'ir.actions.act_window_close'
        }
