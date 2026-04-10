#!/usr/bin/env bash
# Usage: ./notify_telegram.sh "message text"
# Env vars required: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

set -euo pipefail

MESSAGE="${1:?Usage: notify_telegram.sh MESSAGE}"
BOT_TOKEN="${TELEGRAM_BOT_TOKEN:?TELEGRAM_BOT_TOKEN not set}"
CHAT_ID="${TELEGRAM_CHAT_ID:?TELEGRAM_CHAT_ID not set}"

curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
  -H "Content-Type: application/json" \
  -d "$(jq -n \
    --arg chat_id "$CHAT_ID" \
    --arg text "$MESSAGE" \
    --arg parse_mode "Markdown" \
    '{chat_id: $chat_id, text: $text, parse_mode: $parse_mode}'
  )" > /dev/null

echo "Telegram notification sent."
