#!/bin/bash
# Odoo Module Test Runner - Generic Test Script for Any Module
#
# HOW TO RUN:
# -----------
# sudo -u odoo18 bash
# source /opt/odoo18/venv/bin/activate
# /opt/odoo18/custom/addons/kojto_tests/run_tests.sh [module_name] [database_name]
#
# Examples:
#   ./run_tests.sh                          # Tests kojto_products on kojto DB
#   ./run_tests.sh kojto_products kojto     # Tests kojto_products on kojto DB
#   ./run_tests.sh kojto_finance           # Tests kojto_finance on kojto DB
#   ./run_tests.sh trinity_examination erp3 # Tests trinity_examination on erp3 DB
#
# Stops/restarts Odoo server automatically.

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to print status messages
print_status() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

print_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

print_info() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"
}

print_test_header() {
    echo -e "\n${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}\n"
}

print_separator() {
    echo -e "${CYAN}───────────────────────────────────────────────────────────────${NC}"
}

# Parse command line arguments
MODULE_NAME="${1:-kojto_products}"
DATABASE_NAME="${2:-kojto}"

# Validate module name format
if [[ ! "$MODULE_NAME" =~ ^[a-zA-Z0-9_]+$ ]]; then
    echo -e "${RED}ERROR: Invalid module name: $MODULE_NAME${NC}"
    echo "Module name should only contain letters, numbers, and underscores"
    exit 1
fi

# Check if running as odoo18 user
if [ "$USER" != "odoo18" ]; then
    print_warning "Not running as odoo18 user. Attempting to use sudo for systemctl commands..."
fi

# Stop the Odoo server
print_status "Stopping Odoo server..."
sudo systemctl stop odoo18

# Check if stop was successful
if [ $? -ne 0 ]; then
    print_error "Failed to stop Odoo server"
    exit 1
fi

# Run the tests
print_test_header "$(echo $MODULE_NAME | tr '[:lower:]' '[:upper:]') - TEST SUITE"

print_info "Module: $MODULE_NAME"
print_info "Database: $DATABASE_NAME"
print_info "Test Type: Integration Tests"
print_separator

print_status "Environment Setup:"
# Change to a directory odoo18 user has access to
cd /tmp
print_info "Working directory: $(pwd)"
print_info "Python version: $(/opt/odoo18/venv/bin/python --version)"
print_info "Config file: /etc/odoo18.conf"
print_info "Log output: /var/log/odoo/odoo18.log"
print_separator

print_status "Starting test execution..."
print_info "Command: /opt/odoo18/venv/bin/python /opt/odoo18/odoo-bin -c /etc/odoo18.conf -d $DATABASE_NAME --test-enable --stop-after-init -u $MODULE_NAME --log-level=test --http-port=8070"

# Record test start time to filter results
TEST_START_TIME=$(date '+%Y-%m-%d %H:%M:%S')
print_info "Test run started at: $TEST_START_TIME"
echo ""

# Check if module directory exists
MODULE_DIR="/opt/odoo18/custom/addons/$MODULE_NAME"
if [ ! -d "$MODULE_DIR" ]; then
    print_error "Module directory not found: $MODULE_DIR"
    exit 1
fi

# Check if test directory exists
TEST_DIR="$MODULE_DIR/tests"
if [ -d "$TEST_DIR" ]; then
    print_info "Test directory found: $TEST_DIR"
    # Count test files
    TEST_FILE_COUNT=$(find "$TEST_DIR" -name "test_*.py" -type f 2>/dev/null | wc -l)
    if [ "$TEST_FILE_COUNT" -gt 0 ]; then
        print_info "Found $TEST_FILE_COUNT test file(s)"
        # Check for @tagged decorator in test files
        TAGGED_COUNT=$(grep -r "@tagged" "$TEST_DIR" --include="test_*.py" 2>/dev/null | wc -l)
        if [ "$TAGGED_COUNT" -gt 0 ]; then
            print_info "Test files have @tagged decorator ✓"
        fi
        # Count test methods
        TOTAL_TEST_METHODS=$(grep -r "def test_" "$TEST_DIR" --include="test_*.py" 2>/dev/null | wc -l)
        print_info "Total test methods: $TOTAL_TEST_METHODS"
    else
        print_warning "No test files found in $TEST_DIR"
    fi
else
    print_warning "No tests directory found for module: $MODULE_NAME"
fi
echo ""

# Run test and capture output to both console and file
# Using -u (update) instead of -i (install) to trigger post_install tests
/opt/odoo18/venv/bin/python /opt/odoo18/odoo-bin -c /etc/odoo18.conf -d $DATABASE_NAME --test-enable --stop-after-init -u $MODULE_NAME --log-level=test --http-port=8070 2>&1 | tee /tmp/odoo_test_output.log

# Store the test result (use PIPESTATUS to get exit code from python, not tee)
TEST_RESULT=${PIPESTATUS[0]}

echo ""
print_separator
print_status "Test execution completed with exit code: $TEST_RESULT"
print_separator

# Parse test results from log file
ODOO_LOGFILE=$(grep -i "logfile" /etc/odoo18.conf | awk -F= '{print $2}' | tr -d ' ')
if [ -f "$ODOO_LOGFILE" ]; then
    print_test_header "TEST RESULTS SUMMARY"

    # Extract test statistics (only from current run)
    if [ -n "$TEST_START_TIME" ]; then
        # Get lines after test start time
        TEST_STATS=$(sudo awk -v start="$TEST_START_TIME" '$0 >= start' "$ODOO_LOGFILE" 2>/dev/null | grep -E "failed.*error.*of.*tests" | tail -1)
    else
        TEST_STATS=$(sudo grep -E "failed.*error.*of.*tests" "$ODOO_LOGFILE" | tail -1)
    fi
    MODULES_LINE=$(sudo grep -E "modules loaded in" "$ODOO_LOGFILE" | tail -1)
    MODULES_LOADED=$(echo "$MODULES_LINE" | grep -oP '^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+ \d+ INFO \w+ odoo\.modules\.loading: \K\d+' || echo "N/A")
    LOAD_TIME=$(echo "$MODULES_LINE" | grep -oP 'in \K[\d.]+s' || echo "N/A")
    REGISTRY_LINE=$(sudo grep -E "Registry loaded in" "$ODOO_LOGFILE" | tail -1)
    REGISTRY_TIME=$(echo "$REGISTRY_LINE" | grep -oP 'in \K[\d.]+s' || echo "N/A")
    POST_TESTS_LINE=$(sudo grep -E "post-tests in" "$ODOO_LOGFILE" | tail -1)
    POST_TESTS_COUNT=$(echo "$POST_TESTS_LINE" | grep -oP '^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+ \d+ INFO \w+ odoo\.service\.server: \K\d+' || echo "0")
    POST_TESTS_TIME=$(echo "$POST_TESTS_LINE" | grep -oP 'in \K[\d.]+s' || echo "N/A")

    if [ -n "$MODULES_LOADED" ]; then
        print_info "Modules loaded: $MODULES_LOADED modules in $LOAD_TIME"
    fi

    if [ -n "$REGISTRY_TIME" ]; then
        print_info "Registry load time: $REGISTRY_TIME"
    fi

    if [ -n "$POST_TESTS_COUNT" ]; then
        print_info "Post-tests executed: $POST_TESTS_COUNT tests in $POST_TESTS_TIME"
    fi

    print_separator

    if [ -n "$TEST_STATS" ]; then
        # Parse the test statistics
        FAILED=$(echo "$TEST_STATS" | grep -oP '\d+(?= failed)' || echo "0")
        ERRORS=$(echo "$TEST_STATS" | grep -oP '\d+(?= error)' || echo "0")
        TOTAL=$(echo "$TEST_STATS" | grep -oP 'of \d+' | grep -oP '\d+' || echo "0")

        if [ "$TOTAL" = "0" ]; then
            print_warning "No tests found to execute"
            echo -e "${YELLOW}  • Total Tests: 0${NC}"
            echo -e "${YELLOW}  • Note: No test files exist in $MODULE_NAME/tests/${NC}"
            echo -e "${YELLOW}  • Create test_*.py files with @tagged decorator${NC}"
        elif [ "$FAILED" = "0" ] && [ "$ERRORS" = "0" ]; then
            print_status "✓ ALL TESTS PASSED!"
            echo -e "${GREEN}  • Total Tests: $TOTAL${NC}"
            echo -e "${GREEN}  • Passed: $TOTAL${NC}"
            echo -e "${GREEN}  • Failed: 0${NC}"
            echo -e "${GREEN}  • Errors: 0${NC}"
        else
            print_error "✗ TESTS FAILED!"
            echo -e "${RED}  • Total Tests: $TOTAL${NC}"
            echo -e "${RED}  • Passed: $((TOTAL - FAILED - ERRORS))${NC}"
            echo -e "${RED}  • Failed: $FAILED${NC}"
            echo -e "${RED}  • Errors: $ERRORS${NC}"
        fi
    else
        print_warning "Could not extract test statistics from log"
    fi

    print_separator

    # Show test details if available
    print_status "Test Execution Details:"
    echo ""

    # Extract test method names if available
    TEST_METHODS=$(sudo grep -E "running.*test_.*$MODULE_NAME" "$ODOO_LOGFILE" 2>/dev/null | tail -20)
    if [ -n "$TEST_METHODS" ]; then
        echo "$TEST_METHODS" | while IFS= read -r line; do
            echo "  $line"
        done
        echo ""
    fi

    # Check for warnings
    WARNING_COUNT=$(sudo grep -c "WARNING.*$MODULE_NAME" "$ODOO_LOGFILE" 2>/dev/null || echo "0")
    if [ "$WARNING_COUNT" -gt 0 ]; then
        print_warning "Found $WARNING_COUNT warnings (mostly deprecation warnings)"
        echo -e "${YELLOW}  • These are typically _sql_constraints deprecation warnings${NC}"
        echo -e "${YELLOW}  • They don't affect functionality but should be updated for Odoo 18${NC}"
    fi

    # Show any test failures in detail (only from current run)
    if [ -n "$TEST_START_TIME" ]; then
        FAILURES=$(sudo awk -v start="$TEST_START_TIME" '$0 > start' "$ODOO_LOGFILE" 2>/dev/null | grep -A 10 "FAIL:.*$MODULE_NAME" 2>/dev/null)
        if [ -n "$FAILURES" ]; then
            print_separator
            print_error "Test Failures:"
            echo "$FAILURES"
        fi

        # Only show errors if tests actually failed in current run
        ERRORS_DETAIL=$(sudo tail -200 "$ODOO_LOGFILE" 2>/dev/null | grep -A 10 "ERROR.*$MODULE_NAME" 2>/dev/null)

        # Check if these errors are from before test start (likely old)
        if [ -n "$ERRORS_DETAIL" ]; then
            # Extract first timestamp from error details
            FIRST_ERROR_TIME=$(echo "$ERRORS_DETAIL" | head -1 | grep -oP '^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}' || echo "")
            if [ -n "$FIRST_ERROR_TIME" ] && [ -n "$TEST_START_TIME" ]; then
                # Compare timestamps - only show if error is from current run
                # Convert to comparable format for bash
                if [[ "$FIRST_ERROR_TIME" > "$TEST_START_TIME" ]] || [[ "$FIRST_ERROR_TIME" == "$TEST_START_TIME" ]]; then
                    print_separator
                    print_error "Test Errors (from current run):"
                    echo "$ERRORS_DETAIL"
                else
                    print_info "Old errors found in log (ignored - from previous runs)"
                fi
            else
                # If timestamp comparison fails, be conservative and show it
                print_separator
                print_error "Test Errors:"
                echo "$ERRORS_DETAIL"
            fi
        elif [ $TEST_RESULT -eq 1 ] && [ "$FAILED" = "0" ] && [ "$ERRORS" = "0" ]; then
            # Exit code 1 but no failed tests - might be expected (e.g., cycle detection)
            print_info "Exit code 1 with no test failures - likely expected behavior"
        fi
    else
        # Fallback: show recent errors only
        ERRORS_DETAIL=$(sudo tail -100 "$ODOO_LOGFILE" 2>/dev/null | grep -A 10 "ERROR.*$MODULE_NAME" 2>/dev/null)
        if [ -n "$ERRORS_DETAIL" ]; then
            print_separator
            print_error "Recent Test Errors:"
            echo "$ERRORS_DETAIL"
        fi
    fi

    print_separator
else
    print_warning "Log file not found: $ODOO_LOGFILE"
fi

# Check if tests were successful
if [ $TEST_RESULT -ne 0 ]; then
    print_test_header "TEST RUN FAILED"
    print_error "Tests failed with exit code $TEST_RESULT"
    print_warning "Check the detailed output above for error messages"
    print_separator
    print_status "Starting Odoo server..."
    sudo systemctl start odoo18
    exit 1
fi

# Start the Odoo server
print_status "Starting Odoo server..."
sudo systemctl start odoo18

# Check if start was successful
if [ $? -ne 0 ]; then
    print_error "Failed to start Odoo server"
    exit 1
fi

print_test_header "✓ ALL TESTS COMPLETED SUCCESSFULLY ✓"
echo -e "${GREEN}Module: $MODULE_NAME${NC}"
echo -e "${GREEN}Database: $DATABASE_NAME${NC}"
echo -e "${GREEN}Status: PASSED${NC}"
echo -e "${GREEN}Server: RESTARTED${NC}"
print_separator
exit 0

