# -*- coding: utf-8 -*-
{
    'name': 'Kojto Energy Management',
    'version': '18.04.08',
    'category': 'Energy',
    'summary': 'Energy Management and Price Tracking',
    'description': """
        Energy Management Module
        ========================
        * Track energy prices (BGN and EUR per MWh)
        * Monitor energy volumes
        * Manage exchange data (IBEX)
        * Period tracking in CET and UTC
    """,
    'author': 'KOJTO',
    'website': 'https://www.kojto.com',
    'depends': [
        'base',
        'kojto_base',
        'kojto_landingpage',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/cron_sync_hourly_reports.xml',
        'views/kojto_energy_management_prices_views.xml',
        'views/kojto_energy_management_base_prices_views.xml',
        'views/kojto_energy_management_devices_views.xml',
        'views/kojto_energy_management_power_meter_readings_views.xml',
        'views/kojto_energy_management_monthly_summary_views.xml',
        'views/kojto_energy_management_menu_views.xml',
        'views/kojto_energy_management_buttons.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}

