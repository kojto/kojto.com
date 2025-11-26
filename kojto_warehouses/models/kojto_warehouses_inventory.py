from odoo import api, models, fields, tools

class KojtoWarehousesInventory(models.Model):
    _name = "kojto.warehouses.inventory"
    _description = "Warehouse Inventory"
    _auto = False
    _rec_name = "accounting_identifier_id"
    _order = "accounting_identifier_id asc"

    name = fields.Char(string="Name", readonly=True)
    accounting_identifier_id = fields.Many2one("kojto.finance.accounting.identifiers", string="Accounting Identifier", readonly=True)
    unit_id = fields.Many2one("kojto.base.units", string="Unit", readonly=True)
    identifier = fields.Char(string="Identifier", readonly=True)
    identifier_type = fields.Selection(selection=[("material", "Material"), ("goods", "Goods"), ("asset", "Asset")], string="Identifier Type", readonly=True)
    active = fields.Boolean(string="Is Active", readonly=True)
    current_quantity = fields.Float(string="Current Quantity", readonly=True)
    current_value = fields.Float(string="Current Value", readonly=True)
    weighted_unit_price = fields.Float(string="Weighted Unit Price", readonly=True)
    batch_ids = fields.One2many("kojto.warehouses.batches", string="Batches", compute="_compute_batch_ids", readonly=True)

    @api.depends('accounting_identifier_id')
    def _compute_batch_ids(self):
        for record in self:
            if record.accounting_identifier_id:
                record.batch_ids = self.env['kojto.warehouses.batches'].search([
                    ('accounting_identifier_id', '=', record.accounting_identifier_id.id)
                ])
            else:
                record.batch_ids = False

    def init(self):
        try:
            # Create indexes for better performance
            self.env.cr.execute("""
                -- Drop existing indexes if they exist
                DROP INDEX IF EXISTS kojto_warehouses_items_material_id_idx;
                DROP INDEX IF EXISTS kojto_warehouses_items_profile_id_idx;

                -- Create correct indexes
                CREATE INDEX IF NOT EXISTS kojto_warehouses_items_batch_id_idx
                ON kojto_warehouses_items(batch_id);

                CREATE INDEX IF NOT EXISTS kojto_warehouses_transactions_item_id_idx
                ON kojto_warehouses_transactions(item_id);

                CREATE INDEX IF NOT EXISTS kojto_warehouses_batches_accounting_identifier_id_idx
                ON kojto_warehouses_batches(accounting_identifier_id);

                CREATE INDEX IF NOT EXISTS kojto_warehouses_batches_material_id_idx
                ON kojto_warehouses_batches(material_id);

                CREATE INDEX IF NOT EXISTS kojto_warehouses_batches_profile_id_idx
                ON kojto_warehouses_batches(profile_id);

                CREATE INDEX IF NOT EXISTS kojto_warehouses_batches_unit_price_idx
                ON kojto_warehouses_batches(unit_price);

                CREATE INDEX IF NOT EXISTS kojto_warehouses_transactions_to_from_store_idx
                ON kojto_warehouses_transactions(to_from_store);
            """)

            # Drop existing view if it exists
            tools.drop_view_if_exists(self.env.cr, self._table)

            # Create materialized view for item weights
            self.env.cr.execute("""
                CREATE MATERIALIZED VIEW IF NOT EXISTS kojto_warehouses_item_weights AS (
                    SELECT
                        i.id,
                        CASE
                            WHEN i.item_type = 'sheet' THEN
                                CASE
                                    WHEN i.length > 0 AND i.width > 0 AND b.thickness > 0 AND m.density > 0
                                    THEN (i.length * i.width * b.thickness / 1000000000.0) * m.density
                                    ELSE 0
                                END
                            WHEN i.item_type = 'bar' THEN
                                CASE
                                    WHEN i.length > 0 AND m.density > 0 AND p.cross_section > 0
                                    THEN (i.length * p.cross_section / 1000000000.0) * m.density
                                    ELSE 0
                                END
                            ELSE 0
                        END as computed_weight
                    FROM kojto_warehouses_items i
                    JOIN kojto_warehouses_batches b ON b.id = i.batch_id
                    LEFT JOIN kojto_base_material_grades m ON m.id = b.material_id
                    LEFT JOIN kojto_warehouses_profile_shapes p ON p.id = b.profile_id
                );

                CREATE UNIQUE INDEX IF NOT EXISTS kojto_warehouses_item_weights_id_idx
                ON kojto_warehouses_item_weights(id);

                CREATE INDEX IF NOT EXISTS kojto_warehouses_item_weights_computed_weight_idx
                ON kojto_warehouses_item_weights(computed_weight);
            """)

            # Create materialized view for transaction quantities
            self.env.cr.execute("""
                CREATE MATERIALIZED VIEW IF NOT EXISTS kojto_warehouses_transaction_quantities AS (
                    SELECT
                        t.id,
                        CASE
                            WHEN i.item_type IN ('sheet', 'bar') THEN iw.computed_weight
                            WHEN i.item_type = 'part' THEN t.transaction_quantity_override
                            ELSE 0
                        END as computed_quantity
                    FROM kojto_warehouses_transactions t
                    JOIN kojto_warehouses_items i ON i.id = t.item_id
                    LEFT JOIN kojto_warehouses_item_weights iw ON iw.id = i.id
                );

                CREATE UNIQUE INDEX IF NOT EXISTS kojto_warehouses_transaction_quantities_id_idx
                ON kojto_warehouses_transaction_quantities(id);

                CREATE INDEX IF NOT EXISTS kojto_warehouses_transaction_quantities_computed_quantity_idx
                ON kojto_warehouses_transaction_quantities(computed_quantity);
            """)

            # Create the main inventory view
            self.env.cr.execute("""
                CREATE OR REPLACE VIEW kojto_warehouses_inventory AS (
                    WITH inventory_quantities AS (
                        SELECT
                            b.accounting_identifier_id,
                            SUM(
                                CASE
                                    WHEN t.to_from_store = 'to_store' THEN tq.computed_quantity
                                    WHEN t.to_from_store = 'from_store' THEN -tq.computed_quantity
                                    ELSE 0
                                END
                            ) as total_quantity,
                            SUM(
                                CASE
                                    WHEN t.to_from_store = 'to_store' THEN tq.computed_quantity * (b.unit_price * COALESCE(b.unit_price_conversion_rate, 1.0))
                                    WHEN t.to_from_store = 'from_store' THEN -tq.computed_quantity * (b.unit_price * COALESCE(b.unit_price_conversion_rate, 1.0))
                                    ELSE 0
                                END
                            ) as total_value
                        FROM kojto_warehouses_batches b
                        JOIN kojto_warehouses_items i ON i.batch_id = b.id
                        JOIN kojto_warehouses_transactions t ON t.item_id = i.id
                        JOIN kojto_warehouses_transaction_quantities tq ON tq.id = t.id
                        WHERE b.accounting_identifier_id IS NOT NULL
                        GROUP BY b.accounting_identifier_id
                    )
                    SELECT
                        MIN(b.id) as id,
                        b.accounting_identifier_id,
                        ai.name as name,
                        ai.unit_id as unit_id,
                        ai.identifier as identifier,
                        ai.identifier_type as identifier_type,
                        ai.active as active,
                        COALESCE(iq.total_quantity, 0) as current_quantity,
                        COALESCE(iq.total_value, 0) as current_value,
                        CASE
                            WHEN COALESCE(iq.total_quantity, 0) != 0
                            THEN COALESCE(iq.total_value, 0) / NULLIF(iq.total_quantity, 0)
                            ELSE NULL
                        END as weighted_unit_price
                    FROM kojto_warehouses_batches b
                    JOIN kojto_finance_accounting_identifiers ai ON b.accounting_identifier_id = ai.id
                    LEFT JOIN inventory_quantities iq ON iq.accounting_identifier_id = b.accounting_identifier_id
                    WHERE b.accounting_identifier_id IS NOT NULL
                    GROUP BY
                        b.accounting_identifier_id,
                        ai.name,
                        ai.unit_id,
                        ai.identifier,
                        ai.identifier_type,
                        ai.active,
                        iq.total_quantity,
                        iq.total_value
                );
            """)

            # Create refresh function for materialized views
            self.env.cr.execute("""
                CREATE OR REPLACE FUNCTION refresh_warehouse_inventory_views()
                RETURNS trigger AS $$
                BEGIN
                    REFRESH MATERIALIZED VIEW CONCURRENTLY kojto_warehouses_item_weights;
                    REFRESH MATERIALIZED VIEW CONCURRENTLY kojto_warehouses_transaction_quantities;
                    RETURN NULL;
                END;
                $$ LANGUAGE plpgsql;

                DROP TRIGGER IF EXISTS refresh_warehouse_inventory_trigger ON kojto_warehouses_transactions;
                CREATE TRIGGER refresh_warehouse_inventory_trigger
                AFTER INSERT OR UPDATE OR DELETE ON kojto_warehouses_transactions
                FOR EACH STATEMENT EXECUTE FUNCTION refresh_warehouse_inventory_views();
            """)

        except Exception as e:
            raise

    def refresh_materialized_views(self):
        """Manually refresh the materialized views."""
        self.env.cr.execute("""
            REFRESH MATERIALIZED VIEW CONCURRENTLY kojto_warehouses_item_weights;
            REFRESH MATERIALIZED VIEW CONCURRENTLY kojto_warehouses_transaction_quantities;
        """)
