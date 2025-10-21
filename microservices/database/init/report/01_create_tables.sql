-- Report Database Schema
-- Database: windpower_report

-- Report tasks table
CREATE TABLE IF NOT EXISTS report_tasks (
    id SERIAL PRIMARY KEY,
    task_name VARCHAR(100) NOT NULL,
    farm_id INTEGER NOT NULL,
    report_type VARCHAR(50) NOT NULL, -- auto_report, manual_report, scheduled_report
    report_template VARCHAR(50),
    status VARCHAR(20) DEFAULT 'pending', -- pending, running, completed, failed, cancelled
    priority INTEGER DEFAULT 1, -- 1-5, 1 being highest
    scheduled_time TIMESTAMP,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    duration INTERVAL,
    data_period_start TIMESTAMP,
    data_period_end TIMESTAMP,
    report_data JSONB,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Report data table
CREATE TABLE IF NOT EXISTS report_data (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES report_tasks(id) ON DELETE CASCADE,
    farm_id INTEGER NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    report_type VARCHAR(50) NOT NULL,
    data_content JSONB NOT NULL,
    file_path VARCHAR(255),
    file_name VARCHAR(255),
    file_size BIGINT,
    file_hash VARCHAR(64),
    is_uploaded BOOLEAN DEFAULT false,
    upload_status VARCHAR(20), -- pending, success, failed
    upload_response TEXT,
    upload_timestamp TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Report templates table
CREATE TABLE IF NOT EXISTS report_templates (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    template_type VARCHAR(50) NOT NULL, -- auto_report, forecast_report, daily_report, monthly_report
    template_content JSONB NOT NULL,
    is_active BOOLEAN DEFAULT true,
    is_default BOOLEAN DEFAULT false,
    version VARCHAR(20) NOT NULL,
    data_fields JSONB, -- array of required data fields
    format_rules JSONB,
    validation_rules JSONB,
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Schedule configurations table
CREATE TABLE IF NOT EXISTS schedules (
    id SERIAL PRIMARY KEY,
    schedule_name VARCHAR(100) NOT NULL,
    farm_id INTEGER NOT NULL,
    report_type VARCHAR(50) NOT NULL,
    template_id INTEGER REFERENCES report_templates(id) ON DELETE SET NULL,
    cron_expression VARCHAR(100) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    priority INTEGER DEFAULT 1,
    max_retries INTEGER DEFAULT 3,
    retry_interval INTERVAL DEFAULT '5 minutes',
    timeout INTERVAL DEFAULT '30 minutes',
    notification_config JSONB,
    data_retention_days INTEGER DEFAULT 30,
    last_run TIMESTAMP,
    next_run TIMESTAMP,
    run_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Statistics data table
CREATE TABLE IF NOT EXISTS statistics (
    id SERIAL PRIMARY KEY,
    farm_id INTEGER NOT NULL,
    statistic_type VARCHAR(50) NOT NULL, -- daily, monthly, yearly, custom
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    data_content JSONB NOT NULL,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    generated_by VARCHAR(50),
    metadata JSONB
);

-- Report logs table
CREATE TABLE IF NOT EXISTS report_logs (
    id SERIAL PRIMARY KEY,
    task_id INTEGER REFERENCES report_tasks(id) ON DELETE SET NULL,
    farm_id INTEGER NOT NULL,
    log_level VARCHAR(10) NOT NULL, -- INFO, WARN, ERROR, DEBUG
    message TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    component VARCHAR(50), -- generator, uploader, validator
    details JSONB
);

-- Upload history table
CREATE TABLE IF NOT EXISTS upload_history (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES report_tasks(id) ON DELETE CASCADE,
    farm_id INTEGER NOT NULL,
    upload_time TIMESTAMP NOT NULL,
    target_system VARCHAR(100) NOT NULL,
    target_url VARCHAR(255),
    upload_status VARCHAR(20) NOT NULL, -- success, failed, timeout
    response_code INTEGER,
    response_message TEXT,
    response_time INTERVAL,
    retry_count INTEGER DEFAULT 0,
    file_size BIGINT,
    file_hash VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Notification settings table
CREATE TABLE IF NOT EXISTS notification_settings (
    id SERIAL PRIMARY KEY,
    farm_id INTEGER NOT NULL,
    notification_type VARCHAR(50) NOT NULL, -- email, sms, webhook
    recipient VARCHAR(255) NOT NULL,
    template_name VARCHAR(100),
    is_active BOOLEAN DEFAULT true,
    conditions JSONB, -- conditions for triggering notifications
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Report validation rules table
CREATE TABLE IF NOT EXISTS validation_rules (
    id SERIAL PRIMARY KEY,
    rule_name VARCHAR(100) NOT NULL,
    rule_type VARCHAR(50) NOT NULL, -- required_field, data_range, format_check, business_rule
    field_name VARCHAR(100),
    rule_config JSONB NOT NULL,
    error_message TEXT,
    severity VARCHAR(20) DEFAULT 'error', -- warning, error, critical
    is_active BOOLEAN DEFAULT true,
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Failed reports table
CREATE TABLE IF NOT EXISTS failed_reports (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES report_tasks(id) ON DELETE CASCADE,
    farm_id INTEGER NOT NULL,
    failure_reason TEXT NOT NULL,
    failure_details JSONB,
    retry_attempted BOOLEAN DEFAULT false,
    retry_time TIMESTAMP,
    retry_result VARCHAR(50), -- success, failed
    error_code VARCHAR(50),
    error_stack TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Data retention policies table
CREATE TABLE IF NOT EXISTS retention_policies (
    id SERIAL PRIMARY KEY,
    policy_name VARCHAR(100) NOT NULL,
    table_name VARCHAR(50) NOT NULL,
    retention_period INTERVAL NOT NULL,
    retention_action VARCHAR(20) DEFAULT 'delete', -- delete, archive, move
    archive_location VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    last_executed TIMESTAMP,
    next_execution TIMESTAMP,
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- System performance metrics table
CREATE TABLE IF NOT EXISTS performance_metrics (
    id SERIAL PRIMARY KEY,
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(15, 6) NOT NULL,
    metric_unit VARCHAR(20),
    farm_id INTEGER,
    collection_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

-- Create indexes
CREATE INDEX idx_report_tasks_farm_id ON report_tasks(farm_id);
CREATE INDEX idx_report_tasks_status ON report_tasks(status);
CREATE INDEX idx_report_tasks_scheduled_time ON report_tasks(scheduled_time);
CREATE INDEX idx_report_tasks_report_type ON report_tasks(report_type);
CREATE INDEX idx_report_data_task_id ON report_data(task_id);
CREATE INDEX idx_report_data_farm_id ON report_data(farm_id);
CREATE INDEX idx_report_data_timestamp ON report_data(timestamp);
CREATE INDEX idx_report_data_uploaded ON report_data(is_uploaded);
CREATE INDEX idx_report_templates_type ON report_templates(template_type);
CREATE INDEX idx_report_templates_active ON report_templates(is_active);
CREATE INDEX idx_schedules_farm_id ON schedules(farm_id);
CREATE INDEX idx_schedules_active ON schedules(is_active);
CREATE INDEX idx_schedules_next_run ON schedules(next_run);
CREATE INDEX idx_statistics_farm_id ON statistics(farm_id);
CREATE INDEX idx_statistics_type ON statistics(statistic_type);
CREATE INDEX idx_statistics_period ON statistics(period_start, period_end);
CREATE INDEX idx_report_logs_task_id ON report_logs(task_id);
CREATE INDEX idx_report_logs_farm_id ON report_logs(farm_id);
CREATE INDEX idx_report_logs_level ON report_logs(log_level);
CREATE INDEX idx_report_logs_timestamp ON report_logs(timestamp);
CREATE INDEX idx_upload_history_task_id ON upload_history(task_id);
CREATE INDEX idx_upload_history_farm_id ON upload_history(farm_id);
CREATE INDEX idx_upload_history_status ON upload_history(upload_status);
CREATE INDEX idx_upload_history_time ON upload_history(upload_time);
CREATE INDEX idx_notification_settings_farm_id ON notification_settings(farm_id);
CREATE INDEX idx_notification_settings_type ON notification_settings(notification_type);
CREATE INDEX idx_notification_settings_active ON notification_settings(is_active);
CREATE INDEX idx_validation_rules_type ON validation_rules(rule_type);
CREATE INDEX idx_validation_rules_active ON validation_rules(is_active);
CREATE INDEX idx_failed_reports_task_id ON failed_reports(task_id);
CREATE INDEX idx_failed_reports_farm_id ON failed_reports(farm_id);
CREATE INDEX idx_failed_reports_retry ON failed_reports(retry_attempted);
CREATE INDEX idx_retention_policies_table ON retention_policies(table_name);
CREATE INDEX idx_retention_policies_active ON retention_policies(is_active);
CREATE INDEX idx_performance_metrics_name ON performance_metrics(metric_name);
CREATE INDEX idx_performance_metrics_time ON performance_metrics(collection_time);
CREATE INDEX idx_performance_metrics_farm_id ON performance_metrics(farm_id);

-- Insert default report templates
INSERT INTO report_templates (name, description, template_type, template_content, is_default, version, created_by) VALUES
('Auto Report Template', 'Standard template for automatic power reporting', 'auto_report',
 '{"format": "json", "fields": ["time", "farm_code", "available_power", "theoretical_power", "capacity_factor"], "required": ["time", "farm_code", "available_power"]}',
 true, '1.0.0', 'system'),
('Forecast Report Template', 'Template for forecast power reporting', 'forecast_report',
 '{"format": "json", "fields": ["forecast_time", "farm_code", "forecast_power", "confidence_level"], "required": ["forecast_time", "farm_code", "forecast_power"]}',
 true, '1.0.0', 'system'),
('Daily Summary Template', 'Template for daily statistical reports', 'daily_report',
 '{"format": "json", "fields": ["date", "farm_code", "total_generation", "availability", "capacity_factor"], "required": ["date", "farm_code", "total_generation"]}',
 true, '1.0.0', 'system');

-- Insert default validation rules
INSERT INTO validation_rules (rule_name, rule_type, field_name, rule_config, error_message, severity) VALUES
('Required Time Field', 'required_field', 'time', '{}', 'Time field is required', 'error'),
('Required Farm Code', 'required_field', 'farm_code', '{}', 'Farm code is required', 'error'),
('Required Available Power', 'required_field', 'available_power', '{}', 'Available power is required', 'error'),
('Power Range Validation', 'data_range', 'available_power', '{"min": 0, "max": 1000}', 'Available power must be between 0 and 1000 MW', 'error'),
('Time Format Validation', 'format_check', 'time', '{"format": "YYYY-MM-DD HH:MM:SS"}', 'Time must be in YYYY-MM-DD HH:MM:SS format', 'error'),
('Farm Code Validation', 'business_rule', 'farm_code', '{"allowed_values": ["DEFAULT_FARM", "zyx01", "zyx02"]}', 'Invalid farm code', 'error');

-- Insert default schedules
INSERT INTO schedules (schedule_name, farm_id, report_type, template_id, cron_expression, priority, max_retries, created_by) VALUES
('Auto Report Schedule - 15min', 1, 'auto_report', 1, '*/15 * * * *', 1, 3, 'system'),
('Auto Report Schedule - 15min', 2, 'auto_report', 1, '*/15 * * * *', 1, 3, 'system'),
('Auto Report Schedule - 15min', 3, 'auto_report', 1, '*/15 * * * *', 1, 3, 'system'),
('Daily Summary Schedule', 1, 'daily_report', 3, '0 0 * * *', 2, 3, 'system'),
('Daily Summary Schedule', 2, 'daily_report', 3, '0 0 * * *', 2, 3, 'system'),
('Daily Summary Schedule', 3, 'daily_report', 3, '0 0 * * *', 2, 3, 'system');