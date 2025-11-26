#!/bin/bash
# Script to enable print and download buttons in PDF.js preview in the core Odoo 18 installation
# Should be executed once after the installation of Odoo 18 on the local machine
# No arguments required; Odoo directory is fixed at /opt/odoo18
# Usage: ./enable_print_in_pdfjs_preview.sh

FILE_PATH="/opt/odoo18/addons/web/static/src/views/fields/pdf_viewer/pdf_viewer_field.js"

# Check if the file exists
if [ ! -f "$FILE_PATH" ]; then
    echo "Error: File $FILE_PATH does not exist"
    echo "Please ensure Odoo 18 is installed correctly at /opt/odoo18"
    exit 1
fi

# Execute the sed commands to modify the file
echo "Enabling download button..."
sed -i 's!hideDownload:[[:space:]]*true,!hideDownload: false,!g' "$FILE_PATH"
DOWNLOAD_EXIT_CODE=$?

echo "Enabling print button..."
sed -i 's!hidePrint:[[:space:]]*true,!hidePrint: false,!g' "$FILE_PATH"
PRINT_EXIT_CODE=$?

# Check if both sed commands were successful
if [ $DOWNLOAD_EXIT_CODE -eq 0 ] && [ $PRINT_EXIT_CODE -eq 0 ]; then
    echo "Successfully modified PDF viewer settings"
    echo "Download and print buttons are now enabled in PDF.js preview"
    echo "Please restart the Odoo service to apply changes (e.g., systemctl restart odoo)"
elif [ $DOWNLOAD_EXIT_CODE -ne 0 ] && [ $PRINT_EXIT_CODE -ne 0 ]; then
    echo "Error: Both modifications failed"
    echo "Please check:"
    echo " - Sufficient permissions to modify $FILE_PATH"
    echo " - File content for 'hideDownload' and 'hidePrint' patterns"
    exit 1
elif [ $DOWNLOAD_EXIT_CODE -ne 0 ]; then
    echo "Error: Failed to enable download button"
    echo "Print button modification succeeded"
    echo "Please check the download button configuration"
    exit 1
else
    echo "Error: Failed to enable print button"
    echo "Download button modification succeeded"
    echo "Please check the print button configuration"
    exit 1
fi
