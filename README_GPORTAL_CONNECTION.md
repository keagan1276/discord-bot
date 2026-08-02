# Deadside GPORTAL/File Connection Update

Replace the matching files in your project. This update adds FTP, FTPS and SFTP connection fields and log downloading.

## Files to replace
- `bot.py`
- `dashboard/app.py`
- `dashboard/templates/deadside/connection.html`
- `requirements.txt` (or add `paramiko>=3.4,<4` to your existing file)

## Dashboard fields
- Protocol
- Host
- Port
- Username
- Password
- Deadside log path
- Death logs directory
- Log filename patterns
- Number of newest files to read

The password is not returned to the browser after saving. Leaving the password blank keeps the previously saved password. The bot currently stores credentials in its private Railway service filesystem; do not commit real credentials to GitHub.

## GPORTAL
Copy the FTP/SFTP credentials and paths exactly as displayed in the GPORTAL panel. Use the file-transfer port, not the game server port.
