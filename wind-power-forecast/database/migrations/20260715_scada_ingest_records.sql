-- SCADA 样本审计表，供已有生产数据库进行显式升级。
-- 该脚本可重复执行，执行前仍应完成数据库备份。

BEGIN;

CREATE TABLE IF NOT EXISTS scada_ingest_records (
    id SERIAL PRIMARY KEY,
    connection_id INTEGER NOT NULL,
    farm_code VARCHAR(50) NOT NULL,
    ioa INTEGER,
    source_timestamp TIMESTAMP WITHOUT TIME ZONE,
    normalized_timestamp TIMESTAMP WITHOUT TIME ZONE,
    received_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    power_mw DOUBLE PRECISION,
    quality VARCHAR(20) NOT NULL DEFAULT 'unknown',
    outcome VARCHAR(20) NOT NULL,
    message TEXT,
    actual_power_id INTEGER
);

CREATE INDEX IF NOT EXISTS ix_scada_ingest_records_connection_id
    ON scada_ingest_records (connection_id);
CREATE INDEX IF NOT EXISTS ix_scada_ingest_records_farm_code
    ON scada_ingest_records (farm_code);
CREATE INDEX IF NOT EXISTS ix_scada_ingest_records_source_timestamp
    ON scada_ingest_records (source_timestamp);
CREATE INDEX IF NOT EXISTS ix_scada_ingest_records_normalized_timestamp
    ON scada_ingest_records (normalized_timestamp);
CREATE INDEX IF NOT EXISTS ix_scada_ingest_records_received_at
    ON scada_ingest_records (received_at);
CREATE INDEX IF NOT EXISTS ix_scada_ingest_records_quality
    ON scada_ingest_records (quality);
CREATE INDEX IF NOT EXISTS ix_scada_ingest_records_outcome
    ON scada_ingest_records (outcome);
CREATE INDEX IF NOT EXISTS ix_scada_ingest_records_actual_power_id
    ON scada_ingest_records (actual_power_id);

COMMIT;
