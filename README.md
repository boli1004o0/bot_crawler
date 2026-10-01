# 591 Rent Bot

Discord bot that checks the newest 10 Zhu-Nan rental listings on 591 and sends qualifying listings to a channel.

## Discord commands

- `/status` shows the current monitor state and filters.
- `/pause` stops monitoring. Server administrators only.
- `/resume` starts monitoring. Server administrators only.
- `/set_config` changes the rent limit and check interval. Server administrators only.

The rent limit defaults to 11,001 TWD. Settings and already-notified listing IDs are stored in the data directory.

## Deploy with GitHub Actions

The scheduled workflow checks listings every three hours and sends matching listings through a Discord webhook. Its UTC schedule runs at 08:00, 11:00, 14:00, 17:00, 20:00, 23:00, 02:00, and 05:00 Taiwan time. It runs once per check, so the Discord slash commands are not available in this deployment mode.

1. In Discord, create a webhook for the notification channel and copy its URL.
2. In the GitHub repository, open **Settings > Secrets and variables > Actions**, create a repository secret named `DISCORD_WEBHOOK_URL`, and paste the webhook URL as its value. Do not commit the URL or put it in a workflow file.
3. Push this workflow to the repository's default branch.
4. In **Actions**, run **Check 591 rentals** once with **Run workflow** to test it. Scheduled runs may be delayed by GitHub during busy periods.

The rent limit defaults to 11,001 TWD in `.github/workflows/rental-check.yml`. The workflow caches seen listing IDs; its first run may notify matching listings already on the page.

The existing Docker deployment remains available for a continuously running Discord bot with slash commands.
