# -*- coding: utf-8 -*-
"""
Kojto Warehouses Balance Wizard - Actions

Contains action methods for the wizard (export functionality).
"""

from odoo.exceptions import UserError
import io
import base64
import xlsxwriter


def action_export_balance_to_excel(wizard):
    """Export all balance data to Excel with separate sheets"""
    wizard.ensure_one()

    if not wizard.date_from or not wizard.date_to:
        raise UserError("No data to export. Please set date range first.")

    # Ensure transaction_ids are computed and relation table is populated
    wizard._compute_transaction_ids()

    # Recalculate balance lines to ensure values are correct
    wizard._create_balance_lines()

    if not wizard.warehouse_balance_line_ids:
        raise UserError("No data to export. Please compute the balance first.")

    # Create Excel file in memory
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})

    # Define formats
    bold_format = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3'})
    currency_format = workbook.add_format({'num_format': '#,##0.00'})
    header_format = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'align': 'center'})
    date_format = workbook.add_format({'num_format': 'yyyy-mm-dd'})

    currency = wizard.currency_id or wizard.env.ref('base.EUR')

    # Sheet 1: Warehouse Balance Summary
    worksheet = workbook.add_worksheet('Warehouse Balance')

    # Write headers
    headers = ['Warehouse', 'Beginning Value (EUR)', 'Ending Value (EUR)', 'Change (EUR)']
    for col, header in enumerate(headers):
        worksheet.write(0, col, header, header_format)

    # Write data
    for row, line in enumerate(wizard.warehouse_balance_line_ids, start=1):
        worksheet.write(row, 0, line.warehouse_name or '')
        worksheet.write(row, 1, line.beginning_value or 0.0, currency_format)
        worksheet.write(row, 2, line.ending_value or 0.0, currency_format)
        change = (line.ending_value or 0.0) - (line.beginning_value or 0.0)
        worksheet.write(row, 3, change, currency_format)

    # Write totals row
    if wizard.warehouse_balance_line_ids:
        total_row = len(wizard.warehouse_balance_line_ids) + 1
        worksheet.write(total_row, 0, 'TOTAL', bold_format)
        worksheet.write(total_row, 1, wizard.beginning_value or 0.0, currency_format)
        worksheet.write(total_row, 2, wizard.ending_value or 0.0, currency_format)
        total_change = (wizard.ending_value or 0.0) - (wizard.beginning_value or 0.0)
        worksheet.write(total_row, 3, total_change, currency_format)

    # Set column widths
    worksheet.set_column(0, 0, 30)  # Warehouse
    worksheet.set_column(1, 3, 18)  # Financial columns

    # Sheet 2: Transactions
    # Use cached transaction data (no need to create thousands of records)
    import json
    transaction_lines_data = []
    if wizard.transaction_lines_cache:
        try:
            transaction_lines_data = json.loads(wizard.transaction_lines_cache)
        except:
            pass

    if transaction_lines_data:
        worksheet = workbook.add_worksheet('Transactions')

        # Write headers
        headers = [
            'Date', 'Warehouse', 'Transaction', 'Item', 'Batch',
            'Type', 'Quantity', 'Unit Price (EUR)', 'Transaction Value (EUR)'
        ]
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)

        # Write data directly from cached dictionary data
        for row, line_data in enumerate(transaction_lines_data, start=1):
            col = 0
            worksheet.write(row, col, line_data.get('date_issue') or '', date_format)
            col += 1
            worksheet.write(row, col, line_data.get('warehouse_name') or '')
            col += 1
            worksheet.write(row, col, line_data.get('transaction_name') or '')
            col += 1
            worksheet.write(row, col, line_data.get('item_name') or '')
            col += 1
            worksheet.write(row, col, line_data.get('batch_name') or '')
            col += 1

            # Transaction type
            type_label = 'To Store' if line_data.get('transaction_type') == 'to_store' else 'From Store'
            worksheet.write(row, col, type_label)
            col += 1

            worksheet.write(row, col, line_data.get('quantity') or 0.0, currency_format)
            col += 1
            worksheet.write(row, col, line_data.get('unit_price_eur') or 0.0, currency_format)
            col += 1
            worksheet.write(row, col, line_data.get('transaction_value_eur') or 0.0, currency_format)

        # Write totals row
        if transaction_lines_data:
            total_row = len(transaction_lines_data) + 1
            worksheet.write(total_row, 7, 'TOTAL', bold_format)
            worksheet.write(total_row, 8, wizard.total_transactions_value or 0.0, currency_format)

        # Set column widths
        worksheet.set_column(0, 0, 12)  # Date
        worksheet.set_column(1, 1, 25)  # Warehouse
        worksheet.set_column(2, 4, 20)  # Transaction, Item, Batch
        worksheet.set_column(5, 5, 12)  # Type
        worksheet.set_column(6, 8, 18)  # Financial columns

    # Sheet 3: Identifiers (grouped by identifier_id)
    if wizard.identifier_line_ids:
        worksheet = workbook.add_worksheet('Identifiers')

        # Write headers
        headers = [
            'Identifier ID', 'Identifier Name', 'Identifier Type', 'Transaction Count', 'Total Quantity', 'Unit',
            'To Store Quantity', 'From Store Quantity',
            'Total Value (EUR)', 'To Store Value (EUR)', 'From Store Value (EUR)'
        ]
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)

        # Write data
        total_value_eur = 0.0
        total_to_store_value_eur = 0.0
        total_from_store_value_eur = 0.0
        for row, line in enumerate(wizard.identifier_line_ids, start=1):
            col = 0
            worksheet.write(row, col, line.identifier_id or '')
            col += 1
            worksheet.write(row, col, line.identifier_name or '')
            col += 1
            worksheet.write(row, col, dict(line._fields['identifier_type'].selection).get(line.identifier_type, '') if line.identifier_type else '')
            col += 1
            worksheet.write(row, col, line.transaction_count or 0)
            col += 1
            worksheet.write(row, col, line.total_quantity or 0.0, currency_format)
            col += 1
            worksheet.write(row, col, line.unit_id.name if line.unit_id else '')
            col += 1
            worksheet.write(row, col, line.total_to_store_quantity or 0.0, currency_format)
            col += 1
            worksheet.write(row, col, line.total_from_store_quantity or 0.0, currency_format)
            col += 1
            worksheet.write(row, col, line.total_value_eur or 0.0, currency_format)
            col += 1
            worksheet.write(row, col, line.total_to_store_value_eur or 0.0, currency_format)
            col += 1
            worksheet.write(row, col, line.total_from_store_value_eur or 0.0, currency_format)

            total_value_eur += line.total_value_eur or 0.0
            total_to_store_value_eur += line.total_to_store_value_eur or 0.0
            total_from_store_value_eur += line.total_from_store_value_eur or 0.0

        # Write totals row
        if wizard.identifier_line_ids:
            total_row = len(wizard.identifier_line_ids) + 1
            worksheet.write(total_row, 0, 'TOTAL', bold_format)
            worksheet.write(total_row, 8, total_value_eur, currency_format)
            worksheet.write(total_row, 9, total_to_store_value_eur, currency_format)
            worksheet.write(total_row, 10, total_from_store_value_eur, currency_format)

        # Set column widths
        worksheet.set_column(0, 0, 15)  # Identifier ID
        worksheet.set_column(1, 1, 30)  # Identifier Name
        worksheet.set_column(2, 2, 15)  # Identifier Type
        worksheet.set_column(3, 3, 15)  # Transaction Count
        worksheet.set_column(4, 4, 18)  # Total Quantity
        worksheet.set_column(5, 5, 12)  # Unit
        worksheet.set_column(6, 7, 18)  # To/From Store Quantities
        worksheet.set_column(8, 10, 20)  # Financial columns

    # Sheet 4: Subcodes (grouped by subcode_id)
    if wizard.subcode_line_ids:
        worksheet = workbook.add_worksheet('Subcodes')

        # Write headers
        headers = [
            'Subcode', 'Subcode Description', 'Transaction Count',
            'Total Value (EUR)', 'To Store Value (EUR)', 'From Store Value (EUR)'
        ]
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)

        # Write data
        total_value_eur = 0.0
        total_to_store_value_eur = 0.0
        total_from_store_value_eur = 0.0
        for row, line in enumerate(wizard.subcode_line_ids, start=1):
            col = 0
            worksheet.write(row, col, line.subcode_id.name if line.subcode_id else '')
            col += 1
            worksheet.write(row, col, line.subcode_description or '')
            col += 1
            worksheet.write(row, col, line.transaction_count or 0)
            col += 1
            worksheet.write(row, col, line.total_value_eur or 0.0, currency_format)
            col += 1
            worksheet.write(row, col, line.total_to_store_value_eur or 0.0, currency_format)
            col += 1
            worksheet.write(row, col, line.total_from_store_value_eur or 0.0, currency_format)

            total_value_eur += line.total_value_eur or 0.0
            total_to_store_value_eur += line.total_to_store_value_eur or 0.0
            total_from_store_value_eur += line.total_from_store_value_eur or 0.0

        # Write totals row
        if wizard.subcode_line_ids:
            total_row = len(wizard.subcode_line_ids) + 1
            worksheet.write(total_row, 0, 'TOTAL', bold_format)
            worksheet.write(total_row, 3, total_value_eur, currency_format)
            worksheet.write(total_row, 4, total_to_store_value_eur, currency_format)
            worksheet.write(total_row, 5, total_from_store_value_eur, currency_format)

        # Set column widths
        worksheet.set_column(0, 0, 20)  # Subcode
        worksheet.set_column(1, 1, 30)  # Subcode Description
        worksheet.set_column(2, 2, 15)  # Transaction Count
        worksheet.set_column(3, 5, 20)  # Financial columns

    # Sheet 5: Subcodes @ Identifiers (grouped by subcode_id and identifier_id)
    if wizard.subcode_identifier_line_ids:
        worksheet = workbook.add_worksheet('Subcodes @ Identifiers')

        # Write headers
        headers = [
            'Subcode', 'Subcode Description', 'Identifier ID', 'Identifier Name', 'Identifier Type', 'Transaction Count', 'Total Quantity', 'Unit',
            'To Store Quantity', 'From Store Quantity',
            'Total Value (EUR)', 'To Store Value (EUR)', 'From Store Value (EUR)'
        ]
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)

        # Write data
        total_value_eur = 0.0
        total_to_store_value_eur = 0.0
        total_from_store_value_eur = 0.0
        for row, line in enumerate(wizard.subcode_identifier_line_ids, start=1):
            col = 0
            worksheet.write(row, col, line.subcode_id.name if line.subcode_id else '')
            col += 1
            worksheet.write(row, col, line.subcode_description or '')
            col += 1
            worksheet.write(row, col, line.identifier_id or '')
            col += 1
            worksheet.write(row, col, line.identifier_name or '')
            col += 1
            worksheet.write(row, col, dict(line._fields['identifier_type'].selection).get(line.identifier_type, '') if line.identifier_type else '')
            col += 1
            worksheet.write(row, col, line.transaction_count or 0)
            col += 1
            worksheet.write(row, col, line.total_quantity or 0.0, currency_format)
            col += 1
            worksheet.write(row, col, line.unit_id.name if line.unit_id else '')
            col += 1
            worksheet.write(row, col, line.total_to_store_quantity or 0.0, currency_format)
            col += 1
            worksheet.write(row, col, line.total_from_store_quantity or 0.0, currency_format)
            col += 1
            worksheet.write(row, col, line.total_value_eur or 0.0, currency_format)
            col += 1
            worksheet.write(row, col, line.total_to_store_value_eur or 0.0, currency_format)
            col += 1
            worksheet.write(row, col, line.total_from_store_value_eur or 0.0, currency_format)

            total_value_eur += line.total_value_eur or 0.0
            total_to_store_value_eur += line.total_to_store_value_eur or 0.0
            total_from_store_value_eur += line.total_from_store_value_eur or 0.0

        # Write totals row
        if wizard.subcode_identifier_line_ids:
            total_row = len(wizard.subcode_identifier_line_ids) + 1
            worksheet.write(total_row, 0, 'TOTAL', bold_format)
            worksheet.write(total_row, 10, total_value_eur, currency_format)
            worksheet.write(total_row, 11, total_to_store_value_eur, currency_format)
            worksheet.write(total_row, 12, total_from_store_value_eur, currency_format)

        # Set column widths
        worksheet.set_column(0, 0, 20)  # Subcode
        worksheet.set_column(1, 1, 30)  # Subcode Description
        worksheet.set_column(2, 2, 15)  # Identifier ID
        worksheet.set_column(3, 3, 30)  # Identifier Name
        worksheet.set_column(4, 4, 15)  # Identifier Type
        worksheet.set_column(5, 5, 15)  # Transaction Count
        worksheet.set_column(6, 6, 18)  # Total Quantity
        worksheet.set_column(7, 7, 12)  # Unit
        worksheet.set_column(8, 9, 18)  # To/From Store Quantities
        worksheet.set_column(10, 12, 20)  # Financial columns

    workbook.close()
    output.seek(0)

    # Get file data
    file_data = output.read()
    file_data_base64 = base64.b64encode(file_data).decode('utf-8')
    filename = f"Warehouse_Balance_{wizard.date_from}_{wizard.date_to}.xlsx"

    # Create attachment as standalone (not linked to transient wizard model)
    # Using sudo() and not setting res_model/res_id to avoid domain filter issues
    attachment = wizard.env['ir.attachment'].sudo().create({
        'name': filename,
        'datas': file_data_base64,
        'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })

    # Return download action - use ir.actions.act_url with attachment ID
    return {
        'type': 'ir.actions.act_url',
        'url': f'/web/content/{attachment.id}?download=true',
        'target': 'self',
    }


def action_export_warehouse_transactions_to_excel(balance_line):
    """Export transactions for a specific warehouse to Excel"""
    balance_line.ensure_one()

    if not balance_line.wizard_id.date_from or not balance_line.wizard_id.date_to:
        raise UserError("Date range is not set.")

    # Build search domain - if warehouse_id is False, show all warehouses
    if balance_line.warehouse_id:
        # Filter by specific warehouse
        domain = [
            ('batch_id.store_id', '=', balance_line.warehouse_id.id),
            ('date_issue', '>=', balance_line.wizard_id.date_from),
            ('date_issue', '<=', balance_line.wizard_id.date_to),
        ]
    else:
        # Show all warehouses (All Warehouses line)
        domain = [
            ('date_issue', '>=', balance_line.wizard_id.date_from),
            ('date_issue', '<=', balance_line.wizard_id.date_to),
        ]

    # Get transactions in the date range
    transactions = balance_line.env['kojto.warehouses.transactions'].search(domain, order='date_issue desc')

    if not transactions:
        warehouse_name = balance_line.warehouse_name or 'All Warehouses'
        raise UserError(f"No transactions found for {warehouse_name} in the selected date range.")

    # Create Excel file in memory
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})

    # Define formats
    bold_format = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3'})
    currency_format = workbook.add_format({'num_format': '#,##0.00'})
    header_format = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'align': 'center'})
    date_format = workbook.add_format({'num_format': 'yyyy-mm-dd'})

    worksheet = workbook.add_worksheet(f'Transactions - {balance_line.warehouse_name}')

    # Write headers
    headers = [
        'Date', 'Transaction', 'Item', 'Batch', 'Type',
        'Quantity', 'Unit Price (EUR)', 'Transaction Value (EUR)'
    ]
    for col, header in enumerate(headers):
        worksheet.write(0, col, header, header_format)

    # Write data
    total_value = 0.0
    for row, transaction in enumerate(transactions, start=1):
        col = 0
        worksheet.write(row, col, transaction.date_issue or '', date_format)
        col += 1
        worksheet.write(row, col, transaction.name or '')
        col += 1
        worksheet.write(row, col, transaction.item_id.name if transaction.item_id else '')
        col += 1
        worksheet.write(row, col, transaction.batch_id.name if transaction.batch_id else '')
        col += 1

        # Transaction type
        type_label = 'To Store' if transaction.to_from_store == 'to_store' else 'From Store'
        worksheet.write(row, col, type_label)
        col += 1

        worksheet.write(row, col, transaction.transaction_quantity or 0.0, currency_format)
        col += 1

        # Use pre-computed value if available, otherwise calculate
        if transaction.transaction_value_pre_vat_eur and transaction.transaction_quantity > 0:
            unit_price_eur = abs(transaction.transaction_value_pre_vat_eur / transaction.transaction_quantity)
            transaction_value_eur = transaction.transaction_value_pre_vat_eur
        else:
            # Fallback calculation
            if transaction.batch_id and transaction.batch_id.unit_price_converted:
                # Get exchange rate for transaction date
                from .kojto_warehouses_balance_wizard_calculations import get_exchange_rate_to_eur
                exchange_rate = get_exchange_rate_to_eur(balance_line.env, transaction.date_issue)
                unit_price_eur = transaction.batch_id.unit_price_converted * exchange_rate
                # Calculate value in EUR directly
                transaction_value_eur = transaction.transaction_quantity * transaction.batch_id.unit_price_converted * exchange_rate
                if transaction.to_from_store == 'from_store':
                    transaction_value_eur = -transaction_value_eur
            else:
                unit_price_eur = 0.0
                transaction_value_eur = 0.0

        worksheet.write(row, col, unit_price_eur, currency_format)
        col += 1
        worksheet.write(row, col, transaction_value_eur, currency_format)

        total_value += transaction_value_eur

    # Write totals row
    if transactions:
        total_row = len(transactions) + 1
        worksheet.write(total_row, 6, 'TOTAL', bold_format)
        worksheet.write(total_row, 7, total_value, currency_format)

    # Set column widths
    worksheet.set_column(0, 0, 12)  # Date
    worksheet.set_column(1, 4, 20)  # Transaction, Item, Batch, Type
    worksheet.set_column(5, 7, 18)  # Financial columns

    workbook.close()
    output.seek(0)

    # Get file data
    file_data = output.read()
    file_data_base64 = base64.b64encode(file_data).decode('utf-8')
    filename = f"Transactions_{balance_line.warehouse_name}_{balance_line.wizard_id.date_from}_{balance_line.wizard_id.date_to}.xlsx"

    # Create attachment
    attachment = balance_line.env['ir.attachment'].sudo().create({
        'name': filename,
        'datas': file_data_base64,
        'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })

    # Return download action
    return {
        'type': 'ir.actions.act_url',
        'url': f'/web/content/{attachment.id}?download=true',
        'target': 'self',
    }


def action_export_identifier_transactions_to_excel(identifier_line):
    """Export transactions for a specific identifier to Excel"""
    identifier_line.ensure_one()

    if not identifier_line.identifier_id:
        raise UserError("No identifier ID selected.")

    if not identifier_line.wizard_id.date_from or not identifier_line.wizard_id.date_to:
        raise UserError("Date range is not set.")

    # Get transactions for this identifier in the date range
    transactions = identifier_line.transaction_ids.sorted('date_issue desc')

    if not transactions:
        raise UserError(f"No transactions found for Identifier {identifier_line.identifier_id} in the selected date range.")

    # Create Excel file in memory
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})

    # Define formats
    bold_format = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3'})
    currency_format = workbook.add_format({'num_format': '#,##0.00'})
    header_format = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'align': 'center'})
    date_format = workbook.add_format({'num_format': 'yyyy-mm-dd'})

    worksheet = workbook.add_worksheet(f'Transactions - Identifier {identifier_line.identifier_id}')

    # Write headers
    headers = [
        'Date', 'Transaction', 'Identifier ID', 'Identifier Name', 'Identifier Type', 'Warehouse', 'Item', 'Batch', 'Type',
        'Quantity', 'Unit Price (EUR)', 'Transaction Value (EUR)'
    ]
    for col, header in enumerate(headers):
        worksheet.write(0, col, header, header_format)

    # Write data
    total_value_eur = 0.0
    for row, transaction in enumerate(transactions, start=1):
        col = 0
        worksheet.write(row, col, transaction.date_issue or '', date_format)
        col += 1
        worksheet.write(row, col, transaction.name or '')
        col += 1
        worksheet.write(row, col, identifier_line.identifier_id or '')
        col += 1
        worksheet.write(row, col, identifier_line.identifier_name or '')
        col += 1
        identifier_type_label = dict(identifier_line._fields['identifier_type'].selection).get(identifier_line.identifier_type, '') if identifier_line.identifier_type else ''
        worksheet.write(row, col, identifier_type_label)
        col += 1
        worksheet.write(row, col, transaction.batch_id.store_id.name if transaction.batch_id and transaction.batch_id.store_id else '')
        col += 1
        worksheet.write(row, col, transaction.item_id.name if transaction.item_id else '')
        col += 1
        worksheet.write(row, col, transaction.batch_id.name if transaction.batch_id else '')
        col += 1

        # Transaction type
        type_label = 'To Store' if transaction.to_from_store == 'to_store' else 'From Store'
        worksheet.write(row, col, type_label)
        col += 1

        worksheet.write(row, col, transaction.transaction_quantity or 0.0, currency_format)
        col += 1

        # Calculate unit price and value
        unit_price_eur = 0.0
        transaction_value_eur = transaction.transaction_value_pre_vat_eur or 0.0
        if transaction.transaction_quantity > 0:
            unit_price_eur = abs(transaction_value_eur / transaction.transaction_quantity)

        worksheet.write(row, col, unit_price_eur, currency_format)
        col += 1
        worksheet.write(row, col, transaction_value_eur, currency_format)

        total_value_eur += transaction_value_eur

    # Write totals row
    if transactions:
        total_row = len(transactions) + 1
        worksheet.write(total_row, 10, 'TOTAL', bold_format)
        worksheet.write(total_row, 11, total_value_eur, currency_format)

    # Set column widths
    worksheet.set_column(0, 0, 12)  # Date
    worksheet.set_column(1, 1, 20)  # Transaction
    worksheet.set_column(2, 2, 15)  # Identifier ID
    worksheet.set_column(3, 3, 30)  # Identifier Name
    worksheet.set_column(4, 4, 15)  # Identifier Type
    worksheet.set_column(5, 8, 20)  # Warehouse, Item, Batch, Type
    worksheet.set_column(9, 11, 18)  # Financial columns

    workbook.close()
    output.seek(0)

    # Get file data
    file_data = output.read()
    file_data_base64 = base64.b64encode(file_data).decode('utf-8')
    filename = f"Transactions_Identifier_{identifier_line.identifier_id}_{identifier_line.wizard_id.date_from}_{identifier_line.wizard_id.date_to}.xlsx"

    # Create attachment
    attachment = identifier_line.env['ir.attachment'].sudo().create({
        'name': filename,
        'datas': file_data_base64,
        'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })

    # Return download action
    return {
        'type': 'ir.actions.act_url',
        'url': f'/web/content/{attachment.id}?download=true',
        'target': 'self',
    }


def action_export_subcode_transactions_to_excel(subcode_line):
    """Export transactions for a specific subcode to Excel"""
    subcode_line.ensure_one()

    if not subcode_line.subcode_id:
        raise UserError("No subcode selected.")

    if not subcode_line.wizard_id.date_from or not subcode_line.wizard_id.date_to:
        raise UserError("Date range is not set.")

    # Get transactions for this subcode in the date range
    transactions = subcode_line.transaction_ids.sorted('date_issue desc')

    if not transactions:
        subcode_name = subcode_line.subcode_id.name if subcode_line.subcode_id else 'N/A'
        raise UserError(f"No transactions found for Subcode {subcode_name} in the selected date range.")

    # Create Excel file in memory
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})

    # Define formats
    bold_format = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3'})
    currency_format = workbook.add_format({'num_format': '#,##0.00'})
    header_format = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'align': 'center'})
    date_format = workbook.add_format({'num_format': 'yyyy-mm-dd'})

    subcode_name = subcode_line.subcode_id.name if subcode_line.subcode_id else 'N/A'
    worksheet = workbook.add_worksheet(f'Transactions - Subcode {subcode_name}')

    # Write headers
    headers = [
        'Date', 'Transaction', 'Subcode', 'Subcode Description', 'Warehouse', 'Item', 'Batch', 'Type',
        'Quantity', 'Unit Price (EUR)', 'Transaction Value (EUR)'
    ]
    for col, header in enumerate(headers):
        worksheet.write(0, col, header, header_format)

    # Write data
    total_value_eur = 0.0
    for row, transaction in enumerate(transactions, start=1):
        col = 0
        worksheet.write(row, col, transaction.date_issue or '', date_format)
        col += 1
        worksheet.write(row, col, transaction.name or '')
        col += 1
        worksheet.write(row, col, transaction.subcode_id.name if transaction.subcode_id else '')
        col += 1
        worksheet.write(row, col, transaction.subcode_id.description if transaction.subcode_id else '')
        col += 1
        worksheet.write(row, col, transaction.batch_id.store_id.name if transaction.batch_id and transaction.batch_id.store_id else '')
        col += 1
        worksheet.write(row, col, transaction.item_id.name if transaction.item_id else '')
        col += 1
        worksheet.write(row, col, transaction.batch_id.name if transaction.batch_id else '')
        col += 1

        # Transaction type
        type_label = 'To Store' if transaction.to_from_store == 'to_store' else 'From Store'
        worksheet.write(row, col, type_label)
        col += 1

        worksheet.write(row, col, transaction.transaction_quantity or 0.0, currency_format)
        col += 1

        # Calculate unit price and value
        unit_price_eur = 0.0
        transaction_value_eur = transaction.transaction_value_pre_vat_eur or 0.0
        if transaction.transaction_quantity > 0:
            unit_price_eur = abs(transaction_value_eur / transaction.transaction_quantity)

        worksheet.write(row, col, unit_price_eur, currency_format)
        col += 1
        worksheet.write(row, col, transaction_value_eur, currency_format)

        total_value_eur += transaction_value_eur

    # Write totals row
    if transactions:
        total_row = len(transactions) + 1
        worksheet.write(total_row, 9, 'TOTAL', bold_format)
        worksheet.write(total_row, 10, total_value_eur, currency_format)

    # Set column widths
    worksheet.set_column(0, 0, 12)  # Date
    worksheet.set_column(1, 1, 20)  # Transaction
    worksheet.set_column(2, 3, 20)  # Subcode, Description
    worksheet.set_column(4, 7, 20)  # Warehouse, Item, Batch, Type
    worksheet.set_column(8, 10, 18)  # Financial columns

    workbook.close()
    output.seek(0)

    # Get file data
    file_data = output.read()
    file_data_base64 = base64.b64encode(file_data).decode('utf-8')
    subcode_name = subcode_line.subcode_id.name if subcode_line.subcode_id else 'N/A'
    filename = f"Transactions_Subcode_{subcode_name}_{subcode_line.wizard_id.date_from}_{subcode_line.wizard_id.date_to}.xlsx"

    # Create attachment
    attachment = subcode_line.env['ir.attachment'].sudo().create({
        'name': filename,
        'datas': file_data_base64,
        'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })

    # Return download action
    return {
        'type': 'ir.actions.act_url',
        'url': f'/web/content/{attachment.id}?download=true',
        'target': 'self',
    }


def action_export_subcode_identifier_transactions_to_excel(subcode_identifier_line):
    """Export transactions for a specific subcode-identifier combination to Excel"""
    subcode_identifier_line.ensure_one()

    if not subcode_identifier_line.identifier_id or not subcode_identifier_line.subcode_id:
        raise UserError("No identifier or subcode selected.")

    if not subcode_identifier_line.wizard_id.date_from or not subcode_identifier_line.wizard_id.date_to:
        raise UserError("Date range is not set.")

    # Get transactions for this subcode-identifier combination in the date range
    transactions = subcode_identifier_line.transaction_ids.sorted('date_issue desc')

    if not transactions:
        subcode_name = subcode_identifier_line.subcode_id.name if subcode_identifier_line.subcode_id else 'N/A'
        raise UserError(f"No transactions found for {subcode_name} @ {subcode_identifier_line.identifier_id} in the selected date range.")

    # Create Excel file in memory
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})

    # Define formats
    bold_format = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3'})
    currency_format = workbook.add_format({'num_format': '#,##0.00'})
    header_format = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'align': 'center'})
    date_format = workbook.add_format({'num_format': 'yyyy-mm-dd'})

    subcode_name = subcode_identifier_line.subcode_id.name if subcode_identifier_line.subcode_id else 'N/A'
    worksheet = workbook.add_worksheet(f'Transactions - {subcode_name} @ {subcode_identifier_line.identifier_id}')

    # Write headers
    headers = [
        'Date', 'Transaction', 'Identifier ID', 'Identifier Name', 'Identifier Type', 'Subcode', 'Subcode Description', 'Warehouse', 'Item', 'Batch', 'Type',
        'Quantity', 'Unit Price (EUR)', 'Transaction Value (EUR)'
    ]
    for col, header in enumerate(headers):
        worksheet.write(0, col, header, header_format)

    # Write data
    total_value_eur = 0.0
    for row, transaction in enumerate(transactions, start=1):
        col = 0
        worksheet.write(row, col, transaction.date_issue or '', date_format)
        col += 1
        worksheet.write(row, col, transaction.name or '')
        col += 1
        worksheet.write(row, col, subcode_identifier_line.identifier_id or '')
        col += 1
        worksheet.write(row, col, subcode_identifier_line.identifier_name or '')
        col += 1
        identifier_type_label = dict(subcode_identifier_line._fields['identifier_type'].selection).get(subcode_identifier_line.identifier_type, '') if subcode_identifier_line.identifier_type else ''
        worksheet.write(row, col, identifier_type_label)
        col += 1
        worksheet.write(row, col, transaction.subcode_id.name if transaction.subcode_id else '')
        col += 1
        worksheet.write(row, col, transaction.subcode_id.description if transaction.subcode_id else '')
        col += 1
        worksheet.write(row, col, transaction.batch_id.store_id.name if transaction.batch_id and transaction.batch_id.store_id else '')
        col += 1
        worksheet.write(row, col, transaction.item_id.name if transaction.item_id else '')
        col += 1
        worksheet.write(row, col, transaction.batch_id.name if transaction.batch_id else '')
        col += 1

        # Transaction type
        type_label = 'To Store' if transaction.to_from_store == 'to_store' else 'From Store'
        worksheet.write(row, col, type_label)
        col += 1

        worksheet.write(row, col, transaction.transaction_quantity or 0.0, currency_format)
        col += 1

        # Calculate unit price and value
        unit_price_eur = 0.0
        transaction_value_eur = transaction.transaction_value_pre_vat_eur or 0.0
        if transaction.transaction_quantity > 0:
            unit_price_eur = abs(transaction_value_eur / transaction.transaction_quantity)

        worksheet.write(row, col, unit_price_eur, currency_format)
        col += 1
        worksheet.write(row, col, transaction_value_eur, currency_format)

        total_value_eur += transaction_value_eur

    # Write totals row
    if transactions:
        total_row = len(transactions) + 1
        worksheet.write(total_row, 11, 'TOTAL', bold_format)
        worksheet.write(total_row, 12, total_value_eur, currency_format)

    # Set column widths
    worksheet.set_column(0, 0, 12)  # Date
    worksheet.set_column(1, 1, 20)  # Transaction
    worksheet.set_column(2, 2, 15)  # Identifier ID
    worksheet.set_column(3, 3, 30)  # Identifier Name
    worksheet.set_column(4, 4, 15)  # Identifier Type
    worksheet.set_column(5, 6, 20)  # Subcode, Description
    worksheet.set_column(7, 10, 20)  # Warehouse, Item, Batch, Type
    worksheet.set_column(11, 13, 18)  # Financial columns

    workbook.close()
    output.seek(0)

    # Get file data
    file_data = output.read()
    file_data_base64 = base64.b64encode(file_data).decode('utf-8')
    subcode_name = subcode_identifier_line.subcode_id.name if subcode_identifier_line.subcode_id else 'N/A'
    filename = f"Transactions_{subcode_name}_{subcode_identifier_line.identifier_id}_{subcode_identifier_line.wizard_id.date_from}_{subcode_identifier_line.wizard_id.date_to}.xlsx"

    # Create attachment
    attachment = subcode_identifier_line.env['ir.attachment'].sudo().create({
        'name': filename,
        'datas': file_data_base64,
        'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })

    # Return download action
    return {
        'type': 'ir.actions.act_url',
        'url': f'/web/content/{attachment.id}?download=true',
        'target': 'self',
    }

