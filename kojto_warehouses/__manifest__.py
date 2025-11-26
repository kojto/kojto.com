{
    "name": "Kojto Warehouses",
    "summary": "Warehouse management for batches and contents",
    "description": "Manages warehouse batches (bars, sheets, parts) with dynamic content handling and weight calculations.",
    "author": "KOJTO",
    "website": "https://www.kojto.com",
    "category": "KOJTO",
    "version": "18.04.07",
    "depends": ["kojto_finance"],
    "data": [
        "security/ir.model.access.csv",

        "views/kojto_warehouses_batches_views.xml",
        "views/kojto_warehouses_buttons.xml",
        "views/kojto_warehouses_inventory_views.xml",
        "views/kojto_warehouses_items_views.xml",
        "views/kojto_warehouses_transactions_views.xml",
        "views/kojto_warehouses_certificates_views.xml",
        "views/kojto_warehouses_receipts_views.xml",
        "views/kojto_warehouses_profile_shapes_views.xml",
        "views/kojto_warehouses_inspection_report_views.xml",
        "views/kojto_warehouses_invoice_integration_views.xml",

        "wizards/views/kojto_warehouses_invoice_batch_creation_wizard_view.xml",
        "wizards/views/kojto_warehouses_generate_items_wizard_views.xml",
        "wizards/views/kojto_warehouses_balance_wizard_views.xml",

        "views/kojto_warehouses_menu_views.xml",

        "reports/kojto_warehouses_inspection_report_template.xml",
        "reports/kojto_warehouses_inspection_report_reports.xml",
        "reports/kojto_warehouses_receipt_reports.xml",
        "reports/kojto_warehouses_receipt_templates.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
