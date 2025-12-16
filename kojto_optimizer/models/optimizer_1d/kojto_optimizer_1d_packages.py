from odoo import api, fields, models
from odoo.exceptions import ValidationError
from ...utils.export_1d_cutting_plan_to_excel import export_1d_cutting_plan_to_excel
from ...utils.compute_1d_cutting_plan import compute_1d_cutting_plan


class KojtoOptimizer1DPackages(models.Model):
    _name = "kojto.optimizer.1d.packages"
    _description = "Kojto Optimizer 1D Packages"
    _inherit = ["kojto.library.printable"]
    _report_ref = "kojto_optimizer.print_kojto_optimizer_1d_packages"


    name = fields.Char(string="Name", compute="generate_1d_package_name", store=True)
    subcode_id = fields.Many2one("kojto.commission.subcodes", string="Subcode", required=True)
    description = fields.Text(string="Description")
    date_issue = fields.Date(string="Issue Date", default=fields.Date.today)
    issued_by = fields.Many2one('kojto.hr.employees', string='Issued By')
    active = fields.Boolean(string="Is Active", default=True)
    stock_ids = fields.One2many("kojto.optimizer.1d.stock", "package_id", string="Stock")
    bar_ids = fields.One2many("kojto.optimizer.1d.bars", "package_id", string="Bars")
    width_of_cut = fields.Float(string="Width of Cut (mm)", required=True, default=0.0)
    initial_cut = fields.Float(string="Initial Cut (mm)", required=True, default=0.0)
    final_cut = fields.Float(string="Final Cut (mm)", required=True, default=0.0)
    cutting_plan = fields.Text(string="Cutting Plan", compute="compute_1d_cutting_plan", store=True)
    cutting_plan_json = fields.Text(string="Cutting Plan JSON", compute="compute_1d_cutting_plan", store=True)
    optimization_method = fields.Selection(selection=[("greedy", "Greedy"), ("first-fit", "First Fit"), ("best-fit", "Best Fit")], string="Optimization Method", required=True, default="best-fit")
    use_stock_priority = fields.Boolean(string="Use Stock Priority", default=False, help="When enabled, stock pieces will be used in order of their position field")
    language_id = fields.Many2one("res.lang", string="Language", default=lambda self: self.env.ref("base.lang_en").id)
    pdf_attachment_id = fields.Many2one("ir.attachment", string="Attachments")

    @api.constrains("width_of_cut", "initial_cut", "final_cut")
    def _check_non_negative_cuts(self):
        for record in self:
            if any(val < 0 for val in [record.width_of_cut, record.initial_cut, record.final_cut]):
                raise ValidationError("Cut values cannot be negative.")

    @api.constrains("stock_ids", "bar_ids")
    def _check_record_limits(self):
        for record in self:
            if len(record.stock_ids) > 99:
                raise ValidationError("The number of stock items cannot exceed 99.")
            if len(record.bar_ids) > 999:
                raise ValidationError("The number of bars cannot exceed 999.")

    @api.depends("subcode_id")
    def generate_1d_package_name(self):
        for record in self:
            if not all([
                record.subcode_id,
                record.subcode_id.code_id,
                record.subcode_id.maincode_id
            ]):
                record.name = ""
                continue
            base_name_prefix = ".".join([
                record.subcode_id.maincode_id.maincode,
                record.subcode_id.code_id.code,
                record.subcode_id.subcode,
                "1D"
            ])
            self.env.cr.execute("""
                SELECT MAX(CAST(RIGHT(name, 3) AS INTEGER)) as num
                FROM kojto_optimizer_1d_packages
                WHERE name LIKE %s AND id != %s
            """, (
                f"{base_name_prefix}.%",
                record.id or 0
            ))
            last_number = self.env.cr.fetchone()[0] or 0
            next_number = last_number + 1
            if next_number > 999:
                raise ValidationError(
                    f"Maximum 1D package number reached for {base_name_prefix}"
                )
            record.name = f"{base_name_prefix}.{str(next_number).zfill(3)}"

    @api.depends("stock_ids", "bar_ids", "optimization_method", "width_of_cut", "initial_cut", "final_cut", "use_stock_priority")
    def compute_1d_cutting_plan(self):
        for record in self:
            try:
                compute_1d_cutting_plan(record)
            except Exception as e:
                record.cutting_plan = ""
                record.cutting_plan_json = ""

    @api.onchange("stock_ids", "bar_ids", "optimization_method", "width_of_cut", "initial_cut", "final_cut", "use_stock_priority")
    def _onchange_recompute_cutting_plan(self):
        if self._origin:
            self.compute_1d_cutting_plan()

    def action_export_cutting_plan_to_excel(self):
        self.ensure_one()
        return export_1d_cutting_plan_to_excel(self)

    def action_import_stock(self):
        self.ensure_one()
        stock_data = "\n".join(
            f"{stock.stock_position}\t{stock.stock_description}\t{stock.stock_length}\t{stock.available_stock_pieces}"
            for stock in self.stock_ids
        ) if self.stock_ids else "Position\tDescription\tLength\tQuantity\n"
        return {
            "name": "Import Stock",
            "type": "ir.actions.act_window",
            "res_model": "kojto.optimizer.1d.import.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_package_id": self.id,
                "default_import_type": "stock",
                "default_data": stock_data,
                "dialog_size": "small",
            },
        }

    def action_import_bars(self):
        self.ensure_one()
        bar_data = "\n".join(
            f"{bar.bar_position}\t{bar.bar_description}\t{bar.bar_length}\t{bar.required_bar_pieces}"
            for bar in self.bar_ids
        ) if self.bar_ids else "Position\tDescription\tLength\tQuantity\n"
        return {
            "name": "Import Bars",
            "type": "ir.actions.act_window",
            "res_model": "kojto.optimizer.1d.import.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_package_id": self.id,
                "default_import_type": "bars",
                "default_data": bar_data,
                "dialog_size": "small",
            },
        }

    def copy_and_open(self):
        self.ensure_one()
        # Copy the package with basic fields
        new_package = self.copy({
            'issued_by': self.issued_by.id if self.issued_by else False,
            'date_issue': fields.Date.today(),
        })

        # Copy all stock items to the new package
        for stock in self.stock_ids:
            stock_vals = {
                'package_id': new_package.id,
                'stock_position': stock.stock_position,
                'stock_description': stock.stock_description,
                'stock_length': stock.stock_length,
                'available_stock_pieces': stock.available_stock_pieces,
            }
            self.env['kojto.optimizer.1d.stock'].create(stock_vals)

        # Copy all bar items to the new package
        for bar in self.bar_ids:
            bar_vals = {
                'package_id': new_package.id,
                'bar_position': bar.bar_position,
                'bar_description': bar.bar_description,
                'bar_length': bar.bar_length,
                'required_bar_pieces': bar.required_bar_pieces,
            }
            self.env['kojto.optimizer.1d.bars'].create(bar_vals)

        return {
            "type": "ir.actions.act_window",
            "res_model": "kojto.optimizer.1d.packages",
            "view_mode": "form",
            "res_id": new_package.id,
            "target": "current"
        }

