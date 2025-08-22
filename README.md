# Weatherboy - Automated NWS alerts sent to Discord
Created by me as a fun way to track and share active weather alerts sent by the National Weather Service to my friends.

## Setup
- You must use a .env file to store your Discord API key, message channel ID, and a contact email as a User-Agent for the API.
- Python version 3.12 and up.

### .env format
DISCORD_TOKEN=token  
CHANNEL_ID=id  
USER=contact

## Features
- Location tracking
- Almost real-time alert tracking. Faster with less locations.
- Alert count status updates on bot profile.
- *Awesome* message formatting
- Differentiates between the different severity levels of tornado warnings (warning, PDS warning, emergency)

## Commands
!ping - pings bot  
!info - displays info page  
!changelog - shows most recent changes  
!alerts - shows all active alerts.  
!forcequit - automatically kills bot execution; if something goes wrong.  
