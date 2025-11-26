from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class KojtoFactoryItemDimensionsWizard(models.TransientModel):
    _name = 'kojto.factory.item.dimensions.wizard'
    _description = 'Item Dimensions Wizard'

    transaction_id = fields.Many2one('kojto.warehouses.transactions', string='Transaction', required=True)
    item_type = fields.Selection(related='transaction_id.item_id.item_type', string='Item Type', readonly=True)

    # Sheet dimensions
    length = fields.Float(string='Length (mm)', required=True)
    width = fields.Float(string='Width (mm)', required=True)

    # Bar dimension
    bar_length = fields.Float(string='Length (mm)', required=True)

    # Part quantity
    transaction_quantity = fields.Float(string='Quantity', required=True)

    @api.depends('item_type')
    def _compute_field_visibility(self):
        for record in self:
            record.show_sheet_fields = record.item_type == 'sheet'
            record.show_bar_fields = record.item_type == 'bar'
            record.show_part_fields = record.item_type == 'part'

    show_sheet_fields = fields.Boolean(compute='_compute_field_visibility')
    show_bar_fields = fields.Boolean(compute='_compute_field_visibility')
    show_part_fields = fields.Boolean(compute='_compute_field_visibility')

    @api.constrains('length', 'width')
    def _check_sheet_dimensions(self):
        for record in self:
            if record.item_type == 'sheet':
                parent_item = record.transaction_id.item_id
                if record.length >= parent_item.length:
                    raise ValidationError(_("New sheet length must be less than parent sheet length (%s mm)") % parent_item.length)
                if record.width >= parent_item.width:
                    raise ValidationError(_("New sheet width must be less than parent sheet width (%s mm)") % parent_item.width)

    @api.constrains('bar_length')
    def _check_bar_length(self):
        for record in self:
            if record.item_type == 'bar':
                parent_item = record.transaction_id.item_id
                if record.bar_length >= parent_item.length:
                    raise ValidationError(_("New bar length must be less than parent bar length (%s mm)") % parent_item.length)

    def action_create_item(self):
        self.ensure_one()
        transaction = self.transaction_id
        item = transaction.item_id

        # Validate dimensions before creating
        if self.item_type == 'sheet':
            if self.length >= item.length:
                raise ValidationError(_("New sheet length must be less than parent sheet length (%s mm)") % item.length)
            if self.width >= item.width:
                raise ValidationError(_("New sheet width must be less than parent sheet width (%s mm)") % item.width)
        elif self.item_type == 'bar':
            if self.bar_length >= item.length:
                raise ValidationError(_("New bar length must be less than parent bar length (%s mm)") % item.length)

        # Find the next available index for the name
        base_name = item.name
        index = 1
        while True:
            new_name = f"{base_name}.{index}"
            if not self.env['kojto.warehouses.items'].search([('name', '=', new_name)], limit=1):
                break
            index += 1

        # Prepare item values based on type
        item_vals = {
            'name': new_name,
            'batch_id': item.batch_id.id,
            'parent_item_id': item.id,
        }

        if self.item_type == 'sheet':
            item_vals.update({
                'length': self.length,
                'width': self.width,
                'thickness': item.thickness,
            })
        elif self.item_type == 'bar':
            item_vals.update({
                'length': self.bar_length,
            })
        elif self.item_type == 'part':
            item_vals.update({
                'weight_override': self.transaction_quantity,
            })

        # Create new item
        new_item = self.env['kojto.warehouses.items'].create(item_vals)

        # Create incoming transaction for the new item
        transaction_vals = {
            'item_id': new_item.id,
            'batch_id': item.batch_id.id,
            'transaction_unit_id': item.unit_id.id,
            'datetime_issue': fields.Datetime.now(),
            'to_from_store': 'to_store',
            'job_id': transaction.job_id.id,
            'subcode_id': item.batch_id.subcode_id.id
        }

        # Set transaction quantity based on item type
        if self.item_type == 'part':
            transaction_vals['transaction_quantity'] = self.transaction_quantity
        else:
            transaction_vals['transaction_quantity'] = new_item.weight

        self.env['kojto.warehouses.transactions'].create(transaction_vals)

        return {'type': 'ir.actions.act_window_close'}
