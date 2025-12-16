def get_temp_name(prefix):
    """Generate a temporary name for a new record."""
    return f"{prefix}/TEMP"

def get_final_name(record_id, prefix):
    """Generate a final name for a record based on its ID."""
    return f"{prefix}.{record_id:04d}"

def generate_document_name(record, document_bundle, suffix, padding=2):
    """Generate a document name based on document bundle and suffix.

    This function generates a unique name for a document by:
    1. Looking for gaps in the existing sequence numbers
    2. If no gaps are found, using the next available number
    3. Ensuring no name collisions occur

    Args:
        record: The record to generate name for
        document_bundle: The document bundle record
        suffix: The suffix to use (e.g., 'WW', 'CTR', 'QCC')
        padding: Number of digits to pad the sequence number with (default: 2)

    Returns:
        str: The generated name in format {bundle_name}.{suffix}.{padded_number}
    """
    if not document_bundle:
        return "Untitled"

    # Check if the model has a direct document_bundle_id field
    has_document_bundle_field = 'document_bundle_id' in record._fields

    # Build domain based on available fields
    if has_document_bundle_field:
        domain = [
            ("document_bundle_id", "=", document_bundle.id),
            ("id", "!=", record.id if record.id else False)
        ]
    else:
        # For models without direct document_bundle_id, search by name pattern
        domain = [
            ("id", "!=", record.id if record.id else False)
        ]

    existing_records = record.search(domain, order="name ASC")

    # Extract existing numbers from names and track used names
    existing_numbers = set()
    used_names = set()
    base_name = f"{document_bundle.name}.{suffix}."

    for rec in existing_records:
        if rec.name and rec.name.startswith(base_name):
            try:
                num = int(rec.name.split(base_name)[-1])
                existing_numbers.add(num)
                used_names.add(rec.name)
            except (ValueError, IndexError):
                # Skip malformed names
                continue

    # Find the first available number by checking for gaps
    if existing_numbers:
        # Create a sorted list of existing numbers
        sorted_numbers = sorted(existing_numbers)

        # Check for gaps in the sequence
        for i in range(1, sorted_numbers[-1] + 2):  # +2 to handle case where we need next number after max
            if i not in existing_numbers:
                next_num = str(i).zfill(padding)
                candidate_name = f"{base_name}{next_num}"
                if candidate_name not in used_names:
                    return candidate_name

    # If no gaps found or no existing numbers, start with 1
    next_num = "1".zfill(padding)
    return f"{base_name}{next_num}"

# Prefixes
WELDING_SEAM_PREFIX = 'WSM'
CONTROL_PREFIX = 'CTR'
WELDING_TASK_PREFIX = 'WTSK'
QC_CHECKLIST_PREFIX = 'QCC'
PERFORMANCE_DECLARATION_PREFIX = 'DOP'
WPS_PREFIX = 'WPS'
WPQR_PREFIX = 'WPQR'
