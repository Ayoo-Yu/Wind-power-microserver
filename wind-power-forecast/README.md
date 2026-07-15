# wind-power-forecast

## Local development

Local development uses Docker for KingBase and Redis. Flask, Celery and Vue run
directly from the working tree so code changes remain fast to test.

Run `start-local.bat` from Windows. The script will:

1. Start the isolated local KingBase and Redis services.
2. Wait for both services to become healthy.
3. Create the `windpower` database on the first run.
4. Seed local development data unless `LOCAL_SEED_ENABLED=false`.
5. Start Flask, Celery Worker, Celery Beat and Vue in local console windows.

Local infrastructure uses dedicated containers and volumes. It does not reuse the
production Compose project or the database files under `deploy`.

Infrastructure commands:

```bat
manage-local-infra.bat start
manage-local-infra.bat status
manage-local-infra.bat logs
manage-local-infra.bat tools
manage-local-infra.bat stop
```

`tools` starts the optional pgAdmin service at `http://localhost:5050`.

Use `stop-local.bat` to stop the locally running application processes while
keeping KingBase and Redis warm. Use `stop-local.bat all` to stop the local
application and infrastructure together.

The defaults can be overridden before startup:

```bat
set LOCAL_DB_PORT=15432
set LOCAL_DB_USER=system
set LOCAL_DB_PASSWORD=your-local-password
set LOCAL_REDIS_PORT=6379
set LOCAL_SEED_ENABLED=false
start-local.bat
```

## Project setup
```
npm install
```

### Compiles and hot-reloads for development
```
npm run serve
```

### Compiles and minifies for production
```
npm run build
```

### Lints and fixes files
```
npm run lint
```

### Customize configuration
See [Configuration Reference](https://cli.vuejs.org/config/).
