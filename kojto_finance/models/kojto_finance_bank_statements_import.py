from odoo import models, fields
from datetime import date
import base64
import re


class KojtoFinanceBankStatementsImport(models.TransientModel):
    _name = "kojto.finance.bank.statements.import"
    _description = "Bank Statements Import"

    files = fields.Many2many("ir.attachment", string="Select files")


    result_message = fields.Text(string="Import Summary", readonly=True)

    def import_files(self):

        newly_imported = []
        duplicates_ignored = []
        imported_statements = []

        for attachment in self.files:
            if not attachment.datas:
                continue

            # Decode file to check for duplicates
            decoded_bytes = base64.b64decode(attachment.datas)
            statement_file_text = None

            encodings_to_try = ['utf-8', 'windows-1251', 'cp1251', 'iso-8859-5', 'cp1252']

            for encoding in encodings_to_try:
                try:
                    statement_file_text = decoded_bytes.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue

            if statement_file_text is None:
                statement_file_text = decoded_bytes.decode('utf-8', errors='replace')

            if statement_file_text is not None:
                statement_file_text = statement_file_text.replace('\x00', '')
                statement_file_text = re.sub(r"[\r]+ ", "", statement_file_text)
                statement_file_text = re.sub(r"[\r]+", "", statement_file_text)

            # Check if statement already exists
            if statement_file_text:
                existing_record = self.env["kojto.finance.bank.statements"].search([
                    ("statement_file_text", "=", statement_file_text)
                ], limit=1)

                if existing_record:
                    upload_date = existing_record.create_date.strftime("%Y-%m-%d %H:%M:%S") if existing_record.create_date else "Unknown"
                    duplicates_ignored.append(f"{existing_record.name} (Uploaded: {upload_date})")
                    continue

            # Create new statement
            statement = self.env["kojto.finance.bank.statements"].create({
                "statement_file": attachment.datas,
                "statement_filename": attachment.name,
            })
            newly_imported.append(statement.name if statement.name else attachment.name)
            imported_statements.append(statement)

        # Validate balance continuity for all imported statements after all transactions are created
        # Sort statements by date to validate in chronological order
        validation_errors = []
        sorted_statements = sorted(
            imported_statements,
            key=lambda s: fields.Date.to_date(s.date_start) or date.min,
        )
        for statement in sorted_statements:
            error_details = statement.validate_balance_continuity(return_error_details=True)
            if error_details:
                validation_errors.append(error_details)

        total_transactions = sum(stmt.number_of_transactions for stmt in imported_statements)

        message_lines = []

        # STATEMENTS section
        message_lines.append("STATEMENTS:")
        message_lines.append(f"Newly imported: {len(newly_imported)} file(s)")
        if duplicates_ignored:
            message_lines.append(f"Duplicates ignored: {len(duplicates_ignored)} file(s)")

        # Blank line
        message_lines.append("")
        message_lines.append("")

        # TRANSACTIONS section
        message_lines.append("TRANSACTIONS:")
        message_lines.append(f"Transactions created: {total_transactions}")

        # BALANCE CONTINUITY ERRORS section
        if validation_errors:
            message_lines.append("")
            message_lines.append("")
            message_lines.append("BALANCE CONTINUITY ERRORS:")
            for error in validation_errors:
                message_lines.append(
                    f"Date: {error['date']}: Calculated: {error['calculated_balance']:.2f} {error['currency']} | "
                    f"Statement (#{error['statement_number']}): {error['statement_balance']:.2f} {error['currency']} | "
                    f"Difference: {error['difference']:.2f}"
                )

        message = "\n".join(message_lines)

        summary_record = self.env["kojto.finance.bank.statements.import"].create({
            "result_message": message,
        })

        return {
            "name": "Bank Statement Import Summary",
            "type": "ir.actions.act_window",
            "res_model": "kojto.finance.bank.statements.import",
            "view_mode": "form",
            "res_id": summary_record.id,
            "target": "new",  # Opens as popup
            "view_id": self.env.ref("kojto_finance.view_kojto_finance_bank_statements_import_message_popup").id,
        }

