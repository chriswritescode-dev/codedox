-- Add full-text search support for markdown content in documents table

-- Add search vector column for markdown content
ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS markdown_search_vector tsvector;

-- Create GIN index for fast full-text search
CREATE INDEX IF NOT EXISTS idx_documents_markdown_search 
ON documents USING GIN(markdown_search_vector);

-- Function to update markdown search vector
CREATE OR REPLACE FUNCTION update_markdown_search_vector() 
RETURNS trigger AS $$
BEGIN
    -- Only update if markdown_content is not null
    IF NEW.markdown_content IS NOT NULL THEN
        NEW.markdown_search_vector := 
            setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
            setweight(to_tsvector('english', COALESCE(NEW.markdown_content, '')), 'B');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to automatically update search vector on insert/update
DROP TRIGGER IF EXISTS trigger_update_markdown_search_vector ON documents;
CREATE TRIGGER trigger_update_markdown_search_vector
BEFORE INSERT OR UPDATE OF title, markdown_content ON documents
FOR EACH ROW
EXECUTE FUNCTION update_markdown_search_vector();

-- Update existing documents to populate search vectors
UPDATE documents 
SET markdown_search_vector = 
    setweight(to_tsvector('english', COALESCE(title, '')), 'A') ||
    setweight(to_tsvector('english', COALESCE(markdown_content, '')), 'B')
WHERE markdown_content IS NOT NULL;

-- Add function to search markdown with context extraction
CREATE OR REPLACE FUNCTION search_markdown_with_context(
    doc_url TEXT,
    search_query TEXT,
    max_excerpts INTEGER DEFAULT 5,
    excerpt_length INTEGER DEFAULT 200
) RETURNS TABLE (
    excerpt TEXT,
    rank REAL,
    headline TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH doc AS (
        SELECT id, markdown_content, markdown_search_vector
        FROM documents
        WHERE url = doc_url
        LIMIT 1
    )
    SELECT 
        -- Extract excerpt around match
        ts_headline(
            'english',
            d.markdown_content,
            plainto_tsquery('english', search_query),
            'MaxWords=' || excerpt_length || ', MinWords=50, StartSel=<<<, StopSel=>>>, MaxFragments=1'
        ) as excerpt,
        -- Calculate relevance rank
        ts_rank(d.markdown_search_vector, plainto_tsquery('english', search_query)) as rank,
        -- Get highlighted version for display
        ts_headline(
            'english', 
            d.markdown_content,
            plainto_tsquery('english', search_query),
            'MaxWords=50, MinWords=20, StartSel=****, StopSel=****, MaxFragments=3'
        ) as headline
    FROM doc d
    WHERE d.markdown_search_vector @@ plainto_tsquery('english', search_query)
    ORDER BY rank DESC
    LIMIT max_excerpts;
END;
$$ LANGUAGE plpgsql;

-- Add function to get markdown sections containing search term
CREATE OR REPLACE FUNCTION get_markdown_sections_by_search(
    doc_url TEXT,
    search_query TEXT,
    max_tokens INTEGER DEFAULT 2048
) RETURNS TEXT AS $$
DECLARE
    result TEXT := '';
    current_section TEXT;
    current_tokens INTEGER := 0;
    section_tokens INTEGER;
    total_sections INTEGER := 0;
    matched_sections INTEGER := 0;
BEGIN
    -- Get document content
    FOR current_section IN
        SELECT 
            regexp_split_to_table(markdown_content, E'\\n(?=#+ )') as section
        FROM documents
        WHERE url = doc_url
    LOOP
        -- Check if section contains search query
        IF search_query IS NULL OR current_section ILIKE '%' || search_query || '%' THEN
            matched_sections := matched_sections + 1;
            
            -- Estimate tokens (rough: 1 token per 4 chars)
            section_tokens := LENGTH(current_section) / 4;
            
            -- Check if adding this section would exceed limit
            IF current_tokens + section_tokens <= max_tokens THEN
                IF result != '' THEN
                    result := result || E'\n\n';
                END IF;
                result := result || current_section;
                current_tokens := current_tokens + section_tokens;
            ELSE
                -- Add truncation notice
                IF current_tokens = 0 THEN
                    -- First section is too large, truncate it
                    result := LEFT(current_section, max_tokens * 4) || E'\n\n[Section truncated to fit token limit...]';
                ELSE
                    -- We've hit the limit
                    result := result || E'\n\n[' || (matched_sections - total_sections) || ' more matching sections omitted due to token limit]';
                END IF;
                EXIT;
            END IF;
            
            total_sections := total_sections + 1;
        END IF;
    END LOOP;
    
    -- Return empty string if no matches
    IF result = '' AND search_query IS NOT NULL THEN
        -- No sections matched, do a simple excerpt search
        SELECT ts_headline(
            'english',
            markdown_content,
            plainto_tsquery('english', search_query),
            'MaxWords=' || (max_tokens / 2) || ', MinWords=100, StartSel=, StopSel=, MaxFragments=5'
        ) INTO result
        FROM documents
        WHERE url = doc_url
        AND markdown_search_vector @@ plainto_tsquery('english', search_query);
    END IF;
    
    RETURN COALESCE(result, '');
END;
$$ LANGUAGE plpgsql;

-- Add comments for documentation
COMMENT ON COLUMN documents.markdown_search_vector IS 'Full-text search vector for markdown content';
COMMENT ON FUNCTION search_markdown_with_context IS 'Search markdown content and return excerpts with context';
COMMENT ON FUNCTION get_markdown_sections_by_search IS 'Get markdown sections containing search query within token limit';