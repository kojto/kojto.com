import mysql.connector
from mysql.connector import Error
from datetime import datetime, timedelta, timezone
import sys
import time

# Database configuration - UPDATE THESE WITH YOUR DETAILS
DB_CONFIG = {
    'host': '192.168.101.50',  # e.g., 'localhost' or your host
    'database': 'braiko_db',  # e.g., 'your_db'
    'user': 'root',
    'password': 'password_for_nodered',
    'port': 3306  # default MySQL port
}

TABLE_HOURLY = 'HourlyReports'  # Table name
TABLE_POWER = 'PowerMeters'    # Table name

def connect_db():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        if connection.is_connected():
            print("Connected to MySQL database")
            cursor = connection.cursor()
            # Performance optimizations
            cursor.execute("SET SESSION innodb_lock_wait_timeout = 300")
            cursor.execute("SET SESSION bulk_insert_buffer_size = 32 * 1024 * 1024")  # 32MB
            cursor.execute("SET SESSION sql_mode = ''")  # Less strict for faster inserts
            cursor.close()
            return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        sys.exit(1)

def check_table_locks(cursor):
    """Check for active locks on HourlyReports table"""
    try:
        query = """
        SELECT
            r.trx_id waiting_trx_id,
            r.trx_mysql_thread_id waiting_thread,
            r.trx_query waiting_query,
            b.trx_id blocking_trx_id,
            b.trx_mysql_thread_id blocking_thread,
            b.trx_query blocking_query
        FROM information_schema.innodb_lock_waits w
        INNER JOIN information_schema.innodb_trx b ON b.trx_id = w.blocking_trx_id
        INNER JOIN information_schema.innodb_trx r ON r.trx_id = w.requesting_trx_id
        """
        cursor.execute(query)
        locks = cursor.fetchall()
        if locks:
            print("\n⚠️  WARNING: Detected active locks:")
            for lock in locks:
                print(f"  Thread {lock[1]} is waiting on thread {lock[4]}")
                print(f"  Blocking query: {lock[5]}")
        return len(locks)
    except Error:
        # Ignore errors if we can't check locks
        return 0

def get_unique_meter_ids(cursor):
    """Get all unique power meter IDs from PowerMeters table"""
    query = f"SELECT DISTINCT Id FROM {TABLE_POWER} ORDER BY Id"
    cursor.execute(query)
    return [row[0] for row in cursor.fetchall()]

def get_last_hourly_entry(cursor, meter_id):
    """Get the last entry in HourlyReports for a specific meter ID"""
    query = f"""
    SELECT DateTimeUTC
    FROM {TABLE_HOURLY}
    WHERE Id = %s
    ORDER BY DateTimeUTC DESC
    LIMIT 1
    """
    cursor.execute(query, (meter_id,))
    result = cursor.fetchone()
    if result:
        return result[0]
    return None

def round_to_15min(dt):
    """Round datetime to nearest 0, 15, 30, or 45 minutes"""
    if dt is None:
        return None

    # Get the minutes
    minutes = dt.minute

    # Round to nearest 15-minute interval
    if minutes < 8:
        rounded_minutes = 0
    elif minutes < 23:
        rounded_minutes = 15
    elif minutes < 38:
        rounded_minutes = 30
    elif minutes < 53:
        rounded_minutes = 45
    else:
        # Round up to next hour
        dt = dt + timedelta(hours=1)
        rounded_minutes = 0

    return dt.replace(minute=rounded_minutes, second=0, microsecond=0)

def get_all_power_data_for_meter(cursor, meter_id, start_time, end_time):
    """
    Load all PowerMeters data for a specific meter in a time range
    Returns a list of dictionaries
    """
    query = f"""
    SELECT Id, L1_A, L2_A, L3_A, L1_V, L2_V, L3_V, DateTimeUTC,
           L1_L2_V, L2_L3_V, L3_L1_V, P_kW, Phi, F_Hz,
           exp_kWh, imp_kWh, Tot_react_exp_kVArh, Tot_react_imp_kVArh
    FROM {TABLE_POWER}
    WHERE Id = %s
      AND DateTimeUTC >= %s
      AND DateTimeUTC <= %s
    ORDER BY DateTimeUTC
    """
    cursor.execute(query, (meter_id, start_time, end_time))
    columns = [desc[0] for desc in cursor.description]
    results = cursor.fetchall()

    power_data = []
    for row in results:
        power_data.append(dict(zip(columns, row)))
    return power_data

def find_closest_entry_from_index(power_data, target_time, start_idx=0, tolerance_minutes=2):
    """
    Find the closest entry in power_data within ±tolerance_minutes of target_time
    Starts searching from start_idx for efficiency (sliding window approach)
    Returns tuple: (closest_entry, next_start_idx)
    """
    if not power_data or start_idx >= len(power_data):
        return None, start_idx

    tolerance = timedelta(minutes=tolerance_minutes)
    tolerance_seconds = tolerance.total_seconds()

    closest = None
    min_diff = None
    idx = start_idx

    # Move forward to find entries near target_time
    while idx < len(power_data):
        entry = power_data[idx]
        entry_time = entry['DateTimeUTC']
        time_diff_seconds = (entry_time - target_time).total_seconds()

        # If we're way past the target, stop searching
        if time_diff_seconds > tolerance_seconds:
            break

        # Calculate absolute difference
        abs_diff = abs(time_diff_seconds)

        # Update closest if this is better
        if min_diff is None or abs_diff < min_diff:
            min_diff = abs_diff
            closest = entry

        idx += 1

    # Check if closest is within tolerance
    if closest and min_diff <= tolerance_seconds:
        # Return the index to start from next time (one before current to handle edge cases)
        next_start = max(0, idx - 2)
        return closest, next_start

    return None, start_idx

def batch_insert_hourly_reports(cursor, connection, batch_data, max_retries=3):
    """Insert multiple rows into HourlyReports in a single query with retry logic"""
    if not batch_data:
        return 0

    # Using INSERT IGNORE to skip duplicates automatically (much faster)
    insert_query = f"""
    INSERT IGNORE INTO {TABLE_HOURLY} (Id, L1_A, L2_A, L3_A, L1_V, L2_V, L3_V, DateTimeUTC,
                                L1_L2_V, L2_L3_V, L3_L1_V, P_kW, Phi, F_Hz,
                                exp_kWh, imp_kWh, Tot_react_exp_kVArh, Tot_react_imp_kVArh)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    values_list = []
    for row_data, rounded_time in batch_data:
        values = (
            row_data['Id'],
            row_data['L1_A'], row_data['L2_A'], row_data['L3_A'],
            row_data['L1_V'], row_data['L2_V'], row_data['L3_V'],
            rounded_time,
            row_data['L1_L2_V'], row_data['L2_L3_V'], row_data['L3_L1_V'],
            row_data['P_kW'], row_data['Phi'], row_data['F_Hz'],
            row_data['exp_kWh'], row_data['imp_kWh'],
            row_data['Tot_react_exp_kVArh'], row_data['Tot_react_imp_kVArh']
        )
        values_list.append(values)

    # Retry logic for lock timeouts
    for attempt in range(max_retries):
        try:
            cursor.executemany(insert_query, values_list)
            connection.commit()
            return cursor.rowcount  # Return actual number of inserted rows (not counting duplicates)
        except Error as e:
            # Check if it's a lock timeout error (error code 1205)
            if e.errno == 1205 and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2  # Wait 2, 4, 6 seconds (faster retries)
                print(f"    Lock timeout, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                connection.rollback()
                time.sleep(wait_time)
            else:
                # Re-raise if not a lock timeout or out of retries
                raise

    return 0

def get_earliest_power_meter_entry(cursor, meter_id):
    """Get the earliest entry in PowerMeters for a specific meter ID"""
    query = f"""
    SELECT DateTimeUTC
    FROM {TABLE_POWER}
    WHERE Id = %s
    ORDER BY DateTimeUTC ASC
    LIMIT 1
    """
    cursor.execute(query, (meter_id,))
    result = cursor.fetchone()
    if result:
        return result[0]
    return None

def process_meter(cursor, connection, meter_id, now):
    """Process a single power meter to fill in missing 15-minute intervals"""
    print(f"\nProcessing meter ID: {meter_id}")
    start_timer = time.time()

    # Get the last entry in HourlyReports
    last_entry_time = get_last_hourly_entry(cursor, meter_id)

    if last_entry_time is None:
        # No entries yet, start from earliest PowerMeters entry
        earliest_time = get_earliest_power_meter_entry(cursor, meter_id)
        if earliest_time is None:
            print(f"  No data in PowerMeters for ID {meter_id}, skipping")
            return 0

        print(f"  No entries in HourlyReports, starting from earliest PowerMeters entry: {earliest_time}")
        start_time = round_to_15min(earliest_time)
    else:
        print(f"  Last entry in HourlyReports: {last_entry_time}")
        # Round to 15-min and add 15 minutes to get next slot
        start_time = round_to_15min(last_entry_time)
        start_time = start_time + timedelta(minutes=15)

    # Calculate time range
    if start_time > now:
        print(f"  Already up to date!")
        return 0

    # Load all PowerMeters data for this time range at once
    print(f"  Loading PowerMeters data from {start_time} to {now}...")
    power_data = get_all_power_data_for_meter(cursor, meter_id, start_time - timedelta(minutes=5), now + timedelta(minutes=5))
    print(f"  Loaded {len(power_data)} PowerMeters entries")

    if not power_data:
        print(f"  No PowerMeters data in range, skipping")
        return 0

    # Generate all time slots using optimized sliding window approach
    current_time = start_time
    batch_data = []
    inserts_count = 0
    skipped_count = 0
    BATCH_SIZE = 500  # Larger batches for better performance (was 50)
    PROGRESS_INTERVAL = 1000  # Print progress every 1000 inserts
    lock_errors = 0
    search_idx = 0  # Sliding window pointer for power_data

    # Process until we reach or exceed NOW
    while current_time <= now:
        # Find matching entry in PowerMeters (±2 minutes) using sliding window
        power_entry, search_idx = find_closest_entry_from_index(power_data, current_time, search_idx)

        if power_entry:
            batch_data.append((power_entry, current_time))

            # Insert batch when it reaches BATCH_SIZE
            if len(batch_data) >= BATCH_SIZE:
                try:
                    inserted = batch_insert_hourly_reports(cursor, connection, batch_data)
                    inserts_count += inserted
                    batch_data = []
                    # Only print progress periodically
                    if inserts_count % PROGRESS_INTERVAL == 0:
                        print(f"  Progress: {inserts_count} intervals inserted... (current: {current_time})")
                except Error as e:
                    if e.errno == 1205:
                        lock_errors += 1
                        print(f"  Batch insert failed after retries at {current_time}: {e}")
                        print(f"  Skipping this batch to continue processing...")
                    else:
                        print(f"  Batch insert error at {current_time}: {e}")
                    batch_data = []
        else:
            skipped_count += 1

        # Move to next 15-minute slot
        current_time = current_time + timedelta(minutes=15)

    # Insert remaining batch
    if batch_data:
        try:
            inserted = batch_insert_hourly_reports(cursor, connection, batch_data)
            inserts_count += inserted
        except Error as e:
            if e.errno == 1205:
                lock_errors += 1
                print(f"  Final batch insert failed after retries: {e}")
            else:
                print(f"  Final batch insert error: {e}")

    elapsed = time.time() - start_timer
    status = f"  Completed meter {meter_id}: {inserts_count} inserts, {skipped_count} skipped in {elapsed:.1f}s"
    if lock_errors > 0:
        status += f", {lock_errors} lock errors"
    if inserts_count > 0:
        rate = inserts_count / elapsed if elapsed > 0 else 0
        status += f" ({rate:.0f} inserts/sec)"
    print(status)
    return inserts_count

def main():
    connection = connect_db()
    script_start = time.time()
    try:
        cursor = connection.cursor()

        # Get current time in UTC (database uses UTC)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        print(f"Current time (UTC): {now}")
        print(f"Processing data up to: {now}\n")

        # Check for active locks
        check_table_locks(cursor)

        # Get all unique meter IDs
        meter_ids = get_unique_meter_ids(cursor)
        print(f"Found {len(meter_ids)} unique power meter IDs: {meter_ids}\n")

        total_inserts = 0

        # Process each meter
        for meter_id in meter_ids:
            inserts = process_meter(cursor, connection, meter_id, now)
            total_inserts += inserts

        total_elapsed = time.time() - script_start
        print(f"\n{'='*60}")
        print(f"Sync completed successfully!")
        print(f"Total inserts: {total_inserts}")
        print(f"Total time: {total_elapsed:.1f}s")
        if total_inserts > 0:
            print(f"Average rate: {total_inserts/total_elapsed:.0f} inserts/sec")
        print(f"{'='*60}")

    except Error as e:
        print(f"Database error: {e}")
        connection.rollback()
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            print("\nMySQL connection closed")

if __name__ == "__main__":
    main()

