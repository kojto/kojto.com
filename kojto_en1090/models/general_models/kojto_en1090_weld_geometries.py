from odoo import models, fields, api
from odoo.exceptions import ValidationError
import re
import base64

class KojtoEn1090WeldGeometries(models.Model):
    _name = "kojto.en1090.weld.geometries"
    _description = "Universal Weld Geometries for EN 1090 Compliance"
    _order = "name"
    _constraints = [('code_unique', 'unique(code)', 'The weld geometry code must be unique.'),
                    ('name_unique', 'unique(name)', 'The weld geometry name must be unique.'),]

    name = fields.Char(string="Name", required=True, help="Name of the weld geometry, e.g., Single V Butt Weld")
    active = fields.Boolean(string="Active", default=True, help="Indicates if the weld geometry is active")
    translation_ids = fields.One2many("kojto.en1090.translations", "geometry_id", string="Translations")

    code = fields.Char(string="Code", required=True, compute="_compute_code", store=True, readonly=False, help="Unique code for the weld geometry, e.g., BW-V for Single V Butt Weld")
    weld_type = fields.Selection([('butt', 'Butt Weld'), ('fillet', 'Fillet Weld'), ('stud', 'Stud Weld'), ('other', 'Other'),], string="Weld Type", required=True, help="Type of weld, either butt, fillet, stud, or other")
    iso_2553_symbol = fields.Selection(
        [
            ('square', 'Square Groove (‖)'),
            ('single_v', 'Single V Groove (V)'),
            ('double_v', 'Double V Groove (X)'),
            ('single_bevel', 'Single Bevel Groove (⌋)'),
            ('double_bevel', 'Double Bevel Groove (K)'),
            ('single_u', 'Single U Groove (U)'),
            ('single_j', 'Single J Groove (J)'),
            ('single_v_broad', 'Single V Groove with Broad Root Face (Y)'),
            ('single_bevel_broad', 'Single Bevel Groove with Broad Root Face (⅄)'),
            ('fillet', 'Fillet Weld (△)'),
            ('plug', 'Plug Weld (☐)'),
            ('slot', 'Slot Weld (☐)'),
            ('spot', 'Spot Weld (○)'),
            ('seam', 'Seam Weld (≈)'),
            ('surfacing', 'Surfacing Weld (~~~)'),
            ('backing_run', 'Backing Run/Back Weld (∩)'),
            ('edge', 'Edge Weld (⊥)'),
            ('flare_v', 'Flare V Groove (∩)'),
            ('flare_bevel', 'Flare Bevel Groove (⊃)'),
            ('backing_strip', 'Permanent Backing Strip (M)'),
            ('removable_backing', 'Removable Backing Strip (MR)'),
            ('other', 'Other Weld Symbol'),
        ],
        string="ISO 2553 Weld Symbol",
        required=True,
        help="Select a weld symbol per ISO 2553:2019 standard. Examples: 'V' for Single V Groove, '△' for Fillet Weld. Use 'Other' for non-standard or custom symbols."
    )
    standard = fields.Selection([('en_iso_9692_1', 'EN ISO 9692-1'), ('en_iso_14555', 'EN ISO 14555'), ('other', 'Other'),], string="Standard Reference", required=True, default='en_iso_9692_1',  help="Standard defining the weld geometry, typically EN ISO 9692-1 for butt/fillet welds or EN ISO 14555 for stud welds" )
    description = fields.Text(string="Description", help="Description of the weld geometry, including typical applications")
    weld_drawing_svg = fields.Binary(string="SVG Drawing", help="Generic SVG representation of the weld geometry")
    weld_drawing_filename = fields.Char(string="SVG Filename",)

    @api.depends('name', 'weld_type')
    def _compute_code(self):
        for record in self:
            if not record.code or record._origin.code != record.code:
                name_part = ''.join(word[0].upper() for word in (record.name or '').split() if word) or 'UNKNOWN'
                weld_type_prefix = {
                    'butt': 'BW',
                    'fillet': 'FW',
                    'stud': 'SW',
                    'other': 'WELD'
                }.get(record.weld_type, 'WELD')
                record.code = f"{weld_type_prefix}-{name_part}"

    @api.onchange('weld_type')
    def _onchange_weld_type(self):
        if self.weld_type:
            # Reset iso_2553_symbol to False when weld_type changes
            self.iso_2553_symbol = False
            # Set standard based on weld_type
            self.standard = 'en_iso_14555' if self.weld_type == 'stud' else 'en_iso_9692_1'

    @api.onchange('weld_drawing_svg')
    def _onchange_weld_drawing(self):
        if not self.weld_drawing_svg:
            return

        # Set default filename
        base_name = self.name.replace(' ', '_').lower() if self.name else 'weld_geometry'
        self.weld_drawing_filename = f"{base_name}_{self.code or 'unknown'}.svg"

        try:
            # Validate base64 encoding
            try:
                svg_data = base64.b64decode(self.weld_drawing_svg).decode('utf-8')
            except base64.binascii.Error:
                raise ValidationError("Invalid SVG file: The file is not properly base64 encoded.")
            except UnicodeDecodeError:
                raise ValidationError("Invalid SVG file: The file contains invalid UTF-8 characters.")

            # Basic SVG structure validation
            if not svg_data.strip():
                raise ValidationError("Invalid SVG file: The file is empty.")

            # Check for SVG root element
            svg_root_match = re.search(r'<svg\b[^>]*>(.*?)</svg>', svg_data, re.DOTALL | re.IGNORECASE)
            if not svg_root_match:
                raise ValidationError("Invalid SVG file: No <svg> root element found.")

            # Check for required SVG namespace
            if not re.search(r'xmlns=["\']http://www\.w3\.org/2000/svg["\']', svg_data, re.IGNORECASE):
                raise ValidationError("Invalid SVG file: Missing SVG namespace declaration.")

            # Check for viewBox or width/height attributes
            if not (re.search(r'viewBox=["\'][^"\']*["\']', svg_data, re.IGNORECASE) or
                   (re.search(r'width=["\'][^"\']*["\']', svg_data, re.IGNORECASE) and
                    re.search(r'height=["\'][^"\']*["\']', svg_data, re.IGNORECASE))):
                raise ValidationError("Invalid SVG file: Missing viewBox or width/height attributes.")

            # Check for weld geometry elements
            geometry_elements = re.search(r'<polyline\b[^>]*>|<path\b[^>]*>|<circle\b[^>]*>|<line\b[^>]*>|<rect\b[^>]*>', svg_data, re.DOTALL | re.IGNORECASE)
            if not geometry_elements:
                raise ValidationError(
                    "Invalid SVG file: No weld geometry elements found. "
                    "The SVG must contain at least one of: polyline, path, circle, line, or rect elements."
                )

            # Check for potentially dangerous elements
            dangerous_elements = re.search(r'<script\b|<foreignObject\b|<iframe\b|<image\b|<use\b', svg_data, re.IGNORECASE)
            if dangerous_elements:
                raise ValidationError(
                    "Invalid SVG file: Contains potentially dangerous elements. "
                    "Scripts, foreign objects, iframes, images, and external references are not allowed."
                )

        except ValidationError as ve:
            # Re-raise ValidationError as is since it's already user-friendly
            raise ve
        except Exception as e:
            # Catch any other unexpected errors and provide a user-friendly message
            raise ValidationError(
                f"Error validating SVG file: {str(e)}. "
                "Please ensure the file is a valid SVG document containing weld geometry elements."
            )

    @api.constrains('weld_type', 'iso_2553_symbol')
    def _check_weld_type_symbol(self):
        valid_symbols = {
            'butt': {'square', 'v', 'dv', 'bevel', 'dbevel', 'u', 'backing', 'double_half_Y', 'half_v'},
            'fillet': {'fillet'},
            'stud': {'stud'},
            'other': {'other'},
        }
        for record in self:
            if record.weld_type and record.iso_2553_symbol:
                valid_set = valid_symbols.get(record.weld_type, {'other'})
                if record.iso_2553_symbol not in valid_set:
                    raise ValidationError(
                        f"Invalid ISO 2553 symbol '{record.iso_2553_symbol}' for weld type '{record.weld_type}'. "
                        f"Valid symbols are: {', '.join(valid_set)}."
                    )
