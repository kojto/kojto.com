# kojto_products/models/kojto_product_component_revision_links.py
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from ..utils.kojto_products_graph_utils import resolve_graph

class KojtoProductComponentRevisionLink(models.Model):
    _name = 'kojto.product.component.revision.link'
    _description = 'Kojto Product Component Revision Link'

    is_locked = fields.Boolean(string='Locked', related='source_revision_id.is_locked', readonly=True, store=False)
    is_last_revision = fields.Boolean(string='Last Revision', related='source_revision_id.is_last_revision', readonly=True, store=False)
    source_revision_id = fields.Many2one('kojto.product.component.revision', required=True, ondelete='cascade', index=True)
    target_subcode_id = fields.Many2one('kojto.commission.subcodes', string='Target Subcode', required=True)
    target_component_id = fields.Many2one('kojto.product.component', required=True, ondelete='cascade', index=True)
    datetime_issue = fields.Datetime(required=True, default=fields.Datetime.now)
    target_latest_revision_id = fields.Many2one('kojto.product.component.revision', string='Target Latest Revision', related='target_component_id.latest_revision_id', store=True)
    quantity = fields.Float(default=1.0, index=True)
    link_type = fields.Selection([('welded', 'Welded'), ('assembled', 'Assembled'), ('other', 'Other')], string='Link Type', default='other')
    link_description = fields.Text()
    last_cycle_check = fields.Text(string='Last Cycle Check', readonly=True, help="Details of the last cycle detection attempt")
    unit_id = fields.Many2one('kojto.base.units', string='Unit', related='target_component_id.unit_id', readonly=True, store=False)

    _sql_constraints = [
        ('unique_source_target', 'unique(source_revision_id, target_component_id)', 'A link between these components already exists.')
    ]

    @api.constrains('quantity')
    def _check_positive_quantity(self):
        for record in self:
            if record.quantity <= 0:
                raise ValidationError(f"Quantity for link ID {record.id} must be positive.")

    @api.constrains('source_revision_id', 'target_component_id')
    def _check_revision_status(self):
        for record in self:
            # Check if source revision is the latest revision
            if not record.source_revision_id.is_last_revision:
                raise ValidationError("Links can only be created from the latest revision of a component.")

            # Check if target component's latest revision is being used
            target_latest_revision = record.target_component_id.latest_revision_id
            if not target_latest_revision or not target_latest_revision.is_last_revision:
                raise ValidationError("Links can only be created to components with a latest revision.")

    @api.model
    def create(self, vals_list):
        # Handle both single dict and list of dicts
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        # ✓ OPTIMIZED: Batch fetch all revisions and components at once
        source_revision_ids = [v.get('source_revision_id') for v in vals_list]
        target_component_ids = [v.get('target_component_id') for v in vals_list]
        
        source_revisions = self.env['kojto.product.component.revision'].browse(source_revision_ids)
        target_components = self.env['kojto.product.component'].browse(target_component_ids)
        
        # Create lookup maps to avoid repeated queries
        revision_map = {r.id: r for r in source_revisions}
        component_map = {c.id: c for c in target_components}
        
        # ✓ Batch validation
        for vals in vals_list:
            src_rev = revision_map.get(vals.get('source_revision_id'))
            tgt_comp = component_map.get(vals.get('target_component_id'))
            
            if src_rev and not src_rev.is_last_revision:
                raise ValidationError("Links can only be created from the latest revision of a component.")
            
            if not tgt_comp or not tgt_comp.latest_revision_id:
                raise ValidationError("Links can only be created to components with a latest revision.")

        # Create all records at once
        records = super().create(vals_list)

        # Perform post-creation validation if needed (batch cycles for small batches)
        if not self.env.context.get('skip_cycle_check'):
            # Only run cycle checks on smaller batches to avoid timeout
            if len(records) <= 50:
                for record in records:
                    record._validate_links()
                    record._check_self_referential()
                    record._check_no_cycle()

        return records

    def write(self, vals):
        # Check if source revision is the latest revision
        if 'source_revision_id' in vals:
            source_revision = self.env['kojto.product.component.revision'].browse(vals['source_revision_id'])
            if not source_revision.is_last_revision:
                raise ValidationError("Links can only be created from the latest revision of a component.")

        # Check if target component's latest revision is being used
        if 'target_component_id' in vals:
            target_component = self.env['kojto.product.component'].browse(vals['target_component_id'])
            if not target_component.latest_revision_id or not target_component.latest_revision_id.is_last_revision:
                raise ValidationError("Links can only be created to components with a latest revision.")

        # Prevent changes to locked links or non-latest revisions, except for is_locked and datetime_locked in locking_tree context, or last_cycle_check in skip_cycle_check context
        for record in self:
            if (record.is_locked or not record.source_revision_id.is_last_revision) and not (
                self.env.context.get('locking_tree') and set(vals.keys()).issubset({'is_locked', 'datetime_locked'})
                or self.env.context.get('skip_cycle_check') and list(vals.keys()) == ['last_cycle_check']
            ):
                raise ValidationError(
                    f"Cannot modify link (ID {record.id}): Link is either locked or from a non-latest revision and cannot be changed."
                )
        # Set datetime_locked when is_locked is set to True
        if vals.get('is_locked') is True and not vals.get('datetime_locked'):
            vals['datetime_locked'] = fields.Datetime.now()
        super().write(vals)
        if not self.env.context.get('skip_cycle_check'):
            self._validate_links()
            self._check_self_referential()
            self._check_no_cycle()
        return True

    def unlink(self):
        # Check if source revision is the latest revision
        for record in self:
            if not record.source_revision_id.is_last_revision:
                raise ValidationError("Links can only be deleted from the latest revision of a component.")
            if record.is_locked:
                raise ValidationError(
                    f"Cannot delete link (ID {record.id}): Link is locked and cannot be deleted."
                )
            if not self.env.context.get('skip_cycle_check'):
                record._validate_links()
        return super().unlink()

    def _validate_links(self):
        """Validate link integrity before creating, editing, or deleting."""
        for record in self:
            if not record.source_revision_id.exists():
                raise ValidationError(
                    f"Invalid link (ID {record.id}): Source revision {record.source_revision_id.name} does not exist."
                )
            if not record.target_component_id.exists():
                raise ValidationError(
                    f"Invalid link (ID {record.id}): Target component {record.target_component_id.name} does not exist."
                )
            if not record.target_component_id.revision_ids:
                raise ValidationError(
                    f"Invalid link (ID {record.id}): Target component {record.target_component_id.name} has no revisions."
                )
            source_component = record.source_revision_id.component_id
            latest_revision = source_component.get_latest_revision()
            if latest_revision != record.source_revision_id:
                raise ValidationError(
                    f"Invalid link (ID {record.id}): Source revision {record.source_revision_id.name} is not the latest revision "
                    f"of component {source_component.name}. Only the latest revision can be used to create, edit, or delete links."
                )
            target_latest_revision = record.target_component_id.get_latest_revision() if record.target_component_id else False
            if not target_latest_revision:
                raise ValidationError(
                    f"Invalid link (ID {record.id}): No valid latest revision for target component {record.target_component_id.name}."
                )
            if record.target_component_id == source_component or target_latest_revision == record.source_revision_id:
                record._update_cycle_check(
                    f"Attempted self-referential link: Link ID {record.id}, "
                    f"Source {record.source_revision_id.name}, Target {record.target_component_id.name}, "
                    f"Resolves to {target_latest_revision.name}"
                )
                raise ValidationError(
                    f"Cannot create or update link (ID {record.id}): Self-referential link from "
                    f"{record.source_revision_id.name} to itself via target component "
                    f"{record.target_component_id.name} (resolves to {target_latest_revision.name})."
                )

    def _update_cycle_check(self, message):
        """Update last_cycle_check without triggering validation."""
        self.with_context(skip_cycle_check=True).sudo().write({'last_cycle_check': message})

    @api.constrains('source_revision_id', 'target_component_id')
    def _check_self_referential(self):
        if self.env.context.get('skip_cycle_check'):
            return
        for record in self:
            source_component = record.source_revision_id.component_id
            if record.target_component_id == source_component:
                target_latest_revision = record.target_component_id.get_latest_revision()
                if target_latest_revision and target_latest_revision == record.source_revision_id:
                    raise ValidationError(
                        f"Cannot create or update link (ID {record.id}): Self-referential link from "
                        f"{record.source_revision_id.name} to itself via target component "
                        f"{record.target_component_id.name} (resolves to {target_latest_revision.name}) would cause a cycle."
                    )

    @api.constrains('source_revision_id', 'target_component_id')
    def _check_no_cycle(self):
        if self.env.context.get('skip_cycle_check'):
            return
        for record in self:
            if record.source_revision_id:
                has_cycle, cycle_path = resolve_graph(start_revision=record.source_revision_id, env=self.env, mode='cycle')
                if has_cycle:
                    cycle_revision_names = cycle_path.split(' -> ')
                    links = self.env['kojto.product.component.revision.link'].search([
                        ('source_revision_id', 'in', [
                            r.id for r in self.env['kojto.product.component.revision'].search([
                                ('name', 'in', cycle_revision_names)
                            ])
                        ]),
                        ('target_component_id', 'in', [
                            c.id for c in self.env['kojto.product.component'].search([])
                        ])
                    ])
                    cycle_links = []
                    for link in links:
                        target_latest = link.target_component_id.get_latest_revision()
                        if target_latest and target_latest.name in cycle_revision_names:
                            cycle_links.append(
                                f"Link ID {link.id}: {link.source_revision_id.name} -> "
                                f"{link.target_component_id.name} (resolves to {target_latest.name})"
                            )
                    cycle_message = (
                        f"Link ID {record.id}: {cycle_path}\n"
                        f"Source: {record.source_revision_id.name}, Target: {record.target_component_id.name}\n"
                        f"Cycle links found: {'; '.join(cycle_links) if cycle_links else 'None'}"
                    )
                    record._update_cycle_check(cycle_message)
                    delete_suggestion = (
                        f"DELETE FROM kojto_product_component_revision_link WHERE id = {record.id};"
                        if self.env['kojto.product.component.revision.link'].search([('id', '=', record.id)])
                        else "Link not found; check other links in cycle path."
                    )
                    raise UserError(
                        f"Cycle detected in component links: {cycle_path}\n"
                        f"Link ID: {record.id}, Source: {record.source_revision_id.name}, "
                        f"Target: {record.target_component_id.name}\n"
                        f"Cycle links: {'; '.join(cycle_links) if cycle_links else 'None'}\n"
                    )

    @api.constrains('target_component_id')
    def _check_target_component_id(self):
        for rec in self:
            parent = rec.source_revision_id
            if not parent:
                continue
            if rec.target_component_id == parent.component_id:
                raise ValidationError("You cannot link to the same component.")
            duplicates = parent.link_ids.filtered(
                lambda l: l.id != rec.id and l.target_component_id == rec.target_component_id
            )
            if duplicates:
                raise ValidationError("This component is already linked.")

    def action_open_revision_form(self):
        """Open the target component's latest revision in a form view."""
        self.ensure_one()
        if not self.target_component_id or not self.target_component_id.latest_revision_id:
            raise UserError("No revision available to open.")
        return {
            'type': 'ir.actions.act_window',
            'name': 'Component Revision',
            'res_model': 'kojto.product.component.revision',
            'res_id': self.target_component_id.latest_revision_id.id,
            'view_mode': 'form',
            'target': 'new',
        }
