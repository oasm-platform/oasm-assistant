-- Enable pgvector extension if not exists
CREATE EXTENSION IF NOT EXISTS vector;

-- Check if the extension was created successfully
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        RAISE EXCEPTION 'Failed to create pgvector extension';
    END IF;
    
    RAISE NOTICE 'pgvector extension is ready to use';
END $$;
