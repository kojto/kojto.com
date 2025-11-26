import re
import logging

# Configure logger for this parser
logger = logging.getLogger(__name__)

def STSABGSF_parse_transaction_data(transaction_content):
    """
    Parse STSABGSF bank transaction data from MT940 format
    """
    logger.info("=== STSABGSF PARSER STARTED ===")
    logger.info(f"Input transaction_content length: {len(transaction_content)}")
    logger.info(f"Input transaction_content preview: {transaction_content[:200]}...")

    try:
        # Step 1: Clean and prepare data
        logger.info("Step 1: Cleaning and preparing transaction data")
        original_data = transaction_content
        data = transaction_content.replace('\n', '')
        logger.info(f"Data after newline removal - length: {len(data)}")
        logger.info(f"Cleaned data preview: {data[:200]}...")

        # Step 2: Define extraction helper function
        logger.info("Step 2: Setting up extraction helper function")

        def extract(marker, end_marker=None):
            logger.info(f"  Extracting with marker: '{marker}', end_marker: '{end_marker}'")
            try:
                if end_marker:
                    start = data.index(marker) + len(marker)
                    end = data.index(end_marker, start)
                    result = data[start:end].strip()
                    logger.info(f"    Found content between '{marker}' and '{end_marker}': '{result}'")
                    return result
                else:
                    parts = data.split(marker)
                    if len(parts) > 1:
                        result = parts[1].split('+')[0].strip()
                        logger.info(f"    Found content after '{marker}': '{result}'")
                        return result
                    else:
                        logger.warning(f"    No content found after marker '{marker}'")
                        return ""
            except IndexError as e:
                logger.error(f"    IndexError during extraction: {e}")
                return ""
            except Exception as e:
                logger.error(f"    Unexpected error during extraction: {e}")
                return ""

        # Step 3: Extract IBAN from tag 31 (counterparty IBAN)
        logger.info("Step 3: Extracting counterparty IBAN from tag 31")
        iban_pattern = r"31\+([A-Z]{2}\d{2}[A-Z0-9]{4,30})"
        logger.info(f"  Using IBAN pattern: {iban_pattern}")

        iban_match = re.search(iban_pattern, data)
        if iban_match:
            counterparty_iban = iban_match.group(1).strip()
            logger.info(f"  IBAN found: '{counterparty_iban}'")
        else:
            counterparty_iban = ""
            logger.warning("  No IBAN found in tag 31")

        # Step 4: Extract transaction code from tag 86 line starting with TC
        logger.info("Step 4: Extracting transaction code (TC-TSC format)")
        tc_pattern = r"TC(\d+)-TSC(\d+)"
        logger.info(f"  Using TC pattern: {tc_pattern}")

        tc_match = re.search(tc_pattern, data)
        if tc_match:
            tc_num = tc_match.group(1)
            tsc_num = tc_match.group(2)
            transaction_code = f"TC{tc_num}-TSC{tsc_num}"
            logger.info(f"  Transaction code found: '{transaction_code}' (TC{tc_num}, TSC{tsc_num})")
        else:
            transaction_code = ""
            logger.warning("  No transaction code found in TC-TSC format")

        # Step 5: Extract related reference from tag 86 line 28
        logger.info("Step 5: Extracting related reference from tag 86 line 28")
        ref_pattern = r"28\+([^+]+)"
        logger.info(f"  Using reference pattern: {ref_pattern}")

        ref_match = re.search(ref_pattern, data)
        if ref_match:
            related_reference = ref_match.group(1).strip()
            logger.info(f"  Related reference found: '{related_reference}'")
        else:
            related_reference = ""
            logger.warning("  No related reference found in line 28")

        # Step 6: Extract description from tag 86 line 20
        logger.info("Step 6: Extracting description from tag 86 line 20")
        desc_pattern = r"20\+([^+]+)"
        logger.info(f"  Using description pattern: {desc_pattern}")

        desc_match = re.search(desc_pattern, data)
        if desc_match:
            description = desc_match.group(1).strip()
            logger.info(f"  Description found: '{description}'")
        else:
            description = ""
            logger.warning("  No description found in line 20")

        # Step 7: Extract information from tag 86 line 22
        logger.info("Step 7: Extracting information from tag 86 line 22")
        info_pattern = r"22\+([^+]+)"
        logger.info(f"  Using information pattern: {info_pattern}")

        info_match = re.search(info_pattern, data)
        if info_match:
            information = info_match.group(1).strip()
            logger.info(f"  Information found: '{information}'")
        else:
            information = ""
            logger.warning("  No information found in line 22")

        # Step 8: Prepare final result
        logger.info("Step 8: Preparing final result")
        result = {
            "transaction_code": transaction_code,
            "related_reference": related_reference,
            "description": description,
            "information": information,
            "counterparty_iban": counterparty_iban,
        }

        logger.info("Final parsed result:")
        for key, value in result.items():
            logger.info(f"  {key}: '{value}'")

        logger.info("=== STSABGSF PARSER COMPLETED SUCCESSFULLY ===")
        return result

    except Exception as e:
        logger.error(f"=== STSABGSF PARSER FAILED WITH ERROR ===")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        logger.error(f"Original transaction content: {original_data}")
        logger.error(f"Cleaned data: {data if 'data' in locals() else 'Not available'}")
        logger.error("=== END ERROR LOG ===")

        # Return empty result on error
        return {
            "transaction_code": "",
            "related_reference": "",
            "description": "",
            "information": "",
            "counterparty_iban": "",
        }
