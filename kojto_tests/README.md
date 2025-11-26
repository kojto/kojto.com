# Kojto Tests - Generic Test Runner

This directory contains a universal test runner script that can be used to test any Odoo module.

## Quick Start

```bash
# On your Odoo server:
sudo -u odoo18 bash
source /opt/odoo18/venv/bin/activate
/opt/odoo18/custom/addons/kojto_tests/run_tests.sh [module_name] [database_name]
```

## Examples

```bash
# Test kojto_products on kojto database (defaults)
./run_tests.sh

# Test specific module on kojto database
./run_tests.sh kojto_finance

# Test specific module on specific database
./run_tests.sh trinity_examination erp3

# Test any module with custom database
./run_tests.sh kojto_hr kojto
```

## What It Does

1. **Stops** the Odoo server
2. **Runs** all tests for the specified module
3. **Displays** detailed test results with:
   - Pass/Fail statistics
   - Detailed test output
   - Performance metrics
   - Error details (if any)
4. **Restarts** the Odoo server

## Features

- ✅ Color-coded output (Green/Red/Yellow/Blue)
- ✅ Comprehensive test coverage reporting
- ✅ Automatic test discovery (finds all `test_*.py` files)
- ✅ Performance metrics (load times, test execution time)
- ✅ Error filtering (shows only current run errors)
- ✅ Warning detection and reporting
- ✅ Works with any Odoo module

## Requirements

- Module must have a `tests/` directory
- Test files must be named `test_*.py`
- Test classes should use `@tagged('post_install', '-at_install')` decorator
- Tests should inherit from `TransactionCase`

## Output

Results are saved to:
- Console output (real-time)
- `/tmp/odoo_test_output.log` (for reference)
- `/var/log/odoo/odoo18.log` (Odoo's main log)

