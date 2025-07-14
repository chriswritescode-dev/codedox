-- PostgreSQL schema for code extraction and search
-- Requires PostgreSQL 12+ with pg_trgm extension

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Note: Tables are created with IF NOT EXISTS to avoid dropping data
-- To reset the database, use: python cli.py init --drop

-- Crawl job tracking
CREATE TABLE IF NOT EXISTS crawl_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    domain TEXT UNIQUE,
    start_urls TEXT[] NOT NULL,
    max_depth INTEGER DEFAULT 1 CHECK (max_depth >= 0 AND max_depth <= 5),
    domain_restrictions TEXT[],
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'paused', 'completed', 'failed', 'cancelled')),
    total_pages INTEGER DEFAULT 0,
    processed_pages INTEGER DEFAULT 0,
    snippets_extracted INTEGER DEFAULT 0,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    config JSONB DEFAULT '{}',
    created_by TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- New tracking fields for recovery
    last_heartbeat TIMESTAMP,
    crawl_phase VARCHAR(20) CHECK (crawl_phase IN ('crawling', 'enriching', 'finalizing') OR crawl_phase IS NULL),
    crawl_completed_at TIMESTAMP,
    enrichment_started_at TIMESTAMP,
    enrichment_completed_at TIMESTAMP,
    documents_crawled INTEGER DEFAULT 0,
    documents_enriched INTEGER DEFAULT 0,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3
);

-- Documents/pages crawled
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    title TEXT,
    content_type VARCHAR(50) DEFAULT 'html',
    markdown_content TEXT,
    content_hash VARCHAR(64),
    crawl_job_id UUID REFERENCES crawl_jobs(id) ON DELETE CASCADE,
    crawl_depth INTEGER DEFAULT 0,
    parent_url TEXT,
    last_crawled TIMESTAMP DEFAULT NOW(),
    meta_data JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Enrichment tracking
    enrichment_status VARCHAR(20) DEFAULT 'pending' CHECK (enrichment_status IN ('pending', 'processing', 'completed', 'failed', 'skipped')),
    enrichment_error TEXT,
    enriched_at TIMESTAMP
);

-- Code snippets extracted from documents
CREATE TABLE IF NOT EXISTS code_snippets (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    title TEXT,
    description TEXT,
    language VARCHAR(50),
    code_content TEXT NOT NULL,
    code_hash VARCHAR(64) UNIQUE,
    line_start INTEGER,
    line_end INTEGER,
    context_before TEXT,
    context_after TEXT,
    
    -- Enhanced context fields
    section_title TEXT,
    section_content TEXT,  -- Full section containing the code
    related_snippets INTEGER[],  -- IDs of related code snippets
    
    functions TEXT[],
    imports TEXT[],
    keywords TEXT[],
    snippet_type VARCHAR(20) DEFAULT 'code' CHECK (snippet_type IN ('function', 'class', 'example', 'config', 'code')),
    source_url TEXT,
    
    -- Full-text search vector (will be populated by trigger)
    search_vector tsvector,
    
    meta_data JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Link graph for crawl depth tracking
CREATE TABLE IF NOT EXISTS page_links (
    id SERIAL PRIMARY KEY,
    source_url TEXT NOT NULL,
    target_url TEXT NOT NULL,
    link_text TEXT,
    crawl_job_id UUID REFERENCES crawl_jobs(id) ON DELETE CASCADE,
    depth_level INTEGER DEFAULT 1,
    discovered_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(source_url, target_url, crawl_job_id)
);

-- Indexes for performance

-- Crawl jobs indexes
CREATE INDEX IF NOT EXISTS idx_crawl_jobs_status ON crawl_jobs(status);
CREATE INDEX IF NOT EXISTS idx_crawl_jobs_created_by ON crawl_jobs(created_by);
CREATE INDEX IF NOT EXISTS idx_crawl_jobs_created_at ON crawl_jobs(created_at DESC);

-- Documents indexes
CREATE INDEX IF NOT EXISTS idx_documents_url ON documents(url);
CREATE INDEX IF NOT EXISTS idx_documents_crawl_job_id ON documents(crawl_job_id);
CREATE INDEX IF NOT EXISTS idx_documents_content_hash ON documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_documents_crawl_depth ON documents(crawl_depth);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at DESC);

-- Code snippets indexes
CREATE INDEX IF NOT EXISTS idx_snippets_search_vector ON code_snippets USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS idx_snippets_language ON code_snippets(language);
CREATE INDEX IF NOT EXISTS idx_snippets_document_id ON code_snippets(document_id);
CREATE INDEX IF NOT EXISTS idx_snippets_source_url ON code_snippets(source_url);
CREATE INDEX IF NOT EXISTS idx_snippets_functions ON code_snippets USING GIN(functions);
CREATE INDEX IF NOT EXISTS idx_snippets_imports ON code_snippets USING GIN(imports);
CREATE INDEX IF NOT EXISTS idx_snippets_snippet_type ON code_snippets(snippet_type);
CREATE INDEX IF NOT EXISTS idx_snippets_created_at ON code_snippets(created_at DESC);

-- Trigram indexes for fuzzy search
CREATE INDEX IF NOT EXISTS idx_snippets_title_trgm ON code_snippets USING GIN(title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_snippets_description_trgm ON code_snippets USING GIN(description gin_trgm_ops);

-- Page links indexes
CREATE INDEX IF NOT EXISTS idx_page_links_crawl_job_id ON page_links(crawl_job_id);
CREATE INDEX IF NOT EXISTS idx_page_links_depth_level ON page_links(depth_level);

-- Update timestamp triggers
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_crawl_jobs_updated_at ON crawl_jobs;
CREATE TRIGGER update_crawl_jobs_updated_at BEFORE UPDATE ON crawl_jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS update_documents_updated_at ON documents;
CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS update_code_snippets_updated_at ON code_snippets;
CREATE TRIGGER update_code_snippets_updated_at BEFORE UPDATE ON code_snippets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Function to update search vector
CREATE OR REPLACE FUNCTION update_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    -- Use default text search config if 'english' is not available
    NEW.search_vector := 
        setweight(to_tsvector(COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector(COALESCE(NEW.description, '')), 'B') ||
        setweight(to_tsvector(COALESCE(NEW.code_content, '')), 'C') ||
        setweight(to_tsvector(COALESCE(array_to_string(NEW.functions, ' '), '')), 'B') ||
        setweight(to_tsvector(COALESCE(array_to_string(NEW.imports, ' '), '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to maintain search vector
DROP TRIGGER IF EXISTS update_code_snippets_search_vector ON code_snippets;
CREATE TRIGGER update_code_snippets_search_vector 
    BEFORE INSERT OR UPDATE OF title, description, code_content, functions, imports 
    ON code_snippets
    FOR EACH ROW EXECUTE FUNCTION update_search_vector();

-- Helper views

-- View for source statistics
CREATE OR REPLACE VIEW source_statistics AS
SELECT 
    COALESCE(d.meta_data->>'library_name', 'Unknown') as name,
    d.meta_data->>'repository' as repository,
    d.meta_data->>'description' as description,
    cj.status,
    COUNT(DISTINCT d.id) as document_count,
    COUNT(DISTINCT cs.id) as snippet_count,
    SUM(LENGTH(cs.code_content)) as total_characters,
    MAX(cs.created_at) as last_updated,
    cj.id as crawl_job_id
FROM crawl_jobs cj
LEFT JOIN documents d ON d.crawl_job_id = cj.id
LEFT JOIN code_snippets cs ON cs.document_id = d.id
GROUP BY cj.id, d.meta_data->>'library_name', d.meta_data->>'repository', d.meta_data->>'description', cj.status;

-- Function for full-text search
CREATE OR REPLACE FUNCTION search_code_snippets(
    p_query TEXT DEFAULT NULL,
    p_source TEXT DEFAULT NULL,
    p_language TEXT DEFAULT NULL,
    p_limit INTEGER DEFAULT 10,
    p_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    id INTEGER,
    title TEXT,
    description TEXT,
    source_url TEXT,
    language VARCHAR(50),
    code_content TEXT,
    rank REAL,
    snippet_preview TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        cs.id,
        cs.title,
        cs.description,
        cs.source_url,
        cs.language,
        cs.code_content,
        CASE 
            WHEN p_query IS NOT NULL THEN ts_rank(cs.search_vector, plainto_tsquery(p_query))
            ELSE 0.0
        END as rank,
        LEFT(cs.code_content, 200) as snippet_preview
    FROM code_snippets cs
    WHERE 
        (p_query IS NULL OR cs.search_vector @@ plainto_tsquery(p_query))
        AND (p_source IS NULL OR cs.source_url ILIKE '%' || p_source || '%')
        AND (p_language IS NULL OR cs.language = p_language)
    ORDER BY 
        CASE 
            WHEN p_query IS NOT NULL THEN ts_rank(cs.search_vector, plainto_tsquery(p_query))
            ELSE cs.created_at::timestamp::numeric
        END DESC
    LIMIT p_limit
    OFFSET p_offset;
END;
$$ LANGUAGE plpgsql;

-- Failed pages tracking for retry functionality
CREATE TABLE IF NOT EXISTS failed_pages (
    id SERIAL PRIMARY KEY,
    crawl_job_id UUID REFERENCES crawl_jobs(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    error_message TEXT,
    failed_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(crawl_job_id, url)
);

-- Index for fast lookups by crawl job
CREATE INDEX IF NOT EXISTS idx_failed_pages_crawl_job_id ON failed_pages(crawl_job_id);

-- Grant permissions (adjust as needed)
-- GRANT ALL ON ALL TABLES IN SCHEMA public TO your_app_user;
-- GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO your_app_user;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO your_app_user;