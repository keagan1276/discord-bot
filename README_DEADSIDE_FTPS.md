# GPORTAL Deadside FTPS-only update

Replace these files in your project:

- bot.py
- dashboard/app.py
- dashboard/templates/deadside/connection.html

This version limits the Deadside connector to GPORTAL FTPS and provides:

- Protocol fixed to FTPS explicit TLS
- Host
- Port
- Username
- Password
- Server IP
- Deadside log path
- Death logs directory
- File patterns
- Poll interval
- Number of recent files to read

The saved password is preserved when the password field is left blank.
