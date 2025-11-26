from odoo import models, fields
from odoo.exceptions import UserError

class KojtoProfileBatchImportWizard(models.TransientModel):
    _name = "kojto.profile.batch.import.wizard"
    _description = "Import Batch Content Wizard"

    batch_id = fields.Many2one("kojto.profile.batches", string="Source Batch", required=True, help="Select the batch from which to import content.")
    target_batch_id = fields.Many2one("kojto.profile.batches", string="Target Batch", default=lambda self: self.env.context.get('active_id'), readonly=True,)

    def action_import_selected_batch_content(self):
        self.ensure_one()
        if not self.batch_id.batch_content_ids:
            raise UserError("The selected batch has no content to import.")
        existing_positions = set(
            content.position
            for content in self.target_batch_id.batch_content_ids
            if content.position
        )
        new_content_vals = []
        for content in self.batch_id.batch_content_ids:
            new_position = content.position
            if new_position in existing_positions:
                base_position = new_position or ""
                counter = 1
                new_position = f"{base_position}{counter}"
                while new_position in existing_positions:
                    counter += 1
                    new_position = f"{base_position}{counter}"
                if len(new_position) > 5:
                    new_position = new_position[:5]
            existing_positions.add(new_position)
            content_vals = {
                "batch_id": self.target_batch_id.id,
                "position": new_position,
                "profile_id": content.profile_id.id,
                "description": content.description,
                "length": content.length,
                "quantity": content.quantity,
                "length_extension": content.length_extension,
            }
            new_content_vals.append(content_vals)
        if new_content_vals:
            self.env["kojto.profile.batch.content"].create(new_content_vals)
        return {"type": "ir.actions.act_window_close"}
