-- Create incoming_messages table (logs all text and audio inputs)
CREATE TABLE IF NOT EXISTS incoming_messages (
    id SERIAL PRIMARY KEY,
    phone_number VARCHAR(20) NOT NULL,
    message_id VARCHAR(100) UNIQUE NOT NULL,
    message_type VARCHAR(20) NOT NULL,
    raw_payload JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create voice_transcriptions table (logs Whisper and Cleanup results)
CREATE TABLE IF NOT EXISTS voice_transcriptions (
    id SERIAL PRIMARY KEY,
    message_id VARCHAR(100) REFERENCES incoming_messages(message_id) ON DELETE CASCADE,
    raw_transcript TEXT NOT NULL,
    cleaned_transcript TEXT NOT NULL,
    duration_seconds INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create ai_responses table (logs Yara's replies and token usage)
CREATE TABLE IF NOT EXISTS ai_responses (
    id SERIAL PRIMARY KEY,
    phone_number VARCHAR(20) NOT NULL,
    user_message TEXT NOT NULL,
    ai_response TEXT NOT NULL,
    tokens_used INT DEFAULT 0,
    routing_flag VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create security_events table (logs Layer 1 blocks with hashed phone numbers for privacy)
CREATE TABLE IF NOT EXISTS security_events (
    id SERIAL PRIMARY KEY,
    phone_number VARCHAR(20) NOT NULL,
    phone_hash VARCHAR(64),
    violating_input TEXT NOT NULL,
    violation_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create lead_qualification table (stores final structured CRM-ready lead data)
CREATE TABLE IF NOT EXISTS lead_qualification (
    id SERIAL PRIMARY KEY,
    phone_number VARCHAR(20) UNIQUE NOT NULL,
    full_name VARCHAR(100),
    intent VARCHAR(20),
    property_type VARCHAR(20),
    budget_range VARCHAR(50),
    preferred_location VARCHAR(100),
    timeline VARCHAR(50),
    financing_status VARCHAR(50),
    visa_interest BOOLEAN DEFAULT FALSE,
    lead_score VARCHAR(10) NOT NULL,
    consent_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create user_states table to track handoff and delete states
CREATE TABLE IF NOT EXISTS user_states (
    phone_number VARCHAR(20) PRIMARY KEY,
    current_state VARCHAR(30) NOT NULL DEFAULT 'NORMAL',
    metadata JSONB DEFAULT '{}',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==============================================================================
-- DATABASE INDEXES (B-Tree Optimization for Fast Lookups)
-- ==============================================================================
-- 1. Index incoming messages by phone & timestamp for fast rate-limiting & history lookups
CREATE INDEX IF NOT EXISTS idx_incoming_phone_created ON incoming_messages (phone_number, created_at DESC);

-- 2. Index AI responses by phone & timestamp for memory buffer retrieval
CREATE INDEX IF NOT EXISTS idx_ai_responses_phone_created ON ai_responses (phone_number, created_at DESC);

-- 3. Index security events by phone hash & timestamp for incident analysis
CREATE INDEX IF NOT EXISTS idx_security_events_phone_hash ON security_events (phone_hash, created_at DESC);

-- 4. Index lead qualification by phone number for deduplication check
CREATE INDEX IF NOT EXISTS idx_lead_qualification_phone ON lead_qualification (phone_number);


