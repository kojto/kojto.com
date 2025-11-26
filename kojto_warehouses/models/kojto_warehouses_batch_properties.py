from odoo import models, fields, api
from odoo.exceptions import ValidationError

class KojtoWarehousesBatchProperties(models.Model):
    _name = 'kojto.warehouses.batch.properties'
    _description = 'Kojto Warehouses Batch Properties'
    _rec_name = 'chemical_composition_summary'

    name = fields.Char(string='Properties Name', default="from batch certificate", required=True)
    batch_id = fields.Many2one("kojto.warehouses.batches", string="Batch", required=True, ondelete="cascade")
    chemical_composition_summary = fields.Text(string='Chemical Composition Summary', compute='_compute_chemical_composition_summary')
    mechanical_properties_summary = fields.Text(string='Mechanical Properties Summary', compute='_compute_mechanical_properties_summary')
    material_grade_id = fields.Many2one("kojto.base.material.grades", string="Material Grade", related="batch_id.material_id", store=True, readonly=True)

    heat_number = fields.Char(string='Heat Number')

    # Chemical Composition Fields
    carbon = fields.Float(string='C %', help="Carbon", default=0.0, digits=(6, 3))
    silicon = fields.Float(string='Si %', help="Silicon", default=0.0, digits=(6, 3))
    manganese = fields.Float(string='Mn %', help="Manganese", default=0.0, digits=(6, 3))
    chromium = fields.Float(string='Cr %', help="Chromium", default=0.0, digits=(6, 3))
    molybdenum = fields.Float(string='Mo %', help="Molybdenum", default=0.0, digits=(6, 3))
    vanadium = fields.Float(string='V %', help="Vanadium", default=0.0, digits=(6, 3))
    nickel = fields.Float(string='Ni %', help="Nickel", default=0.0, digits=(6, 3))
    copper = fields.Float(string='Cu %', help="Copper", default=0.0, digits=(6, 3))
    phosphorus = fields.Float(string='P %', help="Phosphorus", default=0.0, digits=(6, 3))
    sulfur = fields.Float(string='S %', help="Sulfur", default=0.0, digits=(6, 3))
    nitrogen = fields.Float(string='N %', help="Nitrogen", default=0.0, digits=(6, 3))
    titanium = fields.Float(string='Ti %', help="Titanium", default=0.0, digits=(6, 3))
    magnesium = fields.Float(string='Mg %', help="Magnesium", default=0.0, digits=(6, 3))
    zinc = fields.Float(string='Zn %', help="Zinc", default=0.0, digits=(6, 3))
    iron = fields.Float(string='Fe %', help="Iron", default=0.0, digits=(6, 3))
    aluminum = fields.Float(string='Al %', help="Aluminum", default=0.0, digits=(6, 3))
    tin = fields.Float(string='Sn %', help="Tin", default=0.0, digits=(6, 3))
    cobalt = fields.Float(string='Co %', help="Cobalt", default=0.0, digits=(6, 3))
    boron = fields.Float(string='B %', help="Boron", default=0.0, digits=(6, 3))
    carbon_equivalent = fields.Float(string='CE %', help="Carbon Equivalent (EN 1011-2)", compute='_compute_carbon_equivalent', digits=(6, 3))

    # Mechanical Properties Fields
    yield_strength_0_2 = fields.Float(string='Rp 0.2% (MPa)', help="Yield Strength at 0.2% strain (Rp0.2)", digits=(10, 2))
    yield_strength_1_0 = fields.Float(string='Rp 1.0% (MPa)', help="Yield Strength at 1.0% strain (Rp1.0)", digits=(10, 2))
    tensile_strength = fields.Float(string='Rm (MPa)', help="Tensile Strength (Rm)", digits=(10, 2))
    elongation = fields.Float(string='A (%)', help="Elongation at Break (A)", digits=(6, 2))
    reduction_of_area = fields.Float(string='Area red. Z (%)', help="Reduction of Area (Z)", digits=(6, 2))
    impact_energy = fields.Float(string='Impact KV (J)', help="Impact Energy at specified temperature", digits=(10, 2))
    impact_temperature = fields.Float(string='T (°C)', help="Temperature for Impact Test", digits=(6, 1))
    hardness_hb = fields.Float(string='HB', help="Brinell Hardness", digits=(10, 1))
    hardness_hrc = fields.Float(string='HRC', help="Rockwell C Hardness", digits=(6, 1))
    hardness_hv = fields.Float(string='HV', help="Vickers Hardness", digits=(10, 1))
    young_modulus = fields.Float(string='E (GPa)', help="Young's Modulus (E)", digits=(10, 2))
    poisson_ratio = fields.Float(string='ν', help="Poisson's Ratio (ν)", digits=(6, 3))
    density = fields.Float(string='ρ (kg/m³)', help="Material Density", digits=(10, 2))
    thermal_expansion = fields.Float(string='α (10⁻⁶/K)', help="Coefficient of Thermal Expansion", digits=(10, 2))
    thermal_conductivity = fields.Float(string='λ (W/m·K)', help="Thermal Conductivity", digits=(10, 2))
    electrical_resistivity = fields.Float(string='ρ (Ω·m)', help="Electrical Resistivity", digits=(10, 8))
    description = fields.Text(string='Description')

    melting_process = fields.Selection([
        ('eaf', 'Electric Arc Furnace (EAF)'),
        ('bof', 'Basic Oxygen Furnace (BOF)'),
        ('induction', 'Induction Melting'),
        ('vacuum_arc', 'Vacuum Arc Remelting (VAR)'),
        ('electroslag', 'Electroslag Remelting (ESR)'),
        ('vacuum_induction', 'Vacuum Induction Melting (VIM)'),
        ('open_hearth', 'Open Hearth Furnace'),
        ('aod', 'Argon Oxygen Decarburization (AOD)'),
        ('ladle_refining', 'Ladle Refining'),
        ('other', 'Other')
    ], string='Melting Process')

    @api.constrains('carbon', 'silicon', 'manganese', 'chromium', 'molybdenum', 'vanadium', 'nickel', 'copper', 'phosphorus', 'sulfur',
                    'nitrogen', 'titanium', 'magnesium', 'zinc', 'iron', 'aluminum', 'tin', 'cobalt', 'boron')
    def _check_percentages(self):
        for record in self:
            elements = [
                record.carbon, record.silicon, record.manganese, record.chromium,
                record.molybdenum, record.vanadium, record.nickel, record.copper,
                record.phosphorus, record.sulfur, record.nitrogen, record.titanium,
                record.magnesium, record.zinc, record.iron, record.aluminum,
                record.tin, record.cobalt, record.boron
            ]
            if any(x < 0 for x in elements):
                raise ValidationError("Element percentages cannot be negative.")
            total = sum(elements)
            if total > 100:
                raise ValidationError("Total percentage of elements cannot exceed 100%.")

    @api.depends('carbon', 'silicon', 'manganese', 'chromium', 'molybdenum',
                 'vanadium', 'nickel', 'copper', 'phosphorus', 'sulfur',
                 'nitrogen', 'titanium', 'magnesium', 'zinc', 'iron',
                 'aluminum', 'tin', 'cobalt', 'boron', 'material_grade_id.material_grade_type')
    def _compute_carbon_equivalent(self):
        for record in self:
            # Check if material_grade_id exists and has a material_grade_type
            if record.material_grade_id and record.material_grade_id.material_grade_type:
                material_type = record.material_grade_id.material_grade_type

                # Calculate CE for steel groups (1-11) using Eurocode (EN 1011-2) formula
                if material_type.startswith(('group_1_', 'group_2_', 'group_3_', 'group_5_', 'group_6_', 'group_7_', 'group_8_', 'group_10_', 'group_11_')):
                    # Eurocode (EN 1011-2) formula for CE calculation
                    # CE = C + Mn/6 + (Cr + Mo + V)/5 + (Ni + Cu)/15
                    # Reference: EN 1011-2:2001 - Welding - Recommendations for welding of metallic materials
                    ce = (record.carbon +
                          record.manganese / 6 +
                          (record.chromium + record.molybdenum + record.vanadium) / 5 +
                          (record.nickel + record.copper) / 15)
                    record.carbon_equivalent = ce

                # Calculate CE for cast iron groups (71-76) using cast iron specific formula
                elif material_type.startswith(('group_71', 'group_72_', 'group_73', 'group_74', 'group_75', 'group_76')):
                    # Cast iron carbon equivalent formula
                    # CE = C + Si/4 + P/2
                    # Reference: ISO 945-1:2017 - Microstructure of cast irons - Part 1: Graphite classification by visual analysis
                    # Also referenced in: ASTM A247-19 - Standard Test Methods for Evaluating the Microstructure of Graphite in Iron Castings
                    ce = (record.carbon +
                          record.silicon / 4 +
                          record.phosphorus / 2)
                    record.carbon_equivalent = ce

                else:
                    # Skip CE calculation for non-ferrous materials (aluminum alloys, etc.)
                    record.carbon_equivalent = 0.0
            else:
                # Skip CE calculation when material grade is not set
                record.carbon_equivalent = 0.0

    @api.model
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        return super(KojtoWarehousesBatchProperties, self).create(vals_list)

    @api.depends('name', 'material_grade_id.material_grade_type', 'carbon', 'silicon', 'manganese', 'chromium', 'molybdenum',
                'vanadium', 'nickel', 'copper', 'phosphorus', 'sulfur', 'nitrogen', 'titanium',
                'magnesium', 'zinc', 'iron', 'aluminum', 'tin', 'cobalt', 'boron', 'carbon_equivalent')
    def _compute_chemical_composition_summary(self):
        for record in self:
            # Get material grade type from material grade
            material_grade_type = dict(record.material_grade_id._fields['material_grade_type'].selection).get(record.material_grade_id.material_grade_type, '') if record.material_grade_id else ''

            # Build composition string with non-zero elements
            elements = []
            # Main elements
            if record.carbon > 0:
                elements.append(f"C: {record.carbon:.3f}%")
            if record.silicon > 0:
                elements.append(f"Si: {record.silicon:.3f}%")
            if record.manganese > 0:
                elements.append(f"Mn: {record.manganese:.3f}%")
            if record.chromium > 0:
                elements.append(f"Cr: {record.chromium:.3f}%")
            if record.molybdenum > 0:
                elements.append(f"Mo: {record.molybdenum:.3f}%")
            if record.vanadium > 0:
                elements.append(f"V: {record.vanadium:.3f}%")
            if record.nickel > 0:
                elements.append(f"Ni: {record.nickel:.3f}%")
            if record.copper > 0:
                elements.append(f"Cu: {record.copper:.3f}%")
            # Additional elements
            if record.phosphorus > 0:
                elements.append(f"P: {record.phosphorus:.3f}%")
            if record.sulfur > 0:
                elements.append(f"S: {record.sulfur:.3f}%")
            if record.nitrogen > 0:
                elements.append(f"N: {record.nitrogen:.3f}%")
            if record.titanium > 0:
                elements.append(f"Ti: {record.titanium:.3f}%")
            if record.magnesium > 0:
                elements.append(f"Mg: {record.magnesium:.3f}%")
            if record.zinc > 0:
                elements.append(f"Zn: {record.zinc:.3f}%")
            if record.iron > 0:
                elements.append(f"Fe: {record.iron:.3f}%")
            if record.aluminum > 0:
                elements.append(f"Al: {record.aluminum:.3f}%")
            if record.tin > 0:
                elements.append(f"Sn: {record.tin:.3f}%")
            if record.cobalt > 0:
                elements.append(f"Co: {record.cobalt:.3f}%")
            if record.boron > 0:
                elements.append(f"B: {record.boron:.3f}%")

            # Add carbon equivalent if applicable
            ce_str = f", CE: {record.carbon_equivalent:.3f}%" if record.carbon_equivalent > 0 else ""

            # Combine all parts
            summary_parts = []
            if record.name:
                summary_parts.append(record.name)
            if material_grade_type:
                summary_parts.append(material_grade_type)
            if elements:
                summary_parts.append("(" + ", ".join(elements) + ce_str + ")")

            record.chemical_composition_summary = " - ".join(summary_parts) if summary_parts else ""

    @api.depends('name', 'yield_strength_0_2', 'yield_strength_1_0', 'tensile_strength', 'elongation', 'reduction_of_area',
                'impact_energy', 'impact_temperature', 'hardness_hb', 'hardness_hrc', 'hardness_hv',
                'young_modulus', 'poisson_ratio', 'density', 'thermal_expansion', 'thermal_conductivity',
                'electrical_resistivity')
    def _compute_mechanical_properties_summary(self):
        for record in self:
            # Build mechanical properties summary
            properties = []
            if record.yield_strength_0_2 > 0:
                properties.append(f"Rp0.2: {record.yield_strength_0_2:.0f} MPa")
            if record.yield_strength_1_0 > 0:
                properties.append(f"Rp1.0: {record.yield_strength_1_0:.0f} MPa")
            if record.tensile_strength > 0:
                properties.append(f"Rm: {record.tensile_strength:.0f} MPa")
            if record.elongation > 0:
                properties.append(f"A: {record.elongation:.1f}%")
            if record.reduction_of_area > 0:
                properties.append(f"Z: {record.reduction_of_area:.1f}%")
            if record.impact_energy > 0:
                temp_str = f" @ {record.impact_temperature:.0f}°C" if record.impact_temperature else ""
                properties.append(f"KV: {record.impact_energy:.0f} J{temp_str}")
            if record.hardness_hb > 0:
                properties.append(f"HB: {record.hardness_hb:.0f}")
            if record.hardness_hrc > 0:
                properties.append(f"HRC: {record.hardness_hrc:.1f}")
            if record.hardness_hv > 0:
                properties.append(f"HV: {record.hardness_hv:.0f}")

            # Combine all parts
            summary_parts = []
            if record.name:
                summary_parts.append(record.name)
            if properties:
                summary_parts.append("(" + ", ".join(properties) + ")")

            record.mechanical_properties_summary = " - ".join(summary_parts) if summary_parts else ""
