-- Add snippet_relationships table for proper relationship modeling
-- This replaces the related_snippets array and relationships stored in JSONB

-- Create the relationships table
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

-- Create a view for easy querying of relationships
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

-- Enhanced search function that includes related snippets
CREATE OR REPLACE FUNCTION search_with_relationships(
    p_query TEXT,
    p_source TEXT DEFAULT NULL,
    p_language TEXT DEFAULT NULL,
    p_job_id UUID DEFAULT NULL,
    p_limit INTEGER DEFAULT 20,
    p_include_related BOOLEAN DEFAULT TRUE
)
RETURNS TABLE (
    id INTEGER,
    title TEXT,
    description TEXT,
    language VARCHAR(50),
    code_content TEXT,
    source_url TEXT,
    rank REAL,
    is_primary_result BOOLEAN,
    relationship_context JSONB
) AS $$
DECLARE
    primary_ids INTEGER[];
    total_primary INTEGER;
    related_limit INTEGER;
BEGIN
    -- First get primary search results
    WITH primary_results AS (
        SELECT 
            cs.id,
            cs.title,
            cs.description,
            cs.language,
            cs.code_content,
            cs.source_url,
            ts_rank(cs.search_vector, plainto_tsquery(p_query)) as rank
        FROM code_snippets cs
        JOIN documents d ON cs.document_id = d.id
        JOIN crawl_jobs cj ON d.crawl_job_id = cj.id
        WHERE 
            cs.search_vector @@ plainto_tsquery(p_query)
            AND cj.status != 'cancelled'
            AND (p_job_id IS NULL OR d.crawl_job_id = p_job_id)
            AND (p_source IS NULL OR cj.name = p_source)
            AND (p_language IS NULL OR cs.language = p_language)
        ORDER BY rank DESC
        LIMIT p_limit
    )
    SELECT array_agg(id), COUNT(*) 
    INTO primary_ids, total_primary
    FROM primary_results;
    
    -- Return primary results
    RETURN QUERY
    SELECT 
        pr.id,
        pr.title,
        pr.description,
        pr.language,
        pr.code_content,
        pr.source_url,
        pr.rank,
        TRUE as is_primary_result,
        NULL::JSONB as relationship_context
    FROM primary_results pr;
    
    -- If requested and we have room, add related snippets
    IF p_include_related AND total_primary < p_limit THEN
        related_limit := p_limit - total_primary;
        
        RETURN QUERY
        WITH related_info AS (
            SELECT 
                rel.related_snippet_id,
                jsonb_agg(jsonb_build_object(
                    'primary_snippet_id', rel.snippet_id,
                    'primary_snippet_title', ps.title,
                    'relationship_type', rel.relationship_type,
                    'description', rel.description
                )) as contexts
            FROM find_related_snippets(primary_ids, NULL, related_limit * 2) rel
            JOIN code_snippets ps ON rel.snippet_id = ps.id
            WHERE rel.related_snippet_id NOT IN (SELECT unnest(primary_ids))
            GROUP BY rel.related_snippet_id
        )
        SELECT DISTINCT
            cs.id,
            cs.title,
            cs.description,
            cs.language,
            cs.code_content,
            cs.source_url,
            0.0 as rank,
            FALSE as is_primary_result,
            ri.contexts as relationship_context
        FROM related_info ri
        JOIN code_snippets cs ON ri.related_snippet_id = cs.id
        JOIN documents d ON cs.document_id = d.id
        JOIN crawl_jobs cj ON d.crawl_job_id = cj.id
        WHERE 
            cj.status != 'cancelled'
            AND (p_job_id IS NULL OR d.crawl_job_id = p_job_id)
            AND (p_language IS NULL OR cs.language = p_language)
        LIMIT related_limit;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Migration helper: Convert existing relationships from JSONB to relational table
-- This should be run once after creating the new table
DO $$
DECLARE
    snippet RECORD;
    relationship JSONB;
    doc_snippets INTEGER[];
    target_idx INTEGER;
    target_id INTEGER;
BEGIN
    -- Loop through all snippets with relationships in metadata
    FOR snippet IN 
        SELECT id, document_id, meta_data
        FROM code_snippets 
        WHERE meta_data ? 'relationships' 
        AND jsonb_array_length(meta_data->'relationships') > 0
    LOOP
        -- Get all snippet IDs from the same document in order
        SELECT array_agg(id ORDER BY id)
        INTO doc_snippets
        FROM code_snippets
        WHERE document_id = snippet.document_id;
        
        -- Process each relationship
        FOR relationship IN SELECT * FROM jsonb_array_elements(snippet.meta_data->'relationships')
        LOOP
            -- Get the target index
            target_idx := (relationship->>'related_index')::INTEGER;
            
            -- Convert index to snippet ID (1-based index)
            IF target_idx >= 0 AND target_idx < array_length(doc_snippets, 1) THEN
                target_id := doc_snippets[target_idx + 1];
                
                -- Insert the relationship (ignore duplicates)
                INSERT INTO snippet_relationships (
                    source_snippet_id,
                    target_snippet_id,
                    relationship_type,
                    description
                ) VALUES (
                    snippet.id,
                    target_id,
                    COALESCE(relationship->>'relationship_type', 'related'),
                    relationship->>'description'
                ) ON CONFLICT DO NOTHING;
            END IF;
        END LOOP;
    END LOOP;
END $$;

-- Optional: After verifying the migration worked, you can remove the relationships from meta_data
-- UPDATE code_snippets SET meta_data = meta_data - 'relationships' WHERE meta_data ? 'relationships';