# kojto_warehouses/utils/kojto_warehouses_name_generator.py

from odoo import fields

# Default prefixes
DEFAULT_PREFIX = 'TRX'
ITEM_TEMP_PREFIX = 'TMP'

# Prefix maps
BATCH_PREFIXES = {'sheet': 'BCH.SHT', 'bar': 'BCH.BAR', 'part': 'BCH.PRT'}
ITEM_PREFIXES = {'sheet': 'SHT', 'bar': 'BAR', 'part': 'PRT'}
ITEM_TEMP_PREFIXES = {'sheet': 'TMP.SHT', 'bar': 'TMP.BAR', 'part': 'TMP.PRT'}

def get_temp_name(type_value, prefix_map, default_prefix=DEFAULT_PREFIX):
    """Generate a temporary name with timestamp for uniqueness during creation.

    Args:
        type_value: The type value (e.g., 'sheet', 'bar', 'part')
        prefix_map: Dictionary mapping type values to prefixes
        default_prefix: Default prefix to use if type_value not in prefix_map

    Returns:
        str: Generated temporary name
    """
    # For items, always use TMP prefix regardless of type
    if prefix_map == ITEM_PREFIXES:
        prefix = ITEM_TEMP_PREFIX
    else:
        # For batches, use type-specific prefix (BCH.SHT, BCH.BAR, BCH.PRT)
        prefix = prefix_map.get(type_value, default_prefix)

    timestamp = fields.Datetime.now().strftime('%Y%m%d%H%M%S%f')
    return f"{prefix}.{timestamp}"

def get_final_name(record_id, type_value, prefix_map, default_prefix=DEFAULT_PREFIX):
    """Generate the final name for a record after creation.

    Args:
        record_id: The ID of the record (can be int or NewId)
        type_value: The type value (e.g., 'sheet', 'bar', 'part')
        prefix_map: Dictionary mapping type values to prefixes
        default_prefix: Default prefix to use if type_value not in prefix_map

    Returns:
        str: Generated final name
    """
    # For batches, use type-specific prefix (BCH.SHT, BCH.BAR, BCH.PRT)
    prefix = prefix_map.get(type_value, default_prefix)

    # Handle both permanent IDs (int) and temporary IDs (NewId)
    if isinstance(record_id, int):
        return f"{prefix}.{record_id:06d}"
    else:
        # For temporary IDs, use timestamp to ensure uniqueness
        timestamp = fields.Datetime.now().strftime('%Y%m%d%H%M%S%f')
        return f"{prefix}.{timestamp}"

# Export only the functions
__all__ = ['get_temp_name', 'get_final_name']
