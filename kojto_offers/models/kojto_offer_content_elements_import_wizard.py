# Create a new file models/kojto_offer_content_elements_import_wizard.py
from odoo import models, fields
from odoo.exceptions import UserError
import io
import csv
import re

class KojtoOfferContentElementsImportWizard(models.TransientModel):
    _name = "kojto.offer.content.elements.import.wizard"
    _description = "Import Offer Content Elements Wizard"

    offer_id = fields.Many2one("kojto.offers", string="Offer", required=True, default=lambda self: self.env.context.get('active_id'))
    data = fields.Text(string="Content Elements Data", required=True, help="Paste data here (Content Position\tPosition\tName\tConsolidation\tQuantity\tUnit Price)")

    def _parse_number(self, value_str, field_name, row_num):
        """Parse a number string, handling currency symbols and comma separators."""
        if not value_str:
            return 0.0
        value_str = value_str.strip()
        if not value_str:
            return 0.0
        # Remove currency codes first (with word boundaries for text codes)
        currency_codes = [
            r'\bEUR\b', r'\bEURO\b', r'\bEUROS\b',
            r'\bUSD\b', r'\bUS\s*DOLLAR\b',
            r'\bYEN\b', r'\bJPY\b',
            r'\bRMB\b', r'\bCNY\b',
            r'\bBGN\b', r'\bLEV\b', r'\bLEVA\b',
            r'\bGBP\b', r'\bPOUND\b',
            r'\bCHF\b', r'\bFRANC\b',
            r'\bRUB\b', r'\bRUBLE\b',
        ]
        for pattern in currency_codes:
            value_str = re.sub(pattern, '', value_str, flags=re.IGNORECASE)

        # Remove currency symbols (without word boundaries, as symbols aren't word characters)
        currency_symbols = [r'€', r'\$', r'¥', r'£', r'₽', r'元', r'円', r'лв']
        for symbol in currency_symbols:
            value_str = re.sub(symbol, '', value_str)

        value_str = re.sub(r'[^\d.,\-]', '', value_str)
        if not value_str or value_str == '-':
            return 0.0

        # Detect number format: European (comma as decimal) vs US/International (period as decimal)
        has_comma = ',' in value_str
        has_period = '.' in value_str

        if has_comma and has_period:
            comma_pos = value_str.rfind(',')
            period_pos = value_str.rfind('.')
            if comma_pos > period_pos:
                value_str = value_str.replace('.', '').replace(',', '.')
            else:
                value_str = value_str.replace(',', '')
        elif has_comma and not has_period:
            comma_pos = value_str.rfind(',')
            after_comma = value_str[comma_pos + 1:]
            if after_comma and len(after_comma) <= 3 and after_comma.isdigit() and comma_pos > 0:
                value_str = value_str.replace(',', '.')
            else:
                value_str = value_str.replace(',', '')
        elif has_period and not has_comma:
            period_pos = value_str.rfind('.')
            after_period = value_str[period_pos + 1:]
            if not (after_period and len(after_period) <= 3 and after_period.isdigit() and period_pos > 0):
                value_str = value_str.replace('.', '')

        try:
            return float(value_str)
        except ValueError:
            raise UserError(
                f"Invalid {field_name} value at row {row_num}. "
                f"Supports US format (e.g., '1,400.00') and European format (e.g., '1.400,00' or '1 400,50'). "
                f"Currency symbols are automatically removed."
            )

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

        for row_num, line in enumerate(data_lines, start=(2 if is_header else 1)):
            if len(line) < 6:
                raise UserError(
                    f"Invalid line format at row {row_num}: '{delimiter.join(line)}'. "
                    f"Expected at least 6 columns (Content Position, Position, Name, Consolidation, Quantity, Unit Price)."
                )

            content_pos = line[0].strip()
            element_pos = line[1].strip()
            name = line[2].strip()
            consolidation_name = line[3].strip()

            quantity = self._parse_number(line[4].strip() if len(line) > 4 else "", "Quantity", row_num)
            unit_price = self._parse_number(line[5].strip() if len(line) > 5 else "", "Unit Price", row_num)

            # Find content by position
            content = self.offer_id.content.filtered(lambda c: c.position == content_pos)
            if not content:
                raise UserError(
                    f"Content with position '{content_pos}' not found at row {row_num}. "
                    f"Please check that the content position exists in the offer."
                )

            # Find consolidation by name
            if not consolidation_name or not consolidation_name.strip():
                raise UserError(f"Consolidation is required at row {row_num}. Please provide a valid consolidation name.")

            consolidation = self.env['kojto.offer.consolidation.ids'].search([('name', '=', consolidation_name.strip())], limit=1)
            if not consolidation:
                raise UserError(
                    f"Consolidation '{consolidation_name}' not found at row {row_num}. "
                    f"Please check that the consolidation name is correct and exists in the system."
                )

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
