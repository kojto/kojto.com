from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class KojtoFactoryPackageContents(models.Model):
    _name = "kojto.factory.package.contents"
    _description = "Package Contents"
    _sort = "contract_content_position desc"


    package_content_status = fields.Selection([('planned', 'Planned'), ('in_production', 'In Production'), ('produced', 'Produced'), ('completed', 'Completed')], string='Status', default='planned')

    package_id = fields.Many2one("kojto.factory.packages", string="Package", ondelete="cascade", required=True)

    contract_content_id = fields.Many2one("kojto.contract.contents", string="Contract Content", required=True, domain="[('id', 'in', available_contract_content_ids)]")
    available_contract_content_ids = fields.Many2many('kojto.contract.contents', compute='_compute_available_contract_contents')
    contract_content_position = fields.Char(string="№", size=5)
    contract_content_unit_id = fields.Many2one("kojto.base.units", string="Unit", related="contract_content_id.unit_id", store=True, readonly=True)

    contract_content_quantity = fields.Float(string="Quantity", related="contract_content_id.quantity", store=True, readonly=True)
    package_content_quantity = fields.Float(string="Quantity", digits=(16, 2), required=True)

    @api.constrains('package_content_quantity', 'contract_content_id')
    def _check_quantity_constraints(self):
        for record in self:
            if record.package_content_quantity <= 0:
                raise ValidationError(_("Package content quantity must be greater than zero."))

            # Get all package contents for this contract content across all packages
            all_package_contents = self.search([
                ('contract_content_id', '=', record.contract_content_id.id),
                ('package_id.contract_id', '=', record.package_id.contract_id.id),
                ('id', '!=', record.id)  # Exclude current record for updates
            ])

            # Calculate total quantity already allocated in packages
            total_allocated = sum(all_package_contents.mapped('package_content_quantity'))

            # Check if adding this quantity would exceed the contract content quantity
            if total_allocated + record.package_content_quantity > record.contract_content_id.quantity:
                raise ValidationError(_(
                    "The total quantity of this item across all packages (%s + %s) cannot exceed the contract content quantity (%s)."
                ) % (total_allocated, record.package_content_quantity, record.contract_content_id.quantity))

    @api.onchange('contract_content_id')
    def _onchange_contract_content(self):
        if self.contract_content_id:
            # Set initial quantity to remaining available quantity
            all_package_contents = self.search([
                ('contract_content_id', '=', self.contract_content_id.id),
                ('package_id.contract_id', '=', self.package_id.contract_id.id),
                ('id', '!=', self.id)
            ])
            total_allocated = sum(all_package_contents.mapped('package_content_quantity'))
            self.package_content_quantity = max(0, self.contract_content_id.quantity - total_allocated)

    @api.depends('package_id', 'package_id.contract_id')
    def _compute_available_contract_contents(self):
        for record in self:
            if record.package_id and record.package_id.contract_id:
                # Get all contract contents for this contract
                contract_contents = self.env['kojto.contract.contents'].search([
                    ('contract_id', '=', record.package_id.contract_id.id)
                ])

                # Filter contract contents that have available quantity
                available_contents = self.env['kojto.contract.contents']
                for content in contract_contents:
                    # Get all package contents for this contract content in other packages
                    allocated_package_contents = self.search([
                        ('contract_content_id', '=', content.id),
                        ('package_id.contract_id', '=', record.package_id.contract_id.id),
                        ('id', '!=', record.id or 0)  # Exclude current record
                    ])

                    # Calculate total allocated quantity
                    total_allocated = sum(allocated_package_contents.mapped('package_content_quantity'))

                    # If there's still available quantity, include this content
                    if total_allocated < content.quantity:
                        available_contents |= content

                # Set available contract contents
                record.available_contract_content_ids = available_contents
            else:
                record.available_contract_content_ids = False

    @api.onchange('package_id')
    def _onchange_package_id(self):
        if self.package_id and self.package_id.contract_id:
            # Clear contract_content_id if it doesn't belong to the selected contract
            if self.contract_content_id and self.contract_content_id.contract_id != self.package_id.contract_id:
                self.contract_content_id = False
            # Domain is handled by available_contract_content_ids computed field
            return {
                'domain': {
                    'contract_content_id': [
                        ('contract_id', '=', self.package_id.contract_id.id)
                    ]
                }
            }
        return {'domain': {'contract_content_id': []}}
