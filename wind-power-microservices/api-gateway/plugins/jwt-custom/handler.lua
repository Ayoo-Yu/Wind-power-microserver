local jwt = require "resty.jwt"
local cjson = require "cjson"
local utils = require "kong.tools.utils"

local JwtCustomHandler = {
    VERSION = "1.0.0",
    PRIORITY = 1005,
}

-- JWT Custom Plugin Handler
function JwtCustomHandler:access(conf)
    -- Get the Authorization header
    local auth_header = kong.request.get_header("Authorization")

    if not auth_header then
        return kong.response.exit(401, {
            error = "Unauthorized",
            message = "Missing Authorization header"
        })
    end

    -- Extract the token from Bearer format
    local token = auth_header:match("^Bearer%s+(.+)$")
    if not token then
        return kong.response.exit(401, {
            error = "Unauthorized",
            message = "Invalid Authorization header format. Expected 'Bearer <token>'"
        })
    end

    -- Verify the JWT token
    local jwt_obj = jwt:verify(conf.secret, token)

    if not jwt_obj.verified then
        return kong.response.exit(401, {
            error = "Unauthorized",
            message = "Invalid JWT token: " .. (jwt_obj.reason or "unknown error")
        })
    end

    -- Check token expiration
    local exp = jwt_obj.payload.exp
    if exp and exp < ngx.time() then
        return kong.response.exit(401, {
            error = "Unauthorized",
            message = "JWT token has expired"
        })
    end

    -- Check required claims
    if conf.required_claims and #conf.required_claims > 0 then
        for _, claim in ipairs(conf.required_claims) do
            if not jwt_obj.payload[claim] then
                return kong.response.exit(401, {
                    error = "Unauthorized",
                    message = "Missing required claim: " .. claim
                })
            end
        end
    end

    -- Set consumer information in headers for downstream services
    local consumer_id = jwt_obj.payload.sub or jwt_obj.payload.consumer_id
    local consumer_username = jwt_obj.payload.username or jwt_obj.payload.preferred_username

    if consumer_id then
        kong.service.request.set_header("X-Consumer-ID", consumer_id)
    end

    if consumer_username then
        kong.service.request.set_header("X-Consumer-Username", consumer_username)
    end

    -- Set tenant information if available
    local tenant_id = jwt_obj.payload.tenant_id
    if tenant_id then
        kong.service.request.set_header("X-Tenant-ID", tenant_id)
    end

    -- Set user roles if available
    local roles = jwt_obj.payload.roles or jwt_obj.payload.scope
    if roles then
        if type(roles) == "table" then
            roles = table.concat(roles, ",")
        end
        kong.service.request.set_header("X-User-Roles", roles)
    end

    -- Store JWT payload in Kong context for other plugins
    kong.ctx.shared.jwt_payload = jwt_obj.payload
    kong.ctx.shared.consumer_id = consumer_id
    kong.ctx.shared.consumer_username = consumer_username

    -- Log successful authentication
    kong.log.info("JWT authentication successful for consumer: ", consumer_id or "unknown")
end

-- Function to validate plugin configuration
function JwtCustomHandler:access_validate(conf)
    if not conf.secret or conf.secret == "" then
        return false, "JWT secret is required"
    end

    if conf.required_claims and type(conf.required_claims) ~= "table" then
        return false, "required_claims must be an array"
    end

    return true
end

return JwtCustomHandler