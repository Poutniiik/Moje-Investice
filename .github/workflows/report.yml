name: Denní Report Portfolia

on:
  schedule:
    # 6:00, 16:00, 22:00 (v našem čase)
    - cron: '0 5,15,21 * * 1-5'
  workflow_dispatch:

# Dáváme robotovi právo zapisovat do souborů (Commit & Push)
permissions:
  contents: write

jobs:
  run-report:
    runs-on: ubuntu-latest

    steps:
    - name: Checkout code
      uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'

    - name: Install dependencies
      # OPRAVA: Instalace všech závislostí včetně PyGithub a matplotlib
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt

    - name: Run Robot
      env:
        TELEGRAM_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
        TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        # Token pro stahování a nahrávání dat
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      run: python daily_bot.py

    # Uložíme změny v CSV (Historie) a JSON (Cache) zpět na GitHub
    - name: Commit and Push changes
      run: |
        git config --global user.name 'Investicni Robot'
        git config --global user.email 'robot@github.com'
        # Přidáme soubory, pokud existují/změnily se
        git add value_history.csv || echo "value_history.csv nenalezen"
        git add market_cache.json || echo "market_cache.json nenalezen"
        # Zkusíme commitnout, pokud nejsou změny, nevadí (|| exit 0)
        git commit -m "💾 Auto-save: Historie a Cache" || exit 0
        git push
