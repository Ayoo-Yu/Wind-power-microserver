return {
    postgres = {
        up = [[
            CREATE TABLE IF NOT EXISTS jwt_custom_secrets(
                id uuid PRIMARY KEY,
                created_at timestamp without time zone DEFAULT (CURRENT_TIMESTAMP(0) AT TIME ZONE 'UTC'::text) NOT NULL,
                consumer_id uuid NOT NULL,
                key text UNIQUE NOT NULL,
                algorithm text DEFAULT 'HS256' NOT NULL,
                rsa_public_key text,
                secret text NOT NULL,
                FOREIGN KEY (consumer_id) REFERENCES consumers(id) ON DELETE CASCADE
            );

            DO $$
            BEGIN
                IF (SELECT to_regclass('jwt_custom_secrets_key_idx')) IS NULL THEN
                    CREATE INDEX jwt_custom_secrets_key_idx ON jwt_custom_secrets(key);
                END IF;
                IF (SELECT to_regclass('jwt_custom_secrets_consumer_id_idx')) IS NULL THEN
                    CREATE INDEX jwt_custom_secrets_consumer_id_idx ON jwt_custom_secrets(consumer_id);
                END IF;
            END$$;
        ]],
        down = [[
            DROP TABLE jwt_custom_secrets;
        ]],
    },

    cassandra = {
        up = [[
            CREATE TABLE IF NOT EXISTS jwt_custom_secrets(
                id uuid PRIMARY KEY,
                created_at timestamp,
                consumer_id uuid,
                key text,
                algorithm text,
                rsa_public_key text,
                secret text,
                PRIMARY KEY (id)
            );

            CREATE INDEX IF NOT EXISTS ON jwt_custom_secrets(key);
            CREATE INDEX IF NOT EXISTS ON jwt_custom_secrets(consumer_id);
        ]],
        down = [[
            DROP TABLE jwt_custom_secrets;
        ]],
    },
}