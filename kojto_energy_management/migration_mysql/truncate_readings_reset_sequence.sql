-- Truncate power meter readings table and reset ID sequence
-- WARNING: This will DELETE ALL readings data!
-- Use with caution - data cannot be recovered after this operation

-- Display count before deletion
SELECT COUNT(*) as "Records before truncation"
FROM kojto_energy_management_power_meter_readings;

-- Truncate the table (faster than DELETE and automatically resets sequence)
TRUNCATE TABLE kojto_energy_management_power_meter_readings RESTART IDENTITY CASCADE;

-- Alternative method (if TRUNCATE doesn't work):
-- DELETE FROM kojto_energy_management_power_meter_readings;
-- ALTER SEQUENCE kojto_energy_management_power_meter_readings_id_seq RESTART WITH 1;

-- Verify the table is empty
SELECT COUNT(*) as "Records after truncation"
FROM kojto_energy_management_power_meter_readings;

-- Verify sequence is reset
SELECT nextval('kojto_energy_management_power_meter_readings_id_seq') as "Next ID (should be 1)";

-- Reset the sequence back to 1 (since we just consumed one value)
ALTER SEQUENCE kojto_energy_management_power_meter_readings_id_seq RESTART WITH 1;

-- Show final status
SELECT
    'Power meter readings truncated successfully!' as status,
    (SELECT COUNT(*) FROM kojto_energy_management_power_meter_readings) as record_count,
    (SELECT last_value FROM kojto_energy_management_power_meter_readings_id_seq) as next_id_will_be;

