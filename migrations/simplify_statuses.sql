-- Migration to simplify job statuses to only 'running' and 'completed'
-- Run this after updating the application code

-- First, update existing data to map old statuses to new ones
UPDATE crawl_jobs 
SET status = CASE
    WHEN status IN ('pending', 'running') THEN 'running'
    WHEN status IN ('completed', 'failed', 'cancelled', 'paused') THEN 'completed'
    ELSE 'completed'
END;

UPDATE upload_jobs 
SET status = CASE
    WHEN status IN ('pending', 'running') THEN 'running'
    WHEN status IN ('completed', 'failed', 'cancelled') THEN 'completed'
    ELSE 'completed'
END;

-- Now update the CHECK constraints
-- For crawl_jobs
ALTER TABLE crawl_jobs DROP CONSTRAINT IF EXISTS check_status;
ALTER TABLE crawl_jobs ADD CONSTRAINT check_status 
    CHECK (status IN ('running', 'completed'));

-- For upload_jobs
ALTER TABLE upload_jobs DROP CONSTRAINT IF EXISTS check_upload_status;
ALTER TABLE upload_jobs ADD CONSTRAINT check_upload_status 
    CHECK (status IN ('running', 'completed'));

-- Update default values
ALTER TABLE crawl_jobs ALTER COLUMN status SET DEFAULT 'running';
ALTER TABLE upload_jobs ALTER COLUMN status SET DEFAULT 'running';

-- Add comment to document the change
COMMENT ON COLUMN crawl_jobs.status IS 'Job status: running (active) or completed (finished/cancelled/failed)';
COMMENT ON COLUMN upload_jobs.status IS 'Job status: running (active) or completed (finished/cancelled/failed)';