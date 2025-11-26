import re

def UBBSBGSF_parse_transaction_data(transaction_content):
    data = transaction_content.replace('\n', '')
    start_86 = data.find(':86:')
    start_61 = data.find(':61:')
    credit_mark = data[start_61 + 14] if start_61 != -1 and len(data) > start_61 + 14 else ''

    parts = data[start_86 + 4:].split('/') if start_86 != -1 else []

    iban_match = re.search(r"/[A-Z]{2}\d{2}[A-Z0-9]{4,30}/", data)
    counterparty_iban = iban_match.group(0).strip('/') if iban_match else ""

    result = {
        "transaction_code": parts[0].strip() if len(parts) > 0 else "",
        "description": parts[1].strip() if len(parts) > 1 else "",
        "related_reference": parts[18].strip() if len(parts) > 18 else "",
        "counterparty_iban": counterparty_iban,
    }

    if credit_mark == 'D':
        if not parts[2].strip() and len(parts) > 9:
            result["related_reference"] = parts[9].strip()
        elif not parts[1].strip() and len(parts) > 7:
            result["related_reference"] = parts[7].strip()
        elif len(parts) > 10:
            result["related_reference"] = parts[10].strip()

    return result
