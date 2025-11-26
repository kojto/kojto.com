# -*- coding: utf-8 -*-
"""
Kojto Finance Balance Wizard - Actions

Contains action methods for the wizard.
"""

from odoo.exceptions import UserError
from datetime import datetime
import io
import base64
import xlsxwriter


def action_search_activities(wizard):
    """Search for subcodes with activity in the selected date range and calculate revenue/expense"""
    wizard.ensure_one()

    if wizard.date_from > wizard.date_to:
        raise UserError("From date cannot be after To date.")

    # Use the wizard's creation method which handles both calculation and record creation
    wizard._create_balance_lines()

    return {
        'type': 'ir.actions.act_window',
        'res_model': 'kojto.finance.balance.wizard',
        'res_id': wizard.id,
        'view_mode': 'form',
        'target': 'new',
    }


def action_view_time_tracking(wizard):
    """Open time tracking records for the selected period"""
    wizard.ensure_one()
    datetime_from = datetime.combine(wizard.date_from, datetime.min.time())
    datetime_to = datetime.combine(wizard.date_to, datetime.max.time())

    return {
        'type': 'ir.actions.act_window',
        'name': 'Time Tracking Events',
        'res_model': 'kojto.hr.time.tracking',
        'view_mode': 'list,form',
        'domain': [
            ('datetime_start', '>=', datetime_from),
            ('datetime_start', '<=', datetime_to),
        ],
    }


def action_view_asset_works(wizard):
    """Open asset works records for the selected period"""
    wizard.ensure_one()
    datetime_from = datetime.combine(wizard.date_from, datetime.min.time())
    datetime_to = datetime.combine(wizard.date_to, datetime.max.time())

    return {
        'type': 'ir.actions.act_window',
        'name': 'Asset Works',
        'res_model': 'kojto.asset.works',
        'view_mode': 'list,form',
        'domain': [
            ('datetime_start', '>=', datetime_from),
            ('datetime_start', '<=', datetime_to),
        ],
    }


def action_view_invoices(wizard):
    """Open invoice records for the selected period"""
    wizard.ensure_one()

    return {
        'type': 'ir.actions.act_window',
        'name': 'Invoices',
        'res_model': 'kojto.finance.invoices',
        'view_mode': 'list,form',
        'domain': [
            ('date_issue', '>=', wizard.date_from),
            ('date_issue', '<=', wizard.date_to),
        ],
    }


def action_view_cash_allocations(wizard):
    """Open cash allocation records for the selected period"""
    wizard.ensure_one()

    return {
        'type': 'ir.actions.act_window',
        'name': 'Cash Allocations',
        'res_model': 'kojto.finance.cashflow.allocation',
        'view_mode': 'list,form',
        'domain': [
            ('transaction_id.date_value', '>=', wizard.date_from),
            ('transaction_id.date_value', '<=', wizard.date_to),
        ],
    }


def action_view_subcodes(wizard):
    """Open subcode records that have activity in the period"""
    wizard.ensure_one()

    return {
        'type': 'ir.actions.act_window',
        'name': 'Active Subcodes',
        'res_model': 'kojto.commission.subcodes',
        'view_mode': 'list,form',
        'domain': [('id', 'in', wizard.subcode_balance_line_ids.mapped('subcode_id').ids)],
    }


def action_view_missing_subcodes(wizard):
    """Identify time tracking records with missing subcode_id or credited_subcode_id"""
    wizard.ensure_one()
    datetime_from = datetime.combine(wizard.date_from, datetime.min.time())
    datetime_to = datetime.combine(wizard.date_to, datetime.max.time())

    # Find time tracking records in the period
    time_tracking_records = wizard.env['kojto.hr.time.tracking'].search([
        ('datetime_start', '>=', datetime_from),
        ('datetime_start', '<=', datetime_to),
        ('total_hours', '>', 0),
    ])

    # Find records with missing subcode_id (shouldn't happen as it's required, but check anyway)
    missing_work_subcode = time_tracking_records.filtered(lambda r: not r.subcode_id)

    # Find records with missing credited_subcode_id (no subcode rate found)
    missing_credited_subcode = time_tracking_records.filtered(lambda r: not r.credited_subcode_id)

    # Check for employees with time tracking but NO subcode rates defined at all
    employees_with_tt = time_tracking_records.mapped('employee_id')
    all_subcode_rates = wizard.env['kojto.hr.employee.subcode.rates'].search([])
    # employee_id in subcode rates is an Integer field, not Many2one
    employee_ids_with_rates = set(all_subcode_rates.mapped('employee_id'))
    employees_without_rates = employees_with_tt.filtered(lambda e: e.id not in employee_ids_with_rates)

    # Check for employees with time tracking but no rates valid for the date range
    employees_without_valid_rates = []
    employee_ids_without_rates = set(employees_without_rates.mapped('id'))
    for employee in employees_with_tt:
        if employee.id in employee_ids_without_rates:
            continue  # Already flagged as having no rates at all
        # Check if there's any rate valid for any time tracking record of this employee
        employee_tt_records = time_tracking_records.filtered(lambda r: r.employee_id.id == employee.id)
        has_valid_rate = False
        for tt_record in employee_tt_records:
            valid_rate = wizard.env['kojto.hr.employee.subcode.rates'].search([
                ('employee_id', '=', employee.id),
                ('datetime_start', '<=', tt_record.datetime_start),
            ], order='datetime_start desc', limit=1)
            if valid_rate:
                has_valid_rate = True
                break
        if not has_valid_rate:
            employees_without_valid_rates.append(employee)

    # Combine both issues
    problem_records = missing_work_subcode | missing_credited_subcode
    problem_records = problem_records.sorted('datetime_start', reverse=True)

    if not problem_records and not employees_without_rates and not employees_without_valid_rates:
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'No Missing Subcodes',
                'message': 'All time tracking records in the selected period have both subcode_id and credited_subcode_id set.',
                'type': 'success',
                'sticky': False,
            }
        }

    # Build detailed error message
    message_parts = []
    if missing_work_subcode:
        message_parts.append(f"{len(missing_work_subcode)} time tracking record(s) with missing subcode_id in the time tracking record itself")
    if missing_credited_subcode:
        message_parts.append(f"{len(missing_credited_subcode)} time tracking record(s) with missing credited_subcode_id (no employee subcode rate found for the employee at that date)")
    if employees_without_rates:
        employee_names = ', '.join(employees_without_rates.mapped('name')[:5])
        if len(employees_without_rates) > 5:
            employee_names += f" and {len(employees_without_rates) - 5} more"
        message_parts.append(f"{len(employees_without_rates)} employee(s) with time tracking but NO subcode rates defined at all: {employee_names}")
    if employees_without_valid_rates:
        employee_names = ', '.join([e.name for e in employees_without_valid_rates[:5]])
        if len(employees_without_valid_rates) > 5:
            employee_names += f" and {len(employees_without_valid_rates) - 5} more"
        message_parts.append(f"{len(employees_without_valid_rates)} employee(s) with time tracking but no valid subcode rates for the date range: {employee_names}")

    error_message = "Found the following issues:\n\n" + "\n".join(f"• {part}" for part in message_parts)
    error_message += "\n\nPlease check:\n"
    if missing_work_subcode:
        error_message += "• Time tracking records should always have a subcode_id set\n"
    if missing_credited_subcode or employees_without_rates or employees_without_valid_rates:
        error_message += "• Employee subcode rates: Ensure there is a rate record for each employee with datetime_start <= the time tracking datetime_start\n"
        if employees_without_rates:
            error_message += "• Create subcode rate records for employees with time tracking but no rates defined\n"

    return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
            'title': 'Missing Subcodes Found',
            'message': error_message,
            'type': 'warning',
            'sticky': True,
        }
    }


def action_export_balance_to_excel(wizard):
    """Export all balance data to Excel with separate sheets for each consolidation level"""
    wizard.ensure_one()

    if not wizard.subcode_balance_line_ids:
        raise UserError("No data to export. Please compute the balance first.")

    # Create Excel file in memory
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})

    # Define formats
    bold_format = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3'})
    currency_format = workbook.add_format({'num_format': '#,##0.00'})
    header_format = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'align': 'center'})

    currency = wizard.currency_id or wizard.env.ref('base.EUR')

    # Helper function to write balance lines to a worksheet
    def write_balance_sheet(worksheet, lines, headers, name_cols):
        """Write balance lines to worksheet"""
        # Write headers
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)

        # Write data
        for row, line in enumerate(lines, start=1):
            col = 0
            for name_col in name_cols:
                worksheet.write(row, col, getattr(line, name_col, '') or '')
                col += 1
            worksheet.write(row, col, line.outgoing_pre_vat_total or 0.0, currency_format)
            col += 1
            worksheet.write(row, col, line.incoming_pre_vat_total or 0.0, currency_format)
            col += 1
            worksheet.write(row, col, line.invoiceless_revenue or 0.0, currency_format)
            col += 1
            worksheet.write(row, col, line.invoiceless_expenses or 0.0, currency_format)
            col += 1
            worksheet.write(row, col, line.time_tracking_hours or 0.0, currency_format)
            col += 1
            worksheet.write(row, col, line.time_tracking_total or 0.0, currency_format)
            col += 1
            worksheet.write(row, col, line.assets_total or 0.0, currency_format)
            col += 1
            worksheet.write(row, col, line.result or 0.0, currency_format)

        # Write totals row
        if lines:
            total_row = len(lines) + 1
            # Write TOTAL label in first column
            if name_cols:
                worksheet.write(total_row, 0, 'TOTAL', bold_format)
                start_col = len(name_cols)
            else:
                worksheet.write(total_row, 0, 'TOTAL', bold_format)
                start_col = 0
            worksheet.write(total_row, start_col, sum(lines.mapped('outgoing_pre_vat_total')), currency_format)
            worksheet.write(total_row, start_col + 1, sum(lines.mapped('incoming_pre_vat_total')), currency_format)
            worksheet.write(total_row, start_col + 2, sum(lines.mapped('invoiceless_revenue')), currency_format)
            worksheet.write(total_row, start_col + 3, sum(lines.mapped('invoiceless_expenses')), currency_format)
            worksheet.write(total_row, start_col + 4, sum(lines.mapped('time_tracking_hours')), currency_format)
            worksheet.write(total_row, start_col + 5, sum(lines.mapped('time_tracking_total')), currency_format)
            worksheet.write(total_row, start_col + 6, sum(lines.mapped('assets_total')), currency_format)
            worksheet.write(total_row, start_col + 7, sum(lines.mapped('result')), currency_format)

    # Sheet 1: Company Balance
    if wizard.company_balance_line_ids:
        worksheet = workbook.add_worksheet('Company Balance')
        headers = [
            'Pre-VAT Tot. (OUT)', 'Pre-VAT Tot. (IN)',
            'Invoiceless Revenue', 'Invoiceless Expenses',
            'TT Hours', 'TT Total', 'Assets Total', 'Result'
        ]
        # Write headers
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)

        # Write data (only one row for company balance - no totals row needed)
        line = wizard.company_balance_line_ids[0]
        worksheet.write(1, 0, line.outgoing_pre_vat_total or 0.0, currency_format)
        worksheet.write(1, 1, line.incoming_pre_vat_total or 0.0, currency_format)
        worksheet.write(1, 2, line.invoiceless_revenue or 0.0, currency_format)
        worksheet.write(1, 3, line.invoiceless_expenses or 0.0, currency_format)
        worksheet.write(1, 4, line.time_tracking_hours or 0.0, currency_format)
        worksheet.write(1, 5, line.time_tracking_total or 0.0, currency_format)
        worksheet.write(1, 6, line.assets_total or 0.0, currency_format)
        worksheet.write(1, 7, line.result or 0.0, currency_format)

        worksheet.set_column(0, 7, 18)  # Financial columns

    # Sheet 2: Main Code Balance
    if wizard.maincode_balance_line_ids:
        worksheet = workbook.add_worksheet('Main Code Balance')
        headers = [
            'Main Code', 'Description',
            'Pre-VAT Tot. (OUT)', 'Pre-VAT Tot. (IN)',
            'Invoiceless Revenue', 'Invoiceless Expenses',
            'TT Hours', 'TT Total', 'Assets Total', 'Result'
        ]
        write_balance_sheet(worksheet, wizard.maincode_balance_line_ids, headers, ['maincode', 'description'])
        worksheet.set_column(0, 0, 15)  # Main Code
        worksheet.set_column(1, 1, 30)  # Description
        worksheet.set_column(2, 9, 18)  # Financial columns

    # Sheet 3: Code Balance
    if wizard.code_balance_line_ids:
        worksheet = workbook.add_worksheet('Code Balance')
        headers = [
            'Code Name', 'Description',
            'Pre-VAT Tot. (OUT)', 'Pre-VAT Tot. (IN)',
            'Invoiceless Revenue', 'Invoiceless Expenses',
            'TT Hours', 'TT Total', 'Assets Total', 'Result'
        ]
        write_balance_sheet(worksheet, wizard.code_balance_line_ids, headers, ['code_name', 'description'])
        worksheet.set_column(0, 0, 30)  # Code Name
        worksheet.set_column(1, 1, 30)  # Description
        worksheet.set_column(2, 9, 18)  # Financial columns

    # Sheet 4: Subcode Balance
    if wizard.subcode_balance_line_ids:
        worksheet = workbook.add_worksheet('Subcode Balance')
        headers = [
            'Subcode Name', 'Description',
            'Pre-VAT Tot. (OUT)', 'Pre-VAT Tot. (IN)',
            'Invoiceless Revenue', 'Invoiceless Expenses',
            'TT Hours', 'TT Total', 'Assets Total', 'Result'
        ]
        write_balance_sheet(worksheet, wizard.subcode_balance_line_ids, headers, ['subcode_name', 'description'])
        worksheet.set_column(0, 0, 30)  # Subcode Name
        worksheet.set_column(1, 1, 30)  # Description
        worksheet.set_column(2, 9, 18)  # Financial columns

    workbook.close()
    output.seek(0)

    # Create attachment
    file_data = output.read()
    file_data_base64 = base64.b64encode(file_data).decode('utf-8')
    filename = f"Subcode_Balance_{wizard.date_from}_{wizard.date_to}.xlsx"

    attachment = wizard.env['ir.attachment'].create({
        'name': filename,
        'type': 'binary',
        'datas': file_data_base64,
        'res_model': wizard._name,
        'res_id': wizard.id,
        'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })

    # Return download action
    return {
        'type': 'ir.actions.act_url',
        'url': f'/web/content/{attachment.id}?download=true',
        'target': 'self',
    }


def action_export_breakdown_to_excel(balance_line):
    """Export breakdown data to Excel with separate sheets for each breakdown type"""
    from odoo.exceptions import UserError

    # Get the record ID first, then use browse with sudo to avoid validation
    record_id = balance_line.id
    if not record_id:
        raise UserError("Cannot export: Invalid record.")

    # Determine model name and filename prefix based on the balance line type
    model_name = balance_line._name
    filename_prefix_map = {
        'kojto.finance.balance.company.line': 'Company',
        'kojto.finance.balance.maincode.line': 'Maincode',
        'kojto.finance.balance.code.line': 'Code',
        'kojto.finance.balance.subcode.line': 'Subcode',
    }

    if model_name not in filename_prefix_map:
        raise UserError(f"Cannot export: Unsupported model type {model_name}.")

    filename_prefix = filename_prefix_map[model_name]

    # Use browse with sudo to read the record without triggering validation
    record = balance_line.env[model_name].sudo().browse(record_id)
    if not record.exists():
        raise UserError("Cannot export: Record not found.")

    # Get wizard_id - try from multiple sources
    wizard_id = None
    wizard = None

    # First, try to get wizard_id from the record
    try:
        if record.wizard_id:
            wizard_id = record.wizard_id.id
            wizard = record.wizard_id
    except Exception:
        pass

    # If wizard_id is not available, try to get it from context
    if not wizard_id:
        context = balance_line.env.context
        # Try active_id if it's a wizard
        if context.get('active_model') == 'kojto.finance.balance.wizard':
            wizard_id = context.get('active_id')
            if wizard_id:
                wizard = balance_line.env['kojto.finance.balance.wizard'].sudo().browse(wizard_id)
                if not wizard.exists():
                    wizard = None
                    wizard_id = None
            else:
                # active_id is False, but we're in wizard context - try default_wizard_id
                default_wizard_id = context.get('default_wizard_id')
                if default_wizard_id:
                    wizard = balance_line.env['kojto.finance.balance.wizard'].sudo().browse(default_wizard_id)
                    if wizard.exists():
                        wizard_id = default_wizard_id

    # If still not found, try to find the wizard by searching for records with this balance line
    if not wizard_id and record_id:
        for field_name in ['company_balance_line_ids', 'maincode_balance_line_ids',
                         'code_balance_line_ids', 'subcode_balance_line_ids']:
            found_wizard = balance_line.env['kojto.finance.balance.wizard'].sudo().search([
                (field_name, 'in', [record_id])
            ], limit=1)
            if found_wizard:
                wizard_id = found_wizard.id
                wizard = found_wizard
                break

        # Last resort: try to find wizard by matching date range if we have dates from the record
        if not wizard_id:
            try:
                record_date_from = record.sudo().date_from
                record_date_to = record.sudo().date_to
                if record_date_from and record_date_to:
                    found_wizard = balance_line.env['kojto.finance.balance.wizard'].sudo().search([
                        ('date_from', '=', record_date_from),
                        ('date_to', '=', record_date_to),
                        ('create_uid', '=', balance_line.env.uid)
                    ], order='create_date desc', limit=1)
                    if found_wizard:
                        wizard_id = found_wizard.id
                        wizard = found_wizard
            except Exception:
                pass

    # Get date_from and date_to - prioritize context (from form) since wizard might not be saved
    date_from = None
    date_to = None

    # First try to get dates from context (wizard form values, even if wizard isn't saved)
    context = balance_line.env.context
    context_date_from = context.get('wizard_date_from') or context.get('default_date_from')
    context_date_to = context.get('wizard_date_to') or context.get('default_date_to')
    if context_date_from and context_date_to:
        date_from = context_date_from
        date_to = context_date_to

    # If dates are not available from context, try to get them from wizard (if saved)
    if not date_from or not date_to:
        if wizard and wizard.exists():
            date_from = wizard.date_from
            date_to = wizard.date_to

    # If dates are still not available, try to get them from the record
    if not date_from or not date_to:
        try:
            record_date_from = record.sudo().date_from
            record_date_to = record.sudo().date_to
            if record_date_from and record_date_to:
                date_from = record_date_from
                date_to = record_date_to
        except Exception:
            pass

    if not date_from or not date_to:
        raise UserError("Cannot export: Date range is required.")

    # Import get_breakdown_records
    from .kojto_finance_balance_wizard_calculations import get_breakdown_records
    from datetime import datetime, date

    # Normalize dates - convert strings to date objects if needed
    if isinstance(date_from, str):
        try:
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
        except ValueError:
            # Try alternative format
            try:
                date_from = datetime.strptime(date_from, '%Y-%m-%d %H:%M:%S').date()
            except ValueError:
                raise UserError(f"Invalid date format for date_from: {date_from}")
    elif not isinstance(date_from, date):
        raise UserError(f"Invalid date type for date_from: {type(date_from)}")

    if isinstance(date_to, str):
        try:
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
        except ValueError:
            # Try alternative format
            try:
                date_to = datetime.strptime(date_to, '%Y-%m-%d %H:%M:%S').date()
            except ValueError:
                raise UserError(f"Invalid date format for date_to: {date_to}")
    elif not isinstance(date_to, date):
        raise UserError(f"Invalid date type for date_to: {type(date_to)}")

    # Convert dates to datetime for proper comparison
    datetime_from = datetime.combine(date_from, datetime.min.time())
    datetime_to = datetime.combine(date_to, datetime.max.time())

    # Determine filter parameters based on model type
    subcode_ids = None
    code_ids = None
    maincode_ids = None

    if model_name == 'kojto.finance.balance.subcode.line':
        if record.sudo().subcode_id:
            subcode_ids = [record.sudo().subcode_id.id]
    elif model_name == 'kojto.finance.balance.code.line':
        if record.sudo().code_id:
            code_ids = [record.sudo().code_id.id]
    elif model_name == 'kojto.finance.balance.maincode.line':
        if record.sudo().maincode_id:
            maincode_ids = [record.sudo().maincode_id.id]
    # For company balance line, all filters remain None

    # Get breakdown records using get_breakdown_records
    breakdown = get_breakdown_records(
        record.env, date_from, date_to, datetime_from, datetime_to,
        subcode_ids=subcode_ids, code_ids=code_ids, maincode_ids=maincode_ids
    )

    # Extract record IDs from the recordsets
    outgoing_ids = breakdown['outgoing_pre_vat_total'].ids if breakdown['outgoing_pre_vat_total'] else []
    incoming_ids = breakdown['incoming_pre_vat_total'].ids if breakdown['incoming_pre_vat_total'] else []
    revenue_ids = breakdown['invoiceless_revenue'].ids if breakdown['invoiceless_revenue'] else []
    expenses_ids = breakdown['invoiceless_expenses'].ids if breakdown['invoiceless_expenses'] else []
    tt_ids = breakdown['hr_time_tracking'].ids if breakdown['hr_time_tracking'] else []
    assets_ids = breakdown['assets_works'].ids if breakdown['assets_works'] else []

    # Create Excel file in memory
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})

    # Define formats
    header_format = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'align': 'center'})
    text_format = workbook.add_format({'text_wrap': True})
    currency_format = workbook.add_format({'num_format': '#,##0.00'})

    # Helper function to write records to worksheet
    def write_invoice_contents_sheet(worksheet, record_ids, headers):
        """Write invoice contents records to worksheet"""
        if not record_ids:
            worksheet.write(0, 0, 'No data available')
            return

        # Write header row
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)

        # Read records
        records = record.env['kojto.finance.invoice.contents'].sudo().browse(record_ids)
        for row_idx, rec in enumerate(records, start=1):
            worksheet.write(row_idx, 0, rec.name or '', text_format)
            worksheet.write(row_idx, 1, rec.pre_vat_total or 0.0, currency_format)
            worksheet.write(row_idx, 2, rec.invoice_id.name if rec.invoice_id else '', text_format)
            worksheet.write(row_idx, 3, rec.subcode_id.subcode if rec.subcode_id else '', text_format)

        # Auto-adjust column widths
        worksheet.set_column(0, 0, 40)  # Name
        worksheet.set_column(1, 1, 18)  # Pre-VAT Total
        worksheet.set_column(2, 2, 20)  # Invoice
        worksheet.set_column(3, 3, 15)  # Subcode

    def write_cash_allocation_sheet(worksheet, record_ids, headers):
        """Write cash allocation records to worksheet"""
        if not record_ids:
            worksheet.write(0, 0, 'No data available')
            return

        # Write header row
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)

        # Read records
        records = record.env['kojto.finance.cashflow.allocation'].sudo().browse(record_ids)
        for row_idx, rec in enumerate(records, start=1):
            worksheet.write(row_idx, 0, rec.description or '', text_format)
            worksheet.write(row_idx, 1, rec.amount or 0.0, currency_format)
            worksheet.write(row_idx, 2, rec.transaction_id.name if rec.transaction_id else '', text_format)
            worksheet.write(row_idx, 3, rec.subcode_id.subcode if rec.subcode_id else '', text_format)

        # Auto-adjust column widths
        worksheet.set_column(0, 0, 40)  # Description
        worksheet.set_column(1, 1, 18)  # Amount
        worksheet.set_column(2, 2, 20)  # Transaction
        worksheet.set_column(3, 3, 15)  # Subcode

    def write_time_tracking_sheet(worksheet, record_ids, headers):
        """Write time tracking records to worksheet"""
        if not record_ids:
            worksheet.write(0, 0, 'No data available')
            return

        # Write header row
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)

        # Read records
        records = record.env['kojto.hr.time.tracking'].sudo().browse(record_ids)
        for row_idx, rec in enumerate(records, start=1):
            date_start = rec.datetime_start.strftime("%Y-%m-%d %H:%M") if rec.datetime_start else ""
            worksheet.write(row_idx, 0, date_start, text_format)
            worksheet.write(row_idx, 1, rec.total_hours or 0.0, currency_format)
            worksheet.write(row_idx, 2, rec.value_in_EUR or 0.0, currency_format)
            worksheet.write(row_idx, 3, rec.subcode_id.subcode if rec.subcode_id else '', text_format)
            worksheet.write(row_idx, 4, rec.credited_subcode_id.subcode if rec.credited_subcode_id else '', text_format)

        # Auto-adjust column widths
        worksheet.set_column(0, 0, 18)  # Date Start
        worksheet.set_column(1, 1, 15)  # Total Hours
        worksheet.set_column(2, 2, 18)  # Value (EUR)
        worksheet.set_column(3, 3, 15)  # Subcode
        worksheet.set_column(4, 4, 20)  # Credited Subcode

    def write_asset_works_sheet(worksheet, record_ids, headers):
        """Write asset works records to worksheet"""
        if not record_ids:
            worksheet.write(0, 0, 'No data available')
            return

        # Write header row
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)

        # Read records
        records = record.env['kojto.asset.works'].sudo().browse(record_ids)
        for row_idx, rec in enumerate(records, start=1):
            date_start = rec.datetime_start.strftime("%Y-%m-%d %H:%M") if rec.datetime_start else ""
            worksheet.write(row_idx, 0, date_start, text_format)
            worksheet.write(row_idx, 1, rec.quantity or 0.0, currency_format)
            worksheet.write(row_idx, 2, rec.value_in_EUR or 0.0, currency_format)
            worksheet.write(row_idx, 3, rec.subcode_id.subcode if rec.subcode_id else '', text_format)
            worksheet.write(row_idx, 4, rec.credited_subcode_id.subcode if rec.credited_subcode_id else '', text_format)

        # Auto-adjust column widths
        worksheet.set_column(0, 0, 18)  # Date Start
        worksheet.set_column(1, 1, 15)  # Quantity
        worksheet.set_column(2, 2, 18)  # Value (EUR)
        worksheet.set_column(3, 3, 15)  # Subcode
        worksheet.set_column(4, 4, 20)  # Credited Subcode

    # Sheet 1: Outgoing Pre-VAT Total
    worksheet = workbook.add_worksheet('Outgoing Pre-VAT Total')
    write_invoice_contents_sheet(worksheet, outgoing_ids, ['Name', 'Pre-VAT Total', 'Invoice', 'Subcode'])

    # Sheet 2: Incoming Pre-VAT Total
    worksheet = workbook.add_worksheet('Incoming Pre-VAT Total')
    write_invoice_contents_sheet(worksheet, incoming_ids, ['Name', 'Pre-VAT Total', 'Invoice', 'Subcode'])

    # Sheet 3: Invoiceless Revenue
    worksheet = workbook.add_worksheet('Invoiceless Revenue')
    write_cash_allocation_sheet(worksheet, revenue_ids, ['Description', 'Amount', 'Transaction', 'Subcode'])

    # Sheet 4: Invoiceless Expenses
    worksheet = workbook.add_worksheet('Invoiceless Expenses')
    write_cash_allocation_sheet(worksheet, expenses_ids, ['Description', 'Amount', 'Transaction', 'Subcode'])

    # Sheet 5: Time Tracking Total
    worksheet = workbook.add_worksheet('Time Tracking Total')
    write_time_tracking_sheet(worksheet, tt_ids, ['Date Start', 'Total Hours', 'Value (EUR)', 'Subcode', 'Credited Subcode'])

    # Sheet 6: Assets Total
    worksheet = workbook.add_worksheet('Assets Total')
    write_asset_works_sheet(worksheet, assets_ids, ['Date Start', 'Quantity', 'Value (EUR)', 'Subcode', 'Credited Subcode'])

    workbook.close()
    output.seek(0)

    # Create attachment
    file_data = output.read()
    file_data_base64 = base64.b64encode(file_data).decode('utf-8')

    # Handle date formatting - read() returns date strings
    if date_from:
        if isinstance(date_from, str):
            date_from_str = date_from
        else:
            date_from_str = date_from.strftime('%Y-%m-%d')
    else:
        date_from_str = ''

    if date_to:
        if isinstance(date_to, str):
            date_to_str = date_to
        else:
            date_to_str = date_to.strftime('%Y-%m-%d')
    else:
        date_to_str = ''

    filename = f"{filename_prefix}_Balance_Breakdown_{date_from_str}_{date_to_str}.xlsx"

    # Create standalone attachment (not linked to any model) to avoid validation issues
    # This allows the export to work even if wizard_id is not set
    attachment_vals = {
        'name': filename,
        'type': 'binary',
        'datas': file_data_base64,
        'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        # Don't set res_model or res_id - create as standalone attachment
    }

    attachment = record.env['ir.attachment'].sudo().create(attachment_vals)

    # Return download action
    return {
        'type': 'ir.actions.act_url',
        'url': f'/web/content/{attachment.id}?download=true',
        'target': 'self',
    }

