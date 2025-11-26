# -*- coding: utf-8 -*-
"""
Auto Accounting for Cashflow Allocations

This module provides AI-driven automatic accounting field assignment
for cashflow allocations based on historical allocation patterns.
"""

import logging
import json
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

def _build_allocation_data(allocation):
    """
    Build a dictionary with relevant allocation data for AI analysis.
    """
    data = {
        "id": allocation.id,
        "subcode_id": allocation.subcode_id.id,
        "subcode_code": allocation.subcode_id.code if allocation.subcode_id else "",
        "subcode_name": allocation.subcode_id.name if allocation.subcode_id else "",
        "description": allocation.description or "",
        "amount": allocation.amount,
        "transaction_direction": allocation.transaction_direction,
        "counterparty_id": allocation.transaction_id.counterparty_id.id if allocation.transaction_id and allocation.transaction_id.counterparty_id else None,
        "counterparty_name": allocation.transaction_id.counterparty_id.name if allocation.transaction_id and allocation.transaction_id.counterparty_id else "",
        "accounting_template_id": allocation.accounting_template_id.id if allocation.accounting_template_id else None,
        "accounting_template_name": allocation.accounting_template_id.name if allocation.accounting_template_id else "",
        "accounting_ref_number": allocation.accounting_ref_number if allocation.accounting_ref_number else "",
        "subtype_id": allocation.subtype_id.id if allocation.subtype_id else None,
        "subtype_name": allocation.subtype_id.name if allocation.subtype_id else "",
        "cash_flow_only": allocation.cash_flow_only,
    }
    return data

def _get_most_similar_allocation(current_allocation_data, historical_allocations_data, env):
    """
    Use AI to find the most similar allocation from historical data.
    Returns the ID of the most similar allocation or None if not found.
    """
    # Get AI config from first contact
    ai_config = _get_ai_config(env)
    # Initialize client
    client = OpenAI(base_url=ai_config['api_url'], api_key=ai_config['api_key'], http_client=httpx.Client(verify=False))

    valid_ids = [a['id'] for a in historical_allocations_data]
    _logger.info("Sending %d historical allocations to AI for similarity", len(historical_allocations_data))
    _logger.info("Historical allocations JSON: %s", json.dumps(historical_allocations_data, ensure_ascii=False, indent=2))
    _logger.info("Current allocation JSON: %s", json.dumps(current_allocation_data, ensure_ascii=False, indent=2))

    for attempt in range(AI_API_RETRIES):
        try:
            messages = [
                {"role": "system", "content": (
                    "You are a JSON API. Output ONLY a valid JSON object: {\"most_similar_allocation_id\": <ID or null>} and nothing else. "
                    "Valid allocation IDs: " + str(valid_ids) + ". "
                    "If you output anything else, it will be ignored. Do NOT explain, do NOT describe, do NOT output markdown, do NOT output any text before or after the JSON."
                )},
                {"role": "user", "content": f"""Current cashflow allocation:
{json.dumps(current_allocation_data, ensure_ascii=False, indent=2)}

Find the most similar allocation based on:
1. Subcode match (highest priority)
2. Description similarity (second priority)
3. Amount similarity (third priority)

Note: All historical allocations already match the transaction direction, counterparty, and amount sign."""},
                {"role": "user", "content": f"Historical allocations:\n{json.dumps(historical_allocations_data, ensure_ascii=False, indent=2)}"}
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
                most_similar_id = json.loads(response_text)['most_similar_allocation_id']
                if isinstance(most_similar_id, int) and most_similar_id in valid_ids:
                    _logger.info("Most similar allocation for %s: %s", current_allocation_data.get('id'), most_similar_id)
                    return most_similar_id
                _logger.error("Invalid allocation ID: %s", most_similar_id)
            except (json.JSONDecodeError, KeyError):
                _logger.error("Failed to parse JSON response: %s", response_text[:200])
        except Exception as e:
            _logger.error("AI request failed (attempt %d/%d): %s", attempt + 1, AI_API_RETRIES, str(e))

    _logger.error("No similar allocation found for %s after %d attempts", current_allocation_data.get('id'), AI_API_RETRIES)
    return None

def auto_accounting_for_allocation(allocation):
    """
    Automatically set accounting fields for a single cashflow allocation using AI-driven analysis.

    Steps:
    1. From allocation -> find the transaction direction, counterparty, and amount sign
    2. Find the last 20 allocations that share the same direction, counterparty, and amount sign with accounting fields set
    3. Send the current allocation (where the button is pressed) as goal and the 20 allocations to the AI
    4. AI identifies the most similar historical allocation
    5. Copy accounting fields from that similar allocation

    Returns message indicating success or failure.
    """
    try:
        # Step 1: Get transaction direction, counterparty, and amount sign from the allocation
        _logger.info("=== AUTO ACCOUNTING START for allocation ID: %s ===", allocation.id)

        if not allocation.transaction_id:
            _logger.warning("Cannot auto-account: Allocation has no transaction.")
            return "Cannot auto-account: Allocation has no transaction."

        transaction = allocation.transaction_id
        direction = transaction.transaction_direction
        counterparty_id = transaction.counterparty_id.id if transaction.counterparty_id else None
        amount_sign = 1 if allocation.amount >= 0 else -1

        _logger.info("Allocation details - Direction: %s, Counterparty ID: %s, Amount: %s, Sign: %s",
                     direction, counterparty_id, allocation.amount, "+" if amount_sign >= 0 else "-")

        if not counterparty_id:
            _logger.warning("Cannot auto-account: No counterparty set on transaction.")
            return "❌ Cannot auto-account: Please set a counterparty on the transaction first."

        if not allocation.subcode_id:
            _logger.warning("Cannot auto-account: Allocation must have a subcode.")
            return "❌ Cannot auto-account: Please select a subcode first."
    except Exception as e:
        _logger.error("Error in Step 1 of auto_accounting: %s", str(e), exc_info=True)
        return f"Error in auto accounting: {str(e)}"

    try:
        # Step 2: Find last 20 allocations with same direction, counterparty, and amount sign with accounting fields
        # Determine expected primary_type for cashflow allocations
        expected_ptype = "cashflow_in" if direction == "incoming" else "cashflow_out"

        allocation_domain = [
            ('transaction_id.transaction_direction', '=', direction),
            ('transaction_id.counterparty_id', '=', counterparty_id),
            ('id', '!=', allocation.id),  # Exclude current allocation
            ('accounting_template_id', '!=', False),  # Only include allocations with accounting data
            ('accounting_template_id.primary_type', '=', expected_ptype),  # Only include allocations with correct primary_type
        ]

        # Add amount sign filter
        if amount_sign >= 0:
            allocation_domain.append(('amount', '>=', 0))
        else:
            allocation_domain.append(('amount', '<', 0))

        _logger.info("Searching with domain: %s", allocation_domain)

        historical_allocation_records = allocation.env['kojto.finance.cashflow.allocation'].search(
            allocation_domain,
            order='id desc',
            limit=20
        )

        _logger.info("Found %d historical allocations with correct primary_type (%s)", len(historical_allocation_records), expected_ptype)

        if not historical_allocation_records:
            _logger.warning("Cannot auto-account: No historical allocations found with same direction, counterparty, amount sign, and correct primary_type (%s).", expected_ptype)
            return f"❌ Cannot auto-account: No historical allocations found with same direction, counterparty, amount sign, and correct template type ({expected_ptype}). Please set accounting fields manually for the first allocation."

        # Collect allocation data from historical records
        # Double-check that each allocation has an accounting template set
        historical_allocations = []
        for alloc in historical_allocation_records:
            if alloc.accounting_template_id:
                historical_allocations.append(_build_allocation_data(alloc))
            else:
                _logger.warning("Skipping allocation %s - no accounting template set", alloc.id)

        if not historical_allocations:
            _logger.warning("Cannot auto-account: No historical allocations with accounting templates found after filtering.")
            return "❌ Cannot auto-account: No historical allocations with accounting templates found. Please set accounting fields manually for the first allocation."

        counterparty_name = transaction.counterparty_id.name if transaction.counterparty_id else "Unknown"
        _logger.info("Processing allocation %s for subcode: %s, direction: %s, counterparty: %s, amount_sign: %s, expected_ptype: %s",
                     allocation.id, allocation.subcode_id.display_name, direction, counterparty_name, "+" if amount_sign >= 0 else "-", expected_ptype)
        _logger.info("Using %d historical allocations as reference (with correct primary_type: %s)", len(historical_allocations), expected_ptype)
    except Exception as e:
        _logger.error("Error in Step 2 of auto_accounting: %s", str(e), exc_info=True)
        return f"Error searching historical allocations: {str(e)}"

    try:
        # Step 3: Prepare current allocation data
        current_allocation = _build_allocation_data(allocation)
        _logger.info("Current allocation data prepared: %s", current_allocation)

        # Step 4: Send to AI to find most similar allocation
        _logger.info("Sending to AI for similarity analysis...")
        similar_allocation_id = _get_most_similar_allocation(
            current_allocation,
            historical_allocations,
            allocation.env
        )

        if not similar_allocation_id:
            _logger.warning("AI did not find a similar allocation for allocation %s", allocation.id)
            # Try to find a default accounting template based on transaction direction
            return _try_set_default_accounting_template(allocation)

        _logger.info("AI identified similar allocation: %s", similar_allocation_id)
    except Exception as e:
        _logger.error("Error in Step 3-4 of auto_accounting: %s", str(e), exc_info=True)
        return f"Error during AI analysis: {str(e)}"

    try:
        # Step 5: Find the similar allocation record and copy its accounting fields
        similar_allocation = allocation.env['kojto.finance.cashflow.allocation'].browse(similar_allocation_id)

        if not similar_allocation.exists():
            _logger.error("Similar allocation %s does not exist!", similar_allocation_id)
            return f"Similar allocation (ID: {similar_allocation_id}) not found in database."

        update_vals = {
            'accounting_template_id': similar_allocation.accounting_template_id.id if similar_allocation.accounting_template_id else False,
            'accounting_ref_number': similar_allocation.accounting_ref_number if similar_allocation.accounting_ref_number else False,
            'subtype_id': similar_allocation.subtype_id.id if similar_allocation.subtype_id else False,
            'cash_flow_only': similar_allocation.cash_flow_only,
        }

        _logger.info("Applying update values: %s", update_vals)

        # Apply updates
        allocation.write(update_vals)
        _logger.info("Successfully applied accounting fields from similar allocation %s to allocation %s: %s",
                     similar_allocation_id, allocation.id, update_vals)

        return f"✅ Successfully applied accounting fields from similar allocation (ID: {similar_allocation_id})"
    except Exception as e:
        _logger.error("Error in Step 5 of auto_accounting: %s", str(e), exc_info=True)
        return f"Error applying accounting fields: {str(e)}"


def _try_set_default_accounting_template(allocation):
    """
    Try to set a default accounting template when no historical data is available.
    This is a fallback mechanism for the auto accounting feature.
    """
    try:
        _logger.info("Trying to set default accounting template for allocation %s", allocation.id)

        if not allocation.transaction_id or not allocation.transaction_id.transaction_direction:
            return "❌ Cannot set default: No transaction direction available."

        # Find a default accounting template based on transaction direction
        ptype = "cashflow_in" if allocation.transaction_id.transaction_direction == "incoming" else "cashflow_out"

        default_template = allocation.env['kojto.finance.accounting.templates'].search([
            ('template_type_id.primary_type', '=', ptype)
        ], limit=1)

        if not default_template:
            return f"❌ No default accounting template found for {ptype}. Please set accounting fields manually."

        # Set the default template
        allocation.write({
            'accounting_template_id': default_template.id,
            'cash_flow_only': False,  # Default value
        })

        _logger.info("Set default accounting template %s for allocation %s", default_template.name, allocation.id)
        return f"✅ Set default accounting template: {default_template.name}"

    except Exception as e:
        _logger.error("Error setting default accounting template: %s", str(e), exc_info=True)
        return f"❌ Error setting default template: {str(e)}"

