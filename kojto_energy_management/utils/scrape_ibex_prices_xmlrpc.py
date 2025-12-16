#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#create cron job
# crontab -e
# 0 * * * * /bin/bash -c "source /opt/odoo18/venv/bin/activate && cd /opt/odoo18/custom/addons/kojto_energy_management/utils/ && python3 scrape_ibex_prices_xmlrpc.py --auto --db kojto"


"""
IBEX DAM 15-min Scraper → Odoo XML-RPC
* Starts from DAY AFTER last entry in Odoo
* fill() + Enter (NO CLICK)
* --test mode
* Auto + manual range
* UTC, BGN/EUR, duplicate skip
* Headless + stealth (no captcha on IBEX)
"""
import argparse
import asyncio
import configparser
import json
import logging
import os
import random
import re
import sys
import xmlrpc.client
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------
BASE_URL = "https://ibex.bg/sdac-pv-en/"
DATE_INPUT_SELECTOR = "input.flatpickr-input"
CSV_EXPORT_BUTTON = "#exportCSV"
DOWNLOAD_DIR = Path("/tmp/ibex_downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)
BGN_PER_EUR = 1.95583

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
log = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# HELPERS
# ----------------------------------------------------------------------
def cet_to_utc(cet_dt: datetime) -> datetime:
    return cet_dt - timedelta(hours=1)


def parse_csv(csv_content: str, delivery_date: datetime) -> List[Dict]:
    lines = csv_content.strip().splitlines()
    records = []
    pattern = re.compile(r"QH \d+;(\d{2}:\d{2}) - (\d{2}:\d{2});([\d,]+\.?\d*);([\d,]+\.?\d*)")
    for line in lines:
        m = pattern.search(line)
        if not m:
            continue
        start_str, end_str, eur_str, vol_str = m.groups()
        try:
            start_cet = delivery_date.replace(
                hour=int(start_str[:2]), minute=int(start_str[3:]), second=0, microsecond=0
            )
            end_cet = delivery_date.replace(
                hour=int(end_str[:2]), minute=int(end_str[3:]), second=0, microsecond=0
            )
            if end_cet <= start_cet:
                end_cet += timedelta(days=1)
        except Exception as e:
            log.warning(f"Time parse error: {line} → {e}")
            continue
        try:
            price_eur = float(eur_str.replace(",", "."))
            volume = float(vol_str.replace(",", "."))
        except Exception:
            continue
        price_bgn = round(price_eur * BGN_PER_EUR, 2)
        records.append(
            {
                "period_start_cet": start_cet.strftime("%Y-%m-%d %H:%M:%S"),
                "period_end_cet": end_cet.strftime("%Y-%m-%d %H:%M:%S"),
                "price_bgn_per_mwh": price_bgn,
                "price_eur_per_mwh": price_eur,
                "volume_mwh": volume,
                "exchange": "IBEX-DAM",
                "period_start_utc": cet_to_utc(start_cet).strftime("%Y-%m-%d %H:%M:%S"),
                "period_end_utc": cet_to_utc(end_cet).strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
    return records


# ----------------------------------------------------------------------
# BROWSER (headless + stealth)
# ----------------------------------------------------------------------
async def launch_browser():
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-blink-features=AutomationControlled",
        ],
    )
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1920, "height": 1080},
        java_script_enabled=True,
        locale="en-GB",
        timezone_id="Europe/Sofia",
    )
    # ---- stealth ----
    await context.add_init_script(
        """
        Object.defineProperty(navigator, 'webdriver', { get: () => false });
        window.chrome = window.chrome || {};
        """
    )
    return playwright, browser, context


# ----------------------------------------------------------------------
# DATE INPUT
# ----------------------------------------------------------------------
async def set_date_fill(page, target_date: datetime) -> bool:
    target_str = target_date.strftime("%d.%m.%Y")
    log.info(f"Setting date → {target_str}")

    try:
        await page.wait_for_selector(DATE_INPUT_SELECTOR, timeout=15000)
    except PlaywrightTimeout:
        await page.screenshot(path="/tmp/ibex_no_input.png")
        log.error("Date input not found")
        return False

    await page.fill(DATE_INPUT_SELECTOR, "")
    await page.fill(DATE_INPUT_SELECTOR, target_str)
    await page.press(DATE_INPUT_SELECTOR, "Enter")
    await page.wait_for_timeout(3000)

    actual = await page.input_value(DATE_INPUT_SELECTOR)
    if actual != target_str:
        log.warning(f"Date shows {actual}, expected {target_str}")
    else:
        log.info("Date set correctly")
    return True


# ----------------------------------------------------------------------
# SCRAPE ONE DAY
# ----------------------------------------------------------------------
async def scrape_one_day(page, target_date: datetime) -> Optional[List[Dict]]:
    if not await set_date_fill(page, target_date):
        return None

    # table
    try:
        await page.wait_for_selector("td:has-text('QH')", timeout=30000)
        log.info("Table loaded")
    except PlaywrightTimeout:
        await page.screenshot(path=f"/tmp/ibex_no_table_{target_date:%Y-%m-%d}.png")
        log.error("Table not loaded")
        return None

    # export button
    try:
        await page.wait_for_selector(CSV_EXPORT_BUTTON, timeout=15000, state="visible")
        log.info("Export button ready")
    except PlaywrightTimeout:
        log.error("Export button missing")
        return None

    # download
    async with page.expect_download(timeout=30000) as dl_info:
        await page.click(CSV_EXPORT_BUTTON)
    download = await dl_info.value
    csv_path = DOWNLOAD_DIR / f"ibex_{target_date:%Y-%m-%d}.csv"
    await download.save_as(csv_path)
    log.info(f"CSV → {csv_path}")

    csv_content = csv_path.read_text(encoding="utf-8")
    records = parse_csv(csv_content, target_date)
    if not records:
        log.warning("CSV parsed 0 rows")
        return None
    log.info(f"Parsed {len(records)} rows")
    return records


# ----------------------------------------------------------------------
# ODOO CONNECTOR
# ----------------------------------------------------------------------
class OdooConnector:
    def __init__(self, url: str, db: str, username: str, password: str):
        self.url = url
        self.db = db
        self.username = username
        self.password = password
        self.uid = None
        self.models = None
        self.model = "kojto.energy.management.prices"

    def connect(self) -> bool:
        try:
            common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common", allow_none=True)
            version = common.version()
            log.info(f"Odoo version: {version.get('server_version')}")
            self.uid = common.authenticate(self.db, self.username, self.password, {})
            if not self.uid:
                log.error("Auth failed")
                return False
            self.models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object", allow_none=True)
            log.info(f"Connected UID {self.uid}")
            return True
        except Exception as e:
            log.error(f"Connection error: {e}")
            return False

    def test_model_exists(self) -> bool:
        try:
            fields = self.models.execute_kw(
                self.db,
                self.uid,
                self.password,
                self.model,
                "fields_get",
                [],
                {"attributes": ["string", "type"]},
            )
            log.info(f"Model exists – {len(fields)} fields")
            return True
        except Exception as e:
            log.error(f"Model missing: {e}")
            return False

    def test_create_single(self) -> bool:
        rec = {
            "period_start_cet": "2099-12-31 23:45:00",
            "period_end_cet": "2100-01-01 00:00:00",
            "period_start_utc": "2099-12-31 22:45:00",
            "period_end_utc": "2099-12-31 23:00:00",
            "price_bgn_per_mwh": 999.99,
            "price_eur_per_mwh": 511.00,
            "volume_mwh": 1234.5,
            "exchange": "IBEX-DAM",
        }
        try:
            nid = self.models.execute_kw(self.db, self.uid, self.password, self.model, "create", [rec])
            log.info(f"Test record ID {nid}")
            self.models.execute_kw(self.db, self.uid, self.password, self.model, "unlink", [[nid]])
            return True
        except Exception as e:
            log.error(f"Test insert failed: {e}")
            return False

    def latest_date(self) -> Optional[datetime.date]:
        try:
            ids = self.models.execute_kw(
                self.db,
                self.uid,
                self.password,
                self.model,
                "search",
                [[["exchange", "=", "IBEX-DAM"]]],
                {"order": "period_start_cet desc", "limit": 1},
            )
            if not ids:
                return None
            rec = self.models.execute_kw(
                self.db,
                self.uid,
                self.password,
                self.model,
                "read",
                [ids],
                {"fields": ["period_start_cet"]},
            )[0]
            return datetime.strptime(rec["period_start_cet"], "%Y-%m-%d %H:%M:%S").date()
        except Exception as e:
            log.warning(f"Latest-date query error: {e}")
            return None

    def create_records(self, records: List[Dict]) -> int:
        created = 0
        for r in records:
            try:
                exists = self.models.execute_kw(
                    self.db,
                    self.uid,
                    self.password,
                    self.model,
                    "search_count",
                    [[["period_start_cet", "=", r["period_start_cet"]], ["exchange", "=", "IBEX-DAM"]]],
                )
                if exists:
                    continue
                self.models.execute_kw(
                    self.db,
                    self.uid,
                    self.password,
                    self.model,
                    "create",
                    [
                        {
                            "period_start_cet": r["period_start_cet"],
                            "period_end_cet": r["period_end_cet"],
                            "period_start_utc": r["period_start_utc"],
                            "period_end_utc": r["period_end_utc"],
                            "price_bgn_per_mwh": r["price_bgn_per_mwh"],
                            "price_eur_per_mwh": r["price_eur_per_mwh"],
                            "volume_mwh": r["volume_mwh"],
                            "exchange": r["exchange"],
                        }
                    ],
                )
                created += 1
            except Exception as e:
                log.error(f"Insert error {r['period_start_cet']}: {e}")
        return created


# ----------------------------------------------------------------------
# TEST MODE
# ----------------------------------------------------------------------
async def run_test_mode(odoo: OdooConnector):
    log.info("=== TEST MODE ===")
    if not odoo.connect():
        sys.exit(1)
    if not odoo.test_model_exists():
        sys.exit(1)
    if not odoo.test_create_single():
        sys.exit(1)
    log.info("ALL TESTS OK")
    sys.exit(0)


# ----------------------------------------------------------------------
# MAIN SCRAPER
# ----------------------------------------------------------------------
async def run_scrape_and_insert(start: str, end: str, odoo: OdooConnector):
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    current = start_dt.date()
    end_date = end_dt.date()
    tomorrow = datetime.now().date() + timedelta(days=1)

    total_created = 0
    days_processed = 0

    playwright, browser, context = await launch_browser()
    page = await context.new_page()

    try:
        log.info("Opening IBEX…")
        await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_load_state("networkidle", timeout=60000)
        log.info("Page ready")

        while current <= end_date:
            label = current.strftime("%Y-%m-%d")
            if current == datetime.now().date():
                label += " (TODAY)"
            elif current == tomorrow:
                label += " (TOMORROW)"
            log.info(f"{'='*20} DAY {days_processed+1}: {label} {'='*20}")

            if current > tomorrow:
                log.info("Future day – skip")
                current += timedelta(days=1)
                continue

            records = await scrape_one_day(page, datetime.combine(current, datetime.min.time()))
            if not records:
                log.warning("No data for this day")
                current += timedelta(days=1)
                continue

            if len(records) != 96:
                log.warning(f"Rows ≠ 96 → {len(records)}")

            created = odoo.create_records(records)
            skipped = len(records) - created
            log.info(f"Inserted {created}, skipped {skipped}")
            total_created += created
            days_processed += 1
            current += timedelta(days=1)

            await asyncio.sleep(random.uniform(2, 4))

    except Exception as e:
        await page.screenshot(path="/tmp/ibex_error.png")
        log.error(f"Unexpected error: {e}")
        import traceback
        log.error(traceback.format_exc())
    finally:
        # Properly close all resources before event loop closes
        try:
            await page.close()
        except:
            pass
        try:
            await context.close()
        except:
            pass
        try:
            await browser.close()
        except:
            pass
        try:
            await playwright.stop()
        except:
            pass
        # Give a moment for cleanup to complete
        await asyncio.sleep(0.1)

    log.info(f"DONE – {days_processed} days, {total_created} records")
    print(json.dumps({"records": []}, indent=2), flush=True)


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------
def parse_args():
    p = argparse.ArgumentParser(description="IBEX → Odoo scraper")
    p.add_argument("--start-date", help="YYYY-MM-DD")
    p.add_argument("--end-date", help="YYYY-MM-DD")
    p.add_argument("--auto", action="store_true", help="last+1 → tomorrow")
    p.add_argument("--test", action="store_true", help="Odoo test")
    p.add_argument("--odoo-url", default="http://localhost:8069")
    p.add_argument("--db", required=True)
    p.add_argument("--user")
    p.add_argument("--password")
    p.add_argument("--api-key")
    return p.parse_args()


def read_config():
    cfg_path = "/etc/odoo18.conf"
    if not os.path.exists(cfg_path):
        return None, None
    cfg = configparser.ConfigParser()
    cfg.read(cfg_path)
    if "options" not in cfg:
        return None, None
    return cfg["options"].get("xml_rpc_user"), cfg["options"].get("xml_rpc_password")


def main():
    args = parse_args()
    username = args.user
    password = args.password or args.api_key
    if not username or not password:
        u, p = read_config()
        username = username or u
        password = password or p
    if not username or not password:
        log.error("Odoo credentials missing")
        sys.exit(1)

    odoo = OdooConnector(args.odoo_url, args.db, username, password)

    if args.test:
        asyncio.run(run_test_mode(odoo))
        return

    if args.auto:
        if not odoo.connect():
            sys.exit(1)
        latest = odoo.latest_date()
        today = datetime.now().date()
        start = (latest + timedelta(days=1)) if latest else today
        end = today + timedelta(days=1)
        log.info(f"AUTO mode: {start} → {end}")
    else:
        if not args.start_date or not args.end_date:
            log.error("Need --start-date + --end-date or --auto")
            sys.exit(1)
        start = datetime.strptime(args.start_date, "%Y-%m-%d").date()
        end = datetime.strptime(args.end_date, "%Y-%m-%d").date()

    if not odoo.connect():
        sys.exit(1)

    # Use asyncio.run with proper cleanup to avoid event loop warnings
    try:
        asyncio.run(
            run_scrape_and_insert(
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                odoo=odoo,
            )
        )
    except KeyboardInterrupt:
        log.info("Interrupted by user")
        sys.exit(1)
    except Exception as e:
        log.error(f"Fatal error: {e}")
        import traceback
        log.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
