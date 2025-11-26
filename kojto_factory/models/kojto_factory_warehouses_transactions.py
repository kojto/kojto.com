# kojto_factory/models/kojto_factory_warehouses_transactions.py
from odoo import api, models, fields, _
from odoo.exceptions import ValidationError

class KojtoWarehousesTransactions(models.Model):
    _inherit = 'kojto.warehouses.transactions'

    job_id = fields.Many2one('kojto.factory.jobs', string='Job', ondelete='set null')

    def action_create_item_from_transaction(self):
        self.ensure_one()
        if self.to_from_store != 'from_store':
            return False

        return {
            'name': _('Create New Item'),
            'type': 'ir.actions.act_window',
            'res_model': 'kojto.factory.item.dimensions.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_transaction_id': self.id,
            }
        }
