# Snippet Count Fix Summary

## Issue
The snippet count was showing inconsistent numbers during crawling - displaying much higher counts while processing and then dropping to half when finishing. This was caused by multiple sources of truth for counting snippets and inconsistent handling of existing snippets when reusing jobs.

## Root Causes
1. **Multiple counting locations**: Snippets were counted in page_crawler, result_processor, and job_manager with different logic
2. **Existing snippets not handled properly**: When reusing a job, existing snippets weren't consistently included in counts
3. **Unchanged content returned 0**: When content was unchanged, the result processor returned 0 instead of the existing snippet count

## Changes Made

### 1. job_manager.py
- Added `[SNIPPET_COUNT]` logging to track snippet count changes
- Store `base_snippet_count` in job config when reusing existing jobs
- Log when updating snippet counts to track changes

### 2. result_processor.py  
- Fixed to return existing snippet count when content is unchanged (instead of 0)
- Added `[SNIPPET_COUNT]` logging for debugging

### 3. crawl_manager.py
- Track base snippet count at start of crawl
- Properly accumulate snippets starting from base count
- Added extensive `[SNIPPET_COUNT]` logging to track accumulation

### 4. page_crawler.py
- Removed duplicate snippet counting logic
- Simplified to only track progress for UI updates
- Removed `snippet_count` from `crawl_progress` dict

### 5. progress_tracker.py
- Added `[WEBSOCKET]` logging for debugging WebSocket issues
- Special logging for 403 errors that might indicate auth issues

## How It Works Now
1. When reusing a job, the existing snippet count is stored as `base_snippet_count`
2. During crawling, snippets are accumulated starting from the base count
3. The result processor always returns the actual snippet count (new or existing)
4. The job manager's `snippets_extracted` field is the single source of truth
5. All count updates are logged with `[SNIPPET_COUNT]` prefix for debugging

## Testing
To test the fixes:
1. Run a crawl on a source that already has snippets
2. Watch for `[SNIPPET_COUNT]` log entries
3. Verify the final count matches base + new snippets
4. Check for any `[WEBSOCKET]` 403 errors

## Temporary Logging
The `[SNIPPET_COUNT]` and `[WEBSOCKET]` logging prefixes are temporary for debugging and can be removed once the issue is confirmed fixed.