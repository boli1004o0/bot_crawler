import json
import os
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from bot_crawler import fetch_zhunan_rentals_with_browser, load_seen_houses, save_seen_houses


def send_listing(webhook_url, house):
    price = int(str(house.get("price", "0")).replace(",", ""))
    house_id = str(house.get("id", ""))
    embed = {
        "title": f"🏠 {house.get('title', '無標題')}",
        "url": f"https://rent.591.com.tw/{house_id}",
        "color": 5814783,
        "fields": [
            {"name": "💰 租金", "value": f"**{price}** 元/月", "inline": True},
            {
                "name": "📐 格局",
                "value": f"{house.get('kind_name', '未知類型')} / {house.get('area') or '暫無'}坪",
                "inline": True,
            },
            {"name": "📍 地點", "value": house.get("location", "竹南鎮"), "inline": False},
        ],
        "footer": {"text": "591 租屋網即時偵測 (DrissionPage)"},
    }
    request = Request(
        webhook_url,
        data=json.dumps({"embeds": [embed]}).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "DiscordBot (https://github.com/boli1004o0/bot_crawler, 1.0)",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            if response.status not in (200, 204):
                raise RuntimeError(f"Discord webhook returned HTTP {response.status}")
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Discord webhook returned HTTP {error.code}: {detail}") from error


def main():
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        raise SystemExit("Missing DISCORD_WEBHOOK_URL secret")

    max_price = int(os.environ.get("MAX_PRICE_TWD", "9999"))
    seen_houses = load_seen_houses()
    houses = fetch_zhunan_rentals_with_browser()
    new_count = 0

    for house in houses:
        house_id = str(house.get("id", ""))
        if not house_id or house_id in seen_houses:
            continue

        price_text = str(house.get("price", "0")).replace(",", "")
        price = int(price_text) if price_text.isdigit() else 0
        if max_price > 0 and price > max_price:
            continue

        send_listing(webhook_url, house)
        seen_houses.add(house_id)
        new_count += 1
        time.sleep(1)

    if new_count:
        save_seen_houses(seen_houses)
    print(f"Check complete; sent {new_count} new listing(s).")


if __name__ == "__main__":
    main()