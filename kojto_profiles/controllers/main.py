from odoo import http
from odoo.http import content_disposition
import io
from openpyxl import Workbook

class KojtoProfileController(http.Controller):
    def __init__(self):
        pass

    @http.route('/kojto_profiles/export_excel/<int:batch_id>', type='http', auth="user")
    def export_excel(self, batch_id, **kwargs):
        batch = http.request.env['kojto.profile.batches'].browse(batch_id).ensure_one()

        output = io.BytesIO()
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Profile Batch Export"
        headers = ['Batch Name', 'Subcode', 'Language']
        sheet.append(headers)
        row = [
            batch.name or '',
            batch.subcode_id.name or '' if batch.subcode_id else '',
            batch.language_id.name or '' if batch.language_id else '',
        ]
        sheet.append(row)
        workbook.save(output)
        output.seek(0)
        file_content = output.read()
        output.close()

        filename = f"Profile_Batch_{batch.name or 'Export'}.xlsx"
        return http.request.make_response(
            file_content,
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', content_disposition(filename)),
            ]
        )
