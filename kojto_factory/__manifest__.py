# kojto_factory/__manifest__.py
{
    "name": "Kojto Factory",
    "version": "18.04.07",
    "category": "KOJTO",
    "description": "Factory management module for managing factory jobs, tasks, processes, packages, and item dimensions",
    "author": "KOJTO",
    "website": "https://www.kojto.com",
    "depends": [
        "kojto_warehouses",
        "kojto_assets",
        "kojto_contracts",
    ],
    "data": [
        "security/ir.model.access.csv",
        "wizards/kojto_factory_item_dimensions_wizard_views.xml",
        "views/kojto_factory_packages_views.xml",
        "views/kojto_factory_tasks_views.xml",
        "views/kojto_factory_processes_views.xml",
        "views/kojto_factory_jobs_views.xml",
        "views/kojto_factory_buttons.xml",
        "views/kojto_factory_menu_views.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
