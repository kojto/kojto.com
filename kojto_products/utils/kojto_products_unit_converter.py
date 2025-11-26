# kojto_products/utils/kojto_products_unit_converter.py
from typing import Tuple, Dict, List
from decimal import Decimal, ROUND_HALF_UP

class UnitConverter:
    # Define unit thresholds and their corresponding units
    LENGTH_UNITS = [
        (0.001, 'mm'),  # 1mm = 0.001m
        (1.0, 'm'),     # 1m = 1m
        (1000.0, 'km')  # 1km = 1000m
    ]

    AREA_UNITS = [
        (0.000001, 'mm²'),  # 1mm² = 0.000001m²
        (0.01, 'dm²'),      # 1dm² = 0.01m²
        (1.0, 'm²'),        # 1m² = 1m²
        (10000.0, 'ha')     # 1ha = 10000m²
    ]

    VOLUME_UNITS = [
        (0.000000001, 'mm³'),  # 1mm³ = 0.000000001m³
        (0.000001, 'cm³'),     # 1cm³ = 0.000001m³
        (0.001, 'dm³'),        # 1dm³ = 0.001m³
        (1.0, 'm³')            # 1m³ = 1m³
    ]

    WEIGHT_UNITS = [
        (0.001, 'g'),   # 1g = 0.001kg
        (1.0, 'kg'),    # 1kg = 1kg
        (1000.0, 't')   # 1t = 1000kg
    ]

    TIME_UNITS = [
        (1/60.0, 'sec'),  # 1sec = 1/60min
        (1.0, 'min'),     # 1min = 1min
        (60.0, 'hrs')     # 1hr = 60min
    ]

    @staticmethod
    def _find_best_unit(value: float, units: List[Tuple[float, str]]) -> Tuple[float, str]:
        """
        Find the most appropriate unit for a given value.
        Returns a tuple of (converted_value, unit)
        """
        # Convert to base unit first
        base_value = value

        # Find the best unit
        best_unit = units[0]  # Default to smallest unit
        for threshold, unit in units:
            if base_value >= threshold:
                best_unit = (threshold, unit)
            else:
                break

        # Convert to the best unit
        converted_value = base_value / best_unit[0]

        # Round to 2 decimal places
        rounded_value = Decimal(str(converted_value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        return float(rounded_value), best_unit[1]

    @classmethod
    def convert_length(cls, value: float, from_unit: str = 'm') -> Tuple[float, str]:
        """Convert length to the most appropriate unit"""
        # Convert to base unit (meters) first
        if from_unit == 'mm':
            value = value * 0.001
        elif from_unit == 'km':
            value = value * 1000.0

        return cls._find_best_unit(value, cls.LENGTH_UNITS)

    @classmethod
    def convert_area(cls, value: float, from_unit: str = 'm²') -> Tuple[float, str]:
        """Convert area to the most appropriate unit"""
        # Convert to base unit (square meters) first
        if from_unit == 'mm²':
            value = value * 0.000001
        elif from_unit == 'dm²':
            value = value * 0.01
        elif from_unit == 'ha':
            value = value * 10000.0

        return cls._find_best_unit(value, cls.AREA_UNITS)

    @classmethod
    def convert_volume(cls, value: float, from_unit: str = 'm³') -> Tuple[float, str]:
        """Convert volume to the most appropriate unit"""
        # Convert to base unit (cubic meters) first
        if from_unit == 'mm³':
            value = value * 0.000000001
        elif from_unit == 'cm³':
            value = value * 0.000001
        elif from_unit == 'dm³':
            value = value * 0.001

        return cls._find_best_unit(value, cls.VOLUME_UNITS)

    @classmethod
    def convert_weight(cls, value: float, from_unit: str = 'kg') -> Tuple[float, str]:
        """Convert weight to the most appropriate unit"""
        # Convert to base unit (kilograms) first
        if from_unit == 'g':
            value = value * 0.001
        elif from_unit == 't':
            value = value * 1000.0

        return cls._find_best_unit(value, cls.WEIGHT_UNITS)

    @classmethod
    def convert_time(cls, value: float, from_unit: str = 'min') -> Tuple[float, str]:
        """Convert time to the most appropriate unit"""
        # Convert to base unit (minutes) first
        if from_unit == 'sec':
            value = value / 60.0
        elif from_unit == 'hrs':
            value = value * 60.0

        return cls._find_best_unit(value, cls.TIME_UNITS)

    @classmethod
    def format_value(cls, value: float, unit: str) -> str:
        """Format a value with its unit"""
        return f"{value:,.2f} {unit}"
