#!/bin/bash
#sudo chmod +x /opt/odoo18/custom/addons/kojto_file_assets/static/test_script/run_tests.sh
#sudo -u odoo18 /opt/odoo18/custom/addons/kojto_file_assets/static/test_script/run_tests.sh



# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print status messages
print_status() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

print_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

# Check if running as odoo18 user
if [ "$USER" != "odoo18" ]; then
    print_error "Please run as odoo18 user using: sudo -u odoo18 $0"
    exit 1
fi

# Stop the Odoo server (using sudo for systemctl)
print_status "Stopping Odoo server..."
sudo systemctl stop odoo18

# Check if stop was successful
if [ $? -ne 0 ]; then
    print_error "Failed to stop Odoo server"
    exit 1
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source /opt/odoo18/venv/bin/activate

# Check if virtual environment activation was successful
if [ $? -ne 0 ]; then
    print_error "Failed to activate virtual environment"
    sudo systemctl start odoo18
    exit 1
fi

# Run the tests
print_status "Running tests..."
python3 /opt/odoo18/odoo-bin -c /etc/odoo18.conf -d kojto --test-enable --stop-after-init -i kojto_assets --log-level=test --http-port=8070

# Store the test result
TEST_RESULT=$?

# Deactivate virtual environment
print_status "Deactivating virtual environment..."
deactivate

# Check if tests were successful
if [ $TEST_RESULT -ne 0 ]; then
    print_error "Tests failed"
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

print_status "Tests completed successfully!"
exit 0
