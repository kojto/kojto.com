from odoo import models, fields, api


class KojtosContractContents(models.Model):
    _name = "kojto.contract.contents"
    _description = "Kojto Contract Contents"
    _rec_name = "name"
    _order = "position asc, id asc"

    name = fields.Text(string="Description")
    position = fields.Char(string="№", size=5)

    contract_id = fields.Many2one("kojto.contracts", string="Contract", ondelete="cascade", required=True)
    currency_id = fields.Many2one("res.currency", string="", related="contract_id.currency_id", readonly=True)
    quantity = fields.Float(string="Quantity", digits=(16, 2))
    unit_id = fields.Many2one("kojto.base.units", string="Unit")
    unit_price = fields.Float(string="Unit Price", digits=(16, 5))
    pre_vat_total = fields.Float(string="Pre VAT total", compute="_compute_pre_vat_total", digits=(9, 2))

    vat_rate = fields.Float(string="VAT Rate (%)", digits=(9, 2), default=lambda self: self._default_vat_rate())
    vat_total = fields.Float(string="VAT", compute="compute_vat_total", digits=(9, 2))
    total_price = fields.Float(string="Total price", compute="compute_total_price", digits=(9, 2))

    @api.model
    def _default_vat_rate(self):
        contract_id = self._context.get("default_contract_id")
        if contract_id:
            contract = self.env["kojto.contracts"].browse(contract_id)
            return contract.contract_vat_rate if contract.contract_vat_rate is not None else 0.0
        return 0.0

    @api.onchange("contract_id")
    def _onchange_contract_id(self):
        if self.contract_id:
            self.vat_rate = self.contract_id.contract_vat_rate if self.contract_id.contract_vat_rate is not None else 0.0

    @api.depends("quantity", "unit_price")
    def _compute_pre_vat_total(self):
        for record in self:
            record.pre_vat_total = record.quantity * record.unit_price

    @api.depends("quantity", "unit_price", "vat_rate")
    def compute_vat_total(self):
        for record in self:
            pre_vat_total = record.quantity * record.unit_price
            if pre_vat_total and record.vat_rate is not None:
                record.vat_total = pre_vat_total * (record.vat_rate / 100)
            else:
                record.vat_total = 0.0
        return {}

    @api.depends("quantity", "unit_price", "vat_rate")
    def compute_total_price(self):
        for record in self:
            pre_vat_total = record.quantity * record.unit_price
            vat_total = pre_vat_total * (record.vat_rate / 100) if record.vat_rate is not None else 0.0
            record.total_price = pre_vat_total + vat_total
        return {}
