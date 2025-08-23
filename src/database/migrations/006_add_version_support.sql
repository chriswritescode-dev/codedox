-- Migration: Add version support for libraries
-- This allows multiple versions of the same library (e.g., Next.js v14 and v15) to coexist

-- Add version column to crawl_jobs table
ALTER TABLE crawl_jobs 
ADD COLUMN IF NOT EXISTS version TEXT;

-- Add version column to upload_jobs table  
ALTER TABLE upload_jobs
ADD COLUMN IF NOT EXISTS version TEXT;

-- Drop the old unique constraint on domain (if it exists)
ALTER TABLE crawl_jobs 
DROP CONSTRAINT IF EXISTS crawl_jobs_domain_key;

-- Add new composite unique constraint on (name, version)
ALTER TABLE crawl_jobs
DROP CONSTRAINT IF EXISTS unique_name_version;
ALTER TABLE crawl_jobs
ADD CONSTRAINT unique_name_version UNIQUE (name, version);

-- Add composite unique constraint for upload jobs
ALTER TABLE upload_jobs
DROP CONSTRAINT IF EXISTS unique_upload_name_version;
ALTER TABLE upload_jobs
ADD CONSTRAINT unique_upload_name_version UNIQUE (name, version);

-- Recreate the source_statistics view with version support
DROP VIEW IF EXISTS source_statistics;
CREATE VIEW source_statistics AS
SELECT 
    name,
    version,
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
        cj.version as version,
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
    GROUP BY cj.id, cj.name, cj.version, cj.domain, cj.status, cj.config
    
    UNION ALL
    
    -- Upload jobs
    SELECT 
        uj.name as name,
        uj.version as version,
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
    GROUP BY uj.id, uj.name, uj.version, uj.status, uj.config
) combined_stats;

-- Create indexes for better performance on version queries
CREATE INDEX IF NOT EXISTS idx_crawl_jobs_name_version ON crawl_jobs(name, version);
CREATE INDEX IF NOT EXISTS idx_upload_jobs_name_version ON upload_jobs(name, version);