from odoo import models, fields, api
from odoo.exceptions import ValidationError

class KojtoProfileBatchContent(models.Model):
    _name = "kojto.profile.batch.content"
    _description = "Kojto Profile Batch Content"
    _order = "position"

    position = fields.Char(string="№", size=5)
    description = fields.Char(string="Description")
    batch_id = fields.Many2one("kojto.profile.batches", string="Batch", required=True, ondelete="cascade")
    profile_id = fields.Many2one("kojto.profiles", string="Profile", required=True)
    length = fields.Float(string="Length", required=True, default=0.0, digits=(9, 2))
    length_extension = fields.Float(string="Length Extension", required=True, default=0.0, digits=(9, 2))
    quantity = fields.Float(string="Pcs", digits=(16, 2), default=1, required=True)
    profile_drawing = fields.Binary(related="profile_id.drawing", string="Profile Drawing")
    material_id = fields.Many2one("kojto.base.material.grades", related="profile_id.material_id", string="Material", readonly=True)
    profile_weight = fields.Float(related="profile_id.profile_weight", string="Profile Weight", readonly=True, digits=(9, 2))
    coating_perimeter = fields.Float(related="profile_id.coating_perimeter", string="Coating Perimeter (mm)", readonly=True, store=False, digits=(9, 2))
    total_profile_length_net = fields.Float(string="Tot. Net Length (m)", compute="_compute_total_lengths", store=False, digits=(9, 2))
    total_profile_length_gross = fields.Float(string="Tot. Gross Length (m)", compute="_compute_total_lengths", store=False, digits=(9, 2))
    total_profile_weight_net = fields.Float(string="Tot. Net Weight", compute="_compute_total_weights", store=False, digits=(9, 2))
    total_profile_weight_gross = fields.Float(string="Tot. Gross Weight", compute="_compute_total_weights", store=False, digits=(9, 2))
    total_profile_coating_area = fields.Float(string="Tot. Coating Area (m²)", compute="_compute_total_weights", store=False, digits=(9, 2))
    total_profile_process_time = fields.Float(string="Tot. Process Time (min)", compute="_compute_total_process_time", store=False, digits=(9, 2))
    number_ext_corners = fields.Integer(related="profile_id.number_ext_corners", string="Ext. Corners", readonly=True)

    @api.depends("quantity", "length", "length_extension")
    def _compute_total_lengths(self):
        for record in self:
            record.total_profile_length_net = record.quantity * record.length / 1000
            record.total_profile_length_gross = record.quantity * (record.length + record.length_extension) / 1000

    @api.depends("quantity", "length", "length_extension", "profile_weight", "coating_perimeter")
    def _compute_total_weights(self):
        for record in self:
            record.total_profile_weight_net = record.profile_weight * record.quantity * record.length / 1000 if record.profile_weight else 0.0
            record.total_profile_weight_gross = record.profile_weight * record.quantity * ((record.length + record.length_extension) / 1000) if record.profile_weight else 0.0
            record.total_profile_coating_area = record.quantity * ((record.length + record.length_extension) * record.coating_perimeter) / 1000000 if record.coating_perimeter else 0.0

    @api.depends("quantity", "length", "length_extension", "profile_id.process_ids.time_per_meter")
    def _compute_total_process_time(self):
        for record in self:
            if not record.profile_id or not record.profile_id.process_ids:
                record.total_profile_process_time = 0.0
                continue
            gross_length_per_piece = (record.length + record.length_extension) / 1000
            total_process_time = 0.0
            for process in record.profile_id.process_ids:
                time_per_meter = process.time_per_meter or 0.0
                process_time = (gross_length_per_piece * record.quantity) * time_per_meter
                total_process_time += process_time
            record.total_profile_process_time = total_process_time

    def copy_content_row(self):
        self.ensure_one()
        original_position = self.position or ''
        new_position = original_position
        if len(original_position) >= 2 and original_position[-2:].isdigit():
            try:
                num_part = int(original_position[-2:])
                if 0 <= num_part <= 98:
                    new_position = original_position[:-2] + f"{num_part + 1:02d}"
                elif num_part == 99:
                    new_position = None
            except ValueError:
                new_position = None
        if not new_position or self.env['kojto.profile.batch.content'].search([
            ('batch_id', '=', self.batch_id.id),
            ('position', '=', new_position),
            ('id', '!=', self.id),
        ]):
            base_position = original_position
            counter = 1
            new_position = f"{base_position}{counter}"
            while self.env['kojto.profile.batch.content'].search([
                ('batch_id', '=', self.batch_id.id),
                ('position', '=', new_position),
                ('id', '!=', self.id),
            ]):
                counter += 1
                new_position = f"{base_position}{counter}"
        if len(new_position) > 5:
            new_position = new_position[:5]
        new_row = self.copy({"batch_id": self.batch_id.id, "position": new_position})
        return True

    def open_o2m_record(self):
        self.ensure_one()
        if self.profile_id:
            return {
                "type": "ir.actions.act_window",
                "name": "Profile",
                "res_model": "kojto.profiles",
                "view_mode": "form",
                "res_id": self.profile_id.id,
                "target": "new",
            }
        return True

    _sql_constraints = [('unique_position_per_batch', 'UNIQUE(batch_id, position)', 'The position must be unique within each batch.')]
