-- Prediction Database Schema
-- Database: windpower_prediction

-- Prediction models table
CREATE TABLE IF NOT EXISTS prediction_models (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    model_type VARCHAR(50) NOT NULL, -- lstm, xgboost, random_forest, neural_network
    prediction_type VARCHAR(50) NOT NULL, -- ultra_short, short_term, medium_term
    target_variable VARCHAR(50) NOT NULL, -- power, wind_speed, capacity_factor
    input_features JSONB, -- array of input feature names
    model_version VARCHAR(20) NOT NULL,
    model_file_path VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    is_trained BOOLEAN DEFAULT false,
    training_time INTERVAL,
    accuracy DECIMAL(5, 4),
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Model versions table
CREATE TABLE IF NOT EXISTS model_versions (
    id SERIAL PRIMARY KEY,
    model_id INTEGER NOT NULL REFERENCES prediction_models(id) ON DELETE CASCADE,
    version VARCHAR(20) NOT NULL,
    model_file_path VARCHAR(255) NOT NULL,
    model_size BIGINT,
    hyperparameters JSONB,
    training_dataset_id INTEGER,
    validation_accuracy DECIMAL(5, 4),
    test_accuracy DECIMAL(5, 4),
    training_time INTERVAL,
    is_active BOOLEAN DEFAULT false,
    is_production BOOLEAN DEFAULT false,
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(model_id, version)
);

-- Training tasks table
CREATE TABLE IF NOT EXISTS training_tasks (
    id SERIAL PRIMARY KEY,
    model_id INTEGER NOT NULL REFERENCES prediction_models(id) ON DELETE CASCADE,
    task_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending', -- pending, running, completed, failed, cancelled
    farm_id INTEGER,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    duration INTERVAL,
    training_dataset_path VARCHAR(255),
    validation_dataset_path VARCHAR(255),
    hyperparameters JSONB,
    model_version VARCHAR(20),
    model_file_path VARCHAR(255),
    training_accuracy DECIMAL(5, 4),
    validation_accuracy DECIMAL(5, 4),
    test_accuracy DECIMAL(5, 4),
    loss DECIMAL(10, 6),
    error_message TEXT,
    logs TEXT,
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Training datasets table
CREATE TABLE IF NOT EXISTS training_datasets (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    farm_id INTEGER,
    data_start_date TIMESTAMP,
    data_end_date TIMESTAMP,
    record_count INTEGER,
    file_path VARCHAR(255),
    file_size BIGINT,
    file_hash VARCHAR(64),
    data_source VARCHAR(50),
    quality_score DECIMAL(5, 4),
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Prediction results table
CREATE TABLE IF NOT EXISTS prediction_results (
    id SERIAL PRIMARY KEY,
    model_id INTEGER NOT NULL REFERENCES prediction_models(id) ON DELETE CASCADE,
    model_version_id INTEGER REFERENCES model_versions(id) ON DELETE SET NULL,
    farm_id INTEGER NOT NULL,
    prediction_type VARCHAR(50) NOT NULL,
    prediction_time TIMESTAMP NOT NULL,
    target_time TIMESTAMP NOT NULL,
    predicted_value DECIMAL(12, 3),
    confidence_lower DECIMAL(12, 3),
    confidence_upper DECIMAL(12, 3),
    confidence_level DECIMAL(5, 3),
    actual_value DECIMAL(12, 3),
    error DECIMAL(12, 3),
    percentage_error DECIMAL(8, 4),
    input_data JSONB,
    model_metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Model metrics table
CREATE TABLE IF NOT EXISTS model_metrics (
    id SERIAL PRIMARY KEY,
    model_id INTEGER NOT NULL REFERENCES prediction_models(id) ON DELETE CASCADE,
    model_version_id INTEGER REFERENCES model_versions(id) ON DELETE SET NULL,
    metric_name VARCHAR(50) NOT NULL, -- mae, mse, rmse, mape, r2, accuracy
    metric_value DECIMAL(12, 6) NOT NULL,
    dataset_type VARCHAR(20) NOT NULL, -- training, validation, test
    calculation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    parameters JSONB
);

-- Hyperparameters table
CREATE TABLE IF NOT EXISTS hyperparameters (
    id SERIAL PRIMARY KEY,
    model_type VARCHAR(50) NOT NULL,
    parameter_name VARCHAR(50) NOT NULL,
    parameter_type VARCHAR(20) NOT NULL, -- integer, float, string, boolean, array
    default_value TEXT,
    min_value DECIMAL(12, 6),
    max_value DECIMAL(12, 6),
    step_value DECIMAL(12, 6),
    description TEXT,
    is_required BOOLEAN DEFAULT true,
    is_tunable BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(model_type, parameter_name)
);

-- Model deployments table
CREATE TABLE IF NOT EXISTS model_deployments (
    id SERIAL PRIMARY KEY,
    model_id INTEGER NOT NULL REFERENCES prediction_models(id) ON DELETE CASCADE,
    model_version_id INTEGER NOT NULL REFERENCES model_versions(id) ON DELETE CASCADE,
    deployment_name VARCHAR(100) NOT NULL,
    environment VARCHAR(20) NOT NULL, -- development, staging, production
    status VARCHAR(20) DEFAULT 'pending', -- pending, deployed, failed, retired
    deployed_at TIMESTAMP,
    retired_at TIMESTAMP,
    deployment_config JSONB,
    endpoint_url VARCHAR(255),
    api_key VARCHAR(255),
    health_check_url VARCHAR(255),
    monitoring_config JSONB,
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Feature importance table
CREATE TABLE IF NOT EXISTS feature_importance (
    id SERIAL PRIMARY KEY,
    model_id INTEGER NOT NULL REFERENCES prediction_models(id) ON DELETE CASCADE,
    model_version_id INTEGER REFERENCES model_versions(id) ON DELETE SET NULL,
    feature_name VARCHAR(100) NOT NULL,
    importance_value DECIMAL(12, 6) NOT NULL,
    importance_type VARCHAR(50) DEFAULT 'weight', -- weight, gain, cover, etc.
    rank INTEGER,
    calculation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Prediction schedules table
CREATE TABLE IF NOT EXISTS prediction_schedules (
    id SERIAL PRIMARY KEY,
    model_id INTEGER NOT NULL REFERENCES prediction_models(id) ON DELETE CASCADE,
    farm_id INTEGER NOT NULL,
    schedule_name VARCHAR(100) NOT NULL,
    prediction_type VARCHAR(50) NOT NULL,
    cron_expression VARCHAR(100) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    last_run TIMESTAMP,
    next_run TIMESTAMP,
    run_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    config JSONB,
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Model monitoring table
CREATE TABLE IF NOT EXISTS model_monitoring (
    id SERIAL PRIMARY KEY,
    model_id INTEGER NOT NULL REFERENCES prediction_models(id) ON DELETE CASCADE,
    model_version_id INTEGER REFERENCES model_versions(id) ON DELETE SET NULL,
    monitoring_date TIMESTAMP NOT NULL,
    prediction_count INTEGER DEFAULT 0,
    average_error DECIMAL(12, 6),
    max_error DECIMAL(12, 6),
    error_std DECIMAL(12, 6),
    accuracy_drift DECIMAL(8, 6),
    data_drift_score DECIMAL(8, 6),
    performance_score DECIMAL(8, 6),
    alerts JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_prediction_models_type ON prediction_models(model_type);
CREATE INDEX idx_prediction_models_prediction_type ON prediction_models(prediction_type);
CREATE INDEX idx_prediction_models_active ON prediction_models(is_active);
CREATE INDEX idx_model_versions_model_id ON model_versions(model_id);
CREATE INDEX idx_model_versions_active ON model_versions(is_active);
CREATE INDEX idx_model_versions_production ON model_versions(is_production);
CREATE INDEX idx_training_tasks_model_id ON training_tasks(model_id);
CREATE INDEX idx_training_tasks_status ON training_tasks(status);
CREATE INDEX idx_training_tasks_farm_id ON training_tasks(farm_id);
CREATE INDEX idx_prediction_results_model_id ON prediction_results(model_id);
CREATE INDEX idx_prediction_results_farm_id ON prediction_results(farm_id);
CREATE INDEX idx_prediction_results_prediction_type ON prediction_results(prediction_type);
CREATE INDEX idx_prediction_results_target_time ON prediction_results(target_time);
CREATE INDEX idx_model_metrics_model_id ON model_metrics(model_id);
CREATE INDEX idx_model_metrics_dataset_type ON model_metrics(dataset_type);
CREATE INDEX idx_model_deployments_model_id ON model_deployments(model_id);
CREATE INDEX idx_model_deployments_environment ON model_deployments(environment);
CREATE INDEX idx_feature_importance_model_id ON feature_importance(model_id);
CREATE INDEX idx_prediction_schedules_model_id ON prediction_schedules(model_id);
CREATE INDEX idx_prediction_schedules_farm_id ON prediction_schedules(farm_id);
CREATE INDEX idx_prediction_schedules_active ON prediction_schedules(is_active);
CREATE INDEX idx_model_monitoring_model_id ON model_monitoring(model_id);
CREATE INDEX idx_model_monitoring_date ON model_monitoring(monitoring_date);

-- Insert default hyperparameters
INSERT INTO hyperparameters (model_type, parameter_name, parameter_type, default_value, min_value, max_value, description, is_required, is_tunable) VALUES
('lstm', 'units', 'integer', '50', '10', '500', 'Number of LSTM units', true, true),
('lstm', 'layers', 'integer', '2', '1', '5', 'Number of LSTM layers', true, true),
('lstm', 'dropout', 'float', '0.2', '0.0', '0.5', 'Dropout rate', true, true),
('lstm', 'learning_rate', 'float', '0.001', '0.0001', '0.01', 'Learning rate', true, true),
('lstm', 'epochs', 'integer', '100', '10', '1000', 'Number of training epochs', true, true),
('lstm', 'batch_size', 'integer', '32', '8', '256', 'Batch size', true, true),
('xgboost', 'n_estimators', 'integer', '100', '10', '1000', 'Number of estimators', true, true),
('xgboost', 'max_depth', 'integer', '6', '3', '15', 'Maximum tree depth', true, true),
('xgboost', 'learning_rate', 'float', '0.1', '0.01', '0.3', 'Learning rate', true, true),
('xgboost', 'subsample', 'float', '1.0', '0.5', '1.0', 'Subsample ratio', true, true),
('xgboost', 'colsample_bytree', 'float', '1.0', '0.5', '1.0', 'Column subsample ratio', true, true),
('random_forest', 'n_estimators', 'integer', '100', '10', '1000', 'Number of trees', true, true),
('random_forest', 'max_depth', 'integer', '10', '1', '50', 'Maximum tree depth', true, true),
('random_forest', 'min_samples_split', 'integer', '2', '2', '20', 'Minimum samples to split', true, true),
('random_forest', 'min_samples_leaf', 'integer', '1', '1', '10', 'Minimum samples per leaf', true, true);

-- Insert default prediction models
INSERT INTO prediction_models (name, description, model_type, prediction_type, target_variable, model_version, is_active, created_by) VALUES
('Ultra Short Term Power Prediction', '15-minute ahead power prediction using LSTM', 'lstm', 'ultra_short', 'power', '1.0.0', true, 'system'),
('Short Term Power Prediction', '4-hour ahead power prediction using XGBoost', 'xgboost', 'short_term', 'power', '1.0.0', true, 'system'),
('Medium Term Power Prediction', '72-hour ahead power prediction using Random Forest', 'random_forest', 'medium_term', 'power', '1.0.0', true, 'system');