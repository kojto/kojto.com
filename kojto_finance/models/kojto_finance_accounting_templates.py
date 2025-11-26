# kojto_finance/models/kojto_finance_accounting_templates.py
from odoo import models, fields, api


class KojtoFinanceAccountingTemplates(models.Model):  # счетоводни макети
    _name = "kojto.finance.accounting.templates"
    _description = "Kojto Finance Accounting Templates"
    _rec_name = "name"
    _order = "name desc"

    name = fields.Char("Name", required=True)
    description = fields.Char("Description")

    template_type_id = fields.Many2one("kojto.finance.accounting.types", string="Template Type", required=True)
    primary_type = fields.Selection(related="template_type_id.primary_type", string="Primary Type", readonly=True)

    requires_subtype_id = fields.Boolean(string="Requires Subtype", compute="_compute_requires_extra_info", default=False)
    requires_identifier_id = fields.Boolean(string="Requires Identifier", compute="_compute_requires_extra_info", default=False)
    requires_ref_number = fields.Boolean(string="Requires Ref Number", compute="_compute_requires_extra_info", default=False)

    accounting_ops_ids = fields.Many2many("kojto.finance.accounting.ops", relation="kojto_finance_accounting_templates_ops_rel", string="Accounting Operations")

    @api.depends("accounting_ops_ids")
    def _compute_requires_extra_info(self):
        for record in self:
            record.requires_subtype_id = any(map(lambda x: x.debit_account_id.is_catalogue_account or x.credit_account_id.is_catalogue_account, record.accounting_ops_ids))
            record.requires_identifier_id = any(map(lambda x: x.debit_account_id.is_warehouse_account or x.credit_account_id.is_warehouse_account, record.accounting_ops_ids))
            record.requires_ref_number = any(map(lambda x: x.debit_account_id.is_ref_number_account or x.credit_account_id.is_ref_number_account, record.accounting_ops_ids))
