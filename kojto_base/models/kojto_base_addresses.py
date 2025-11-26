from odoo import models, fields, api

class KojtoBaseAddresses(models.Model):
    _name = "kojto.base.addresses"
    _description = "Kojto Addresses"
    _rec_name = "name"
    _order = "address desc"

    name = fields.Char(string="Name", compute="get_name")
    address = fields.Char(string="Address")
    city = fields.Char(string="City")
    country_id = fields.Many2one("res.country", string="Country")
    language_id = fields.Many2one("res.lang", string="Language", default=lambda self: self.env.ref("base.lang_en").id)

    postal_code = fields.Char(string="Postal Code")
    region = fields.Char(string="Region")
    active = fields.Boolean(string="Is Active", default=True)

    @api.depends("city", "postal_code", "country_id", "address", "language_id")
    def get_name(self):
        for record in self:
            parts = []
            if record.address:
                parts.append(record.address)
            if record.postal_code or record.city:
                city_part = f"{record.postal_code or ''} {record.city or ''}".strip()
                if city_part:
                    parts.append(city_part)
            if record.country_id and record.country_id.name:
                # Get translated country name based on the address language
                country_name = record.country_id.with_context(lang=record.language_id.code).name if record.language_id else record.country_id.name
                parts.append(country_name)

            record.name = ", ".join(parts) if parts else ""
