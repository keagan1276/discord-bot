# Pirates Bot — Deadside top-tab dashboard

Replace the matching files in your project:

- `bot.py`
- `dashboard/app.py`
- `dashboard/templates/base.html`
- `dashboard/static/css/dashboard-system.css`
- `dashboard/static/js/dashboard-system.js`
- add `dashboard/templates/integrations.html`
- add the complete `dashboard/templates/deadside/` folder

## Navigation

The sidebar now contains one `Game Integrations` entry. Deadside uses top tabs:

- Overview
- Connection
- Channels
- Killfeed
- Leaderboards
- Statistics
- Advanced

## Current Deadside connector

The first connector reads an HTTP(S) endpoint that returns either:

- a JSON list of kill objects,
- `{ "events": [...] }`, or
- plain-text log lines parsed by the configured regex.

## Required Discord channels

Before enabling and saving the integration, select:

- Killfeed channel
- Leaderboard channel, unless automatic leaderboards are disabled

## Deploy

```bat
python -m py_compile bot.py
python -m py_compile dashboard\app.py
git add .
git commit -m "Add Deadside top tab dashboard"
git push origin main
```
