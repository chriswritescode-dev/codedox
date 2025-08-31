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
    version TEXT,
    domain TEXT,
    start_urls TEXT[] NOT NULL,
    max_depth INTEGER DEFAULT 1 CHECK (max_depth >= 0 AND max_depth <= 5),
    domain_restrictions TEXT[],
    status VARCHAR(20) DEFAULT 'running' CHECK (status IN ('running', 'completed')),
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
    crawl_phase VARCHAR(20) CHECK (crawl_phase IN ('crawling', 'finalizing') OR crawl_phase IS NULL),
    crawl_completed_at TIMESTAMP,
    documents_crawled INTEGER DEFAULT 0,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    
    -- Unique constraint on name and version combination
    CONSTRAINT unique_name_version UNIQUE (name, version)
);

-- Upload job tracking
CREATE TABLE IF NOT EXISTS upload_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    version TEXT,
    source_type VARCHAR(20) DEFAULT 'upload' CHECK (source_type IN ('upload', 'file', 'api')),
    file_count INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'running' CHECK (status IN ('running', 'completed')),
    processed_files INTEGER DEFAULT 0,
    snippets_extracted INTEGER DEFAULT 0,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    config JSONB DEFAULT '{}',
    created_by TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Unique constraint on name and version combination
    CONSTRAINT unique_upload_name_version UNIQUE (name, version)
);

-- Documents/pages crawled
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    title TEXT,
    content_type VARCHAR(50) DEFAULT 'markdown',
    content_hash VARCHAR(64),
    markdown_content TEXT,
    crawl_job_id UUID REFERENCES crawl_jobs(id) ON DELETE CASCADE,
    upload_job_id UUID REFERENCES upload_jobs(id) ON DELETE CASCADE,
    source_type VARCHAR(20) DEFAULT 'crawl' CHECK (source_type IN ('crawl', 'upload')),
    crawl_depth INTEGER DEFAULT 0,
    parent_url TEXT,
    last_crawled TIMESTAMP DEFAULT NOW(),
    meta_data JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Ensure document is linked to either crawl or upload job
    CONSTRAINT check_job_link CHECK (
        (crawl_job_id IS NOT NULL AND upload_job_id IS NULL AND source_type = 'crawl') OR
        (upload_job_id IS NOT NULL AND crawl_job_id IS NULL AND source_type = 'upload')
    )
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


-- Indexes for performance

-- Crawl jobs indexes
CREATE INDEX IF NOT EXISTS idx_crawl_jobs_status ON crawl_jobs(status);
CREATE INDEX IF NOT EXISTS idx_crawl_jobs_created_by ON crawl_jobs(created_by);
CREATE INDEX IF NOT EXISTS idx_crawl_jobs_created_at ON crawl_jobs(created_at DESC);

-- Upload jobs indexes
CREATE INDEX IF NOT EXISTS idx_upload_jobs_status ON upload_jobs(status);
CREATE INDEX IF NOT EXISTS idx_upload_jobs_created_by ON upload_jobs(created_by);
CREATE INDEX IF NOT EXISTS idx_upload_jobs_created_at ON upload_jobs(created_at DESC);

-- Version-specific indexes for better performance
CREATE INDEX IF NOT EXISTS idx_crawl_jobs_name_version ON crawl_jobs(name, version);
CREATE INDEX IF NOT EXISTS idx_upload_jobs_name_version ON upload_jobs(name, version);

-- Documents indexes
CREATE INDEX IF NOT EXISTS idx_documents_url ON documents(url);
CREATE INDEX IF NOT EXISTS idx_documents_crawl_job_id ON documents(crawl_job_id);
CREATE INDEX IF NOT EXISTS idx_documents_upload_job_id ON documents(upload_job_id);
CREATE INDEX IF NOT EXISTS idx_documents_source_type ON documents(source_type);
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

-- Trigram indexes for fuzzy search on code snippets
CREATE INDEX IF NOT EXISTS idx_snippets_title_trgm ON code_snippets USING GIN(title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_snippets_description_trgm ON code_snippets USING GIN(description gin_trgm_ops);

-- Document search indexes
CREATE INDEX IF NOT EXISTS idx_documents_title ON documents(title);
-- Trigram indexes for fuzzy search on documents
CREATE INDEX IF NOT EXISTS idx_documents_title_trgm ON documents USING GIN(title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_documents_url_trgm ON documents USING GIN(url gin_trgm_ops);


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

DROP TRIGGER IF EXISTS update_upload_jobs_updated_at ON upload_jobs;
CREATE TRIGGER update_upload_jobs_updated_at BEFORE UPDATE ON upload_jobs
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

-- Function to update markdown search vector
CREATE OR REPLACE FUNCTION update_markdown_search_vector_trigger()
RETURNS TRIGGER AS $$
BEGIN
    NEW.markdown_search_vector := to_tsvector('english', COALESCE(NEW.markdown_content, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to maintain markdown search vector
DROP TRIGGER IF EXISTS update_markdown_search_vector ON documents;
CREATE TRIGGER update_markdown_search_vector
    BEFORE INSERT OR UPDATE OF markdown_content
    ON documents
    FOR EACH ROW EXECUTE FUNCTION update_markdown_search_vector_trigger();

-- Helper views

-- View for source statistics
CREATE OR REPLACE VIEW source_statistics AS
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

-- Snippet relationships table for tracking code dependencies
CREATE TABLE IF NOT EXISTS snippet_relationships (
    id SERIAL PRIMARY KEY,
    source_snippet_id INTEGER NOT NULL REFERENCES code_snippets(id) ON DELETE CASCADE,
    target_snippet_id INTEGER NOT NULL REFERENCES code_snippets(id) ON DELETE CASCADE,
    relationship_type VARCHAR(50) NOT NULL CHECK (
        relationship_type IN (
            'imports', 'extends', 'implements', 'uses', 
            'example_of', 'configuration_for', 'related'
        )
    ),
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    
    -- Ensure no duplicate relationships
    UNIQUE(source_snippet_id, target_snippet_id, relationship_type)
);

-- Create indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_snippet_rel_source ON snippet_relationships(source_snippet_id);
CREATE INDEX IF NOT EXISTS idx_snippet_rel_target ON snippet_relationships(target_snippet_id);
CREATE INDEX IF NOT EXISTS idx_snippet_rel_type ON snippet_relationships(relationship_type);

-- View for easy querying of relationships
CREATE OR REPLACE VIEW snippet_relationships_view AS
SELECT 
    sr.id,
    sr.relationship_type,
    sr.description,
    -- Source snippet info
    s1.id as source_id,
    s1.title as source_title,
    s1.language as source_language,
    s1.snippet_type as source_type,
    -- Target snippet info
    s2.id as target_id,
    s2.title as target_title,
    s2.language as target_language,
    s2.snippet_type as target_type,
    -- Document info
    d1.url as source_url,
    d2.url as target_url,
    d1.crawl_job_id as source_job_id,
    d2.crawl_job_id as target_job_id
FROM snippet_relationships sr
JOIN code_snippets s1 ON sr.source_snippet_id = s1.id
JOIN code_snippets s2 ON sr.target_snippet_id = s2.id
JOIN documents d1 ON s1.document_id = d1.id
JOIN documents d2 ON s2.document_id = d2.id;

-- Function to find related snippets efficiently
DROP FUNCTION IF EXISTS find_related_snippets(INTEGER[], VARCHAR[], INTEGER);
CREATE OR REPLACE FUNCTION find_related_snippets(
    p_snippet_ids INTEGER[],
    p_relationship_types VARCHAR[] DEFAULT NULL,
    p_limit INTEGER DEFAULT 10
)
RETURNS TABLE (
    snippet_id INTEGER,
    related_snippet_id INTEGER,
    relationship_type VARCHAR(50),
    description TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT DISTINCT
        sr.source_snippet_id,
        sr.target_snippet_id,
        sr.relationship_type,
        sr.description
    FROM snippet_relationships sr
    WHERE 
        sr.source_snippet_id = ANY(p_snippet_ids)
        AND (p_relationship_types IS NULL OR sr.relationship_type = ANY(p_relationship_types))
    UNION
    SELECT DISTINCT
        sr.target_snippet_id,
        sr.source_snippet_id,
        CASE 
            WHEN sr.relationship_type = 'imports' THEN 'imported_by'
            WHEN sr.relationship_type = 'extends' THEN 'extended_by'
            WHEN sr.relationship_type = 'implements' THEN 'implemented_by'
            WHEN sr.relationship_type = 'uses' THEN 'used_by'
            WHEN sr.relationship_type = 'example_of' THEN 'has_example'
            WHEN sr.relationship_type = 'configuration_for' THEN 'configured_by'
            ELSE 'related'
        END as relationship_type,
        sr.description
    FROM snippet_relationships sr
    WHERE 
        sr.target_snippet_id = ANY(p_snippet_ids)
        AND (p_relationship_types IS NULL OR sr.relationship_type = ANY(p_relationship_types))
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions (adjust as needed)
-- GRANT ALL ON ALL TABLES IN SCHEMA public TO your_app_user;
-- GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO your_app_user;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO your_app_user;