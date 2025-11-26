# kojto_products/models/wizards/kojto_product_import_wizard.py
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta

class KojtoProductImportWizard(models.TransientModel):
    _name = 'kojto.product.import.wizard'
    _description = 'Kojto Product Import Wizard'

    import_data = fields.Text(string='Import Data', required=True)

    def _validate_line(self, line, line_num, current_component_name, valid_link_types):
        # Split strictly by tabs and ensure at least 11 columns (added component_type)
        fields = line.rstrip().split('\t')
        if len(fields) < 11:
            return None, f"Line {line_num}: Expected at least 11 tab-separated columns, found {len(fields)}."
        # Pad with empty strings to ensure 17 columns (16 + component_type)
        fields = [f.strip() for f in fields] + [""] * (17 - len(fields))
        # Valid component types
        valid_component_types = {'package', 'standard_part', 'part', 'drawing', 'process', 'other'}
        # Validate fields
        if fields[0]:
            if not all(fields[i] for i in [0, 2, 3]):
                return None, f"Line {line_num}: Name, Unit ID, and Subcode required."
            subcode = self.env['kojto.commission.subcodes'].search([('name', '=', fields[3])], limit=1)
            if not subcode:
                return None, f"Line {line_num}: Subcode '{fields[3]}' not found."
            unit = self.env['kojto.base.units'].search([('name', '=', fields[2])], limit=1)
            if not unit:
                return None, f"Line {line_num}: Unit ID '{fields[2]}' not found."
            if fields[4] and fields[4] not in valid_component_types:
                return None, f"Line {line_num}: Invalid component_type '{fields[4]}'. Must be one of {', '.join(valid_component_types)}."
            for idx, name in [(5, 'weight'), (6, 'length'), (7, 'area'), (8, 'volume'), (9, 'price'), (10, 'time'), (11, 'other_attribute')]:
                if fields[idx] and not fields[idx].replace('.', '', 1).isdigit():
                    return None, f"Line {line_num}: Invalid {name} '{fields[idx]}'."
            target_subcode = None
            if fields[12]:
                target_subcode = self.env['kojto.commission.subcodes'].search([('name', '=', fields[12])], limit=1)
                if not target_subcode:
                    return None, f"Line {line_num}: Target Subcode '{fields[12]}' not found."
            if fields[13]:
                if not fields[14] or not fields[14].replace('.', '', 1).isdigit():
                    return None, f"Line {line_num}: Link requires valid quantity."
                if fields[15] and fields[15] not in valid_link_types:
                    return None, f"Line {line_num}: Invalid link_type '{fields[15]}'."
            return {
                'type': 'component',
                'fields': fields,
                'subcode': subcode,
                'unit': unit,
                'target_subcode': target_subcode
            }, None
        elif fields[13]:
            if fields[0]:
                return None, f"Line {line_num}: Name must be empty for link-only line."
            if not fields[14] or not fields[14].replace('.', '', 1).isdigit():
                return None, f"Line {line_num}: Link requires valid quantity."
            if fields[15] and fields[15] not in valid_link_types:
                return None, f"Line {line_num}: Invalid link_type '{fields[15]}'."
            if not current_component_name:
                return None, f"Line {line_num}: Link-only line before component."
            target_subcode = None
            if fields[12]:
                target_subcode = self.env['kojto.commission.subcodes'].search([('name', '=', fields[12])], limit=1)
                if not target_subcode:
                    return None, f"Line {line_num}: Target Subcode '{fields[12]}' not found."
            return {
                'type': 'link',
                'fields': fields,
                'component_name': current_component_name,
                'target_subcode': target_subcode
            }, None
        return None, f"Line {line_num}: Invalid line; must define component or link."

    def action_import(self):
        self.ensure_one()
        lines = self.import_data.strip().split('\n')
        if not lines:
            raise ValidationError("No data provided.")
        valid_link_types = {'welded', 'assembled', 'other'}
        errors = []
        component_definitions = {}
        component_lines = []
        link_lines = []
        current_component_name = None

        # Parse and validate input lines
        for line_num, line in enumerate(lines, 1):
            if not line.strip():
                continue
            result, error = self._validate_line(line, line_num, current_component_name, valid_link_types)
            if error:
                errors.append(error)
                continue
            if result['type'] == 'component':
                fields = result['fields']
                component_definitions[fields[0]] = {
                    'subcode': result['subcode'],
                    'unit_id': result['unit'],
                    'component_type': fields[4] or 'package',  # Default to 'package' if empty
                    'weight_attribute': float(fields[5]) if fields[5] else 0.0,
                    'length_attribute': float(fields[6]) if fields[6] else 0.0,
                    'area_attribute': float(fields[7]) if fields[7] else 0.0,
                    'volume_attribute': float(fields[8]) if fields[8] else 0.0,
                    'price_attribute': float(fields[9]) if fields[9] else 0.0,
                    'time_attribute': float(fields[10]) if fields[10] else 0.0,
                    'other_attribute': float(fields[11]) if fields[11] else 0.0,
                    'links': [{
                        'target_subcode': result['target_subcode'],
                        'target_component': fields[13],
                        'quantity': float(fields[14]) if fields[14] else 0.0,
                        'link_type': fields[15] or None,
                        'link_description': fields[16] or None
                    }] if fields[13] else []
                }
                current_component_name = fields[0]
                component_lines.append({'line_num': line_num, 'name': fields[0]})
            else:
                fields = result['fields']
                link_lines.append({
                    'line_num': line_num,
                    'target_subcode': result['target_subcode'],
                    'target_component': fields[13],
                    'quantity': float(fields[14]) if fields[14] else 0.0,
                    'link_type': fields[15] or None,
                    'link_description': fields[16] or None,
                    'component_name': current_component_name
                })

        if not component_definitions:
            errors.append("No valid components found.")
        if errors:
            raise ValidationError("\n".join(errors))

        components = {}
        new_components = set()

        # Create or retrieve components
        for name, data in component_definitions.items():
            component = self.env['kojto.product.component'].search(
                [('name', '=', name), ('subcode_id', '=', data['subcode'].id)], limit=1
            )
            if not component:
                component = self.env['kojto.product.component'].create({
                    'name': name,
                    'subcode_id': data['subcode'].id,
                    'unit_id': data['unit_id'].id,
                    'component_type': data['component_type']
                })
                new_components.add(name)
            components[name] = component

        # Process revisions
        for name, data in component_definitions.items():
            component = components[name]
            latest_revision = component.get_latest_revision()

            # For new components, update the initial revision
            if name in new_components:
                if latest_revision:
                    latest_revision.write({
                        'weight_attribute': data['weight_attribute'],
                        'length_attribute': data['length_attribute'],
                        'area_attribute': data['area_attribute'],
                        'volume_attribute': data['volume_attribute'],
                        'price_attribute': data['price_attribute'],
                        'time_attribute': data['time_attribute'],
                        'other_attribute': data['other_attribute'],
                        'datetime_issue': datetime.now()
                    })
                components[name] = {'component': component, 'revision': latest_revision}
                continue

            # Check if a new revision is needed
            params_differ = latest_revision and (
                any(abs(latest_revision[field] - data[field]) >= 0.0001 for field in ['weight_attribute', 'length_attribute', 'area_attribute', 'volume_attribute', 'price_attribute', 'time_attribute', 'other_attribute'])
            )
            db_links = latest_revision.link_ids if latest_revision else []
            import_links = data['links']
            links_differ = len(db_links) != len(import_links)

            if not links_differ and import_links:
                for import_link in import_links:
                    target_subcode_id = import_link['target_subcode'].id if import_link['target_subcode'] else component.subcode_id.id
                    target = components.get(import_link['target_component']) or self.env['kojto.product.component'].search([
                        ('name', '=', import_link['target_component']),
                        ('subcode_id', '=', target_subcode_id)
                    ], limit=1)
                    if not target:
                        links_differ = True
                        break
                    if not db_links.filtered(
                        lambda l: l.target_component_id == target and
                                  l.target_subcode_id.id == target_subcode_id and
                                  abs(l.quantity - import_link['quantity']) < 0.0001 and
                                  l.link_type == import_link['link_type'] and
                                  l.link_description == import_link['link_description']
                    ):
                        links_differ = True
                        break

            if params_differ or links_differ or not latest_revision:
                latest_revision = self.env['kojto.product.component.revision'].create({
                    'component_id': component.id,
                    'weight_attribute': data['weight_attribute'],
                    'length_attribute': data['length_attribute'],
                    'area_attribute': data['area_attribute'],
                    'volume_attribute': data['volume_attribute'],
                    'price_attribute': data['price_attribute'],
                    'time_attribute': data['time_attribute'],
                    'other_attribute': data['other_attribute'],
                    'datetime_issue': datetime.now()
                })
            components[name] = {'component': component, 'revision': latest_revision}

        # Process links
        target_components_cache = {}
        for line in component_lines + link_lines:
            component_name = line['name'] if 'name' in line else line['component_name']
            component = components[component_name]['component']
            revision = components[component_name]['revision']
            links = component_definitions[component_name]['links'] if 'name' in line else [{
                'target_subcode': line['target_subcode'],
                'target_component': line['target_component'],
                'quantity': line['quantity'],
                'link_type': line['link_type'],
                'link_description': line['link_description']
            }]

            for link_data in links:
                if not link_data['target_component']:
                    continue
                target_subcode_id = link_data['target_subcode'].id if link_data['target_subcode'] else component.subcode_id.id
                cache_key = (link_data['target_component'], target_subcode_id)
                if cache_key in target_components_cache:
                    target_component = target_components_cache[cache_key]
                else:
                    target_component = components.get(link_data['target_component']) or self.env['kojto.product.component'].search([
                        ('name', '=', link_data['target_component']),
                        ('subcode_id', '=', target_subcode_id)
                    ], limit=1)
                    if not target_component:
                        target_component = self.env['kojto.product.component'].create({
                            'name': link_data['target_component'],
                            'subcode_id': target_subcode_id,
                            'unit_id': component_definitions[component_name]['unit_id'].id,
                            'component_type': 'package'  # Default for new target components
                        })
                        target_revision = target_component.get_latest_revision()
                        if target_revision:
                            target_revision.write({
                                'weight_attribute': 0.0,
                                'length_attribute': 0.0,
                                'area_attribute': 0.0,
                                'volume_attribute': 0.0,
                                'price_attribute': 0.0,
                                'time_attribute': 0.0,
                                'other_attribute': 0.0,
                                'datetime_issue': datetime.now()
                            })
                    target_components_cache[cache_key] = target_component
                self.env['kojto.product.component.revision.link'].create({
                    'source_revision_id': revision.id,
                    'target_component_id': target_component.id,
                    'target_subcode_id': target_subcode_id,
                    'quantity': link_data['quantity'],
                    'link_type': link_data['link_type'],
                    'link_description': link_data['link_description']
                })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'kojto.product.component',
            'view_mode': 'list,form',
            'views': [(self.env.ref('kojto_products.component_list_view').id, 'list')],
            'name': 'Components',
            'target': 'current',
        }

