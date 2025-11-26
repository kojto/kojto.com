# kojto_finance/models/kojto_finance_cashflow_ajur_exports.py
# The file implements functionality to export cashflow transactions from Odoo to AJUR(accounting software) accounting format, generating properly formatted accounting entries that can be imported into AJUR.

from odoo import models, api, fields
from odoo.exceptions import UserError
from io import BytesIO, StringIO
from datetime import datetime
from collections import defaultdict

from . import kojto_finance_vat_treatment
from .kojto_finance_ajur_exports import KojtoFinanceExportSelectionToAjur, AJUR_CURRENCY_NAME_MAPPINGS, AJUR_TRANSACTION_TYPE_MAPPINGS

import base64


class KojtoFinanceCashflowExportSelectionToAjur(KojtoFinanceExportSelectionToAjur):
    _name = "kojto.finance.cashflow.exportselectiontoajur"
    _description = "Kojto Finance Cashflow Export Selection To Ajur"

    def action_export_to_ajur(self):
        transaction_ids = self._context.get("selected_transactions", [])

        if not transaction_ids:
            raise UserError("Please select at least one transaction")

        transactions = self.env["kojto.finance.cashflow"].browse(transaction_ids)

        if not transactions:
            raise UserError("Looks like the selected transactions have no content to export")

        # Add validation step before accountant ID check (like invoice validation)
        self._validate_export_to_ajur(transactions)

        result = StringIO()
        accountant_id = self._get_accountant_id()
        filename = f"Ajur-Cashflow-Export-{datetime.now().strftime('%Y-%m-%d-%H-%M')}.txt"

        for transaction in transactions:
            # generate the AJUR template text to see if the transaction is valid(it might throw an error if the transaction is not valid)
            ajur_template_txt = self._generate_transaction_export_txt(transaction)

            acc_op_date = transaction.date_value.strftime("%Y-%m-%d") if transaction.date_value else ""
            acc_archive_number = self._get_acc_archive_number(transaction)

            # save the archive number and operation date on the current invoice
            transaction.write(
                {
                    "accountant_id": accountant_id,
                    "accounting_op_date": acc_op_date,
                    "accounting_archive_number": acc_archive_number,
                    "date_export": fields.Date.today(),
                }
            )

            result.write(ajur_template_txt)

        if not len(result.getvalue()):
            raise UserError("Looks like the selected transactions have no allocations to export")

        result.seek(0)
        file_data = result.getvalue().encode("utf-8")
        file_b64 = base64.b64encode(file_data)

        attachment_data = {"name": filename, "type": "binary", "datas": file_b64, "res_model": "kojto.finance.cashflow", "mimetype": "text/plain"}
        attachment = self.env["ir.attachment"].create(attachment_data)

        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "self",
        }

    def _validate_export_to_ajur(self, transactions):
        """Validate transactions before export (similar to invoice validation)"""
        transaction_errors = defaultdict(list)

        for transaction in transactions:
            # Check if transaction has allocations
            if not transaction.transaction_allocation_ids:
                transaction_errors[transaction.id].append("no transaction allocations")
                continue

            # Check each allocation
            for allocation in transaction.transaction_allocation_ids:
                if not allocation.accounting_template_id:
                    transaction_errors[transaction.id].append(f"allocation {allocation.id} has no accounting template")

                if allocation.accounting_template_id.requires_subtype_id and not allocation.subtype_id:
                    transaction_errors[transaction.id].append(f"allocation {allocation.id} has no subtype")

                if allocation.accounting_template_id.requires_identifier_id and not allocation.identifier_id:
                    transaction_errors[transaction.id].append(f"allocation {allocation.id} has no identifier")

                if not allocation.subcode_id:
                    transaction_errors[transaction.id].append(f"allocation {allocation.id} has no subcode")

        errors_str = ""
        for transaction_id, errors in transaction_errors.items():
            transaction = self.env["kojto.finance.cashflow"].browse(transaction_id)
            errors_str += f"Transaction {transaction.description or transaction.id} cannot be exported:\n\t\t" + "\n\t\t".join(errors) + "\n"

        if errors_str:
            raise UserError(errors_str)

    def _generate_transaction_export_txt(self, transaction):
        # Prepare the accounting template data which will be used to replace placeholders in the debit and credit accounts structure templates
        transaction_vars, transaction_allocation_vars = self._get_accounting_template_vars(transaction)

        # Generate the accounting rows
        result = self._generate_all_accounting_operations_per_transaction(
            transaction_vars,
            transaction_allocation_vars,
        )

        return result

    def _get_accounting_template_vars(self, transaction):
        exchange_rate_to_bgn = transaction.exchange_rate_to_bgn if transaction.currency_id.name != "BGN" else 1

        trx_acc_statement_number = transaction.statement_id.number if transaction.statement_id else "0"

        doc_type = AJUR_TRANSACTION_TYPE_MAPPINGS.get(
            (transaction.transaction_direction, transaction.bank_account_id.account_type),
            "УУ",
        )

        if transaction.bank_account_id.account_type == "cash":
            trx_acc_statement_number = transaction.date_value.strftime("%Y%m") if transaction.date_value else ""

        # Variables for the main transaction record
        transaction_vars = {
            "trx_direction": transaction.transaction_direction,
            "trx_medium": transaction.bank_account_id.account_type,
            "trx_doc_type": doc_type,
            "trx_date": transaction.date_value.strftime("%d.%m.%Y") if transaction.date_value else "",
            "trx_currency_code": transaction.currency_id.name,
            "trx_currency": AJUR_CURRENCY_NAME_MAPPINGS.get(transaction.currency_id.name, transaction.currency_id.name),
            "currency_code": transaction.currency_id.name,
            "currency": AJUR_CURRENCY_NAME_MAPPINGS.get(transaction.currency_id.name, transaction.currency_id.name),
            "trx_bank_account_iban": transaction.bank_account_id.IBAN,
            "trx_bank_account_desc": transaction.bank_account_id.description,
            "trx_bank_account_ref_number": transaction.bank_account_id.ref_number,
            "trx_exchange_rate_to_bgn": exchange_rate_to_bgn,
            "trx_amount": transaction.amount,
            "trx_amount_bgn": transaction.amount * exchange_rate_to_bgn,
            "trx_acc_archive_number": self._get_acc_archive_number(transaction),
            "trx_acc_statement_number": trx_acc_statement_number,
            "trx_acc_op_date": transaction.date_value.strftime("%d.%m.%Y") if transaction.date_value else "",
            "trx_accountant_id": self._get_accountant_id(),
            "counterparty_name": transaction.counterparty_id.name,
            "counterparty_reg_num": transaction.counterparty_id.registration_number if transaction.counterparty_id.registration_number else "00",
            "counterparty_client_number": transaction.counterparty_id.client_number if transaction.counterparty_id else "0",
        }

        # Variables for each transaction allocation
        transaction_allocations_vars = []
        for allocation in transaction.transaction_allocation_ids:
            allocation_vars = self._get_accounting_template_vars_for_allocation(
                allocation,
                exchange_rate_to_bgn,
            )

            if not allocation_vars:
                continue

            transaction_allocations_vars.append(allocation_vars)

        return transaction_vars, transaction_allocations_vars

    def _get_accounting_template_vars_for_allocation(self, allocation, exchange_rate_to_bgn):
        allocation_vars = {
            "trx_allocation_accounting_ref_number": allocation.accounting_ref_number,
            "trx_allocation_subtype_name": allocation.subtype_id.name,
            "trx_allocation_subtype": allocation.subtype_id.subtype_number,
            "content_subtype": allocation.subtype_id.subtype_number,
            "content_subtype_name": allocation.subtype_id.name,
            "trx_allocation_subcode": allocation.subcode_id.name,
            "trx_allocation_maincode_code": allocation.subcode_id.maincode_id.maincode + "." + allocation.subcode_id.code_id.code,
            "trx_allocation_amount": allocation.amount,
            "trx_allocation_amount_bgn": allocation.amount * exchange_rate_to_bgn,
            "trx_allocation_amount_eur": allocation.amount * allocation.transaction_id.exchange_rate_to_eur,
            "trx_allocation_amount_base": allocation.amount_base,
            "trx_allocation_currency_code": allocation.transaction_id.currency_id.name,
            "trx_allocation_currency_name": AJUR_CURRENCY_NAME_MAPPINGS.get(allocation.transaction_id.currency_id.name, allocation.transaction_id.currency_id.name),
            "trx_allocation_accounting_template_id": allocation.accounting_template_id,
        }

        if not allocation.invoice_id:
            return allocation_vars

        invoice = allocation.invoice_id
        invoice_vars = {
            "num": invoice.consecutive_number,
            "pnum": invoice.parent_invoice_id.consecutive_number if invoice.parent_invoice_id else invoice.consecutive_number,
            "subcode": invoice.subcode_id.name,
            "maincode_code": invoice.subcode_id.maincode_id.maincode + "." + invoice.subcode_id.code_id.code,
            "type": invoice.invoice_type,
            "issue_date": invoice.date_issue.strftime("%d.%m.%Y") if invoice.date_issue else "",
            "pissue_date": invoice.parent_invoice_date_issue.strftime("%d.%m.%Y") if invoice.parent_invoice_id and invoice.parent_invoice_id.date_issue else (invoice.date_issue.strftime("%d.%m.%Y") if invoice.date_issue else ""),
            "due_date": invoice.date_due.strftime("%d.%m.%Y") if invoice.date_due else "",
            "company_name": invoice.company_id.name,
            "company_tax_num": invoice.company_tax_number_id.tax_number if invoice.company_tax_number_id else "",
            "company_reg_num": invoice.company_registration_number,
            "company_short_num": invoice.company_registration_number[-4:],
            "document_in_out_type": invoice.document_in_out_type,
            "counterparty_tax_num": invoice.counterparty_tax_number_id.tax_number if invoice.counterparty_tax_number_id else "00",
            "counterparty_country": invoice.counterparty_address_id.country_id.code if invoice.counterparty_address_id else "",
            "currency_code": invoice.currency_id.name,
            "currency_name": AJUR_CURRENCY_NAME_MAPPINGS.get(invoice.currency_id.name, invoice.currency_id.name),
        }

        invoice_vars["auto_vat_num"] = invoice.counterparty_tax_number_id.tax_number
        invoice_vars["auto_eik_num"] = "999999999999999"

        if invoice_vars["counterparty_country"] == "BG":
            invoice_vars["auto_eik_num"] = invoice.counterparty_registration_number
            invoice_vars["auto_vat_num"] = invoice_vars["auto_eik_num"]
            if invoice.counterparty_tax_number_id:
                invoice_vars["auto_vat_num"] = invoice.counterparty_tax_number_id.tax_number
        elif invoice.counterparty_id.is_non_EU:
            invoice_vars["auto_vat_num"] = "999999999999999"

        allocation_vars.update(invoice_vars)

        return allocation_vars

    def _get_acc_archive_number(self, transaction):
        # The magix numbers here are requested by the accountants!!!
        if transaction.bank_account_id.account_type == "cash":
            return f"501/{transaction.date_value.strftime('%m')}" if transaction.date_value else "501/00"

        if not transaction.statement_id:
            return "501/0"

        if transaction.currency_id.name == "BGN":
            return f"503/{transaction.statement_id.number}"

        return f"504/{transaction.statement_id.number}"

    def _generate_all_accounting_operations_per_transaction(
        self,
        transaction_vars,
        transaction_allocations_vars,
    ):
        ops_txt = StringIO()

        if not transaction_allocations_vars or not transaction_vars:
            return ""

        # Acc operations for each allocation
        for i, allocation_vars in enumerate(transaction_allocations_vars):
            ## Basic accounting operations
            accounting_template = allocation_vars.get("trx_allocation_accounting_template_id")
            if not accounting_template:
                continue

            if not accounting_template.accounting_ops_ids:
                continue

            for acc_row in accounting_template.accounting_ops_ids:
                try:
                    operation_text = self._generate_accounting_operation(acc_row, transaction_vars, allocation_vars)
                    ops_txt.write(operation_text + "\r\n")
                except Exception as e:
                    raise e

        result = ops_txt.getvalue()
        return result

    def _generate_accounting_operation(self, acc_row, transaction_vars, allocation_vars):
        tv = transaction_vars
        at = allocation_vars["trx_allocation_accounting_template_id"]
        debit_acc_suffix, credit_acc_suffix = self._render_account_structure_template(acc_row, transaction_vars, allocation_vars)

        # trx_allocation_amount is the amount in the currency of the transaction that was allocated to the account
        # trx_allocation_amount_base is the amount in the base currency of the document that the allocation is related to
        if transaction_vars["trx_direction"] == "outgoing":
            debit_amount_currency = 0 if not acc_row.debit_account_id.is_currency_account else allocation_vars["trx_allocation_amount_base"]
            credit_amount_currency = 0 if not acc_row.credit_account_id.is_currency_account else allocation_vars["trx_allocation_amount"]
        else:
            debit_amount_currency = 0 if not acc_row.debit_account_id.is_currency_account else allocation_vars["trx_allocation_amount"]
            credit_amount_currency = 0 if not acc_row.credit_account_id.is_currency_account else allocation_vars["trx_allocation_amount_base"]

        txt_parts = [
            f"{acc_row.acc_operation_type}@@",
            f"{tv['trx_acc_statement_number']}#",
            f"{tv['trx_date']}#",
            f"{tv['trx_acc_archive_number']}#",
            f"{acc_row.acc_operation}##",
            f"{tv['trx_accountant_id']}#",
            f"{tv['trx_acc_op_date']}#",
            f"{tv['trx_doc_type']}#",
            f"##",
            f"##",
            f"{at.template_type_id.name}@@",
            f"{acc_row.debit_account_id.account_number}@@",
            f"{debit_acc_suffix}@@",
            f"{acc_row.credit_account_id.account_number}@@",
            f"{credit_acc_suffix}@@",
            f"{allocation_vars['trx_allocation_amount_bgn']}#",
            f"0#",
            f"0#",
            f"0#",
            f"0#",
            f"{debit_amount_currency}#",
            f"{credit_amount_currency}@@",
        ]

        return "".join(txt_parts)

    def _render_account_structure_template(self, acc_row, transaction_vars, allocation_vars):
        if not acc_row.debit_account_id or not acc_row.credit_account_id:
            raise ValueError("Debit or credit account is missing")

        debit_template = acc_row.debit_account_id.account_structure_template or ""
        credit_template = acc_row.credit_account_id.account_structure_template or ""

        def replace_template_vars(template, vars):
            result = template
            for key, value in vars.items():
                if not isinstance(value, (str)):
                    value = str(value)
                result = result.replace(f"{{{key}}}", value)
            return result

        # the following order is important because the allocation vars will override the transaction vars
        debit_acc_suffix = replace_template_vars(debit_template, allocation_vars)
        debit_acc_suffix = replace_template_vars(debit_acc_suffix, transaction_vars)

        # the following order is important because the allocation vars will override the transaction vars
        credit_acc_suffix = replace_template_vars(credit_template, allocation_vars)
        credit_acc_suffix = replace_template_vars(credit_acc_suffix, transaction_vars)

        return debit_acc_suffix, credit_acc_suffix
