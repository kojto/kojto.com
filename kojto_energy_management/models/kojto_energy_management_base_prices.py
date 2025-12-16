# -*- coding: utf-8 -*-

import os
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError


class KojtoEnergyManagementBasePrices(models.Model):
    _name = 'kojto.energy.management.base.prices'
    _description = 'Energy Management Base Prices'
    _order = 'device_id, price_type, start_date desc'
    _sql_constraints = [
        ('unique_device_type_date',
         'UNIQUE(device_id, price_type, start_date)',
         'A base price for this device, price type, and start date already exists!'),
    ]

    device_id = fields.Many2one('kojto.energy.management.devices', string='Device', required=True, ondelete='cascade', index=True, help='Power meter device this base price applies to')
    price_type = fields.Selection([('import', 'Import'),('export', 'Export')], string='Price Type', required=True, index=True, help='Whether this is a base price for imported or exported energy')
    start_date = fields.Datetime(string='Start Date (UTC)', required=True, index=True, help='Date and time (UTC) from which this base price becomes valid')
    base_price_eur_per_mwh = fields.Float(string='Base Price per MWh (EUR)', digits=(16, 2), required=True, help='Base price in EUR per MWh')
    valid_until = fields.Datetime(string='Valid Until', compute='_compute_valid_until', help='This base price is valid until the next base price starts (or indefinitely if no successor)')
    notes = fields.Text(string='Notes', help='Additional notes about this base price')


    @api.depends('device_id', 'price_type', 'start_date')
    def _compute_valid_until(self):
        """Compute the end of validity period (start date of next base price)"""
        for record in self:
            if record.device_id and record.start_date:
                # Find the next base price for this device and price type
                next_price = self.search([
                    ('device_id', '=', record.device_id.id),
                    ('price_type', '=', record.price_type),
                    ('start_date', '>', record.start_date),
                    ('id', '!=', record.id)
                ], order='start_date asc', limit=1)

                if next_price:
                    record.valid_until = next_price.start_date
                else:
                    # No successor, valid indefinitely
                    record.valid_until = False
            else:
                record.valid_until = False

    @api.constrains('device_id', 'price_type', 'start_date')
    def _check_unique_device_type_date(self):
        """Ensure base price for this device, type, and date is unique"""
        for record in self:
            if record.device_id and record.start_date:
                # Search for other records with the same device, type, and date
                domain = [
                    ('device_id', '=', record.device_id.id),
                    ('price_type', '=', record.price_type),
                    ('start_date', '=', record.start_date),
                    ('id', '!=', record.id)
                ]
                duplicate = self.search(domain, limit=1)
                if duplicate:
                    raise ValidationError(
                        f'A base price for this device, price type, and start date already exists!\n'
                        f'Device: {record.device_id.name}\n'
                        f'Price Type: {dict(self._fields["price_type"].selection)[record.price_type]}\n'
                        f'Start Date: {record.start_date}'
                    )

    def name_get(self):
        """Custom name_get to show device, type, and date"""
        result = []
        for record in self:
            price_type_label = dict(self._fields['price_type'].selection)[record.price_type]
            name = f"{record.device_id.name} - {price_type_label} - {record.start_date}"
            result.append((record.id, name))
        return result

    @api.model
    def get_base_price_for_datetime(self, device_id, price_type, datetime_utc):
        """
        Get the applicable base price for a given device, price type, and datetime.
        Returns the base price record where start_date <= datetime_utc < next start_date
        """
        if not device_id or not price_type or not datetime_utc:
            return self.browse()

        try:
            # Find the base price that was active at the given datetime
            # The price is valid from its start_date until the next price's start_date
            base_price = self.search([
                ('device_id', '=', device_id),
                ('price_type', '=', price_type),
                ('start_date', '<=', datetime_utc)
            ], order='start_date desc', limit=1)

            return base_price
        except Exception:
            # If cursor is closed or any other DB error, return empty recordset
            # This can happen during concurrent transactions
            return self.browse()

    def action_recompute_affected_readings(self):
        """
        Trigger background recomputation of readings affected by this base price change.
        Only recomputes readings for the specific device and time period.
        """
        for record in self:
            if not record.device_id or not record.start_date:
                continue

            # Get module path
            module_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            script_path = os.path.join(module_path, 'utils', 'recompute_reading_values_xmlrpc.py')

            if not os.path.exists(script_path):
                raise UserError(f"Recompute script not found at: {script_path}")

            try:
                # Get database name
                db_name = self.env.cr.dbname

                # Determine the time period to recompute
                start_date_str = record.start_date.strftime('%Y-%m-%d %H:%M:%S')

                # If there's a valid_until date, use it; otherwise recompute everything after start_date
                end_date_str = ""
                if record.valid_until:
                    end_date_str = f"--end-date '{record.valid_until.strftime('%Y-%m-%d %H:%M:%S')}'"

                # Build command with specific device, date range, and price type
                cmd = (
                    f"sudo -u odoo18 -H /opt/odoo18/venv/bin/python {script_path} "
                    f"--db {db_name} "
                    f"--device-id {record.device_id.id} "
                    f"--start-date '{start_date_str}' "
                    f"{end_date_str} "
                    f"--price-type {record.price_type}"
                )

                # Start in background
                os.system(f"nohup {cmd} > /tmp/recompute_readings_{record.device_id.id}.log 2>&1 &")

                # Prepare message
                price_type_label = dict(self._fields['price_type'].selection)[record.price_type]
                period_info = f"from {start_date_str}"
                if record.valid_until:
                    period_info += f" to {record.valid_until.strftime('%Y-%m-%d %H:%M:%S')}"
                else:
                    period_info += " onwards"

                consumption_field = 'imported_kwh' if record.price_type == 'import' else 'exported_kwh'

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': '✓ Recomputation Started',
                        'message': f'Recalculating energy values for:\n'
                                   f'Device: {record.device_id.name}\n'
                                   f'Price Type: {price_type_label}\n'
                                   f'Period: {period_info}\n'
                                   f'Filter: Only readings with non-zero {consumption_field}\n\n'
                                   f'📊 Check progress: /tmp/recompute_readings_{record.device_id.id}.log',
                        'type': 'success',
                        'sticky': False,
                    }
                }

            except Exception as e:
                raise UserError(f"Failed to start recomputation:\n{str(e)}")

