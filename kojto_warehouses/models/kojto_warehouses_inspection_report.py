from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class KojtoWarehousesInspectionReport(models.Model):
    _name = "kojto.warehouses.inspection.report"
    _description = "Warehouse Inspection Report"
    _rec_name = "name"
    _order = "name desc"
    _inherit = ["kojto.library.printable"]
    _report_ref = "kojto_warehouses.print_inspection_report"

    # Basic Information
    name = fields.Char(string="Protocol Number", required=True, copy=False, compute='_compute_name', store=True)
    active = fields.Boolean(default=True, string="Active")

    # Company Information
    company_id = fields.Many2one("kojto.contacts", string="Company", default=1, required=True, readonly=True)
    company_name_id = fields.Many2one("kojto.base.names", string="Name on document", domain="[('contact_id', '=', company_id)]")
    company_address_id = fields.Many2one("kojto.base.addresses", string="Address", domain="[('contact_id', '=', company_id)]")
    company_phone_id = fields.Many2one("kojto.base.phones", string="Phone", domain="[('contact_id', '=', company_id)]")
    company_email_id = fields.Many2one("kojto.base.emails", string="Emails", domain="[('contact_id', '=', company_id)]")

    batch_id = fields.Many2one("kojto.warehouses.batches", string="Batch", required=True, ondelete="cascade")
    counterparty_id = fields.Many2one(related="batch_id.counterparty_id", string="Manufacturer", ondelete="cascade")

    item_ids = fields.Many2many("kojto.warehouses.items", string="Items", required=True, domain="[('batch_id', '=', batch_id)]", context={'active_test': False})
    date_issued = fields.Date(string="Issued Date", required=True, default=fields.Date.today)
    inspected_by = fields.Many2one("res.users", string="Inspected By", required=True, default=lambda self: self.env.user)
    language_id = fields.Many2one('res.lang', string='Language', default=lambda self: self.env['res.lang']._lang_get(self.env.user.lang))
    pdf_attachment_id = fields.Many2one("ir.attachment", string="PDF Attachment", copy=False)

    # Inspection Parameters
    supplier_ok = fields.Boolean(string="Supplier OK")
    supplier_note = fields.Char(string="Supplier Note", default="No issues found on supplier")
    material_ok = fields.Boolean(string="Material OK")
    material_note = fields.Char(string="Material Note", default="No issues found on material")
    material_grade_ok = fields.Boolean(string="Material Grade OK")
    material_grade_note = fields.Char(string="Material Grade Note", default="No issues found on material grade")
    quantity_ok = fields.Boolean(string="Quantity OK")
    quantity_note = fields.Char(string="Quantity Note", default="No issues found on quantity")

    # Document Verification
    invoice_ok = fields.Boolean(string="Invoice OK")
    invoice_note = fields.Char(string="Invoice Note", default="No issues found on invoice")
    inspection_certificates_ok = fields.Boolean(string="Inspection Certificates OK")
    inspection_certificates_note = fields.Char(string="Inspection Certificates Note", default="No issues found on inspection certificates")
    test_reports_ok = fields.Boolean(string="Test Reports OK")
    test_reports_note = fields.Char(string="Test Reports Note", default="No issues found on test reports")
    declaration_ok = fields.Boolean(string="Declaration of Conformity OK")
    declaration_note = fields.Char(string="Declaration Note", default="No issues found on declaration")

    # Surface Inspection
    surface_defects_ok = fields.Boolean(string="Surface Defects OK")
    surface_defects_note = fields.Char(string="Surface Defects Note", default="No issues found on surface defects")

    # Status and Items
    status = fields.Selection([('draft', 'Draft'), ('pending', 'Pending'), ('confirmed', 'Confirmed'), ('rejected', 'Rejected')], string="Status", default='draft', required=True)
    notes = fields.Text(string="Additional Notes")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'company_id' in fields_list:
            company = self.env["kojto.contacts"].browse(1)
            if not company.exists():
                raise ValidationError(_("Company contact not found."))

            # Get the default language
            lang_id = self.env['res.lang']._lang_get(self.env.user.lang).id

            for model, field in [
                ("kojto.base.names", "company_name_id"),
                ("kojto.base.addresses", "company_address_id"),
                ("kojto.base.phones", "company_phone_id"),
                ("kojto.base.emails", "company_email_id"),
            ]:
                if field in fields_list:
                    # For names and addresses, try to find one matching the language first
                    if model in ['kojto.base.names', 'kojto.base.addresses']:
                        record = self.env[model].search([
                            ("contact_id", "=", company.id),
                            ("active", "=", True),
                            ("language_id", "=", lang_id)
                        ], limit=1)
                        if not record:
                            # If no record with matching language, get any active record
                            record = self.env[model].search([
                                ("contact_id", "=", company.id),
                                ("active", "=", True)
                            ], limit=1)
                    else:
                        # For phones and emails, just get the first active record
                        record = self.env[model].search([
                            ("contact_id", "=", company.id),
                            ("active", "=", True)
                        ], limit=1)
                    if record:
                        res[field] = record.id

        # Set default status to confirmed
        if 'status' in fields_list:
            res['status'] = 'confirmed'

        # Set all check fields to True by default
        check_fields = [
            'supplier_ok',
            'material_ok',
            'material_grade_ok',
            'quantity_ok',
            'invoice_ok',
            'inspection_certificates_ok',
            'test_reports_ok',
            'declaration_ok',
            'surface_defects_ok'
        ]
        for field in check_fields:
            if field in fields_list:
                res[field] = True

        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('batch_id') and not vals.get('item_ids'):
                # Get all items from the batch that have no parent_item_id and are not in another inspection report
                batch = self.env['kojto.warehouses.batches'].browse(vals['batch_id'])
                items = self.env['kojto.warehouses.items'].search([
                    ('batch_id', '=', batch.id),
                    ('parent_item_id', '=', False),
                    ('inspection_report_id', '=', False)
                ])
                if items:
                    vals['item_ids'] = [(6, 0, items.ids)]
        return super().create(vals_list)

    @api.constrains('item_ids')
    def _check_items_unique(self):
        for report in self:
            for item in report.item_ids:
                if item.inspection_report_id and item.inspection_report_id != report:
                    raise ValidationError(_(
                        "Item %s is already assigned to inspection report %s"
                    ) % (item.name, item.inspection_report_id.name))

    @api.depends('batch_id', 'batch_id.name')
    def _compute_name(self):
        for report in self:
            if report.batch_id:
                # Get the last inspection report number for this batch
                last_report = self.search([
                    ('batch_id', '=', report.batch_id.id),
                    ('id', '!=', report.id)
                ], order='name desc', limit=1)

                if last_report and last_report.name:
                    # Extract the number and increment it
                    try:
                        last_num = int(last_report.name.split('.')[-1])
                        new_num = str(last_num + 1).zfill(2)
                    except (ValueError, IndexError):
                        new_num = '01'
                else:
                    new_num = '01'

                # Format: BATCHNAME.IR.XX
                report.name = f"{report.batch_id.name}.IR.{new_num}"
            else:
                report.name = False

    def action_confirm(self):
        self.ensure_one()
        if not self.item_ids:
            raise ValidationError(_("Cannot confirm report without items."))
        self.status = 'confirmed'
        self.item_ids.write({'inspection_report_id': self.id})

    def action_reject(self):
        self.ensure_one()
        self.status = 'rejected'
        self.item_ids.write({'inspection_report_id': False})

    def action_draft(self):
        self.ensure_one()
        self.status = 'draft'
        self.item_ids.write({'inspection_report_id': False})

    def unlink(self):
        for report in self:
            if report.status != 'draft':
                raise ValidationError(_("Cannot delete confirmed or rejected reports."))
            report.item_ids.write({'inspection_report_id': False})
        return super().unlink()
