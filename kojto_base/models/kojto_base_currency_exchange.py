from odoo import models, fields, api
from odoo.exceptions import ValidationError
import xml.etree.ElementTree as ET
import requests
from datetime import datetime

class KojtoBaseCurrencyExchange(models.Model):
    _name = "kojto.base.currency.exchange"
    _description = "Kojto Base Currency Exchange"
    _order = "datetime desc, target_currency_id desc"

    base_currency_id = fields.Many2one("res.currency", string="Base Currency", default=lambda self: self.env.ref("base.EUR"))
    target_currency_id = fields.Many2one("res.currency", string="Target Currency")
    exchange_rate = fields.Float(string="Exchange Rate", digits=(12, 5), help="Exchange rate with 5 decimal places precision")
    datetime = fields.Datetime(string="Date and Time")
    url = fields.Char("Originates from URL")

    @api.model
    def process_ecb_data(self, url, base_currency):
        """Process ECB exchange rate data."""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except requests.RequestException:
            raise ValidationError(f"Failed to download file from {url}.")

        try:
            root = ET.fromstring(response.content)
            namespace = {"gesmes": "http://www.gesmes.org/xml/2002-08-01", "": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}

            for cube_date in root.findall(".//Cube[@time]", namespace):
                date_str = cube_date.attrib["time"]
                # Convert date string to datetime (ECB uses YYYY-MM-DD)
                date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d 00:00:00")

                for cube_rate in cube_date.findall("Cube[@currency]", namespace):
                    currency_code = cube_rate.attrib["currency"]

                    # Skip BGN currency
                    if currency_code == "BGN":
                        continue

                    try:
                        raw_rate = cube_rate.attrib["rate"]
                        rate = float(raw_rate)
                        # Round to 5 decimal places to ensure precision
                        rate = round(rate, 5)
                    except ValueError:
                        continue  # Skip invalid rates

                    target_currency = self.env["res.currency"].search([("name", "=", currency_code), ("active", "=", True)], limit=1)
                    if not target_currency:
                        continue  # Skip inactive or missing currencies

                    # Additional check to ensure BGN is never processed
                    if target_currency.name == "BGN":
                        continue

                    # Check for existing record to avoid duplicates
                    existing = self.search([
                        ("base_currency_id", "=", base_currency.id),
                        ("target_currency_id", "=", target_currency.id),
                        ("datetime", "=", date)
                    ], limit=1)
                    if existing:
                        continue  # Skip duplicates

                    # Ensure rate is stored with 5 decimal places
                    self.create({
                        "base_currency_id": base_currency.id,
                        "target_currency_id": target_currency.id,
                        "exchange_rate": rate,
                        "datetime": date,
                        "url": url
                    })
        except ET.ParseError:
            raise ValidationError(f"Failed to parse XML from {url}.")

    def import_ecb_daily_rates(self):
        """Import ECB daily exchange rates, auto-activating EUR if inactive."""
        url = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
        base_currency = self.env["res.currency"].search([("name", "=", "EUR")], limit=1)
        if not base_currency:
            raise ValidationError("Base currency EUR not found in res_currency.")
        if not base_currency.active:
            base_currency.write({"active": True})
            company = self.env.company
            if company.currency_id != base_currency:
                company.write({"currency_id": base_currency.id})
        self.process_ecb_data(url, base_currency)

    def import_ecb_90d_rates(self):
        """Import ECB 90-day exchange rates, auto-activating EUR if inactive."""
        url = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml"
        base_currency = self.env["res.currency"].search([("name", "=", "EUR")], limit=1)
        if not base_currency:
            raise ValidationError("Base currency EUR not found in res_currency.")
        if not base_currency.active:
            base_currency.write({"active": True})
            company = self.env.company
            if company.currency_id != base_currency:
                company.write({"currency_id": base_currency.id})
        self.process_ecb_data(url, base_currency)

    def import_ecb_historical_rates(self):
        """Import ECB historical exchange rates, auto-activating EUR if inactive."""
        url = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml"
        base_currency = self.env["res.currency"].search([("name", "=", "EUR")], limit=1)
        if not base_currency:
            raise ValidationError("Base currency EUR not found in res_currency.")
        if not base_currency.active:
            base_currency.write({"active": True})
            company = self.env.company
            if company.currency_id != base_currency:
                company.write({"currency_id": base_currency.id})
        self.process_ecb_data(url, base_currency)
