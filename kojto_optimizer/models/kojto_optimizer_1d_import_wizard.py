from odoo import fields, models
from odoo.exceptions import ValidationError


class KojtoOptimizer1DImportWizard(models.TransientModel):
    _name = "kojto.optimizer.1d.import.wizard"
    _description = "Import Wizard for Kojto Optimizer 1D"

    package_id = fields.Many2one("kojto.optimizer.1d.packages", string="Package", required=True)
    import_type = fields.Selection([("stock", "Stock"), ("bars", "Bars")], string="Import Type", required=True)
    data = fields.Text(string="Import Data")

    def action_import(self):
        self.ensure_one()
        package = self.package_id
        lines = [line.strip() for line in self.data.strip().split("\n") if line.strip()]
        if not lines:
            raise ValidationError("No valid data provided.")

        # Expect 4 columns for both stock and bars
        expected_columns = 4
        header = lines[0].split("\t")
        expected_header = ["Position", "Description", "Length", "Quantity"]
        start_idx = 1 if header == expected_header else 0
        if len(lines) <= start_idx:
            raise ValidationError("No valid data rows provided.")

        records = []
        positions = set()
        for line in lines[start_idx:]:
            if "\t" in line:
                parts = line.split("\t")
            elif ";" in line:
                parts = line.split(";")
            elif "," in line:
                parts = line.split(",")
            else:
                raise ValidationError(f"Invalid row format (no valid separator found): {line}")

            if len(parts) != expected_columns:
                raise ValidationError(f"Invalid row format (must have {expected_columns} columns): {line}")

            position, description, length, quantity = parts
            # Validate position
            position = position.strip()
            if not position:
                raise ValidationError(f"Position cannot be empty in row: {line}")
            if position in positions:
                raise ValidationError(f"Duplicate position '{position}' in import data.")
            positions.add(position)

            try:
                length = float(length.strip())
                quantity = int(quantity.strip())
            except ValueError:
                raise ValidationError(f"Invalid number format in row: {line}")

            records.append((position, description.strip(), length, quantity))

        if self.import_type == "stock":
            package.stock_ids.unlink()
            package.stock_ids = [
                (
                    0,
                    0,
                    {
                        "stock_position": position,
                        "stock_description": desc,
                        "stock_length": length,
                        "available_stock_pieces": quantity,
                    },
                )
                for position, desc, length, quantity in records
            ]
        else:
            package.bar_ids.unlink()
            package.bar_ids = [
                (
                    0,
                    0,
                    {
                        "bar_position": position,
                        "bar_description": desc,
                        "bar_length": length,
                        "required_bar_pieces": quantity,
                    },
                )
                for position, desc, length, quantity in records
            ]
        return {"type": "ir.actions.act_window_close"}
