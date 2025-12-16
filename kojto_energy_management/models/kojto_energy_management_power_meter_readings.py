# -*- coding: utf-8 -*-

import os
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError


class KojtoEnergyManagementPowerMeterReadings(models.Model):
    _name = 'kojto.energy.management.power.meter.readings'
    _description = 'Energy Management Power Meter Readings'
    _order = 'datetime_utc desc'

    # Reference to Device (Power Meter)
    power_meter_id = fields.Many2one('kojto.energy.management.devices', string='Power Meter', required=True, ondelete='cascade', index=True, help='Reference to the power meter/device that generated this reading')

    # Currency for monetary fields
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.ref('base.EUR').id, help='Currency for all monetary values (EUR)')

    # Timestamp
    datetime_utc = fields.Datetime(string='DateTime', required=True, index=True, help='Timestamp of the reading in UTC converted by Odoo in current TZ')
    datetime_utc_char = fields.Char(string='DateTime (UTC)', compute='_compute_datetime_utc_char', help='Datetime (char field) displayed as string without timezone conversion in UTC format')

    # Phase Current (Amperes)
    l1_a = fields.Float(string='L1 (A)', digits=(16, 3), help='L1 phase current in Amperes')
    l2_a = fields.Float(string='L2 (A)', digits=(16, 3), help='L2 phase current in Amperes')
    l3_a = fields.Float(string='L3 (A)', digits=(16, 3), help='L3 phase current in Amperes')

    # Phase Voltage (Volts)
    l1_v = fields.Float(string='L1 (V)', digits=(16, 2), help='L1 phase voltage in Volts')
    l2_v = fields.Float(string='L2 (V)', digits=(16, 2), help='L2 phase voltage in Volts')
    l3_v = fields.Float(string='L3 (V)', digits=(16, 2), help='L3 phase voltage in Volts')

    # Line Voltage (Volts)
    l1_l2_v = fields.Float(string='L1-L2 (V)', digits=(16, 2), help='L1-L2 line voltage in Volts')
    l2_l3_v = fields.Float(string='L2-L3 (V)', digits=(16, 2), help='L2-L3 line voltage in Volts')
    l3_l1_v = fields.Float(string='L3-L1 (V)', digits=(16, 2), help='L3-L1 line voltage in Volts')

    # Power and Frequency
    p_kw = fields.Float(string='Active (kW)', digits=(16, 3), help='Active power in kilowatts')
    phi = fields.Float(string='PFactor (Phi)', digits=(16, 3), help='Power factor (Cos φ)')
    f_hz = fields.Float(string='Freq (Hz)', digits=(16, 2), help='Frequency in Hertz')

    # Energy Counters (kWh)
    exported_kwh_counter = fields.Float(string='Exp. Counter (kWh)', digits=(16, 3), help='Total exported active energy counter in kilowatt-hours')
    imported_kwh_counter = fields.Float(string='Imp. Counter (kWh)', digits=(16, 3), help='Total imported active energy counter in kilowatt-hours')

    # Computed Energy Consumption (difference from previous reading)
    imported_kwh = fields.Float(string='Imp. (kWh)', digits=(16, 3), compute='_compute_energy_consumption', store=True, help='Imported energy since previous reading (difference)')
    exported_kwh = fields.Float(string='Exp. (kWh)', digits=(16, 3), compute='_compute_energy_consumption', store=True, help='Exported energy since previous reading (difference)')

    # Computed Energy Value in EUR
    imported_kwh_value = fields.Float(string='Imp. Value', digits=(16, 2), compute='_compute_energy_value', store=True, help='Monetary value of imported energy in EUR')
    exported_kwh_value = fields.Float(string='Exp. Value', digits=(16, 2), compute='_compute_energy_value', store=True, help='Monetary value of exported energy in EUR')

    # Price components (EUR per MWh)
    price_per_mwh_eur = fields.Float(string='Market Price (per MWh)', digits=(16, 2), compute='_compute_energy_value', store=True, help='Market price in EUR per MWh from exchange')
    base_price_per_mwh_import_eur = fields.Float(string='Base Import Price (per MWh)', digits=(16, 2), compute='_compute_energy_value', store=True, help='Base price for import in EUR per MWh')
    base_price_per_mwh_export_eur = fields.Float(string='Base Export Price (per MWh)', digits=(16, 2), compute='_compute_energy_value', store=True, help='Base price for export in EUR per MWh')

    # Reactive Energy (kVArh)
    tot_react_exp_kvarh = fields.Float(string='Exp. Reactive (kVArh)', digits=(16, 3), help='Total exported reactive energy in kilovar-hours')
    tot_react_imp_kvarh = fields.Float(string='Imp. Reactive (kVArh)', digits=(16, 3), help='Total imported reactive energy in kilovar-hours')

    @api.depends('datetime_utc')
    def _compute_datetime_utc_char(self):
        """Convert datetime_utc to string without timezone conversion"""
        for record in self:
            if record.datetime_utc:
                # Format datetime as string (YYYY-MM-DD HH:MM:SS)
                record.datetime_utc_char = record.datetime_utc.strftime('%Y-%m-%d %H:%M:%S')
            else:
                record.datetime_utc_char = ''

    @api.depends('power_meter_id', 'datetime_utc', 'imported_kwh_counter', 'exported_kwh_counter',
                 'power_meter_id.max_imported_kwh_counter_value', 'power_meter_id.max_exported_kwh_counter_value')
    def _compute_energy_consumption(self):
        """Compute energy consumption as difference from previous reading with rollover handling"""
        for record in self:
            if record.power_meter_id and record.datetime_utc:
                # Find the previous reading for this power meter
                previous_reading = self.search([
                    ('power_meter_id', '=', record.power_meter_id.id),
                    ('datetime_utc', '<', record.datetime_utc),
                    ('id', '!=', record.id)
                ], order='datetime_utc desc', limit=1)

                if previous_reading:
                    # Get max counter values from device (0 means no limit)
                    max_import = record.power_meter_id.max_imported_kwh_counter_value or 0.0
                    max_export = record.power_meter_id.max_exported_kwh_counter_value or 0.0

                    # Calculate imported energy with rollover handling
                    if record.imported_kwh_counter < previous_reading.imported_kwh_counter and max_import > 0:
                        # Rollover detected: counter reset to 0
                        record.imported_kwh = (max_import - previous_reading.imported_kwh_counter) + record.imported_kwh_counter
                    else:
                        # Normal calculation
                        record.imported_kwh = record.imported_kwh_counter - previous_reading.imported_kwh_counter

                    # Calculate exported energy with rollover handling
                    if record.exported_kwh_counter < previous_reading.exported_kwh_counter and max_export > 0:
                        # Rollover detected: counter reset to 0
                        record.exported_kwh = (max_export - previous_reading.exported_kwh_counter) + record.exported_kwh_counter
                    else:
                        # Normal calculation
                        record.exported_kwh = record.exported_kwh_counter - previous_reading.exported_kwh_counter
                else:
                    # No previous reading, consumption is 0
                    record.imported_kwh = 0.0
                    record.exported_kwh = 0.0
            else:
                record.imported_kwh = 0.0
                record.exported_kwh = 0.0

    @api.depends('imported_kwh', 'exported_kwh', 'power_meter_id', 'datetime_utc',
                 'power_meter_id.exchange')
    def _compute_energy_value(self):
        """Compute monetary value of energy consumption"""
        for record in self:
            # Initialize values
            record.imported_kwh_value = 0.0
            record.exported_kwh_value = 0.0
            record.price_per_mwh_eur = 0.0
            record.base_price_per_mwh_import_eur = 0.0
            record.base_price_per_mwh_export_eur = 0.0

            if not record.power_meter_id or not record.datetime_utc:
                continue

            try:
                # Get the exchange from the power meter
                exchange = record.power_meter_id.exchange
                if not exchange:
                    continue

                # Find the corresponding energy price for this datetime and exchange
                # Reading datetime is the END of the measurement period
                # So we match with the price period that ends closest to (or at) this time
                price_record = self.env['kojto.energy.management.prices'].search([
                    ('exchange', '=', exchange),
                    ('period_end_utc', '<=', record.datetime_utc)
                ], order='period_end_utc desc', limit=1)

                if price_record:
                    # Get the market price in EUR per MWh
                    market_price_eur_per_mwh = price_record.price_eur_per_mwh
                    record.price_per_mwh_eur = market_price_eur_per_mwh

                    # Get the base prices using the new time-based model
                    base_price_model = self.env['kojto.energy.management.base.prices']

                    # Find the import base price valid for this datetime
                    import_base_price_record = base_price_model.get_base_price_for_datetime(
                        record.power_meter_id.id,
                        'import',
                        record.datetime_utc
                    )
                    import_base_price = import_base_price_record.base_price_eur_per_mwh if import_base_price_record else 0.0
                    record.base_price_per_mwh_import_eur = import_base_price

                    # Find the export base price valid for this datetime
                    export_base_price_record = base_price_model.get_base_price_for_datetime(
                        record.power_meter_id.id,
                        'export',
                        record.datetime_utc
                    )
                    export_base_price = export_base_price_record.base_price_eur_per_mwh if export_base_price_record else 0.0
                    record.base_price_per_mwh_export_eur = export_base_price

                    # Calculate total price per MWh (market price + base price)
                    total_import_price_per_mwh = market_price_eur_per_mwh + import_base_price
                    total_export_price_per_mwh = market_price_eur_per_mwh + export_base_price

                    # Calculate value: (kWh * (price_per_MWh) / 1000)
                    # Divide by 1000 to convert kWh to MWh
                    record.imported_kwh_value = (record.imported_kwh * total_import_price_per_mwh) / 1000.0
                    record.exported_kwh_value = (record.exported_kwh * total_export_price_per_mwh) / 1000.0
            except Exception:
                # If any database error (cursor closed, etc.), keep values at 0.0
                # This can happen during concurrent transactions or when cursor is closed
                pass

    @api.constrains('power_meter_id', 'datetime_utc')
    def _check_unique_meter_datetime(self):
        """Ensure a reading for this power meter at this time is unique"""
        for record in self:
            if record.power_meter_id and record.datetime_utc:
                # Search for other records with the same meter and datetime (excluding current record)
                domain = [
                    ('power_meter_id', '=', record.power_meter_id.id),
                    ('datetime_utc', '=', record.datetime_utc),
                    ('id', '!=', record.id)
                ]
                duplicate = self.search(domain, limit=1)
                if duplicate:
                    raise ValidationError(
                        f'A reading for this power meter at this time already exists!\n'
                        f'Power Meter: {record.power_meter_id.name}\n'
                        f'DateTime (UTC): {record.datetime_utc}'
                    )

    def action_calculate_energy_values(self):
        """Recalculate energy values for selected readings"""
        for record in self:
            # Force recalculation by invalidating cache and recomputing
            record._compute_energy_value()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Energy Values Calculated',
                'message': f'Successfully calculated energy values for {len(self)} reading(s).',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_recalculate_all(self):
        """Recalculate both energy consumption (with rollover) and energy values for selected readings"""
        for record in self:
            # Force recalculation of energy consumption (imported_kwh, exported_kwh) - includes rollover logic
            record._compute_energy_consumption()
            # Force recalculation of energy values (imported_kwh_value, exported_kwh_value) - includes prices
            record._compute_energy_value()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Readings Recalculated',
                'message': f'Successfully recalculated consumption and values for {len(self)} reading(s).',
                'type': 'success',
                'sticky': False,
            }
        }

    def name_get(self):
        """Custom name_get to show meter name and timestamp"""
        result = []
        for record in self:
            name = f"{record.power_meter_id.name} - {record.datetime_utc}"
            result.append((record.id, name))
        return result

    def cron_sync_hourly_reports(self):
        """
        Scheduled action to sync hourly reports from MySQL
        Runs every 30 minutes
        """
        return self.action_sync_hourly_reports()

    def action_sync_hourly_reports(self):
        """
        Trigger MySQL HourlyReports sync daemon
        The daemon runs independently and communicates with Odoo via XML-RPC
        """
        # Get module path
        module_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        script_path = os.path.join(module_path, 'utils', 'sync_hourly_reports_xmlrpc.py')

        if not os.path.exists(script_path):
            raise UserError(f"Sync script not found at: {script_path}")

        try:
            # Get database name
            db_name = self.env.cr.dbname

            # Build command to run in background
            # Script will read credentials from /etc/odoo18.conf automatically
            # No passwords in code or command line!
            cmd = f"sudo -u odoo18 -H /opt/odoo18/venv/bin/python {script_path} --auto --db {db_name}"

            # Start in background (completely detached)
            os.system(f"nohup {cmd} > /tmp/hourly_reports_sync.log 2>&1 &")

            # Give the sync a moment to start and check for immediate errors
            import time
            time.sleep(2)

            # Check if there was an immediate configuration error
            if os.path.exists('/tmp/hourly_reports_sync.log'):
                with open('/tmp/hourly_reports_sync.log', 'r') as f:
                    log_content = f.read()
                    if 'No credentials provided' in log_content:
                        raise UserError(
                            "❌ XML-RPC Credentials Missing!\n\n"
                            "The hourly reports sync needs XML-RPC credentials to authenticate.\n\n"
                            "🔧 Fix: Add these lines to /etc/odoo18.conf:\n\n"
                            "xml_rpc_user = admin\n"
                            "xml_rpc_password = your_admin_password\n\n"
                            "📝 Then restart Odoo:\n"
                            "sudo systemctl restart odoo18\n\n"
                            "💡 Tip: Use an API key instead of password for better security.\n"
                            "Check log: /tmp/hourly_reports_sync.log"
                        )
                    elif 'Authentication failed' in log_content:
                        raise UserError(
                            "❌ Authentication Failed!\n\n"
                            "The XML-RPC credentials in /etc/odoo18.conf are incorrect.\n\n"
                            "🔧 Fix: Check these settings in /etc/odoo18.conf:\n\n"
                            "xml_rpc_user = admin\n"
                            "xml_rpc_password = your_correct_password\n\n"
                            "Then restart: sudo systemctl restart odoo18\n\n"
                            "Check log: /tmp/hourly_reports_sync.log"
                        )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '✓ Sync Started',
                    'message': 'Hourly reports sync is running in the background.\n'
                               'Records will appear automatically.\n\n'
                               '📊 Check progress: /tmp/hourly_reports_sync.log',
                    'type': 'success',
                    'sticky': False,
                }
            }

        except UserError:
            raise
        except Exception as e:
            raise UserError(f"Failed to start hourly reports sync daemon:\n{str(e)}")

