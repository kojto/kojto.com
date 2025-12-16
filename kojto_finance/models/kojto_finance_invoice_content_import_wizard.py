from odoo import models, fields, api
from odoo.exceptions import UserError
import io
import csv
import re


class KojtoFinanceInvoiceContentImportWizard(models.TransientModel):
    _name = "kojto.finance.invoice.content.import.wizard"
    _description = "Import Invoice Content Wizard"

    invoice_id = fields.Many2one("kojto.finance.invoices", string="Invoice", required=True, default=lambda self: self.env.context.get('active_id'))
    data = fields.Text(string="Content Data", required=True, help="Paste data here (Position;Name;Quantity;Unit;Unit Price;VAT Rate;Subcode)")

    def _parse_number(self, value_str, field_name, row_num):
        """
        Parse a number string, handling:
        - Currency symbols (EUR, USD, YEN, JPY, RMB, CNY, BGN, etc.)
        - Comma separators (1,400.00)
        - Whitespace
        - Empty values (returns 0.0)

        Args:
            value_str: The string value to parse
            field_name: Name of the field (for error messages)
            row_num: Row number (for error messages)

        Returns:
            float: The parsed number

        Raises:
            UserError: If the value cannot be parsed as a number
        """
        if not value_str:
            return 0.0

        # Remove whitespace
        value_str = value_str.strip()

        if not value_str:
            return 0.0

        # Remove common currency symbols and codes (case-insensitive)
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

        # Remove any remaining non-digit, non-decimal, non-comma, non-minus characters
        # This removes any other currency symbols, spaces, and other characters
        value_str = re.sub(r'[^\d.,\-]', '', value_str)

        # Handle empty string after cleaning
        if not value_str or value_str == '-':
            return 0.0

        # Detect number format: European (comma as decimal) vs US/International (period as decimal)
        # European format: "1.400,00" (period = thousand, comma = decimal)
        # US format: "1,400.00" (comma = thousand, period = decimal)

        has_comma = ',' in value_str
        has_period = '.' in value_str

        if has_comma and has_period:
            # Both present - determine which is decimal separator based on position
            comma_pos = value_str.rfind(',')
            period_pos = value_str.rfind('.')

            if comma_pos > period_pos:
                # Comma comes after period - European format: "1.400,50"
                # Period is thousand separator, comma is decimal separator
                value_str = value_str.replace('.', '').replace(',', '.')
            else:
                # Period comes after comma - US format: "1,400.50"
                # Comma is thousand separator, period is decimal separator
                value_str = value_str.replace(',', '')
        elif has_comma and not has_period:
            # Only comma - check if it's likely a decimal separator
            comma_pos = value_str.rfind(',')
            after_comma = value_str[comma_pos + 1:]
            # If comma followed by 1-3 digits at the end, it's likely a decimal separator
            if after_comma and len(after_comma) <= 3 and after_comma.isdigit() and comma_pos > 0:
                # European decimal format: "1400,50" or "1 400,50"
                value_str = value_str.replace(',', '.')
            else:
                # Likely just a thousand separator: "1,400" -> "1400"
                value_str = value_str.replace(',', '')
        elif has_period and not has_comma:
            # Only period - check context
            period_pos = value_str.rfind('.')
            after_period = value_str[period_pos + 1:]
            # If period followed by 1-3 digits at end, likely decimal separator
            if after_period and len(after_period) <= 3 and after_period.isdigit() and period_pos > 0:
                # Likely decimal separator, keep as is: "1400.50"
                pass
            else:
                # Might be thousand separator: "1.400" -> "1400"
                value_str = value_str.replace('.', '')
        # If neither comma nor period, value_str is already numeric

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

    def _is_position_identifier(self, value):
        """Check if a value is a Position identifier (e.g., '01', '02a', '03b', '02_01', '02.01')."""
        if not value:
            return False
        value = value.strip()
        # Position pattern: starts with digits, optionally followed by underscores, dots, letters, and more digits
        # Matches: '01', '02a', '03b', '02_01', '02.01', '01_02_03', '02A', etc.
        return bool(re.match(r'^[\d]+([._a-zA-Z][\da-zA-Z._]*)?$', value))

    def _normalize_multiline_data(self, text, delimiter):
        """
        Merge continuation lines into the previous row.
        Lines that don't start with a Position identifier are merged into the previous row's Name field.
        """
        lines = text.split('\n')
        if not lines:
            return text

        normalized_lines = []

        for i, line in enumerate(lines):
            line = line.rstrip('\r')

            if not line.strip():
                # Skip completely empty lines
                continue

            # Split by delimiter to check first field
            parts = line.split(delimiter)
            first_field = parts[0].strip() if parts else ""

            # Header line (first line) or line starting with Position identifier = new row
            if i == 0 or self._is_position_identifier(first_field):
                normalized_lines.append(line)
            elif normalized_lines:
                # This is a continuation line - merge into previous row's Name field
                last_line = normalized_lines[-1]
                last_parts = last_line.split(delimiter)

                if len(last_parts) >= 2:
                    # Merge continuation text into Name field (index 1)
                    continuation_first = parts[0].strip() if parts else ""

                    # Add continuation to Name field, replacing multiple spaces/newlines with single space
                    current_name = last_parts[1].rstrip()
                    merged_name = (current_name + ' ' + continuation_first).strip()
                    # Replace multiple spaces/newlines with single space
                    merged_name = ' '.join(merged_name.split())
                    last_parts[1] = merged_name

                    # If continuation line has remaining columns, use them
                    if len(parts) > 1:
                        # Replace columns after Name with continuation columns
                        last_parts = last_parts[:2] + parts[1:]

                    normalized_lines[-1] = delimiter.join(last_parts)
                else:
                    # Fallback: append as continuation text
                    continuation_text = ' '.join(line.split())
                    normalized_lines[-1] = normalized_lines[-1].rstrip() + ' ' + continuation_text

        return '\n'.join(normalized_lines)

    def action_import(self):
        self.ensure_one()
        if not self.data:
            raise UserError("No data provided to import.")

        try:
            delimiter = self._detect_delimiter(self.data)

            # Normalize multiline data - merge continuation lines into previous rows
            normalized_data = self._normalize_multiline_data(self.data, delimiter)

            data_file = io.StringIO(normalized_data)
            reader = csv.reader(data_file, delimiter=delimiter)
            headers = next(reader)

            if not headers or len(headers) < 5:
                raise UserError(f"Invalid data format. Expected headers: Position{delimiter}Name{delimiter}Quantity{delimiter}Unit{delimiter}Unit Price{delimiter}VAT Rate{delimiter}Subcode")

            # Delete all existing content for this invoice
            self.invoice_id.content.unlink()

            new_content_vals = []
            for row_num, row in enumerate(reader, start=2):  # Start from 2 because we skipped header
                if len(row) < 5:
                    raise UserError(f"Invalid row format at line {row_num}: '{delimiter.join(row)}'. Expected at least 5 columns.")

                # Parse columns - fixed order: Position, Name, Quantity, Unit, Unit Price, VAT Rate, Subcode
                position = row[0].strip() if len(row) > 0 else ""
                name = row[1].strip() if len(row) > 1 else ""
                quantity_str = row[2].strip() if len(row) > 2 else ""
                unit_name = row[3].strip() if len(row) > 3 else ""
                unit_price_str = row[4].strip() if len(row) > 4 else ""
                vat_rate_str = row[5].strip() if len(row) > 5 else ""
                subcode_name = row[6].strip() if len(row) > 6 else ""

                # Parse numeric values with improved error messages
                quantity = self._parse_number(quantity_str, "Quantity", row_num)
                unit_price = self._parse_number(unit_price_str, "Unit Price", row_num)
                vat_rate = self._parse_number(vat_rate_str, "VAT Rate", row_num)

                # Find unit by name if provided (unit is optional)
                unit_id = False
                if unit_name and unit_name.strip():
                    unit = self.env["kojto.base.units"].search([("name", "=", unit_name.strip())], limit=1)
                    if unit:
                        unit_id = unit.id
                    else:
                        raise UserError(
                            f"Unit '{unit_name}' not found in the system at row {row_num}. "
                            f"Please check that the unit name is correct and exists in the system."
                        )

                # Find subcode by name if provided, otherwise use invoice's subcode
                subcode_id = False
                if subcode_name and subcode_name.strip():
                    subcode = self.env["kojto.commission.subcodes"].search([("name", "=", subcode_name.strip())], limit=1)
                    if subcode:
                        subcode_id = subcode.id
                    else:
                        raise UserError(f"Subcode '{subcode_name}' not found in the system at row {row_num}.")
                else:
                    # If no subcode provided in import, use the invoice's subcode
                    if self.invoice_id.subcode_id:
                        subcode_id = self.invoice_id.subcode_id.id

                # Clean up name: replace any remaining newlines with spaces
                cleaned_name = name.strip() if name else ""
                cleaned_name = ' '.join(cleaned_name.split())  # Replace all whitespace with single spaces

                content_vals = {
                    "invoice_id": self.invoice_id.id,
                    "position": position or False,
                    "name": cleaned_name or False,
                    "quantity": quantity,
                    "unit_id": unit_id,
                    "unit_price": unit_price,
                    "vat_rate": vat_rate,
                    "subcode_id": subcode_id,
                    "vat_treatment_id": self.invoice_id.invoice_vat_treatment_id.id if self.invoice_id.invoice_vat_treatment_id else False,
                }
                new_content_vals.append(content_vals)

            if new_content_vals:
                # Create all content records
                created_contents = self.env["kojto.finance.invoice.contents"].create(new_content_vals)

                # Recompute invoice content computed fields
                for content in created_contents:
                    content._compute_pre_vat_total()

                # Recompute dependent fields on content records
                created_contents._compute_vat_total()
                created_contents._compute_total_price()
                created_contents._compute_redistribution_is_valid()
                created_contents._compute_value_in_bgn()
                created_contents._compute_value_in_eur()

                # Recompute invoice-level computed fields that depend on content
                # Must reload invoice to get fresh content records
                self.invoice_id.invalidate_recordset(['content'])
                self.invoice_id._compute_all_totals()
                self.invoice_id._compute_invoice_has_invalid_redistribution()
                self.invoice_id._compute_payable_amount()
                self.invoice_id._compute_total_price_base_currency()
                self.invoice_id._compute_open_amount()

            return {"type": "ir.actions.act_window_close"}

        except Exception as e:
            raise UserError(f"Error importing invoice content: {str(e)}")
