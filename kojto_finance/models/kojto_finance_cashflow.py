from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from collections import defaultdict
from ..utils.cashflow_auto_allocate import auto_allocate_for_transaction

class KojtoFinanceCashflow(models.Model):
    _name = "kojto.finance.cashflow"
    _description = "Kojto Finance Cashflow"
    _rec_name = "name"
    _order = "id desc"
    _sql_constraints = [('amount_positive', 'CHECK (amount > 0)', 'Amount must be greater than zero.')]

    auto_allocated = fields.Boolean(string="Auto Allocated", default=False)
    name = fields.Char(string="Name", compute="_compute_name", store=False)
    transaction_data_raw = fields.Text(string="Base Data", readonly=True)
    statement_id = fields.Many2one("kojto.finance.bank.statements", string="Statement", readonly=True)
    bank_account_id = fields.Many2one("kojto.base.bank.accounts", string="Our Bank Account", required=True, domain=lambda self: self.domain_bank_account_id())
    transaction_allocation_ids = fields.One2many("kojto.finance.cashflow.allocation", "transaction_id", string="Transaction Allocation")

    date_value = fields.Date(string="Date", required=True, index=True)
    date_entry = fields.Date(string="Entry Date")

    transaction_direction = fields.Selection([("incoming", "Incoming"), ("outgoing", "Outgoing")], string="Transaction Direction", required=True, index=True)
    currency_id = fields.Many2one("res.currency", string="Currency", related="bank_account_id.currency_id", readonly=True)

    exchange_rate_to_bgn = fields.Float(string="Rate to BGN", default=1.0, required=True, digits=(9, 5))
    exchange_rate_to_eur = fields.Float(string="Rate to EUR", default=1.0, required=True, digits=(9, 5))
    swift_transaction_code = fields.Char(string="SWIFT")
    transaction_code = fields.Char(string="Code")

    accountant_id = fields.Char(string="Accountant User ID")
    accounting_archive_number = fields.Char(string="Accounting Archive Number")
    accounting_op_date = fields.Date(string="Accounting Operation Date")
    date_export = fields.Date(string="Accounting Export Date", index=True)
    accounting_is_exported = fields.Boolean(string="Accounting Is Exported", compute="_compute_accounting_is_exported")

    counterparty_id = fields.Many2one("kojto.contacts", string="Counterparty")
    counterparty_bank_account_id = fields.Many2one("kojto.base.bank.accounts", string="Counterparty Bank Account")

    counterparty_bank_account_domain = fields.Char(string="Counterparty Bank Account Domain", compute="_compute_bank_account_domain", store=False)
    counterparty_bank_id = fields.Many2one("kojto.base.banks", string="Counterparty Bank")
    counterparty_bank_account_owner_id = fields.Many2one("kojto.contacts", related="counterparty_bank_account_id.contact_id", string="Bank Account Owner")

    accounting_template_domain = fields.Char(string="Accounting Template Domain", compute="_compute_accounting_template_domain", store=False)
    accounting_template_id = fields.Many2one("kojto.finance.accounting.templates", string="Default Accounting Template", required=False)

    information = fields.Char(string="Additional information")
    related_reference = fields.Char(string="Related Reference")
    description = fields.Char(string="Description", required=True)

    creator_id = fields.Many2one("res.users", string="Creator")

    unallocated_amount = fields.Float(string="Unallocated", compute="_compute_unallocated_amount", digits=(12, 2), store=True)
    amount = fields.Float(string="Amount", digits=(12, 2))

    requires_identifier_id = fields.Boolean(related="accounting_template_id.requires_identifier_id", compute="_compute_requires_identifier_id")
    active = fields.Boolean(string="Active", default=True)

    allocation_summary = fields.Html(string="Allocation Summary", compute="_compute_allocation_summary", store=True)

    @api.constrains('amount')
    def _check_amount_positive(self):
        for record in self:
            if record.amount <= 0:
                raise ValidationError("Transaction amount must be positive!")

    @api.constrains("exchange_rate_to_bgn", "exchange_rate_to_eur")
    def _check_exchange_rates(self):
        for record in self:
            if record.exchange_rate_to_bgn <= 0 or record.exchange_rate_to_eur <= 0:
                raise ValidationError("Exchange rate to BGN and to EUR must be greater than zero!")

    @api.depends("amount", "transaction_allocation_ids", "transaction_allocation_ids.amount")
    def _compute_unallocated_amount(self):
        for record in self:
            total_allocated = sum(record.transaction_allocation_ids.mapped("amount"))
            record.unallocated_amount = record.amount - total_allocated

    def compute_unallocated_amount(self):
        self._compute_unallocated_amount()
        return {}

    def recompute_allocation_summary(self):
        """Recompute allocation summary for selected cashflow transactions"""
        if not self:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Warning',
                    'message': 'Please select one or more cashflow transactions to recompute their summaries.',
                    'type': 'warning',
                    'sticky': False,
                }
            }

        # Process in batches to handle large selections (Odoo has default limits)
        batch_size = 1000
        processed_count = 0
        record_ids = self.ids

        # Process in batches
        for i in range(0, len(record_ids), batch_size):
            batch_ids = record_ids[i:i+batch_size]
            batch_records = self.env['kojto.finance.cashflow'].browse(batch_ids)
            # Invalidate cache to force recomputation
            batch_records.invalidate_recordset(['allocation_summary'])
            # Recompute the allocation summary
            batch_records._compute_allocation_summary()
            processed_count += len(batch_records)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': f'Recomputed allocation summary for {processed_count} cashflow transaction(s).',
                'type': 'success',
                'sticky': False,
            }
        }

    @api.depends("transaction_allocation_ids", "transaction_allocation_ids.amount", "transaction_allocation_ids.subcode_id", "transaction_allocation_ids.invoice_id", "transaction_allocation_ids.accounting_template_id", "transaction_allocation_ids.accounting_ref_number", "transaction_allocation_ids.subtype_id", "transaction_allocation_ids.cash_flow_only", "transaction_allocation_ids.cash_flow_only_inherited")
    def _compute_allocation_summary(self):
        for record in self:
            if not record.transaction_allocation_ids:
                record.allocation_summary = ""
                continue

            summary_lines = []
            for allocation in record.transaction_allocation_ids:
                line_parts = []

                line_parts.append(f"{allocation.amount:,.2f}")

                if record.currency_id:
                    line_parts.append(record.currency_id.name)

                if allocation.invoice_id:
                    line_parts.append(f"({allocation.invoice_id.consecutive_number or allocation.invoice_id.name})")

                if allocation.subcode_id:
                    line_parts.append(f"→ {allocation.subcode_id.name}")

                if allocation.accounting_template_id:
                    line_parts.append(f"[{allocation.accounting_template_id.name}]")

                if allocation.accounting_ref_number:
                    line_parts.append(f"#{allocation.accounting_ref_number}")

                if allocation.subtype_id:
                    line_parts.append(f"<{allocation.subtype_id.name}>")

                # Add CFO for cash flow only allocations (either direct or inherited from subcode)
                # Check both the direct field and the subcode's cash_flow_only field
                is_cfo = allocation.cash_flow_only or (allocation.subcode_id and allocation.subcode_id.cash_flow_only)
                if is_cfo:
                    line_parts.append('<span style="color: blue; font-weight: bold;">CFO</span>')

                summary_lines.append(" ".join(line_parts))

            record.allocation_summary = f'<div style="font-size: 80%;">{("<br/>".join(summary_lines))}</div>'

    @api.depends("transaction_direction")
    def _compute_name(self):
        for record in self:
            if record.transaction_direction:
                record.name = f"{record.bank_account_id.bank_id.name if record.bank_account_id.bank_id else ''} - {record.bank_account_id.IBAN if record.bank_account_id else ''}"
            else:
                record.name = f"New Cashflow"

    @api.depends("transaction_direction")
    def _compute_accounting_template_domain(self):
        for record in self:
            record.accounting_template_domain = []
            if not record.transaction_direction:
                continue

            ptype = "cashflow_in" if record.transaction_direction == "incoming" else "cashflow_out"
            record.accounting_template_domain = [("template_type_id.primary_type", "=", ptype)]

    def _compute_accounting_is_exported(self):
        for record in self:
            record.accounting_is_exported = record.date_export is not False
        return {}


    @api.model
    def create(self, vals):
        def _set_exchange_rates(val):
            bank_account_id = val.get('bank_account_id')
            if bank_account_id:
                bank_account = self.env['kojto.base.bank.accounts'].browse(bank_account_id)
                currency_id = bank_account.currency_id.id if bank_account.currency_id else None

                if currency_id == 125:
                    val['exchange_rate_to_bgn'] = 1.95583
                    val['exchange_rate_to_eur'] = 1
                elif currency_id == 26:
                    val['exchange_rate_to_bgn'] = 1
                    val['exchange_rate_to_eur'] = 0.51129

        if isinstance(vals, list):
            for val in vals:
                _set_exchange_rates(val)
            cashflow = super(KojtoFinanceCashflow, self).create(vals)
        else:
            _set_exchange_rates(vals)
            cashflow = super(KojtoFinanceCashflow, self).create(vals)

        cashflow.invalidate_recordset(['unallocated_amount'])
        cashflow._compute_unallocated_amount()
        cashflow.auto_allocate_cashflow_transaction_to_invoice()
        return cashflow

    def write(self, vals):
        bank_account_id = vals.get('bank_account_id')
        if bank_account_id:
            bank_account = self.env['kojto.base.bank.accounts'].browse(bank_account_id)
            currency_id = bank_account.currency_id.id if bank_account.currency_id else None

            if currency_id == 125:
                vals['exchange_rate_to_bgn'] = 1.95583
                vals['exchange_rate_to_eur'] = 1
            elif currency_id == 26:
                vals['exchange_rate_to_bgn'] = 1
                vals['exchange_rate_to_eur'] = 0.51129
        result = super(KojtoFinanceCashflow, self).write(vals)
        return result

    def domain_bank_account_id(self):
        contact = self.env["kojto.contacts"].search([("res_company_id", "=", self.env.company.id)], limit=1)
        if contact and contact.bank_accounts:
            return [("id", "in", contact.bank_accounts.ids)]
        return []

    @api.depends("accounting_template_id")
    def _compute_requires_identifier_id(self):
        for record in self:
            record.requires_identifier_id = record.accounting_template_id.requires_identifier_id if record.accounting_template_id else False

    @api.onchange("accounting_template_id")
    def _onchange_accounting_template_id(self):
        if self.accounting_template_id:
            for allocation in self.transaction_allocation_ids:
                allocation.accounting_template_id = self.accounting_template_id

    @api.onchange("transaction_id")
    def select_default_accounting_template(self):
        self.accounting_template_id = self.transaction_id.accounting_template_id

    @api.onchange("invoice_id")
    def set_amount_and_subcode_id(self):
        if not self.invoice_id:
            return

        contents = self.invoice_id.content
        if not contents:
            return

        if self.subcode_id:
            return

        allocated_subcodes = self.transaction_id.transaction_allocation_ids.mapped("subcode_id")

        amount_by_subcode = defaultdict(lambda: {"amount": 0, "subcode_id": None, "currency_id": None, "exchange_rate_to_bgn": 1.0})
        for line in contents:
            amount_by_subcode[line.subcode_id.id]["amount"] += line.total_price
            amount_by_subcode[line.subcode_id.id]["subcode_id"] = line.subcode_id
            amount_by_subcode[line.subcode_id.id]["currency_id"] = line.currency_id
            amount_by_subcode[line.subcode_id.id]["exchange_rate_to_bgn"] = line.invoice_id.exchange_rate_to_bgn

        amount_by_subcode = sorted(amount_by_subcode.items(), key=lambda x: x[1]["subcode_id"].id, reverse=True)

        filtered_amount_by_subcode = [x for x in amount_by_subcode if x[1]["subcode_id"] not in allocated_subcodes]
        if not filtered_amount_by_subcode:
            return

        self.amount = filtered_amount_by_subcode[0][1]["amount"]
        self.subcode_id = filtered_amount_by_subcode[0][1]["subcode_id"]

    def open_form(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Cashflow",
            "res_model": "kojto.finance.cashflow",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def export_to_ajur(self):
        self.ensure_one()
        exporter = self.env["kojto.finance.cashflow.exportselectiontoajur"].with_context(selected_transactions=[self.id])
        return exporter.action_export_to_ajur()

    def open_o2m_record(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Open Allocation Record",
            "res_model": "kojto.finance.cashflow.allocation",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    @api.depends("counterparty_bank_account_id")
    def _compute_counterparty_id(self):
        for record in self:
            if record.counterparty_bank_account_id and record.counterparty_bank_account_id.contact_id:
                record.counterparty_id = record.counterparty_bank_account_id.contact_id

    @api.onchange("currency_id", "date_value")
    def _compute_exchange_rate_to_acc_currency(self):
        if self.currency_id and self.currency_id.id == 125:
            self.exchange_rate_to_bgn = 1.95583
            self.exchange_rate_to_eur = 1
        elif self.currency_id and self.currency_id.id == 26:
            self.exchange_rate_to_bgn = 1
            self.exchange_rate_to_eur = 0.51129
        else:
            self.exchange_rate_to_bgn = self.get_exchange_rate(self.currency_id, self.env.ref("base.BGN"), self.date_value)
            self.exchange_rate_to_eur = self.get_exchange_rate(self.currency_id, self.env.ref("base.EUR"), self.date_value)

    def get_exchange_rate(self, from_currency, to_currency, date):
        if from_currency == to_currency:
            return 1.0

        if not date or not from_currency or not to_currency:
            return 0.0

        exchange_rate = self.env["kojto.base.currency.exchange"].search(
            [
                ("base_currency_id", "=", from_currency.id),
                ("target_currency_id", "=", to_currency.id),
                ("datetime", ">=", date),
                ("datetime", "<=", date),
            ],
            order="datetime DESC",
            limit=1,
        )

        if not exchange_rate:
            if from_currency.name == 'BGN' and to_currency.name == 'EUR':
                return 0.51129
            elif from_currency.name == 'EUR' and to_currency.name == 'BGN':
                return 1.95583
            elif from_currency.name == 'BGN' and to_currency.name == 'BGN':
                return 1.0
            elif from_currency.name == 'EUR' and to_currency.name == 'EUR':
                return 1.0
            return 0.0

        return exchange_rate.exchange_rate

    @api.onchange("counterparty_bank_account_id")
    def _onchange_counterparty_bank_account_id(self):
        if self.counterparty_bank_account_id and self.counterparty_bank_account_id.contact_id:
            self.counterparty_id = self.counterparty_bank_account_id.contact_id
        else:
            self.counterparty_id = False

    def open_counterparty_bank_account_id(self):
        self.ensure_one()
        if not self.counterparty_bank_account_id:
            raise UserError("No counterparty bank account is associated with this transaction.")

        return {
            "name": "Please select counterparty for this IBAN",
            "type": "ir.actions.act_window",
            "res_model": "kojto.base.bank.accounts",
            "res_id": self.counterparty_bank_account_id.id,
            "view_mode": "form",
            "view_id": self.env.ref("kojto_finance.view_kojto_base_bank_accounts_contact_only").id,
            "target": "new",
        }

    def unlink(self):
        invoice_ids = []
        for record in self:
            if record.statement_id:
                raise UserError(_("Cannot delete cashflow record that is linked to a bank statement. Please unlink it from the statement first."))
            if record.transaction_allocation_ids:
                inv_ids = record.transaction_allocation_ids.mapped('invoice_id.id')
                invoice_ids.extend([inv_id for inv_id in inv_ids if inv_id])

        result = super(KojtoFinanceCashflow, self).unlink()

        if invoice_ids:
            pass

        return result

    def auto_allocate(self):
        for record in self:
            auto_allocate_for_transaction(record)
        return True

    def auto_allocate_cashflow_transaction_to_invoice(self):
        import re
        Invoice = self.env['kojto.finance.invoices']
        Allocation = self.env['kojto.finance.cashflow.allocation']

        def find_invoice(cashflow):
            amount = cashflow.amount
            base_domain = [('paid', '=', False)]

            if not cashflow.transaction_data_raw:
                return False

            for num in re.findall(r'\b\d{4,}\b', str(cashflow.transaction_data_raw)):
                invoices = Invoice.search(
                    base_domain + [('consecutive_number', '=', num)],
                    order='date_issue desc'
                )
                for inv in invoices:
                    if abs(inv.total_price - amount) <= 0.01:
                        return inv
            return False

        for c in self.filtered(lambda x: x.amount > 0):
            invoice = find_invoice(c)
            if not invoice:
                continue

            existing_allocation = Allocation.search([
                ('transaction_id', '=', c.id),
                ('invoice_id', '=', invoice.id)
            ], limit=1)
            if existing_allocation:
                continue

            vals = {}
            if not c.counterparty_id:
                vals['counterparty_id'] = invoice.counterparty_id.id
            if invoice.counterparty_bank_account_id and not c.counterparty_bank_account_id:
                vals['counterparty_bank_account_id'] = invoice.counterparty_bank_account_id.id
            if vals:
                c.write(vals)

            subcode = invoice.subcode_id or c.transaction_allocation_ids[:1].subcode_id
            if not subcode:
                continue

            alloc_amount = min(c.unallocated_amount, c.amount)

            Allocation.create({
                'transaction_id': c.id,
                'invoice_id': invoice.id,
                'subcode_id': subcode.id,
                'amount': alloc_amount,
                'amount_base': alloc_amount,
                'auto_allocated': True,
                'description': f"Auto-allocated to invoice {invoice.consecutive_number}",
                'accounting_template_id': invoice.invoice_acc_template_id.id or False,
                'subtype_id': invoice.invoice_acc_subtype_id.id or False,
            })
