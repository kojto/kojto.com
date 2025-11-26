#$ kojto_optimizer/utils/export_2dr_cutting_plan_to_excel.py

from odoo import models
import xlsxwriter
from io import BytesIO
import base64

def export_2dr_cutting_plan_to_excel(package):

    # Create an in-memory binary stream for the Excel file
    output = BytesIO()

    # Create a new Excel workbook and worksheet
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet("2DR Cutting Plan")

    # Define some basic formatting
    bold_format = workbook.add_format({'bold': True})
    normal_format = workbook.add_format({'font_size': 10})

    # Write the cutting plan title
    worksheet.write(0, 0, "2D Rectangular Cutting Plan", bold_format)

    # Split the cutting_plan text into lines and write to the worksheet
    if package.cutting_plan:
        lines = package.cutting_plan.split("\n")
        for row, line in enumerate(lines, start=1):  # Start from row 1 to leave space for title
            worksheet.write(row, 0, line, normal_format)

    # Adjust column width to fit content (approximate)
    worksheet.set_column(0, 0, 50)  # Set column A width to 50 characters

    # Close the workbook to finalize the file
    workbook.close()

    # Get the binary data from the stream
    output.seek(0)
    file_data = output.getvalue()

    # Encode the file data in base64 for Odoo attachment
    file_data_base64 = base64.b64encode(file_data).decode('utf-8')

    # Create an attachment in Odoo
    attachment = package.env['ir.attachment'].create({
        'name': f"2DR_Cutting_Plan_{package.name or 'Unnamed'}.xlsx",
        'type': 'binary',
        'datas': file_data_base64,
        'res_model': package._name,
        'res_id': package.id,
        'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })

    # Clean up the stream
    output.close()

    # Return an action to download the file
    return {
        'type': 'ir.actions.act_url',
        'url': f'/web/content/{attachment.id}?download=true',
        'target': 'self',
    }
