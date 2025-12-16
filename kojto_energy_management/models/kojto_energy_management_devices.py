# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class KojtoEnergyManagementDevices(models.Model):
    _name = 'kojto.energy.management.devices'
    _description = 'Energy Management Devices (Power Meters, Inverters, etc.)'
    _order = 'name'

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'The device name must be unique!'),
    ]

    # Basic Information
    name = fields.Char(string='Name', required=True, index=True, help='Unique name for the device')

    device_type = fields.Selection([('power_meter', 'Power Meter'), ('inverter', 'Solar Inverter'), ('battery', 'Battery System'), ('ev_charger', 'EV Charger'), ('sensor', 'Sensor'), ('controller', 'Controller'), ('other', 'Other Device')], string='Device Type', required=True, default='power_meter', help='Type of device')

    protocol = fields.Selection([('modbus_tcp', 'Modbus TCP'), ('modbus_rtu', 'Modbus RTU'), ('http_api', 'HTTP API'), ('mqtt', 'MQTT'), ('snmp', 'SNMP'), ('custom_database', 'Custom Database'), ('other', 'Other Protocol')], string='Protocol', required=True, default='modbus_tcp', help='Communication protocol used by the device')

    # Connection Information
    domain_ip = fields.Char(string='Domain / IP', required=True, help='IP address or domain name of the device')
    port = fields.Integer(string='Port', default=502, required=True, help='Communication port (default: 502 for Modbus TCP)')
    unit = fields.Integer(string='Unit ID / Slave ID', default=1, help='Modbus unit identifier or slave ID (1-247)')
    active = fields.Boolean(string='Active', default=True, help='Set to false to disable this device')

    # MQTT Configuration (only applicable when protocol is 'mqtt')
    mqtt_broker_host = fields.Char(string='MQTT Broker Host', help='MQTT broker hostname or IP address')
    mqtt_broker_port = fields.Integer(string='MQTT Broker Port', default=1883, help='MQTT broker port (default: 1883 for non-SSL, 8883 for SSL)')
    mqtt_client_id = fields.Char(string='MQTT Client ID', help='Unique client identifier (leave empty for auto-generated)')
    mqtt_username = fields.Char(string='MQTT Username', help='Username for MQTT broker authentication (optional)')
    mqtt_password = fields.Char(string='MQTT Password', help='Password for MQTT broker authentication (optional)')
    mqtt_use_tls = fields.Boolean(string='Use TLS/SSL', default=False, help='Enable secure connection using TLS/SSL')
    mqtt_qos = fields.Selection([('0', 'QoS 0 (At most once)'), ('1', 'QoS 1 (At least once)'), ('2', 'QoS 2 (Exactly once)')], string='MQTT QoS Level', default='0', help='Quality of Service level for MQTT messages')
    mqtt_subscribe_topic = fields.Char(string='Subscribe Topic (Read)', help='MQTT topic to subscribe to for reading device data (supports wildcards: +, #)')
    mqtt_publish_topic = fields.Char(string='Publish Topic (Write)', help='MQTT topic to publish commands to (optional, only if you need to control the device)')
    mqtt_keepalive = fields.Integer(string='Keep Alive (seconds)', default=60, help='Maximum period in seconds between communications with the broker')
    mqtt_clean_session = fields.Boolean(string='Clean Session', default=True, help='Start with a clean session (no persistent connection state)')

    # Additional Information
    description = fields.Text(string='Description', help='Brief description of the device and its purpose')
    model = fields.Selection([
        # Power Meters
        ('frodexim_fsc100', 'Frodexim FSC100'),
        ('lovato_dmg_210', 'LOVATO DMG 210'),
        ('megarevo_mega250ts', 'Megarevo MEGA250TS'),
        ('promod_pro380_mod_ct', 'Promod PRO380 MOD CT'),
        ('eastron_sdm630mct', 'Eastron SDM630MCT'),
        ('acrel_adw300', 'Acrel ADW300'),
        # Solar Inverters
        ('solax_x3_60k_tl', 'SOLAX X3 60K TL'),
        ('huawei_sun2000_60k_tl', 'HUAWEI SUN2000 60KTL'),
        # Other
        ('other', 'Other'),
    ], string='Model', help='Device model')
    serial_number = fields.Char(string='Serial Number', help='Device serial number')

    # Pricing & Exchange (applicable for power meters)
    exchange = fields.Char(string='Exchange', size=25, default='IBEX-DAM', help='Energy exchange name (e.g., IBEX)')

    # Relationship to Base Prices
    base_price_ids = fields.One2many('kojto.energy.management.base.prices', 'device_id', string='Base Prices', help='Time-based base prices for imported and exported energy')
    base_price_count = fields.Integer(string='Base Price Count', compute='_compute_base_price_count',help='Number of base prices configured')
    current_import_base_price_eur = fields.Float(string='Current Import Base Price (EUR/MWh)', compute='_compute_current_base_prices', digits=(16, 2), help='Current base price for imported energy (valid now)')
    current_export_base_price_eur = fields.Float(string='Current Export Base Price (EUR/MWh)', compute='_compute_current_base_prices', digits=(16, 2), help='Current base price for exported energy (valid now)')

    # Counter Rollover Settings (for power meters with limited counter range)
    max_imported_kwh_counter_value = fields.Float(string='Max Imp. Counter (kWh)', digits=(16, 3), help='Maximum value for imported kWh counter before it resets to 0 (leave 0 for no limit)')
    max_exported_kwh_counter_value = fields.Float(string='Max Exp. Counter (kWh)', digits=(16, 3), help='Maximum value for exported kWh counter before it resets to 0 (leave 0 for no limit)')

    @api.constrains('port')
    def _check_port(self):
        for record in self:
            if record.port < 1 or record.port > 65535:
                raise ValidationError('Port must be between 1 and 65535')

    @api.constrains('unit')
    def _check_unit(self):
        for record in self:
            if record.unit < 1 or record.unit > 247:
                raise ValidationError('Modbus Unit ID must be between 1 and 247')

    @api.constrains('name')
    def _check_name_unique(self):
        """Ensure device name is unique"""
        for record in self:
            if record.name:
                # Search for other records with the same name (excluding current record)
                domain = [('name', '=', record.name), ('id', '!=', record.id)]
                duplicate = self.search(domain, limit=1)
                if duplicate:
                    raise ValidationError(
                        f'A device with the name "{record.name}" already exists!\n'
                        f'Device names must be unique. Please choose a different name.'
                    )

    @api.depends('base_price_ids')
    def _compute_base_price_count(self):
        """Compute the total number of base prices"""
        for record in self:
            record.base_price_count = len(record.base_price_ids)

    @api.depends('base_price_ids', 'base_price_ids.start_date', 'base_price_ids.base_price_eur_per_mwh', 'base_price_ids.price_type')
    def _compute_current_base_prices(self):
        """Compute current base prices (valid at current datetime)"""
        from datetime import datetime

        for record in self:
            current_datetime = fields.Datetime.now()
            base_price_model = self.env['kojto.energy.management.base.prices']

            # Get current import base price
            import_price = base_price_model.get_base_price_for_datetime(
                record.id,
                'import',
                current_datetime
            )
            record.current_import_base_price_eur = import_price.base_price_eur_per_mwh if import_price else 0.0

            # Get current export base price
            export_price = base_price_model.get_base_price_for_datetime(
                record.id,
                'export',
                current_datetime
            )
            record.current_export_base_price_eur = export_price.base_price_eur_per_mwh if export_price else 0.0

    def name_get(self):
        """Custom name_get to show name and IP"""
        result = []
        for record in self:
            name = f"{record.name} ({record.domain_ip})"
            result.append((record.id, name))
        return result

