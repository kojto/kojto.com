# kojto_profiles/__manifest__.py
{
    "name": "Kojto Profiles",
    "version": "18.04.07",
    "images": ["static/description/icon.png"],
    "category": "KOJTO",
    "description": "Profile management module for managing profiles, configurators, batches, strips, shapes, and profile optimization",
    "author": "KOJTO",
    "website": "https://www.kojto.com",
    "depends": [
        "kojto_contacts",
        "kojto_optimizer"
    ],
    "external_dependencies": {"python": ["openpyxl"]},
    "data": [
        "security/ir.model.access.csv",
        "views/kojto_profiles_views.xml",
        "views/kojto_profile_configurator_views.xml",
        "views/kojto_profile_batch_wizards_views.xml",
        "views/kojto_profile_batches_views.xml",
        "views/kojto_profile_strips_views.xml",
        "views/kojto_profile_shapes.xml",
        "views/kojto_profiles_buttons.xml",
        "views/kojto_profiles_menu_views.xml",
        "reports/kojto_profiles_reports.xml",
        "reports/kojto_profiles_templates.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
