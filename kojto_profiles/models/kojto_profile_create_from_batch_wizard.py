#$ kojto_profiles/models/kojto_profile_create_from_batch_wizard.py

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from odoo.tools.translate import _
from datetime import datetime, timedelta
from collections import defaultdict
import logging

_logger = logging.getLogger(__name__)

class KojtoProfileCreateFromBatchWizard(models.TransientModel):
    _name = "kojto.profile.create.from.batch.wizard"
    _description = "Create from Batch Wizard"

    @api.model
    def _get_profile_domain(self):
        batch_id = self.env.context.get('default_batch_id') or self.env.context.get('active_id')
        if batch_id:
            batch = self.env['kojto.profile.batches'].browse(batch_id)
            if batch.exists():
                profile_ids = batch.batch_content_ids.mapped('profile_id').filtered(lambda p: p.exists()).ids
                return [('id', 'in', profile_ids)]
        return []

    @api.model
    def _get_shape_domain(self):
        batch_id = self.env.context.get('default_batch_id') or self.env.context.get('active_id')
        if batch_id:
            batch = self.env['kojto.profile.batches'].browse(batch_id)
            if batch.exists():
                self.env.cr.execute("""
                    SELECT DISTINCT si.shape_id
                    FROM kojto_profile_shape_inserts si
                    JOIN kojto_profile_batch_content bc ON bc.profile_id = si.profile_id
                    WHERE bc.batch_id = %s AND si.shape_id IS NOT NULL
                """, (batch_id,))
                shape_ids = [row[0] for row in self.env.cr.fetchall() if row[0]]
                return [('id', 'in', shape_ids)] if shape_ids else [('id', 'in', [])]
        return [('id', 'in', [])]

    def _compute_profile_domain(self):
        for wizard in self:
            if wizard.batch_id:
                profile_ids = wizard.batch_id.batch_content_ids.mapped('profile_id').filtered(lambda p: p.exists()).ids
                wizard.profile_domain = [('id', 'in', profile_ids)]
            else:
                wizard.profile_domain = []

    def _compute_shape_domain(self):
        for wizard in self:
            if wizard.batch_id:
                self.env.cr.execute("""
                    SELECT DISTINCT si.shape_id
                    FROM kojto_profile_shape_inserts si
                    JOIN kojto_profile_batch_content bc ON bc.profile_id = si.profile_id
                    WHERE bc.batch_id = %s AND si.shape_id IS NOT NULL
                """, (wizard.batch_id.id,))
                shape_ids = [row[0] for row in self.env.cr.fetchall() if row[0]]
                wizard.shape_domain = [('id', 'in', shape_ids)] if shape_ids else [('id', 'in', [])]
            else:
                wizard.shape_domain = [('id', 'in', [])]

    batch_id = fields.Many2one("kojto.profile.batches", string="Batch", required=True, readonly=True)
    profile_domain = fields.Char(compute="_compute_profile_domain", readonly=True, store=False)
    shape_domain = fields.Char(compute="_compute_shape_domain", readonly=True, store=False)
    profile_ids = fields.Many2many("kojto.profiles", string="Profiles", help="Select profiles to process from the batch.", domain="profile_domain")
    shape_ids = fields.Many2many("kojto.profile.shapes", string="Shapes", help="Select shapes associated with the profiles in the batch.", domain="shape_domain")

    @api.model
    def default_get(self, fields_list):
        res = super(KojtoProfileCreateFromBatchWizard, self).default_get(fields_list)
        batch_id = self.env.context.get('default_batch_id') or self.env.context.get('active_id')

        if batch_id:
            batch = self.env['kojto.profile.batches'].browse(batch_id)
            if not batch.exists():
                res['profile_ids'] = [(6, 0, [])]
                res['shape_ids'] = [(6, 0, [])]
                res['batch_id'] = False
                return res

            self.env.cr.execute("""
                SELECT DISTINCT profile_id
                FROM kojto_profile_batch_content
                WHERE batch_id = %s AND profile_id IS NOT NULL
            """, (batch_id,))
            profile_ids = [row[0] for row in self.env.cr.fetchall() if row[0]]
            res['profile_ids'] = [(6, 0, profile_ids)] if profile_ids else [(6, 0, [])]

            if 'shape_ids' in fields_list:
                self.env.cr.execute("""
                    SELECT DISTINCT si.shape_id
                    FROM kojto_profile_shape_inserts si
                    JOIN kojto_profile_batch_content bc ON bc.profile_id = si.profile_id
                    WHERE bc.batch_id = %s AND si.shape_id IS NOT NULL
                """, (batch_id,))
                shape_ids = [row[0] for row in self.env.cr.fetchall() if row[0]]
                res['shape_ids'] = [(6, 0, shape_ids)] if shape_ids else [(6, 0, [])]

            res['batch_id'] = batch_id
        else:
            res['profile_ids'] = [(6, 0, [])]
            res['shape_ids'] = [(6, 0, [])]

        return res

    @api.onchange('batch_id')
    def _onchange_batch_id(self):
        if self.batch_id:
            self.env.cr.execute("""
                SELECT DISTINCT profile_id
                FROM kojto_profile_batch_content
                WHERE batch_id = %s AND profile_id IS NOT NULL
            """, (self.batch_id.id,))
            profile_ids = [row[0] for row in self.env.cr.fetchall() if row[0]]

            self.env.cr.execute("""
                SELECT DISTINCT si.shape_id
                FROM kojto_profile_shape_inserts si
                JOIN kojto_profile_batch_content bc ON bc.profile_id = si.profile_id
                WHERE bc.batch_id = %s AND si.shape_id IS NOT NULL
            """, (self.batch_id.id,))
            shape_ids = [row[0] for row in self.env.cr.fetchall() if row[0]]

            self.profile_ids = [(6, 0, profile_ids)] if profile_ids else [(6, 0, [])]
            self.shape_ids = [(6, 0, shape_ids)] if shape_ids else [(6, 0, [])]
            return {
                'domain': {
                    'profile_ids': [('id', 'in', profile_ids)] if profile_ids else [],
                    'shape_ids': [('id', 'in', shape_ids)] if shape_ids else []
                }
            }
        return {'domain': {'profile_ids': [], 'shape_ids': []}}

    def action_create_1d_packages(self):
        self.ensure_one()
        if not self.profile_ids and not self.shape_ids:
            raise UserError(_("No profiles or shapes selected to create 1D optimization packages."))

        batch = self.batch_id
        created_packages = []

        # Process profiles
        for profile in self.profile_ids:
            contents = batch.batch_content_ids.filtered(lambda c: c.profile_id == profile)
            if not contents:
                continue

            bar_vals = []
            position = 1
            for content in contents:
                if not content.length or not content.quantity:
                    continue
                bar_vals.append({
                    "bar_position": str(position).zfill(3),
                    "bar_length": content.length,
                    "required_bar_pieces": content.quantity,
                    "bar_description": f"Bar for {profile.name}",
                })
                position += 1

            if not bar_vals:
                continue

            description = f"{profile.name} @ {batch.name} (P{profile.id})"
            existing_package = self.env["kojto.optimizer.1d.packages"].search([('description', '=', description)], limit=1)
            if existing_package:
                description = f"{description} {datetime.now().strftime('%Y%m%d%H%M%S')}"

            package_vals = {
                "subcode_id": batch.subcode_id.id if batch.subcode_id else False,
                "description": description,
                "bar_ids": [(0, 0, vals) for vals in bar_vals],
                "width_of_cut": 5.0,
                "initial_cut": 0.0,
                "final_cut": 0.0,
                "optimization_method": "best-fit",
            }

            try:
                new_package = self.env["kojto.optimizer.1d.packages"].create(package_vals)
                self.env.cr.commit()
                created_packages.append(new_package.id)
            except Exception as e:
                raise UserError(_("Failed to create 1D package for profile '%s': %s") % (profile.name, str(e)))

        # Process shapes
        for shape in self.shape_ids:
            shape_data = []
            for content in batch.batch_content_ids:
                profile = content.profile_id
                if not profile:
                    continue

                self.env.cr.execute("""
                    SELECT COUNT(si.id) as insert_count
                    FROM kojto_profile_shape_inserts si
                    WHERE si.profile_id = %s AND si.shape_id = %s
                """, (profile.id, shape.id))
                insert_count = self.env.cr.fetchone()[0] or 0
                if not insert_count:
                    continue

                if not content.length or not content.quantity:
                    continue
                total_length = (content.length or 0.0) + (content.length_extension or 0.0)
                shape_data.append({
                    'length': total_length,
                    'pcs': content.quantity * insert_count,
                    'position': content.position or '',
                })

            if not shape_data:
                continue

            consolidated_data = defaultdict(lambda: {'length': 0, 'pcs': 0, 'positions': set()})
            for data in shape_data:
                key = data['length']
                consolidated_data[key]['length'] = data['length']
                consolidated_data[key]['pcs'] += data['pcs']
                consolidated_data[key]['positions'].add(data['position'])

            bar_vals = []
            position = 1
            for key, data in consolidated_data.items():
                bar_vals.append({
                    "bar_position": str(position).zfill(3),
                    "bar_length": data['length'],
                    "required_bar_pieces": data['pcs'],
                    "bar_description": f"Shape bar for {shape.name}",
                })
                position += 1

            description = f"Shape {shape.name} @ {batch.name} (S{shape.id})"
            existing_package = self.env["kojto.optimizer.1d.packages"].search([('description', '=', description)], limit=1)
            if existing_package:
                description = f"{description} {datetime.now().strftime('%Y%m%d%H%M%S')}"

            package_vals = {
                "subcode_id": batch.subcode_id.id if batch.subcode_id else False,
                "description": description,
                "bar_ids": [(0, 0, vals) for vals in bar_vals],
                "width_of_cut": 5.0,
                "initial_cut": 0.0,
                "final_cut": 0.0,
                "optimization_method": "best-fit",
            }

            try:
                new_package = self.env["kojto.optimizer.1d.packages"].create(package_vals)
                self.env.cr.commit()
                created_packages.append(new_package.id)
            except Exception as e:
                raise UserError(_("Failed to create 1D package for shape '%s': %s") % (shape.name, str(e)))

        if not created_packages:
            raise UserError(_("No 1D optimization packages were created. Please verify the batch contents have valid length and quantity."))

        return {
            "type": "ir.actions.act_window",
            "name": _("1D Optimization Packages for %s") % batch.name,
            "res_model": "kojto.optimizer.1d.packages",
            "view_mode": "list,form",
            "domain": [("id", "in", created_packages)],
            "target": "current",
        }

    def action_create_2dr_packages(self):
        self.ensure_one()
        if not self.profile_ids:
            raise UserError(_("No profiles selected to create 2DR optimization packages."))

        batch = self.batch_id
        strip_data = []

        for profile in self.profile_ids:
            contents = batch.batch_content_ids.filtered(lambda c: c.profile_id == profile)
            if not contents:
                continue

            for content in contents:
                profile = content.profile_id
                if not (hasattr(profile, 'strip_ids') and profile.strip_ids):
                    continue
                total_length = (content.length or 0.0) + (content.length_extension or 0.0)
                quantity = content.quantity or 0
                if not total_length or not quantity:
                    continue
                material_id = content.material_id.id if content.material_id else False
                for strip in profile.strip_ids:
                    thickness = strip.thickness if strip.thickness else 0.0
                    projected_length = strip.projected_length or 0.0
                    if not projected_length:
                        continue
                    strip_data.append({
                        'strip': strip,
                        'thickness': thickness,
                        'material_id': material_id,
                        'width': projected_length,
                        'length': total_length,
                        'quantity': quantity,
                        'profile_name': profile.name or '',
                    })

        if not strip_data:
            raise UserError(_("No valid strips found for 2DR optimization. Please ensure selected profiles have strips with valid dimensions."))

        thickness_material_groups = {}
        for data in strip_data:
            thickness = data['thickness']
            material_id = data['material_id']
            key = (thickness, material_id)
            if key not in thickness_material_groups:
                thickness_material_groups[key] = []
            thickness_material_groups[key].append(data)

        created_packages = []
        for (thickness, material_id), strips in thickness_material_groups.items():
            cut_rectangle_vals = []
            position = 1
            for strip_info in strips:
                cut_rectangle_vals.append({
                    "cut_position": str(position).zfill(3),
                    "cut_description": f"Strip from {strip_info['profile_name']}",
                    "cut_width": strip_info['width'],
                    "cut_length": strip_info['length'],
                    "required_cut_rectangle_pieces": int(strip_info['quantity']),
                })
                position += 1

            material_name = self.env["kojto.base.material.grades"].browse(material_id).name if material_id else "No Material"
            description = f"Thickness {thickness}mm, Material {material_name} @ {batch.name}"
            package_vals = {
                "subcode_id": batch.subcode_id.id if getattr(batch, 'subcode_id', False) else False,
                "thickness": thickness,
                "material_id": material_id,
                "description": description,
                "cutted_rectangles_ids": [(0, 0, vals) for vals in cut_rectangle_vals],
                "width_of_cut": 5.0,
                "optimization_method": "maxrects_bssf",
            }

            try:
                new_package = self.env["kojto.optimizer.2dr.packages"].create(package_vals)
                self.env.cr.commit()
                created_packages.append(new_package.id)
            except Exception as e:
                raise UserError(_("Failed to create 2DR package for thickness %smm: %s") % (thickness, str(e)))

        if not created_packages:
            raise UserError(_("No 2DR optimization packages were created. Please verify strip data for selected profiles."))

        return {
            "type": "ir.actions.act_window",
            "name": _("2DR Optimization Packages for %s") % batch.name,
            "res_model": "kojto.optimizer.2dr.packages",
            "view_mode": "list,form",
            "domain": [("id", "in", created_packages)],
            "target": "current",
        }

    def action_create_offer(self):
        self.ensure_one()
        if not self.profile_ids:
            raise UserError(_("No profiles selected to create an offer."))

        batch = self.batch_id
        content_lines = []
        errors = []

        seen_contents = set()
        for profile in self.profile_ids:
            contents = batch.batch_content_ids.filtered(lambda c: c.profile_id == profile)
            if not contents:
                errors.append(_("- Profile '%s': No associated content found in the batch.") % profile.name)
                continue

            for content in contents:
                content_key = (content.profile_id.id, content.quantity, content.length, content.position)
                if content_key in seen_contents:
                    continue
                seen_contents.add(content_key)

                if not content.total_profile_weight_net or not content.total_profile_length_net:
                    errors.append(_("- Profile '%s', Content ID %s: Invalid weight (%s) or length (%s).") %
                                  (profile.name, content.id, content.total_profile_weight_net or 'None',
                                   content.total_profile_length_net or 'None'))
                    continue

                # Validate content values before creating lines
                if not content.total_profile_weight_net or content.total_profile_weight_net <= 0:
                    errors.append(_("- Profile '%s': Invalid weight (%s).") % (profile.name, content.total_profile_weight_net or 'None'))
                    continue

                if not content.total_profile_length_net or content.total_profile_length_net <= 0:
                    errors.append(_("- Profile '%s': Invalid length (%s).") % (profile.name, content.total_profile_length_net or 'None'))
                    continue

                if not content.number_ext_corners or content.number_ext_corners < 0:
                    errors.append(_("- Profile '%s': Invalid number of external corners (%s).") % (profile.name, content.number_ext_corners or 'None'))
                    continue

                if not content.coating_perimeter or content.coating_perimeter <= 0:
                    errors.append(_("- Profile '%s': Invalid coating perimeter (%s).") % (profile.name, content.coating_perimeter or 'None'))
                    continue

                # Get unit IDs by name to avoid hardcoded IDs, with fallback to hardcoded IDs
                weight_unit = self.env['kojto.base.units'].search([('name', '=', 'kg')], limit=1)
                if not weight_unit:
                    weight_unit = self.env['kojto.base.units'].browse(14)  # Fallback to hardcoded ID

                length_unit = self.env['kojto.base.units'].search([('name', '=', 'm')], limit=1)
                if not length_unit:
                    length_unit = self.env['kojto.base.units'].browse(9)  # Fallback to hardcoded ID

                area_unit = self.env['kojto.base.units'].search([('name', '=', 'm2')], limit=1)
                if not area_unit:
                    area_unit = self.env['kojto.base.units'].browse(17)  # Fallback to hardcoded ID

                if not weight_unit.exists() or not length_unit.exists() or not area_unit.exists():
                    errors.append(_("- Required units (kg, m, m2) not found in the system."))
                    continue

                # Create content line for weight
                weight_content = {
                    "name": f"{content.profile_id.name} {content.length} {content.quantity}pcs",
                    "position": content.position,
                    "quantity": content.total_profile_weight_net,
                    "unit_id": weight_unit.id,
                    "unit_price": 0.0,  # Default unit price
                    "vat_rate": 0.0,  # Default VAT rate
                }
                content_lines.append((0, 0, weight_content))

                # Create content line for chamfers
                chamfer_content = {
                    "name": f"{content.profile_id.name} chamfers",
                    "position": f"{content.position}ch",
                    "quantity": content.total_profile_length_net * content.number_ext_corners,
                    "unit_id": length_unit.id,  # Length unit for chamfers
                    "unit_price": 0.0,  # Default unit price
                    "vat_rate": 0.0,  # Default VAT rate
                }
                content_lines.append((0, 0, chamfer_content))

                # Create content line for coating
                coating_content = {
                    "name": f"{content.profile_id.name} coating",
                    "position": f"{content.position}co",
                    "quantity": (content.total_profile_length_net * content.coating_perimeter) / 1000,
                    "unit_id": area_unit.id,  # Area unit (m²) for coating
                    "unit_price": 0.0,  # Default unit price
                    "vat_rate": 0.0,  # Default VAT rate
                }
                content_lines.append((0, 0, coating_content))

        if not content_lines:
            error_message = _("Unable to create offer due to the following issues:\n%s") % "\n".join(errors) if errors else \
                            _("No valid content found for the selected profiles. Please check the batch content.")
            raise UserError(error_message)

        # Validate required fields
        if not batch.subcode_id:
            raise UserError(_("Failed to create offer: Batch ID %s does not have a valid subcode.") % batch.id)

        if not batch.subcode_id.code_id:
            raise UserError(_("Failed to create offer: Subcode '%s' does not have a valid code.") % batch.subcode_id.name)

        # Try to get company from batch first, then fallback to default company contact
        company_id = False
        if getattr(batch, 'company_id', False) and batch.company_id:
            company_id = batch.company_id.id
        else:
            company_contact = self.env['kojto.contacts'].search([('res_company_id', '=', self.env.company.id)], limit=1)
            if company_contact:
                company_id = company_contact.id
            else:
                # Try to find any company contact
                any_company = self.env['kojto.contacts'].search([('contact_type', '=', 'company')], limit=1)
                if any_company:
                    company_id = any_company.id
                else:
                    raise UserError(_("Failed to create offer: No company contact found. Please ensure there is at least one company contact in the system."))

        # Set counterparty ID to 1
        counterparty_id = 1
        counterparty_contact = self.env['kojto.contacts'].browse(counterparty_id)
        if not counterparty_contact.exists():
            raise UserError(_("Failed to create offer: Customer contact ID %s does not exist.") % counterparty_id)

        # Try to get payment terms ID 1, if not available find the first one
        payment_terms_id = 1
        payment_terms = self.env['kojto.base.payment.terms'].browse(payment_terms_id)
        if not payment_terms.exists():
            # Try to find the first available payment terms
            first_payment_terms = self.env['kojto.base.payment.terms'].search([], limit=1)
            if first_payment_terms:
                payment_terms_id = first_payment_terms.id
            else:
                # Create a default payment term if none exist
                try:
                    payment_terms = self.env['kojto.base.payment.terms'].create({
                        'name': 'Standard Payment Terms',
                        'abbreviation': 'STD',
                        'description': 'Standard payment terms for offers',
                        'language_id': self.env.ref("base.lang_en").id,
                    })
                    payment_terms_id = payment_terms.id
                except Exception as e:
                    raise UserError(_("Failed to create offer: No payment terms found and unable to create default payment terms. Error: %s") % str(e))

        offer_vals = {
            "subject": f"Offer for Batch {batch.name or batch.id}",
            "subcode_id": batch.subcode_id.id,
            "payment_terms_id": payment_terms_id,
            "counterparty_id": counterparty_id,
            "company_id": company_id,
            "document_in_out_type": "outgoing",
            "currency_id": self.env.company.currency_id.id,
            "language_id": self.env.ref("base.lang_en").id,
            "datetime_issue": datetime.now(),
            "datetime_end": datetime.now() + timedelta(days=7),
            "content": content_lines,
        }

        try:
            new_offer = self.env["kojto.offers"].create(offer_vals)

            # Verify the offer was created correctly

        except ValidationError as e:
            raise UserError(_("Cannot create offer: %s") % str(e))
        except Exception as e:
            import traceback
            raise UserError(_("Failed to create offer for batch ID %s. Please ensure valid company and payment terms are set. Error: %s") % (batch.id, str(e)))

        action = {
            "type": "ir.actions.act_window",
            "name": _("Offer for %s") % batch.name,
            "res_model": "kojto.offers",
            "view_mode": "form",
            "res_id": new_offer.id,
            "target": "current",
        }
        return action
