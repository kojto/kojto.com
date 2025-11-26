import re
import logging

_logger = logging.getLogger(__name__)

def FINVBGSF_parse_transaction_data(transaction_content):
    try:
        _logger.info(f"Starting FINVBGSF parsing for transaction: {transaction_content[:100]}...")

        data = transaction_content.replace('\n', '')
        _logger.info(f"Cleaned data: {data[:200]}...")

        start_86 = data.find(':86:')
        start_61 = data.find(':61:')
        _logger.info(f"Found :86: at position {start_86}, :61: at position {start_61}")

        credit_mark = data[start_61 + 14] if start_61 != -1 and len(data) > start_61 + 14 else ''
        _logger.info(f"Credit mark: '{credit_mark}'")

        # Parse the :86: section which contains transaction details
        parts = data[start_86 + 4:].split('^') if start_86 != -1 else []
        _logger.info(f"Parsed parts from :86: section: {parts}")

        # Extract IBAN from the transaction details
        iban_match = re.search(r"BG\d{2}[A-Z0-9]{4,30}", data)
        counterparty_iban = iban_match.group(0) if iban_match else ""
        _logger.info(f"Found IBAN: '{counterparty_iban}'")

        # Extract company name (usually in part with index 32)
        company_name = ""
        for part in parts:
            if part.startswith('32'):
                company_name = part[2:].strip()
                break
        _logger.info(f"Found company name: '{company_name}'")

        # Extract reference number (usually in part with index 30)
        reference_number = ""
        for part in parts:
            if part.startswith('30'):
                reference_number = part[2:].strip()
                break
        _logger.info(f"Found reference number: '{reference_number}'")

        # Extract invoice/payment reference (usually in part with index 20 or 21)
        payment_reference = ""
        for part in parts:
            if part.startswith('20'):
                payment_reference = part[2:].strip()
                break
            elif part.startswith('21'):
                payment_reference = part[2:].strip()
                break
        _logger.info(f"Found payment reference: '{payment_reference}'")

        result = {
            "transaction_code": parts[0].strip() if len(parts) > 0 else "",
            "description": parts[1].strip() if len(parts) > 1 else "",
            "related_reference": reference_number,
            "counterparty_iban": counterparty_iban,
            "company_name": company_name,
            "payment_reference": payment_reference,
        }

        # For debit transactions, try to find additional reference information
        if credit_mark == 'D':
            _logger.info("Processing debit transaction for additional references")
            # Look for additional reference in description or other parts
            if not result["related_reference"] and len(parts) > 1:
                # Try to extract reference from description
                desc = parts[1] if len(parts) > 1 else ""
                ref_match = re.search(r'No\s+(\d+)', desc)
                if ref_match:
                    result["related_reference"] = ref_match.group(1)
                    _logger.info(f"Found additional reference in description: '{ref_match.group(1)}'")

        _logger.info(f"Final result: {result}")
        return result

    except Exception as e:
        _logger.error(f"Error in FINVBGSF_parse_transaction_data: {str(e)}")
        _logger.error(f"Transaction content: {transaction_content}")
        raise
