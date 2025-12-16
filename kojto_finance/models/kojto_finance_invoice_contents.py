import re

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

from .kojto_finance_vat_treatment import VAT_RATES_BY_TYPE
from ..utils.invoice_auto_accounting import auto_accounting_for_content

class KojtoFinanceInvoiceContents(models.Model):
    _name = "kojto.finance.invoice.contents"
    _description = "Kojto Finance Invoice Contents"
    _rec_name = "name"
    _order = "position asc, id asc"

    name = fields.Text(string="Description", size=200)
    name_translation = fields.Text(string="Description Translation", size=200)
    position = fields.Char(string="№", size=5, required=True)



    invoice_id = fields.Many2one("kojto.finance.invoices", string="Invoice Reference", required=True, ondelete="cascade", index=True)
    currency_id = fields.Many2one("res.currency", string="", related="invoice_id.currency_id", readonly=True)
    quantity = fields.Float(string="Quantity", digits=(16, 3), required=True)
    unit_id = fields.Many2one("kojto.base.units", string="Unit")
    unit_price = fields.Float(string="Unit Price", digits=(16, 2))
    pre_vat_total = fields.Float(string="Pre VAT total", digits=(9, 2))
    vat_rate = fields.Float(string="VAT Rate (%)", digits=(9, 2), default=lambda self: self.invoice_id.invoice_vat_rate)
    vat_treatment_id = fields.Many2one("kojto.finance.vat.treatment", string="VAT Treatment", required=True, default=lambda self: self._default_vat_treatment())
    custom_vat = fields.Float(string="Custom Vat", digits=(9, 2), default=None)
    vat_total = fields.Float(string="VAT", compute="_compute_vat_total", digits=(9, 2))
    total_price = fields.Float(string="Total price", compute="_compute_total_price", digits=(9, 2))

    subcode_id = fields.Many2one("kojto.commission.subcodes", string="Subcode", default=lambda self: self.invoice_id.subcode_id)
    accounting_template_id = fields.Many2one("kojto.finance.accounting.templates", string="Accounting Template")
    accounting_template_domain = fields.Char(string="Accounting Template Domain", compute="_compute_accounting_template_domain", store=False)

    is_redistribution = fields.Boolean(string="Is Redistribution", default=False)
    redistribution_is_valid = fields.Boolean(string="Valid", compute="_compute_redistribution_is_valid")

    identifier_id = fields.Many2one("kojto.finance.accounting.identifiers", string="Identifier ID", domain="[('active', '=', True)]")

    subtype_id = fields.Many2one("kojto.finance.accounting.subtypes", string="Subtype ID")
    subtype_domain = fields.Char(string="Subtype Domain", compute="_compute_subtype_domain")

    requires_identifier_id = fields.Boolean(related="accounting_template_id.requires_identifier_id")
    requires_subtype_id = fields.Boolean(related="accounting_template_id.requires_subtype_id")

    exchange_rate_to_bgn = fields.Float(string="Exchange Rate to BGN", related="invoice_id.exchange_rate_to_bgn", digits=(9, 5))
    exchange_rate_to_eur = fields.Float(string="Exchange Rate to EUR", related="invoice_id.exchange_rate_to_eur", digits=(9, 5))
    value_in_bgn = fields.Float(string="Value in BGN", digits=(16, 2), compute="_compute_value_in_bgn")
    value_in_eur = fields.Float(string="Value in EUR", digits=(16, 2), compute="_compute_value_in_eur")

    @api.depends("pre_vat_total", "exchange_rate_to_bgn")
    def _compute_value_in_bgn(self):
        for record in self:
            record.value_in_bgn = record.pre_vat_total * record.exchange_rate_to_bgn
        return {}

    @api.depends("pre_vat_total", "exchange_rate_to_eur")
    def _compute_value_in_eur(self):
        for record in self:
            record.value_in_eur = record.pre_vat_total * record.exchange_rate_to_eur
        return {}

    @api.model
    def _default_vat_treatment(self):
        if not self.invoice_id:
            return False
        return self.invoice_id.invoice_vat_treatment_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('invoice_id'):
                invoice = self.env['kojto.finance.invoices'].browse(vals['invoice_id'])
                if not vals.get('vat_rate'):
                    vals['vat_rate'] = invoice.invoice_vat_rate
                if not vals.get('vat_treatment_id'):
                    vals['vat_treatment_id'] = invoice.invoice_vat_treatment_id.id

            # Clear dependent fields if template is not set
            if not vals.get('accounting_template_id'):
                vals['subtype_id'] = False
                vals['identifier_id'] = False
        return super().create(vals_list)

    def write(self, vals):
        """Override write to ensure dependent fields are cleared when template is removed"""
        # If accounting_template_id is being set to False/None, clear dependent fields
        if 'accounting_template_id' in vals and not vals['accounting_template_id']:
            vals['subtype_id'] = False
            vals['identifier_id'] = False

        # If template is being changed, check if we need to clear dependent fields
        elif 'accounting_template_id' in vals and vals['accounting_template_id']:
            new_template = self.env['kojto.finance.accounting.templates'].browse(vals['accounting_template_id'])

            # Clear identifier if new template doesn't require it
            if not new_template.requires_identifier_id:
                vals['identifier_id'] = False

            # Clear subtype if new template doesn't require it
            if not new_template.requires_subtype_id:
                vals['subtype_id'] = False

        return super().write(vals)

    @api.depends("invoice_id.document_in_out_type")
    def _compute_accounting_template_domain(self):
        for record in self:
            if not record.invoice_id:
                record.accounting_template_domain = "[]"
                continue

            # Map document_in_out_type to primary_type
            primary_type = "purchase" if record.invoice_id.document_in_out_type == "incoming" else "sale"
            record.accounting_template_domain = f"[('template_type_id.primary_type', '=', '{primary_type}')]"
        return {}

    @api.depends("accounting_template_id")
    def _compute_requires_subtype_id(self):
        for record in self:
            record.requires_subtype_id = record.accounting_template_id.requires_subtype_id if record.accounting_template_id else False
        return {}

    @api.depends("accounting_template_id")
    def _compute_subtype_domain(self):
        for record in self:
            if not record.accounting_template_id:
                record.subtype_domain = "[]"
                continue

            record.subtype_domain = f"[('template_type_ids', 'in', {record.accounting_template_id.template_type_id.id})]"
        return {}

    @api.depends("accounting_template_id")
    def _compute_requires_identifier_id(self):
        for record in self:
            record.requires_identifier_id = record.accounting_template_id.requires_identifier_id if record.accounting_template_id else False
        return {}

    @api.onchange("invoice_id")
    def onchange_invoice_id(self):
        if self.invoice_id:
            self.subcode_id = self.invoice_id.subcode_id
            self.vat_rate = self.invoice_id.invoice_vat_rate
            self.vat_treatment_id = self.invoice_id.invoice_vat_treatment_id

    @api.onchange("vat_treatment_id")
    def onchange_vat_treatment_id(self):
        self.vat_rate = 0.0
        if self.vat_treatment_id and VAT_RATES_BY_TYPE:
            self.vat_rate = VAT_RATES_BY_TYPE.get(self.vat_treatment_id.vat_treatment_type, 0)

    @api.onchange("accounting_template_id")
    def onchange_accounting_template_id(self):
        """Clear dependent fields when accounting template is removed or changed"""
        if not self.accounting_template_id:
            # Clear dependent fields when template is removed
            self.subtype_id = False
            self.identifier_id = False
        else:
            # Clear subtype if it doesn't match the new template's domain
            if self.subtype_id and self.accounting_template_id.template_type_id:
                if self.accounting_template_id.template_type_id not in self.subtype_id.template_type_ids:
                    self.subtype_id = False

            # Clear identifier if template doesn't require it
            if self.identifier_id and not self.accounting_template_id.requires_identifier_id:
                self.identifier_id = False

            # Clear subtype if template doesn't require it
            if self.subtype_id and not self.accounting_template_id.requires_subtype_id:
                self.subtype_id = False

    @api.onchange("quantity", "unit_price")
    def _compute_pre_vat_total(self):
        if self.quantity and self.unit_price:
            self.pre_vat_total = self.quantity * self.unit_price
        else:
            self.pre_vat_total = 0.0

    @api.onchange("quantity", "pre_vat_total")
    def _compute_unit_price(self):
        if self.quantity and self.pre_vat_total:
            self.unit_price = self.pre_vat_total / self.quantity
        else:
            self.unit_price = 0.0

    @api.depends("pre_vat_total", "vat_rate")
    def _compute_vat_total(self):
        for record in self:
            if record.pre_vat_total and record.vat_rate:
                record.vat_total = record.pre_vat_total * (record.vat_rate / 100)
            else:
                record.vat_total = 0.0
        return {}

    @api.depends("pre_vat_total", "vat_rate")
    def _compute_total_price(self):
        for record in self:
            record.total_price = record.pre_vat_total + record.vat_total
        return {}

    def refresh_compute_totals(self):
        self._compute_pre_vat_total()
        self._compute_vat_total()
        self._compute_total_price()
        return {}

    def open_o2m_record(self):
        return {
            "name": _("Invoice Content"),
            "type": "ir.actions.act_window",
            "res_model": "kojto.finance.invoice.contents",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
            "context": {},
        }

    @api.depends('invoice_id', 'is_redistribution', 'pre_vat_total')
    def _compute_redistribution_is_valid(self):
        # First pass: calculate sums for each invoice
        invoice_sums = {}
        for record in self:
            if record.invoice_id and record.is_redistribution:
                invoice_id = record.invoice_id.id
                if invoice_id not in invoice_sums:
                    invoice_sums[invoice_id] = 0
                invoice_sums[invoice_id] += record.pre_vat_total

        # Second pass: set validity based on sums
        for record in self:
            if not record.is_redistribution:
                record.redistribution_is_valid = True
                continue

            if not record.invoice_id:
                record.redistribution_is_valid = True
                continue

            invoice_id = record.invoice_id.id
            total = invoice_sums.get(invoice_id, 0)

            # If sum is not 0 (within tolerance), all redistributions for this invoice are invalid
            record.redistribution_is_valid = abs(total) < 0.01

    @api.constrains('is_redistribution', 'pre_vat_total', 'subcode_id', 'invoice_id')
    def _check_redistribution_constraints(self):
        """Ensure redistribution contents follow subcode rules:
        - Negative amounts must have same subcode as invoice
        - Positive amounts must have different subcode from invoice
        """
        for record in self:
            if not record.is_redistribution:
                continue

            invoice_subcode_id = record.invoice_id.subcode_id.id if record.invoice_id.subcode_id else False

            if record.pre_vat_total < 0:
                if record.subcode_id.id != invoice_subcode_id:
                    raise ValidationError(
                        _("Redistribution with negative amount for invoice %s must have the same subcode as the invoice (%s).")
                        % (record.invoice_id.display_name, record.invoice_id.subcode_id.display_name or "None")
                    )
            elif record.pre_vat_total > 0:
                if record.subcode_id.id == invoice_subcode_id and invoice_subcode_id:
                    raise ValidationError(
                        _("Redistribution with positive amount for invoice %s cannot have the same subcode as the invoice (%s).")
                        % (record.invoice_id.display_name, record.invoice_id.subcode_id.display_name)
                    )

    def auto_accounting(self):
        """
        Automatically set accounting fields for this content line using AI.
        Analyzes similar historical invoice contents and recommends accounting field values.
        """
        for content in self:
            result = auto_accounting_for_content(content)

            # Invalidate cache to ensure UI shows updated values
            content.invalidate_recordset([
                'vat_treatment_id',
                'accounting_template_id',
                'identifier_id',
                'subtype_id',
                'vat_rate'
            ])

            # Show notification
            content.env['bus.bus']._sendone(
                content.env.user.partner_id,
                'simple_notification',
                {
                    'title': 'Auto Accounting',
                    'message': result,
                    'type': 'success' if 'Successfully' in result else 'warning',
                }
            )

        # Return True to refresh the current view without navigation
        return True


