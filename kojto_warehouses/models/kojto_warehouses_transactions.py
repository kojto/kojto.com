from odoo import api, models, fields, _
from odoo.exceptions import ValidationError, UserError
from ..utils.kojto_warehouses_name_generator import get_temp_name, get_final_name
import logging
_logger = logging.getLogger(__name__)

# Transaction prefixes
TRANSACTION_PREFIXES = {'to_store': 'TRX.TO', 'from_store': 'TRX.FR'}
DEFAULT_PREFIX = 'TRX'


class KojtoWarehousesTransactions(models.Model):
    _name = "kojto.warehouses.transactions"
    _description = "Warehouse Transactions"
    _rec_name = "name"
    _order = "date_issue desc"

    name = fields.Char("Name", required=True, copy=False, default=lambda self: get_temp_name(self._context.get('to_from_store', 'from_store'), TRANSACTION_PREFIXES, DEFAULT_PREFIX))

    item_id = fields.Many2one("kojto.warehouses.items", string="Item", required=True, ondelete="cascade", index=True)
    batch_id = fields.Many2one("kojto.warehouses.batches", string="Batch", related="item_id.batch_id", readonly=True, store=True, index=True)
    identifier_id = fields.Char(string="Identifier ID", related="batch_id.invoice_content_id.identifier_id.identifier", readonly=True, store=True, index=True)

    subcode_id = fields.Many2one("kojto.commission.subcodes", string="Subcode", required=True, index=True)

    parent_item_id = fields.Many2one("kojto.warehouses.items", string="Parent Item", related="item_id.parent_item_id", readonly=True)
    date_issue = fields.Date(string="Issue Date", default=fields.Date.today, index=True)
    issued_by = fields.Many2one("kojto.hr.employees", string="Issued By", default=lambda self: self.env.user.employee, readonly=True)
    transaction_unit_id = fields.Many2one("kojto.base.units", string="Unit", related="item_id.unit_id")
    transaction_quantity = fields.Float(string="Quantity", compute="compute_transaction_quantity", store=True)
    transaction_quantity_override = fields.Float(string="Quantity", default=1.0)
    to_from_store = fields.Selection([('to_store', 'To Store'), ('from_store', 'From Store')], string="In / Out", required=True, default='from_store', index=True)
    item_summary = fields.Text(string="Item Summary", related="item_id.item_summary")
    is_part_type = fields.Boolean(string="Is Part Type", compute="_compute_is_part_type")

    # Pre-VAT transaction values (computed for performance)
    transaction_value_pre_vat_eur = fields.Float(string="Transaction Value", digits=(16, 2), compute="_compute_transaction_value_pre_vat", store=True, index=True, help="Transaction value in EUR before VAT, calculated using exchange rate at transaction date")
    currency_id = fields.Many2one("res.currency", string="Currency", compute="_compute_currency_id", readonly=True, help="Currency for monetary widget (always EUR)")

    receipt_id = fields.Many2one("kojto.warehouses.receipts", string="Receipt", ondelete='cascade')

    transaction_summary = fields.Text(string="Transaction Summary", compute="_compute_transaction_summary")

    # All subcode validation is now handled in the constraint below.
    @api.constrains('subcode_id', 'to_from_store')
    def _check_subcode_rules(self):
        for record in self:
            if record.to_from_store == 'to_store':
                _logger.info("Transaction %s: item_id=%s, parent_item_id=%s", record.name, record.item_id.id, record.item_id.parent_item_id.id if record.item_id.parent_item_id else None)
                parent_item = record.item_id.parent_item_id
                if parent_item:
                    parent_from_store_tx = self.search([
                        ('item_id', '=', parent_item.id),
                        ('to_from_store', '=', 'from_store')
                    ], order='date_issue asc', limit=1)
                    if parent_from_store_tx and parent_from_store_tx.subcode_id:
                        if record.subcode_id != parent_from_store_tx.subcode_id:
                            raise ValidationError(_(
                                "Invalid subcode for To Store transaction.\n"
                                "This item has a parent item, and its subcode must match the subcode of the parent's From Store transaction.\n"
                                "Parent item: '%s' | Parent From Store subcode: '%s'\n"
                                "Current subcode: '%s'"
                            ) % (
                                parent_item.name,
                                parent_from_store_tx.subcode_id.name,
                                record.subcode_id.name
                            ))
                    else:
                        raise ValidationError(_(
                            "Invalid subcode for To Store transaction.\n"
                            "This item has a parent item, but the parent does not have a From Store transaction with a subcode.\n"
                            "Parent item: '%s'\n"
                            "Current subcode: '%s'"
                        ) % (
                            parent_item.name,
                            record.subcode_id.name
                        ))
                else:
                    # No parent: must match batch invoice subcode
                    if record.batch_id.subcode_id:
                        if record.subcode_id != record.batch_id.subcode_id:
                            raise ValidationError(_(
                                "Invalid subcode for To Store transaction.\n"
                                "Batch '%s' has subcode '%s' from its invoice content.\n"
                                "You must use this subcode for all To Store transactions without a parent.\n"
                                "Current subcode: '%s'"
                            ) % (record.batch_id.name, record.batch_id.subcode_id.name, record.subcode_id.name))
                    else:
                        raise ValidationError(_(
                            "Invalid subcode for To Store transaction.\n"
                            "Batch '%s' does not have a subcode from its invoice content.\n"
                            "Current subcode: '%s'"
                        ) % (record.batch_id.name, record.subcode_id.name))
            # No validation for from_store transactions

    @api.model_create_multi
    def create(self, vals_list):
        """Handle creation with batch context."""
        for vals in vals_list:
            if 'item_id' not in vals and self._context.get('default_batch_id'):
                # Find an item from the batch if not specified
                batch = self.env['kojto.warehouses.batches'].browse(self._context['default_batch_id'])
                item = batch.items_ids[:1]  # Take first item
                if not item:
                    raise ValidationError(_("No items available in batch %s for transaction creation.") % batch.name)
                vals['item_id'] = item.id

            item = self.env['kojto.warehouses.items'].browse(vals['item_id'])
            if not item.exists():
                raise ValidationError(_("Invalid item ID."))

            # Validate batch_id consistency
            if vals.get('batch_id') and vals['batch_id'] != item.batch_id.id:
                raise ValidationError(_("Transaction batch ID must match item's batch ID."))

            # Set default values based on item type
            if item.item_type in ['sheet', 'bar']:
                if 'transaction_quantity_override' not in vals:
                    vals['transaction_quantity_override'] = 1.0
            else:
                if 'transaction_quantity_override' not in vals:
                    vals['transaction_quantity_override'] = 1.0

            if 'date_issue' not in vals:
                vals['date_issue'] = fields.Date.today()

            if 'to_from_store' not in vals:
                vals['to_from_store'] = 'to_store'

            item.validate_transaction_quantity(
                vals.get('transaction_quantity_override', 1.0),
                vals.get('to_from_store', 'to_store')
            )

        transactions = super().create(vals_list)
        for transaction in transactions:
            transaction.item_id._compute_current_item_quantity()
            transaction.item_id.compute_active()
            transaction.write({'name': get_final_name(transaction.id, transaction.to_from_store, TRANSACTION_PREFIXES, DEFAULT_PREFIX)})
            # Update batch computations
            transaction.batch_id._compute_current_batch_quantity()
            transaction.batch_id.compute_active()

        return transactions

    def write(self, vals):
        """Update batch computations on transaction changes."""
        result = super().write(vals)
        if 'transaction_quantity_override' in vals:
            for transaction in self:
                transaction.item_id._compute_current_item_quantity()
        affected_batches = self.mapped('batch_id')
        for batch in affected_batches:
            batch._compute_current_batch_quantity()
            batch.compute_active()
        return result

    @api.constrains('to_from_store', 'job_id', 'item_id')
    def _check_first_transaction_rules(self):
        for record in self:
            if record.item_id:
                item_transactions = self.search([('item_id', '=', record.item_id.id)], order='date_issue asc')
                if item_transactions and item_transactions[0].id == record.id and record.to_from_store != 'to_store':
                    raise ValidationError(_("[Transaction Model] The first transaction for an item must be to store."))
            if hasattr(record, 'job_id') and record.job_id:
                job_transactions = self.search([('job_id', '=', record.job_id.id)], order='date_issue asc')
                if job_transactions and job_transactions[0].id == record.id and record.to_from_store != 'from_store':
                    raise ValidationError(_("[Transaction Model] The first transaction for a job must be from store."))

    @api.constrains('transaction_quantity_override')
    def _check_positive_quantity(self):
        """Validate that transaction quantity is positive."""
        for record in self:
            if record.transaction_quantity_override <= 0:
                raise ValidationError(_("[Transaction Model] Transaction quantity must be positive."))

    @api.constrains('transaction_quantity_override', 'item_id', 'to_from_store')
    def _check_quantity_sum(self):
        """Validate that transaction doesn't result in negative quantity."""
        for transaction in self:
            if transaction.item_id:
                other_transactions = self.search([('item_id', '=', transaction.item_id.id), ('id', '!=', transaction.id)])
                current_quantity = sum(t.transaction_quantity if t.to_from_store == 'to_store' else -t.transaction_quantity for t in other_transactions)
                current_quantity += transaction.transaction_quantity if transaction.to_from_store == 'to_store' else -transaction.transaction_quantity
                if current_quantity < 0:
                    raise ValidationError(_("[Transaction Model] This transaction would result in negative quantity for item %s. Current quantity would be: %.2f") % (transaction.item_id.name, current_quantity))

    @api.onchange('item_id')
    def _onchange_item_id(self):
        pass  # Remove all automatic overrides

    @api.constrains('receipt_id')
    def _check_receipt_uniqueness(self):
        """Validate that a transaction is linked to at most one receipt."""
        for record in self:
            if record.receipt_id and record.receipt_id.transaction_ids.filtered(lambda t: t.id != record.id and t.receipt_id == record.receipt_id):
                raise ValidationError(_("[Transaction Model] A transaction can only be linked to one receipt at a time."))


    def unlink(self):
        """Update batch computations on deletion and check receipt constraints."""

        """Prevent deletion of transactions linked to receipts."""
        for record in self:
            if record.receipt_id:
                raise ValidationError(_("Cannot delete transaction %s as it is linked to receipt %s.") % (record.name, record.receipt_id.name))

        affected_batches = self.mapped('batch_id')
        result = super().unlink()
        for batch in affected_batches:
            batch._compute_current_batch_quantity()
            batch.compute_active()
        return result

    def action_create_receipt(self):
        if not self:
            raise UserError(_("No transactions selected."))

        transactions = self.filtered(lambda t: not t.receipt_id)
        if not transactions:
            raise UserError(_("No valid transactions available. All selected transactions are already linked to receipts."))

        types = set(transactions.mapped('to_from_store'))
        if len(types) > 1:
            raise UserError(_("Selected transactions must all be of the same type (To Store or From Store)."))

        transactions = self.env['kojto.warehouses.transactions'].search([
            ('id', 'in', transactions.ids),
            ('receipt_id', '=', False)
        ])
        if not transactions:
            raise UserError(_("No valid transactions available after re-validation. Some transactions may have been linked concurrently."))

        with self.env.cr.savepoint():
            receipt = self.env['kojto.warehouses.receipts'].create({
                'to_from_store': transactions[0].to_from_store,
                'store_id': transactions[0].batch_id.store_id.id or self.env['kojto.base.stores'].search([('active', '=', True)], limit=1).id,
                'issued_to': transactions[0].issued_by.name if transactions[0].issued_by else _('Not Specified'),
                'transaction_ids': [(6, 0, transactions.ids)],
                'description': _('Created from transactions: %s') % ', '.join(transactions.mapped('name'))
            })
            # Update transactions with receipt
            transactions.write({'receipt_id': receipt.id})

        return {
            'name': _('Receipt'),
            'type': 'ir.actions.act_window',
            'res_model': 'kojto.warehouses.receipts',
            'view_mode': 'form',
            'res_id': receipt.id,
            'target': 'current',
        }

    @api.depends('item_id', 'item_id.item_type', 'item_id.weight', 'transaction_quantity_override')
    def compute_transaction_quantity(self):
        """Compute the transaction quantity based on item type."""
        for rec in self:
            if not rec.item_id:
                rec.transaction_quantity = rec.transaction_quantity_override
                continue

            if not rec.item_id.exists():
                continue

            # Force refresh item from database
            item = self.env['kojto.warehouses.items'].browse(rec.item_id.id)

            if item.item_type in ['sheet', 'bar']:
                rec.transaction_quantity = item.weight
            else:
                rec.transaction_quantity = float(rec.transaction_quantity_override)

        return {}

    @api.onchange('transaction_quantity_override')
    def _onchange_transaction_quantity_override(self):
        """Handle override changes."""
        pass

    @api.depends('item_id', 'item_id.name', 'item_id.item_type', 'item_id.weight', 'item_id.length', 'item_id.width', 'item_id.material_id', 'item_id.profile_id', 'item_id.thickness', 'item_id.part_type', 'transaction_quantity', 'transaction_unit_id', 'to_from_store', 'name')
    def _compute_transaction_summary(self):
        """Compute a summary of the transaction."""
        for rec in self:
            rec.transaction_summary = f"Transaction: {rec.name}, Item: {rec.item_id.name}, Type: {rec.item_id.item_type}, Quantity: {rec.transaction_quantity}, Unit: {rec.transaction_unit_id.name or 'N/A'}"

    def action_open_transaction_form(self):
        """Open the transaction form in an inline dialog."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Edit Transaction' if self.id else 'New Transaction',
            'res_model': 'kojto.warehouses.transactions',
            'view_mode': 'form',
            'view_id': self.env.ref('kojto_warehouses.view_kojto_warehouses_transactions_inline_form').id,
            'res_id': self.id,
            'target': 'new',  # Opens in a modal dialog
            'context': {
                'default_batch_id': self.batch_id.id,
                'default_item_id': self.item_id.id,
                'default_to_from_store': self.to_from_store or 'from_store',
            }
        }

    def action_save_transaction(self):
        """Save the transaction from the dialog."""
        self.ensure_one()
        return {'type': 'ir.actions.act_window_close'}

    @api.depends('item_id', 'item_id.item_type')
    def _compute_is_part_type(self):
        """Compute whether the item is a part type."""
        for rec in self:
            rec.is_part_type = rec.item_id and rec.item_id.item_type == 'part'

    @api.depends('batch_id', 'batch_id.unit_price_converted', 'transaction_quantity', 'date_issue', 'to_from_store')
    def _compute_transaction_value_pre_vat(self):
        """Compute pre-VAT transaction values in EUR."""
        for rec in self:
            if not rec.batch_id or not rec.batch_id.unit_price_converted or rec.transaction_quantity <= 0:
                rec.transaction_value_pre_vat_eur = 0.0
                continue

            # Get exchange rate for transaction date
            exchange_rate = self._get_exchange_rate_to_eur(rec.date_issue)

            # Calculate value in EUR (pre-VAT) directly
            value_eur = rec.transaction_quantity * rec.batch_id.unit_price_converted * exchange_rate

            # For 'from_store' transactions, values are negative
            if rec.to_from_store == 'from_store':
                rec.transaction_value_pre_vat_eur = -value_eur
            else:
                rec.transaction_value_pre_vat_eur = value_eur

    def _get_exchange_rate_to_eur(self, date):
        """Get exchange rate from BGN to EUR for a given date."""
        if not date:
            return 0.51129  # Fallback rate

        bgn_currency = self.env['res.currency'].search([('name', '=', 'BGN')], limit=1)
        eur_currency = self.env['res.currency'].search([('name', '=', 'EUR')], limit=1)

        if not bgn_currency or not eur_currency:
            return 0.51129  # Fallback: 1 BGN = 0.51129 EUR

        # Try to get exchange rate from exchange model
        exchange_rate = self.env['kojto.base.currency.exchange'].search([
            ('base_currency_id', '=', bgn_currency.id),
            ('target_currency_id', '=', eur_currency.id),
            ('datetime', '<=', date),
        ], order='datetime desc', limit=1)

        if exchange_rate:
            return exchange_rate.exchange_rate

        # Fallback to hardcoded rate: 1 BGN = 0.51129 EUR
        return 0.51129

    @api.depends()
    def _compute_currency_id(self):
        """Always use EUR currency for monetary widget"""
        eur_currency = self.env.ref('base.EUR', raise_if_not_found=False)
        for rec in self:
            rec.currency_id = eur_currency.id if eur_currency else False

    def action_recompute_transaction_values(self):
        """Recompute transaction value fields for selected transactions"""
        # Force recomputation by writing to a dependency field
        # This will trigger the compute method for stored computed fields
        count = len(self)
        for transaction in self:
            # Write to date_issue (a dependency) to trigger recomputation
            # This will cause _compute_transaction_value_pre_vat to run
            transaction.write({'date_issue': transaction.date_issue})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': f'Transaction values recomputed for {count} transaction(s).',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_recompute_identifier_id(self):
        """Recompute identifier_id field for selected transactions"""
        count = len(self)
        # Recompute stored related field by reading from source and updating
        for transaction in self:
            identifier_id = False
            if transaction.batch_id and transaction.batch_id.invoice_content_id and transaction.batch_id.invoice_content_id.identifier_id:
                identifier_id = transaction.batch_id.invoice_content_id.identifier_id.identifier
            # Update the stored value directly
            transaction.env.cr.execute(
                "UPDATE kojto_warehouses_transactions SET identifier_id = %s WHERE id = %s",
                (identifier_id, transaction.id)
            )
        # Invalidate cache to refresh UI
        self.invalidate_recordset(['identifier_id'])

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': f'Identifier ID recomputed for {count} transaction(s).',
                'type': 'success',
                'sticky': False,
            }
        }
