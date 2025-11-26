# kojto_finance/models/kojto_finance_vat_treatment.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

VAT_TRTYPE_NONE = ("no_vat", "No VAT")
VAT_TRTYPE_FULL = ("full_vat", "Full VAT")
VAT_TRTYPE_PARTIAL = ("partial_vat", "Partial VAT")
VAT_TRTYPE_ART82_2_5 = ("art82_2_5_vat", "VAT for deliveries Article 82 2 5")
VAT_TRTYPE_FULL9 = ("full9_vat", "Full VAT deduction 9%")
VAT_TRTYPE_OUTSIDE_EU_ART28_1_2 = ("outside_eu_art28_1_2_vat", "VAT for trades outside EU Article 28 1 2")
VAT_TRTYPE_INSIDE_EU_ART53 = ("inside_eu_art53_vat", "VAT for trades inside EU Article 53")
VAT_TRTYPE_ART140_ART146_ART173 = ("art140_art146_art173_vat", "VAT for trades inside EU Article 140 146 173")
VAT_TRTYPE_ART21_2 = ("art21_2_vat", "VAT for trades inside EU Article 21 2")
VAT_TRTYPE_ART69_21_2_NON_EU = ("art69_21_2_vat_non_eu", "VAT for trades outside EU Article 69 2 / 21 2")
VAT_TRTYPE_EXEMPT_DELEVERIES = ("exempt_deleveries_vat", "VAT for Exempt Deleveries")
VAT_TRTYPE_INTERMEDIARY_TRIPARTIE = ("intermediary_tripartie_vat", "VAT for Intermediary Tripartie")
VAT_TRTYPE_SALE_WASTE_ART163A = ("sale_waste_art163a_vat", "VAT for Selling Waste Article 163a")
VAT_TRTYPE_SKIP_VAT = ("skip_vat", "Skip VAT")

_vat_tr_type_choices = [
    VAT_TRTYPE_FULL,
    VAT_TRTYPE_NONE,
    VAT_TRTYPE_PARTIAL,
    VAT_TRTYPE_ART82_2_5,
    VAT_TRTYPE_FULL9,
    VAT_TRTYPE_OUTSIDE_EU_ART28_1_2,
    VAT_TRTYPE_INSIDE_EU_ART53,
    VAT_TRTYPE_ART140_ART146_ART173,
    VAT_TRTYPE_ART21_2,
    VAT_TRTYPE_ART69_21_2_NON_EU,
    VAT_TRTYPE_EXEMPT_DELEVERIES,
    VAT_TRTYPE_INTERMEDIARY_TRIPARTIE,
    VAT_TRTYPE_SALE_WASTE_ART163A,
    VAT_TRTYPE_SKIP_VAT,
]

VAT_RATES_BY_TYPE = {
    VAT_TRTYPE_FULL[0]: 20,
    VAT_TRTYPE_NONE[0]: 0,
    VAT_TRTYPE_PARTIAL[0]: 20,
    VAT_TRTYPE_ART82_2_5[0]: 20,
    VAT_TRTYPE_FULL9[0]: 9,
}

class KojtoFinanceVatTreatment(models.Model):
    _name = "kojto.finance.vat.treatment"
    _description = "Kojto Finance Vat Treatment"
    _rec_name = "display_name"
    _order = "code"

    code = fields.Char(string="Code", required=True)
    vat_in_out_type = fields.Selection(string="In/Out", selection=[("incoming", "Incoming"), ("outgoing", "Outgoing")], required=True)
    translation_ids = fields.One2many("kojto.finance.vat.treatment.translation", "treatment_id", string="Translations")
    all_translations = fields.Char(string="Translations", compute="_compute_all_translations", store=False)
    display_name = fields.Char(string="Display Name", compute="_compute_display_name", store=True)
    vat_treatment_type = fields.Selection(string="VAT treatment type", selection=_vat_tr_type_choices, default=VAT_TRTYPE_FULL[0], required=True,)
    accounting_ops_ids = fields.Many2many("kojto.finance.accounting.ops", string="Accounting Operations")

    @api.constrains("code")
    def _check_unique_code(self):
        for record in self:
            if self.search([("code", "=", record.code), ("id", "!=", record.id)]):
                raise ValidationError("The Code must be unique!")

    def _compute_all_translations(self):
        for record in self:
            record.all_translations = ""

            if not record.translation_ids:
                continue

            record.all_translations = " | ".join(f"{t.language_id.code}: {t.description}" for t in record.translation_ids)


    @api.depends("code", "translation_ids", "vat_treatment_type")
    def _compute_display_name(self):
        for record in self:
            vat_treatment_type = next(filter(lambda t: t[0] == record.vat_treatment_type, _vat_tr_type_choices), None)
            record.display_name = f"{record.code} - {vat_treatment_type[1]}"
        return {}


    def compute_display_name(self):
        #DELETE after migration
        for record in self:
            vat_treatment_type = next(filter(lambda t: t[0] == record.vat_treatment_type, _vat_tr_type_choices), None)
            record.display_name = f"{record.code} - {vat_treatment_type[1]}"
        return {}

    def get_translated_name(self, language_code=None):
        """Get the translated description for the VAT treatment based on language code.
        If no translation is found, returns the original display_name.
        """
        self.ensure_one()

        if not language_code:
            language_code = self.env.context.get('lang', 'en_US')

        # Find translation for the specified language
        translation = self.translation_ids.filtered(lambda t: t.language_id.code == language_code)

        if translation:
            return translation[0].description

        # If no translation found, return the original display_name
        return self.display_name
