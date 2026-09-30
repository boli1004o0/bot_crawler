# 591 Rent Bot

Discord bot that checks the newest 10 Zhu-Nan rental listings on 591 and sends qualifying listings to a channel.

## Discord commands

- `/status` shows the current monitor state and filters.
- `/pause` stops monitoring. Server administrators only.
- `/resume` starts monitoring. Server administrators only.
- `/set_config` changes the rent limit and check interval. Server administrators only.

The rent limit defaults to 9,999 TWD. Settings and already-notified listing IDs are stored in the data directory.

## Deploy on an Oracle Cloud Always Free VM

Create an Always Free eligible VM in Oracle Cloud. An Ampere A1 Flex VM with Ubuntu 24.04 ARM, 1 OCPU, and 6 GB RAM is a suitable starting size when capacity is available. Free capacity varies by region.

SSH into the VM and install Docker, Compose, and Git:

```bash
sudo apt update
sudo apt install -y git docker.io docker-compose-v2
sudo systemctl enable --now docker
```

Clone the repository and create the private environment file:

```bash
git clone https://github.com/boli1004o0/bot_crawler.git
cd bot_crawler
cp .env.example .env
nano .env
```

Set `DISCORD_BOT_TOKEN` and `DISCORD_CHANNEL_ID` in `.env`. Do not commit or share this file. Invite the bot to your Discord server with the `applications.commands`, `Send Messages`, and `Embed Links` permissions.

Create the persistent data folder and start the bot:

```bash
mkdir -p data
sudo chown 10001:10001 data
sudo docker compose up -d --build
sudo docker compose logs -f
```

Use `/status`, `/pause`, and `/resume` in Discord. The pause/resume commands require Discord server administrator permission. The bot only needs outbound network access; do not open public inbound ports for it. Oracle's Always Free capacity and account eligibility are subject to Oracle's current terms.

To deploy a later GitHub update:

```bash
git pull
sudo docker compose up -d --build
```
