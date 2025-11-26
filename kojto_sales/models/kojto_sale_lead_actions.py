from odoo import models, fields

class KojtoSaleLeadAction(models.Model):
    _name = "kojto.sale.lead.action"
    _description = "Kojto Sale Lead Action"

    lead_id = fields.Many2one("kojto.sale.leads", string="Sale Lead", required=True, ondelete="cascade")
    date = fields.Datetime(string="When", default=fields.Datetime.now, required=True)
    contact_person = fields.Char(string="Who")
    channel = fields.Selection([
        ('email', 'Email'),
        ('phone', 'Phone'),
        ('meeting', 'Meeting'),
        ('online_meeting', 'Online Meeting'),
        ('phone_call', 'Phone Call'),
        ('sms', 'SMS'),
        ('whatsapp', 'Whatsapp'),
        ('telegram', 'Telegram'),
        ('viber', 'Viber'),
        ('skype', 'Skype'),
        ('other', 'Other')
    ], string="Channel")
    description = fields.Text(string="What was discussed")
