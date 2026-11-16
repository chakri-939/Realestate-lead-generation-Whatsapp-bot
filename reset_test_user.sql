-- Database Cleanup Script for Testing
-- Run this script to completely wipe a phone number's history and state.
-- This simulates a brand-new user starting their very first interaction.

-- 1. Reset user state back to NORMAL (or wipe it to trigger fallback flow)
DELETE FROM user_states WHERE phone_number = 'YOUR_TEST_PHONE_NUMBER';

-- 2. Clear conversation memory (forces Yara to re-introduce herself and ask for consent)
DELETE FROM ai_responses WHERE phone_number = 'YOUR_TEST_PHONE_NUMBER';

-- 3. Clear any existing qualification entries
DELETE FROM lead_qualification WHERE phone_number = 'YOUR_TEST_PHONE_NUMBER';

-- 4. Clear raw webhook message logs (will cascade delete voice_transcriptions)
DELETE FROM incoming_messages WHERE phone_number = 'YOUR_TEST_PHONE_NUMBER';

-- 5. Clear security events log
DELETE FROM security_events WHERE phone_number = 'YOUR_TEST_PHONE_NUMBER';


