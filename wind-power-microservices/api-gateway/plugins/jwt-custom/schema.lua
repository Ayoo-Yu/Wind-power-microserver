return {
    name = "jwt-custom",
    fields = {
        {
            config = {
                type = "record",
                fields = {
                    {
                        secret = {
                            type = "string",
                            required = true,
                            encrypted = true,
                        },
                    },
                    {
                        required_claims = {
                            type = "array",
                            elements = {
                                type = "string",
                            },
                            default = {},
                        },
                    },
                    {
                        header_name = {
                            type = "string",
                            default = "Authorization",
                        },
                    },
                    {
                        bearer_prefix = {
                            type = "string",
                            default = "Bearer",
                            one_of = { "Bearer", "JWT" },
                        },
                    },
                    {
                        validate_expiry = {
                            type = "boolean",
                            default = true,
                        },
                    },
                    {
                        validate_signature = {
                            type = "boolean",
                            default = true,
                        },
                    },
                },
            },
        },
    },
}