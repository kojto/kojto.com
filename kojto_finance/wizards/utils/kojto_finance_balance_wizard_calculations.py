# -*- coding: utf-8 -*-
"""
Kojto Finance Balance Wizard - Calculations

Contains calculation methods for subcode balance aggregation.
"""

from datetime import datetime
from .kojto_finance_balance_wizard_sql import execute_subcode_financials_query


def get_breakdown_records(env, date_from, date_to, datetime_from, datetime_to, subcode_ids=None, code_ids=None, maincode_ids=None):
    """
    Get breakdown records for balance lines.

    Args:
        env: Odoo environment
        date_from: Start date
        date_to: End date
        datetime_from: Start datetime
        datetime_to: End datetime
        subcode_ids: List of subcode IDs (for subcode balance lines)
        code_ids: List of code IDs (for code balance lines)
        maincode_ids: List of maincode IDs (for maincode balance lines)
        None: For company balance lines (all records)

    Returns:
        dict: Dictionary with breakdown records for each type
    """
    try:
        breakdown = {
            'outgoing_pre_vat_total': env['kojto.finance.invoice.contents'].browse([]),
            'incoming_pre_vat_total': env['kojto.finance.invoice.contents'].browse([]),
            'invoiceless_revenue': env['kojto.finance.cashflow.allocation'].browse([]),
            'invoiceless_expenses': env['kojto.finance.cashflow.allocation'].browse([]),
            'hr_time_tracking': env['kojto.hr.time.tracking'].browse([]),
            'assets_works': env['kojto.asset.works'].browse([]),
        }

        # Build domain for subcode filtering
        if subcode_ids:
            subcode_domain = [('subcode_id', 'in', subcode_ids)]
        elif code_ids:
            # Get all subcodes for these codes
            subcodes = env['kojto.commission.subcodes'].search([('code_id', 'in', code_ids)])
            subcode_domain = [('subcode_id', 'in', subcodes.ids)]
        elif maincode_ids:
            # Get all subcodes for these maincodes
            subcodes = env['kojto.commission.subcodes'].search([('maincode_id', 'in', maincode_ids)])
            subcode_domain = [('subcode_id', 'in', subcodes.ids)]
        else:
            # Company level - no subcode filter
            subcode_domain = []

        # Outgoing pre-VAT total: invoice contents with outgoing invoices
        outgoing_invoices = env['kojto.finance.invoices'].search([
            ('date_issue', '>=', date_from),
            ('date_issue', '<=', date_to),
            ('invoice_type', '!=', 'proforma'),
            ('document_in_out_type', '=', 'outgoing'),
        ])
        if outgoing_invoices:
            domain = [
                ('invoice_id', 'in', outgoing_invoices.ids),
                ('subcode_id', '!=', False),
            ] + subcode_domain
            breakdown['outgoing_pre_vat_total'] = env['kojto.finance.invoice.contents'].search(domain)

        # Incoming pre-VAT total: invoice contents with incoming invoices
        incoming_invoices = env['kojto.finance.invoices'].search([
            ('date_issue', '>=', date_from),
            ('date_issue', '<=', date_to),
            ('invoice_type', '!=', 'proforma'),
            ('document_in_out_type', '=', 'incoming'),
        ])
        if incoming_invoices:
            domain = [
                ('invoice_id', 'in', incoming_invoices.ids),
                ('subcode_id', '!=', False),
            ] + subcode_domain
            breakdown['incoming_pre_vat_total'] = env['kojto.finance.invoice.contents'].search(domain)

        # Invoiceless revenue: cash allocations with incoming direction, no invoice
        ir_domain = [
            ('transaction_id.date_value', '>=', date_from),
            ('transaction_id.date_value', '<=', date_to),
            ('transaction_id.transaction_direction', '=', 'incoming'),
            ('amount', '>', 0),
            ('invoice_id', '=', False),
            ('subcode_id.code_id.maincode_id.cash_flow_only', '=', False),
            ('cash_flow_only', '=', False),
        ]
        if subcode_ids:
            ir_domain.append(('subcode_id', 'in', subcode_ids))
        elif code_ids:
            subcodes = env['kojto.commission.subcodes'].search([('code_id', 'in', code_ids)])
            ir_domain.append(('subcode_id', 'in', subcodes.ids))
        elif maincode_ids:
            subcodes = env['kojto.commission.subcodes'].search([('maincode_id', 'in', maincode_ids)])
            ir_domain.append(('subcode_id', 'in', subcodes.ids))
        breakdown['invoiceless_revenue'] = env['kojto.finance.cashflow.allocation'].search(ir_domain)

        # Invoiceless expenses: cash allocations with outgoing direction, no invoice
        ie_domain = [
            ('transaction_id.date_value', '>=', date_from),
            ('transaction_id.date_value', '<=', date_to),
            ('transaction_id.transaction_direction', '=', 'outgoing'),
            ('amount', '>', 0),
            ('invoice_id', '=', False),
            ('subcode_id.code_id.maincode_id.cash_flow_only', '=', False),
            ('cash_flow_only', '=', False),
        ]
        if subcode_ids:
            ie_domain.append(('subcode_id', 'in', subcode_ids))
        elif code_ids:
            subcodes = env['kojto.commission.subcodes'].search([('code_id', 'in', code_ids)])
            ie_domain.append(('subcode_id', 'in', subcodes.ids))
        elif maincode_ids:
            subcodes = env['kojto.commission.subcodes'].search([('maincode_id', 'in', maincode_ids)])
            ie_domain.append(('subcode_id', 'in', subcodes.ids))
        breakdown['invoiceless_expenses'] = env['kojto.finance.cashflow.allocation'].search(ie_domain)

        # Time tracking: records in date range
        tt_domain = [
            ('datetime_start', '>=', datetime_from),
            ('datetime_start', '<=', datetime_to),
        ]
        if subcode_ids:
            tt_domain.append('|')
            tt_domain.append(('subcode_id', 'in', subcode_ids))
            tt_domain.append(('credited_subcode_id', 'in', subcode_ids))
        elif code_ids:
            subcodes = env['kojto.commission.subcodes'].search([('code_id', 'in', code_ids)])
            tt_domain.append('|')
            tt_domain.append(('subcode_id', 'in', subcodes.ids))
            tt_domain.append(('credited_subcode_id', 'in', subcodes.ids))
        elif maincode_ids:
            subcodes = env['kojto.commission.subcodes'].search([('maincode_id', 'in', maincode_ids)])
            tt_domain.append('|')
            tt_domain.append(('subcode_id', 'in', subcodes.ids))
            tt_domain.append(('credited_subcode_id', 'in', subcodes.ids))
        breakdown['hr_time_tracking'] = env['kojto.hr.time.tracking'].search(tt_domain)

        # Asset works: records in date range
        aw_domain = [
            ('datetime_start', '>=', datetime_from),
            ('datetime_start', '<=', datetime_to),
        ]
        if subcode_ids:
            aw_domain.append('|')
            aw_domain.append(('subcode_id', 'in', subcode_ids))
            aw_domain.append(('credited_subcode_id', 'in', subcode_ids))
        elif code_ids:
            subcodes = env['kojto.commission.subcodes'].search([('code_id', 'in', code_ids)])
            aw_domain.append('|')
            aw_domain.append(('subcode_id', 'in', subcodes.ids))
            aw_domain.append(('credited_subcode_id', 'in', subcodes.ids))
        elif maincode_ids:
            subcodes = env['kojto.commission.subcodes'].search([('maincode_id', 'in', maincode_ids)])
            aw_domain.append('|')
            aw_domain.append(('subcode_id', 'in', subcodes.ids))
            aw_domain.append(('credited_subcode_id', 'in', subcodes.ids))
        breakdown['assets_works'] = env['kojto.asset.works'].search(aw_domain)

        return breakdown
    except Exception:
        # Return empty breakdown on error
        return {
            'outgoing_pre_vat_total': env['kojto.finance.invoice.contents'].browse([]),
            'incoming_pre_vat_total': env['kojto.finance.invoice.contents'].browse([]),
            'invoiceless_revenue': env['kojto.finance.cashflow.allocation'].browse([]),
            'invoiceless_expenses': env['kojto.finance.cashflow.allocation'].browse([]),
            'hr_time_tracking': env['kojto.hr.time.tracking'].browse([]),
            'assets_works': env['kojto.asset.works'].browse([]),
        }


def calculate_subcode_balance(env, date_from, date_to):
    """
    Calculate subcode balance - returns calculated data only (no record creation).

    Args:
        env: Odoo environment
        date_from: Start date
        date_to: End date

    Returns:
        dict: Dictionary containing:
            - subcode_balance_lines: List of dicts with balance line data
            - code_balance_lines: List of dicts with code balance line data
            - maincode_balance_lines: List of dicts with maincode balance line data
            - company_balance_lines: List of dicts with company balance line data
    """
    if not date_from or not date_to:
        return {
            'subcode_balance_lines': [],
            'code_balance_lines': [],
            'maincode_balance_lines': [],
            'company_balance_lines': [],
        }

    if date_from > date_to:
        return {
            'subcode_balance_lines': [],
            'code_balance_lines': [],
            'maincode_balance_lines': [],
            'company_balance_lines': [],
        }

    # Convert dates to datetime for proper comparison
    datetime_from = datetime.combine(date_from, datetime.min.time())
    datetime_to = datetime.combine(date_to, datetime.max.time())

    # Find subcodes with time tracking events (both work subcodes and costcenter subcodes)
    time_tracking_records = env['kojto.hr.time.tracking'].search([
        ('datetime_start', '>=', datetime_from),
        ('datetime_start', '<=', datetime_to),
    ])
    time_tracking_work_subcodes = time_tracking_records.mapped('subcode_id')
    time_tracking_costcenter_subcodes = time_tracking_records.mapped('credited_subcode_id').filtered(lambda x: x)

    # Find subcodes with asset works
    asset_works_records = env['kojto.asset.works'].search([
        ('datetime_start', '>=', datetime_from),
        ('datetime_start', '<=', datetime_to),
    ])
    asset_works_subcodes = asset_works_records.mapped('subcode_id')

    # Find invoices in the period
    invoices = env['kojto.finance.invoices'].search([
        ('date_issue', '>=', date_from),
        ('date_issue', '<=', date_to),
        ('invoice_type', '!=', 'proforma'),
    ])

    # Find cash allocations in the period
    cash_allocations = env['kojto.finance.cashflow.allocation'].search([
        ('transaction_id.date_value', '>=', date_from),
        ('transaction_id.date_value', '<=', date_to),
    ])

    # Combine all unique subcodes (including both work and costcenter subcodes from time tracking)
    invoice_subcodes = invoices.mapped('subcode_id')
    cash_allocation_subcodes = cash_allocations.mapped('subcode_id')
    all_subcodes = (
        time_tracking_work_subcodes |
        time_tracking_costcenter_subcodes |
        asset_works_subcodes |
        invoice_subcodes |
        cash_allocation_subcodes
    )

    # Calculate revenue and expense per subcode using SQL (same approach as dashboard)
    query_results = execute_subcode_financials_query(
        env,
        date_from,
        date_to,
        datetime_from,
        datetime_to
    )

    # Build dictionary of financials by subcode
    subcode_financials = {}
    for row in query_results:
        subcode_id, outgoing_pre_vat_total, incoming_pre_vat_total, invoiceless_revenue, invoiceless_expenses, time_tracking_total, time_tracking_hours, assets_total = row
        if subcode_id:
            # Time tracking values: negative for work subcode (depletes), positive for costcenter subcode (credited)
            # Asset works values: negative for work subcode (depletes), positive for credited subcode (credited)
            # This is already handled in the SQL query
            subcode_financials[subcode_id] = {
                'outgoing_pre_vat_total': outgoing_pre_vat_total or 0.0,
                'incoming_pre_vat_total': incoming_pre_vat_total or 0.0,
                'invoiceless_revenue': invoiceless_revenue or 0.0,
                'invoiceless_expenses': invoiceless_expenses or 0.0,
                'time_tracking_total': time_tracking_total or 0.0,
                'time_tracking_hours': time_tracking_hours or 0.0,
                'assets_total': assets_total or 0.0,
            }

    # Calculate balance lines for all subcodes, excluding those where all columns are 0
    balance_lines = []
    for subcode in all_subcodes:
        financials = subcode_financials.get(subcode.id, {
            'outgoing_pre_vat_total': 0.0,
            'incoming_pre_vat_total': 0.0,
            'invoiceless_revenue': 0.0,
            'invoiceless_expenses': 0.0,
            'time_tracking_total': 0.0,
            'time_tracking_hours': 0.0,
            'assets_total': 0.0,
        })

        # Check if all financial columns are zero (including time tracking and asset works)
        # Use abs() for time tracking and asset works since they're stored as negative values
        if (financials['outgoing_pre_vat_total'] == 0.0 and
            financials['incoming_pre_vat_total'] == 0.0 and
            financials['invoiceless_revenue'] == 0.0 and
            financials['invoiceless_expenses'] == 0.0 and
            abs(financials['time_tracking_total']) == 0.0 and
            abs(financials['time_tracking_hours']) == 0.0 and
            abs(financials['assets_total']) == 0.0):
            continue  # Skip subcodes with all zeros

        # Calculate result (includes TT total and Assets total which are already negative)
        result = (
            financials['outgoing_pre_vat_total']
            - financials['incoming_pre_vat_total']
            - financials['invoiceless_expenses']
            + financials['invoiceless_revenue']
            + financials['time_tracking_total']
            + financials['assets_total']
        )

        balance_lines.append({
            'subcode_id': subcode.id,
            'date_from': date_from,
            'date_to': date_to,
            'outgoing_pre_vat_total': financials['outgoing_pre_vat_total'],
            'incoming_pre_vat_total': financials['incoming_pre_vat_total'],
            'invoiceless_revenue': financials['invoiceless_revenue'],
            'invoiceless_expenses': financials['invoiceless_expenses'],
            'time_tracking_total': financials['time_tracking_total'],
            'time_tracking_hours': financials['time_tracking_hours'],
            'assets_total': financials['assets_total'],
            'result': result,
        })

    # Calculate consolidated balances by code and maincode
    code_balance_lines = calculate_code_balance(all_subcodes, subcode_financials, date_from, date_to)
    maincode_balance_lines = calculate_maincode_balance(all_subcodes, subcode_financials, date_from, date_to)
    company_balance_lines = calculate_company_balance(all_subcodes, subcode_financials, date_from, date_to)

    return {
        'subcode_balance_lines': balance_lines,
        'code_balance_lines': code_balance_lines,
        'maincode_balance_lines': maincode_balance_lines,
        'company_balance_lines': company_balance_lines,
    }

def calculate_code_balance(all_subcodes, subcode_financials, date_from, date_to):
    """Consolidate subcode balances by code - returns calculated data only (no record creation)"""
    # Build dictionary to aggregate by code_id
    code_aggregates = {}

    # Aggregate by code from all subcodes
    for subcode in all_subcodes:
        financials = subcode_financials.get(subcode.id, {
            'outgoing_pre_vat_total': 0.0,
            'incoming_pre_vat_total': 0.0,
            'invoiceless_revenue': 0.0,
            'invoiceless_expenses': 0.0,
            'time_tracking_total': 0.0,
            'time_tracking_hours': 0.0,
            'assets_total': 0.0,
        })

        # Check if all financial columns are zero (including time tracking and asset works)
        if (financials['outgoing_pre_vat_total'] == 0.0 and
            financials['incoming_pre_vat_total'] == 0.0 and
            financials['invoiceless_revenue'] == 0.0 and
            financials['invoiceless_expenses'] == 0.0 and
            abs(financials['time_tracking_total']) == 0.0 and
            abs(financials['time_tracking_hours']) == 0.0 and
            abs(financials['assets_total']) == 0.0):
            continue  # Skip subcodes with all zeros

        code_id = subcode.code_id.id

        if code_id not in code_aggregates:
            code_aggregates[code_id] = {
                'code_id': code_id,
                'outgoing_pre_vat_total': 0.0,
                'incoming_pre_vat_total': 0.0,
                'invoiceless_revenue': 0.0,
                'invoiceless_expenses': 0.0,
                'time_tracking_total': 0.0,
                'time_tracking_hours': 0.0,
                'assets_total': 0.0,
            }

        # Aggregate values
        code_aggregates[code_id]['outgoing_pre_vat_total'] += financials['outgoing_pre_vat_total']
        code_aggregates[code_id]['incoming_pre_vat_total'] += financials['incoming_pre_vat_total']
        code_aggregates[code_id]['invoiceless_revenue'] += financials['invoiceless_revenue']
        code_aggregates[code_id]['invoiceless_expenses'] += financials['invoiceless_expenses']
        code_aggregates[code_id]['time_tracking_total'] += financials['time_tracking_total']
        code_aggregates[code_id]['time_tracking_hours'] += financials['time_tracking_hours']
        code_aggregates[code_id]['assets_total'] += financials['assets_total']

    # Build balance lines data
    balance_lines = []
    for code_id, aggregates in code_aggregates.items():
        # Calculate result (includes TT total and Assets total which are already negative)
        result = (
            aggregates['outgoing_pre_vat_total']
            - aggregates['incoming_pre_vat_total']
            - aggregates['invoiceless_expenses']
            + aggregates['invoiceless_revenue']
            + aggregates['time_tracking_total']
            + aggregates['assets_total']
        )

        balance_lines.append({
            'code_id': code_id,
            'date_from': date_from,
            'date_to': date_to,
            'outgoing_pre_vat_total': aggregates['outgoing_pre_vat_total'],
            'incoming_pre_vat_total': aggregates['incoming_pre_vat_total'],
            'invoiceless_revenue': aggregates['invoiceless_revenue'],
            'invoiceless_expenses': aggregates['invoiceless_expenses'],
            'time_tracking_total': aggregates['time_tracking_total'],
            'time_tracking_hours': aggregates['time_tracking_hours'],
            'assets_total': aggregates['assets_total'],
            'result': result,
        })

    return balance_lines


def calculate_maincode_balance(all_subcodes, subcode_financials, date_from, date_to):
    """Consolidate subcode balances by maincode - returns calculated data only (no record creation)"""
    # Build dictionary to aggregate by maincode_id
    maincode_aggregates = {}

    # Aggregate by maincode from all subcodes
    for subcode in all_subcodes:
        financials = subcode_financials.get(subcode.id, {
            'outgoing_pre_vat_total': 0.0,
            'incoming_pre_vat_total': 0.0,
            'invoiceless_revenue': 0.0,
            'invoiceless_expenses': 0.0,
            'time_tracking_total': 0.0,
            'time_tracking_hours': 0.0,
            'assets_total': 0.0,
        })

        # Check if all financial columns are zero (including time tracking and asset works)
        if (financials['outgoing_pre_vat_total'] == 0.0 and
            financials['incoming_pre_vat_total'] == 0.0 and
            financials['invoiceless_revenue'] == 0.0 and
            financials['invoiceless_expenses'] == 0.0 and
            abs(financials['time_tracking_total']) == 0.0 and
            abs(financials['time_tracking_hours']) == 0.0 and
            abs(financials['assets_total']) == 0.0):
            continue  # Skip subcodes with all zeros

        maincode_id = subcode.maincode_id.id

        if maincode_id not in maincode_aggregates:
            maincode_aggregates[maincode_id] = {
                'maincode_id': maincode_id,
                'outgoing_pre_vat_total': 0.0,
                'incoming_pre_vat_total': 0.0,
                'invoiceless_revenue': 0.0,
                'invoiceless_expenses': 0.0,
                'time_tracking_total': 0.0,
                'time_tracking_hours': 0.0,
                'assets_total': 0.0,
            }

        # Aggregate values
        maincode_aggregates[maincode_id]['outgoing_pre_vat_total'] += financials['outgoing_pre_vat_total']
        maincode_aggregates[maincode_id]['incoming_pre_vat_total'] += financials['incoming_pre_vat_total']
        maincode_aggregates[maincode_id]['invoiceless_revenue'] += financials['invoiceless_revenue']
        maincode_aggregates[maincode_id]['invoiceless_expenses'] += financials['invoiceless_expenses']
        maincode_aggregates[maincode_id]['time_tracking_total'] += financials['time_tracking_total']
        maincode_aggregates[maincode_id]['time_tracking_hours'] += financials['time_tracking_hours']
        maincode_aggregates[maincode_id]['assets_total'] += financials['assets_total']

    # Build balance lines data
    balance_lines = []
    for maincode_id, aggregates in maincode_aggregates.items():
        # Calculate result (includes TT total and Assets total which are already negative)
        result = (
            aggregates['outgoing_pre_vat_total']
            - aggregates['incoming_pre_vat_total']
            - aggregates['invoiceless_expenses']
            + aggregates['invoiceless_revenue']
            + aggregates['time_tracking_total']
            + aggregates['assets_total']
        )

        balance_lines.append({
            'maincode_id': maincode_id,
            'date_from': date_from,
            'date_to': date_to,
            'outgoing_pre_vat_total': aggregates['outgoing_pre_vat_total'],
            'incoming_pre_vat_total': aggregates['incoming_pre_vat_total'],
            'invoiceless_revenue': aggregates['invoiceless_revenue'],
            'invoiceless_expenses': aggregates['invoiceless_expenses'],
            'time_tracking_total': aggregates['time_tracking_total'],
            'time_tracking_hours': aggregates['time_tracking_hours'],
            'assets_total': aggregates['assets_total'],
            'result': result,
        })

    return balance_lines


def calculate_company_balance(all_subcodes, subcode_financials, date_from, date_to):
    """Consolidate all subcode balances into a single company line - returns calculated data only (no record creation)"""
    # Aggregate all subcodes
    company_aggregates = {
        'outgoing_pre_vat_total': 0.0,
        'incoming_pre_vat_total': 0.0,
        'invoiceless_revenue': 0.0,
        'invoiceless_expenses': 0.0,
        'time_tracking_total': 0.0,
        'time_tracking_hours': 0.0,
        'assets_total': 0.0,
    }

    # Aggregate all subcodes
    for subcode in all_subcodes:
        financials = subcode_financials.get(subcode.id, {
            'outgoing_pre_vat_total': 0.0,
            'incoming_pre_vat_total': 0.0,
            'invoiceless_revenue': 0.0,
            'invoiceless_expenses': 0.0,
            'time_tracking_total': 0.0,
            'time_tracking_hours': 0.0,
            'assets_total': 0.0,
        })

        # Check if all financial columns are zero (including time tracking and asset works)
        if (financials['outgoing_pre_vat_total'] == 0.0 and
            financials['incoming_pre_vat_total'] == 0.0 and
            financials['invoiceless_revenue'] == 0.0 and
            financials['invoiceless_expenses'] == 0.0 and
            abs(financials['time_tracking_total']) == 0.0 and
            abs(financials['time_tracking_hours']) == 0.0 and
            abs(financials['assets_total']) == 0.0):
            continue  # Skip subcodes with all zeros

        # Aggregate values
        company_aggregates['outgoing_pre_vat_total'] += financials['outgoing_pre_vat_total']
        company_aggregates['incoming_pre_vat_total'] += financials['incoming_pre_vat_total']
        company_aggregates['invoiceless_revenue'] += financials['invoiceless_revenue']
        company_aggregates['invoiceless_expenses'] += financials['invoiceless_expenses']
        company_aggregates['time_tracking_total'] += financials['time_tracking_total']
        company_aggregates['time_tracking_hours'] += financials['time_tracking_hours']
        company_aggregates['assets_total'] += financials['assets_total']

    # Calculate result (includes TT total and Assets total which are already negative)
    result = (
        company_aggregates['outgoing_pre_vat_total']
        - company_aggregates['incoming_pre_vat_total']
        - company_aggregates['invoiceless_expenses']
        + company_aggregates['invoiceless_revenue']
        + company_aggregates['time_tracking_total']
        + company_aggregates['assets_total']
    )

    # Build single balance line data
    balance_line_data = {
        'date_from': date_from,
        'date_to': date_to,
        'outgoing_pre_vat_total': company_aggregates['outgoing_pre_vat_total'],
        'incoming_pre_vat_total': company_aggregates['incoming_pre_vat_total'],
        'invoiceless_revenue': company_aggregates['invoiceless_revenue'],
        'invoiceless_expenses': company_aggregates['invoiceless_expenses'],
        'time_tracking_total': company_aggregates['time_tracking_total'],
        'time_tracking_hours': company_aggregates['time_tracking_hours'],
        'assets_total': company_aggregates['assets_total'],
        'result': result,
    }

    return [balance_line_data]

