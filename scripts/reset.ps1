# ==============================================================================
# Bilingual WhatsApp Lead Gen System - Demo Reset Script
# ==============================================================================
# Syntax: PowerShell automation script to reset DB state & restart n8n container.
# Connectivity: Executes psql inside 'whatsapp_postgres' and restarts 'whatsapp_n8n'.
# ==============================================================================

Param (
    [string]$PhoneNumber = ""
)

# Load environment variables from .env file
if (Test-Path ".env") {
    Get-Content .env | ForEach-Object {
        if ($_ -match "^\s*([^#=]+)=(['""]?)(.*)\2\s*$") {
            $name = $matches[1].Trim()
            $value = $matches[3].Trim()
            [System.Environment]::SetEnvironmentVariable($name, $value, [System.EnvironmentVariableTarget]::Process)
        }
    }
}

$dbUser = $env:POSTGRES_USER
if (-not $dbUser -or $dbUser -eq "n8n_admin") { $dbUser = "postgres_admin" }
$appDbName = "whatsapp_lead_db"

Write-Host "`n🧹 [RESET] Preparing workspace reset for video recording..." -ForegroundColor Cyan

if ($PhoneNumber -ne "") {
    Write-Host "🎯 Target Phone Number: $PhoneNumber" -ForegroundColor Yellow
    $sql = @"
DO `$$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'user_states') THEN
        DELETE FROM user_states WHERE phone_number = '$PhoneNumber';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'ai_responses') THEN
        DELETE FROM ai_responses WHERE phone_number = '$PhoneNumber';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'lead_qualification') THEN
        DELETE FROM lead_qualification WHERE phone_number = '$PhoneNumber';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'incoming_messages') THEN
        DELETE FROM incoming_messages WHERE phone_number = '$PhoneNumber';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'security_events') THEN
        DELETE FROM security_events WHERE phone_number = '$PhoneNumber';
    END IF;
END `$$;
"@
} else {
    Write-Host "⚠️ No phone number specified. Wiping ALL test tables completely..." -ForegroundColor Red
    $sql = @"
DO `$$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'user_states') THEN
        TRUNCATE TABLE user_states CASCADE;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'ai_responses') THEN
        TRUNCATE TABLE ai_responses CASCADE;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'lead_qualification') THEN
        TRUNCATE TABLE lead_qualification CASCADE;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'incoming_messages') THEN
        TRUNCATE TABLE incoming_messages CASCADE;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'security_events') THEN
        TRUNCATE TABLE security_events CASCADE;
    END IF;
END `$$;
"@
}

# Execute SQL in postgres container against application database
Write-Host "Executing database wipe in PostgreSQL container..." -ForegroundColor Gray
$sql | docker exec -i whatsapp_postgres psql -U $dbUser -d $appDbName

# Restart n8n container to clear transient node state/memory
Write-Host "Restarting n8n container to reset buffer memory..." -ForegroundColor Gray
docker restart whatsapp_n8n | Out-Null

Write-Host "[SUCCESS] Database state and n8n memory cleared!" -ForegroundColor Green
Write-Host "Next Steps for Video Recording:" -ForegroundColor Yellow
Write-Host "   1. Open Google Sheets CRM and delete any test rows from 'Lead Pipeline' and 'Handoff Queue'."
Write-Host "   2. Send a new message from WhatsApp to start a fresh lead conversation." -ForegroundColor Yellow



