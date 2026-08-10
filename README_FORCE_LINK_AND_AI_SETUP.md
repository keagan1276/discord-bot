# Pirate AI Setup Helper + /force link

Replace:
- bot.py

New admin command:
- /force link

Examples:
- /force link game:Deadside member:@Jack gamertag:PirateJack
- /force link game:DayZ member:@Jack gamertag:PirateJack
- /force link game:DayZ member:@Jack gamertag:PirateJack guid:DAYZ-GUID-HERE

Permissions:
- Administrator only.

Force-link behavior:
- Replaces the selected member's old link.
- If another Discord member already has the same gamertag, the duplicate link is removed.
- For DayZ, a duplicate GUID is also removed from another account.
- Records that the link was force-created and which administrator performed it.

Pirate AI changes:
The helper can now answer setup/troubleshooting questions such as:
- Pirate how do I set up the bot?
- Pirate why can't I manage my server?
- Pirate how do I set up Deadside?
- Pirate what do I need for DayZ?
- Pirate why aren't my channels loading?
- Pirate what Railway variables do I need?
- Pirate why am I getting Internal Server Error?
- Pirate how do I link a player as admin?

Railway:
Keep OPENAI_API_KEY configured on the BOT service.
