#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hourly Reports MySQL to Odoo Sync Tool (via XML-RPC)
Transfers data from MySQL HourlyReports table to Odoo power meter readings

Features:
- Batch processing for optimal performance
- Automatic duplicate detection
- Counter rollover handling (automatic via Odoo computed fields)
  Configure max counter values in device settings for meters with limited ranges

Usage:
    /opt/odoo18/venv/bin/python /opt/odoo18/custom/addons/kojto_energy_management/utils/sync_hourly_reports_xmlrpc.py --auto --db kojto
    python sync_hourly_reports_xmlrpc.py --db kojto --start-date "2025-10-01 00:00:00" --end-date "2025-10-20 23:59:59"
"""

import sys
import argparse
import xmlrpc.client
import os
import configparser
import mysql.connector
from mysql.connector import Error
from datetime import datetime, timedelta

# Database configuration from incremental_power_data_sync.py
DB_CONFIG = {
    'host': '192.168.101.50',
    'database': 'braiko_db',
    'user': 'root',
    'password': 'password_for_nodered',
    'port': 3306
}

TABLE_HOURLY = 'HourlyReports'


class HourlyReportsSyncToOdoo:
    """Sync MySQL HourlyReports to Odoo via XML-RPC"""

    def __init__(self, odoo_url='http://localhost:8069', db='kojto', username=None, password=None, api_key=None):
        self.odoo_url = odoo_url
        self.db = db
        self.username = username
        self.password = password
        self.api_key = api_key
        self.uid = None
        self.models = None
        self.mysql_connection = None
        self.device_id_map = {}  # Map MySQL device ID to Odoo power_meter_id

    def connect_to_mysql(self):
        """Connect to MySQL database"""
        try:
            self.mysql_connection = mysql.connector.connect(**DB_CONFIG)
            if self.mysql_connection.is_connected():
                print(f"✓ Connected to MySQL database: {DB_CONFIG['database']}@{DB_CONFIG['host']}")
                return True
        except Error as e:
            print(f"✗ Error connecting to MySQL: {e}")
            return False

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
                raise Exception("No credentials provided. Set xml_rpc_user/xml_rpc_password in /etc/odoo18.conf or pass via arguments")

            print(f"Authenticating as: {username}")

            # Store credentials in instance for later use
            self.username = username
            self.password = auth_method

            # Authenticate
            common = xmlrpc.client.ServerProxy(f'{self.odoo_url}/xmlrpc/2/common', allow_none=True)

            print(f"Calling authenticate(db='{self.db}', user='{username}', password='***')...")
            self.uid = common.authenticate(self.db, username, auth_method, {})
            print(f"Authenticate returned: {self.uid}")

            if not self.uid:
                try:
                    version_info = common.version()
                    print(f"Server version: {version_info}")
                    print(f"Server is reachable but authentication failed")
                    print(f"Database: {self.db}")
                    print(f"Username: {username}")
                    print(f"Check that user exists and password is correct")
                except Exception as ver_err:
                    print(f"Cannot reach server: {ver_err}")

                raise Exception("Authentication failed - check credentials")

            # Get models proxy
            self.models = xmlrpc.client.ServerProxy(f'{self.odoo_url}/xmlrpc/2/object', allow_none=True)

            print(f"✓ Connected to Odoo as user ID: {self.uid}")
            return True

        except Exception as e:
            print(f"✗ Failed to connect to Odoo: {e}")
            import traceback
            print(traceback.format_exc())
            return False

    def build_device_id_map(self):
        """Build a mapping from MySQL device ID to Odoo power_meter_id"""
        print("\nBuilding device ID mapping (MySQL ID → Odoo power_meter_id)...")

        try:
            # Get all devices from MySQL
            cursor = self.mysql_connection.cursor()
            cursor.execute("SELECT DISTINCT Id FROM HourlyReports ORDER BY Id")
            mysql_ids = [row[0] for row in cursor.fetchall()]
            cursor.close()

            print(f"Found {len(mysql_ids)} unique device IDs in MySQL: {mysql_ids}")

            # Map MySQL ID to Odoo device - OPTIMIZED: Single batch call
            # Fetch all power meter and inverter devices at once (inverters can also report power readings)
            all_devices = self.models.execute_kw(
                self.db, self.uid, self.password,
                'kojto.energy.management.devices',
                'search_read',
                [[['device_type', 'in', ['power_meter', 'inverter']]]],
                {'fields': ['id', 'name', 'device_type']}
            )

            # Build a name-to-id and name-to-type mapping
            device_name_map = {device['name']: {'id': device['id'], 'type': device['device_type']} for device in all_devices}

            # Map MySQL IDs to Odoo device IDs
            for mysql_id in mysql_ids:
                # Try multiple search patterns
                search_patterns = [
                    mysql_id,  # Exact match
                    f"Power Meter {mysql_id}",  # With prefix
                ]

                found = False
                for pattern in search_patterns:
                    if pattern in device_name_map:
                        device_info = device_name_map[pattern]
                        odoo_device_id = device_info['id']
                        device_type = device_info['type']
                        self.device_id_map[mysql_id] = odoo_device_id
                        print(f"  ✓ Mapped MySQL ID '{mysql_id}' → Odoo device ID {odoo_device_id} ('{pattern}', type: {device_type})")
                        found = True
                        break

                if not found:
                    print(f"  ⚠ Warning: No Odoo device found for MySQL ID '{mysql_id}'")
                    print(f"     Tried patterns: {search_patterns}")
                    print(f"     Create an Odoo device (power_meter or inverter) with exact name '{mysql_id}'")

            if not self.device_id_map:
                print("\n⚠ ERROR: No device mappings found!")
                print("   Please create Odoo devices with names matching your MySQL device IDs:")
                for mysql_id in mysql_ids[:5]:  # Show first 5 as examples
                    print(f"   - Name: '{mysql_id}'")
                if len(mysql_ids) > 5:
                    print(f"   ... and {len(mysql_ids) - 5} more")
                return False

            print(f"\n✓ Successfully mapped {len(self.device_id_map)} device(s)")
            return True

        except Exception as e:
            print(f"✗ Error building device ID map: {e}")
            import traceback
            print(traceback.format_exc())
            return False

    def get_latest_reading_from_odoo(self, odoo_device_id):
        """Get the latest reading datetime for a specific device in Odoo"""
        try:
            record_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'kojto.energy.management.power.meter.readings',
                'search',
                [[['power_meter_id', '=', odoo_device_id]]],
                {'order': 'datetime_utc desc', 'limit': 1}
            )

            if record_ids:
                records = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'kojto.energy.management.power.meter.readings',
                    'read',
                    [record_ids],
                    {'fields': ['datetime_utc']}
                )

                if records and records[0].get('datetime_utc'):
                    latest_datetime_str = records[0]['datetime_utc']
                    # Parse datetime (format: 'YYYY-MM-DD HH:MM:SS')
                    latest_datetime = datetime.strptime(latest_datetime_str, '%Y-%m-%d %H:%M:%S')
                    return latest_datetime

            return None

        except Exception as e:
            print(f"  ✗ Error querying latest reading: {e}")
            return None

    def get_latest_reading_from_mysql(self, mysql_device_id):
        """Get the latest reading datetime for a specific device in MySQL HourlyReports"""
        try:
            cursor = self.mysql_connection.cursor()
            query = f"SELECT MAX(DateTimeUTC) as latest FROM {TABLE_HOURLY} WHERE Id = %s"
            cursor.execute(query, (mysql_device_id,))
            result = cursor.fetchone()
            cursor.close()

            if result and result[0]:
                # result[0] is already a datetime object from MySQL
                return result[0]

            return None

        except Error as e:
            print(f"  ✗ Error querying latest reading from MySQL: {e}")
            return None

    def fetch_hourly_reports_from_mysql(self, start_datetime=None, end_datetime=None, mysql_device_id=None):
        """
        Fetch HourlyReports from MySQL within a date range for a specific device.

        Args:
            start_datetime: If None, fetches ALL data (no lower limit) - used for inactive/new devices
            end_datetime: Upper limit (typically current time)
            mysql_device_id: Specific device ID to fetch (required for device-by-device processing)
        """
        try:
            cursor = self.mysql_connection.cursor()

            # Build query
            query = f"""
            SELECT Id, L1_A, L2_A, L3_A, L1_V, L2_V, L3_V, DateTimeUTC,
                   L1_L2_V, L2_L3_V, L3_L1_V, P_kW, Phi, F_Hz,
                   exp_kWh, imp_kWh, Tot_react_exp_kVArh, Tot_react_imp_kVArh
            FROM {TABLE_HOURLY}
            WHERE 1=1
            """

            params = []

            # Always filter by device ID (device-by-device basis)
            if mysql_device_id is not None:
                query += " AND Id = %s"
                params.append(mysql_device_id)

            # If start_datetime is None, no lower limit is applied (fetches ALL historical data)
            # This is used for inactive/new devices that have no existing readings in Odoo
            if start_datetime:
                query += " AND DateTimeUTC >= %s"
                params.append(start_datetime)

            if end_datetime:
                query += " AND DateTimeUTC <= %s"
                params.append(end_datetime)

            query += " ORDER BY DateTimeUTC ASC"

            # Debug: Print the query being executed
            if mysql_device_id:
                print(f"  🔍 MySQL Query for device '{mysql_device_id}':")
                print(f"     {query}")
                print(f"     Parameters: {params}")

            cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            results = cursor.fetchall()

            # Debug: Check if any data exists for this device at all
            if mysql_device_id and len(results) == 0:
                # Check latest record for this device (any time)
                check_query = f"SELECT MAX(DateTimeUTC) as latest FROM {TABLE_HOURLY} WHERE Id = %s"
                cursor.execute(check_query, (mysql_device_id,))
                latest_result = cursor.fetchone()
                if latest_result and latest_result[0]:
                    latest_in_mysql = latest_result[0]
                    print(f"  ⚠ Latest record in MySQL for '{mysql_device_id}': {latest_in_mysql}")
                    if start_datetime and latest_in_mysql < start_datetime:
                        print(f"     ⚠ Latest MySQL data ({latest_in_mysql}) is BEFORE requested start ({start_datetime})")
                        print(f"     💡 This device may need the incremental sync script to run first")
                else:
                    print(f"  ⚠ No data found in HourlyReports table for device '{mysql_device_id}' at all")
                    print(f"     💡 Check if data exists in PowerMeters table and run incremental_power_data_sync.py")

            records = []
            for row in results:
                records.append(dict(zip(columns, row)))

            cursor.close()
            return records

        except Error as e:
            print(f"✗ Error fetching data from MySQL: {e}")
            return []

    def create_readings_in_odoo(self, records):
        """Create power meter readings in Odoo via XML-RPC - OPTIMIZED with batching"""
        if not records:
            return 0, 0

        print(f"\nCreating {len(records)} reading(s) in Odoo...")

        created_count = 0
        skipped_count = 0
        error_count = 0

        # OPTIMIZATION 1: Pre-filter records by mapped devices
        valid_records = []
        for record in records:
            mysql_device_id = record['Id']
            if mysql_device_id not in self.device_id_map:
                skipped_count += 1
                continue
            valid_records.append(record)

        if not valid_records:
            print(f"✓ Created: 0, Skipped (no device mapping): {skipped_count}, Errors: 0")
            return 0, skipped_count

        # OPTIMIZATION 2: Batch duplicate checking per device
        # Group records by device for efficient duplicate checking
        records_by_device = {}
        for record in valid_records:
            mysql_device_id = record['Id']
            odoo_device_id = self.device_id_map[mysql_device_id]
            if odoo_device_id not in records_by_device:
                records_by_device[odoo_device_id] = []
            records_by_device[odoo_device_id].append(record)

        # Fetch existing datetimes per device (batch operation) - OPTIMIZED with date range
        existing_datetimes_by_device = {}

        # Get min/max dates from records to limit the query
        all_datetimes = []
        for record in valid_records:
            dt = record['DateTimeUTC']
            if isinstance(dt, datetime):
                all_datetimes.append(dt.strftime('%Y-%m-%d %H:%M:%S'))
            else:
                all_datetimes.append(str(dt))

        if all_datetimes:
            min_date = min(all_datetimes)
            max_date = max(all_datetimes)
            print(f"  Checking for duplicates in date range: {min_date} to {max_date}")

        for odoo_device_id in records_by_device.keys():
            try:
                # Only fetch readings in the date range we're about to insert
                domain = [['power_meter_id', '=', odoo_device_id]]
                if all_datetimes:
                    domain.append(['datetime_utc', '>=', min_date])
                    domain.append(['datetime_utc', '<=', max_date])

                existing_readings = self.models.execute_kw(
                    self.db, self.uid, self.password,
                    'kojto.energy.management.power.meter.readings',
                    'search_read',
                    [domain],
                    {'fields': ['datetime_utc']}
                )
                existing_datetimes_by_device[odoo_device_id] = {
                    r['datetime_utc'] for r in existing_readings
                }
                print(f"  Device {odoo_device_id}: Found {len(existing_datetimes_by_device[odoo_device_id])} existing readings in range")
            except Exception as e:
                print(f"  ⚠ Warning: Could not fetch existing readings for device {odoo_device_id}: {e}")
                existing_datetimes_by_device[odoo_device_id] = set()

        # OPTIMIZATION 3: Batch record creation
        records_to_create = []
        for record in valid_records:
            try:
                mysql_device_id = record['Id']
                odoo_device_id = self.device_id_map[mysql_device_id]

                # Format datetime
                datetime_utc = record['DateTimeUTC']
                if isinstance(datetime_utc, datetime):
                    datetime_utc_str = datetime_utc.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    datetime_utc_str = str(datetime_utc)

                # Check if already exists (using cached set)
                if datetime_utc_str in existing_datetimes_by_device.get(odoo_device_id, set()):
                    skipped_count += 1
                    continue

                # Prepare record for batch creation
                records_to_create.append({
                    'power_meter_id': odoo_device_id,
                    'datetime_utc': datetime_utc_str,
                    'l1_a': record.get('L1_A'),
                    'l2_a': record.get('L2_A'),
                    'l3_a': record.get('L3_A'),
                    'l1_v': record.get('L1_V'),
                    'l2_v': record.get('L2_V'),
                    'l3_v': record.get('L3_V'),
                    'l1_l2_v': record.get('L1_L2_V'),
                    'l2_l3_v': record.get('L2_L3_V'),
                    'l3_l1_v': record.get('L3_L1_V'),
                    'p_kw': record.get('P_kW'),
                    'phi': record.get('Phi'),
                    'f_hz': record.get('F_Hz'),
                    'exported_kwh_counter': record.get('exp_kWh'),
                    'imported_kwh_counter': record.get('imp_kWh'),
                    'tot_react_exp_kvarh': record.get('Tot_react_exp_kVArh'),
                    'tot_react_imp_kvarh': record.get('Tot_react_imp_kVArh'),
                })

            except Exception as e:
                error_count += 1
                print(f"  ✗ Error preparing record: {e}")
                continue

        # Batch create records (in chunks of 100 for better performance and progress feedback)
        batch_size = 100
        total_to_create = len(records_to_create)

        if total_to_create > 0:
            print(f"  Batch creating {total_to_create} new record(s)...")

            for i in range(0, total_to_create, batch_size):
                batch = records_to_create[i:i+batch_size]
                try:
                    self.models.execute_kw(
                        self.db, self.uid, self.password,
                        'kojto.energy.management.power.meter.readings',
                        'create',
                        [batch]
                    )
                    created_count += len(batch)
                    print(f"  Progress: {created_count}/{total_to_create} created...")
                except Exception as e:
                    error_count += len(batch)
                    print(f"  ✗ Error creating batch: {e}")

        print(f"✓ Created: {created_count}, Skipped (duplicates): {skipped_count}, Errors: {error_count}")
        return created_count, skipped_count


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Sync MySQL HourlyReports to Odoo via XML-RPC')
    parser.add_argument('--start-date', help='Start datetime (YYYY-MM-DD HH:MM:SS)')
    parser.add_argument('--end-date', help='End datetime (YYYY-MM-DD HH:MM:SS)')
    parser.add_argument('--auto', action='store_true', help='Auto-detect dates from Odoo (sync from latest to now)')
    parser.add_argument('--odoo-url', default='http://localhost:8069', help='Odoo URL')
    parser.add_argument('--db', required=True, help='Odoo database name')
    parser.add_argument('--user', help='Odoo username (default: read from config)')
    parser.add_argument('--password', help='Odoo password (default: read from /etc/odoo18.conf)')
    parser.add_argument('--api-key', help='Odoo API key (instead of password)')

    args = parser.parse_args()

    print("=" * 60)
    print("Hourly Reports MySQL → Odoo Sync Tool (XML-RPC)")
    print("=" * 60)
    print()

    # Create sync instance
    syncer = HourlyReportsSyncToOdoo(
        odoo_url=args.odoo_url,
        db=args.db,
        username=args.user,
        password=args.password,
        api_key=args.api_key
    )

    # Connect to MySQL
    if not syncer.connect_to_mysql():
        print("Failed to connect to MySQL")
        sys.exit(1)

    # Connect to Odoo
    if not syncer.connect_to_odoo():
        print("Failed to connect to Odoo")
        sys.exit(1)

    # Build device ID mapping
    if not syncer.build_device_id_map():
        print("Failed to build device ID mapping")
        sys.exit(1)

    # Determine date range
    start_datetime = None
    end_datetime = None

    if args.auto:
        print("\n" + "=" * 60)
        print("AUTO MODE: Detecting date range from Odoo...")
        print("=" * 60)

        # For each mapped device, find the latest reading and sync from there
        # IMPORTANT: Each device is processed individually (device-by-device basis)
        # Even inactive devices (with no existing readings in Odoo) will have ALL their data transferred
        total_created = 0
        total_skipped = 0

        print(f"Processing {len(syncer.device_id_map)} mapped device(s) individually...\n")

        for mysql_device_id, odoo_device_id in syncer.device_id_map.items():
            print(f"\n--- Processing MySQL Device ID {mysql_device_id} (Odoo ID {odoo_device_id}) ---")

            # Get latest reading from Odoo FOR THIS SPECIFIC DEVICE
            # This ensures each device is handled independently and we start from where we left off
            latest_odoo_datetime = syncer.get_latest_reading_from_odoo(odoo_device_id)

            # Also check latest in MySQL for informational purposes
            latest_mysql_datetime = syncer.get_latest_reading_from_mysql(mysql_device_id)

            if latest_mysql_datetime:
                print(f"  ℹ Latest record in MySQL: {latest_mysql_datetime}")
            else:
                print(f"  ⚠ No data found in MySQL for this device")
                print(f"  → Skipping this device")
                continue  # Skip to next device

            if latest_odoo_datetime:
                # Device has existing readings in Odoo: sync only new data after the latest reading
                start_datetime = latest_odoo_datetime + timedelta(seconds=1)  # Start after the last reading
                print(f"  ✓ Latest record in Odoo: {latest_odoo_datetime}")
                print(f"  → Will sync NEW data from: {start_datetime}")

                # Check if MySQL has newer data available
                if latest_mysql_datetime:
                    if latest_mysql_datetime < latest_odoo_datetime:
                        print(f"  ⚠ Warning: MySQL latest ({latest_mysql_datetime}) is older than Odoo latest ({latest_odoo_datetime})")
                        print(f"     This device may be up to date or MySQL data may be behind")
                    elif latest_mysql_datetime == latest_odoo_datetime:
                        print(f"  ℹ MySQL and Odoo are synchronized (both at {latest_mysql_datetime})")
                        print(f"     No new data to sync - device is up to date")
                    else:
                        # MySQL has newer data - this is the normal case
                        time_diff = latest_mysql_datetime - latest_odoo_datetime
                        print(f"  ✓ MySQL has newer data ({time_diff} ahead of Odoo)")
            else:
                # Device has NO existing readings (inactive/new device): sync ALL available data
                start_datetime = None
                print(f"  ⚠ Device has NO existing readings in Odoo (inactive/new device)")
                print(f"  → Will sync ALL available data from MySQL for this device")

            # Sync up to now (current time)
            end_datetime = datetime.now()
            print(f"  Syncing up to: {end_datetime}")

            # Fetch records for THIS SPECIFIC DEVICE from MySQL
            records = syncer.fetch_hourly_reports_from_mysql(
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                mysql_device_id=mysql_device_id  # Device-specific query
            )

            print(f"  Fetched {len(records)} record(s) from MySQL for this device")

            if records:
                created, skipped = syncer.create_readings_in_odoo(records)
                total_created += created
                total_skipped += skipped
                print(f"  ✓ Device sync complete: {created} created, {skipped} skipped")
            else:
                # Provide more helpful feedback when no records found
                if latest_odoo_datetime and latest_mysql_datetime:
                    if latest_mysql_datetime <= latest_odoo_datetime:
                        print(f"  ✓ Device is up to date - no new data in MySQL")
                    else:
                        print(f"  ⚠ No records found in MySQL for this device in the specified date range")
                        print(f"     This may indicate the incremental sync script needs to run to aggregate PowerMeters → HourlyReports")
                else:
                    print(f"  ⚠ No records found in MySQL for this device in the specified date range")

        print("\n" + "=" * 60)
        print(f"✓ AUTO SYNC COMPLETED")
        print(f"  Total Created: {total_created}")
        print(f"  Total Skipped: {total_skipped}")
        print("=" * 60)

    else:
        # Manual date range mode
        if not args.start_date or not args.end_date:
            print("ERROR: --start-date and --end-date required (or use --auto)")
            sys.exit(1)

        try:
            start_datetime = datetime.strptime(args.start_date, '%Y-%m-%d %H:%M:%S')
            end_datetime = datetime.strptime(args.end_date, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            print("ERROR: Invalid date format. Use 'YYYY-MM-DD HH:MM:SS'")
            sys.exit(1)

        print("\n" + "=" * 60)
        print(f"MANUAL MODE: Syncing from {start_datetime} to {end_datetime}")
        print("=" * 60)

        # Fetch all records in date range
        records = syncer.fetch_hourly_reports_from_mysql(
            start_datetime=start_datetime,
            end_datetime=end_datetime
        )

        print(f"\nFetched {len(records)} record(s) from MySQL")

        if records:
            created, skipped = syncer.create_readings_in_odoo(records)

            print("\n" + "=" * 60)
            print(f"✓ SYNC COMPLETED")
            print(f"  Total Created: {created}")
            print(f"  Total Skipped: {skipped}")
            print("=" * 60)
        else:
            print("No records found in the specified date range")

    # Close MySQL connection
    if syncer.mysql_connection and syncer.mysql_connection.is_connected():
        syncer.mysql_connection.close()
        print("\n✓ MySQL connection closed")


if __name__ == '__main__':
    main()
