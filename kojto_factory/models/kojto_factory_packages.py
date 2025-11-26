import uuid
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class KojtoFactoryPackages(models.Model):
    _name = 'kojto.factory.packages'
    _description = 'Kojto Factory Packages'
    _rec_name = 'name'
    _order = 'name asc'

    name = fields.Char(string="Number", compute="_compute_package_name", store=True, required=True)
    active = fields.Boolean(string='Active', default=True)
    status = fields.Selection([
        ('unknown', 'Unknown'),
        ('not_released', 'Not Released'),
        ('released_for_production', 'Released for Production'),
        ('produced', 'Produced'),
        ('packaged', 'Packaged'),
        ('loaded', 'Loaded'),
        ('received_by_client', 'Received by Client'),
    ], string='Status', default='unknown', required=True, tracking=True, help='Current status of the package')

    contract_id = fields.Many2one('kojto.contracts', string='Contract', required=True, ondelete='cascade')
    subcode_id = fields.Many2one(related='contract_id.subcode_id', string='Subcode', required=True)

    date_start = fields.Date(string='Start Date', default=fields.Date.today)
    date_end = fields.Date(string='End Date')
    issued_by = fields.Many2one('kojto.hr.employees', string='Issued By', default=lambda self: self.env.user.employee)
    task_ids = fields.One2many('kojto.factory.tasks', 'package_id', string='Tasks')
    description = fields.Text(string='Description', help='Description of the package and its contents')
    total_planned_work_hours = fields.Float(string='Planned HRS', compute='_compute_total_planned_work_hours', store=True)
    total_actual_work_hours = fields.Float(string='Actual HRS', compute='_compute_total_actual_work_hours', store=True)
    counterparty_id = fields.Many2one(related='contract_id.counterparty_id', string='Counterparty')

    package_content_ids = fields.One2many('kojto.factory.package.contents', 'package_id', string='Contents')

    def _get_default_employee(self):
        user = self.env.user
        employee = self.env['kojto.hr.employees'].search([('user_id', '=', user.id)], limit=1)
        return employee.id if employee else False

    @api.depends('subcode_id', 'subcode_id.name')
    def _compute_package_name(self):
        for package in self:
            if not package.subcode_id or not package.subcode_id.name:
                package.name = False
                continue
            domain = [('subcode_id', '=', package.subcode_id.id), ('id', '!=', package.id)]
            count = self.search_count(domain)
            package.name = f"{package.subcode_id.name}.PK.{str(count + 1).zfill(3)}"

    @api.constrains('subcode_id')
    def _check_subcode_id(self):
        for record in self:
            if not record.subcode_id:
                raise ValidationError("A valid subcode must be selected.")

    @api.constrains('contract_id')
    def _check_contract_subcode(self):
        """Ensure that when contract changes, the new contract has a valid subcode."""
        for record in self:
            if record.contract_id and not record.contract_id.subcode_id:
                raise ValidationError(_("The selected contract must have a valid subcode."))

    @api.constrains('name')
    def _check_name_unique(self):
        for record in self:
            if self.search([('name', '=', record.name), ('id', '!=', record.id)]):
                raise ValidationError("Package name must be unique.")

    @api.depends('task_ids')
    def _compute_total_planned_work_hours(self):
        for package in self:
            package.total_planned_work_hours = sum(task.planned_work_hours for task in package.task_ids)

    @api.depends('task_ids')
    def _compute_total_actual_work_hours(self):
        for package in self:
            package.total_actual_work_hours = sum(task.produced_task_quantity for task in package.task_ids)

    @api.onchange('task_ids', 'active')
    def _onchange_active_status(self):
        if self.task_ids:
            if not self.active:
                for task in self.task_ids:
                    task.active = False
            else:
                if not any(task.active for task in self.task_ids):
                    self.active = False
        else:
            self.active = True
        if not self.active and self.task_ids and any(task.active for task in self.task_ids):
            self.active = True

    @api.onchange('contract_id')
    def _onchange_contract_id(self):
        """Handle contract change in UI - names will be recalculated on save."""
        if self.contract_id:
            if not self.contract_id.subcode_id:
                return {
                    'warning': {
                        'title': _('Warning'),
                        'message': _('The selected contract does not have a valid subcode. Please select a contract with a valid subcode.')
                    }
                }

            # Update the subcode field to show the new value
            self.subcode_id = self.contract_id.subcode_id

            # Trigger name recalculation for immediate UI feedback
            self._compute_package_name()

            # Recalculate task names in a controlled manner for UI feedback
            if self.task_ids:
                tasks = self.task_ids.sorted('id')
                for index, task in enumerate(tasks, 1):
                    task.set_task_name_directly(self.name, index)
        else:
            # Clear subcode if no contract is selected
            self.subcode_id = False

    def write(self, vals):
        res = super(KojtoFactoryPackages, self).write(vals)
        if 'active' in vals and not vals['active']:
            self.task_ids.write({'active': False})
        elif 'task_ids' in vals:
            for package in self:
                if package.task_ids:
                    package.write({'active': any(task.active for task in package.task_ids)})
                else:
                    package.write({'active': True})

        # Recalculate names if contract changed
        if 'contract_id' in vals:
            self._recalculate_names_after_contract_change()

        return res

    def _recalculate_names_after_contract_change(self):
        """Recalculate package and task names when contract changes."""
        for package in self:
            # Recalculate package name
            package._compute_package_name()

            # Recalculate task names in a controlled manner to avoid duplicates
            if package.task_ids:
                # Get all tasks for this package and sort them by ID to ensure consistent ordering
                tasks = package.task_ids.sorted('id')

                # Set task names directly using the new method
                for index, task in enumerate(tasks, 1):
                    task.set_task_name_directly(package.name, index)

    def copy_package_row(self):
        """Copy the current package row, duplicating task_ids."""
        self.ensure_one()
        if not self.subcode_id:
            raise ValidationError(_("Cannot copy a package without a subcode."))

        # Compute the new package name first
        domain = [('subcode_id', '=', self.subcode_id.id)]
        count = self.search_count(domain)
        new_name = f"{self.subcode_id.name}.PK.{str(count + 1).zfill(3)}"

        # Get current user's employee
        current_employee = self.env.user.employee
        issued_by_id = current_employee.id if current_employee else False

        # Copy the package and set 'name' directly
        new_package = self.copy({
            'name': new_name,  # Set the computed name directly
            'task_ids': False,  # Don't copy tasks yet
            'subcode_id': self.subcode_id.id,  # Ensure subcode is copied
            'date_start': fields.Date.today(),  # Reset start date
            'date_end': False,  # Reset end date
            'issued_by': issued_by_id,  # Set current user's employee as issuer
        })

        # Now create tasks one by one with pre-computed names
        for index, task in enumerate(self.task_ids, 1):
            task_name = f"{new_name}.{str(index).zfill(2)}"
            new_task = task.copy({
                'package_id': new_package.id,
                'name': task_name,  # Set the computed name directly
                'produced_task_quantity': 0.0,
                'open_task_quantity': task.required_task_quantity,
                'job_content_ids': False,  # Don't copy job content
                'issued_by': issued_by_id,  # Set current user's employee as issuer
                'date_issue': fields.Date.today(),  # Reset issue date
            })

        return True  # Stay in list view

    def copy_all_contract_contents(self):
        """Copy all contract contents into the package as package contents."""
        self.ensure_one()

        if not self.contract_id:
            raise ValidationError(_("Cannot copy contract contents without a contract."))

        # Get all contract contents for this contract
        contract_contents = self.env['kojto.contract.contents'].search([
            ('contract_id', '=', self.contract_id.id)
        ])

        if not contract_contents:
            raise ValidationError(_("No contract contents found for this contract."))

        # Get existing package contents to avoid duplicates
        existing_contract_content_ids = self.package_content_ids.mapped('contract_content_id.id')

        # Create package contents for contract contents that don't already exist
        created_contents = []
        for contract_content in contract_contents:
            if contract_content.id not in existing_contract_content_ids:
                # Calculate remaining quantity for this contract content
                all_package_contents = self.env['kojto.factory.package.contents'].search([
                    ('contract_content_id', '=', contract_content.id),
                    ('package_id.contract_id', '=', self.contract_id.id),
                    ('package_id', '!=', self.id)
                ])
                total_allocated = sum(all_package_contents.mapped('package_content_quantity'))
                remaining_quantity = max(0, contract_content.quantity - total_allocated)

                if remaining_quantity > 0:
                    package_content = self.env['kojto.factory.package.contents'].create({
                        'package_id': self.id,
                        'contract_content_id': contract_content.id,
                        'contract_content_position': contract_content.position,
                        'package_content_quantity': remaining_quantity,
                        'package_content_status': 'planned',
                    })
                    created_contents.append(package_content)

        if created_contents:
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Information'),
                    'message': _('All contract contents are already in the package or have no remaining quantity.'),
                    'type': 'info',
                    'sticky': False,
                }
            }

    def create_invoice(self):
        """Create an invoice from the package using package contents"""
        self.ensure_one()

        if not self.env["ir.model"].search([("model", "=", "kojto.finance.invoices")], limit=1):
            raise ValidationError("The 'Kojto Finance' module is not installed. Please install it to create invoices.")

        if not self.package_content_ids:
            raise ValidationError("Cannot create invoice from package with no contents.")

        # Get contract information for invoice creation
        contract = self.contract_id
        if not contract:
            raise ValidationError("Package must be linked to a contract to create an invoice.")

        # Invert the document_in_out_type: incoming contracts create outgoing invoices
        invoice_document_type = "outgoing" if contract.document_in_out_type == "incoming" else "incoming"

        # Get default VAT treatment based on document type
        default_vat_treatment = self.env["kojto.finance.vat.treatment"].search([
            ("vat_in_out_type", "=", invoice_document_type), ("vat_treatment_type", "=", "full_vat")
        ], limit=1)
        if not default_vat_treatment:
            default_vat_treatment = self.env["kojto.finance.vat.treatment"].search([
                ("vat_in_out_type", "=", invoice_document_type)
            ], limit=1)

        now = fields.Datetime.now()
        currency_bgn = self.env.ref("base.BGN")
        currency_eur = self.env.ref("base.EUR")
        if contract.currency_id and contract.currency_id.id == currency_bgn.id:
            exchange_rate_to_bgn = 1.0
            exchange_rate_to_eur = 1.95583
        elif contract.currency_id and contract.currency_id.id == currency_eur.id:
            exchange_rate_to_bgn = 1.0 / 1.95583
            exchange_rate_to_eur = 1.0
        else:
            exchange_rate_to_bgn = 1.0
            exchange_rate_to_eur = 1.0

        # Find the first bank account of our company with the contract currency
        company_bank_account_id = False
        if contract.company_bank_account_id:
            company_bank_account_id = contract.company_bank_account_id.id
        else:
            company_bank_accounts = self.env["kojto.base.bank.accounts"].search([
                ("currency_id", "=", contract.currency_id.id),
                ("active", "=", True)
            ], limit=1)
            if company_bank_accounts:
                company_bank_account_id = company_bank_accounts.id

        # Create temp_invoice for consecutive_number logic (same as contracts)
        temp_invoice = self.env["kojto.finance.invoices"].new({
            "document_in_out_type": invoice_document_type,
            "invoice_type": "invoice",
        })

        # Get consecutive number using the same logic as contracts
        if invoice_document_type == "incoming":
            # For incoming invoices, use UUID like in contracts
            consecutive_number = f"{uuid.uuid4()}"
        else:
            # For outgoing invoices, use pick_next_consecutive_number like in contracts
            consecutive_number = temp_invoice.pick_next_consecutive_number()

        # Create invoice data
        invoice = {
            "subcode_id": self.subcode_id.id,
            "subject": f"Invoice for Package {self.name}",
            "active": True,
            "document_in_out_type": invoice_document_type,
            "invoice_type": "invoice",
            "consecutive_number": consecutive_number,
            "parent_invoice_id": False,
            "invoice_vat_rate": contract.contract_vat_rate if hasattr(contract, 'contract_vat_rate') else False,
            "invoice_vat_treatment_id": default_vat_treatment.id if default_vat_treatment else False,
            "payment_terms_id": contract.payment_terms_id.id if contract.payment_terms_id else False,
            "currency_id": contract.currency_id.id,
            "language_id": contract.language_id.id if contract.language_id else 10,  # Default language ID 10
            "incoterms_id": contract.incoterms_id.id if contract.incoterms_id else False,
            "incoterms_address": contract.incoterms_address,

            # Company information
            "company_id": contract.company_id.id,
            "company_name_id": contract.company_name_id.id if contract.company_name_id else False,
            "company_address_id": contract.company_address_id.id if contract.company_address_id else False,
            "company_bank_account_id": company_bank_account_id,
            "company_tax_number_id": contract.company_tax_number_id.id if contract.company_tax_number_id else False,
            "company_phone_id": contract.company_phone_id.id if contract.company_phone_id else False,
            "company_email_id": contract.company_email_id.id if contract.company_email_id else False,

            # Counterparty information
            "counterparty_id": contract.counterparty_id.id,
            "counterparty_type": contract.counterparty_type,
            "counterparty_name_id": contract.counterparty_name_id.id if contract.counterparty_name_id else False,
            "counterparty_bank_account_id": contract.counterparty_bank_account_id.id if contract.counterparty_bank_account_id else False,
            "counterparty_address_id": contract.counterparty_address_id.id if contract.counterparty_address_id else False,
            "counterparty_tax_number_id": contract.counterparty_tax_number_id.id if contract.counterparty_tax_number_id else False,
            "counterparty_phone_id": contract.counterparty_phone_id.id if contract.counterparty_phone_id else False,
            "counterparty_email_id": contract.counterparty_email_id.id if contract.counterparty_email_id else False,
            "counterpartys_reference": contract.counterpartys_reference,
            "pre_content_text": contract.pre_content_text,
            "post_content_text": contract.post_content_text,
            "issued_by_name_id": contract.issued_by_name_id.id if contract.issued_by_name_id else False,
            "exchange_rate_to_eur": exchange_rate_to_eur,
            "exchange_rate_to_bgn": exchange_rate_to_bgn,
            "datetime_issue": now,
            "datetime_tax_event": now,
        }

        new_invoices = self.env["kojto.finance.invoices"].create(invoice)

        # Create invoice contents from package contents
        for package_content in self.package_content_ids:
            if package_content.contract_content_id:
                content = self.env["kojto.finance.invoice.contents"].create(
                    {
                        "invoice_id": new_invoices.id,
                        "name": package_content.contract_content_id.name,
                        "position": package_content.contract_content_position,
                        "quantity": package_content.package_content_quantity,
                        "unit_id": package_content.contract_content_unit_id.id if package_content.contract_content_unit_id else False,
                        "unit_price": package_content.contract_content_id.unit_price if package_content.contract_content_id.unit_price else 0.0,
                        "subcode_id": self.subcode_id.id,
                        "vat_treatment_id": default_vat_treatment.id if default_vat_treatment else False,
                    }
                )

        new_invoices.refresh_compute_totals()

        return {
            "type": "ir.actions.act_window",
            "res_model": "kojto.finance.invoices",
            "res_id": new_invoices.id,
            "view_mode": "form",
            "target": "current",
        }

    def create_delivery(self):
        """Create a delivery document from the package using package contents"""
        self.ensure_one()

        if not self.env["ir.model"].search([("model", "=", "kojto.deliveries")], limit=1):
            raise ValidationError("The 'Kojto Deliveries' module is not installed. Please install it to create deliveries.")

        if not self.package_content_ids:
            raise ValidationError("Cannot create delivery from package with no contents.")

        # Get contract information for delivery creation
        contract = self.contract_id
        if not contract:
            raise ValidationError("Package must be linked to a contract to create a delivery.")

        # Create the delivery record
        delivery_data = {
            "subject": f"Delivery for Package {self.name}",
            "active": True,
            "document_in_out_type": contract.document_in_out_type,
            "datetime_delivery": fields.Datetime.now(),
            "currency_id": contract.currency_id.id,
            "language_id": contract.language_id.id if contract.language_id else 10,  # Default language ID 10
            "incoterms_id": contract.incoterms_id.id if contract.incoterms_id else False,
            "incoterms_address": contract.incoterms_address,

            # Company information
            "company_id": contract.company_id.id,
            "company_name_id": contract.company_name_id.id if contract.company_name_id else False,
            "company_address_id": contract.company_address_id.id if contract.company_address_id else False,
            "company_bank_account_id": contract.company_bank_account_id.id if contract.company_bank_account_id else False,
            "company_tax_number_id": contract.company_tax_number_id.id if contract.company_tax_number_id else False,
            "company_phone_id": contract.company_phone_id.id if contract.company_phone_id else False,
            "company_email_id": contract.company_email_id.id if contract.company_email_id else False,

            # Counterparty information
            "counterparty_id": contract.counterparty_id.id,
            "counterparty_type": contract.counterparty_type,
            "counterparty_name_id": contract.counterparty_name_id.id if contract.counterparty_name_id else False,
            "counterparty_bank_account_id": contract.counterparty_bank_account_id.id if contract.counterparty_bank_account_id else False,
            "counterparty_address_id": contract.counterparty_address_id.id if contract.counterparty_address_id else False,
            "counterparty_tax_number_id": contract.counterparty_tax_number_id.id if contract.counterparty_tax_number_id else False,
            "counterparty_phone_id": contract.counterparty_phone_id.id if contract.counterparty_phone_id else False,
            "counterparty_email_id": contract.counterparty_email_id.id if contract.counterparty_email_id else False,
            "counterpartys_reference": contract.counterpartys_reference,

            # Document content
            "pre_content_text": contract.pre_content_text,
            "post_content_text": contract.post_content_text,

            # Required field
            "subcode_id": self.subcode_id.id if self.subcode_id else False,
        }

        # Create the delivery
        new_delivery = self.env["kojto.deliveries"].create(delivery_data)

        # Copy package contents to delivery contents
        for package_content in self.package_content_ids:
            if package_content.contract_content_id:
                delivery_content_data = {
                    "delivery_id": new_delivery.id,
                    "name": package_content.contract_content_id.name,
                    "position": package_content.contract_content_position,
                    "quantity": package_content.package_content_quantity,
                    "unit_id": package_content.contract_content_unit_id.id if package_content.contract_content_unit_id else False,
                }

                self.env["kojto.delivery.contents"].create(delivery_content_data)

        # Return action to open the created delivery
        return {
            "type": "ir.actions.act_window",
            "res_model": "kojto.deliveries",
            "res_id": new_delivery.id,
            "view_mode": "form",
            "target": "current",
        }
