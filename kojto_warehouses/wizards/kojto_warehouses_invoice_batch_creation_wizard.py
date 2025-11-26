# kojto_warehouses/wizards/kojto_warehouses_invoice_batch_creation_wizard.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class KojtoWarehousesInvoiceBatchCreationWizard(models.TransientModel):
    _name = 'kojto.warehouses.invoice.batch.creation.wizard'
    _description = 'Wizard to Create Batch from Invoice'

    # Invoice relation fields (pre-filled from invoice)
    invoice_id = fields.Many2one('kojto.finance.invoices', string='Invoice', required=True, readonly=True)
    invoice_content_id = fields.Many2one('kojto.finance.invoice.contents', string='Invoice Content', required=True,
                                         domain="[('invoice_id', '=', invoice_id)]")
    counterparty_id = fields.Many2one('kojto.contacts', string='Manufacturer', required=True)

    # Batch type selection
    batch_type = fields.Selection([
        ('sheet', 'Sheet'),
        ('bar', 'Bar'),
        ('part', 'Part')
    ], string='Batch Type', required=True, default='sheet')

    # Store selection
    store_id = fields.Many2one('kojto.base.stores', string='Store', required=True, default=lambda self: self._get_default_store())

    # Material and dimensional fields
    material_id = fields.Many2one('kojto.base.material.grades', string='Material')
    profile_id = fields.Many2one('kojto.warehouses.profile.shapes', string='Profile')
    thickness = fields.Float(string='Thickness (mm)', default=10.0)
    part_type = fields.Selection([
        ('common', 'Common'),
        ('fastener', 'Fastener'),
        ('package', 'Package'),
        ('other', 'Other')
    ], string='Part Type', default='common')

    # Accounting fields
    accounting_identifier_id = fields.Many2one('kojto.finance.accounting.identifiers', string='Accounting Identifier', required=True)

    # Pricing fields (pre-filled from invoice content)
    unit_price = fields.Float(string='Unit Price', digits=(16, 2), default=1.0)
    unit_price_conversion_rate = fields.Float(string='Conversion Rate', digits=(16, 4), default=1.0)

    # Additional fields
    name_secondary = fields.Char(string='Secondary Name')
    description = fields.Text(string='Description')

    def _get_default_store(self):
        """Get the store from the last created batch, or the first store if no batches exist"""
        # Try to get the last batch's store
        last_batch = self.env['kojto.warehouses.batches'].search([], order='id desc', limit=1)
        if last_batch and last_batch.store_id:
            return last_batch.store_id.id

        # Fallback to first store if no batches exist
        store = self.env['kojto.base.stores'].search([], limit=1)
        return store.id if store else False

    @api.onchange('invoice_content_id')
    def _onchange_invoice_content_id(self):
        """Pre-fill pricing and accounting identifier from invoice content"""
        if self.invoice_content_id:
            self.unit_price = self.invoice_content_id.unit_price
            # Set accounting identifier from invoice content line
            if self.invoice_content_id.identifier_id:
                self.accounting_identifier_id = self.invoice_content_id.identifier_id
            # Set conversion rate from invoice if available
            if self.invoice_id and self.invoice_id.currency_id:
                if self.invoice_id.currency_id.name == 'BGN':
                    self.unit_price_conversion_rate = 1.0
                elif self.invoice_id.currency_id.name == 'EUR':
                    self.unit_price_conversion_rate = self.invoice_id.exchange_rate_to_bgn
                else:
                    self.unit_price_conversion_rate = self.invoice_id.exchange_rate_to_bgn

    @api.onchange('invoice_id')
    def _onchange_invoice_id(self):
        """Update counterparty when invoice changes"""
        if self.invoice_id:
            self.counterparty_id = self.invoice_id.counterparty_id

    def action_create_batch(self):
        """Create the batch with filled values"""
        self.ensure_one()

        # Validate required fields based on batch type
        if self.batch_type == 'sheet' and not self.thickness:
            raise ValidationError(_("Sheet batch requires thickness."))
        if self.batch_type == 'bar' and not self.profile_id:
            raise ValidationError(_("Bar batch requires profile."))

        # Prepare batch values
        batch_vals = {
            'batch_type': self.batch_type,
            'store_id': self.store_id.id,
            'counterparty_id': self.counterparty_id.id,
            'invoice_id': self.invoice_id.id,
            'invoice_content_id': self.invoice_content_id.id,
            'accounting_identifier_id': self.accounting_identifier_id.id,
            'material_id': self.material_id.id if self.material_id else False,
            'profile_id': self.profile_id.id if self.profile_id else False,
            'thickness': self.thickness,
            'part_type': self.part_type,
            'unit_price': self.unit_price,
            'unit_price_conversion_rate': self.unit_price_conversion_rate,
            'name_secondary': self.name_secondary,
            'description': self.description,
            'date_issue': self.invoice_id.date_issue,
            'active': True,
        }

        # Create the batch
        batch = self.env['kojto.warehouses.batches'].create(batch_vals)

        # Return action to open the created batch
        return {
            'name': _('Batch'),
            'type': 'ir.actions.act_window',
            'res_model': 'kojto.warehouses.batches',
            'view_mode': 'form',
            'res_id': batch.id,
            'target': 'current',
        }

