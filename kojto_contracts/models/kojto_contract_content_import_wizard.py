from odoo import models, fields
from odoo.exceptions import UserError
import io
import csv
import re


class KojtoContractContentImportWizard(models.TransientModel):
    _name = "kojto.contract.content.import.wizard"
    _description = "Import Contract Content Wizard"

    contract_id = fields.Many2one("kojto.contracts", string="Contract", required=True, default=lambda self: self.env.context.get('active_id'))
    data = fields.Text(string="Content Data", required=True, help="Paste data here (Position;Name;Quantity;Unit;Unit Price;VAT Rate)")

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
            data_file = io.StringIO(self.data)
            reader = csv.reader(data_file, delimiter=delimiter)
            headers = next(reader)

            if not headers or len(headers) < 5:
                raise UserError(f"Invalid data format. Expected headers: Position{delimiter}Name{delimiter}Quantity{delimiter}Unit{delimiter}Unit Price{delimiter}VAT Rate")

            # Check if we have 6 columns (with VAT Rate) or 5 columns (without VAT Rate)
            has_vat_rate = len(headers) >= 6

            # Delete all existing content for this contract
            self.contract_id.content.unlink()

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

                quantity = self._parse_number(quantity_str, "Quantity", row_num)
                unit_price = self._parse_number(unit_price_str, "Unit Price", row_num)
                vat_rate = self._parse_number(vat_rate_str, "VAT Rate", row_num)

                if not unit_name or not unit_name.strip():
                    raise UserError(f"Unit is required at row {row_num}. Please provide a valid unit name.")

                unit = self.env["kojto.base.units"].search([("name", "=", unit_name.strip())], limit=1)
                if not unit:
                    raise UserError(
                        f"Unit '{unit_name}' not found in the system at row {row_num}. "
                        f"Please check that the unit name is correct and exists in the system."
                    )

                content_vals = {
                    "contract_id": self.contract_id.id,
                    "position": position.strip() or False,
                    "name": name.strip() or False,
                    "quantity": quantity,
                    "unit_id": unit.id,
                    "unit_price": unit_price,
                    "vat_rate": vat_rate,
                }
                new_content_vals.append(content_vals)

            if new_content_vals:
                created_contents = self.env["kojto.contract.contents"].create(new_content_vals)

                # Recompute contract content computed fields
                created_contents._compute_pre_vat_total()
                created_contents.compute_vat_total()
                created_contents.compute_total_price()

                # Recompute contract-level computed fields that depend on content
                self.contract_id.invalidate_recordset(['content'])
                self.contract_id.compute_all_totals()

            return {"type": "ir.actions.act_window_close"}

        except Exception as e:
            raise UserError(f"Error importing contract content: {str(e)}")
