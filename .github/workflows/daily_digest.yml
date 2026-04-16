name: Daily Tech & Gold Digest

on:
  schedule:
    # 北京时间 08:00 = UTC 00:00
    - cron: '0 0 * * *'
  # 允许手动触发，方便调试
  workflow_dispatch:

jobs:
  send-digest:
    runs-on: ubuntu-latest
    timeout-minutes: 10

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install requests feedparser

      - name: Run daily digest script
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python scripts/daily_digest.py
