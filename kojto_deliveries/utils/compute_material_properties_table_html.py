def compute_material_properties_table_html(batch_ids):
    """
    Compute the HTML content for material properties table based on batch properties.

    Args:
        batch_ids: Recordset of kojto.warehouses.batches

    Returns:
        str: HTML content for the material properties table
    """
    if not batch_ids:
        return ""

    # Get all batch properties from all batches
    all_batch_properties = []
    for batch in batch_ids:
        if batch.batch_properties_ids:
            # Get the first batch property for each batch
            first_property = batch.batch_properties_ids[0]
            all_batch_properties.append({
                'batch_name': batch.name,
                'heat_number': first_property.heat_number if first_property.heat_number else '',
                'material_grade': first_property.material_grade_id.name if first_property.material_grade_id else '',
                'property': first_property
            })

    if not all_batch_properties:
        return ""

    # Define chemical elements to display
    chemical_elements = [
        ('carbon', 'C'),
        ('silicon', 'Si'),
        ('manganese', 'Mn'),
        ('chromium', 'Cr'),
        ('molybdenum', 'Mo'),
        ('vanadium', 'V'),
        ('nickel', 'Ni'),
        ('copper', 'Cu'),
        ('phosphorus', 'P'),
        ('sulfur', 'S'),
        ('nitrogen', 'N'),
        ('titanium', 'Ti'),
        ('magnesium', 'Mg'),
        ('zinc', 'Zn'),
        ('iron', 'Fe'),
        ('aluminum', 'Al'),
        ('tin', 'Sn'),
        ('cobalt', 'Co'),
        ('boron', 'B')
    ]

    # Define mechanical properties to display
    mechanical_properties = [
        ('yield_strength_0_2', 'Rp 0.2% (MPa)'),
        ('yield_strength_1_0', 'Rp 1.0% (MPa)'),
        ('tensile_strength', 'Rm (MPa)'),
        ('elongation', 'A (%)'),
        ('reduction_of_area', 'Area red. Z (%)'),
        ('impact_energy', 'Impact KV (J)'),
        ('impact_temperature', 'Impact test T (°C)'),
        ('hardness_hb', 'HB'),
        ('hardness_hrc', 'HRC'),
        ('hardness_hv', 'HV'),
        ('young_modulus', 'E (GPa)'),
        ('poisson_ratio', 'ν'),
        ('density', 'ρ (kg/m³)'),
        ('thermal_expansion', 'α (10⁻⁶/K)'),
        ('thermal_conductivity', 'λ (W/m·K)'),
        ('electrical_resistivity', 'ρ (Ω·m)')
    ]

    # Filter chemical elements to only include those with at least one non-zero value
    active_chemical_elements = []
    for field_name, field_label in chemical_elements:
        has_value = False
        for batch_data in all_batch_properties:
            value = getattr(batch_data['property'], field_name, 0.0)
            if value and value > 0:
                has_value = True
                break
        if has_value:
            active_chemical_elements.append((field_name, field_label))

    # Filter mechanical properties to only include those with at least one non-zero value
    active_mechanical_properties = []
    for field_name, field_label in mechanical_properties:
        has_value = False
        for batch_data in all_batch_properties:
            value = getattr(batch_data['property'], field_name, 0.0)
            if value and value > 0:
                has_value = True
                break
        if has_value:
            active_mechanical_properties.append((field_name, field_label))

    # Start building HTML content
    html_content = """
    <div style="width: 100%; overflow-x: auto; margin-bottom: 20px; margin-top: 20px;">
    """

    # Calculate column widths for Chemical Composition Table
    chemical_total_columns = len(active_chemical_elements) + 3  # +3 for Batch, Heat Number and Material Grade columns
    batch_width = 12  # Fixed width for batch column
    heat_number_width = 12  # Fixed width for heat number column
    material_width = 16  # Fixed width for material grade column
    chemical_property_width = (100 - batch_width - heat_number_width - material_width) / len(active_chemical_elements)  # Remaining width for chemical property columns

    # Chemical Composition Table
    html_content += f"""
        <table class="performance-table" style="width: 100%; max-width: 100%; border-collapse: collapse; word-wrap: break-word; word-break: normal; margin-bottom: 20px;">
            <thead>
                <tr style="background-color: #B0C4DE; font-weight: bold;">
                    <th style="padding: 4px; border: 1px solid #ddd; text-align: center; width: 100%;" colspan="{chemical_total_columns}">Chemical Composition (%)</th>
                </tr>
                <tr style="background-color: #B0C4DE; font-weight: bold;">
                    <th style="padding: 4px; border: 1px solid #ddd; text-align: center; width: {batch_width}%; word-wrap: break-word; word-break: normal; white-space: normal;">Batch</th>
                    <th style="padding: 4px; border: 1px solid #ddd; text-align: center; width: {heat_number_width}%; word-wrap: break-word; word-break: normal; white-space: normal;">Heat Number</th>
                    <th style="padding: 4px; border: 1px solid #ddd; text-align: center; width: {material_width}%; word-wrap: break-word; word-break: normal; white-space: normal;">Material Grade</th>
    """

    # Add chemical property columns
    for field_name, field_label in active_chemical_elements:
        html_content += f"""
                    <th style="padding: 4px; border: 1px solid #ddd; text-align: center; width: {chemical_property_width}%; word-wrap: break-word; word-break: normal; white-space: normal;">{field_label}</th>
        """

    html_content += """
                </tr>
            </thead>
            <tbody>
    """

    # Add rows for each batch
    for batch_data in all_batch_properties:
        html_content += f"""
            <tr>
                <td style="padding: 4px; border: 1px solid #ddd; text-align: left; font-weight: bold; word-wrap: break-word; white-space: normal;">{batch_data['batch_name']}</td>
                <td style="padding: 4px; border: 1px solid #ddd; text-align: center; word-wrap: break-word; white-space: normal;">{batch_data['heat_number']}</td>
                <td style="padding: 4px; border: 1px solid #ddd; text-align: center; word-wrap: break-word; white-space: normal;">{batch_data['material_grade']}</td>
        """

        # Add chemical composition values for this batch
        for field_name, field_label in active_chemical_elements:
            value = getattr(batch_data['property'], field_name, 0.0)
            if value and value > 0:
                if field_name == 'carbon_equivalent':
                    # Format to 3 decimal places and remove trailing zeros, but keep at least one digit after decimal
                    formatted_value = f"{value:.3f}".rstrip('0')
                    if formatted_value.endswith('.'):
                        formatted_value = formatted_value + '0'  # Add 0 after decimal point
                else:
                    # Format to 3 decimal places and remove trailing zeros, but keep at least one digit after decimal
                    formatted_value = f"{value:.3f}".rstrip('0')
                    if formatted_value.endswith('.'):
                        formatted_value = formatted_value + '0'  # Add 0 after decimal point
            else:
                formatted_value = ""

            html_content += f"""
                <td style="padding: 4px; border: 1px solid #ddd; text-align: center; word-wrap: break-word; white-space: normal;">{formatted_value}</td>
        """

        html_content += """
            </tr>
        """

    html_content += """
            </tbody>
        </table>
    """

    # Calculate column widths for Mechanical Properties Table
    mechanical_total_columns = len(active_mechanical_properties) + 3  # +3 for Batch, Heat Number and Material Grade columns
    mechanical_property_width = (100 - batch_width - heat_number_width - material_width) / len(active_mechanical_properties)  # Remaining width for mechanical property columns

    # Mechanical Properties Table
    html_content += f"""
        <table class="performance-table" style="width: 100%; max-width: 100%; border-collapse: collapse; word-wrap: break-word; word-break: normal; margin-bottom: 20px;">
            <thead>
                <tr style="background-color: #B0C4DE; font-weight: bold;">
                    <th style="padding: 4px; border: 1px solid #ddd; text-align: center; width: 100%;" colspan="{mechanical_total_columns}">Mechanical Properties</th>
                </tr>
                <tr style="background-color: #B0C4DE; font-weight: bold;">
                    <th style="padding: 4px; border: 1px solid #ddd; text-align: center; width: {batch_width}%; word-wrap: break-word; word-break: normal; white-space: normal;">Batch</th>
                    <th style="padding: 4px; border: 1px solid #ddd; text-align: center; width: {heat_number_width}%; word-wrap: break-word; word-break: normal; white-space: normal;">Heat Number</th>
                    <th style="padding: 4px; border: 1px solid #ddd; text-align: center; width: {material_width}%; word-wrap: break-word; word-break: normal; white-space: normal;">Material Grade</th>
    """

    # Add mechanical property columns
    for field_name, field_label in active_mechanical_properties:
        html_content += f"""
                    <th style="padding: 4px; border: 1px solid #ddd; text-align: center; width: {mechanical_property_width}%; word-wrap: break-word; word-break: normal; white-space: normal;">{field_label}</th>
        """

    html_content += """
                </tr>
            </thead>
            <tbody>
    """

    # Add rows for each batch
    for batch_data in all_batch_properties:
        html_content += f"""
            <tr>
                <td style="padding: 4px; border: 1px solid #ddd; text-align: left; font-weight: bold; word-wrap: break-word; white-space: normal;">{batch_data['batch_name']}</td>
                <td style="padding: 4px; border: 1px solid #ddd; text-align: center; word-wrap: break-word; white-space: normal;">{batch_data['heat_number']}</td>
                <td style="padding: 4px; border: 1px solid #ddd; text-align: center; word-wrap: break-word; white-space: normal;">{batch_data['material_grade']}</td>
        """

        # Add mechanical properties values for this batch
        for field_name, field_label in active_mechanical_properties:
            value = getattr(batch_data['property'], field_name, 0.0)
            if value and value > 0:
                if field_name in ['poisson_ratio']:
                    formatted_value = f"{value:.3f}"
                elif field_name in ['elongation', 'reduction_of_area', 'impact_temperature', 'hardness_hrc']:
                    formatted_value = f"{value:.1f}"
                elif field_name in ['hardness_hb', 'hardness_hv', 'impact_energy']:
                    formatted_value = f"{value:.0f}"
                elif field_name in ['yield_strength_0_2', 'yield_strength_1_0', 'tensile_strength', 'young_modulus', 'density', 'thermal_expansion', 'thermal_conductivity']:
                    formatted_value = f"{value:.0f}"
                elif field_name == 'electrical_resistivity':
                    formatted_value = f"{value:.2e}"
                else:
                    formatted_value = f"{value:.2f}"
            else:
                formatted_value = ""

            html_content += f"""
                <td style="padding: 4px; border: 1px solid #ddd; text-align: center; word-wrap: break-word; white-space: normal;">{formatted_value}</td>
        """

        html_content += """
            </tr>
        """

    html_content += """
            </tbody>
        </table>
    </div>
    """

    return html_content
