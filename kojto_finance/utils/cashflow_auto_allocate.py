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
#AI_MODEL = "llama3.1:70b"
#AI_MODEL = "gemma2:2b"
#AI_MODEL = "gemma2:9b"
#AI_MODEL = "mistral:7b"
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

def _build_transaction_data(record, include_descriptions=False):
    """Helper function to build transaction data dictionary with all relevant fields."""
    data = {
        'id': record.id,
        'date': str(record.date_value) if record.date_value else "",
        'amount': record.amount,
        'unallocated_amount': record.unallocated_amount,
        'transaction_data_raw': getattr(record, 'transaction_data_raw', None),
        'allocations': [{
            'amount': alloc.amount,
            'invoice_id': alloc.invoice_id.id if alloc.invoice_id else None,
            'invoice_number': alloc.invoice_id.consecutive_number if alloc.invoice_id else None,
            'subcode_id': alloc.subcode_id.id if alloc.subcode_id else None,
            'subcode_code': alloc.subcode_id.code if alloc.subcode_id else None,
            'subcode_name': alloc.subcode_id.name if alloc.subcode_id else None,
            'description': alloc.description if include_descriptions else None,
            'accounting_template_id': alloc.accounting_template_id.id if alloc.accounting_template_id else None,
            'accounting_ref_number': alloc.accounting_ref_number,
            'subtype_id': alloc.subtype_id.id if alloc.subtype_id else None,
            'cash_flow_only': alloc.cash_flow_only
        } for alloc in record.transaction_allocation_ids]
    }
    return data

def _generate_allocation_descriptions(similar_transaction_data, current_transaction_data, num_new_allocations, env):
    """
    Use AI to generate appropriate descriptions for newly created allocations.

    Args:
        similar_transaction_data: Transaction data dict with allocations (including descriptions)
        current_transaction_data: Current transaction data dict with allocations (without descriptions)
        num_new_allocations: Number of new allocations to generate descriptions for
        env: Odoo environment

    Returns:
        List of descriptions (strings) for each new allocation, or None if AI fails
    """
    # Get AI config from first contact
    ai_config = _get_ai_config(env)
    client = OpenAI(base_url=ai_config['api_url'], api_key=ai_config['api_key'], http_client=httpx.Client(verify=False))

    _logger.info("Requesting AI to generate %d allocation descriptions", num_new_allocations)
    _logger.info("Similar transaction data: %s", json.dumps(similar_transaction_data, ensure_ascii=False, indent=2))
    _logger.info("Current transaction data: %s", json.dumps(current_transaction_data, ensure_ascii=False, indent=2))

    for attempt in range(AI_API_RETRIES):
        try:
            messages = [
                {"role": "system", "content": (
                    "You are a JSON API. Output ONLY a valid JSON object: {\"descriptions\": [\"description1\", \"description2\", ...]} and nothing else. "
                    "The descriptions array must have exactly " + str(num_new_allocations) + " elements. "
                    "Each description should be a clear, concise Bulgarian text describing the allocation purpose. "
                    "Do NOT explain, do NOT describe, do NOT output markdown, do NOT output any text before or after the JSON."
                )},
                {"role": "user", "content": f"""Similar historical transaction (as reference):
{json.dumps(similar_transaction_data, ensure_ascii=False, indent=2)}

Current transaction with new allocations (need descriptions):
{json.dumps(current_transaction_data, ensure_ascii=False, indent=2)}

Generate appropriate descriptions for each of the {num_new_allocations} new allocations in the current transaction.
Consider:
1. The similar transaction's allocation descriptions as examples
2. The subcode/invoice being allocated to
3. The transaction context (amount, date, transaction_data_raw)
4. Keep descriptions concise and informative in Bulgarian"""}
            ]

            response = client.chat.completions.create(
                model=AI_MODEL,
                messages=messages,
                temperature=AI_TEMPERATURE,
                top_p=AI_TOP_P,
                max_tokens=500,
                n=1,
                timeout=AI_API_TIMEOUT
            )

            response_text = response.choices[0].message.content or ""
            try:
                result = json.loads(response_text)
                descriptions = result.get('descriptions', [])
                if isinstance(descriptions, list) and len(descriptions) == num_new_allocations:
                    _logger.info("AI generated descriptions: %s", descriptions)
                    return descriptions
                _logger.error("Invalid descriptions format or count: expected %d, got %s", num_new_allocations, descriptions)
            except (json.JSONDecodeError, KeyError) as e:
                _logger.error("Failed to parse JSON response: %s (error: %s)", response_text[:200], str(e))
        except Exception as e:
            _logger.error("AI request failed for descriptions (attempt %d/%d): %s", attempt + 1, AI_API_RETRIES, str(e))

    _logger.error("Failed to generate descriptions after %d attempts", AI_API_RETRIES)
    return None

def auto_allocate_for_transaction(self):
    """
    Automatically allocate transactions using AI-driven similarity analysis with DeepSeek-R1:14b via Ollama's OpenAI-compatible API.

    - Identifies the most similar historical transaction from the same bank account and direction, where the sum of its allocations equals its total amount.
    - If the similar transaction has a single allocation to a subcode, allocates the current transaction's full unallocated amount to the same subcode with the same description.
    - If the similar transaction has a single allocation to an invoice, queries the AI to find the most suitable open invoice (from 100 invoices with open amounts, matching the opposite direction of the transaction) and allocates the full unallocated amount to that invoice.
    - In all other cases (e.g., no similar transaction, multiple allocations, or no suitable invoice), returns 'No auto allocation possible'.
    - Ensures allocations are logged and marked as auto-allocated for tracking purposes.
    """
    for record in self:
        if record.unallocated_amount <= 0:
            return "No auto allocation possible"

        similar_id = find_most_similar_transaction(record)
        if not similar_id:
            return "No auto allocation possible"

        similar = self.browse(similar_id)
        allocations = similar.transaction_allocation_ids

        if len(allocations) == 0:
            return "No auto allocation possible"

        # Handle single allocation case
        if len(allocations) == 1:
            alloc = allocations[0]
        else:
            # Handle multiple allocations - find the most similar allocation
            # For small amounts (like bank charges), prefer allocations that are likely to be charges/fees
            # Look for subcodes that might indicate bank charges or fees
            bank_charge_keywords = ['bank', 'charge', 'fee', 'commission', 'service']

            # First, try to find an allocation with bank-related keywords in subcode name
            for allocation in allocations:
                if allocation.subcode_id and allocation.subcode_id.name:
                    subcode_name_lower = allocation.subcode_id.name.lower()
                    if any(keyword in subcode_name_lower for keyword in bank_charge_keywords):
                        alloc = allocation
                        break
            else:
                # If no bank-related allocation found, use the smallest allocation
                # (likely to be a charge/fee rather than a main payment)
                alloc = min(allocations, key=lambda x: x.amount)

        if alloc.subcode_id:
            # Prepare new allocation data for AI description generation
            new_alloc_data = {
                'amount': record.unallocated_amount,
                'subcode_id': alloc.subcode_id.id,
                'subcode_code': alloc.subcode_id.code,
                'subcode_name': alloc.subcode_id.name,
                'invoice_id': None,
                'invoice_number': None,
                'description': None,
                'accounting_template_id': alloc.accounting_template_id.id if alloc.accounting_template_id else None,
                'accounting_ref_number': alloc.accounting_ref_number if alloc.accounting_ref_number else None,
                'subtype_id': alloc.subtype_id.id if alloc.subtype_id else None,
                'cash_flow_only': alloc.cash_flow_only,
            }

            # Build transaction data for AI
            similar_transaction_data = _build_transaction_data(similar, include_descriptions=True)
            current_transaction_data = _build_transaction_data(record, include_descriptions=False)
            current_transaction_data['allocations'] = [new_alloc_data]  # Add the new allocation

            # Generate description using AI
            ai_descriptions = _generate_allocation_descriptions(similar_transaction_data, current_transaction_data, 1, record.env)
            # Fallback to transaction description if AI fails
            transaction_description = getattr(record, 'transaction_data_raw', None) or getattr(record, 'description', '') or ''
            generated_description = ai_descriptions[0] if ai_descriptions else transaction_description

            # Allocate to same subcode with all accounting fields
            # Template is already validated to have correct primary_type during transaction filtering
            alloc_vals = {
                'amount': record.unallocated_amount,
                'subcode_id': alloc.subcode_id.id,
                'description': generated_description,
                'auto_allocated': True,
                'accounting_template_id': alloc.accounting_template_id.id if alloc.accounting_template_id else False,
                'accounting_ref_number': alloc.accounting_ref_number if alloc.accounting_ref_number else False,
                'subtype_id': alloc.subtype_id.id if alloc.subtype_id else False,
                'cash_flow_only': alloc.cash_flow_only,
            }

            _logger.info("Creating allocation with vals: %s", alloc_vals)
            record.write({'transaction_allocation_ids': [(0, 0, alloc_vals)]})
            if ai_descriptions:
                _logger.info("Allocated transaction %s to subcode %s with AI-generated description: %s", record.id, alloc.subcode_id.id, generated_description)
            else:
                _logger.info("Allocated transaction %s to subcode %s with transaction description (AI failed): %s", record.id, alloc.subcode_id.id, generated_description)
            return True

        elif alloc.invoice_id:
            # New logic: Find all open, opposite-direction invoices
            invoice_direction = 'incoming' if record.transaction_direction == 'outgoing' else 'outgoing'
            domain = [
                ('document_in_out_type', '=', invoice_direction),
                ('open_amount', '!=', 0)
            ]
            if record.counterparty_id:
                domain.append(('counterparty_id', '=', record.counterparty_id.id))
            else:
                # No counterparty: filter out invoices older than 4 months
                from datetime import datetime, timedelta
                four_months_ago = (datetime.now() - timedelta(days=120)).date()
                domain.append(('date_issue', '>=', str(four_months_ago)))
            invoices = self.env['kojto.finance.invoices'].search(domain, order='id desc', limit=100)

            # Prepare lists for ordering
            description = (getattr(record, 'description', None) or getattr(record, 'transaction_description', '') or '').lower()
            invoices_with_match = []
            invoices_without_match = []
            for inv in invoices:
                consecutive_number = str(inv.consecutive_number)
                if consecutive_number and consecutive_number in description:
                    invoices_with_match.append(inv)
                else:
                    invoices_without_match.append(inv)
            ordered_invoices = invoices_with_match + invoices_without_match

            # First pass: prepare new allocations data for AI
            remaining_amount = record.unallocated_amount
            new_allocations_data = []
            for inv in ordered_invoices:
                if remaining_amount <= 0:
                    break
                alloc_amount = min(remaining_amount, inv.open_amount)
                if alloc_amount <= 0:
                    continue
                new_alloc_data = {
                    'amount': alloc_amount,
                    'invoice_id': inv.id,
                    'invoice_number': inv.consecutive_number,
                    'subcode_id': inv.subcode_id.id if inv.subcode_id else None,
                    'subcode_code': inv.subcode_id.code if inv.subcode_id else None,
                    'subcode_name': inv.subcode_id.name if inv.subcode_id else None,
                    'description': None,
                    'accounting_template_id': alloc.accounting_template_id.id if alloc.accounting_template_id else None,
                    'accounting_ref_number': alloc.accounting_ref_number if alloc.accounting_ref_number else None,
                    'subtype_id': alloc.subtype_id.id if alloc.subtype_id else None,
                    'cash_flow_only': alloc.cash_flow_only,
                }
                new_allocations_data.append((inv, alloc_amount, new_alloc_data))
                remaining_amount -= alloc_amount

            if not new_allocations_data:
                return "No auto allocation possible"

            # Build transaction data for AI
            similar_transaction_data = _build_transaction_data(similar, include_descriptions=True)
            current_transaction_data = _build_transaction_data(record, include_descriptions=False)
            current_transaction_data['allocations'] = [data[2] for data in new_allocations_data]  # Add all new allocations

            # Generate descriptions using AI
            ai_descriptions = _generate_allocation_descriptions(similar_transaction_data, current_transaction_data, len(new_allocations_data), record.env)

            # Fallback to transaction description if AI fails
            transaction_description = getattr(record, 'transaction_data_raw', None) or getattr(record, 'description', '') or ''

            # Second pass: create allocations with AI-generated descriptions
            # Template is already validated to have correct primary_type during transaction filtering
            allocations = []
            for idx, (inv, alloc_amount, new_alloc_data) in enumerate(new_allocations_data):
                # Use AI-generated description if available, otherwise fallback to transaction description
                generated_description = ai_descriptions[idx] if ai_descriptions and idx < len(ai_descriptions) else transaction_description

                alloc_vals = {
                    'amount': alloc_amount,
                    'invoice_id': inv.id,
                    'subcode_id': inv.subcode_id.id if inv.subcode_id else False,
                    'description': generated_description,
                    'auto_allocated': True,
                    'accounting_template_id': alloc.accounting_template_id.id if alloc.accounting_template_id else False,
                    'accounting_ref_number': alloc.accounting_ref_number if alloc.accounting_ref_number else False,
                    'subtype_id': alloc.subtype_id.id if alloc.subtype_id else False,
                    'cash_flow_only': alloc.cash_flow_only,
                }

                _logger.info("Creating allocation with vals: %s", alloc_vals)
                allocations.append((0, 0, alloc_vals))
                if ai_descriptions:
                    _logger.info("Allocated transaction %s to invoice %s for amount %s with AI-generated description: %s",
                               record.id, inv.id, alloc_amount, generated_description)
                else:
                    _logger.info("Allocated transaction %s to invoice %s for amount %s with transaction description (AI failed): %s",
                               record.id, inv.id, alloc_amount, generated_description)

            if allocations:
                record.write({'transaction_allocation_ids': allocations})
                return True
            return "No auto allocation possible"

        return "No auto allocation possible"

    return "No auto allocation possible"

def find_most_similar_transaction(record):
    """
    Find the historical transaction most similar to the current transaction using DeepSeek-R1:14b via Ollama's OpenAI-compatible API.
    Returns only the ID of the most similar transaction.
    """
    # Get AI config from first contact
    ai_config = _get_ai_config(record.env)
    # Fetch historical transactions with same counterparty (no amount restrictions)
    transactions = record.search([
        ('bank_account_id', '=', record.bank_account_id.id),
        ('transaction_direction', '=', record.transaction_direction),
        ('counterparty_id', '=', record.counterparty_id.id),
        ('id', '!=', record.id)
    ], order='id desc', limit=20)

    # If no transactions found with same counterparty, look for transactions with similar amounts (±100%)
    if not transactions:
        amount_min = record.amount * 0.5  # -50% (allowing for ±100% range)
        amount_max = record.amount * 2.0  # +100%

        transactions = record.search([
            ('bank_account_id', '=', record.bank_account_id.id),
            ('transaction_direction', '=', record.transaction_direction),
            ('amount', '>=', amount_min),
            ('amount', '<=', amount_max),
            ('id', '!=', record.id)
        ], order='id desc', limit=20)

        _logger.info("No transactions found with same counterparty, searching for similar amounts (%.2f - %.2f)", amount_min, amount_max)

    # Determine expected primary_type for cashflow transactions
    expected_ptype = "cashflow_in" if record.transaction_direction == "incoming" else "cashflow_out"

    # Filter transactions where sum of allocations equals transaction amount
    transactions_data = []
    transactions_data_no_accounting = []
    for t in transactions:
        alloc_sum = sum(alloc.amount for alloc in t.transaction_allocation_ids)
        if abs(alloc_sum - t.amount) <= 0.01:
            transaction_data = _build_transaction_data(t)
            # Check if at least one allocation has accounting template with correct primary_type
            has_correct_accounting = any(
                alloc.get('accounting_template_id') and
                record.env['kojto.finance.accounting.templates'].browse(alloc.get('accounting_template_id')).primary_type == expected_ptype
                for alloc in transaction_data['allocations']
            )
            # Check if has any accounting fields (for fallback)
            has_accounting_fields = any(
                alloc.get('accounting_template_id') or
                alloc.get('accounting_ref_number') or
                alloc.get('subtype_id')
                for alloc in transaction_data['allocations']
            )
            if has_correct_accounting:
                transactions_data.append(transaction_data)
            elif has_accounting_fields:
                transactions_data_no_accounting.append(transaction_data)
            else:
                transactions_data_no_accounting.append(transaction_data)

    # If we have transactions with correct accounting templates, use only those
    # Otherwise, fall back to transactions with any accounting fields (or none)
    if not transactions_data:
        transactions_data = transactions_data_no_accounting
        _logger.info("No historical transactions with correct primary_type (%s) found, using %d transactions as fallback", expected_ptype, len(transactions_data))
    else:
        _logger.info("Found %d historical transactions with correct primary_type (%s) (excluding %d without)", len(transactions_data), expected_ptype, len(transactions_data_no_accounting))

    if not transactions_data:
        _logger.info("No valid historical transactions for transaction %s", record.id)
        # Try one more time with even more relaxed criteria - look for any transactions with similar amounts
        _logger.info("Trying relaxed search for transaction %s with similar amounts", record.id)

        # Use even wider range for final attempt (±200%)
        amount_min = record.amount * 0.33  # -67% (allowing for ±200% range)
        amount_max = record.amount * 3.0   # +200%

        relaxed_transactions = record.search([
            ('bank_account_id', '=', record.bank_account_id.id),
            ('transaction_direction', '=', record.transaction_direction),
            ('amount', '>=', amount_min),
            ('amount', '<=', amount_max),
            ('id', '!=', record.id)
        ], order='id desc', limit=10)

        for t in relaxed_transactions:
            transaction_data = _build_transaction_data(t)
            transactions_data.append(transaction_data)

        if transactions_data:
            _logger.info("Found %d transactions with relaxed criteria (amount range %.2f - %.2f)", len(transactions_data), amount_min, amount_max)
        else:
            _logger.info("No transactions found even with relaxed criteria")
            return None

    current_transaction = _build_transaction_data(record)

    # Print the number of transactions and the JSON sent
    valid_ids = [t['id'] for t in transactions_data]
    _logger.info("Sending %d historical transactions to AI for similarity:", len(transactions_data))
    _logger.info("Historical transactions JSON: %s", json.dumps(transactions_data, ensure_ascii=False, indent=2))
    _logger.info("Current transaction JSON: %s", json.dumps(current_transaction, ensure_ascii=False, indent=2))

    # Initialize client
    client = OpenAI(base_url=ai_config['api_url'], api_key=ai_config['api_key'], http_client=httpx.Client(verify=False))

    for attempt in range(AI_API_RETRIES):
        try:
            messages = [
                {"role": "system", "content": (
                    "You are a JSON API. Output ONLY a valid JSON object: {\"most_similar_transaction_id\": <ID or null>} and nothing else. "
                    "Valid transaction IDs: " + str(valid_ids) + ". "
                    "If you output anything else, it will be ignored. Do NOT explain, do NOT describe, do NOT output markdown, do NOT output any text before or after the JSON."
                )},
                {"role": "user", "content": f"Current transaction:\n{json.dumps(current_transaction, ensure_ascii=False, indent=2)}"},
                {"role": "user", "content": f"Historical transactions:\n{json.dumps(transactions_data, ensure_ascii=False, indent=2)}"},
                {"role": "user", "content": (
                    "Find the most similar transaction based on:\n"
                    "1. Amount similarity (prefer transactions with similar amounts, especially for small amounts like bank charges)\n"
                    "2. Transaction type/purpose (bank charges vs salary payments vs invoices, etc.)\n"
                    "3. Description keywords and patterns\n"
                    "4. Allocation patterns (similar subcodes)\n"
                    "For small amounts (<100), prioritize other small amounts and similar transaction types.\n"
                    "Return null if no transaction is reasonably similar."
                )}
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
                most_similar_id = json.loads(response_text)['most_similar_transaction_id']
                if isinstance(most_similar_id, int) and most_similar_id in {t['id'] for t in transactions_data}:
                    _logger.info("Most similar transaction for %s: %s", record.id, most_similar_id)
                    return most_similar_id
                _logger.error("Invalid transaction ID: %s", most_similar_id)
            except (json.JSONDecodeError, KeyError):
                _logger.error("Failed to parse JSON response: %s", response_text[:200])
        except Exception as e:
            _logger.error("AI request failed (attempt %d/%d): %s", attempt + 1, AI_API_RETRIES, str(e))

    _logger.error("No similar transaction found for %s after %d attempts", record.id, AI_API_RETRIES)
    return None

def find_most_suitable_invoice(self):
    """
    Find the most suitable open invoice for the current transaction using AI.
    Returns the ID of the most suitable invoice.
    """
    for record in self:
        # Determine invoice direction
        invoice_direction = 'incoming' if record.transaction_direction == 'outgoing' else 'outgoing'

        # Fetch open invoices with matching counterparty
        invoices = self.env['kojto.finance.invoices'].search([
            ('document_in_out_type', '=', invoice_direction),
            ('open_amount', '!=', 0),
            ('counterparty_id', '=', record.counterparty_id.id)
        ], order='id desc', limit=100)

        invoices_data = [{
                    'id': inv.id,
                    'number': inv.consecutive_number,
                    'date': str(inv.date_issue) if inv.date_issue else "",
                    'open_amount': inv.open_amount,
                    'total_price': inv.total_price,
            'counterparty': inv.counterparty_id.display_name if inv.counterparty_id else None,
            'direction': inv.document_in_out_type
        } for inv in invoices]

        if not invoices_data:
            _logger.info("No open invoices for transaction %s", record.id)
            return None

        current_transaction = _build_transaction_data(record)

        # Get AI config from first contact
        ai_config = _get_ai_config(self.env)
        # Initialize client
        client = OpenAI(base_url=ai_config['api_url'], api_key=ai_config['api_key'], http_client=httpx.Client(verify=False))

        for attempt in range(AI_API_RETRIES):
            try:
                messages = [
                    {"role": "system", "content": "Output ONLY a valid JSON object with a single field 'most_suitable_invoice_id' containing the ID (integer) of the most suitable invoice. No other text or fields."},
                    {"role": "user", "content": f"Current transaction:\n{json.dumps(current_transaction, ensure_ascii=False, indent=2)}"},
                    {"role": "user", "content": f"Open invoices:\n{json.dumps(invoices_data, ensure_ascii=False, indent=2)}"},
                    {"role": "user", "content": "Identify the open invoice most suitable for allocation to the current transaction based on matching amount to unallocated_amount, description keywords, partner, date proximity, etc. Prefer invoices where open_amount >= unallocated_amount. Output only the JSON object with 'most_suitable_invoice_id'."}
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
                    most_suitable_id = json.loads(response_text)['most_suitable_invoice_id']
                    invoice = next((inv for inv in invoices if inv.id == most_suitable_id), None)
                    if invoice and isinstance(most_suitable_id, int) and invoice.open_amount >= record.unallocated_amount - 0.01:
                        _logger.info("Most suitable invoice for %s: %s", record.id, most_suitable_id)
                        return most_suitable_id
                    _logger.error("Invalid or insufficient open amount for invoice ID: %s", most_suitable_id)
                except (json.JSONDecodeError, KeyError):
                    _logger.error("Failed to parse JSON response: %s", response_text[:200])
            except Exception as e:
                _logger.error("AI request failed (attempt %d/%d): %s", attempt + 1, AI_API_RETRIES, str(e))

        _logger.error("No suitable invoice found for %s after %d attempts", record.id, AI_API_RETRIES)
        return None
