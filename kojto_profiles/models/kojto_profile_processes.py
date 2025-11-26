from odoo import models, fields, api
from odoo.exceptions import ValidationError

class KojtoProfileProcesses(models.Model):
    _name = "kojto.profile.processes"
    _description = "Kojto Profile Processes"
    _rec_name = "position"

    position = fields.Char(string="№", size=5)
    profile_id = fields.Many2one("kojto.profiles", string="Profile Name", ondelete="cascade", required=True)
    process_type = fields.Selection(
        [
            ("machine_welding", "Machine Welding"),
            ("manual_welding", "Manual Welding"),
            ("machine_chamfering", "Machine Chamfering"),
            ("manual_chamfering", "Manual Chamfering"),
            ("machining", "Machining"),
            ("coating", "Coating"),
            ("straightening", "Straightening"),
            ("assembly", "Assembly"),
            ("inspection", "Inspection"),
            ("other", "Other"),
        ],
        string="Process Type",
        required=True,
        help="The type of process applied to the profile.",
    )
    time_per_meter = fields.Float(string="(min/m)", required=True, help="Time required per meter of profile length, in minutes.")
    description = fields.Text(string="Description", help="Detailed description of the process, including any specific instructions or notes.")

    # Python Constraints
    @api.constrains("time_per_meter")
    def _check_time_per_meter(self):
        for record in self:
            if record.time_per_meter < 0:
                raise ValidationError("Time per meter cannot be negative for process '%s'." % record.name)
