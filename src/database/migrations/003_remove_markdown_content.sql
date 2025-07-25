-- Migration: Remove markdown_content column from documents table
-- Purpose: We only need content_hash for change detection, not the full content
-- Date: 2025-07-25

-- Drop the markdown_content column
ALTER TABLE documents 
DROP COLUMN IF EXISTS markdown_content;

-- Update the source_statistics view to not reference markdown_content
-- (The view doesn't actually use markdown_content, so no changes needed)

-- Note: content_hash column is retained for change detection
-- This migration is safe to run multiple times due to IF EXISTS clause