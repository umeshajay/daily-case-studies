# Daily Business Case Studies

Sends a curated business case study from top universities (Harvard, MIT, Stanford, Wharton, Kellogg, etc.) to your Telegram every morning at 9 AM.

## Setup

### 1. Get Telegram credentials
- Open Telegram, search `@BotFather`, send `/newbot`, and save the token
- Start a chat with your bot, send a message, then visit:
  `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
- Copy your `chat_id` from the response

### 2. Push to GitHub
```bash
echo "# daily-case-studies" >> README.md
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USER/daily-case-studies.git
git push -u origin main
```

### 3. Add GitHub Secrets
Go to your repo → **Settings → Secrets and variables → Actions** and add:
- `TELEGRAM_BOT_TOKEN` — your bot token
- `TELEGRAM_CHAT_ID` — your chat ID

### 4. Enable the workflow
Go to the **Actions** tab — the workflow `Daily Case Study` will run automatically at 9 AM daily (UTC+5:30). You can also trigger it manually with the "Run workflow" button.

## Test manually
```bash
pip install -r requirements.txt
TELEGRAM_BOT_TOKEN=your_token TELEGRAM_CHAT_ID=your_id python send_case_study.py
```
