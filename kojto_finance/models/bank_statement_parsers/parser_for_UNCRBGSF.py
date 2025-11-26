import re

def UNCRBGSF_parse_transaction_data(transaction_content):
    data = transaction_content.replace('\n', '')

    def extract(marker, end_marker=None):
        try:
            if end_marker:
                start = data.index(marker) + len(marker)
                end = data.index(end_marker, start)
                return data[start:end].strip()
            return data.split(marker)[1].split('+')[0].strip()
        except IndexError:
            return ""

    iban_match = re.search(r"[A-Z]{2}\d{2}[A-Z0-9]{4,30}", data)
    counterparty_iban = iban_match.group(0).strip() if iban_match else ""

    return {
        "transaction_code": "",
        "related_reference": extract('+00', '+10'),
        "description": extract('+21'),
        "information": extract('+22'),
        "counterparty_iban": counterparty_iban,
    }
