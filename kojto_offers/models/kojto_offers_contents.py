from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class KojtoOffersContents(models.Model):
    _name = "kojto.offer.contents"
    _description = "Kojto Docs Offer Contents"
    _rec_name = "name"
    _order = "position asc, id asc"

    name = fields.Char(string="Description")
    position = fields.Char(string="№", size=5)
    offer_id = fields.Many2one("kojto.offers", string="Offer", ondelete="cascade")
    currency_id = fields.Many2one("res.currency", string="", related="offer_id.currency_id", store=False, readonly=True)
    content_elements = fields.One2many("kojto.offer.content.elements", "content_id", string="Content Elements")
    content_elements_count = fields.Integer(string="Content Elements Count", compute="compute_content_element_count")
    quantity = fields.Float(string="Quantity", digits=(16, 2))
    estimation_quantity = fields.Float(string="Est. Qty", digits=(16, 2), default=1)
    unit_id = fields.Many2one("kojto.base.units", string="Unit")
    unit_price = fields.Float(string="Unit Price", digits=(16, 2))
    pre_vat_total = fields.Float(string="Pre VAT total", compute="compute_pre_vat_total", store=False, digits=(9, 2))
    vat_rate = fields.Float(string="VAT Rate (%)", digits=(9, 2), default=lambda self: self._default_vat_rate())

    custom_vat = fields.Float(string="Custom Vat", digits=(9, 2), default=None)
    vat_total = fields.Float(string="VAT", compute="compute_vat_total", digits=(9, 2))
    total_price = fields.Float(string="Total price", compute="compute_total_price", digits=(9, 2))

    est_total_price = fields.Float(string="Est. Total Price", compute="compute_est_elements_total", digits=(16, 2))
    est_unit_price = fields.Float(string="Est. Unit Price", compute="compute_est_unit_price", digits=(16, 2))
    est_total_contribution_margin = fields.Float(string="C-Margin Total", compute="compute_est_total_contribution_margin", digits=(16, 2))
    est_total_contribution_margin_percent = fields.Float(string="C-Margin (%)", compute="compute_est_total_contribution_margin_percent", digits=(16, 2))

    @api.model
    def _default_vat_rate(self):
        offer_id = self._context.get("default_offer_id")
        if offer_id:
            offer = self.env["kojto.offers"].browse(offer_id)
            return offer.offer_vat_rate if offer.offer_vat_rate is not None else 0.0
        return 0.0

    @api.onchange("offer_id")
    def _onchange_offer_id(self):
        if self.offer_id and self.offer_id.offer_vat_rate:
            self.vat_rate = self.offer_id.offer_vat_rate

    @api.onchange('custom_vat')
    def _onchange_custom_vat(self):
        if self.custom_vat is not None:
            if self.custom_vat == -1:
                # Set vat_rate to the offer's vat_rate if custom_vat is -1
                if self.offer_id and self.offer_id.offer_vat_rate is not None:
                    self.vat_rate = self.offer_id.offer_vat_rate
                else:
                    self.vat_rate = 0.0
            else:
                pre_vat_total = self.quantity * self.unit_price
                if pre_vat_total:
                    self.vat_rate = (self.custom_vat / pre_vat_total) * 100
                else:
                    self.vat_rate = 0.0
        else:
            if self.offer_id and self.offer_id.offer_vat_rate is not None:
                self.vat_rate = self.offer_id.offer_vat_rate

    @api.depends("content_elements.total_price")
    def compute_est_elements_total(self):
        for record in self:
            record.est_total_price = sum(element.total_price for element in record.content_elements if element.total_price)
        return {}

    @api.depends("est_total_price", "quantity", "estimation_quantity")
    def compute_est_unit_price(self):
        for record in self:
            if record.est_total_price:
                # If estimation_quantity > 0, use it; otherwise use quantity
                denominator = record.estimation_quantity if record.estimation_quantity > 0 else record.quantity
                if denominator:
                    record.est_unit_price = record.est_total_price / denominator
                else:
                    record.est_unit_price = 0.0
            else:
                record.est_unit_price = 0.0
        return {}

    @api.depends("content_elements.contribution_margin")
    def compute_est_total_contribution_margin(self):
        for record in self:
            record.est_total_contribution_margin = sum(element.contribution_margin for element in record.content_elements if element.contribution_margin)
        return {}

    @api.depends("est_total_contribution_margin", "est_total_price", "content_elements")
    def compute_est_total_contribution_margin_percent(self):
        for record in self:
            record.est_total_contribution_margin_percent = record.est_total_contribution_margin / record.est_total_price * 100 if record.est_total_price else 0.0
        return {}

    @api.depends("content_elements")
    def compute_content_element_count(self):
        for record in self:
            record.content_elements_count = len(record.content_elements)
        return {}

    @api.onchange("quantity", "unit_price")
    def compute_pre_vat_total(self):
        for record in self:
            record.pre_vat_total = record.quantity * record.unit_price
        return {}

    @api.onchange("quantity", "pre_vat_total")
    def compute_unit_price(self):
        for record in self:
            if record.quantity:
                record.unit_price = record.pre_vat_total / record.quantity
        return {}

    @api.depends('quantity', 'unit_price', 'vat_rate', 'custom_vat', 'name', 'position', 'offer_id', 'unit_id', 'content_elements', 'content_elements_count')
    def compute_vat_total(self):
        for record in self:
            pre_vat_total = record.quantity * record.unit_price
            if record.custom_vat is not None and record.custom_vat != -1:
                record.vat_total = record.custom_vat
            else:
                record.vat_total = pre_vat_total * (record.vat_rate / 100.0)
        return {}

    @api.depends("pre_vat_total", "vat_rate")
    def compute_total_price(self):
        for record in self:
            record.total_price = record.pre_vat_total + record.vat_total
        return {}

    @api.constrains('custom_vat')
    def _check_custom_vat(self):
        for rec in self:
            if rec.custom_vat is not None and rec.custom_vat < -1:
                raise ValidationError(_('Custom VAT must be -1, 0, or a positive value.'))

    def open_content_elements(self):
        self.ensure_one()

        # Build quantity string with estimation quantity if available
        quantity_str = f"{self.quantity} qty" if self.quantity else ""
        if self.estimation_quantity:
            quantity_str += f" / {self.estimation_quantity} est. qty"
        unit_str = self.unit_id.name if self.unit_id else ""
        quantity_unit = f"({quantity_str} / {unit_str})" if quantity_str and unit_str else f"({quantity_str})" if quantity_str else f"({unit_str})" if unit_str else ""

        # Build the window name
        if self.name:
            name = f"Elements of Content - {self.position} {self.name} {quantity_unit}"
        elif self.position:
            name = f"Elements of Content - {self.position} {quantity_unit}"
        elif quantity_str or unit_str:
            name = f"Elements of Content {quantity_unit}"
        else:
            name = "Elements of Content"

        return {
            "type": "ir.actions.act_window",
            "res_model": "kojto.offer.content.elements",
            "view_mode": "list,form",
            "domain": [("content_id", "=", self.id)],
            "context": {"default_content_id": self.id},
            "target": "new",
            "name": name,
        }

    def copy(self, default=None):
        default = dict(default or {})

        # Add "(Copy)" to the name if not already specified
        if 'name' not in default:
            default['name'] = f"{self.name}" if self.name else "-"

        # Create the copy of the offer content
        copied_content = super().copy(default)

        # Copy all associated content elements
        for element in self.content_elements:
            element.copy({
                'content_id': copied_content.id,
                'name': f"{element.name}" if element.name else "-",
            })

        return copied_content


