-- Migration: Replace global code_hash unique constraint with per-document uniqueness
-- This allows the same code to exist in different sources (e.g., different versions of documentation)
-- while preventing duplicates within the same document/source

-- Drop the old global unique constraint if it exists
ALTER TABLE code_snippets DROP CONSTRAINT IF EXISTS code_snippets_code_hash_key;

-- Add composite unique constraint: unique per document (which ties to a source)
-- This ensures no duplicate code within the same document, but allows the same code
-- across different documents/sources
ALTER TABLE code_snippets ADD CONSTRAINT unique_code_per_document UNIQUE (document_id, code_hash);

-- Add an index on code_hash alone for efficient lookups during duplicate detection
CREATE INDEX IF NOT EXISTS idx_snippets_code_hash ON code_snippets(code_hash);

-- Add a comment explaining the change
COMMENT ON COLUMN code_snippets.code_hash IS 'Hash of code content for duplicate detection. Unique per document (not globally) to allow same code in different sources.';

-- Make code_hash NOT NULL if it isn't already
ALTER TABLE code_snippets ALTER COLUMN code_hash SET NOT NULL;