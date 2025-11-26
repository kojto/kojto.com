# kojto_finance/models/kojto_finance_invoices_ajur_exports.py
# The file implements functionality to export invoices from Odoo to AJUR(accounting software) accounting format, generating properly formatted accounting entries that can be imported into AJUR.
from odoo import models, api, fields
from odoo.exceptions import UserError, ValidationError
from io import BytesIO, StringIO
from datetime import datetime
from collections import defaultdict

from . import kojto_finance_vat_treatment
from .kojto_finance_ajur_exports import KojtoFinanceExportSelectionToAjur, AJUR_CURRENCY_NAME_MAPPINGS, AJUR_DOC_MAPPINGS
import base64


class KojtoFinanceInvoicesExportSelectionToAjur(KojtoFinanceExportSelectionToAjur):
    _name = "kojto.finance.invoices.exportselectiontoajur"
    _description = "Kojto Finance Invoices Export Selection To Ajur"

    acc_op_datetime = fields.Datetime(string="Operation Date", default="")
    acc_op_date = fields.Date(string="Operation Date (Date)", compute="_compute_acc_op_date", store=True, index=True)

    @api.depends('acc_op_datetime')
    def _compute_acc_op_date(self):
        """Compute acc_op_date from acc_op_datetime"""
        for record in self:
            if record.acc_op_datetime:
                record.acc_op_date = record.acc_op_datetime.date() if record.acc_op_datetime else False
            else:
                record.acc_op_date = False

    def action_export_to_ajur(self):
        # Get the actual invoices to export
        invoice_model = self.env['kojto.finance.invoices']
        active_ids = self.env.context.get('active_ids', [])
        invoices = invoice_model.browse(active_ids)
        # Check for missing subcodes before exporting
        missing_subcodes = []
        for invoice in invoices:
            for content in invoice.content:
                if not content.subcode_id:
                    missing_subcodes.append(f"Invoice content ID {content.id} (invoice ID {invoice.id}) is missing a subcode.")
        if missing_subcodes:
            error_message = "Cannot export to Ajur due to missing subcodes in the following invoice content lines:\n" + "\n".join(missing_subcodes)
            raise ValidationError(error_message)

        invoice_ids = self._context.get("selected_invoices", [])
        if not invoice_ids:
            raise UserError("Please select at least one invoice")

        invoices = self.env["kojto.finance.invoices"].browse(invoice_ids)

        self._validate_export_to_ajur(invoices)

        result = StringIO()
        accountant_id = self._get_accountant_id()
        filename = f"Ajur-Invoices-Export-{datetime.now().strftime('%Y-%m-%d-%H-%M')}.txt"

        for i, invoice in enumerate(invoices, start=1):
            if invoice.invoice_type not in ("invoice", "credit_note", "debit_note", "insurance_policy"):
                continue

            invoice.accounting_op_date = self.acc_op_datetime if self.acc_op_datetime else invoice.accounting_op_date
            invoice.accounting_export_date = datetime.now()
            invoice.accountant_id = accountant_id

            # generate the AJUR template text to see if the invoice is valid(it might throw an error if the invoice is not valid)
            ajur_template_txt = self._generate_invoice_export_txt(invoice)

            result.write(ajur_template_txt)

        if not len(result.getvalue()):
            raise UserError("Looks like the selected invoices have no content to export or archiving number is not set")

        # save the accounting operation date, accountant id and export date on exported invoices
        for invoice in invoices:
            invoice.write(
                {
                    "accounting_op_date": invoice.accounting_op_date,
                    "accountant_id": invoice.accountant_id,
                    "accounting_export_date": invoice.accounting_export_date,
                }
            )

        result.seek(0)
        file_data = result.getvalue().encode("utf-8")
        file_b64 = base64.b64encode(file_data)

        attachment_data = {"name": filename, "type": "binary", "datas": file_b64, "res_model": "kojto.finance.invoices", "mimetype": "text/plain"}
        attachment = self.env["ir.attachment"].create(attachment_data)

        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "self",
        }

    def _validate_export_to_ajur(self, invoices):
        invoice_errors = defaultdict(list)
        for i, invoice in enumerate (invoices, start=1):
            if not invoice.accounting_archive_number:
                invoice_errors[invoice.consecutive_number].append("no archiving number")

            if not invoice.accounting_op_date:
                invoice_errors[invoice.consecutive_number].append("no accounting operation date")

            for content in invoice.content:
                if content.accounting_template_id.requires_subtype_id and not content.subtype_id:
                    invoice_errors[invoice.consecutive_number].append(f"content {content.name} has no subtype")

                if content.accounting_template_id.requires_identifier_id and not content.identifier_id:
                    invoice_errors[invoice.consecutive_number].append(f"content '{content.name}' has no identifier")

                if not content.accounting_template_id:
                    invoice_errors[invoice.consecutive_number].append(f"content '{content.name}' has no accounting template")

                if not content.vat_treatment_id:
                    invoice_errors[invoice.consecutive_number].append(f"content '{content.name}' has no VAT treatment")

        errors_str = ""
        for invoice_consecutive_number, invoice_errors in invoice_errors.items():
            errors_str += f"Invoice {invoice_consecutive_number} cannot be exported:\n\t\t" + "\n\t\t".join(invoice_errors) + "\n"

        if errors_str:
            raise UserError(errors_str)

    def _generate_invoice_export_txt(self, invoice):
        # Prepare the accounting template data which will be used to replace placeholders in the debit and credit accounts structure templates
        invoice_vars, invoice_content_vars_by_acc_template, invoice_content_vars_by_vat_treatment = self._get_accounting_template_vars(
            invoice,
        )

        # Generate the accounting rows
        result = self._generate_all_accounting_operations_per_invoice(
            invoice_vars,
            invoice_content_vars_by_acc_template,
            invoice_content_vars_by_vat_treatment,
        )

        return result

    def _get_accounting_template_vars(self, invoice):
        exchange_rate_to_bgn = invoice.exchange_rate_to_bgn if invoice.currency_id.name != "BGN" else 1

        if not invoice.counterparty_address_id:
            raise UserError(f"No counterparty address is set for invoice {invoice.consecutive_number}")

        invoice_vars = {
            "num": invoice.consecutive_number,
            "pnum": invoice.parent_invoice_id.consecutive_number if invoice.parent_invoice_id else invoice.consecutive_number,
            "subcode": invoice.subcode_id.name,
            "maincode_code": invoice.subcode_id.maincode_id.maincode + "." + invoice.subcode_id.code_id.code,
            "type": invoice.invoice_type,
            "issue_date": invoice.date_issue.strftime("%d.%m.%Y") if invoice.date_issue else "",
            "pissue_date": invoice.parent_invoice_date_issue.strftime("%d.%m.%Y") if invoice.parent_invoice_id and invoice.parent_invoice_id.date_issue else (invoice.date_issue.strftime("%d.%m.%Y") if invoice.date_issue else ""),
            "due_date": invoice.date_due.strftime("%d.%m.%Y") if invoice.date_due else "",
            "op_date": invoice.accounting_op_date.strftime("%d.%m.%Y"),
            "arch_num": invoice.accounting_archive_number,
            "acc_user": invoice.accountant_id,
            "counterparty_name": invoice.counterparty_id.name,
            "counterparty_reg_num": invoice.counterparty_registration_number if invoice.counterparty_registration_number else "00",
            "counterparty_short_num": invoice.counterparty_tax_number_id.tax_number[-4:] if invoice.counterparty_tax_number_id else invoice.counterparty_id.id,
            "counterparty_tax_num": invoice.counterparty_tax_number_id.tax_number if invoice.counterparty_tax_number_id else "00",
            "counterparty_country": invoice.counterparty_address_id.country_id.code if invoice.counterparty_address_id else "",
            "counterparty_client_number": invoice.counterparty_id.client_number if invoice.counterparty_id else "0",
            "company_name": invoice.company_id.name,
            "company_tax_num": invoice.company_tax_number_id.tax_number if invoice.company_tax_number_id else "",
            "company_reg_num": invoice.company_registration_number,
            "company_short_num": invoice.company_registration_number[-4:],
            "currency_code": invoice.currency_id.name,
            "currency": AJUR_CURRENCY_NAME_MAPPINGS.get(invoice.currency_id.name, invoice.currency_id.name),
            "exchange_rate_to_bgn": exchange_rate_to_bgn,
            "pre_vat_total": invoice.pre_vat_total,
            "pre_vat_total_bgn": invoice.pre_vat_total * exchange_rate_to_bgn,
            "vat_total": invoice.vat_total,
            "vat_total_bgn": invoice.vat_total * exchange_rate_to_bgn,
            "vat_drift": 0,
            "vat_drift_bgn": 0,
            "custom_vat": invoice.custom_vat,
            "custom_vat_bgn": invoice.custom_vat * exchange_rate_to_bgn,
            "total_price": invoice.total_price,
            "total_price_bgn": invoice.total_price * exchange_rate_to_bgn,
            "document_in_out_type": invoice.document_in_out_type,
            "invoice_vat_treatment_id": invoice.invoice_vat_treatment_id.id,
        }

        if invoice_vars["custom_vat"] > 0:
            invoice_vars["vat_drift"] = invoice_vars["vat_total"] - invoice_vars["custom_vat"]
            invoice_vars["vat_drift_bgn"] = invoice_vars["vat_total_bgn"] - invoice_vars["custom_vat_bgn"]

        invoice_vars["auto_vat_num"] = invoice.counterparty_tax_number_id.tax_number
        invoice_vars["auto_eik_num"] = "999999999999999"

        if invoice_vars["counterparty_country"] == "BG":
            invoice_vars["auto_eik_num"] = invoice.counterparty_registration_number
            invoice_vars["auto_vat_num"] = invoice_vars["auto_eik_num"]
            if invoice.counterparty_tax_number_id:
                invoice_vars["auto_vat_num"] = invoice.counterparty_tax_number_id.tax_number
        elif invoice.counterparty_id.is_non_EU:
            invoice_vars["auto_vat_num"] = "999999999999999"

        invoice_content_vars_by_acc_template, invoice_content_vars_by_vat_treatment = self._group_similar_content(invoice)

        max_vat_total_bgn = max(invoice_content_vars_by_vat_treatment.values(), key=lambda x: x["content_vat_total"])
        max_vat_total_bgn["vat_drift_bgn"] = invoice_vars["vat_drift_bgn"]
        max_vat_total_bgn["vat_drift"] = invoice_vars["vat_drift"]
        max_vat_total_bgn["content_vat_total_bgn"] = max_vat_total_bgn["content_vat_total_bgn"] - invoice_vars["vat_drift_bgn"]
        max_vat_total_bgn["content_vat_total"] -= invoice_vars["vat_drift"]

        return invoice_vars, invoice_content_vars_by_acc_template, invoice_content_vars_by_vat_treatment

    def _group_similar_content(self, invoice):
        grouped_content_by_acc_template = defaultdict(
            lambda: {
                "vat_treatment_id": None,
                "accounting_template_id": None,
                "content_subcode": None,
                "content_subtype": None,
                "content_subtype_name": None,
                "content_identifier": None,
                "content_identifier_name": None,
                "content_warehouse": None,
                "content_warehouse_name": None,
                "content_quantity": 0,
                "content_unit_price": 0,
                "content_pre_vat_total": 0,
                "content_vat_rate": 0,
                "content_vat_total": 0,
                "content_total_price": 0,
                "content_pre_vat_total_bgn": 0,
                "content_vat_total_bgn": 0,
                "content_total_price_bgn": 0,
                "content_unit": None,
                "content_name": None,
            }
        )

        grouped_content_by_vat_treatment = defaultdict(
            lambda: {
                "accounting_template_id": None,
                "vat_treatment_id": None,
                "content_pre_vat_total": 0,
                "content_maincode_code": invoice.subcode_id.maincode_id.maincode + "." + invoice.subcode_id.code_id.code,
                "content_vat_rate": 0,
                "content_vat_total": 0,
                "content_total_price": 0,
                "content_pre_vat_total_bgn": 0,
                "content_vat_total_bgn": 0,
                "content_total_price_bgn": 0,
                "vat_drift_bgn": 0,
                "vat_drift": 0,
            }
        )

        for content in invoice.content:
            if not content.subcode_id:
                raise ValidationError(
                    f"Invoice content ID {content.id} (invoice ID {content.invoice_id.id if content.invoice_id else 'N/A'}) "
                    f"is missing a subcode_id. Please assign a valid subcode to this line before exporting or processing."
                )
            key = (
                content.accounting_template_id.id,
                content.subcode_id.maincode_id.maincode + "." + content.subcode_id.code_id.code,
                content.subtype_id.id,
                content.identifier_id.id,
            )

            unit_name_in_bg = content.unit_id.name
            for translation in content.unit_id.translation_ids:
                if translation.language_id.code.startswith("bg"):
                    unit_name_in_bg = translation.name
                    break

            grouped_content_by_acc_template[key]["vat_treatment_id"] = content.vat_treatment_id
            grouped_content_by_acc_template[key]["accounting_template_id"] = content.accounting_template_id
            grouped_content_by_acc_template[key]["content_subcode"] = content.subcode_id.name
            grouped_content_by_acc_template[key]["content_maincode_code"] = content.subcode_id.maincode_id.maincode + "." + content.subcode_id.code_id.code
            grouped_content_by_acc_template[key]["content_subtype_name"] = content.subtype_id.name
            grouped_content_by_acc_template[key]["content_subtype"] = content.subtype_id.subtype_number
            grouped_content_by_acc_template[key]["content_identifier"] = content.identifier_id.identifier
            grouped_content_by_acc_template[key]["content_identifier_name"] = content.identifier_id.name
            grouped_content_by_acc_template[key]["content_warehouse_name"] = content.accounting_template_id.template_type_id.accounting_warehouse_name
            grouped_content_by_acc_template[key]["content_warehouse"] = content.accounting_template_id.template_type_id.accounting_warehouse
            grouped_content_by_acc_template[key]["content_name"] = content.name
            grouped_content_by_acc_template[key]["content_unit"] = unit_name_in_bg
            grouped_content_by_acc_template[key]["content_quantity"] += content.quantity
            grouped_content_by_acc_template[key]["content_unit_price"] += content.unit_price
            grouped_content_by_acc_template[key]["content_pre_vat_total"] += content.pre_vat_total
            grouped_content_by_acc_template[key]["content_vat_rate"] = content.vat_rate
            grouped_content_by_acc_template[key]["content_vat_total"] += content.vat_total
            grouped_content_by_acc_template[key]["content_total_price"] += content.total_price

            grouped_content_by_acc_template[key]["content_pre_vat_total_bgn"] += content.pre_vat_total * invoice.exchange_rate_to_bgn
            grouped_content_by_acc_template[key]["content_vat_total_bgn"] += content.vat_total * invoice.exchange_rate_to_bgn
            grouped_content_by_acc_template[key]["content_total_price_bgn"] += content.total_price * invoice.exchange_rate_to_bgn

            grouped_content_by_vat_treatment[content.vat_treatment_id.vat_treatment_type]["accounting_template_id"] = content.accounting_template_id
            grouped_content_by_vat_treatment[content.vat_treatment_id.vat_treatment_type]["vat_treatment_id"] = content.vat_treatment_id
            grouped_content_by_vat_treatment[content.vat_treatment_id.vat_treatment_type]["content_pre_vat_total"] += content.pre_vat_total
            grouped_content_by_vat_treatment[content.vat_treatment_id.vat_treatment_type]["content_vat_rate"] += content.vat_rate
            grouped_content_by_vat_treatment[content.vat_treatment_id.vat_treatment_type]["content_vat_total"] += content.vat_total

            # VAT FOR ART69_21_2_NON_EU MUST BE 0 (SWISS invoices)
            if content.vat_treatment_id.vat_treatment_type == kojto_finance_vat_treatment.VAT_TRTYPE_ART69_21_2_NON_EU[0]:
                grouped_content_by_vat_treatment[content.vat_treatment_id.vat_treatment_type]["content_vat_total"] = 0

            grouped_content_by_vat_treatment[content.vat_treatment_id.vat_treatment_type]["content_total_price"] += content.total_price
            grouped_content_by_vat_treatment[content.vat_treatment_id.vat_treatment_type]["content_pre_vat_total_bgn"] += content.pre_vat_total * invoice.exchange_rate_to_bgn
            grouped_content_by_vat_treatment[content.vat_treatment_id.vat_treatment_type]["content_vat_total_bgn"] += content.vat_total * invoice.exchange_rate_to_bgn
            grouped_content_by_vat_treatment[content.vat_treatment_id.vat_treatment_type]["content_total_price_bgn"] += content.total_price * invoice.exchange_rate_to_bgn

        return grouped_content_by_acc_template, grouped_content_by_vat_treatment

    def _generate_all_accounting_operations_per_invoice(
        self,
        invoice_vars,
        invoice_content_vars_by_acc_template,
        invoice_content_vars_by_vat_treatment,
    ):
        ops_txt = StringIO()

        if not invoice_content_vars_by_acc_template or not invoice_content_vars_by_vat_treatment or not invoice_vars:
            return ""

        # Acc operations for each content
        for content_vars in invoice_content_vars_by_acc_template.values():
            ## Basic accounting operations
            for acc_row in content_vars["accounting_template_id"].accounting_ops_ids:
                ops_txt.write(
                    self._generate_accounting_operation(acc_row, invoice_vars, content_vars, amount_ref="content_pre_vat_total") + "\r\n",
                )

        for vat_treatment_type, content_vars in invoice_content_vars_by_vat_treatment.items():
            ## VAT accounting operations
            if not len(content_vars["vat_treatment_id"].accounting_ops_ids):
                continue

            ## There should be only one VAT accounting operation per content
            dds_acc_row = content_vars["vat_treatment_id"].accounting_ops_ids[0]
            ops_txt.write(
                self._generate_accounting_operation(dds_acc_row, invoice_vars, content_vars, amount_ref="content_vat_total") + "\r\n",
            )

        # VAT book operation
        ops_txt.write(
            self._generate_accounting_vat_book_operation(invoice_vars, invoice_content_vars_by_vat_treatment) + "\r\n",
        )

        return ops_txt.getvalue()

    def _generate_accounting_operation(
        self,
        acc_row,
        invoice_vars,
        content_vars,
        amount_ref="content_pre_vat_total",
    ):
        iv = invoice_vars
        at = content_vars["accounting_template_id"]
        debit_acc_suffix, credit_acc_suffix = self._render_account_structure_template(acc_row, invoice_vars, content_vars)
        debit_amount_currency, credit_amount_currency = self._calculate_acc_row_amounts_to_bgn(acc_row, content_vars, amount_ref)
        debit_qty, credit_qty, debit_unit, credit_unit = self._calculate_acc_row_qty(acc_row, content_vars)

        amount_bgn = content_vars[amount_ref + "_bgn"]

        # more info on the exact templates: https://docs.google.com/spreadsheets/d/1JiZcSsIaVpwSzlXzKVyqoaIthaxxC9yhG_cX_eMif2Y/edit?gid=220125368#gid=220125368
        # basic accounting operations

        doc_type, doc_number = AJUR_DOC_MAPPINGS.get(iv["type"], ("", ""))

        txt_parts = [
            f"{acc_row.acc_operation_type}@@",
            f"{iv['num']}#",
            f"{iv['issue_date']}#",
            f"{iv['arch_num']}#",
            f"{acc_row.acc_operation}##",
            f"{iv['acc_user']}#",
            f"{iv['op_date']}#",
            f"{doc_type}#",
            f"{debit_unit}##",
            f"{credit_unit}##",
            f"{at.template_type_id.name}@@",
            f"{acc_row.debit_account_id.account_number}@@",
            f"{debit_acc_suffix}@@",
            f"{acc_row.credit_account_id.account_number}@@",
            f"{credit_acc_suffix}@@",
            f"{amount_bgn}#",
            f"{debit_qty}#",
            f"0#",
            f"{credit_qty}#",
            f"0#",
            f"{debit_amount_currency}#",
            f"{credit_amount_currency}@@",
        ]

        return "".join(txt_parts)

    def _generate_accounting_vat_book_operation(self, invoice_vars, content_vars):
        """Generate VAT book operation for AJUR export."""
        if not self._should_generate_vat_book_operation(invoice_vars, content_vars):
            return ""

        vat_amounts = self._extract_vat_amounts_by_treatment(invoice_vars, content_vars)
        operation_context = self._build_vat_operation_context(invoice_vars, content_vars)

        return self._format_vat_book_operation_text(operation_context, vat_amounts)

    def _should_generate_vat_book_operation(self, invoice_vars, content_vars):
        """Determine if VAT book operation should be generated."""
        if not content_vars:
            return False

        # Skip VAT book operation for documents with skip VAT treatment
        vat_treatment_types = [v for v in content_vars.keys() if v != kojto_finance_vat_treatment.VAT_TRTYPE_SKIP_VAT[0]]
        if not vat_treatment_types:
            return False

        # Skip VAT book operation for incoming documents from outside Bulgaria
        is_incoming = invoice_vars["document_in_out_type"] == "incoming"
        is_bg_vat = invoice_vars["counterparty_tax_num"].lower().startswith("bg")
        is_bg_address = invoice_vars["counterparty_country"] == "BG"

        return not (is_incoming and not is_bg_vat and not is_bg_address)

    def _extract_vat_amounts_by_treatment(self, invoice_vars, content_vars):
        """Extract VAT base and sum amounts for all treatment types."""
        vat_treatment_types = [
            (kojto_finance_vat_treatment.VAT_TRTYPE_FULL, "vat_base", "vat_sum"),
            (kojto_finance_vat_treatment.VAT_TRTYPE_PARTIAL, "vat_base_partial", "vat_sum_partial"),
            (kojto_finance_vat_treatment.VAT_TRTYPE_NONE, "vat_base_none", None),
            (kojto_finance_vat_treatment.VAT_TRTYPE_ART82_2_5, "vat_base_art82_2_5", "vat_sum_art82_2_5"),
            (kojto_finance_vat_treatment.VAT_TRTYPE_FULL9, "vat_base_full9", "vat_sum_full9"),
            (kojto_finance_vat_treatment.VAT_TRTYPE_OUTSIDE_EU_ART28_1_2, "vat_base_art28_1_2", None),
            (kojto_finance_vat_treatment.VAT_TRTYPE_ART140_ART146_ART173, "vat_base_art140_art146_art173", None),
            (kojto_finance_vat_treatment.VAT_TRTYPE_INSIDE_EU_ART53, "vat_base_art53", None),
            (kojto_finance_vat_treatment.VAT_TRTYPE_ART21_2, "vat_base_art21_2", None),
            (kojto_finance_vat_treatment.VAT_TRTYPE_ART69_21_2_NON_EU, "vat_base_art69_21_2_non_eu", None),
            (kojto_finance_vat_treatment.VAT_TRTYPE_EXEMPT_DELEVERIES, "vat_base_exempt_deleveries", None),
            (kojto_finance_vat_treatment.VAT_TRTYPE_INTERMEDIARY_TRIPARTIE, "vat_base_intermediary_tripartie", None),
            (kojto_finance_vat_treatment.VAT_TRTYPE_SALE_WASTE_ART163A, "vat_base_sale_waste_163a", None),
        ]

        amounts = {}
        for treatment_type, base_key, sum_key in vat_treatment_types:
            treatment_data = content_vars.get(treatment_type[0], {})
            amounts[base_key] = treatment_data.get("content_pre_vat_total_bgn", 0)
            if sum_key:
                amounts[sum_key] = treatment_data.get("content_vat_total_bgn", 0)

        amounts["vat_base_purchase"] = self._calculate_vat_base_for_purchase_operation(amounts)
        amounts["vat_sum_purchase"] = self._calculate_vat_sum_for_purchase_operation(amounts)

        # Handle custom VAT adjustments
        self._apply_custom_vat_adjustments(invoice_vars, amounts)

        return amounts

    def _apply_custom_vat_adjustments(self, invoice_vars, amounts):
        """Apply custom VAT amount adjustments based on invoice VAT treatment."""
        if invoice_vars["custom_vat"] == 0:
            return

        vat_treatment_id = invoice_vars.get("invoice_vat_treatment_id")
        vat_treatment_record = vat_treatment_id
        if isinstance(vat_treatment_id, int):
            vat_treatment_record = self.env["kojto.finance.vat.treatment"].browse(vat_treatment_id)

        if (vat_treatment_record and
            vat_treatment_record.vat_treatment_type == kojto_finance_vat_treatment.VAT_TRTYPE_PARTIAL[0]):
            amounts["vat_sum_partial"] = invoice_vars["custom_vat_bgn"]
            amounts["vat_sum_partial_purchase"] = invoice_vars["custom_vat_bgn"]
        else:
            amounts["vat_sum"] = invoice_vars["custom_vat_bgn"]
            amounts["vat_sum_purchase"] = invoice_vars["custom_vat_bgn"]

    def _build_vat_operation_context(self, invoice_vars, content_vars):
        """Build context object for VAT operation formatting."""
        accounting_template = list(content_vars.values())[0]["accounting_template_id"]

        return {
            "operation_type": self._determine_operation_type(accounting_template),
            "doc_number": AJUR_DOC_MAPPINGS.get(invoice_vars["type"], ("", ""))[1],
            "doc_type": self._determine_document_type(content_vars),
            "template_name": accounting_template.template_type_id.name,
            "invoice_vars": invoice_vars,
        }

    def _determine_operation_type(self, accounting_template):
        """Determine operation type based on accounting template."""
        return "ДДСПК" if accounting_template.template_type_id.primary_type == "purchase" else "ДДСПР"

    def _determine_document_type(self, content_vars):
        """Determine document type based on VAT treatment."""
        return "01" if kojto_finance_vat_treatment.VAT_TRTYPE_SALE_WASTE_ART163A[0] in content_vars else "#"

    def _format_vat_book_operation_text(self, context, amounts):
        """Format the VAT book operation text."""
        iv = context["invoice_vars"]

        # Build base text parts
        txt_parts = [
            f"{context['operation_type']}@@",
            f"{iv['num']}#",
            f"{iv['issue_date']}#",
            f"{iv['arch_num']}##",
            f"{context['doc_number']}#0#",
            f"{context['template_name']}#",
            f"{context['doc_type']}@@",
            f"{iv['counterparty_client_number']}#",
            f"{iv['counterparty_name']}#",
            f"{iv['auto_eik_num']}#",
            f"{iv['auto_vat_num']}@@",
        ]

        # Add operation-specific parts
        if context["operation_type"] == "ДДСПК":
            txt_parts.extend([
                f"{amounts['vat_base_purchase']}#",
                f"{amounts['vat_sum_purchase']}#",
            ])

            txt_parts.extend(self._build_purchase_operation_parts(amounts))
        else:
            txt_parts.extend([
                f"{amounts['vat_base'] + amounts['vat_base_sale_waste_163a']}#",
                f"{amounts['vat_sum']}#",
            ])

            txt_parts.extend(self._build_sales_operation_parts(amounts))

        return "".join(txt_parts)

    def _calculate_vat_base_for_purchase_operation(self, amounts):
        """Calculate VAT base for purchase operation."""
        return (
            amounts['vat_base'] +
            amounts['vat_base_sale_waste_163a'] +
            amounts['vat_base_art140_art146_art173'] +
            amounts['vat_base_art21_2'] +
            amounts['vat_base_art69_21_2_non_eu'] +
            amounts['vat_base_exempt_deleveries'] +
            amounts['vat_base_intermediary_tripartie'] +
            amounts['vat_base_art53'] +
            amounts['vat_base_art28_1_2'] +
            amounts['vat_base_full9'] +
            amounts['vat_base_art82_2_5']
        )

    def _calculate_vat_sum_for_purchase_operation(self, amounts):
        """Calculate VAT sum for purchase operation."""
        return (
            amounts['vat_sum'] +
            amounts['vat_sum_art82_2_5'] +
            amounts['vat_sum_full9']
        )

    def _build_purchase_operation_parts(self, amounts):
        """Build text parts specific to purchase operations (ДДСПК)."""
        return [
            f"{amounts['vat_base_partial']}#",
            f"{amounts['vat_sum_partial']}#",
            f"{amounts['vat_base_none']}#",
            f"0#",
            f"0@@",
        ]

    def _build_sales_operation_parts(self, amounts):
        """Build text parts specific to sales operations (ДДСПР)."""
        return [
            f"{amounts['vat_base_art82_2_5']}#",
            f"{amounts['vat_sum_art82_2_5']}#",
            f"0#",
            f"{amounts['vat_base_full9']}#",
            f"{amounts['vat_sum_full9']}#",
            f"{amounts['vat_base_art28_1_2']}#",
            f"{amounts['vat_base_art53']}#",
            f"{amounts['vat_base_art140_art146_art173']}#",
            f"{amounts['vat_base_art21_2']}#",
            f"{amounts['vat_base_art69_21_2_non_eu']}#",
            f"{amounts['vat_base_exempt_deleveries']}#0#",
            f"{amounts['vat_base_intermediary_tripartie']}#",
            f"0#0#",
            f"{amounts['vat_base_art53']}#",
            f"{amounts['vat_base_intermediary_tripartie']}#",
            f"{amounts['vat_base_art21_2']}#",
            f"@@",
        ]

    def _render_account_structure_template(self, acc_row, invoice_vars, content_vars={}):
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

        debit_acc_suffix = replace_template_vars(debit_template, invoice_vars)
        debit_acc_suffix = replace_template_vars(debit_acc_suffix, content_vars)

        credit_acc_suffix = replace_template_vars(credit_template, invoice_vars)
        credit_acc_suffix = replace_template_vars(credit_acc_suffix, content_vars)

        return debit_acc_suffix, credit_acc_suffix

    def _calculate_acc_row_amounts_to_bgn(
        self,
        acc_row,
        content_vars,
        amount_ref="content_pre_vat_total",
    ):
        debit_amount_currency = 0 if not acc_row.debit_account_id.is_currency_account else content_vars[amount_ref]
        credit_amount_currency = 0 if not acc_row.credit_account_id.is_currency_account else content_vars[amount_ref]

        return debit_amount_currency, credit_amount_currency

    def _calculate_acc_row_qty(self, acc_row, content_vars):
        debit_qty = 0 if not acc_row.debit_account_id.is_warehouse_account else content_vars.get("content_quantity", 0)
        credit_qty = 0 if not acc_row.credit_account_id.is_warehouse_account else content_vars.get("content_quantity", 0)
        debit_unit = "" if not acc_row.debit_account_id.is_warehouse_account else content_vars.get("content_unit", "")
        credit_unit = "" if not acc_row.credit_account_id.is_warehouse_account else content_vars.get("content_unit", "")

        return debit_qty, credit_qty, debit_unit, credit_unit
