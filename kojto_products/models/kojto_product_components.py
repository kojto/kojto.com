# kojto_products/models/kojto_product_components.py
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from ..utils.kojto_products_graph_utils import resolve_graph
from ..utils.kojto_products_export_excel import export_revision_tree_to_excel

class KojtoProductComponents(models.Model):
    _name = 'kojto.product.component'
    _description = 'Kojto Product Component'
    _inherit = [
        'kojto.product.articles.mixin',
        'kojto.product.technical.document.mixin',
        'kojto.product.packages.mixin',
        'kojto.product.process.mixin',
    ]

    name = fields.Char(string='Name', required=True, index=True)
    active = fields.Boolean(string='Active', default=True)
    unit_id = fields.Many2one('kojto.base.units', string='Unit', required=True, default=lambda self: self.env['kojto.base.units'].search([('name', '=', 'unit')], limit=1).id or False)
    subcode_id = fields.Many2one('kojto.commission.subcodes', string='Subcode', required=True, index=True)
    component_type = fields.Selection([
        ('article', 'Article'),
        ('technical_document', 'Technical Document'),
        ('package', 'Package'),
        ('process', 'Process'),
        ('other', 'Other')
    ], string='Component Type', default='article')
    description = fields.Text(string='Description')
    component_revision_number = fields.Char(string='Rev.', compute='_compute_component_revision_number', size=2)
    revision_ids = fields.One2many('kojto.product.component.revision', 'component_id', string='Revisions')
    latest_revision_id = fields.Many2one('kojto.product.component.revision', string='Latest Revision', compute='_compute_latest_revision_id', store=True, index=True)
    latest_revision_datetime = fields.Datetime(string='Last Change', related='latest_revision_id.datetime_issue', store=True)
    analysis_top_down = fields.Html(string='Analysis Top Down', related='latest_revision_id.analysis_top_down', store=False)
    analysis_bottom_up = fields.Html(string='Analysis Bottom Up', related='latest_revision_id.analysis_bottom_up', store=False)


    @api.model
    def create(self, vals_list):
        # Handle both single dict and list of dicts
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        # Create the components
        components = super().create(vals_list)

        # Create initial revision for each component
        for component in components:
            revision_vals = {
                'name': component.name,
                'revision_number': 1,
                'component_id': component.id,
                'subcode_id': component.subcode_id.id,
                'component_type': component.component_type,
                'weight_attribute': 0.0,
                'length_attribute': 0.0,
                'area_attribute': 0.0,
                'volume_attribute': 0.0,
                'time_attribute': 0.0,
                'price_attribute': 0.0,
                'other_attribute': 0.0,
                'datetime_issue': fields.Datetime.now(),
            }
            revision = self.env['kojto.product.component.revision'].create(revision_vals)
            component.latest_revision_id = revision.id

        return components

    def write(self, vals):
        """Trigger recomputation of revision names when component name changes."""
        result = super().write(vals)
        if 'name' in vals:
            revisions = self.env['kojto.product.component.revision'].search([('component_id', 'in', self.ids)])
            if revisions:
                revisions._compute_component_revision_name()
        return result

    @api.depends('revision_ids', 'revision_ids.datetime_issue')
    def _compute_component_revision_number(self):
        for component in self:
            persisted_revisions = component.revision_ids.filtered(lambda r: r.id and isinstance(r.id, int))
            latest_revision = component.get_latest_revision(persisted_revisions)
            if latest_revision:
                sorted_revisions = persisted_revisions.sorted(
                    key=lambda r: (r.datetime_issue or fields.Datetime.from_string('1970-01-01 00:00:00'), r.id)
                )
                revision_index = sorted_revisions.ids.index(latest_revision.id) if latest_revision.id in sorted_revisions.ids else 0
                component.component_revision_number = f"{revision_index:02d}"
            else:
                component.component_revision_number = '-'

    @api.depends('revision_ids', 'revision_ids.datetime_issue')
    def _compute_latest_revision_id(self):
        for component in self:
            # ✓ OPTIMIZED: Use SQL query with index instead of loading all revisions
            latest_revision = self.env['kojto.product.component.revision'].search([
                ('component_id', '=', component.id),
            ], order='datetime_issue DESC, id DESC', limit=1)

            component.latest_revision_id = latest_revision.id if latest_revision else False

    def get_latest_revision(self, revisions=None):
        self.ensure_one()
        # ✓ OPTIMIZED: Use SQL directly with index
        latest = self.env['kojto.product.component.revision'].search([
            ('component_id', '=', self.id),
        ], order='datetime_issue DESC, id DESC', limit=1)
        return latest or False

    def action_create_revision(self):
        self.ensure_one()
        latest_revision = self.get_latest_revision()
        revision_vals = {
            'component_id': self.id,
            'datetime_issue': fields.Datetime.now(),
            'weight_attribute': latest_revision.weight_attribute if latest_revision else 0.0,
            'length_attribute': latest_revision.length_attribute if latest_revision else 0.0,
            'volume_attribute': latest_revision.volume_attribute if latest_revision else 0.0,
            'area_attribute': latest_revision.area_attribute if latest_revision else 0.0,
            'time_attribute': latest_revision.time_attribute if latest_revision else 0.0,
            'price_attribute': latest_revision.price_attribute if latest_revision else 0.0,
            'other_attribute': latest_revision.other_attribute if latest_revision else 0.0,
        }
        new_revision = self.env['kojto.product.component.revision'].create(revision_vals)
        self.invalidate_recordset()
        return new_revision

    @api.constrains('name', 'subcode_id')
    def _check_name_subcode_unique(self):
        for record in self:
            if self.search_count([
                ('name', '=ilike', record.name),
                ('subcode_id', '=', record.subcode_id.id),
                ('id', '!=', record.id)
            ]):
                raise ValidationError(f"Component with name '{record.name}' and subcode '{record.subcode_id.name}' already exists.")

    def unlink(self):
        for record in self:
            links = self.env['kojto.product.component.revision.link'].search([('target_component_id', '=', record.id)])
            if links:
                raise ValidationError(f"Cannot delete component '{record.name}' because it is referenced in revision links.")
        return super().unlink()

    def action_resolve_component(self):
        self.ensure_one()
        selected_revision_id = self.env.context.get('selected_revision_id')
        if selected_revision_id:
            revision = self.env['kojto.product.component.revision'].browse(selected_revision_id)
            if revision.component_id != self:
                raise UserError("Selected revision does not belong to this component.")
            # Trigger resolve_graph to recompute analysis (happens in revision's compute method)
            # The form shows `analysis_top_down` and `analysis_bottom_up` via related fields.
            # Returning the action will re-render the form and recompute on the revision model.
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'kojto.product.component',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_revision_comparison_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'kojto.product.component.comparison.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_component_id': self.id}
        }

    def copy_and_open(self):
        """
        Copy the component with subcode_id, unit_id, component_type, and name (with incremented suffix if needed).
        Create a new component, which triggers revision creation, and open it in a form view.
        """
        self.ensure_one()
        # Base name for the new component
        base_name = self.name
        # Find existing components with similar names for the same subcode_id
        existing_names = self.env['kojto.product.component'].search([
            ('name', 'like', f"{base_name}%"),
            ('subcode_id', '=', self.subcode_id.id)
        ]).mapped('name')
        new_name = f"{base_name} (1)"
        suffix = 1
        while new_name in existing_names:
            suffix += 1
            new_name = f"{base_name} ({suffix})"

        # Create a copy of the component
        new_component = self.copy({
            'name': new_name,
            'subcode_id': self.subcode_id.id,
            'unit_id': self.unit_id.id,
            'component_type': self.component_type,
            'active': True,
            'description': self.description,
        })

        # Verify that a revision was created
        if not new_component.revision_ids:
            raise ValidationError(f"Failed to create a revision for the new component '{new_name}'.")

        # Return an action to open the new component in a form view
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'kojto.product.component',
            'res_id': new_component.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_export_last_revision(self):
        """Export the last revision of the component to Excel."""
        self.ensure_one()
        if not self.latest_revision_id:
            raise UserError("No revision available for export.")

        try:
            visited, edges, aggregated_attributes, lock_status = resolve_graph(
                start_revision=self.latest_revision_id,
                env=self.env,
                mode='tree'
            )
            revision_map = {
                rev.id: rev for rev in self.env['kojto.product.component.revision'].browse(visited) if rev.exists()
            }
            file_content, file_name = export_revision_tree_to_excel(
                edges=edges,
                visited=visited,
                aggregated_attributes=aggregated_attributes,
                revision_map=revision_map,
                env=self.env,
                start_revision_id=self.latest_revision_id.id,
                revision_number=self.latest_revision_id.revision_number,
                lock_status=lock_status
            )
            attachment = self.env['ir.attachment'].create({
                'name': file_name,
                'datas': file_content,
                'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'res_model': self._name,
                'res_id': self.id,
            })
            return {
                'type': 'ir.actions.act_url',
                'url': '/web/content/%s?download=true' % attachment.id,
                'target': 'self',
            }
        except Exception as e:
            raise UserError(f"Error exporting last revision: {str(e)}")

    def action_open_revision_form(self):
        """Open the component's latest revision in a form view."""
        self.ensure_one()
        if not self.latest_revision_id:
            raise UserError("No revision available to open.")
        return {
            'type': 'ir.actions.act_window',
            'name': 'Component Revision',
            'res_model': 'kojto.product.component.revision',
            'res_id': self.latest_revision_id.id,
            'view_mode': 'form',
            'target': 'new',
        }
