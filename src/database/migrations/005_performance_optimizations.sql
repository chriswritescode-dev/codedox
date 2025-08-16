-- Migration: Performance optimizations
-- Date: 2025-08-16

-- Add index for duplicate code detection
CREATE INDEX IF NOT EXISTS idx_snippets_code_hash ON code_snippets(code_hash);

-- Add composite indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_crawl_jobs_status_created ON crawl_jobs(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_upload_jobs_status_created ON upload_jobs(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_documents_url_hash ON documents(url, content_hash);

-- Optimize full-text search function with language config and limited code content
CREATE OR REPLACE FUNCTION update_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := 
        setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.description, '')), 'B') ||
        setweight(to_tsvector('english', LEFT(COALESCE(NEW.code_content, ''), 5000)), 'C') ||
        setweight(to_tsvector('english', COALESCE(array_to_string(NEW.functions, ' '), '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(array_to_string(NEW.imports, ' '), '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Update statistics for frequently queried columns
ALTER TABLE code_snippets ALTER COLUMN language SET STATISTICS 1000;
ALTER TABLE code_snippets ALTER COLUMN search_vector SET STATISTICS 1000;
ALTER TABLE crawl_jobs ALTER COLUMN status SET STATISTICS 1000;
ALTER TABLE upload_jobs ALTER COLUMN status SET STATISTICS 1000;