import sys
import psycopg2
from tabulate import tabulate

# Usage: python check_invoice_allocation_debug.py <invoice_id>

DB_PARAMS = {
    'dbname': 'kojto',
    'user': 'your_db_user',
    'password': 'your_db_password',
    'host': 'localhost',
    'port': 5432,
}

def main(invoice_id):
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()

    print(f"\n=== Invoice {invoice_id} ===")
    cur.execute("SELECT * FROM kojto_finance_invoices WHERE id = %s", (invoice_id,))
    print(tabulate(cur.fetchall(), headers=[desc[0] for desc in cur.description]))

    print(f"\n=== Invoice Contents for {invoice_id} ===")
    cur.execute("SELECT * FROM kojto_finance_invoice_contents WHERE invoice_id = %s", (invoice_id,))
    print(tabulate(cur.fetchall(), headers=[desc[0] for desc in cur.description]))

    print(f"\n=== Allocations for {invoice_id} ===")
    cur.execute("SELECT * FROM kojto_finance_cashflow_allocation WHERE invoice_id = %s", (invoice_id,))
    allocations = cur.fetchall()
    print(tabulate(allocations, headers=[desc[0] for desc in cur.description]))

    print(f"\n=== Cashflow for Allocations ===")
    cur.execute("SELECT transaction_id FROM kojto_finance_cashflow_allocation WHERE invoice_id = %s", (invoice_id,))
    transaction_ids = [row[0] for row in cur.fetchall()]
    if transaction_ids:
        cur.execute(f"SELECT * FROM kojto_finance_cashflow WHERE id IN %s", (tuple(transaction_ids),))
        print(tabulate(cur.fetchall(), headers=[desc[0] for desc in cur.description]))
    else:
        print("No related cashflow transactions.")

    print(f"\n=== Allocation EUR Calculation ===")
    cur.execute('''
        SELECT
            alloc.id AS allocation_id,
            alloc.amount AS allocation_amount,
            cf.exchange_rate_to_eur AS cashflow_exchange_rate_to_eur,
            (alloc.amount * cf.exchange_rate_to_eur) AS allocation_amount_in_eur_by_rate
        FROM
            kojto_finance_cashflow_allocation alloc
        JOIN
            kojto_finance_cashflow cf ON cf.id = alloc.transaction_id
        WHERE
            alloc.invoice_id = %s
        ORDER BY alloc.id
    ''', (invoice_id,))
    print(tabulate(cur.fetchall(), headers=[desc[0] for desc in cur.description]))

    cur.close()
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python check_invoice_allocation_debug.py <invoice_id>")
        sys.exit(1)
    main(int(sys.argv[1]))
