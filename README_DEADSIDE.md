# Deadside killfeed module

Replace your bot service `bot.py` and dashboard service `dashboard/app.py`, `dashboard/templates/base.html`, and add `dashboard/templates/deadside.html`.

This first connector accepts an HTTP(S) endpoint containing either JSON kill events or plain-text logs. The bot polls each Discord guild independently and stores seen event IDs to prevent duplicates. Existing events are remembered on the first poll and are not posted, preventing a historical flood.

## JSON format
```json
[{"id":"unique-id","killer":"Player A","victim":"Player B","weapon":"AKM","distance":187,"headshot":true}]
```
Or `{ "events": [...] }`.

## Important
Your hosting provider must expose logs through an HTTP(S) endpoint or you must run a small bridge that exposes the log file in this format. FTP/SFTP provider adapters are the next connector layer and require provider-specific details.
