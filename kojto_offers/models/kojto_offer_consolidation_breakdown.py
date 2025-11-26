from odoo import models, fields, api, tools, _

class KojtoOfferConsolidationBreakdown(models.Model):
    _name = "kojto.offer.consolidation.breakdown"
    _description = "Kojto Offer Consolidation Breakdown"
    _auto = False  # This makes it a PostgreSQL view
    _order = "position asc"

    offer_id = fields.Many2one("kojto.offers", string="Offer")
    name = fields.Char(string="Consolidation Name")
    unit_id = fields.Many2one("kojto.base.units", string="Unit")
    quantity = fields.Float(string="Quantity")
    avg_unit_price = fields.Float(string="Avg. Unit Price")
    currency_id = fields.Many2one("res.currency", string="Currency")
    total_price_with_all_surcharges = fields.Float(string="Est. Total Price")
    total_contribution_margin = fields.Float(string="C-Margin")
    total_contribution_margin_percent = fields.Float(string="C-Margin (%)", compute="compute_total_contribution_margin_percent", store=False)
    position = fields.Char(string="№")


    def init(self):
        # Drop the view if it exists
        tools.drop_view_if_exists(self.env.cr, self._table)

        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    ROW_NUMBER() OVER () as id,
                    o.id as offer_id,
                    ci.name,
                    ci.unit_id,
                    SUM(CASE
                        WHEN oc.estimation_quantity IS NULL OR oc.estimation_quantity = 0
                        THEN ce.quantity
                        ELSE ce.quantity * oc.quantity / oc.estimation_quantity
                    END) as quantity,
                    CASE
                        WHEN SUM(CASE
                            WHEN oc.estimation_quantity IS NULL OR oc.estimation_quantity = 0
                            THEN ce.quantity
                            ELSE ce.quantity * oc.quantity / oc.estimation_quantity
                        END) > 0
                        THEN SUM(ce.unit_price * ce.quantity * (1 + COALESCE(surcharges_total.surcharge_total, 0) / 100.0)) / SUM(CASE
                            WHEN oc.estimation_quantity IS NULL OR oc.estimation_quantity = 0
                            THEN ce.quantity
                            ELSE ce.quantity * oc.quantity / oc.estimation_quantity
                        END)
                        ELSE 0
                    END as avg_unit_price,
                    o.currency_id,
                    SUM(ce.unit_price * ce.quantity * (1 + COALESCE(surcharges_total.surcharge_total, 0) / 100.0)) as total_price_with_all_surcharges,
                    SUM(ce.unit_price * ce.quantity * (ci.contribution_margin_percent / 100.0) + ce.unit_price * ce.quantity * (COALESCE(surcharges_total.surcharge_total, 0) / 100.0)) as total_contribution_margin,
                    CASE
                        WHEN SUM(ce.unit_price * ce.quantity * (1 + COALESCE(surcharges_total.surcharge_total, 0) / 100.0)) > 0
                        THEN (SUM(ce.unit_price * ce.quantity * (ci.contribution_margin_percent / 100.0) + ce.unit_price * ce.quantity * (COALESCE(surcharges_total.surcharge_total, 0) / 100.0)) / SUM(ce.unit_price * ce.quantity * (1 + COALESCE(surcharges_total.surcharge_total, 0) / 100.0))) * 100
                        ELSE 0
                    END as total_contribution_margin_percent,
                    LPAD(ROW_NUMBER() OVER (PARTITION BY o.id ORDER BY ci.name ASC)::text, 2, '0') as position
                FROM kojto_offers o
                JOIN kojto_offer_contents oc ON oc.offer_id = o.id
                JOIN kojto_offer_content_elements ce ON ce.content_id = oc.id
                JOIN kojto_offer_consolidation_ids ci ON ci.id = ce.consolidation_id
                LEFT JOIN (
                    SELECT
                        ci_id.id as consolidation_id,
                        SUM(s.surcharge) as surcharge_total
                    FROM kojto_offer_consolidation_ids ci_id
                    JOIN kojto_offer_consolidation_ids_kojto_offer_surcharges_rel rel ON rel.kojto_offer_consolidation_ids_id = ci_id.id
                    JOIN kojto_offer_surcharges s ON s.id = rel.kojto_offer_surcharges_id
                    GROUP BY ci_id.id
                ) surcharges_total ON surcharges_total.consolidation_id = ci.id
                GROUP BY o.id, ci.name, ci.unit_id, o.currency_id
                ORDER BY o.id, ci.name ASC
            )
        """ % self._table)

    @api.depends("total_contribution_margin", "total_price_with_all_surcharges")
    def compute_total_contribution_margin_percent(self):
        for record in self:
            if record.total_price_with_all_surcharges and record.total_price_with_all_surcharges > 0:
                record.total_contribution_margin_percent = (record.total_contribution_margin / record.total_price_with_all_surcharges) * 100
            else:
                record.total_contribution_margin_percent = 0.0
        return {}
