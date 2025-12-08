-- Migration: Add user_id columns for multi-tenancy
-- Run this migration BEFORE deploying the new code
-- user_id = NULL means system/shared data

-- ============================================================================
-- Helper function to rename owner_id to user_id or add user_id if neither exists
-- ============================================================================
CREATE OR REPLACE FUNCTION migrate_to_user_id(tbl TEXT) RETURNS VOID AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name=tbl AND column_name='owner_id') THEN
        EXECUTE format('ALTER TABLE %I RENAME COLUMN owner_id TO user_id', tbl);
        RAISE NOTICE 'Renamed owner_id to user_id in %', tbl;
    ELSIF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name=tbl AND column_name='user_id') THEN
        EXECUTE format('ALTER TABLE %I ADD COLUMN user_id UUID', tbl);
        RAISE NOTICE 'Added user_id column to %', tbl;
    ELSE
        RAISE NOTICE 'user_id already exists in %', tbl;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Page Models
-- ============================================================================

-- liste_page_recherche
SELECT migrate_to_user_id('liste_page_recherche');
CREATE INDEX IF NOT EXISTS idx_page_user ON liste_page_recherche(user_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_page_user_page ON liste_page_recherche(user_id, page_id);
ALTER TABLE liste_page_recherche DROP CONSTRAINT IF EXISTS liste_page_recherche_page_id_key;

-- suivi_page
SELECT migrate_to_user_id('suivi_page');
CREATE INDEX IF NOT EXISTS idx_suivi_user ON suivi_page(user_id);

-- suivi_page_archive
SELECT migrate_to_user_id('suivi_page_archive');

-- ============================================================================
-- Organization Models
-- ============================================================================

-- tags
SELECT migrate_to_user_id('tags');
CREATE INDEX IF NOT EXISTS idx_tag_user ON tags(user_id);
ALTER TABLE tags DROP CONSTRAINT IF EXISTS tags_name_key;
DROP INDEX IF EXISTS idx_tag_name;
CREATE UNIQUE INDEX IF NOT EXISTS idx_tag_user_name ON tags(user_id, name);

-- page_tags
SELECT migrate_to_user_id('page_tags');
CREATE INDEX IF NOT EXISTS idx_page_tag_user ON page_tags(user_id);
DROP INDEX IF EXISTS idx_page_tag_unique;
CREATE UNIQUE INDEX IF NOT EXISTS idx_page_tag_unique ON page_tags(user_id, page_id, tag_id);

-- page_notes
SELECT migrate_to_user_id('page_notes');
CREATE INDEX IF NOT EXISTS idx_page_note_user ON page_notes(user_id);

-- favorites
SELECT migrate_to_user_id('favorites');
CREATE INDEX IF NOT EXISTS idx_favorite_user ON favorites(user_id);
ALTER TABLE favorites DROP CONSTRAINT IF EXISTS favorites_page_id_key;
CREATE UNIQUE INDEX IF NOT EXISTS idx_favorite_user_page ON favorites(user_id, page_id);

-- collections
SELECT migrate_to_user_id('collections');
CREATE INDEX IF NOT EXISTS idx_collection_user ON collections(user_id);

-- collection_pages
SELECT migrate_to_user_id('collection_pages');
CREATE INDEX IF NOT EXISTS idx_collection_page_user ON collection_pages(user_id);
DROP INDEX IF EXISTS idx_collection_page_unique;
CREATE UNIQUE INDEX IF NOT EXISTS idx_collection_page_unique ON collection_pages(user_id, collection_id, page_id);

-- blacklist
SELECT migrate_to_user_id('blacklist');
CREATE INDEX IF NOT EXISTS idx_blacklist_user ON blacklist(user_id);
ALTER TABLE blacklist DROP CONSTRAINT IF EXISTS blacklist_page_id_key;
CREATE UNIQUE INDEX IF NOT EXISTS idx_blacklist_user_page ON blacklist(user_id, page_id);

-- saved_filters
SELECT migrate_to_user_id('saved_filters');
CREATE INDEX IF NOT EXISTS idx_saved_filter_user ON saved_filters(user_id);

-- scheduled_scans
SELECT migrate_to_user_id('scheduled_scans');
CREATE INDEX IF NOT EXISTS idx_scheduled_scan_user ON scheduled_scans(user_id);

-- ============================================================================
-- Search Models
-- ============================================================================

-- search_logs
SELECT migrate_to_user_id('search_logs');
CREATE INDEX IF NOT EXISTS idx_search_log_user ON search_logs(user_id);

-- page_search_history
SELECT migrate_to_user_id('page_search_history');
CREATE INDEX IF NOT EXISTS idx_page_search_history_user ON page_search_history(user_id);

-- winning_ad_search_history
SELECT migrate_to_user_id('winning_ad_search_history');
CREATE INDEX IF NOT EXISTS idx_winning_ad_search_history_user ON winning_ad_search_history(user_id);

-- search_queue
SELECT migrate_to_user_id('search_queue');
CREATE INDEX IF NOT EXISTS idx_search_queue_user ON search_queue(user_id);

-- api_call_logs
SELECT migrate_to_user_id('api_call_logs');
CREATE INDEX IF NOT EXISTS idx_api_call_user ON api_call_logs(user_id);

-- ============================================================================
-- Ads Models
-- ============================================================================

-- liste_ads_recherche
SELECT migrate_to_user_id('liste_ads_recherche');
CREATE INDEX IF NOT EXISTS idx_ads_user ON liste_ads_recherche(user_id);
CREATE INDEX IF NOT EXISTS idx_ads_user_ad ON liste_ads_recherche(user_id, ad_id);

-- winning_ads
SELECT migrate_to_user_id('winning_ads');
CREATE INDEX IF NOT EXISTS idx_winning_ads_user ON winning_ads(user_id);
ALTER TABLE winning_ads DROP CONSTRAINT IF EXISTS winning_ads_ad_id_key;
CREATE UNIQUE INDEX IF NOT EXISTS idx_winning_ads_user_ad ON winning_ads(user_id, ad_id);

-- liste_ads_recherche_archive
SELECT migrate_to_user_id('liste_ads_recherche_archive');

-- winning_ads_archive
SELECT migrate_to_user_id('winning_ads_archive');

-- ============================================================================
-- Cleanup
-- ============================================================================
DROP FUNCTION IF EXISTS migrate_to_user_id(TEXT);

-- ============================================================================
-- Done!
-- ============================================================================
-- After running this migration, existing data will have user_id = NULL
-- which means "system/shared data" accessible by all users.
--
-- To assign existing data to a specific user, run:
-- UPDATE table_name SET user_id = 'your-user-uuid' WHERE user_id IS NULL;
