#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Recompute Power Meter Reading Values Tool (via XML-RPC)
Recalculates:
1. Energy consumption (imported_kwh, exported_kwh) with counter ROLLOVER handling
2. Energy values (imported_kwh_value, exported_kwh_value) based on time-based base prices
3. Price components (price_per_mwh_eur, base_price_per_mwh_import_eur, base_price_per_mwh_export_eur)

Usage:
    /opt/odoo18/venv/bin/python /opt/odoo18/custom/addons/kojto_energy_management/utils/recompute_reading_values_xmlrpc.py --auto --db kojto
    python recompute_reading_values_xmlrpc.py --db kojto --start-date "2025-10-01 00:00:00" --end-date "2025-10-20 23:59:59"
    python recompute_reading_values_xmlrpc.py --db kojto --device-id 1 --price-type import
    python recompute_reading_values_xmlrpc.py --db kojto --batch-size 1000
"""

import sys
import argparse
import xmlrpc.client
import os
import configparser
from datetime import datetime, timedelta


class ReadingValuesRecomputer:
    """Recompute power meter reading values via XML-RPC"""

    def __init__(self, odoo_url='http://localhost:8069', db='kojto', username=None, password=None, api_key=None):
        self.odoo_url = odoo_url
        self.db = db
        self.username = username
        self.password = password
        self.api_key = api_key
        self.uid = None
        self.models = None
        self.auth = None  # Will store the authentication method to use

    def connect_to_odoo(self):
        """Connect to Odoo via XML-RPC"""
        print(f"Connecting to Odoo at {self.odoo_url}...")

        try:
            # Try to read credentials from Odoo config file first
            config_file = '/etc/odoo18.conf'

            username = None
            auth_method = None

            # Priority 1: Try config file
            if os.path.exists(config_file):
                print(f"Reading credentials from {config_file}...")
                config = configparser.ConfigParser()
                config.read(config_file)

                if 'options' in config:
                    if 'xml_rpc_user' in config['options']:
                        username = config['options']['xml_rpc_user']
                        print(f"✓ Read xml_rpc_user from config: {username}")

                    if 'xml_rpc_password' in config['options']:
                        auth_method = config['options']['xml_rpc_password']
                        print("✓ Read xml_rpc_password from config")

            # Priority 2: Use provided arguments (override config)
            if self.username:
                username = self.username
                print(f"Using provided username: {username}")

            if self.api_key:
                auth_method = self.api_key
                print("Using provided API key")
            elif self.password:
                auth_method = self.password
                print("Using provided password")

            # Priority 3: Defaults
            if not username:
                username = 'admin'
                print("Warning: No username found, defaulting to 'admin'")

            if not auth_method:
                print("✗ No credentials provided!")
                print("\nPlease add XML-RPC credentials to /etc/odoo18.conf:")
                print("  xml_rpc_user = admin")
                print("  xml_rpc_password = your_password_or_api_key")
                print("\nOr provide credentials via command line arguments:")
                print("  --username admin --password your_password")
                print("  --username admin --api-key your_api_key")
                return False

            # Connect to Odoo
            common = xmlrpc.client.ServerProxy(f'{self.odoo_url}/xmlrpc/2/common')
            self.uid = common.authenticate(self.db, username, auth_method, {})

            if not self.uid:
                print("✗ Authentication failed!")
                print(f"Username: {username}")
                print("Please check your credentials.")
                return False

            # Store authentication method for future use
            self.auth = auth_method

            self.models = xmlrpc.client.ServerProxy(f'{self.odoo_url}/xmlrpc/2/object')
            print(f"✓ Connected to Odoo as user: {username} (uid={self.uid})")
            return True

        except Exception as e:
            print(f"✗ Error connecting to Odoo: {e}")
            return False

    def recompute_readings(self, start_date=None, end_date=None, device_id=None, batch_size=500, price_type=None):
        """
        Recompute energy consumption and values for readings
        - Energy consumption (kWh) with counter rollover handling
        - Energy values (EUR) based on time-based base prices

        Args:
            start_date: Start date filter (datetime string or None for all)
            end_date: End date filter (datetime string or None for all)
            device_id: Specific device ID to recompute (None for all devices)
            batch_size: Number of records to process in each batch
            price_type: 'import' or 'export' - only recompute readings with non-zero consumption of this type
        """
        print("\n" + "="*80)
        print("POWER METER READINGS FULL RECOMPUTATION")
        print("(Energy consumption with rollover + Energy values with prices)")
        print("="*80)

        try:
            # Build domain for filtering readings
            domain = []

            if start_date:
                domain.append(('datetime_utc', '>=', start_date))
                print(f"Start Date: {start_date}")

            if end_date:
                domain.append(('datetime_utc', '<=', end_date))
                print(f"End Date: {end_date}")

            if device_id:
                domain.append(('power_meter_id', '=', device_id))
                print(f"Device ID: {device_id}")

            # Filter by price type - only recompute readings with non-zero consumption
            if price_type == 'import':
                domain.append(('imported_kwh', '!=', 0))
                print(f"Price Type: Import (only non-zero imported_kwh)")
            elif price_type == 'export':
                domain.append(('exported_kwh', '!=', 0))
                print(f"Price Type: Export (only non-zero exported_kwh)")

            # Count total records
            total_count = self.models.execute_kw(
                self.db, self.uid, self.auth,
                'kojto.energy.management.power.meter.readings',
                'search_count',
                [domain]
            )

            print(f"\nTotal readings to recompute: {total_count}")

            if total_count == 0:
                print("No readings found matching the criteria.")
                return

            # Get all reading IDs
            reading_ids = self.models.execute_kw(
                self.db, self.uid, self.auth,
                'kojto.energy.management.power.meter.readings',
                'search',
                [domain],
                {'order': 'datetime_utc asc'}
            )

            print(f"Found {len(reading_ids)} reading IDs")
            print(f"Processing in batches of {batch_size}...")
            print("-"*80)

            # Process in batches
            total_processed = 0
            total_failed = 0
            batch_num = 0

            for i in range(0, len(reading_ids), batch_size):
                batch_num += 1
                batch_ids = reading_ids[i:i+batch_size]

                print(f"\nBatch {batch_num}: Processing {len(batch_ids)} readings (IDs {batch_ids[0]} to {batch_ids[-1]})...")

                try:
                    # Read the records to trigger recomputation
                    # When we read computed fields, Odoo automatically recalculates them
                    # But we need to explicitly write to trigger stored computed fields

                    # Get the records
                    records = self.models.execute_kw(
                        self.db, self.uid, self.auth,
                        'kojto.energy.management.power.meter.readings',
                        'read',
                        [batch_ids],
                        {'fields': ['id', 'datetime_utc', 'power_meter_id', 'imported_kwh', 'exported_kwh']}
                    )

                    # Trigger FULL recomputation by calling the action method
                    # This will recalculate:
                    # 1. Energy consumption (imported_kwh, exported_kwh) with rollover logic
                    # 2. Energy values (imported_kwh_value, exported_kwh_value) with time-based prices
                    # 3. Price components (price_per_mwh_eur, base_price_per_mwh_import_eur, base_price_per_mwh_export_eur)
                    result = self.models.execute_kw(
                        self.db, self.uid, self.auth,
                        'kojto.energy.management.power.meter.readings',
                        'action_recalculate_all',
                        [batch_ids]
                    )

                    total_processed += len(batch_ids)
                    print(f"  ✓ Batch {batch_num} completed: {len(batch_ids)} readings recomputed")
                    print(f"  Progress: {total_processed}/{total_count} ({100*total_processed/total_count:.1f}%)")

                except Exception as e:
                    total_failed += len(batch_ids)
                    print(f"  ✗ Batch {batch_num} failed: {e}")

            # Summary
            print("\n" + "="*80)
            print("RECOMPUTATION SUMMARY")
            print("="*80)
            print(f"Total readings processed: {total_processed}")
            print(f"Total failures: {total_failed}")
            print(f"Success rate: {100*(total_processed-total_failed)/total_processed:.1f}%")
            print("="*80)

            return True

        except Exception as e:
            print(f"\n✗ Error during recomputation: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_device_list(self):
        """Get list of all power meter devices"""
        try:
            devices = self.models.execute_kw(
                self.db, self.uid, self.auth,
                'kojto.energy.management.devices',
                'search_read',
                [[('device_type', '=', 'power_meter')]],
                {'fields': ['id', 'name', 'exchange']}
            )

            print("\n" + "="*80)
            print("AVAILABLE POWER METER DEVICES")
            print("="*80)
            for device in devices:
                print(f"ID: {device['id']:3d} | Name: {device['name']:30s} | Exchange: {device.get('exchange', 'N/A')}")
            print("="*80)

            return devices
        except Exception as e:
            print(f"✗ Error fetching device list: {e}")
            return []

    def get_base_prices_summary(self, device_id=None):
        """Get summary of base prices configuration"""
        try:
            domain = []
            if device_id:
                domain.append(('device_id', '=', device_id))

            base_prices = self.models.execute_kw(
                self.db, self.uid, self.auth,
                'kojto.energy.management.base.prices',
                'search_read',
                [domain],
                {'fields': ['device_id', 'price_type', 'start_date', 'base_price_eur_per_mwh'], 'order': 'device_id, price_type, start_date'}
            )

            print("\n" + "="*80)
            print("BASE PRICES CONFIGURATION")
            print("="*80)

            if not base_prices:
                print("No base prices configured!")
            else:
                current_device = None
                for bp in base_prices:
                    device_name = bp['device_id'][1] if bp['device_id'] else 'Unknown'
                    if current_device != device_name:
                        current_device = device_name
                        print(f"\nDevice: {device_name}")

                    print(f"  {bp['price_type']:6s} | Start: {bp['start_date']} | Price: {bp['base_price_eur_per_mwh']:.2f} EUR/MWh")

            print("="*80)

            return base_prices
        except Exception as e:
            print(f"✗ Error fetching base prices: {e}")
            return []


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Recompute power meter reading values based on new base prices')

    parser.add_argument('--db', required=True, help='Odoo database name')
    parser.add_argument('--url', default='http://localhost:8069', help='Odoo URL (default: http://localhost:8069)')
    parser.add_argument('--username', help='Odoo username (default: read from /etc/odoo18.conf)')
    parser.add_argument('--password', help='Odoo password')
    parser.add_argument('--api-key', help='Odoo API key (preferred over password)')

    parser.add_argument('--start-date', help='Start date (YYYY-MM-DD HH:MM:SS)')
    parser.add_argument('--end-date', help='End date (YYYY-MM-DD HH:MM:SS)')
    parser.add_argument('--device-id', type=int, help='Specific device ID to recompute')
    parser.add_argument('--batch-size', type=int, default=500, help='Batch size for processing (default: 500)')
    parser.add_argument('--price-type', choices=['import', 'export'], help='Only recompute readings with non-zero consumption of this type (import or export)')

    parser.add_argument('--auto', action='store_true', help='Auto mode: recompute all readings from the last 30 days')
    parser.add_argument('--list-devices', action='store_true', help='List all available power meter devices')
    parser.add_argument('--show-prices', action='store_true', help='Show base prices configuration')

    args = parser.parse_args()

    # Create recomputer instance
    recomputer = ReadingValuesRecomputer(
        odoo_url=args.url,
        db=args.db,
        username=args.username,
        password=args.password,
        api_key=args.api_key
    )

    # Connect to Odoo
    if not recomputer.connect_to_odoo():
        sys.exit(1)

    # List devices if requested
    if args.list_devices:
        recomputer.get_device_list()
        return

    # Show base prices if requested
    if args.show_prices:
        recomputer.get_base_prices_summary(args.device_id)
        return

    # Determine date range
    start_date = args.start_date
    end_date = args.end_date

    if args.auto:
        # Auto mode: last 30 days
        end_date = datetime.now().strftime('%Y-%m-%d 23:59:59')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d 00:00:00')
        print("\nAuto mode: Recomputing readings from last 30 days")

    # Recompute readings
    success = recomputer.recompute_readings(
        start_date=start_date,
        end_date=end_date,
        device_id=args.device_id,
        batch_size=args.batch_size,
        price_type=args.price_type
    )

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

