# kojto_warehouses/models/kojto_warehouses_invoice_integration.py
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class KojtoFinanceInvoiceWithBatchCreation(models.Model):
    _inherit = "kojto.finance.invoices"

    def action_create_batch_from_invoice(self):
        """Open wizard to create a batch from invoice"""
        self.ensure_one()

        # Check if this is an incoming invoice (purchases)
        if self.document_in_out_type != 'incoming':
            raise UserError(_("Batches can only be created from incoming invoices (purchases)."))

        # Create wizard with pre-filled values
        wizard = self.env['kojto.warehouses.invoice.batch.creation.wizard'].create({
            'invoice_id': self.id,
            'counterparty_id': self.counterparty_id.id,
        })

        return {
            'name': _('Create Batch from Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'kojto.warehouses.invoice.batch.creation.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
            'context': {
                'default_invoice_id': self.id,
                'default_counterparty_id': self.counterparty_id.id,
            }
        }


class KojtoFinanceInvoiceContentWithBatchCreation(models.Model):
    _inherit = "kojto.finance.invoice.contents"

    def action_create_batch_from_content_line(self):
        """Open wizard to create a batch from this invoice content line"""
        self.ensure_one()

        # Prepare wizard values
        wizard_vals = {
            'invoice_id': self.invoice_id.id,
            'invoice_content_id': self.id,
            'counterparty_id': self.invoice_id.counterparty_id.id,
            'unit_price': self.unit_price,
        }

        # Add accounting identifier if available
        if self.identifier_id:
            wizard_vals['accounting_identifier_id'] = self.identifier_id.id

        # Set conversion rate based on invoice currency
        if self.invoice_id and self.invoice_id.currency_id:
            if self.invoice_id.currency_id.name == 'BGN':
                wizard_vals['unit_price_conversion_rate'] = 1.0
            elif self.invoice_id.currency_id.name == 'EUR':
                wizard_vals['unit_price_conversion_rate'] = self.invoice_id.exchange_rate_to_bgn
            else:
                wizard_vals['unit_price_conversion_rate'] = self.invoice_id.exchange_rate_to_bgn

        # Create wizard with pre-filled values from the content line
        wizard = self.env['kojto.warehouses.invoice.batch.creation.wizard'].create(wizard_vals)

        return {
            'name': _('Create Batch from Invoice Line'),
            'type': 'ir.actions.act_window',
            'res_model': 'kojto.warehouses.invoice.batch.creation.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

