#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Recompute Employee Subcode Rates and Time Tracking Computed Fields Tool (via XML-RPC)

This script runs two recomputations in sequence:
1. Employee Subcode Rates: hour_rate_in_BGN, hour_rate_in_EUR (in batches of 10)
2. Time Tracking: credited_subcode_id, value_in_BGN, value_in_EUR

Usage:
    python3 /opt/odoo18/custom/addons/kojto_hr/recompute_subcode_rates_and_time_tracking_xmlrpc.py --db kojto
    python3 recompute_subcode_rates_and_time_tracking_xmlrpc.py --db kojto --start-date "2025-01-01 00:00:00" --end-date "2025-12-31 23:59:59"
    python3 recompute_subcode_rates_and_time_tracking_xmlrpc.py --db kojto --employee-id 1
    python3 recompute_subcode_rates_and_time_tracking_xmlrpc.py --db kojto --auto
    python3 recompute_subcode_rates_and_time_tracking_xmlrpc.py --db kojto --user admin --password your_password
    python3 recompute_subcode_rates_and_time_tracking_xmlrpc.py --db kojto --user admin --api-key your_api_key
"""

import sys
import argparse
import xmlrpc.client
import os
import configparser
from datetime import datetime, timedelta


class SubcodeRatesRecomputer:
    """Recompute employee subcode rates computed fields via XML-RPC"""

    def __init__(self, odoo_url='http://localhost:8069', db='kojto', username=None, password=None):
        self.odoo_url = odoo_url
        self.db = db
        self.username = username
        self.password = password
        self.uid = None
        self.models = None

    def connect_to_odoo(self):
        """Connect to Odoo via XML-RPC"""
        print(f"Connecting to Odoo at {self.odoo_url}...")

        try:
            common = xmlrpc.client.ServerProxy(f'{self.odoo_url}/xmlrpc/2/common', allow_none=True)
            version = common.version()
            print(f"Odoo version: {version.get('server_version')}")
            self.uid = common.authenticate(self.db, self.username, self.password, {})

            if not self.uid:
                print("✗ Authentication failed!")
                print(f"Username: {self.username}")
                print("Please check your credentials.")
                return False

            self.models = xmlrpc.client.ServerProxy(f'{self.odoo_url}/xmlrpc/2/object', allow_none=True)
            print(f"✓ Connected to Odoo as user: {self.username} (uid={self.uid})")
            return True

        except Exception as e:
            print(f"✗ Error connecting to Odoo: {e}")
            return False

    def recompute_fields(self, start_date=None, end_date=None, employee_id=None, batch_size=10):
        """
        Recompute hour_rate_in_BGN and hour_rate_in_EUR for employee subcode rate records

        Args:
            start_date: Start date filter (datetime string or None for all)
            end_date: End date filter (datetime string or None for all)
            employee_id: Specific employee ID to recompute (None for all employees)
            batch_size: Number of records to process in each batch (default: 10)
        """
        print("\n" + "="*80)
        print("EMPLOYEE SUBCODE RATES FIELDS RECOMPUTATION")
        print("(hour_rate_in_BGN, hour_rate_in_EUR)")
        print("="*80)

        try:
            # Build domain for filtering subcode rate records
            domain = []

            if start_date:
                domain.append(('datetime_start', '>=', start_date))
                print(f"Start Date: {start_date}")

            if end_date:
                domain.append(('datetime_start', '<=', end_date))
                print(f"End Date: {end_date}")

            if employee_id:
                domain.append(('employee_id', '=', employee_id))
                print(f"Employee ID: {employee_id}")

            # Count total records
            total_count = self.models.execute_kw(
                self.db, self.uid, self.password,
                'kojto.hr.employee.subcode.rates',
                'search_count',
                [domain]
            )

            print(f"\nTotal subcode rate records to recompute: {total_count}")

            if total_count == 0:
                print("No subcode rate records found matching the criteria.")
                return True

            # Get all subcode rate IDs
            rate_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'kojto.hr.employee.subcode.rates',
                'search',
                [domain],
                {'order': 'datetime_start desc'}
            )

            print(f"Found {len(rate_ids)} subcode rate record IDs")
            print(f"Processing in batches of {batch_size}...")
            print("-"*80)

            # Process in batches
            total_processed = 0
            total_failed = 0
            batch_num = 0

            for i in range(0, len(rate_ids), batch_size):
                batch_num += 1
                batch_ids = rate_ids[i:i+batch_size]

                print(f"\nBatch {batch_num}: Processing {len(batch_ids)} records (IDs {batch_ids[0]} to {batch_ids[-1]})...")

                try:
                    # Call the batch recompute method
                    result = self.models.execute_kw(
                        self.db, self.uid, self.password,
                        'kojto.hr.employee.subcode.rates',
                        'recompute_hour_rates_batch',
                        [batch_ids]
                    )

                    total_processed += len(batch_ids)
                    message = result.get('message', 'Completed')
                    print(f"  ✓ Batch {batch_num} completed: {len(batch_ids)} records recomputed")
                    print(f"    {message}")
                    print(f"  Progress: {total_processed}/{total_count} ({100*total_processed/total_count:.1f}%)")

                except Exception as e:
                    total_failed += len(batch_ids)
                    print(f"  ✗ Batch {batch_num} failed: {e}")
                    import traceback
                    traceback.print_exc()

            # Summary
            print("\n" + "="*80)
            print("SUBCODE RATES RECOMPUTATION SUMMARY")
            print("="*80)
            print(f"Total records processed: {total_processed}")
            print(f"Total failures: {total_failed}")
            if total_processed > 0:
                print(f"Success rate: {100*(total_processed-total_failed)/total_processed:.1f}%")
            print("="*80)

            return True

        except Exception as e:
            print(f"\n✗ Error during subcode rates recomputation: {e}")
            import traceback
            traceback.print_exc()
            return False


class TimeTrackingRecomputer:
    """Recompute time tracking computed fields via XML-RPC"""

    def __init__(self, odoo_url='http://localhost:8069', db='kojto', username=None, password=None):
        self.odoo_url = odoo_url
        self.db = db
        self.username = username
        self.password = password
        self.uid = None
        self.models = None

    def connect_to_odoo(self):
        """Connect to Odoo via XML-RPC"""
        print(f"Connecting to Odoo at {self.odoo_url}...")

        try:
            common = xmlrpc.client.ServerProxy(f'{self.odoo_url}/xmlrpc/2/common', allow_none=True)
            version = common.version()
            print(f"Odoo version: {version.get('server_version')}")
            self.uid = common.authenticate(self.db, self.username, self.password, {})

            if not self.uid:
                print("✗ Authentication failed!")
                print(f"Username: {self.username}")
                print("Please check your credentials.")
                return False

            self.models = xmlrpc.client.ServerProxy(f'{self.odoo_url}/xmlrpc/2/object', allow_none=True)
            print(f"✓ Connected to Odoo as user: {self.username} (uid={self.uid})")
            return True

        except Exception as e:
            print(f"✗ Error connecting to Odoo: {e}")
            return False

    def recompute_fields(self, start_date=None, end_date=None, employee_id=None, batch_size=500):
        """
        Recompute credited_subcode_id, value_in_BGN, and value_in_EUR for time tracking records

        Args:
            start_date: Start date filter (datetime string or None for all)
            end_date: End date filter (datetime string or None for all)
            employee_id: Specific employee ID to recompute (None for all employees)
            batch_size: Number of records to process in each batch (default: 500)
        """
        print("\n" + "="*80)
        print("TIME TRACKING FIELDS RECOMPUTATION")
        print("(credited_subcode_id, value_in_BGN, value_in_EUR)")
        print("="*80)

        try:
            # Build domain for filtering time tracking records
            domain = []

            if start_date:
                domain.append(('datetime_start', '>=', start_date))
                print(f"Start Date: {start_date}")

            if end_date:
                domain.append(('datetime_start', '<=', end_date))
                print(f"End Date: {end_date}")

            if employee_id:
                domain.append(('employee_id', '=', employee_id))
                print(f"Employee ID: {employee_id}")

            # Count total records
            total_count = self.models.execute_kw(
                self.db, self.uid, self.password,
                'kojto.hr.time.tracking',
                'search_count',
                [domain]
            )

            print(f"\nTotal time tracking records to recompute: {total_count}")

            if total_count == 0:
                print("No time tracking records found matching the criteria.")
                return True

            # Get all time tracking IDs
            tracking_ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                'kojto.hr.time.tracking',
                'search',
                [domain],
                {'order': 'datetime_start asc'}
            )

            print(f"Found {len(tracking_ids)} time tracking record IDs")
            print(f"Processing in batches of {batch_size}...")
            print("-"*80)

            # Process in batches
            total_processed = 0
            total_failed = 0
            batch_num = 0

            for i in range(0, len(tracking_ids), batch_size):
                batch_num += 1
                batch_ids = tracking_ids[i:i+batch_size]

                print(f"\nBatch {batch_num}: Processing {len(batch_ids)} records (IDs {batch_ids[0]} to {batch_ids[-1]})...")

                try:
                    # Call the batch recompute method
                    result = self.models.execute_kw(
                        self.db, self.uid, self.password,
                        'kojto.hr.time.tracking',
                        'compute_value_in_BGN_and_EUR_batch',
                        [batch_ids]
                    )

                    total_processed += len(batch_ids)
                    message = result.get('message', 'Completed')
                    print(f"  ✓ Batch {batch_num} completed: {len(batch_ids)} records recomputed")
                    print(f"    {message}")
                    print(f"  Progress: {total_processed}/{total_count} ({100*total_processed/total_count:.1f}%)")

                except Exception as e:
                    total_failed += len(batch_ids)
                    print(f"  ✗ Batch {batch_num} failed: {e}")
                    import traceback
                    traceback.print_exc()

            # Summary
            print("\n" + "="*80)
            print("TIME TRACKING RECOMPUTATION SUMMARY")
            print("="*80)
            print(f"Total records processed: {total_processed}")
            print(f"Total failures: {total_failed}")
            if total_processed > 0:
                print(f"Success rate: {100*(total_processed-total_failed)/total_processed:.1f}%")
            print("="*80)

            return True

        except Exception as e:
            print(f"\n✗ Error during time tracking recomputation: {e}")
            import traceback
            traceback.print_exc()
            return False


def read_config():
    """Read XML-RPC credentials from config file"""
    cfg_path = "/etc/odoo18.conf"
    if not os.path.exists(cfg_path):
        return None, None
    cfg = configparser.ConfigParser()
    cfg.read(cfg_path)
    if "options" not in cfg:
        return None, None
    return cfg["options"].get("xml_rpc_user"), cfg["options"].get("xml_rpc_password")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Recompute employee subcode rates and time tracking computed fields')

    parser.add_argument('--db', required=True, help='Odoo database name')
    parser.add_argument('--odoo-url', default='http://localhost:8069', help='Odoo URL (default: http://localhost:8069)')
    parser.add_argument('--user', help='Odoo username')
    parser.add_argument('--password', help='Odoo password')
    parser.add_argument('--api-key', help='Odoo API key (used as password)')

    parser.add_argument('--start-date', help='Start date (YYYY-MM-DD HH:MM:SS)')
    parser.add_argument('--end-date', help='End date (YYYY-MM-DD HH:MM:SS)')
    parser.add_argument('--employee-id', type=int, help='Specific employee ID to recompute')
    parser.add_argument('--subcode-rates-batch-size', type=int, default=10, help='Batch size for subcode rates processing (default: 10)')
    parser.add_argument('--time-tracking-batch-size', type=int, default=500, help='Batch size for time tracking processing (default: 500)')

    parser.add_argument('--auto', action='store_true', help='Auto mode: recompute all records from the last 30 days')
    parser.add_argument('--skip-subcode-rates', action='store_true', help='Skip subcode rates recomputation')
    parser.add_argument('--skip-time-tracking', action='store_true', help='Skip time tracking recomputation')

    args = parser.parse_args()

    # Get credentials: command line args take priority, then config file
    username = args.user
    password = args.password or args.api_key
    if not username or not password:
        u, p = read_config()
        username = username or u
        password = password or p

    if not username or not password:
        print("✗ Odoo credentials missing")
        print("\nPlease add XML-RPC credentials to /etc/odoo18.conf:")
        print("  xml_rpc_user = admin")
        print("  xml_rpc_password = your_password_or_api_key")
        print("\nOr provide credentials via command line arguments:")
        print("  --user admin --password your_password")
        print("  --user admin --api-key your_api_key")
        sys.exit(1)

    # Determine date range
    start_date = args.start_date
    end_date = args.end_date

    if args.auto:
        # Auto mode: last 30 days
        end_date = datetime.now().strftime('%Y-%m-%d 23:59:59')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d 00:00:00')
        print("\nAuto mode: Recomputing records from last 30 days")

    # Step 1: Recompute Subcode Rates (in batches of 10)
    if not args.skip_subcode_rates:
        print("\n" + "="*80)
        print("STEP 1: RECOMPUTING SUBCODE RATES")
        print("="*80)

        subcode_recomputer = SubcodeRatesRecomputer(
            odoo_url=args.odoo_url,
            db=args.db,
            username=username,
            password=password
        )

        if not subcode_recomputer.connect_to_odoo():
            sys.exit(1)

        success_subcode = subcode_recomputer.recompute_fields(
            start_date=start_date,
            end_date=end_date,
            employee_id=args.employee_id,
            batch_size=args.subcode_rates_batch_size
        )

        if not success_subcode:
            print("\n✗ Subcode rates recomputation failed. Continuing with time tracking...")
    else:
        print("\nSkipping subcode rates recomputation (--skip-subcode-rates)")
        success_subcode = True

    # Step 2: Recompute Time Tracking Fields
    if not args.skip_time_tracking:
        print("\n" + "="*80)
        print("STEP 2: RECOMPUTING TIME TRACKING FIELDS")
        print("="*80)

        time_tracking_recomputer = TimeTrackingRecomputer(
            odoo_url=args.odoo_url,
            db=args.db,
            username=username,
            password=password
        )

        if not time_tracking_recomputer.connect_to_odoo():
            sys.exit(1)

        success_time_tracking = time_tracking_recomputer.recompute_fields(
            start_date=start_date,
            end_date=end_date,
            employee_id=args.employee_id,
            batch_size=args.time_tracking_batch_size
        )

        if not success_time_tracking:
            print("\n✗ Time tracking recomputation failed.")
    else:
        print("\nSkipping time tracking recomputation (--skip-time-tracking)")
        success_time_tracking = True

    # Final summary
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)
    if not args.skip_subcode_rates:
        print(f"Subcode Rates: {'✓ Completed' if success_subcode else '✗ Failed'}")
    if not args.skip_time_tracking:
        print(f"Time Tracking: {'✓ Completed' if success_time_tracking else '✗ Failed'}")
    print("="*80)

    sys.exit(0 if (success_subcode and success_time_tracking) else 1)


if __name__ == '__main__':
    main()

