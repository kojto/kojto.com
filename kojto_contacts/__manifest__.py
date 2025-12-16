# kojto_contacts/__manifest__.py
{
    "name": "Kojto Contacts",
    "version": "18.04.08",
    "category": "KOJTO",
    "description": "Contact management module with AI configuration settings for finance automation",
    "author": "KOJTO",
    "website": "https://www.kojto.com",
    "depends": [
        "kojto_base",
        "kojto_landingpage"
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ensure_contact_1.xml",
        "views/kojto_contacts_views.xml",
        "views/kojto_contacts_base_views.xml",
        "views/kojto_contacts_menu_view.xml",
        "views/kojto_contacts_buttons.xml",
        "actions/action_dropdown_view.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
