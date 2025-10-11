-- Performance optimization indexes for playback_events table
-- Created as part of code analysis improvements

-- Index for users cache service playback activity query
-- Optimizes GROUP BY (server_id, username, provider_user_id) with date filtering
CREATE INDEX IF NOT EXISTS idx_playback_events_server_username_date
ON playback_events(server_id, username, started_at DESC)
WHERE username IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_playback_events_server_provider_date
ON playback_events(server_id, provider_user_id, started_at DESC)
WHERE provider_user_id IS NOT NULL;

-- Index for analytics queries that filter by date and group by media
CREATE INDEX IF NOT EXISTS idx_playback_events_started_at
ON playback_events(started_at DESC);

-- Index for top libraries analytics
CREATE INDEX IF NOT EXISTS idx_playback_events_library_section
ON playback_events(library_section, started_at DESC)
WHERE library_section IS NOT NULL AND library_section != 'Unknown Library';

-- Composite index for common analytics filters
CREATE INDEX IF NOT EXISTS idx_playback_events_server_date_type
ON playback_events(server_id, started_at DESC, media_type)
WHERE media_type IS NOT NULL;
