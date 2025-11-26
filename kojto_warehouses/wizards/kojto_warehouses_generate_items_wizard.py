# kojto_warehouses/wizards/kojto_warehouses_generate_items_wizard.py
from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class KojtoWarehousesGenerateItemsWizard(models.TransientModel):
    _name = "kojto.warehouses.generate.items.wizard"
    _description = "Generate Items Wizard"

    batch_id = fields.Many2one("kojto.warehouses.batches", string="Batch", required=True)
    batch_type = fields.Selection(related="batch_id.batch_type", string="Batch Type", readonly=True)

    number_of_items = fields.Integer(
        string="Number of Items to Generate",
        help="Specify how many items to automatically create for this batch",
        default=1,
        required=True
    )

    # Dimension fields for batch item generation
    gen_items_length = fields.Float(
        string="Length (mm)",
        help="Length to apply to all generated items",
        required=True
    )
    gen_items_width = fields.Float(
        string="Width (mm)",
        help="Width to apply to all generated sheet items"
    )
    gen_items_weight = fields.Float(
        string="Weight (kg)",
        help="Weight to apply to all generated part items"
    )

    @api.onchange('batch_type')
    def _onchange_batch_type(self):
        """Set default values based on batch type."""
        if self.batch_type == 'sheet':
            self.gen_items_length = 1000.0
            self.gen_items_width = 1000.0
        elif self.batch_type == 'bar':
            self.gen_items_length = 1000.0
        elif self.batch_type == 'part':
            self.gen_items_weight = 1.0

    def action_generate_items(self):
        """Generate items based on the wizard values."""
        self.ensure_one()

        if self.number_of_items <= 0:
            raise ValidationError(_("Please specify a number of items to generate."))

        # Validate required fields based on batch type
        if self.batch_type == 'sheet':
            if not self.gen_items_length or not self.gen_items_width:
                raise ValidationError(_("Sheet items require both length and width to be specified."))
        elif self.batch_type == 'bar':
            if not self.gen_items_length:
                raise ValidationError(_("Bar items require length to be specified."))
        elif self.batch_type == 'part':
            if not self.gen_items_weight:
                raise ValidationError(_("Part items require weight to be specified."))

        # Generate items
        self.batch_id._generate_items(
            self.number_of_items,
            self.gen_items_length,
            self.gen_items_width,
            self.gen_items_weight
        )

        return {
            'type': 'ir.actions.act_window_close',
            'context': {
                'message': _('Successfully generated %d items.') % self.number_of_items,
            }
        }
