def migrate(cr, version):
    """
    Pre-migration script to remove the old WPS-document bundle relationship
    """
    # Drop the foreign key constraint first
    cr.execute("""
        ALTER TABLE kojto_en1090_doc_bundle_wps_rel
        DROP CONSTRAINT IF EXISTS kojto_en1090_doc_bundle_wps_rel_wps_id_fkey;
    """)

    # Drop the foreign key constraint for bundle_id
    cr.execute("""
        ALTER TABLE kojto_en1090_doc_bundle_wps_rel
        DROP CONSTRAINT IF EXISTS kojto_en1090_doc_bundle_wps_rel_bundle_id_fkey;
    """)

    # Drop the table entirely
    cr.execute("""
        DROP TABLE IF EXISTS kojto_en1090_doc_bundle_wps_rel;
    """)

    # Also remove any related field definitions from ir_model_fields
    cr.execute("""
        DELETE FROM ir_model_fields
        WHERE name = 'wps_record_ids'
        AND model_id IN (
            SELECT id FROM ir_model
            WHERE model = 'kojto.en1090.document.bundles'
        );
    """)

    cr.execute("""
        DELETE FROM ir_model_fields
        WHERE name = 'document_bundle_id'
        AND model_id IN (
            SELECT id FROM ir_model
            WHERE model = 'kojto.en1090.wps'
        );
    """)
