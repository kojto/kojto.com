# -*- coding: utf-8 -*-

from . import models
from . import wizards
from . import utils


def post_init_hook(env):
    env.cr.execute(
        """
        CREATE UNIQUE INDEX uniq_number_for_outgoing_invoices
        ON kojto_finance_invoices (consecutive_number, company_id)
        WHERE document_in_out_type = 'outgoing' and invoice_type != 'proforma';
    """
    )
    env.cr.execute(
        """
        CREATE UNIQUE INDEX uniq_number_for_outgoing_proforms
        ON kojto_finance_invoices (consecutive_number, company_id)
        WHERE document_in_out_type = 'outgoing' and invoice_type = 'proforma';
    """
    )
    env.cr.execute(
        """
        CREATE UNIQUE INDEX uniq_invoice_name
        ON kojto_finance_invoices (name)
    """
    )
    # env.cr.execute(
    #     """
    #     CREATE UNIQUE INDEX uniq_number_for_incoming_invoices
    #     ON kojto_finance_invoices (consecutive_number, document_in_out_type, counterparty_id)
    #     WHERE document_in_out_type = 'incoming';
    # """
    # )
