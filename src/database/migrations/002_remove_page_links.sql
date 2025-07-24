-- Migration to remove the page_links table
-- This table is no longer needed as Crawl4AI handles navigation internally

-- Drop the table and all dependent objects
DROP TABLE IF EXISTS page_links CASCADE;

-- Drop any orphaned indexes (in case they weren't cascaded)
DROP INDEX IF EXISTS idx_page_links_crawl_job_id;
DROP INDEX IF EXISTS idx_page_links_depth_level;

-- Remove page_links from any views that might reference it
-- (The source_statistics view doesn't reference page_links, so we're good)

-- Log completion
DO $$
BEGIN
    RAISE NOTICE 'Migration 002_remove_page_links completed successfully';
END $$;