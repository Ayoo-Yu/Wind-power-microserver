local typedefs = require "kong.db.schema.typedefs"

return {
    jwt_custom_secrets = {
        name = "jwt_custom_secrets",
        primary_key = { "id" },
        endpoint_key = "key",
        cache_key = { "key" },
        admin_api_name = "jwt-custom-secrets",
        admin_api_nested_name = "jwt-custom-secret",
        fields = {
            {
                id = typedefs.uuid,
            },
            {
                created_at = typedefs.auto_timestamp_s,
            },
            {
                consumer = {
                    type = "foreign",
                    reference = "consumers",
                    required = true,
                    on_delete = "cascade",
                },
            },
            {
                key = {
                    type = "string",
                    required = true,
                    unique = true,
                    auto = true,
                },
            },
            {
                algorithm = {
                    type = "string",
                    default = "HS256",
                    one_of = { "HS256", "HS384", "HS512", "RS256", "RS384", "RS512", "ES256", "ES384", "ES512" },
                },
            },
            {
                rsa_public_key = {
                    type = "string",
                },
            },
            {
                secret = {
                    type = "string",
                    required = true,
                    encrypted = true,
                },
            },
        },
    },
}