# -*- coding: utf-8 -*-
# kojto_products/models/kojto_product_component_revisions.py
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta
from ..utils.kojto_products_graph_utils import resolve_graph
from ..utils.kojto_products_collect_revision_paths import collect_revision_paths
from ..utils.kojto_products_export_html import format_top_down, format_bottom_up
from ..utils.kojto_products_export_excel import export_revision_tree_to_excel

class KojtoProductComponentRevision(models.Model):
    _name = 'kojto.product.component.revision'
    _description = 'Kojto Product Component Revision'
    _rec_name = 'name'

    is_locked = fields.Boolean(string='Locked', default=False, index=True)
    is_last_revision = fields.Boolean(string='Last Revision', compute='_compute_is_last_revision')
    datetime_locked = fields.Datetime(string='Datetime Locked', readonly=True)
    name = fields.Char(string='Name', compute='_compute_component_revision_name', store=True)
    revision_number = fields.Char(string='Revision Number', compute='_compute_revision_number', store=False)
    component_id = fields.Many2one('kojto.product.component', required=True, ondelete='cascade', index=True)
    subcode_id = fields.Many2one('kojto.commission.subcodes', string='Subcode', related='component_id.subcode_id', store=True, readonly=True)
    component_type = fields.Selection(related='component_id.component_type', store=True, readonly=True)
    weight_attribute = fields.Float(string='Weight (kg)')
    length_attribute = fields.Float(string='Length (m)')
    area_attribute = fields.Float(string='Area (m2)')
    volume_attribute = fields.Float(string='Volume (m3)')
    time_attribute = fields.Float(string='Time (min)')
    price_attribute = fields.Float(string='Price (EUR)')
    other_attribute = fields.Float(string='Other')
    datetime_issue = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    link_ids = fields.One2many('kojto.product.component.revision.link', 'source_revision_id', string='Links')
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments', relation='kojto_product_component_revision_attachment_rel', column1='revision_id', column2='attachment_id')
    analysis_top_down = fields.Html(string='Analysis Top Down', compute='_compute_analysis_results', store=False, sanitize_attributes=False)
    analysis_bottom_up = fields.Html(string='Analysis Bottom Up', compute='_compute_analysis_results', store=False, sanitize_attributes=False)
    export_file = fields.Binary(string='Export File', readonly=True, attachment=True)
    export_file_name = fields.Char(string='Export File Name', readonly=True)

    @api.depends('component_id', 'datetime_issue')
    def _compute_is_last_revision(self):
        for revision in self:
            if not revision.component_id:
                revision.is_last_revision = False
                continue
            # Get all revisions of this component
            persisted_revisions = revision.component_id.revision_ids.filtered(lambda r: r.id and isinstance(r.id, int))
            if not persisted_revisions:
                revision.is_last_revision = True  # If it's the only revision, it's the latest
                continue
            # Sort revisions by datetime_issue and id, same as get_latest_revision
            sorted_revisions = persisted_revisions.sorted(
                key=lambda r: (r.datetime_issue or fields.Datetime.from_string('1970-01-01 00:00:00'), r.id),
                reverse=True
            )
            # A revision is the latest if it has the most recent datetime_issue and highest id
            revision.is_last_revision = (
                revision.datetime_issue == sorted_revisions[0].datetime_issue and
                revision.id == sorted_revisions[0].id
            )

    @api.depends('component_id')
    def _compute_revision_number(self):
        if not self:
            return

        # ✓ OPTIMIZED: Batch process all revisions by component instead of per-revision queries
        components = self.mapped('component_id')

        for component in components:
            # Get all revisions for this component, sorted by datetime_issue and id
            revisions = self.search([
                ('component_id', '=', component.id)
            ], order='datetime_issue ASC, id ASC')

            # Assign revision numbers based on position
            for index, rev in enumerate(revisions):
                rev.revision_number = f"{index:02d}"

    @api.depends('component_id', 'component_id.name', 'datetime_issue')
    def _compute_component_revision_name(self):
        for component_id in self.mapped('component_id'):
            revisions = self.search([('component_id', '=', component_id.id)], order='datetime_issue ASC')
            component_name = component_id.name or 'unnamed'
            for index, rev in enumerate(revisions):
                rev.name = f"{component_name}_rev{index:02d}"

    @api.depends('datetime_issue', 'link_ids')
    def _compute_analysis_results(self):
        for revision in self:
            if not revision.id or not revision.exists():
                revision.analysis_top_down = "<ul><li>No revision data available</li></ul>"
                revision.analysis_bottom_up = "<ul><li>No revision data available</li></ul>"
                continue

            # ✓ Use resolve_depth from context (defaults to 30 if not specified)
            max_depth = self.env.context.get('resolve_depth', 30)

            # ✓ Include ALL children in traversal for correct aggregates
            # Only limit depth to prevent stack overflow
            visited, edges, aggregated_attributes, lock_status = resolve_graph(
                start_revision=revision,
                env=self.env,
                mode='tree',
                max_depth=max_depth  # ← Limit depth only
            )
            revision_map = {
                rev.id: rev for rev in self.env['kojto.product.component.revision'].browse(visited) if rev.exists()
            }
            # Get paths and quantities for bottom-up analysis
            paths, quantities, link_quantities = collect_revision_paths(
                revision.id, edges, revision_map, self.env
            )

            revision.analysis_top_down = format_top_down(
                edges=edges,
                visited=visited,
                aggregated_attributes=aggregated_attributes,
                revision_map=revision_map,
                env=self.env,
                start_revision_id=revision.id,
                lock_status=lock_status
            )
            revision.analysis_bottom_up = format_bottom_up(
                start_revision=revision,
                paths=paths,
                quantities=quantities,
                link_quantities=link_quantities,
                revision_map=revision_map,
                lock_status=lock_status
            )

    @api.model
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        base_datetime = fields.Datetime.now()
        for index, vals in enumerate(vals_list):
            vals['datetime_issue'] = vals.get('datetime_issue', base_datetime + timedelta(milliseconds=index))
            vals['name'] = vals.get('name', f"temp_{vals.get('component_id', 'new')}_{vals['datetime_issue']}")
        revisions = super().create(vals_list)
        revisions._compute_component_revision_name()
        for revision in revisions:
            if revision.name.startswith('temp_'):
                raise ValidationError(f"Failed to compute name for revision ID {revision.id}.")
        return revisions

    def write(self, vals):
        # Skip validation during copying or locking operations
        if self.env.context.get('copying_revision') or self.env.context.get('locking_tree'):
            return super().write(vals)

        # Prevent modifications to non-latest revisions
        for revision in self:
            if not revision.is_last_revision:
                raise ValidationError(
                    f"Cannot modify revision '{revision.name}' because it is not the latest revision. "
                    f"Only the latest revision can be modified."
                )

        if 'is_locked' in vals and vals['is_locked'] is False:
            for revision in self:
                if revision.is_locked:
                    raise ValidationError(f"Cannot unlock revision '{revision.name}'. Locked revisions cannot be unlocked.")
        if 'is_locked' in vals and vals['is_locked'] is True and not self.env.context.get('locking_tree'):
            for revision in self:
                if not revision.is_locked:
                    # Set datetime_locked for the revision being locked
                    vals['datetime_locked'] = fields.Datetime.now()
                    self._lock_revision_tree(revision)
        return super().write(vals)

    def _lock_revision_tree(self, revision):
        # Get the revision tree using resolve_graph
        visited, edges, aggregated_attributes = resolve_graph(
            start_revision=revision,
            env=self.env,
            mode='tree'
        )
        # Get revisions to lock
        revisions_to_lock = self.env['kojto.product.component.revision'].browse(visited).filtered(lambda r: r.exists())
        # Use the same datetime_locked as the starting revision
        lock_datetime = revision.datetime_locked or fields.Datetime.now()
        # Only lock revisions that are not already locked
        revisions_to_update = revisions_to_lock.filtered(lambda r: not r.is_locked)
        if revisions_to_update:
            revisions_to_update.with_context(locking_tree=True).write({
                'is_locked': True,
                'datetime_locked': lock_datetime
            })

    def unlink(self):
        for revision in self:
            if not revision.component_id:
                continue
            revision_count = self.env['kojto.product.component.revision'].search_count([
                ('component_id', '=', revision.component_id.id)
            ])
            if revision_count <= 1:
                raise UserError("Cannot delete the last remaining revision of a component.")
            latest_revision = self.env['kojto.product.component.revision'].search([
                ('component_id', '=', revision.component_id.id)
            ], order='datetime_issue DESC, id DESC', limit=1)
            if revision != latest_revision:
                raise UserError(
                    f"Cannot delete revision '{revision.name}' because it is not the latest revision. "
                    f"Only the latest revision ('{latest_revision.name}') can be deleted."
                )
            if revision.link_ids:
                raise UserError(
                    f"Cannot delete revision '{revision.name}' because it is referenced by {len(revision.link_ids)} link(s)."
                )
        component_ids = self.mapped('component_id').ids
        result = super().unlink()
        revisions = self.env['kojto.product.component.revision'].search([('component_id', 'in', component_ids)])
        if revisions:
            revisions._compute_component_revision_name()
        return result

    def action_open_revision_form(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Component Revision',
            'res_model': 'kojto.product.component.revision',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_lock(self):
        """Lock the revision and its linked revisions after confirmation."""
        self.ensure_one()
        if self.is_locked:
            raise UserError(f"Revision '{self.name}' is already locked.")
        self.write({'is_locked': True})
        return True

    def action_export_revision_tree(self):
        try:
            visited, edges, aggregated_attributes, lock_status = resolve_graph(
                start_revision=self,
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
                start_revision_id=self.id,
                revision_number=self.revision_number,
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
            raise UserError(f"Error exporting revision tree: {str(e)}")

    def copy_and_open(self):
        """Copy the revision with attributes and links, set is_locked=False, and open in a form view."""
        self.ensure_one()
        if not self.is_last_revision:
            raise ValidationError(
                f"Cannot copy revision '{self.name}' because it is not the latest revision. "
                f"Please create a new revision from the component view first."
            )

        # Create new revision through the component's action_create_revision
        new_revision = self.component_id.action_create_revision()

        # Copy links from the current revision to the new one
        for link in self.link_ids:
            self.env['kojto.product.component.revision.link'].create({
                'source_revision_id': new_revision.id,
                'target_subcode_id': link.target_subcode_id.id,
                'target_component_id': link.target_component_id.id,
                'quantity': link.quantity,
                'link_type': link.link_type,
                'link_description': link.link_description,
                'datetime_issue': fields.Datetime.now(),
            })

        # Return action to open new revision
        return {
            'type': 'ir.actions.act_window',
            'name': 'Component Revision',
            'res_model': 'kojto.product.component.revision',
            'res_id': new_revision.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def copy_revision(self):
        """Copy the revision with attributes and links, set is_locked=False."""
        self.ensure_one()
        if not self.is_last_revision:
            raise ValidationError(
                f"Cannot copy revision '{self.name}' because it is not the latest revision. "
                f"Please create a new revision from the component view first."
            )

        # Create new revision directly with copying context
        revision_vals = {
            'component_id': self.component_id.id,
            'datetime_issue': fields.Datetime.now(),
            'weight_attribute': self.weight_attribute,
            'length_attribute': self.length_attribute,
            'area_attribute': self.area_attribute,
            'volume_attribute': self.volume_attribute,
            'time_attribute': self.time_attribute,
            'price_attribute': self.price_attribute,
            'other_attribute': self.other_attribute,
        }

        # Create revision with copying context to bypass validation
        new_revision = self.env['kojto.product.component.revision'].with_context(copying_revision=True).create(revision_vals)

        # Copy all links from the current revision to the new one
        for link in self.link_ids:
            self.env['kojto.product.component.revision.link'].create({
                'source_revision_id': new_revision.id,
                'target_subcode_id': link.target_subcode_id.id,
                'target_component_id': link.target_component_id.id,
                'quantity': link.quantity,
                'link_type': link.link_type,
                'link_description': link.link_description,
                'datetime_issue': fields.Datetime.now(),
            })

        return True
