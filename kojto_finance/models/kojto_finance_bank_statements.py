from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
import base64
import re
from datetime import timedelta
import importlib
import os

class KojtoFinanceBankStatements(models.Model):
    _name = "kojto.finance.bank.statements"
    _description = "Bank Statements"
    _rec_name = "name"
    _order = "date_start desc, bank_account_id desc"

    name = fields.Char(string="Name", compute="compute_name", readonly=True, store=True)

    @api.depends("bank_account_id", "number")
    def compute_name(self):
        for record in self:
            record.name = f"{record.bank_account_id.IBAN} / {record.number}"

    uploader_id = fields.Integer(string="Uploader ID")
    status = fields.Integer(string="Status")
    comment = fields.Char(string="Comment")
    number = fields.Integer(string="Number")
    consecutive_number = fields.Char(string="Consecutive №", readonly=True)

    date_start = fields.Date(string="Start Date", index=True)
    date_end = fields.Date(string="End Date")

    start_balance = fields.Float(string="Start Balance", digits=(12, 2))
    end_balance = fields.Float(string="End Balance", digits=(12, 2))
    number_of_transactions = fields.Integer(string="Number of Transactions", compute="compute_number_of_transactions")
    transactions = fields.Text(string="Transactions", readonly=True)
    bank_account_id = fields.Many2one("kojto.base.bank.accounts", string="Bank Account ID")
    bank_bic_code = fields.Char(related="bank_account_id.BIC", string="BIC Code")
    currency = fields.Char(string="Currency")

    statement_file = fields.Binary(string="Statement File")
    statement_filename = fields.Char(string="Filename")
    statement_file_text = fields.Text(string="Statement File Text", copy=False, readonly=True)
    attachments = fields.Many2many("ir.attachment", string="Attachments", domain="[('res_model', '=', 'kojto.finance.bank.statements'), ('res_id', '=', id)]")

    tag_20 = fields.Char(string="Tag 20", readonly=True)
    tag_25 = fields.Char(string="Tag 25", readonly=True)
    tag_28 = fields.Char(string="Tag 28", readonly=True)
    tag_28c = fields.Char(string="Tag 28C", readonly=True)
    tag_60f = fields.Char(string="Tag 60F", readonly=True)
    tag_60m = fields.Char(string="Tag 60M", readonly=True)
    tag_62f = fields.Char(string="Tag 62F", readonly=True)

    @api.constrains("statement_file", "statement_filename")
    def check_file_extension(self):
        for record in self:
            if record.statement_file and record.statement_filename:
                filename = record.statement_filename.lower()
                if not filename.endswith(".txt"):
                    raise ValidationError("The file must have a .txt extension")

    @api.model
    def create(self, vals_list):
        if not isinstance(vals_list, list):
            vals_list = [vals_list]

        records = []
        for vals in vals_list:
            if "statement_file" in vals:
                decoded_bytes = base64.b64decode(vals["statement_file"])
                statement_file_text = None

                encodings_to_try = ['utf-8', 'windows-1251', 'cp1251', 'iso-8859-5', 'cp1252']

                for encoding in encodings_to_try:
                    try:
                        statement_file_text = decoded_bytes.decode(encoding)
                        print(f"Successfully decoded with {encoding}")
                        break
                    except UnicodeDecodeError:
                        continue

                if statement_file_text is None:
                    statement_file_text = decoded_bytes.decode('utf-8', errors='replace')
                    print("Warning: Used UTF-8 with character replacement")

                if statement_file_text is not None:
                    statement_file_text = statement_file_text.replace('\x00', '')
                    statement_file_text = re.sub(r"[\r]+ ", "", statement_file_text)
                    statement_file_text = re.sub(r"[\r]+", "", statement_file_text)
                    vals["statement_file_text"] = statement_file_text
                else:
                    vals["statement_file_text"] = None

            if "statement_file_text" in vals and vals["statement_file_text"]:
                existing_record = self.search([("statement_file_text", "=", vals["statement_file_text"])], limit=1)
                if existing_record:
                    continue

            record = super(KojtoFinanceBankStatements, self).create(vals)
            record.extract_statement_from_file()
            records.append(record)

        return records[0] if len(records) == 1 else self.browse([r.id for r in records])


    def extract_statement_from_file(self):
        if self.statement_file_text:
            self.statement_file = ""
            self.extract_mt940_tags()
        else:
            print(f"[BankStatements:{self.id}] No statement_file_text available for extraction")

    def extract_mt940_tags(self):
        pattern = re.compile(r":(\d{2}[A-Z]?):(.*?)(?=\n:|$)", re.DOTALL)
        matches = pattern.findall(self.statement_file_text)

        tag_values = {}
        for tag, content in matches:
            tag_field_name = f"tag_{tag.lower()}"
            if hasattr(self, tag_field_name):
                if tag_field_name not in tag_values:
                    tag_values[tag_field_name] = []
                tag_values[tag_field_name].append(content.strip())

        values_to_write = {}
        for field_name, values in tag_values.items():
            values_to_write[field_name] = "\n\n".join(values)

        self.write(values_to_write)
        self.extract_values_from_tags()

    def extract_values_from_tags(self):
        self.name = self.tag_20 or ""
        self.number = self.tag_28 or ""
        self.consecutive_number = ""

        if self.tag_28c:
            raw_28c = self.tag_28c.replace(":28C:", "").strip()
            tokens = [t for t in re.split(r"[\s]+", raw_28c) if t]

            last_token = tokens[-1] if tokens else ""
            parts = last_token.split("/") if last_token else [""]

            number_str = parts[0].strip() if parts else ""
            try:
                self.number = int(number_str) if re.fullmatch(r"\d+", number_str) else number_str

            except Exception:
                self.number = number_str
            self.consecutive_number = parts[1].strip() if len(parts) > 1 else ""

        self.date_start, self.start_balance = None, 0.0
        self.date_end, self.end_balance = None, 0.0

        for tag in [self.tag_60f, self.tag_62f]:
            if tag:
                match = re.match(r"C(\d{2})(\d{2})(\d{2})(\D{3})(\d+[,.]\d{2})", tag)
                if match:
                    year, month, day = int(f"20{match.group(1)}"), int(match.group(2)), int(match.group(3))
                    date = fields.Date.from_string(f"{year:04}-{month:02}-{day:02}")
                    balance = float(match.group(5).replace(",", "."))
                    if tag == self.tag_60f:
                        self.date_start, self.start_balance = date, balance
                    else:
                        self.date_end, self.end_balance = date, balance

        self.select_account_iban()
        self.validate_balance_continuity()
        self.compute_number_of_transactions()
        self.extract_and_create_transactions()

    def select_account_iban(self):
        if self.tag_25:
            contact = self.env["kojto.contacts"].search([("res_company_id", "=", self.env.company.id)], limit=1)
            if contact:
                financial_account = contact.bank_accounts.filtered(lambda a: a.IBAN == self.tag_25)
                if financial_account:
                    self.bank_account_id = financial_account.id
                    return
                match = re.search(r'(\d{11,})', self.tag_25)
                account_number = match.group(1) if match else None
                if account_number:
                    fuzzy_account = contact.bank_accounts.filtered(lambda a: a.IBAN and a.IBAN.endswith(account_number))
                    if fuzzy_account:
                        self.bank_account_id = fuzzy_account.id
                        return
                raise UserError(f"The IBAN {self.tag_25} is not registered in the contact's bank accounts. Please check if the account is correctly added.")
            else:
                raise UserError("No contact found for the current company. Please configure a contact with bank accounts.")

    def validate_balance_continuity(self, return_error_details=False):
        if not self.bank_account_id or not self.date_start:
            return None

        statement_date = self.date_start

        previous_transactions = self.env["kojto.finance.cashflow"].search([
            ("bank_account_id", "=", self.bank_account_id.id),
            ("date_value", "<", statement_date)
        ], limit=1)

        if not previous_transactions:
            return None

        previous_day = statement_date - timedelta(days=1)
        balance_record = self.env["kojto.finance.single.account.balance"].create({
            "bank_account_id": self.bank_account_id.id,
            "from_date": previous_day,
            "to_date": statement_date,
        })

        calculated_balance = balance_record.amount

        tolerance = 0.01
        balance_difference = abs(calculated_balance - self.start_balance)

        if balance_difference > tolerance:
            error_details = {
                'date': statement_date.strftime("%Y-%m-%d"),
                'calculated_balance': calculated_balance,
                'statement_balance': self.start_balance,
                'difference': balance_difference,
                'currency': self.currency or 'BGN',
                'statement_number': self.number
            }

            if return_error_details:
                return error_details
            else:
                return None

        return None

    @api.depends("statement_file_text")
    def compute_number_of_transactions(self):
        for record in self:
            if record.statement_file_text:
                pattern = re.compile(r":61:", re.IGNORECASE)
                count = len(pattern.findall(record.statement_file_text))
                record.number_of_transactions = count
            else:
                record.number_of_transactions = 0


    def _calculate_exchange_rates(self, transaction_date, source_currency_id):
        rate_to_bgn = 1.0
        rate_to_eur = 1.0

        if not source_currency_id:
            return rate_to_bgn, rate_to_eur

        bgn_currency = self.env['res.currency'].search([('name', '=', 'BGN')], limit=1)
        eur_currency = self.env['res.currency'].search([('name', '=', 'EUR')], limit=1)

        if not bgn_currency or not eur_currency:
            return rate_to_bgn, rate_to_eur

        exchange_model = self.env['kojto.base.currency.exchange']

        if source_currency_id.id != bgn_currency.id:
            exchange_rate = exchange_model.search([
                ('base_currency_id', '=', source_currency_id.id),
                ('target_currency_id', '=', bgn_currency.id),
                ('datetime', '<=', transaction_date),
                ('exchange_rate', '>', 0)
            ], order='datetime desc', limit=1)

            if exchange_rate and exchange_rate.exchange_rate > 0:
                rate_to_bgn = exchange_rate.exchange_rate
            else:
                exchange_rate = exchange_model.search([
                    ('base_currency_id', '=', bgn_currency.id),
                    ('target_currency_id', '=', source_currency_id.id),
                    ('datetime', '<=', transaction_date),
                    ('exchange_rate', '>', 0)
                ], order='datetime desc', limit=1)

                if exchange_rate and exchange_rate.exchange_rate > 0:
                    rate_to_bgn = 1.0 / exchange_rate.exchange_rate
                else:
                    exchange_rate = exchange_model.search([
                        '|',
                        ('base_currency_id', '=', source_currency_id.id),
                        ('target_currency_id', '=', source_currency_id.id),
                        '|',
                        ('base_currency_id', '=', bgn_currency.id),
                        ('target_currency_id', '=', bgn_currency.id),
                        ('exchange_rate', '>', 0)
                    ], order='datetime desc', limit=1)

                    if exchange_rate and exchange_rate.exchange_rate > 0:
                        if exchange_rate.base_currency_id.id == source_currency_id.id and exchange_rate.target_currency_id.id == bgn_currency.id:
                            rate_to_bgn = exchange_rate.exchange_rate
                        elif exchange_rate.base_currency_id.id == bgn_currency.id and exchange_rate.target_currency_id.id == source_currency_id.id:
                            rate_to_bgn = 1.0 / exchange_rate.exchange_rate
                        else:
                            rate_to_bgn = 1.0

        if source_currency_id.id != eur_currency.id:
            exchange_rate = exchange_model.search([
                ('base_currency_id', '=', source_currency_id.id),
                ('target_currency_id', '=', eur_currency.id),
                ('datetime', '<=', transaction_date),
                ('exchange_rate', '>', 0)
            ], order='datetime desc', limit=1)

            if exchange_rate and exchange_rate.exchange_rate > 0:
                rate_to_eur = exchange_rate.exchange_rate
            else:
                exchange_rate = exchange_model.search([
                    ('base_currency_id', '=', eur_currency.id),
                    ('target_currency_id', '=', source_currency_id.id),
                    ('datetime', '<=', transaction_date),
                    ('exchange_rate', '>', 0)
                ], order='datetime desc', limit=1)

                if exchange_rate and exchange_rate.exchange_rate > 0:
                    rate_to_eur = 1.0 / exchange_rate.exchange_rate
                else:
                    exchange_rate = exchange_model.search([
                        '|',
                        ('base_currency_id', '=', source_currency_id.id),
                        ('target_currency_id', '=', source_currency_id.id),
                        '|',
                        ('base_currency_id', '=', eur_currency.id),
                        ('target_currency_id', '=', eur_currency.id),
                        ('exchange_rate', '>', 0)
                    ], order='datetime desc', limit=1)

                    if exchange_rate and exchange_rate.exchange_rate > 0:
                        if exchange_rate.base_currency_id.id == source_currency_id.id and exchange_rate.target_currency_id.id == eur_currency.id:
                            rate_to_eur = exchange_rate.exchange_rate
                        elif exchange_rate.base_currency_id.id == eur_currency.id and exchange_rate.target_currency_id.id == source_currency_id.id:
                            rate_to_eur = 1.0 / exchange_rate.exchange_rate
                        else:
                            rate_to_eur = 1.0

        rate_to_bgn = max(rate_to_bgn, 0.0001)
        rate_to_eur = max(rate_to_eur, 0.0001)

        return rate_to_bgn, rate_to_eur

    def extract_and_create_transactions(self):
        cashflow_model = self.env["kojto.finance.cashflow"]
        bank_account_model = self.env["kojto.base.bank.accounts"]

        parser_dir = os.path.join(os.path.dirname(__file__), "bank_statement_parsers")
        available_parsers = []
        for fname in os.listdir(parser_dir):
            if fname.startswith("parser_for_") and fname.endswith(".py"):
                bic = fname[len("parser_for_"):-3]
                available_parsers.append(bic)

        parser_method_name = f"parser_for_{self.bank_bic_code}"
        try:
            parser_module = importlib.import_module(f".bank_statement_parsers.{parser_method_name}", package=__package__)
            parser = getattr(parser_module, f"{self.bank_bic_code}_parse_transaction_data")
        except (ModuleNotFoundError, AttributeError):
            print(f"Warning: No parser found for BIC {self.bank_bic_code} in statement ID {self.id}. Transactions will not be parsed. Available parsers: {available_parsers}")
            parser = lambda x: {}

        if not self.statement_file_text:
            return

        transactions = self.statement_file_text.split(":61")[1:]
        for idx, raw_part in enumerate(transactions):
            try:
                transaction_content = f":61{raw_part.split(':6', 1)[0].strip()}"
                transaction_content = re.sub(r"\n\s*|\s*\n", "", transaction_content).replace(":61", "\n:61").replace(":86", "\n:86")

                if cashflow_model.search([("transaction_data_raw", "=", transaction_content), ("statement_id", "=", self.id)], limit=1):
                    continue

                start_61 = transaction_content.find(":61:")
                start_86 = transaction_content.find(":86:")
                if start_61 == -1 and start_86 == -1:
                    continue

                text_86 = transaction_content[start_86 + 4:] if start_86 != -1 else ""
                parsed = parser(transaction_content)

                counterparty_iban = parsed.get("counterparty_iban", "")
                counterparty_bank_account_id = False
                if counterparty_iban:
                    counterparty_bank_account = bank_account_model.search([("IBAN", "=", counterparty_iban)], limit=1)
                    if counterparty_bank_account:
                        counterparty_bank_account_id = counterparty_bank_account.id
                    else:
                        bank_code = counterparty_iban[4:8] if len(counterparty_iban) >= 8 else ""
                        matching_bank_account = False
                        if bank_code:
                            matching_bank_account = bank_account_model.search([
                                ("IBAN", "!=", counterparty_iban),
                                ("IBAN", "like", f"%{bank_code}%")
                            ], limit=1)
                        new_bank_account_vals = {
                            "IBAN": counterparty_iban,
                            "name": f"Account {counterparty_iban}",
                        }
                        if matching_bank_account and matching_bank_account.BIC:
                            bank_model = self.env["kojto.base.banks"]
                            existing_bank = bank_model.search([("BIC", "=", matching_bank_account.BIC)], limit=1)
                            if existing_bank:
                                new_bank_account_vals["bank_id"] = existing_bank.id
                            else:
                                new_bank = bank_model.create({
                                    "name": f"Bank {bank_code}",
                                    "BIC": matching_bank_account.BIC,
                                })
                                new_bank_account_vals["bank_id"] = new_bank.id
                        new_bank_account = bank_account_model.create(new_bank_account_vals)
                        counterparty_bank_account_id = new_bank_account.id

                counterparty_id = False
                if counterparty_bank_account_id:
                    counterparty_bank_account = bank_account_model.browse(counterparty_bank_account_id)
                    if counterparty_bank_account.contact_id:
                        counterparty_id = counterparty_bank_account.contact_id.id

                cashflow_vals = {
                    "transaction_data_raw": transaction_content,
                    "statement_id": self.id,
                    "bank_account_id": self.bank_account_id.id if self.bank_account_id else False,
                    "related_reference": parsed.get("related_reference", "" if "+00" not in text_86 or "+10" not in text_86 else text_86[text_86.index("+00") + len("+00"):text_86.index("+10")].strip()),
                    "information": parsed.get("information") if parsed.get("information") else "No information provided",
                    "description": parsed.get("description") if parsed.get("description") else "No description provided",
                    "counterparty_bank_account_id": counterparty_bank_account_id,
                    "counterparty_id": counterparty_id,
                }

                if start_61 != -1:
                    transaction_data = transaction_content[start_61 + 4:].split(":")[0].strip()
                    year, month, day = f"20{transaction_data[:2]}", transaction_data[2:4], transaction_data[4:6]
                    transaction_date = fields.Date.from_string(f"{year}-{month}-{day}")
                    source_currency_id = self.bank_account_id.currency_id if self.bank_account_id else False
                    rate_to_bgn, rate_to_eur = self._calculate_exchange_rates(transaction_date, source_currency_id)
                    direction = "incoming" if transaction_data[10] == "C" else "outgoing"
                    amount_match = re.search(r"[A-Za-z](\d+[.,]?\d*)", transaction_data[10:])
                    amount_str = amount_match.group(1).replace(",", ".") if amount_match else "0"
                    try:
                        amount = abs(float(amount_str))
                    except Exception:
                        amount = 0.0
                    cashflow_vals.update({
                        "swift_transaction_code": parsed.get("transaction_code", transaction_data),
                        "date_value": transaction_date,
                        "date_entry": fields.Date.from_string(f"{year}-{transaction_data[6:8]}-{transaction_data[8:10]}"),
                        "transaction_direction": direction,
                        "amount": amount,
                        "exchange_rate_to_bgn": rate_to_bgn,
                        "exchange_rate_to_eur": rate_to_eur,
                    })
                    if amount <= 0.0:
                        continue

                search_domain = []
                for field, value in [
                    ("transaction_data_raw", cashflow_vals.get("transaction_data_raw")),
                    ("bank_account_id", cashflow_vals.get("bank_account_id")),
                    ("information", cashflow_vals.get("information")),
                    ("description", cashflow_vals.get("description")),
                    ("counterparty_bank_account_id", cashflow_vals.get("counterparty_bank_account_id")),
                    ("counterparty_id", cashflow_vals.get("counterparty_id")),
                ]:
                    if value and value != "" and value is not False:
                        search_domain.append((field, "=", value))

                existing_cashflow = cashflow_model.search(search_domain, limit=1)

                if not existing_cashflow:
                    cashflow_model.create(cashflow_vals)
                    continue

                if existing_cashflow:
                    existing_cashflow.write(cashflow_vals)
                    continue

            except Exception as e:
                continue

        return
