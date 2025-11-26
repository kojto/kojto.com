from odoo import models, fields, api


class KojtoDeliveryConsumedMaterials(models.Model):
    _name = "kojto.delivery.consumed.materials"
    _description = "Delivery Consumed Materials"
    _rec_name = "name"
    _sort = "delivery_content_position"

    name = fields.Char(string="Name")
    description = fields.Char(string="Description")
    delivery_content_id = fields.Many2one("kojto.delivery.contents", string="Delivery Content", ondelete="cascade")
    delivery_content_position = fields.Char(related="delivery_content_id.position", string="Position", store=True)

    invoice_id = fields.Many2one("kojto.finance.invoices", string="Invoice")
    invoice_content_id = fields.Many2one("kojto.finance.invoice.contents", string="Invoice Content", domain="[('invoice_id', '=', invoice_id)]")

    batch_id = fields.Many2one("kojto.warehouses.batches", string="Batch")
    batch_unit_id = fields.Many2one("kojto.base.units", string="Unit", related="batch_id.unit_id", store=True, readonly=True)
    batch_quantity_consumed = fields.Float(string="Consumed Qty", digits=(14, 2))

    @api.onchange('batch_id')
    def _onchange_batch_id(self):
        if self.batch_id:
            self.invoice_id = self.batch_id.invoice_id
            self.invoice_content_id = False  # Reset invoice content when batch changes

    @api.onchange('invoice_id')
    def _onchange_invoice_id(self):
        if self.invoice_id:
            # Find batches associated with this invoice
            batches = self.env['kojto.warehouses.batches'].search([('invoice_id', '=', self.invoice_id.id)])

            # If there's only one batch, set it automatically
            if len(batches) == 1:
                self.batch_id = batches[0]

                # If there's only one invoice content, set it automatically
                invoice_contents = self.env['kojto.finance.invoice.contents'].search([('invoice_id', '=', self.invoice_id.id)])
                if len(invoice_contents) == 1:
                    self.invoice_content_id = invoice_contents[0]
            else:
                # Reset batch if multiple batches or no batches found
                self.batch_id = False
                self.invoice_content_id = False

    @api.onchange('invoice_content_id')
    def _onchange_invoice_content_id(self):
        if self.invoice_content_id:
            # Find batches that are connected to this invoice content
            # Assuming there's a relationship between batches and invoice contents
            batches = self.env['kojto.warehouses.batches'].search([
                ('invoice_id', '=', self.invoice_content_id.invoice_id.id)
            ])

            # If there's only one batch connected to this content, set it automatically
            if len(batches) == 1:
                self.batch_id = batches[0]
                self.invoice_id = self.invoice_content_id.invoice_id
            else:
                # Reset batch if multiple batches or no batches found
                self.batch_id = False

    def delete_consumed_material(self):
        """Custom delete method that removes the consumed material but stays in the list view"""
        self.ensure_one()
        delivery_content_id = self.delivery_content_id.id
        self.unlink()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Consumed Materials',
            'res_model': 'kojto.delivery.consumed.materials',
            'view_mode': 'list',
            'domain': [('delivery_content_id', '=', delivery_content_id)],
            'context': {'default_delivery_content_id': delivery_content_id},
            'target': 'new',
        }
