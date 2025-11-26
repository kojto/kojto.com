# kojto_commission_codes/__manifest__.py
{
    "name": "Kojto Commission Codes",
    "summary": "Commission code management system",
    "description": "Module for managing commission codes, main codes, and subcodes used for categorization and tracking across the system",
    "author": "KOJTO",
    "website": "https://www.kojto.com",
    "category": "KOJTO",
    "version": "18.04.07",
    "depends": ["kojto_landingpage", "kojto_base"],
    "data": [
        "security/ir.model.access.csv",
        "views/kojto_commission_codes_view.xml",
        "views/kojto_commission_main_codes_view.xml",
        "views/kojto_commission_subcodes_view.xml",
        "views/kojto_commission_codes_menu_view.xml",
        "views/kojto_commission_codes_buttons.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
