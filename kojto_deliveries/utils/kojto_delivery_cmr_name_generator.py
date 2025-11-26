from odoo import fields

# CMR prefix
CMR_PREFIX = 'CMR'

def get_temp_name(prefix=CMR_PREFIX):
    """Generate a temporary name with timestamp for uniqueness during creation.

    Args:
        prefix: The prefix to use for the temporary name

    Returns:
        str: Generated temporary name
    """
    timestamp = fields.Datetime.now().strftime('%Y%m%d%H%M%S%f')
    return f"{prefix}.{timestamp}"

def get_final_name(record_id, prefix=CMR_PREFIX):
    """Generate the final name for a CMR record after creation.

    Args:
        record_id: The ID of the record (can be int or NewId)
        prefix: The prefix to use for the final name

    Returns:
        str: Generated final name
    """
    # Handle both permanent IDs (int) and temporary IDs (NewId)
    if isinstance(record_id, int):
        return f"{prefix}.{record_id:06d}"
    else:
        # For temporary IDs, use timestamp to ensure uniqueness
        timestamp = fields.Datetime.now().strftime('%Y%m%d%H%M%S%f')
        return f"{prefix}.{timestamp}"

# Legacy functions for backward compatibility
def generate_cmr_name(record_id):
    """Generate a CMR name based on the record ID (legacy function).

    Args:
        record_id: The ID of the CMR record

    Returns:
        str: Generated CMR name in format CMR.XXXXXX
    """
    return get_final_name(record_id, CMR_PREFIX)

def generate_cmr_name_simple(record_id):
    """Generate a simple CMR name (alias for generate_cmr_name for backward compatibility).

    Args:
        record_id: The ID of the CMR record

    Returns:
        str: Generated CMR name
    """
    return generate_cmr_name(record_id)

def generate_cmr_name_simple_legacy(record):
    """Generate a simple CMR name using the next available number (legacy function).

    This is a simpler version that just finds the highest number and adds 1.
    Use this if you prefer the original logic.

    Args:
        record: The CMR record to generate name for

    Returns:
        str: The generated name in format CMR_{padded_number}
    """
    # Find the latest CMR with a name matching the pattern
    latest_cmr = record.search([
        ('name', 'like', 'CMR_%')
    ], order='name desc', limit=1)

    if latest_cmr and latest_cmr.name:
        try:
            # Extract the number part after CMR_
            number_part = latest_cmr.name.split('CMR_')[1]
            next_number = int(number_part) + 1
        except (ValueError, IndexError):
            next_number = 1
    else:
        next_number = 1

    # Format with leading zeros to ensure minimum 6 digits
    return f"CMR_{str(next_number).zfill(6)}"
