# Pirates Bot AI Helper

Replace:
- bot.py

Keep/add:
- assets/help/pirates_bot_help.png

Railway BOT service variables:
- OPENAI_API_KEY = your OpenAI project API key
- PIRATE_AI_MODEL = gpt-5-mini (optional)
- PIRATE_AI_COOLDOWN = 8 (optional)
- PIRATE_AI_CHANNEL_IDS = comma-separated Discord channel IDs (optional)

Examples:
- Pirate what command checks my balance?
- Pirate how do I play blackjack?
- Pirate how do I link my Deadside account?
- Pirate how do I see my DayZ coordinates?
- Pirate what command buys from the DayZ shop?
- Pirate how do I access the dashboard?

The helper:
- only responds when the message starts with `Pirate`
- ignores bot users through the existing on_message guard
- uses current registered slash commands as extra context
- is told not to invent commands
- has an 8 second per-user cooldown by default
- can be restricted to selected channels
- falls back to built-in command help if OpenAI is unavailable
- uses the OpenAI Responses API with store:false
- needs no new Python package because it uses urllib already present in bot.py
