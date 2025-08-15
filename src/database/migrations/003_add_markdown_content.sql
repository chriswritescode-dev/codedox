-- Migration: Add markdown_content column to documents table
-- Purpose: Store full page markdown for future re-extraction and analysis
-- Date: 2025-08-15

-- Add the markdown_content column to store full page content
ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS markdown_content TEXT;

-- Add comment to document the column purpose
COMMENT ON COLUMN documents.markdown_content IS 'Full markdown content of the document for re-extraction and analysis';

-- This column will store the complete markdown content from crawled pages
-- Benefits:
-- 1. Enables re-extraction without re-crawling
-- 2. Allows full-text search on complete document content
-- 3. Useful for debugging and content analysis
-- 4. Preserves original content for future processing improvements

-- Log completion
DO $$
BEGIN
    RAISE NOTICE 'Migration 003_add_markdown_content completed successfully';
END $$;