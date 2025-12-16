#!/bin/bash
# Install pynest2d for Odoo 2D Optimizer
# This script installs pynest2d system package and creates a symlink in the Odoo venv
#
 cd /opt/odoo18/custom/addons/kojto_optimizer
# sudo ./install_pynest2d.sh

set -e

echo "=== Installing pynest2d for Odoo 2D Optimizer ==="
echo ""

# Configuration - adjust these if your Odoo installation differs
ODOO_USER="${ODOO_USER:-odoo18}"
ODOO_VENV="${ODOO_VENV:-/opt/odoo18/venv}"

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    echo "This script must be run as root or with sudo"
    exit 1
fi

# Check if Odoo user exists
if ! id "$ODOO_USER" &>/dev/null; then
    echo "Error: Odoo user '$ODOO_USER' not found"
    echo "Please set ODOO_USER environment variable or adjust the script"
    exit 1
fi

# Check if venv exists
if [ ! -d "$ODOO_VENV" ]; then
    echo "Error: Odoo virtual environment not found at $ODOO_VENV"
    echo "Please set ODOO_VENV environment variable or adjust the script"
    exit 1
fi

echo "1. Installing pynest2d system package..."
if dpkg -l | grep -q python3-pynest2d; then
    echo "   ✓ pynest2d already installed"
else
    apt-get update
    apt-get install -y python3-pynest2d
    echo "   ✓ pynest2d installed"
fi
echo ""

echo "2. Checking pynest2d in system Python..."
if python3 -c "import pynest2d" 2>/dev/null; then
    PYNEST2D_LOCATION=$(python3 -c "import pynest2d; print(pynest2d.__file__)" 2>/dev/null)
    echo "   ✓ pynest2d found in system Python"
    echo "   Location: $PYNEST2D_LOCATION"
else
    echo "   ✗ pynest2d not found in system Python"
    echo "   Please install it manually: sudo apt-get install -y python3-pynest2d"
    exit 1
fi
echo ""

echo "3. Checking pynest2d in Odoo venv..."
if sudo -u "$ODOO_USER" "$ODOO_VENV/bin/python3" -c "import pynest2d" 2>/dev/null; then
    echo "   ✓ pynest2d already available in Odoo venv"
    echo "   Location: $(sudo -u "$ODOO_USER" "$ODOO_VENV/bin/python3" -c 'import pynest2d; print(pynest2d.__file__)' 2>/dev/null)"
    echo ""
    echo "=== Installation Complete ==="
    echo "pynest2d is already properly configured."
    exit 0
else
    echo "   ✗ pynest2d NOT available in Odoo venv"
fi
echo ""

echo "4. Creating symlink in Odoo venv..."
VENV_SITE_PACKAGES=$(sudo -u "$ODOO_USER" "$ODOO_VENV/bin/python3" -c "import site; print(site.getsitepackages()[0])" 2>/dev/null)

if [ -z "$VENV_SITE_PACKAGES" ]; then
    echo "   ✗ Error: Could not determine venv site-packages directory"
    exit 1
fi

echo "   Venv site-packages: $VENV_SITE_PACKAGES"

# Get the base name of pynest2d module
PYNEST2D_NAME=$(basename "$PYNEST2D_LOCATION" | sed 's/\..*//')
PYNEST2D_FULLNAME=$(basename "$PYNEST2D_LOCATION")

echo "   Creating symlinks..."

# Create symlink with base name
sudo -u "$ODOO_USER" ln -sf "$PYNEST2D_LOCATION" "$VENV_SITE_PACKAGES/$PYNEST2D_NAME" 2>/dev/null || true

# If it's a .so file, also create symlinks with .so extension and full filename
if [[ "$PYNEST2D_LOCATION" == *.so ]]; then
    sudo -u "$ODOO_USER" ln -sf "$PYNEST2D_LOCATION" "$VENV_SITE_PACKAGES/$PYNEST2D_NAME.so" 2>/dev/null || true
    sudo -u "$ODOO_USER" ln -sf "$PYNEST2D_LOCATION" "$VENV_SITE_PACKAGES/$PYNEST2D_FULLNAME" 2>/dev/null || true
fi

echo ""

echo "5. Verifying installation..."
if sudo -u "$ODOO_USER" "$ODOO_VENV/bin/python3" -c "import pynest2d; print('SUCCESS')" 2>&1 | grep -q "SUCCESS"; then
    echo "   ✓ pynest2d is now available in Odoo venv!"
    echo ""
    echo "   Testing import with details:"
    sudo -u "$ODOO_USER" "$ODOO_VENV/bin/python3" -c "
import pynest2d
print('   Location:', pynest2d.__file__)
print('   Available attributes:', [x for x in dir(pynest2d) if not x.startswith('_')][:5])
" 2>/dev/null || true
    echo ""
    echo "=== Installation Complete ==="
    echo ""
    echo "Next steps:"
    echo "1. Restart Odoo: sudo systemctl restart odoo18"
    echo "2. Test the 2D optimizer in Odoo"
else
    echo "   ✗ Installation failed. pynest2d is still not available in venv"
    echo ""
    echo "   Troubleshooting:"
    echo "   1. Check if pynest2d is installed: python3 -c 'import pynest2d'"
    echo "   2. Check venv site-packages: ls -la $VENV_SITE_PACKAGES | grep pynest2d"
    echo "   3. Check permissions: ls -la $PYNEST2D_LOCATION"
    exit 1
fi

