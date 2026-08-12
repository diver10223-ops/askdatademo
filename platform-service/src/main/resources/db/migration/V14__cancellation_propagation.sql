ALTER TABLE run_request ADD COLUMN cancelled_by VARCHAR(128);
ALTER TABLE run_request ADD COLUMN cancelled_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE run_request ADD COLUMN cancel_propagated_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE run_request ADD COLUMN cancel_attempts INTEGER NOT NULL DEFAULT 0 CHECK (cancel_attempts >= 0);
CREATE INDEX idx_run_request_cancel_retry ON run_request(cancel_requested,status,cancel_propagated_at,created_at);
