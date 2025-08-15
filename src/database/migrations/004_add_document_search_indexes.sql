-- Migration: Add document search indexes for improved performance
-- Date: 2025-01-15
-- Purpose: Add missing indexes on documents table for title and URL searching

-- Add regular B-tree index on title for exact/prefix matches
CREATE INDEX IF NOT EXISTS idx_documents_title ON documents(title);

-- Add trigram indexes for fuzzy search performance
-- These indexes support ILIKE queries and similarity searches
CREATE INDEX IF NOT EXISTS idx_documents_title_trgm ON documents USING GIN(title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_documents_url_trgm ON documents USING GIN(url gin_trgm_ops);

-- Note: pg_trgm extension must be enabled (already done in schema.sql)