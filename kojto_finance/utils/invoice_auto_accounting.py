import json
import logging
import httpx
from openai import OpenAI
from odoo.exceptions import UserError
from odoo import _

_logger = logging.getLogger(__name__)

# AI Configuration
AI_API_TIMEOUT = 60
AI_API_RETRIES = 3
AI_MODEL = "llama3.1:8b"
AI_TEMPERATURE = 0.3
AI_TOP_P = 0.9

def _get_ai_config(env):
    """Get AI configuration from the first contact. Raises UserError if missing."""
    config = env['kojto.contacts'].get_ai_config()

    if not config.get('api_url') or not config['api_url'].strip():
        raise UserError(_(
            "AI API URL is not configured. Please set the AI API URL in the first contact (ID: 1)."
        ))

    if not config.get('api_key') or not config['api_key'].strip():
        raise UserError(_(
            "AI API Key is not configured. Please set the AI API Key in the first contact (ID: 1)."
        ))

    return {
        'api_url': config['api_url'].strip(),
        'api_key': config['api_key'].strip()
    }

def _build_invoice_content_data(content):
    """Helper function to build invoice content data dictionary with all relevant fields."""
    data = {
        'id': content.id,
        'position': content.position,
        'name': content.name,
        'quantity': content.quantity,
        'unit_id': content.unit_id.id if content.unit_id else None,
        'unit_name': content.unit_id.name if content.unit_id else None,
        'unit_price': content.unit_price,
        'pre_vat_total': content.pre_vat_total,
        'vat_rate': content.vat_rate,
        'subcode_id': content.subcode_id.id if content.subcode_id else None,
        'subcode_name': content.subcode_id.display_name if content.subcode_id else None,
        'vat_treatment_id': content.vat_treatment_id.id if content.vat_treatment_id else None,
        'vat_treatment_name': content.vat_treatment_id.display_name if content.vat_treatment_id else None,
        'accounting_template_id': content.accounting_template_id.id if content.accounting_template_id else None,
        'accounting_template_name': content.accounting_template_id.display_name if content.accounting_template_id else None,
        'identifier_id': content.identifier_id.id if content.identifier_id else None,
        'identifier_name': content.identifier_id.display_name if content.identifier_id else None,
        'subtype_id': content.subtype_id.id if content.subtype_id else None,
        'subtype_name': content.subtype_id.display_name if content.subtype_id else None,
    }
    return data

def auto_accounting_for_content(content_line):
    """
    Automatically set accounting fields for a single invoice content line using AI-driven analysis.

    Steps:
    1. From content -> find the invoice direction and counterparty
    2. Find the last up to 30 invoice contents that share the same counterparty_id and direction
    3. Send the current content (where the button is pressed) as goal and the 30 contents to the AI
    4. AI identifies the most similar historical content
    5. Copy accounting fields from that similar content

    Returns message indicating success or failure.
    """
    # Step 1: Get invoice direction and counterparty from the content's invoice
    if not content_line.invoice_id:
        _logger.info("Cannot auto-account: Content has no invoice.")
        return "Cannot auto-account: Content has no invoice."

    invoice = content_line.invoice_id
    direction = invoice.document_in_out_type
    counterparty_id = invoice.counterparty_id.id if invoice.counterparty_id else None

    if not counterparty_id:
        _logger.info("Cannot auto-account: No counterparty set on invoice.")
        return "Cannot auto-account: No counterparty set on invoice."

    if content_line.is_redistribution:
        _logger.info("Cannot auto-account: Redistribution lines are not supported.")
        return "Cannot auto-account: Redistribution lines are not supported."

    # Step 2: Find last up to 30 invoice contents with same counterparty and direction
    # Determine expected primary_type for invoice contents
    expected_ptype = "purchase" if direction == "incoming" else "sale"

    content_domain = [
        ('invoice_id.document_in_out_type', '=', direction),
        ('invoice_id.counterparty_id', '=', counterparty_id),
        ('id', '!=', content_line.id),  # Exclude current content
        ('is_redistribution', '=', False),  # Exclude redistribution lines
        ('accounting_template_id', '!=', False),  # Only include contents with accounting data
        ('accounting_template_id.primary_type', '=', expected_ptype),  # Only include contents with correct primary_type
    ]

    historical_content_records = content_line.env['kojto.finance.invoice.contents'].search(
        content_domain,
        order='id desc',
        limit=30
    )

    if not historical_content_records:
        _logger.info("Cannot auto-account: No historical invoice contents found with same counterparty, direction, and correct primary_type (%s).", expected_ptype)
        return f"Cannot auto-account: No historical invoice contents found with same counterparty, direction, and correct template type ({expected_ptype})."

    # Collect content data from historical records
    historical_contents = []
    for content in historical_content_records:
        historical_contents.append(_build_invoice_content_data(content))

    _logger.info("Processing content line %s: %s (expected_ptype: %s)", content_line.position, content_line.name, expected_ptype)
    _logger.info("Using %d historical invoice contents as reference (with correct primary_type: %s)", len(historical_contents), expected_ptype)

    # Step 3: Prepare current content data
    current_content = _build_invoice_content_data(content_line)

    # Step 4: Send to AI to find most similar content
    similar_content_id = _get_most_similar_content(
        current_content,
        historical_contents,
        content_line.env
    )

    if not similar_content_id:
        _logger.info("No similar content found for content line %s", content_line.position)
        return "No similar content found."

    # Step 5: Find the similar content record and copy its accounting fields
    similar_content = content_line.env['kojto.finance.invoice.contents'].browse(similar_content_id)

    # Template is already validated to have correct primary_type during content filtering
    update_vals = {
        'vat_treatment_id': similar_content.vat_treatment_id.id if similar_content.vat_treatment_id else False,
        'accounting_template_id': similar_content.accounting_template_id.id if similar_content.accounting_template_id else False,
        'identifier_id': similar_content.identifier_id.id if similar_content.identifier_id else False,
        'subtype_id': similar_content.subtype_id.id if similar_content.subtype_id else False,
        'vat_rate': similar_content.vat_rate,
    }

    # Apply updates
    content_line.write(update_vals)
    _logger.info("Successfully applied accounting fields from similar content %s to content line %s: %s",
                 similar_content_id, content_line.position, update_vals)

    # Refresh the invoice to show updated data
    content_line.invoice_id.invalidate_recordset()

    return f"Successfully applied accounting fields from similar content"


def _get_most_similar_content(current_content, historical_contents, env):
    """
    Find the most similar historical content using AI.

    Returns the ID of the most similar content or None if not found.
    """
    # Get AI config from first contact
    ai_config = _get_ai_config(env)
    # Initialize client
    client = OpenAI(base_url=ai_config['api_url'], api_key=ai_config['api_key'], http_client=httpx.Client(verify=False))

    valid_ids = [c['id'] for c in historical_contents]
    _logger.info("Sending %d historical contents to AI for similarity", len(historical_contents))
    _logger.info("Historical contents JSON: %s", json.dumps(historical_contents, ensure_ascii=False, indent=2))
    _logger.info("Current content JSON: %s", json.dumps(current_content, ensure_ascii=False, indent=2))

    for attempt in range(AI_API_RETRIES):
        try:
            messages = [
                {"role": "system", "content": (
                    "You are a JSON API. Output ONLY a valid JSON object: {\"most_similar_content_id\": <ID or null>} and nothing else. "
                    "Valid content IDs: " + str(valid_ids) + ". "
                    "If you output anything else, it will be ignored. Do NOT explain, do NOT describe, do NOT output markdown, do NOT output any text before or after the JSON."
                )},
                {"role": "user", "content": f"Current invoice content line:\n{json.dumps(current_content, ensure_ascii=False, indent=2)}"},
                {"role": "user", "content": f"Historical invoice contents:\n{json.dumps(historical_contents, ensure_ascii=False, indent=2)}"}
            ]

            response = client.chat.completions.create(
                model=AI_MODEL,
                messages=messages,
                temperature=AI_TEMPERATURE,
                top_p=AI_TOP_P,
                max_tokens=100,
                n=1,
                timeout=AI_API_TIMEOUT
            )

            response_text = response.choices[0].message.content or ""
            try:
                most_similar_id = json.loads(response_text)['most_similar_content_id']
                if isinstance(most_similar_id, int) and most_similar_id in valid_ids:
                    _logger.info("Most similar content for %s: %s", current_content.get('id'), most_similar_id)
                    return most_similar_id
                _logger.error("Invalid content ID: %s", most_similar_id)
            except (json.JSONDecodeError, KeyError):
                _logger.error("Failed to parse JSON response: %s", response_text[:200])
        except Exception as e:
            _logger.error("AI request failed (attempt %d/%d): %s", attempt + 1, AI_API_RETRIES, str(e))

    _logger.error("No similar content found for %s after %d attempts", current_content.get('id'), AI_API_RETRIES)
    return None

