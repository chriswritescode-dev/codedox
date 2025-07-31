-- Migration to add upload support to CodeDox
-- This adds upload_jobs table and updates documents table

-- Create upload_jobs table
CREATE TABLE IF NOT EXISTS upload_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    source_type VARCHAR(20) DEFAULT 'upload' CHECK (source_type IN ('upload', 'file', 'api')),
    file_count INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    processed_files INTEGER DEFAULT 0,
    snippets_extracted INTEGER DEFAULT 0,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    config JSONB DEFAULT '{}',
    created_by TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Add indexes for upload_jobs
CREATE INDEX IF NOT EXISTS idx_upload_jobs_status ON upload_jobs(status);
CREATE INDEX IF NOT EXISTS idx_upload_jobs_created_by ON upload_jobs(created_by);
CREATE INDEX IF NOT EXISTS idx_upload_jobs_created_at ON upload_jobs(created_at DESC);

-- Add trigger for upload_jobs
DROP TRIGGER IF EXISTS update_upload_jobs_updated_at ON upload_jobs;
CREATE TRIGGER update_upload_jobs_updated_at BEFORE UPDATE ON upload_jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Add new columns to documents table
ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS upload_job_id UUID REFERENCES upload_jobs(id) ON DELETE CASCADE,
ADD COLUMN IF NOT EXISTS source_type VARCHAR(20) DEFAULT 'crawl' CHECK (source_type IN ('crawl', 'upload'));

-- Add index for upload_job_id
CREATE INDEX IF NOT EXISTS idx_documents_upload_job_id ON documents(upload_job_id);
CREATE INDEX IF NOT EXISTS idx_documents_source_type ON documents(source_type);

-- Drop and recreate the constraint to ensure document is linked to either crawl or upload job
ALTER TABLE documents DROP CONSTRAINT IF EXISTS check_job_link;
ALTER TABLE documents ADD CONSTRAINT check_job_link CHECK (
    (crawl_job_id IS NOT NULL AND upload_job_id IS NULL AND source_type = 'crawl') OR
    (upload_job_id IS NOT NULL AND crawl_job_id IS NULL AND source_type = 'upload')
);

-- Update existing documents to have source_type = 'crawl' if they have a crawl_job_id
UPDATE documents 
SET source_type = 'crawl' 
WHERE crawl_job_id IS NOT NULL AND source_type IS NULL;

-- Drop the old source_statistics view
DROP VIEW IF EXISTS source_statistics;

-- Recreate source_statistics view to include both crawl and upload jobs
CREATE OR REPLACE VIEW source_statistics AS
SELECT 
    name,
    domain,
    repository,
    description,
    status,
    document_count,
    snippet_count,
    total_characters,
    last_updated,
    job_id,
    job_type
FROM (
    -- Crawl jobs
    SELECT 
        cj.name as name,
        cj.domain as domain,
        cj.config->'metadata'->>'repository' as repository,
        cj.config->'metadata'->>'description' as description,
        cj.status,
        COUNT(DISTINCT d.id) as document_count,
        COUNT(DISTINCT cs.id) as snippet_count,
        SUM(LENGTH(cs.code_content)) as total_characters,
        MAX(cs.created_at) as last_updated,
        cj.id as job_id,
        'crawl' as job_type
    FROM crawl_jobs cj
    LEFT JOIN documents d ON d.crawl_job_id = cj.id
    LEFT JOIN code_snippets cs ON cs.document_id = d.id
    GROUP BY cj.id, cj.name, cj.domain, cj.status, cj.config
    
    UNION ALL
    
    -- Upload jobs
    SELECT 
        uj.name as name,
        NULL as domain,
        uj.config->'metadata'->>'repository' as repository,
        uj.config->'metadata'->>'description' as description,
        uj.status,
        COUNT(DISTINCT d.id) as document_count,
        COUNT(DISTINCT cs.id) as snippet_count,
        SUM(LENGTH(cs.code_content)) as total_characters,
        MAX(cs.created_at) as last_updated,
        uj.id as job_id,
        'upload' as job_type
    FROM upload_jobs uj
    LEFT JOIN documents d ON d.upload_job_id = uj.id
    LEFT JOIN code_snippets cs ON cs.document_id = d.id
    GROUP BY uj.id, uj.name, uj.status, uj.config
) combined_stats;