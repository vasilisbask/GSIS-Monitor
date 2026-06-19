-- Create function to update timestamp
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 1. Service Table
CREATE TABLE IF NOT EXISTS service (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    url VARCHAR(255) NOT NULL,
    verification_keyword VARCHAR(100),
    exclusion_keyword VARCHAR(100),
    skip_tls_verify BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    order_index INT DEFAULT 0 NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Trigger for updating service.updated_at
CREATE TRIGGER update_service_modtime
    BEFORE UPDATE ON service
    FOR EACH ROW
    EXECUTE FUNCTION update_modified_column();

-- 2. Ping Log Table (TimescaleDB Hypertable)
CREATE TABLE IF NOT EXISTS ping_log (
    time TIMESTAMPTZ NOT NULL,
    service_id INT NOT NULL REFERENCES service(id) ON DELETE CASCADE,
    is_healthy BOOLEAN NOT NULL,
    status_code INT,
    error_message TEXT,
    dns_lookup_ms DOUBLE PRECISION,
    tcp_connect_ms DOUBLE PRECISION,
    tls_handshake_ms DOUBLE PRECISION,
    ttfb_ms DOUBLE PRECISION,
    total_response_ms DOUBLE PRECISION,
    ssl_expiry_days INT,
    content_verified BOOLEAN DEFAULT FALSE
);

-- Create index for faster dashboard reads
CREATE INDEX IF NOT EXISTS idx_ping_log_service_time ON ping_log (service_id, time DESC);

-- Convert to hypertable and set 30-day retention policy if TimescaleDB is available
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        BEGIN
            PERFORM create_hypertable('ping_log', 'time', if_not_exists => TRUE);
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'create_hypertable failed, skipping: %', SQLERRM;
        END;

        BEGIN
            PERFORM add_retention_policy('ping_log', INTERVAL '30 days');
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'add_retention_policy failed (possibly already exists), skipping: %', SQLERRM;
        END;
    END IF;
END $$;

-- 3. Alert Rule Table
CREATE TABLE IF NOT EXISTS alert_rule (
    id SERIAL PRIMARY KEY,
    service_id INT NOT NULL REFERENCES service(id) ON DELETE CASCADE,
    metric VARCHAR(50) NOT NULL, -- 'latency', 'status_code', 'ssl_expiry', 'content_verified'
    operator VARCHAR(10) NOT NULL, -- '>', '<', '=', '!='
    value DOUBLE PRECISION NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Alert Log Table
CREATE TABLE IF NOT EXISTS alert_log (
    id SERIAL PRIMARY KEY,
    service_id INT NOT NULL REFERENCES service(id) ON DELETE CASCADE,
    alert_rule_id INT REFERENCES alert_rule(id) ON DELETE SET NULL,
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'active', -- 'active', 'resolved'
    message TEXT NOT NULL
);

-- Seed initial GSIS public services
INSERT INTO service (name, url, verification_keyword, exclusion_keyword, skip_tls_verify)
VALUES 
('e-Paravolo', 'https://www.gsis.gr/polites-epiheiriseis/pliromes-kai-eispraxeis/e-paravolo', 'e-Παράβολο', NULL, FALSE),
('Taxisnet SSO Login', 'https://login.gsis.gr/sso', 'gsis_logo.png', NULL, FALSE),
('Διαύγεια', 'https://diavgeia.gov.gr', NULL, NULL, FALSE),
('Απογραφή', 'https://apografi.gov.gr', NULL, NULL, TRUE),
('ΓΓΠΣΨΔ Portal', 'https://www.gsis.gr', 'Γενική Γραμματεία', NULL, FALSE)
ON CONFLICT (name) DO NOTHING;

-- Seed default alert rules for these services
-- e.g. latency > 2500ms, or healthy is false (handled by backend or status_code != 200, content_verified = false)
INSERT INTO alert_rule (service_id, metric, operator, value)
SELECT id, 'latency', '>', 2500.0 FROM service
ON CONFLICT DO NOTHING;

INSERT INTO alert_rule (service_id, metric, operator, value)
SELECT id, 'ssl_expiry', '<', 15.0 FROM service
ON CONFLICT DO NOTHING;
