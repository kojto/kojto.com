from odoo import models, fields, api
import re

class KojtoSaleLeads(models.Model):
    _name = "kojto.sale.leads"
    _description = "Kojto Sale Leads"
    _rec_name = "name"
    _order = "date_start desc, name desc"

    # General Information
    name = fields.Char(string="Sale Lead Nr", required=True, readonly=True, default=lambda self: self.generate_next_consecutive_number())
    subject = fields.Char(string="Subject", default="Laser Welded Profiles")
    active = fields.Boolean(string="Active", default=True)
    status = fields.Selection([
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('qualified', 'Qualified'),
        ('proposal_sent', 'Proposal Sent'),
        ('negotiation', 'Negotiation'),
        ('won', 'Won'),
        ('lost', 'Lost'),
        ('cancelled', 'Cancelled')
    ], string="Status", default='new', required=True)
    date_start = fields.Date(string="Start Date", default=fields.Date.today, required=True)
    date_execution = fields.Date(string="Execution Date")

    # Project Information
    project_name = fields.Char(string="Project Name", default="Unknown Project")
    project_address = fields.Char(string="Project Address")
    project_city = fields.Char(string="Project City")
    project_country_id = fields.Many2one("res.country", string="Project Country")
    repr_html_counterparties = fields.Html(compute="compute_html_counterparties", string="Counterparties", store=True)
    expected_project_quantity = fields.Float(string="Quantity", digits=(16, 2), required=True)
    project_unit_id = fields.Many2one("kojto.base.units", string="Unit", default=lambda self: self.env["kojto.base.units"].search([("name", "=", "kg")], limit=1).id)
    expected_project_value = fields.Float(string="Price", digits=(9, 2))
    project_currency_id = fields.Many2one("res.currency", string="Currency", default=lambda self: self.env.ref("base.EUR").id, required=True)

    # Relational Fields
    counterparty_ids = fields.One2many("kojto.sale.lead.counterparty", "sale_lead_id", string="Counterparties")
    content_ids = fields.One2many("kojto.sale.lead.content", "sale_lead_id", string="Contents")
    action_ids = fields.One2many("kojto.sale.lead.action", "lead_id", string="Actions")
    offer_ids = fields.Many2many("kojto.offers", string="Offers")
    attachment_ids = fields.Many2many("ir.attachment", string="Attachments")
    description = fields.Text(string="Description")

    last_sales_interaction_datetime = fields.Datetime(string="Last Interaction", compute="_compute_last_sales_interaction_datetime")
    next_sales_interaction_datetime = fields.Datetime(string="Next Interaction", compute="_compute_next_sales_interaction_datetime")

    @api.model
    def _default_company_id(self):
        contact = self.env["kojto.contacts"].search([("res_company_id", "=", self.env.company.id)], limit=1)
        return contact.id if contact else False

    @api.depends("counterparty_ids")
    def compute_html_counterparties(self):
        for record in self:
            counterparties = record.counterparty_ids.mapped("counterparty_id.name")
            if counterparties:
                record.repr_html_counterparties = "<br/>".join(counterparties)
            else:
                record.repr_html_counterparties = "No Counterparties"
        return {}

    @api.model
    def generate_next_consecutive_number(self):
        try:
            largest_number = self.env["kojto.sale.leads"].search([], order="name desc", limit=1)
            if largest_number:
                numeric_part_match = re.search(r"\d+$", largest_number.name)
                next_consecutive_number = int(numeric_part_match.group()) + 1 if numeric_part_match else 1
            else:
                next_consecutive_number = 1
            return str(next_consecutive_number).zfill(5)
        except Exception as e:
            raise ValueError(f"Failed to generate next number: {str(e)}")

    @api.depends("counterparty_ids", "counterparty_ids.next_interaction_datetime")
    def _compute_next_sales_interaction_datetime(self):
        for record in self:
            next_interaction = False
            current_datetime = datetime.now()

            # Check all counterparties for their next interaction datetime
            if record.counterparty_ids:
                future_interactions = []
                for counterparty in record.counterparty_ids:
                    if hasattr(counterparty, 'next_interaction_datetime') and counterparty.next_interaction_datetime:
                        if counterparty.next_interaction_datetime > current_datetime:
                            future_interactions.append(counterparty.next_interaction_datetime)

                # Select the closest (earliest) future interaction
                if future_interactions:
                    next_interaction = min(future_interactions)

            record.next_sales_interaction_datetime = next_interaction

    @api.depends("action_ids", "action_ids.date")
    def _compute_last_sales_interaction_datetime(self):
        for record in self:
            last_interaction = False

            # Check all actions for this sale lead
            if record.action_ids:
                # Find the most recent action date
                action_dates = [action.date for action in record.action_ids if action.date]
                if action_dates:
                    last_interaction = max(action_dates)

            record.last_sales_interaction_datetime = last_interaction
