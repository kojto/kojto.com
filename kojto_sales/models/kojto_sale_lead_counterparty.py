from odoo import models, fields, api

class KojtoSaleLeadCounterparty(models.Model):
    _name = "kojto.sale.lead.counterparty"
    _description = "Kojto Sale Lead Counterparty"
    _order = "print_number desc"

    # Relational Fields
    sale_lead_id = fields.Many2one("kojto.sale.leads", string="Sale Lead", required=True, ondelete="cascade")
    counterparty_id = fields.Many2one("kojto.contacts", string="Counterparty", ondelete="set null")

    # Counterparty Details (Related Fields)
    counterparty_type = fields.Selection(related="counterparty_id.contact_type", string="Counterparty Type")
    registration_number = fields.Char(related="counterparty_id.registration_number", string="Registration Number")
    registration_number_type = fields.Char(related="counterparty_id.registration_number_type", string="Registration Number Type")
    bank_account_id = fields.Many2one("kojto.base.bank.accounts", string="Bank Account")
    name_id = fields.Many2one("kojto.base.names", string="Name on Document")
    address_id = fields.Many2one("kojto.base.addresses", string="Address")
    tax_number_id = fields.Many2one("kojto.base.tax.numbers", string="Tax Number")
    phone_id = fields.Many2one("kojto.base.phones", string="Phone")
    email_id = fields.Many2one("kojto.base.emails", string="Email")
    next_interaction_datetime = fields.Datetime(string="Next Interaction Date")
    next_interaction_description = fields.Char(string="Next Interaction Description")

    # Additional Fields
    counterparty_lead_comment = fields.Char(string="Comment")
    print_number = fields.Integer(string="Print Number", readonly=True)
    role = fields.Selection(
        [
            ("investor", "Investor"),
            ("client", "Client"),
            ("architect", "Architect"),
            ("consultant", "Consultant"),
            ("unknown", "Unknown"),
            ("competitor", "Competitor"),
            ("engineer", "Engineer"),
            ("main_contractor", "Main Contractor"),
            ("facade_contractor", "Facade Contractor"),
        ],
        string="Role",
        default="unknown",
    )

    @api.model
    def create(self, vals):
        # Handle both single dict and list of dicts (batch create)
        if isinstance(vals, dict):
            if 'role' not in vals or not vals['role']:
                vals['role'] = 'unknown'
            return super().create(vals)
        elif isinstance(vals, list):
            for v in vals:
                if 'role' not in v or not v['role']:
                    v['role'] = 'unknown'
            return super().create(vals)
        return super().create(vals)

    def write(self, vals):
        # Ensure role field has a valid value when updating
        if 'role' in vals and not vals['role']:
            vals['role'] = 'unknown'
        return super().write(vals)
