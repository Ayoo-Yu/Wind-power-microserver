-- Simulation Database Schema
-- Database: windpower_simulation

-- Simulation scenarios table
CREATE TABLE IF NOT EXISTS simulation_scenarios (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    scenario_type VARCHAR(50) NOT NULL, -- power_curve, wake_effect, wind_resource, grid_integration
    farm_id INTEGER NOT NULL,
    base_wind_speed DECIMAL(6, 2), -- m/s
    base_wind_direction DECIMAL(6, 2), -- degrees
    base_temperature DECIMAL(5, 2), -- Celsius
    base_pressure DECIMAL(7, 2), -- hPa
    base_air_density DECIMAL(6, 4), -- kg/m³
    simulation_duration INTERVAL, -- simulation time period
    time_step INTERVAL DEFAULT '1 minute', -- simulation time step
    is_template BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Simulation runs table
CREATE TABLE IF NOT EXISTS simulation_runs (
    id SERIAL PRIMARY KEY,
    scenario_id INTEGER NOT NULL REFERENCES simulation_scenarios(id) ON DELETE CASCADE,
    run_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending', -- pending, running, completed, failed, cancelled
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    duration INTERVAL,
    progress DECIMAL(5, 4) DEFAULT 0.0,
    total_steps INTEGER,
    completed_steps INTEGER DEFAULT 0,
    input_parameters JSONB,
    run_config JSONB,
    results_summary JSONB,
    error_message TEXT,
    logs TEXT,
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Simulation results table
CREATE TABLE IF NOT EXISTS simulation_results (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES simulation_runs(id) ON DELETE CASCADE,
    timestamp TIMESTAMP NOT NULL,
    step_number INTEGER NOT NULL,
    farm_id INTEGER NOT NULL,
    total_power DECIMAL(12, 3), -- MW
    average_wind_speed DECIMAL(6, 2), -- m/s
    average_wind_direction DECIMAL(6, 2), -- degrees
    average_temperature DECIMAL(5, 2), -- Celsius
    air_density DECIMAL(6, 4), -- kg/m³
    capacity_factor DECIMAL(5, 3),
    turbulence_intensity DECIMAL(6, 4),
    wake_loss DECIMAL(8, 4), -- MW
    availability DECIMAL(5, 4),
    turbine_results JSONB, -- detailed turbine-level results
    power_curve_data JSONB, -- power curve points
    wake_effect_data JSONB, -- wake effect visualization data
    grid_data JSONB, -- grid integration data
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(run_id, step_number)
);

-- Physical parameters table
CREATE TABLE IF NOT EXISTS physical_parameters (
    id SERIAL PRIMARY KEY,
    parameter_name VARCHAR(100) NOT NULL,
    parameter_type VARCHAR(50) NOT NULL, -- turbine, farm, environmental, grid
    parameter_value DECIMAL(15, 6) NOT NULL,
    unit VARCHAR(20) NOT NULL,
    description TEXT,
    source VARCHAR(50), -- measured, calculated, estimated
    confidence_level DECIMAL(5, 4),
    valid_from TIMESTAMP,
    valid_to TIMESTAMP,
    farm_id INTEGER,
    turbine_id INTEGER,
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Optimization tasks table
CREATE TABLE IF NOT EXISTS optimization_tasks (
    id SERIAL PRIMARY KEY,
    task_name VARCHAR(100) NOT NULL,
    optimization_type VARCHAR(50) NOT NULL, -- layout, yaw, pitch, power, maintenance
    scenario_id INTEGER NOT NULL REFERENCES simulation_scenarios(id) ON DELETE CASCADE,
    farm_id INTEGER NOT NULL,
    status VARCHAR(20) DEFAULT 'pending', -- pending, running, completed, failed, cancelled
    algorithm VARCHAR(50) NOT NULL, -- genetic_algorithm, particle_swarm, simulated_annealing
    objective_function VARCHAR(100) NOT NULL,
    constraints JSONB,
    parameters JSONB,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    iterations INTEGER DEFAULT 0,
    best_fitness DECIMAL(15, 6),
    best_solution JSONB,
    convergence_data JSONB,
    error_message TEXT,
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Wind resource data table
CREATE TABLE IF NOT EXISTS wind_resource_data (
    id SERIAL PRIMARY KEY,
    farm_id INTEGER NOT NULL,
    height DECIMAL(6, 2) NOT NULL, -- meters
    wind_speed DECIMAL(6, 2), -- m/s
    wind_direction DECIMAL(6, 2), -- degrees
    turbulence_intensity DECIMAL(6, 4),
    wind_shear DECIMAL(6, 4),
    air_density DECIMAL(6, 4), -- kg/m³
    temperature DECIMAL(5, 2), -- Celsius
    pressure DECIMAL(7, 2), -- hPa
    data_frequency VARCHAR(20), -- 10min, hourly, daily
    data_period_start TIMESTAMP,
    data_period_end TIMESTAMP,
    source VARCHAR(50), -- measured, modeled, reanalysis
    quality_score DECIMAL(5, 4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Power curve data table
CREATE TABLE IF NOT EXISTS power_curve_data (
    id SERIAL PRIMARY KEY,
    turbine_model VARCHAR(50) NOT NULL,
    manufacturer VARCHAR(50),
    rated_power DECIMAL(8, 3), -- MW
    cut_in_speed DECIMAL(5, 2), -- m/s
    rated_speed DECIMAL(5, 2), -- m/s
    cut_out_speed DECIMAL(5, 2), -- m/s
    wind_speed DECIMAL(5, 2) NOT NULL, -- m/s
    power_output DECIMAL(8, 3) NOT NULL, -- MW
    power_coefficient DECIMAL(6, 4),
    thrust_coefficient DECIMAL(6, 4),
    air_density DECIMAL(6, 4), -- kg/m³
    data_source VARCHAR(50), -- manufacturer, measured, calculated
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Wake model parameters table
CREATE TABLE IF NOT EXISTS wake_model_parameters (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(50) NOT NULL, -- jensen, ainslie, larsen, gaussian
    wake_expansion_coefficient DECIMAL(6, 4),
    thrust_coefficient DECIMAL(6, 4),
    turbulence_intensity DECIMAL(6, 4),
    wind_shear_expponent DECIMAL(6, 4),
    roughness_length DECIMAL(8, 6), -- m
    ambient_turbulence DECIMAL(6, 4),
    description TEXT,
    is_default BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    created_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Grid connection data table
CREATE TABLE IF NOT EXISTS grid_connection_data (
    id SERIAL PRIMARY KEY,
    farm_id INTEGER NOT NULL,
    connection_point VARCHAR(100) NOT NULL,
    voltage_level DECIMAL(8, 2), -- kV
    rated_capacity DECIMAL(12, 3), -- MW
    short_circuit_capacity DECIMAL(12, 3), -- MVA
    x_ratio DECIMAL(8, 4), -- reactance ratio
    r_ratio DECIMAL(8, 4), -- resistance ratio
    power_factor_limits JSONB,
    voltage_limits JSONB,
    frequency_limits JSONB,
    grid_code VARCHAR(50),
    interconnection_date DATE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Terrain data table
CREATE TABLE IF NOT EXISTS terrain_data (
    id SERIAL PRIMARY KEY,
    farm_id INTEGER NOT NULL,
    coordinate_x DECIMAL(12, 8), -- longitude or local X
    coordinate_y DECIMAL(12, 8), -- latitude or local Y
    elevation DECIMAL(8, 2), -- meters above sea level
    roughness_class INTEGER,
    roughness_length DECIMAL(8, 6), -- m
    land_use_type VARCHAR(50),
    obstacle_height DECIMAL(6, 2), -- m
    obstacle_distance DECIMAL(8, 2), -- m
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Environmental conditions table
CREATE TABLE IF NOT EXISTS environmental_conditions (
    id SERIAL PRIMARY KEY,
    farm_id INTEGER NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    air_temperature DECIMAL(5, 2), -- Celsius
    air_pressure DECIMAL(7, 2), -- hPa
    air_density DECIMAL(6, 4), -- kg/m³
    humidity DECIMAL(5, 2), -- %
    solar_radiation DECIMAL(8, 2), -- W/m²
    precipitation DECIMAL(6, 2), -- mm
    visibility DECIMAL(6, 2), -- km
    cloud_cover DECIMAL(4, 2), -- %
    icing_condition BOOLEAN DEFAULT false,
    icing_severity INTEGER, -- 0-5 scale
    lightning_probability DECIMAL(5, 4), -- probability 0-1
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(farm_id, timestamp)
);

-- Create indexes
CREATE INDEX idx_simulation_scenarios_farm_id ON simulation_scenarios(farm_id);
CREATE INDEX idx_simulation_scenarios_type ON simulation_scenarios(scenario_type);
CREATE INDEX idx_simulation_scenarios_active ON simulation_scenarios(is_active);
CREATE INDEX idx_simulation_runs_scenario_id ON simulation_runs(scenario_id);
CREATE INDEX idx_simulation_runs_status ON simulation_runs(status);
CREATE INDEX idx_simulation_runs_farm_id ON simulation_runs(farm_id);
CREATE INDEX idx_simulation_results_run_id ON simulation_results(run_id);
CREATE INDEX idx_simulation_results_timestamp ON simulation_results(timestamp);
CREATE INDEX idx_simulation_results_farm_id ON simulation_results(farm_id);
CREATE INDEX idx_physical_parameters_name ON physical_parameters(parameter_name);
CREATE INDEX idx_physical_parameters_type ON physical_parameters(parameter_type);
CREATE INDEX idx_physical_parameters_farm_id ON physical_parameters(farm_id);
CREATE INDEX idx_optimization_tasks_scenario_id ON optimization_tasks(scenario_id);
CREATE INDEX idx_optimization_tasks_type ON optimization_tasks(optimization_type);
CREATE INDEX idx_optimization_tasks_status ON optimization_tasks(status);
CREATE INDEX idx_optimization_tasks_farm_id ON optimization_tasks(farm_id);
CREATE INDEX idx_wind_resource_data_farm_id ON wind_resource_data(farm_id);
CREATE INDEX idx_wind_resource_data_height ON wind_resource_data(height);
CREATE INDEX idx_power_curve_data_model ON power_curve_data(turbine_model);
CREATE INDEX idx_power_curve_data_active ON power_curve_data(is_active);
CREATE INDEX idx_wake_model_parameters_model ON wake_model_parameters(model_name);
CREATE INDEX idx_wake_model_parameters_active ON wake_model_parameters(is_active);
CREATE INDEX idx_grid_connection_data_farm_id ON grid_connection_data(farm_id);
CREATE INDEX idx_grid_connection_data_active ON grid_connection_data(is_active);
CREATE INDEX idx_terrain_data_farm_id ON terrain_data(farm_id);
CREATE INDEX idx_environmental_conditions_farm_id ON environmental_conditions(farm_id);
CREATE INDEX idx_environmental_conditions_timestamp ON environmental_conditions(timestamp);

-- Insert default wake model parameters
INSERT INTO wake_model_parameters (model_name, wake_expansion_coefficient, thrust_coefficient, turbulence_intensity, wind_shear_expponent, roughness_length, description, is_default) VALUES
('Jensen', 0.075, 0.8, 0.1, 0.15, 0.01, 'Classic Jensen wake model', true),
('Ainslie', 0.075, 0.8, 0.1, 0.15, 0.01, 'Ainslie eddy viscosity wake model', false),
('Larsen', 0.075, 0.8, 0.1, 0.15, 0.01, 'Larsen wake model', false),
('Gaussian', 0.075, 0.8, 0.1, 0.15, 0.01, 'Gaussian wake model', false);

-- Insert default simulation scenarios
INSERT INTO simulation_scenarios (name, description, scenario_type, farm_id, base_wind_speed, base_wind_direction, simulation_duration, is_template, created_by) VALUES
('Standard Power Curve Simulation', 'Simulate power curve for standard conditions', 'power_curve', 1, 8.0, 270, '24 hours', true, 'system'),
('Wake Effect Analysis', 'Analyze wake effects in wind farm', 'wake_effect', 1, 10.0, 270, '24 hours', true, 'system'),
('Wind Resource Assessment', 'Assess wind resource potential', 'wind_resource', 1, 7.5, 270, '1 year', true, 'system'),
('Grid Integration Study', 'Study grid integration capabilities', 'grid_integration', 1, 9.0, 270, '24 hours', true, 'system');

-- Insert default optimization tasks
INSERT INTO optimization_tasks (task_name, optimization_type, scenario_id, farm_id, algorithm, objective_function, constraints, created_by) VALUES
('Turbine Layout Optimization', 'layout', 2, 1, 'genetic_algorithm', 'maximize_annual_energy_production', '{"min_spacing": "3D", "max_area": 1000000}', 'system'),
('Yaw Angle Optimization', 'yaw', 2, 1, 'particle_swarm', 'minimize_wake_losses', '{"yaw_range": [-30, 30]}', 'system'),
('Pitch Control Optimization', 'pitch', 2, 1, 'simulated_annealing', 'maximize_power_output', '{"pitch_range": [0, 45]}', 'system');