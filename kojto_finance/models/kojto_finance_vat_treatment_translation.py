# kojto_finance/models/kojto_finance_vat_treatment_translation.py
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class KojtoFinanceVatTreatmentTranslation(models.Model):
    _name = "kojto.finance.vat.treatment.translation"
    _description = "Kojto Base Vat Treatment Translations"
    _rec_name = "name"

    treatment_id = fields.Many2one("kojto.finance.vat.treatment", string="VAT Treatment", required=True, ondelete="cascade")
    language_id = fields.Many2one("res.lang", string="Language", default=lambda self: self.env.ref("base.lang_en").id, required=True)
    name = fields.Char(string="Name", required=True)
    description = fields.Char(string="Description")

    _sql_constraints = [("unique_treatment_language", "unique(treatment_id, language_id)", "Only one translation per language is allowed for each VAT treatment!")]
