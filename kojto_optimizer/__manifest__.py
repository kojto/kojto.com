# kojto_optimizer/__manifest__.py
{
    "name": "Kojto Optimizer",
    "version": "18.04.08",
    "category": "KOJTO",
    "description": "1D and 2D optimization",
    "author": "KOJTO",
    "website": "https://www.kojto.com",
    "depends": ["kojto_contacts", "kojto_hr"],
    "external_dependencies": {"python": ["binpacking", "pulp", "openpyxl", "ezdxf", "weasyprint", "rectpack", "svgwrite", "shapely"]},
    "data": [
        "security/ir.model.access.csv",
        "views/kojto_optimizer_1d_views.xml",
        "views/kojto_optimizer_2d_views.xml",
        "views/kojto_optimizer_2dr_views.xml",
        "views/kojto_optimizer_buttons.xml",
        "views/kojto_optimizer_menu_views.xml",

        "reports/kojto_optimizer_1d_reports.xml",
        "reports/kojto_optimizer_1d_templates.xml",
        "reports/kojto_optimizer_2d_reports.xml",
        "reports/kojto_optimizer_2d_templates.xml",
        "reports/kojto_optimizer_2dr_reports.xml",
        "reports/kojto_optimizer_2dr_templates.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
