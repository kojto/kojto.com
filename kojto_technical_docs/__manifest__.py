{
    "name": "Kojto Technical Docs",
    "version": "18.04.08",
    "category": "KOJTO",
    "description": "Technical documentation management module for managing technical documents and their revisions",
    "author": "KOJTO",
    "website": "https://www.kojto.com",
    "depends": ["kojto_deliveries"],
    "data": [
        "security/ir.model.access.csv",
        "views/kojto_technical_docs_views.xml",
        "views/kojto_technical_doc_revisions_views.xml",
        "views/kojto_technical_docs_buttons.xml",
        "views/kojto_technical_docs_menu_views.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
