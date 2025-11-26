# kojto_finance/models/kojto_finance_accounting_ops.py
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class KojtoFinanceAccountingOps(models.Model):
    _name = "kojto.finance.accounting.ops"
    _description = "Kojto Finance Accounting Operations"
    _order = "row_number asc"
    _rec_name = "name"

    name = fields.Char(string="Name", compute="_compute_name", store=True)
    row_number = fields.Integer(string="№", default=1, required=True)

    template_id = fields.Many2one("kojto.finance.accounting.templates", string="Template", ondelete="cascade")
    debit_account_id = fields.Many2one("kojto.finance.accounting.accounts", string="Debit", required=True)
    credit_account_id = fields.Many2one("kojto.finance.accounting.accounts", string="Credit", required=True)

    acc_operation_type = fields.Char(string="Accounting Operation Type", required=True, default="ОПДДС")
    acc_operation = fields.Char(string="Accounting Operation", required=True, default="201")

    @api.depends("debit_account_id", "credit_account_id", "row_number")  # Add row_number as a dependency
    def _compute_name(self):
        for record in self:
            row_number = record.row_number or "N/A"
            debit_number = record.debit_account_id.account_number or "N/A"
            credit_number = record.credit_account_id.account_number or "N/A"
            record.name = f"pos {row_number}, debit {debit_number}, credit {credit_number}"
            return {}

    @api.constrains("template_id", "row_number")
    def _check_unique_row_number_per_template(self):
        for record in self:
            if record.template_id and record.row_number:
                existing_count = self.search_count(
                    [
                        ("template_id", "=", record.template_id.id),
                        ("row_number", "=", record.row_number),
                        ("id", "!=", record.id),  # Exclude the current record
                    ]
                )
                if existing_count > 0:
                    raise ValidationError(f"Row number {record.row_number} already exists for template " f"'{record.template_id.name}'. Row numbers must be unique per template!")

    def delete_acc_ops(self):
        self.ensure_one()
        self.unlink()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Accounting Operations',
            'res_model': 'kojto.finance.accounting.ops',
            'view_mode': 'list',
            'target': 'new',
        }
