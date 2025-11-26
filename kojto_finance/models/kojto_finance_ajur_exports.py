# kojto_finance/models/kojto_finance_ajur_exports.py
from odoo import models, api, fields
from odoo.exceptions import UserError

AJUR_CURRENCY_NAME_MAPPINGS = {
    "BGN": "Български лев",
    "CHF": "Швейцарски франк",
    "EUR": "Евро",
    "GBP": "Британска лира",
    "ILS": "Израелски шекел",
    "USD": "Щатски долар",
}

AJUR_DOC_MAPPINGS = {
    "invoice": ("Ф-ра", "1"),
    "debit_note": ("ДИ", "2"),
    "credit_note": ("КИ", "3"),
    "insurance_policy": ("ЗП", "4"),
}

AJUR_TRANSACTION_TYPE_MAPPINGS = {
    ("incoming", "cash"): "ПКО",
    ("outgoing", "cash"): "РКО",
    ("incoming", "bank"): "БИ",
    ("outgoing", "bank"): "БИ",
}


class KojtoFinanceExportSelectionToAjur(models.TransientModel):
    _name = "kojto.finance.exportselectiontoajur"
    _description = "Kojto Finance Export Selection To Ajur"

    def action_export_to_ajur(self):
        raise NotImplementedError("This method should be implemented by the child class")

    def _get_accountant_id(self):
        current_user = self.env.user

        # Search for employee record
        employee = self.env["kojto.hr.employees"].search([("user_id", "=", current_user.id)], limit=1)

        if not employee:
            raise UserError("No employee record found for the current user. Please contact your administrator to set up your employee record.")

        # Check if user_id_accountant is properly set (not None, not empty string, not just whitespace)
        accountant_id = employee.user_id_accountant

        if not accountant_id or (isinstance(accountant_id, str) and not accountant_id.strip()):
            raise UserError(f"Employee '{employee.name}' does not have a valid accountant ID set. Please contact your administrator to set the 'Accountant User ID' field.")

        result = accountant_id.strip() if isinstance(accountant_id, str) else str(accountant_id)
        return result
