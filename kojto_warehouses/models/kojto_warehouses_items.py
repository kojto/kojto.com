# kojto_warehouses/models/kojto_warehouses_items.py
from odoo import api, models, fields, exceptions, _
from odoo.exceptions import ValidationError
from ..utils.kojto_warehouses_name_generator import get_temp_name, get_final_name, ITEM_PREFIXES

# Material constants
DENSITY_CONVERSION = 1000000000.0  # mm3 to m3 conversion
DEFAULT_CROSS_SECTION = 100.0  # mm2

class KojtoWarehousesItems(models.Model):
    _name = "kojto.warehouses.items"
    _description = "Warehouse Items"
    _rec_name = "name"
    _order = "name desc"
    _sql_constraints = [('name_uniq', 'unique(name)', 'Item name must be unique!'),]

    name = fields.Char("Name", required=True, copy=False, default=lambda self: get_temp_name(self._context.get('item_type', 'sheet'), ITEM_PREFIXES, 'ITEM'))
    active = fields.Boolean(string="Is Active", compute="compute_active", store=True)
    name_secondary = fields.Char("Name Secondary")
    item_description = fields.Text("Item Description")
    batch_id = fields.Many2one("kojto.warehouses.batches", string="Batch", required=True, ondelete="cascade")
    inspection_report_id = fields.Many2one('kojto.warehouses.inspection.report', string='Inspection Report', readonly=True, copy=False)
    parent_item_id = fields.Many2one("kojto.warehouses.items", string="Parent Item", ondelete="set null")
    allowed_parent_item_ids = fields.Many2many("kojto.warehouses.items", "kojto_warehouses_items_allowed_parent_rel", "item_id", "parent_id", compute="_compute_allowed_parent_item_ids", store=False, string="Allowed Parent Items")

    item_type = fields.Selection(related="batch_id.batch_type", string="Type", store=True, readonly=True)
    unit_id = fields.Many2one(related="batch_id.unit_id", string="Unit", readonly=True)
    material_id = fields.Many2one(related="batch_id.material_id", string="Material", readonly=True)
    profile_id = fields.Many2one(related="batch_id.profile_id", string="Profile", readonly=True)
    thickness = fields.Float(string="Thickness (mm)", related="batch_id.thickness", readonly=True)
    certificate_ids = fields.One2many(related="batch_id.certificate_ids", string="Certificates", readonly=True)

    length = fields.Float(string="Length (mm)", default=1000.0)
    width = fields.Float(string="Width (mm)", default=1000.0)
    weight = fields.Float(string="Weight (kg)", compute="compute_weight", store=True, default=1.0)
    current_item_quantity = fields.Float(string="Current Qty", compute="_compute_current_item_quantity")
    transaction_ids = fields.One2many("kojto.warehouses.transactions", "item_id", string="Transactions")

    part_type = fields.Selection([('common', 'Common'), ('fastener', 'Fastener'), ('package', 'Package'), ('other', 'Other')], string="Part Type", default='common')
    item_summary = fields.Text(string="Item Summary", compute="_compute_item_summary")

    reservation_subcode_id = fields.Many2one("kojto.commission.subcodes", string="Reservation Subcode", required=False)
    reserved_by = fields.Many2one("kojto.hr.employees", string="Reserved By", default=lambda self: self.env.user.employee, readonly=True)
    reserved_datetime = fields.Datetime(string="Reserved On", default=fields.Datetime.now, readonly=True)
    reservation_comment = fields.Char(string="Comment")


    @api.constrains('item_type', 'batch_id')
    def _check_item_type_matches_batch(self):
        """Ensure item type matches batch type."""
        for item in self:
            if item.batch_id and item.item_type != item.batch_id.batch_type:
                raise ValidationError(_(
                    "Item type (%s) must match batch type (%s) for item %s"
                ) % (item.item_type, item.batch_id.batch_type, item.name))

    @api.constrains('item_type', 'length', 'width', 'thickness')
    def _check_material_fields(self):
        for item in self:
            if item.item_type == 'sheet':
                if not (item.length and item.width and item.thickness):
                    raise ValidationError(_("Sheet items must have length, width, and thickness."))
                if not item.batch_id or not item.material_id:
                    raise ValidationError(_("Sheet items need a batch and material."))
            elif item.item_type == 'bar':
                if not item.length:
                    raise ValidationError(_("Bar items must have length."))
                if not item.batch_id or not item.batch_id.profile_id:
                    raise ValidationError(_("Bar items need a batch with profile."))
            elif item.item_type == 'part' and not item.weight:
                raise ValidationError(_("Part items must have a weight override value."))

    @api.constrains('parent_item_id')
    def _check_parent_item_same_batch(self):
        for item in self:
            if item.parent_item_id and item.parent_item_id.batch_id != item.batch_id:
                raise ValidationError(_("Parent item must belong to the same batch."))

    @api.depends('length', 'width', 'thickness', 'batch_id.material_id', 'batch_id.profile_id', 'item_type')
    def compute_weight(self):
        """Compute weight based on item type and dimensions."""
        for rec in self:
            # Handle missing batch or item type
            if not rec.batch_id or not rec.item_type:
                rec.weight = 0.0
                continue

            # Handle parts - use default weight
            if rec.item_type == 'part':
                rec.weight = 1.0
                continue

            # Handle missing material or density
            if not rec.material_id or not rec.material_id.density:
                rec.weight = 0.0
                continue

            density = rec.material_id.density
            volume_mm3 = 0.0

            # Calculate volume based on item type
            if rec.item_type == 'sheet':
                if all([rec.length > 0, rec.width > 0, rec.thickness > 0]):
                    volume_mm3 = rec.length * rec.width * rec.thickness
            elif rec.item_type == 'bar':
                if rec.length > 0 and rec.batch_id.profile_id:
                    cross_section = rec.batch_id.profile_id.cross_section or DEFAULT_CROSS_SECTION
                    volume_mm3 = rec.length * cross_section

            # Calculate final weight
            volume_m3 = volume_mm3 / DENSITY_CONVERSION
            rec.weight = volume_m3 * density

            # Update transaction quantities for sheets and bars
            if rec.item_type in ['sheet', 'bar']:
                transactions = rec.env['kojto.warehouses.transactions'].search([
                    ('item_id', '=', rec.id),
                    ('item_id.item_type', 'in', ['sheet', 'bar'])
                ])
                if transactions:
                    transactions.write({'transaction_quantity': rec.weight})

        return {}

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('batch_id'):
                raise ValidationError(_("Batch ID is required."))
            batch = self.env['kojto.warehouses.batches'].browse(vals['batch_id'])
            if batch.batch_type == 'sheet' and not batch.thickness:
                raise ValidationError(_("Sheet batch needs thickness."))

        items = super().create(vals_list)
        for item in items:
            item.compute_weight()
            if item.item_type == 'sheet' and not item.weight:
                raise ValidationError(_("Weight calculation failed for sheet item %s.") % item.name)
            item.write({'name': get_final_name(item.id, item.item_type, ITEM_PREFIXES, 'ITEM')})

            try:
                # Get the appropriate subcode
                subcode = item._get_transaction_subcode()

                # Only create transaction if we have a subcode
                if subcode:
                    # Create initial transaction through transaction model
                    transaction_values = {
                        'item_id': item.id,
                        'transaction_quantity': item.weight,
                        'transaction_quantity_override': 1.0,  # Default value, user can change it
                        'date_issue': fields.Date.today(),
                        'to_from_store': 'to_store',
                        'subcode_id': subcode.id  # Add the subcode to the transaction
                    }
                    self.env['kojto.warehouses.transactions'].create(transaction_values)
            except Exception as e:
                # Log the error but don't prevent item creation
                self.env.user.message_post(
                    body=_("Item %s created but initial transaction failed: %s") % (item.name, str(e)),
                    message_type='comment',
                    subtype_xmlid='mail.mt_note'
                )

            # Force recompute of available quantity and active status
            item._compute_current_item_quantity()
            item.compute_active()
        return items

    def write(self, vals):
        if 'batch_id' in vals:
            if not vals['batch_id']:
                raise ValidationError(_("Cannot unset batch ID."))
            batch = self.env['kojto.warehouses.batches'].browse(vals['batch_id'])
            if batch.batch_type == 'sheet' and not batch.thickness:
                raise ValidationError(_("Sheet batch needs thickness."))

        old_weights = {item.id: item.weight for item in self}
        result = super().write(vals)

        weight_fields = {'length', 'width', 'thickness', 'item_type', 'batch_id'}
        if weight_fields.intersection(vals):
            for item in self:
                try:
                    if item.item_type == 'sheet':
                        if not all([item.length, item.width, item.thickness]) or any(v <= 0 for v in [item.length, item.width, item.thickness]):
                            raise ValidationError(_("Sheet item %s needs valid dimensions.") % item.name)
                        if not item.material_id:
                            raise ValidationError(_("Sheet item %s needs material.") % item.name)

                    item.compute_weight()

                    if item.item_type == 'sheet' and not item.weight:
                        raise ValidationError(_("Weight calculation failed for sheet item %s.") % item.name)

                    if item.weight != old_weights.get(item.id, 0.0):
                        # Force recompute of available quantity since weight changed
                        item._compute_current_item_quantity()
                        item.compute_active()
                except Exception as e:
                    raise

        return result

    @api.depends('transaction_ids.transaction_quantity', 'transaction_ids.to_from_store')
    def _compute_current_item_quantity(self):
        """Compute current quantity by summing transaction quantities."""
        for item in self:
            quantity = sum(
                transaction.transaction_quantity if transaction.to_from_store == 'to_store'
                else -transaction.transaction_quantity
                for transaction in item.transaction_ids
            )
            item.current_item_quantity = quantity

    @api.depends('current_item_quantity')
    def compute_active(self):
        """Compute active status for items."""
        for item in self:
            item.active = item.current_item_quantity > 0
        return {}

    @api.depends('length', 'width', 'thickness', 'material_id', 'part_type', 'item_type')
    def _compute_item_summary(self):
        for item in self:
            material_part = f" - {item.material_id.name}" if item.material_id else ""
            if item.item_type == 'sheet':
                item.item_summary = f"{item.length} x {item.width} x {item.thickness} mm{material_part}"
            elif item.item_type == 'bar':
                item.item_summary = f"{item.length} mm{material_part}"
            elif item.item_type == 'part':
                item.item_summary = f"{item.part_type.capitalize()}{material_part}"
            else:
                item.item_summary = ""

    def action_open_item_form(self):
        self.ensure_one()
        return {
            'name': 'Item Details',
            'type': 'ir.actions.act_window',
            'res_model': 'kojto.warehouses.items',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }

    def _get_transaction_subcode(self):
        """Get the appropriate subcode for a transaction following these rules:
        1. First try to get subcode from batch's invoice content
        2. If not available, try to get subcode from last transaction of the batch
        3. If neither available, return False to allow any subcode
        """
        self.ensure_one()

        # Try to get subcode from batch's invoice content
        if self.batch_id.invoice_content_id and self.batch_id.invoice_content_id.subcode_id:
            return self.batch_id.invoice_content_id.subcode_id

        # Try to get subcode from last transaction of the batch
        last_transaction = self.env['kojto.warehouses.transactions'].search([
            ('batch_id', '=', self.batch_id.id),
            ('subcode_id', '!=', False)
        ], order='date_issue desc', limit=1)

        if last_transaction and last_transaction.subcode_id:
            return last_transaction.subcode_id

        # If we get here, no valid subcode was found
        # Instead of raising an error, return False to allow any subcode
        return False

    def action_create_outgoing_transaction(self):
        self.ensure_one()
        # Get the appropriate subcode
        subcode = self._get_transaction_subcode()

        # Create outgoing transaction through transaction model
        transaction_values = {
            'item_id': self.id,
            'transaction_quantity': self.weight,
            'transaction_quantity_override': 1.0,  # Default value, user can change it
            'date_issue': fields.Date.today(),
            'to_from_store': 'from_store',
            'subcode_id': subcode.id  # Add the subcode to the transaction
        }
        self.env['kojto.warehouses.transactions'].create(transaction_values)
        return False

    @api.depends('batch_id')
    def _compute_allowed_parent_item_ids(self):
        for item in self:
            if item.batch_id:
                domain = [('batch_id', '=', item.batch_id.id)]
                if item._origin.id:
                    domain.append(('id', '!=', item._origin.id))
                item.allowed_parent_item_ids = self.search(domain)
            else:
                item.allowed_parent_item_ids = False

    @api.constrains('transaction_ids', 'transaction_ids.transaction_quantity', 'transaction_ids.to_from_store')
    def _check_item_transactions(self):
        """Validate all transactions related to this item."""
        for item in self:
            # Check first transaction rule
            transactions = item.transaction_ids.sorted('date_issue')
            if transactions and transactions[0].to_from_store != 'to_store':
                raise ValidationError(_("[Item Model] The first transaction for item %s must be to store.") % item.name)

            # Check quantity sum and weight matching
            current_quantity = 0
            for transaction in transactions:
                if item.item_type in ['sheet', 'bar']:
                    # For sheets and bars, enforce weight matching
                    if abs(transaction.transaction_quantity - item.weight) > 0.001:  # Using small epsilon for float comparison
                        raise ValidationError(_("[Item Model] For sheets and bars, transaction quantity must match the item's weight (%.2f kg).") % item.weight)
                    current_quantity += item.weight if transaction.to_from_store == 'to_store' else -item.weight
                else:
                    # For parts, just use the transaction quantity
                    current_quantity += transaction.transaction_quantity if transaction.to_from_store == 'to_store' else -transaction.transaction_quantity

            if current_quantity < 0:
                raise ValidationError(_("[Item Model] Item %s has negative quantity: %.2f") % (item.name, current_quantity))

    def validate_transaction_quantity(self, quantity, transaction_type='to_store'):
        """Validate if a transaction with given quantity would be valid for this item."""
        # Basic positive quantity check for all items
        if quantity <= 0:
            raise ValidationError(_("[Item Model] Transaction quantity must be positive."))

        # For sheets and bars, validate that the computed quantity matches the item's weight
        if self.item_type in ['sheet', 'bar']:
            # The computed quantity (transaction_quantity) must match the item's weight
            # The override value (transaction_quantity_override) can be any positive value
            # This validation is handled by the transaction model's compute_transaction_quantity method
            pass

        # Check if this would result in negative quantity
        current_quantity = sum(
            t.transaction_quantity if t.to_from_store == 'to_store' else -t.transaction_quantity
            for t in self.transaction_ids
        )
        if transaction_type == 'to_store':
            current_quantity += self.weight if self.item_type in ['sheet', 'bar'] else quantity
        else:
            current_quantity -= self.weight if self.item_type in ['sheet', 'bar'] else quantity
        if current_quantity < 0:
            raise ValidationError(_("[Item Model] This transaction would result in negative quantity for item %s. Current quantity would be: %.2f") % (self.name, current_quantity))

    @api.onchange('reservation_subcode_id')
    def _onchange_reservation_subcode_id(self):
        """Clear reservation fields when subcode is cleared."""
        if not self.reservation_subcode_id:
            self.reserved_by = False
            self.reserved_datetime = False
            self.reservation_comment = False

    def action_clear_reservation(self):
        """Clear all reservation fields."""
        self.write({
            'reservation_subcode_id': False,
            'reserved_by': False,
            'reserved_datetime': False,
            'reservation_comment': False
        })
        return True
