# Deadside GPORTAL + Admin Logs update

Replace the included files in your project.

## Added
- FTP, FTPS and SFTP host, port, username and password
- Separate game server IP, game port, query port and RCON port
- Deadside base log path and death-log directory
- Separate admin-log directory and filename patterns
- Admin Discord feed for item spawns, vehicle spawns, teleports, kicks, bans and god-mode changes
- Duplicate protection for admin events

## Important
The server IP/game port are not used to log in to FTP/SFTP. Use the separate file-access host and port shown by your provider.

Admin events can only be reported when the hosting provider writes those actions to an accessible log file. The parser is intentionally generic because log formats vary by provider and Deadside version.
