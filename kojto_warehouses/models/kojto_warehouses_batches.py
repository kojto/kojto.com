from odoo import api, models, fields, exceptions, _
from odoo.exceptions import ValidationError
from collections import Counter
from ..utils.kojto_warehouses_name_generator import get_temp_name, get_final_name, BATCH_PREFIXES

class KojtoWarehousesBatches(models.Model):
    _name = "kojto.warehouses.batches"
    _description = "Warehouse Batches"
    _rec_name = "name"
    _order = "name desc"

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Batch name must be unique.'),
        ('sheet_thickness_required', 'CHECK (batch_type != \'sheet\' OR thickness IS NOT NULL)', 'Sheet batch needs thickness.'),
        ('bar_profile_required', 'CHECK (batch_type != \'bar\' OR profile_id IS NOT NULL)', 'Bar batch needs profile.')
    ]

    name = fields.Char("Name", required=True, copy=False, index=True, default=lambda self: get_temp_name(self._context.get('batch_type', 'sheet'), BATCH_PREFIXES, 'BCH'))
    active = fields.Boolean(string="Is Active", compute="compute_active", store=True, search="_search_active")


    batch_properties_ids = fields.One2many("kojto.warehouses.batch.properties", "batch_id", string="Batch Properties")
    counterparty_id = fields.Many2one("kojto.contacts", string="Manufacturer", help="Manufacturer of the batch")
    name_secondary = fields.Char("Secondary Name", copy=False)
    batch_summary = fields.Text(string="Batch Summary", compute="_compute_batch_summary")
    description = fields.Text(string="Description")

    store_id = fields.Many2one("kojto.base.stores", string="Store", index=True)
    batch_type = fields.Selection([('sheet', 'Sheet'), ('bar', 'Bar'), ('part', 'Part')], string="Type", required=True, default='sheet', index=True)
    date_issue = fields.Date(string="Issue Date", default=fields.Date.today)

    # from accounting
    invoice_id = fields.Many2one("kojto.finance.invoices", string="Invoice")
    invoice_content_id = fields.Many2one("kojto.finance.invoice.contents", string="Invoice Content")
    subcode_id = fields.Many2one("kojto.commission.subcodes", related="invoice_content_id.subcode_id", string="Subcode")
    accounting_identifier_id = fields.Many2one("kojto.finance.accounting.identifiers", string="Accounting Identifier")
    accounting_identifier_domain = fields.Char(string="Accounting Identifier Domain", compute="_compute_accounting_identifier_domain", store=False)
    unit_id = fields.Many2one("kojto.base.units", string="Unit", related="accounting_identifier_id.unit_id")

    current_batch_quantity = fields.Float(string="Current Quantity", compute="_compute_current_batch_quantity")
    current_batch_value = fields.Float(string="Current Value (BGN)", compute="_compute_current_batch_value", store=True)

    items_ids = fields.One2many("kojto.warehouses.items", "batch_id", string="Items", context={'active_test': False})
    certificate_ids = fields.One2many("kojto.warehouses.certificates", "batch_id", string="Attachments")
    inspection_report_ids = fields.One2many("kojto.warehouses.inspection.report", "batch_id", string="Inspection Reports")
    repr_attachments = fields.Char(string="Attachments", compute="_compute_single_attachment")
    transaction_ids = fields.One2many("kojto.warehouses.transactions", "batch_id", string="Transactions")

    material_id = fields.Many2one("kojto.base.material.grades", string="Material")
    profile_id = fields.Many2one("kojto.warehouses.profile.shapes", string="Profile")
    thickness = fields.Float(string="Thickness (mm)", default=10.0)
    part_type = fields.Selection([('common', 'Common'), ('fastener', 'Fastener'), ('package', 'Package'), ('other', 'Other')], string="Part Type", default='common')

    unit_price = fields.Float(string="Unit Price", digits=(16, 2), default=1.0)
    unit_price_conversion_rate = fields.Float(string="Conversion Rate", digits=(16, 4), default=1.0)
    unit_price_converted = fields.Float(string="Unit Price (BGN)", compute="_compute_unit_price_converted")

    @api.constrains('name')
    def _check_name_unique(self):
        for record in self:
            if record.name:
                existing = self.search([
                    ('name', '=', record.name),
                    ('id', '!=', record.id)
                ], limit=1)
                if existing:
                    raise ValidationError(_("A batch with name '%s' already exists.") % record.name)

    @api.depends('unit_price', 'unit_price_conversion_rate')
    def _compute_unit_price_converted(self):
        for record in self:
            record.unit_price_converted = record.unit_price * (record.unit_price_conversion_rate or 1.0)

    @api.depends('invoice_content_id', 'invoice_content_id.identifier_id')
    def _compute_accounting_identifier_domain(self):
        """Compute domain for accounting_identifier_id based on invoice_content_id."""
        for record in self:
            if record.invoice_content_id and record.invoice_content_id.identifier_id:
                # Filter to only show the identifier from invoice content
                record.accounting_identifier_domain = str([('id', '=', record.invoice_content_id.identifier_id.id)])
            else:
                # Show all active identifiers
                record.accounting_identifier_domain = str([('active', '=', True)])

    @api.depends('items_ids', 'items_ids.name', 'items_ids.item_type', 'items_ids.weight', 'items_ids.length', 'items_ids.width',
                 'material_id', 'profile_id', 'thickness', 'part_type', 'current_batch_quantity', 'unit_id')
    def _compute_batch_summary(self):
        for batch in self:
            if not batch.items_ids:
                batch.batch_summary = ""
                continue

            method = getattr(self, f"_compute_summary_{batch.batch_type}", lambda b: "")
            batch.batch_summary = method(batch)

    @api.depends('certificate_ids', 'certificate_ids.name', 'certificate_ids.certificate_type')
    def _compute_single_attachment(self):
        for record in self:
            if not record.certificate_ids:
                record.repr_attachments = ""
                continue

            cert_counts = Counter(cert.certificate_type for cert in record.certificate_ids)
            summary_parts = [f"{count} {cert_type}" for cert_type, count in cert_counts.items()]
            record.repr_attachments = ", ".join(summary_parts)

    @api.depends('items_ids', 'items_ids.current_item_quantity')
    def _compute_current_batch_quantity(self):
        """Compute current quantity based on items' current quantities only."""
        for batch in self:
            batch.current_batch_quantity = sum(item.current_item_quantity for item in batch.items_ids)

    @api.depends('current_batch_quantity')
    def compute_active(self):
        """Compute active status for batches. Can be called directly from outside."""
        for rec in self:
            rec.active = (rec.current_batch_quantity > 0)
        return {}

    @api.depends('current_batch_quantity', 'unit_price_converted')
    def _compute_current_batch_value(self):
        for batch in self:
            batch.current_batch_value = batch.current_batch_quantity * batch.unit_price_converted

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('batch_type') == 'sheet' and not vals.get('thickness'):
                raise ValidationError(_("Sheet batch needs thickness."))
            if vals.get('batch_type') == 'bar' and not vals.get('profile_id'):
                raise ValidationError(_("Bar batch needs profile."))

        batches = super().create(vals_list)
        for batch in batches:
            batch.write({'name': get_final_name(batch.id, batch.batch_type, BATCH_PREFIXES, 'BCH')})
        return batches

    def write(self, vals):
        """Write method for batches. Odoo automatically handles recomputation of computed fields."""
        return super().write(vals)

    def _generate_items(self, count, length=0, width=0, weight=0):
        """Generate a specified number of items for this batch with given dimensions."""
        self.ensure_one()

        # Validate that required dimensions are provided based on batch type
        if self.batch_type == 'sheet':
            if not length or not width:
                raise ValidationError(_("Sheet items require both length and width to be specified."))
        elif self.batch_type == 'bar':
            if not length:
                raise ValidationError(_("Bar items require length to be specified."))
        elif self.batch_type == 'part':
            if not weight:
                raise ValidationError(_("Part items require weight to be specified."))

        items_vals = []
        for i in range(count):
            item_vals = {
                'batch_id': self.id,
            }

            # Set dimensions based on batch type and provided values
            if self.batch_type == 'sheet':
                item_vals.update({
                    'length': length,
                    'width': width,
                })
            elif self.batch_type == 'bar':
                item_vals.update({
                    'length': length,
                })
            elif self.batch_type == 'part':
                item_vals.update({
                    'weight': weight,
                })

            items_vals.append(item_vals)

        # Create all items at once
        if items_vals:
            self.env['kojto.warehouses.items'].create(items_vals)

    def action_generate_items(self):
        """Action to generate items - opens a wizard."""
        self.ensure_one()
        return {
            'name': 'Generate Items',
            'type': 'ir.actions.act_window',
            'res_model': 'kojto.warehouses.generate.items.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_batch_id': self.id,
                'default_batch_type': self.batch_type,
            }
        }

    def action_create_inspection_report(self):
        """Create a new inspection report for this batch."""
        self.ensure_one()
        return {
            'name': 'Create Inspection Report',
            'type': 'ir.actions.act_window',
            'res_model': 'kojto.warehouses.inspection.report',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_batch_id': self.id,
            }
        }

    @api.constrains('invoice_id', 'invoice_content_id', 'accounting_identifier_id')
    def _check_invoice_content_belongs_to_invoice(self):
        """Ensure that the selected invoice content belongs to the selected invoice and accounting identifier matches."""
        for batch in self:
            if batch.invoice_content_id and batch.invoice_id:
                if batch.invoice_content_id.invoice_id != batch.invoice_id:
                    raise ValidationError(_(
                        "Invoice content '%s' does not belong to invoice '%s'. "
                        "Please select an invoice content from the selected invoice."
                    ) % (batch.invoice_content_id.name, batch.invoice_id.name))

            # Ensure accounting identifier matches the one from invoice content
            if batch.invoice_content_id and batch.invoice_content_id.identifier_id and batch.accounting_identifier_id:
                if batch.accounting_identifier_id != batch.invoice_content_id.identifier_id:
                    raise ValidationError(_(
                        "Accounting identifier '%s' does not match the identifier from invoice content '%s'. "
                        "The accounting identifier should be '%s'."
                    ) % (
                        batch.accounting_identifier_id.name,
                        batch.invoice_content_id.name,
                        batch.invoice_content_id.identifier_id.name
                    ))

    @api.onchange('invoice_id')
    def _onchange_invoice_id(self):
        """Filter invoice contents based on selected invoice and clear if invoice changes."""
        if self.invoice_id:
            # Automatically set counterparty from invoice
            self.counterparty_id = self.invoice_id.counterparty_id

            # If current invoice content doesn't belong to new invoice, clear it
            if self.invoice_content_id and self.invoice_content_id.invoice_id != self.invoice_id:
                self.invoice_content_id = False
                # Also clear accounting_identifier_id since invoice content changed
                self.accounting_identifier_id = False
            return {'domain': {'invoice_content_id': [('invoice_id', '=', self.invoice_id.id)]}}
        else:
            # If invoice is cleared, also clear invoice content, accounting identifier, and counterparty
            self.invoice_content_id = False
            self.accounting_identifier_id = False
            self.counterparty_id = False
            return {'domain': {'invoice_content_id': []}}

    @api.onchange('invoice_content_id')
    def _onchange_invoice_content_id(self):
        """Update related fields when invoice content changes."""
        if self.invoice_content_id:
            # Set the invoice from the invoice content
            self.invoice_id = self.invoice_content_id.invoice_id
            self.unit_price = self.invoice_content_id.unit_price

            # Clear and set the accounting identifier from invoice content
            self.accounting_identifier_id = False  # Clear first to force domain update
            if self.invoice_content_id.identifier_id:
                self.accounting_identifier_id = self.invoice_content_id.identifier_id
                # Filter accounting_identifier_id to only show the one from invoice content
                return {'domain': {'accounting_identifier_id': [('id', '=', self.invoice_content_id.identifier_id.id)]}}
            else:
                # If no identifier in invoice content, show all active
                return {'domain': {'accounting_identifier_id': [('active', '=', True)]}}
        else:
            # Clear accounting_identifier_id and reset domain
            self.accounting_identifier_id = False
            return {'domain': {'accounting_identifier_id': [('active', '=', True)]}}

    @api.model
    def _search_active(self, operator, value):
        """Search method for active field to optimize filtering.
        Maps active=True to current_batch_quantity > 0
        Maps active=False to current_batch_quantity <= 0
        """
        if operator == '=':
            return [('current_batch_quantity', '>' if value else '<=', 0)]
        elif operator == '!=':
            return [('current_batch_quantity', '<=' if value else '>', 0)]
        return []

    def _compute_summary_sheet(self, batch):
        """Compute summary for sheet type batches."""
        if not batch.items_ids:
            return ""

        material_name = batch.material_id.name or ""
        thickness_str = f"{batch.thickness}mm" if batch.thickness else ""

        dimension_groups = Counter(
            f"{int(item.length)}x{int(item.width)}mm"
            for item in batch.items_ids
            if item.item_type == 'sheet' and item.length and item.width
        )
        dim_summary = [f"{count}pcs {dim}" for dim, count in dimension_groups.items()]

        parts = [part for part in [material_name, thickness_str] if part]
        if dim_summary:
            parts.append("-> " + ", ".join(dim_summary))
        return ", ".join(parts)

    def _compute_summary_bar(self, batch):
        """Compute summary for bar type batches."""
        if not batch.items_ids:
            return ""

        material_name = batch.material_id.name or ""
        profile_name = batch.profile_id.name or ""

        length_groups = Counter(
            f"{int(item.length)}mm"
            for item in batch.items_ids
            if item.item_type == 'bar' and item.length
        )
        length_summary = [f"{count}pcs {length}" for length, count in length_groups.items()]

        parts = [part for part in [material_name, profile_name] if part]
        if length_summary:
            parts.append(" ".join(length_summary))
        return ", ".join(parts)

    def _compute_summary_part(self, batch):
        """Compute summary for part type batches."""
        if not batch.items_ids:
            return ""

        part_type = dict(batch._fields['part_type'].selection).get(batch.part_type, "")
        unit_name = batch.unit_id.name or ""
        quantity_str = f"{batch.current_batch_quantity:.2f}" if batch.current_batch_quantity else "0"

        parts = [part for part in [part_type, f"{quantity_str} {unit_name}"] if part]
        return ", ".join(parts)

    def _compute_json_properties_of_batch_materials(self):
        """
        Compute all chemical and mechanical properties of all batch_properties_ids as a nested JSON.
        Returns a list of dicts, one per batch_properties record.
        """
        property_fields_chemical = [
            'carbon', 'silicon', 'manganese', 'chromium', 'molybdenum', 'vanadium', 'nickel', 'copper',
            'phosphorus', 'sulfur', 'nitrogen', 'titanium', 'magnesium', 'zinc', 'iron', 'aluminum',
            'tin', 'cobalt', 'boron', 'carbon_equivalent'
        ]
        property_fields_mechanical = [
            'yield_strength_0_2', 'yield_strength_1_0', 'tensile_strength', 'elongation', 'reduction_of_area',
            'impact_energy', 'impact_temperature', 'hardness_hb', 'hardness_hrc', 'hardness_hv',
            'young_modulus', 'poisson_ratio', 'density', 'thermal_expansion', 'thermal_conductivity',
            'electrical_resistivity'
        ]
        extra_fields = ['name', 'description', 'melting_process', 'material_grade_id']

        result = []
        for batch in self:
            batch_json = []
            for prop in batch.batch_properties_ids:
                chemical = {field: getattr(prop, field) for field in property_fields_chemical}
                mechanical = {field: getattr(prop, field) for field in property_fields_mechanical}
                extra = {
                    'name': prop.name,
                    'description': prop.description,
                    'melting_process': prop.melting_process,
                    'material_grade_id': prop.material_grade_id.id if prop.material_grade_id else None,
                    'material_grade_name': prop.material_grade_id.name if prop.material_grade_id else None,
                }
                batch_json.append({
                    'chemical': chemical,
                    'mechanical': mechanical,
                    'extra': extra
                })
            result.append(batch_json)
        return result

    @api.constrains('invoice_id', 'invoice_content_id', 'accounting_identifier_id')
    def _check_required_accounting_fields(self):
        """Ensure that invoice_id, invoice_content_id, and accounting_identifier_id are provided."""
        for batch in self:
            if not batch.invoice_id:
                raise ValidationError(_("Invoice is required for batch '%s'.") % batch.name)
            if not batch.invoice_content_id:
                raise ValidationError(_("Invoice Content is required for batch '%s'.") % batch.name)
            if not batch.accounting_identifier_id:
                raise ValidationError(_("Accounting Identifier is required for batch '%s'.") % batch.name)
