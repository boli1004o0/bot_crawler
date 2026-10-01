import os
import re
import json
import asyncio
from pathlib import Path
import discord
from discord.ext import tasks, commands
from dotenv import load_dotenv
from DrissionPage import ChromiumPage, ChromiumOptions

load_dotenv()

BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))
DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parent))
DATA_DIR.mkdir(parents=True, exist_ok=True)
SEEN_HOUSES_FILE = DATA_DIR / "seen_houses.json"
SETTINGS_FILE = DATA_DIR / "bot_settings.json"

DEFAULT_CONFIG = {
    "max_price": 11001,
    "interval_min": 5,
    "is_active": True
}

def load_config():
    config = DEFAULT_CONFIG.copy()
    try:
        saved_config = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return config

    if not isinstance(saved_config, dict):
        return config

    max_price = saved_config.get("max_price")
    interval_min = saved_config.get("interval_min")
    is_active = saved_config.get("is_active")
    if type(max_price) is int and max_price >= 0:
        config["max_price"] = max_price
    if type(interval_min) is int and interval_min > 0:
        config["interval_min"] = interval_min
    if type(is_active) is bool:
        config["is_active"] = is_active
    return config

def save_config():
    try:
        temporary_file = SETTINGS_FILE.with_suffix(".tmp")
        temporary_file.write_text(
            json.dumps(config, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        temporary_file.replace(SETTINGS_FILE)
        return True
    except OSError as e:
        print(f"[-] 保存設定失敗: {e}")
        return False

config = load_config()

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

def load_seen_houses():
    if os.path.exists(SEEN_HOUSES_FILE):
        try:
            with open(SEEN_HOUSES_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_seen_houses(seen_set):
    with open(SEEN_HOUSES_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen_set), f, ensure_ascii=False, indent=2)
def fetch_zhunan_rentals_with_browser():
    """使用 DrissionPage 讀取 591 頁面上的竹南租屋卡片。"""
    page = None
    try:
        co = ChromiumOptions()
        browser_path = os.getenv("CHROME_PATH")
        if browser_path:
            co.set_browser_path(browser_path)
        co.headless(os.getenv("CHROME_HEADLESS", "false").lower() == "true")
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-gpu')
        co.set_argument('--disable-dev-shm-usage')
        co.set_user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
        
        print("[+] 正在啟動 Chromium...")
        page = ChromiumPage(co)
        
        # 先寫入苗栗縣 (7) Cookie 防止 591 自動跳轉預設縣市
        print("[+] 正在開啟 591 首頁...")
        page.get("https://rent.591.com.tw")
        page.set.cookies({'name': 'urlJumpIp', 'value': '7', 'domain': '.591.com.tw'})
        
        # 依發布時間由新到舊載入竹南鎮房源
        target_url = "https://rent.591.com.tw/?region=7&section=80&order=posttime&orderType=desc"
        print("[+] 正在開啟 591 竹南租屋頁面...")
        page.get(target_url)
        
        # 591 目前直接在頁面輸出房源卡片，無需等待 rs-list API
        page.wait.eles_loaded('css:.item', timeout=15)
        cards = page.eles('css:.item')[:10]
        items = []
        seen_ids = set()
        
        for card in cards:
            try:
                link_ele = card.ele('css:.item-info-title a')
                if not link_ele:
                    continue

                href = link_ele.attr('href') or ""
                house_id = href.rstrip("/").rsplit("/", 1)[-1]
                if not house_id or house_id in seen_ids:
                    continue
                seen_ids.add(house_id)

                card_text = card.text
                title = link_ele.text.strip() or "竹南租屋"
                price_match = re.search(r"([\d,]+)\s*元/月", card_text)
                area_match = re.search(r"([\d.]+)\s*坪", card_text)
                room_type = next(
                    (kind for kind in ("整層住家", "獨立套房", "分租套房", "雅房", "車位", "其他") if kind in card_text),
                    "租屋"
                )

                items.append({
                    "id": house_id,
                    "title": title,
                    "price": price_match.group(1).replace(",", "") if price_match else "0",
                    "location": "苗栗縣竹南鎮",
                    "kind_name": room_type,
                    "area": area_match.group(1) if area_match else ""
                })
            except Exception:
                continue

        print(f"[+] 成功從頁面卡片抓取到 {len(items)} 筆竹南房源！")
        return items

    except Exception as e:
        print(f"[-] 抓取失敗: {e}")
        return []
    finally:
        if page:
            page.quit() # 抓取結束後自動釋放與關閉視窗
            
@tasks.loop(minutes=5)
async def check_rentals_task():
    if not config["is_active"]:
        return

    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print("[-] 找不到設定的 Discord 頻道，請確認 CHANNEL_ID 是否正確。")
        return

    seen_houses = load_seen_houses()
    
    # 由於開啟瀏覽器屬於阻塞操作，放到獨立線程執行避免卡住 Discord Bot
    print("[+] 正在開啟瀏覽器檢查竹南最新房源...")
    houses = await asyncio.to_thread(fetch_zhunan_rentals_with_browser)
    new_count = 0

    for house in houses:
        house_id = str(house.get("id"))
        if not house_id or house_id in seen_houses:
            continue

        price_str = str(house.get("price", "0")).replace(",", "")
        price = int(price_str) if price_str.isdigit() else 0
        
        # 預算過濾
        if config["max_price"] > 0 and price > config["max_price"]:
            continue

        title = house.get("title", "無標題")
        location = house.get("location", "竹南鎮")
        room_type = house.get("kind_name", "未知類型")
        area = str(house.get("area", "暫無"))
        link = f"https://rent.591.com.tw/{house_id}"

        embed = discord.Embed(
            title=f"🏠 {title}",
            url=link,
            color=0x58B9FF
        )
        embed.add_field(name="💰 租金", value=f"**{price}** 元/月", inline=True)
        embed.add_field(name="📐 格局", value=f"{room_type} / {area}坪", inline=True)
        embed.add_field(name="📍 地點", value=location, inline=False)
        embed.set_footer(text="591 租屋網即時偵測 (DrissionPage)")

        await channel.send(embed=embed)
        seen_houses.add(house_id)
        new_count += 1
        await asyncio.sleep(1)

    if new_count > 0:
        save_seen_houses(seen_houses)
        print(f"[+] 成功發現並發送 {new_count} 筆新房源通知！")
    else:
        print("[+] 檢查完畢，沒有發現新房源。")

@bot.event
async def on_ready():
    print(f"[+] Bot 已上線：{bot.user.name}")
    try:
        synced = await bot.tree.sync()
        print(f"[+] 已同步 {len(synced)} 個斜線指令")
    except Exception as e:
        print(f"[-] 同步指令失敗: {e}")
    
    check_rentals_task.change_interval(minutes=config["interval_min"])
    if config["is_active"] and not check_rentals_task.is_running():
        check_rentals_task.start()

def is_server_admin(interaction: discord.Interaction):
    return (
        isinstance(interaction.user, discord.Member)
        and interaction.user.guild_permissions.administrator
    )

async def update_monitoring_state(interaction: discord.Interaction, is_active: bool):
    if not is_server_admin(interaction):
        await interaction.response.send_message("只有伺服器管理員可以控制租屋偵測。", ephemeral=True)
        return

    config["is_active"] = is_active
    saved = save_config()
    if is_active:
        if not check_rentals_task.is_running():
            check_rentals_task.start()
        message = "租屋偵測已開啟。"
    else:
        if check_rentals_task.is_running():
            check_rentals_task.cancel()
        message = "租屋偵測已關閉。"

    if not saved:
        message += "（設定未能寫入資料目錄，重啟後可能不會保留。）"
    await interaction.response.send_message(message, ephemeral=True)

@bot.tree.command(name="pause", description="暫停租屋偵測")
async def pause(interaction: discord.Interaction):
    await update_monitoring_state(interaction, False)

@bot.tree.command(name="resume", description="恢復租屋偵測")
async def resume(interaction: discord.Interaction):
    await update_monitoring_state(interaction, True)

@bot.tree.command(name="status", description="查看當前租屋爬蟲設定狀態")
async def status(interaction: discord.Interaction):
    max_p = f"{config['max_price']} 元" if config['max_price'] > 0 else "不限價格"
    msg = (
        f"📊 **目前偵測設定**\n"
        f"• 狀態: {'🟢 運作中' if config['is_active'] else '🔴 已暫停'}\n"
        f"• 預算上限: **{max_p}**\n"
        f"• 檢查間隔: 每 **{config['interval_min']}** 分鐘一次"
    )
    await interaction.response.send_message(msg)

@bot.tree.command(name="set_config", description="設定最高租金與檢查頻率")
async def set_config(interaction: discord.Interaction, max_price: int, interval_minutes: int):
    if not is_server_admin(interaction):
        await interaction.response.send_message("只有伺服器管理員可以修改租金與檢查時間。", ephemeral=True)
        return

    config["max_price"] = max_price
    config["interval_min"] = interval_minutes
    check_rentals_task.change_interval(minutes=interval_minutes)
    saved = save_config()
    
    max_p_str = f"{max_price} 元" if max_price > 0 else "不限制"
    message = (
        f"✅ **設定更新成功！**\n"
        f"• 預算上限改為：**{max_p_str}**\n"
        f"• 檢查頻率改為：每 **{interval_minutes}** 分鐘一次"
    )
    if not saved:
        message += "\n⚠️ 設定未能寫入資料目錄，重啟後可能不會保留。"
    await interaction.response.send_message(message)

if __name__ == "__main__":
    bot.run(BOT_TOKEN)