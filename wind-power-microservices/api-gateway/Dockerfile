# Multi-stage build for Kong API Gateway
FROM kong:3.5.0-alpine as builder

# Install additional plugins and dependencies
USER root
RUN apk add --no-cache \
    git \
    gcc \
    musl-dev \
    lua5.1-dev \
    && git clone https://github.com/Kong/kong-plugin-jwt-crafter.git /tmp/jwt-crafter \
    && cd /tmp/jwt-crafter \
    && luarocks make

# Production stage
FROM kong:3.5.0-alpine

# Set environment variables
ENV KONG_DATABASE=postgres
ENV KONG_PG_HOST=kong-db
ENV KONG_PG_PORT=5432
ENV KONG_PG_USER=kong
ENV KONG_PG_PASSWORD=kong
ENV KONG_CASSANDRA_CONTACT_POINTS=kong-db
ENV KONG_ADMIN_ACCESS_LOG=/dev/stdout
ENV KONG_ADMIN_ERROR_LOG=/dev/stderr
ENV KONG_ADMIN_LISTEN=0.0.0.0:8001
ENV KONG_PROXY_ACCESS_LOG=/dev/stdout
ENV KONG_PROXY_ERROR_LOG=/dev/stderr
ENV KONG_PROXY_LISTEN=0.0.0.0:8000, 0.0.0.0:8443 ssl
ENV KONG_NGINX_DAEMON=off
ENV KONG_DECLARATIVE_CONFIG=/kong/declarative/kong.yml

# Install custom plugins
USER root
RUN apk add --no-cache \
    curl \
    jq \
    && luarocks install kong-plugin-jwt-crafter

# Copy custom plugins and configurations
COPY plugins/ /usr/local/share/lua/5.1/kong/plugins/
COPY config/ /kong/config/
COPY declarative/ /kong/declarative/

# Create Kong user and set permissions
RUN addgroup -g 1000 kong \
    && adduser -u 1000 -G kong -s /bin/sh -D kong \
    && chown -R kong:kong /kong /usr/local/share/lua/5.1/kong/plugins/

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD kong health || exit 1

USER kong

# Expose ports
EXPOSE 8000 8443 8001 8444

# Start Kong
CMD ["kong", "docker-start"]