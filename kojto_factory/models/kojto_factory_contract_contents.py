from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class KojtoFactoryContractContents(models.Model):
    _inherit = "kojto.contract.contents"

    # Factory specific fields
    factory_planned_quantity = fields.Float(string="Planned Quantity", compute="_compute_factory_package_content_quantity")
    factory_in_production_quantity = fields.Float(string="In Production Quantity", compute="_compute_factory_package_content_quantity")
    factory_produced_quantity = fields.Float(string="Produced Quantity", compute="_compute_factory_package_content_quantity")

    factory_package_content_ids = fields.One2many("kojto.factory.package.contents", "contract_content_id", string="Package Contents")

    @api.depends("factory_package_content_ids.package_content_quantity",
                "factory_package_content_ids.package_content_status")
    def _compute_factory_package_content_quantity(self):
        for record in self:
            # Get all package contents for this record
            package_contents = record.factory_package_content_ids

            # Calculate planned quantity (sum of all package contents)
            record.factory_planned_quantity = sum(package_contents.mapped("package_content_quantity"))

            # Calculate in production quantity (sum of package contents with status 'in_production')
            in_production_contents = package_contents.filtered("package_content_status == 'in_production'")
            record.factory_in_production_quantity = sum(in_production_contents.mapped("package_content_quantity"))

            # Calculate produced quantity (sum of produced quantities from tasks in packages)
            package_ids = package_contents.mapped('package_id').ids
            tasks = self.env['kojto.factory.tasks'].search([
                ('package_id', 'in', package_ids),
                ('package_id.package_content_ids.contract_content_id', '=', record.id)
            ])
            record.factory_produced_quantity = sum(tasks.mapped('produced_task_quantity'))

    def action_view_factory_packages(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Factory Packages"),
            "res_model": "kojto.factory.packages",
            "view_mode": "tree,form",
            "domain": [("id", "in", self.factory_package_content_ids.mapped("package_id").ids)],
            "context": {"create": False},
        }
