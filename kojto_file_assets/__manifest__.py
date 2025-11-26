# Copyright 2022 TMC

{
    "name": "Kojto File Assets",
    "summary": "Shared file assets and styling for KOJTO modules",
    "description": "Module providing shared CSS, JavaScript, XML templates, and styling assets used across all KOJTO modules",
    "version": "18.04.07",
    "author": "KOJTO",
    "website": "https://www.kojto.com",
    "category": "KOJTO",
    "depends": ["web", "base"],
    "data": [
        "static/src/xml/webclient_templates.xml",
        "static/src/xml/pdf_css_template_1090.xml",
        "static/src/xml/pdf_css_template_header.xml",
        "static/src/xml/report_paperformat_data.xml",
        "static/src/xml/language_settings.xml",
        "static/src/xml/internal_layout.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "kojto_file_assets/static/src/css/kojto_list_view.css",
            "kojto_file_assets/static/src/css/kojto_form_view.css",
            "kojto_file_assets/static/src/css/kojto_main.css",
            "kojto_file_assets/static/src/scss/control_panel.scss",
            "kojto_file_assets/static/src/scss/list_renderer.scss",
            "kojto_file_assets/static/src/scss/form_controller.scss",
            "kojto_file_assets/static/src/js/kojto.js",
            'kojto_file_assets/static/src/js/remove_junk_user_menus.js',
        ],
        "web._assets_primary_variables": [
            ("prepend", "kojto_file_assets/static/src/scss/primary_variables.scss"),
        ],
    },
    "installable": True,
    "application": True,
    "auto_install": False,
}
