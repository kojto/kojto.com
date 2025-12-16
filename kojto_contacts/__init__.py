from . import models

def post_init_hook(env):
    """
    Post-init hook to ensure contact with id=1 exists.
    Creates "Our Company" contact if it doesn't exist.
    """
    # Check if contact with id=1 exists using SQL
    env.cr.execute("SELECT id FROM kojto_contacts WHERE id = 1")
    existing = env.cr.fetchone()

    if not existing:
        # Get admin user ID (usually 2, but use 1 as fallback)
        env.cr.execute("SELECT id FROM res_users WHERE id = 2 OR id = 1 ORDER BY id LIMIT 1")
        user_result = env.cr.fetchone()
        user_id = user_result[0] if user_result else 1

        # Get the default language_id (defaults to English)
        env.cr.execute("""
            SELECT id FROM res_lang WHERE code = 'en_US'
            ORDER BY id LIMIT 1
        """)
        lang_result = env.cr.fetchone()
        language_id = lang_result[0] if lang_result else None

        # Insert the contact with id=1 directly using SQL
        if language_id:
            env.cr.execute("""
                INSERT INTO kojto_contacts (
                    id, contact_type, name, client_number, active, language_id,
                    create_uid, create_date, write_uid, write_date
                ) VALUES (
                    1, 'company', 'Our Company', 0, true, %s,
                    %s, NOW(), %s, NOW()
                )
            """, (language_id, user_id, user_id))
        else:
            env.cr.execute("""
                INSERT INTO kojto_contacts (
                    id, contact_type, name, client_number, active,
                    create_uid, create_date, write_uid, write_date
                ) VALUES (
                    1, 'company', 'Our Company', 0, true,
                    %s, NOW(), %s, NOW()
                )
            """, (user_id, user_id))

        # Also create the corresponding name record in kojto.base.names
        # Check if the table exists first (might not exist in some cases)
        env.cr.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'kojto_base_names'
            )
        """)
        names_table_exists = env.cr.fetchone()[0]

        if names_table_exists:
            env.cr.execute("""
                INSERT INTO kojto_base_names (
                    name, contact_id, active,
                    create_uid, create_date, write_uid, write_date
                ) VALUES (
                    'Our Company', 1, true,
                    %s, NOW(), %s, NOW()
                )
            """, (user_id, user_id))

        # Ensure the sequence is at least at 2 (if id=1 was inserted)
        env.cr.execute("""
            SELECT setval(
                pg_get_serial_sequence('kojto_contacts', 'id'),
                GREATEST(1, (SELECT MAX(id) FROM kojto_contacts))
            )
        """)

        env.cr.commit()

