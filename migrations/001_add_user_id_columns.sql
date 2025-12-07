-- Migration: Add user_id columns for multi-tenancy
-- Run this migration BEFORE deploying the new code
-- user_id = NULL means system/shared data

-- ============================================================================
-- Page Models
-- ============================================================================

-- liste_page_recherche
ALTER TABLE liste_page_recherche ADD COLUMN IF NOT EXISTS user_id UUID;
CREATE INDEX IF NOT EXISTS idx_page_user ON liste_page_recherche(user_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_page_user_page ON liste_page_recherche(user_id, page_id);
-- Remove old unique constraint on page_id (now unique per user)
ALTER TABLE liste_page_recherche DROP CONSTRAINT IF EXISTS liste_page_recherche_page_id_key;

-- suivi_page
ALTER TABLE suivi_page ADD COLUMN IF NOT EXISTS user_id UUID;
CREATE INDEX IF NOT EXISTS idx_suivi_user ON suivi_page(user_id);

-- suivi_page_archive
ALTER TABLE suivi_page_archive ADD COLUMN IF NOT EXISTS user_id UUID;

-- ============================================================================
-- Organization Models
-- ============================================================================

-- tags
ALTER TABLE tags ADD COLUMN IF NOT EXISTS user_id UUID;
CREATE INDEX IF NOT EXISTS idx_tag_user ON tags(user_id);
-- Remove old unique constraint
ALTER TABLE tags DROP CONSTRAINT IF EXISTS tags_name_key;
DROP INDEX IF EXISTS idx_tag_name;
CREATE UNIQUE INDEX IF NOT EXISTS idx_tag_user_name ON tags(user_id, name);

-- page_tags
ALTER TABLE page_tags ADD COLUMN IF NOT EXISTS user_id UUID;
CREATE INDEX IF NOT EXISTS idx_page_tag_user ON page_tags(user_id);
DROP INDEX IF EXISTS idx_page_tag_unique;
CREATE UNIQUE INDEX IF NOT EXISTS idx_page_tag_unique ON page_tags(user_id, page_id, tag_id);

-- page_notes
ALTER TABLE page_notes ADD COLUMN IF NOT EXISTS user_id UUID;
CREATE INDEX IF NOT EXISTS idx_page_note_user ON page_notes(user_id);

-- favorites
ALTER TABLE favorites ADD COLUMN IF NOT EXISTS user_id UUID;
CREATE INDEX IF NOT EXISTS idx_favorite_user ON favorites(user_id);
-- Remove old unique constraint
ALTER TABLE favorites DROP CONSTRAINT IF EXISTS favorites_page_id_key;
CREATE UNIQUE INDEX IF NOT EXISTS idx_favorite_user_page ON favorites(user_id, page_id);

-- collections
ALTER TABLE collections ADD COLUMN IF NOT EXISTS user_id UUID;
CREATE INDEX IF NOT EXISTS idx_collection_user ON collections(user_id);

-- collection_pages
ALTER TABLE collection_pages ADD COLUMN IF NOT EXISTS user_id UUID;
CREATE INDEX IF NOT EXISTS idx_collection_page_user ON collection_pages(user_id);
DROP INDEX IF EXISTS idx_collection_page_unique;
CREATE UNIQUE INDEX IF NOT EXISTS idx_collection_page_unique ON collection_pages(user_id, collection_id, page_id);

-- blacklist
ALTER TABLE blacklist ADD COLUMN IF NOT EXISTS user_id UUID;
CREATE INDEX IF NOT EXISTS idx_blacklist_user ON blacklist(user_id);
-- Remove old unique constraint
ALTER TABLE blacklist DROP CONSTRAINT IF EXISTS blacklist_page_id_key;
CREATE UNIQUE INDEX IF NOT EXISTS idx_blacklist_user_page ON blacklist(user_id, page_id);

-- saved_filters
ALTER TABLE saved_filters ADD COLUMN IF NOT EXISTS user_id UUID;
CREATE INDEX IF NOT EXISTS idx_saved_filter_user ON saved_filters(user_id);

-- scheduled_scans
ALTER TABLE scheduled_scans ADD COLUMN IF NOT EXISTS user_id UUID;
CREATE INDEX IF NOT EXISTS idx_scheduled_scan_user ON scheduled_scans(user_id);

-- ============================================================================
-- Search Models
-- ============================================================================

-- search_logs
ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS user_id UUID;
CREATE INDEX IF NOT EXISTS idx_search_log_user ON search_logs(user_id);

-- page_search_history
ALTER TABLE page_search_history ADD COLUMN IF NOT EXISTS user_id UUID;
CREATE INDEX IF NOT EXISTS idx_page_search_history_user ON page_search_history(user_id);

-- winning_ad_search_history
ALTER TABLE winning_ad_search_history ADD COLUMN IF NOT EXISTS user_id UUID;
CREATE INDEX IF NOT EXISTS idx_winning_ad_search_history_user ON winning_ad_search_history(user_id);

-- search_queue
ALTER TABLE search_queue ADD COLUMN IF NOT EXISTS user_id UUID;
CREATE INDEX IF NOT EXISTS idx_search_queue_user ON search_queue(user_id);

-- api_call_logs
ALTER TABLE api_call_logs ADD COLUMN IF NOT EXISTS user_id UUID;
CREATE INDEX IF NOT EXISTS idx_api_call_user ON api_call_logs(user_id);

-- ============================================================================
-- Ads Models
-- ============================================================================

-- liste_ads_recherche
ALTER TABLE liste_ads_recherche ADD COLUMN IF NOT EXISTS user_id UUID;
CREATE INDEX IF NOT EXISTS idx_ads_user ON liste_ads_recherche(user_id);
CREATE INDEX IF NOT EXISTS idx_ads_user_ad ON liste_ads_recherche(user_id, ad_id);

-- winning_ads
ALTER TABLE winning_ads ADD COLUMN IF NOT EXISTS user_id UUID;
CREATE INDEX IF NOT EXISTS idx_winning_ads_user ON winning_ads(user_id);
-- Remove old unique constraint
ALTER TABLE winning_ads DROP CONSTRAINT IF EXISTS winning_ads_ad_id_key;
CREATE UNIQUE INDEX IF NOT EXISTS idx_winning_ads_user_ad ON winning_ads(user_id, ad_id);

-- liste_ads_recherche_archive
ALTER TABLE liste_ads_recherche_archive ADD COLUMN IF NOT EXISTS user_id UUID;

-- winning_ads_archive
ALTER TABLE winning_ads_archive ADD COLUMN IF NOT EXISTS user_id UUID;

-- ============================================================================
-- Done!
-- ============================================================================
-- After running this migration, existing data will have user_id = NULL
-- which means "system/shared data" accessible by all users.
--
-- To assign existing data to a specific user, run:
-- UPDATE table_name SET user_id = 'your-user-uuid' WHERE user_id IS NULL;
