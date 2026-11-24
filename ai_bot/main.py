# ai_bot/main.py
import os
import json
import datetime
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)

# Ưu tiên nạp .env trong thư mục ai_bot/, nếu không có sẽ nạp .env ở thư mục gốc
local_env = os.path.join(BASE_DIR, '.env')
root_env = os.path.join(ROOT_DIR, '.env')
if os.path.exists(local_env):
    load_dotenv(local_env)
elif os.path.exists(root_env):
    load_dotenv(root_env)
else:
    load_dotenv()

TOKEN = os.getenv('AI_TOKEN') or os.getenv('TOKEN')

if not TOKEN or TOKEN == "None":
    print("❌ [AI BOT ERROR] Chưa cài đặt AI_TOKEN (hoặc TOKEN) trong file .env!")
    exit(1)

OWNER_ID = 1135806949527670835
SUBOWNER_ID = [1138020979348606996]
WELCOME_CHANNEL_ID = 1297128688801808434

intents = discord.Intents.default()
intents.message_content = True
intents.members = False
intents.presences = False


class KatAIBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def setup_hook(self):
        print("🛰️ [AI BOT] Đang khởi động hệ thống AI Cogs...")
        try:
            await self.load_extension('AIphcbot')
            print("   🔹 Loaded Cog: AIphcbot -> OK")
        except Exception as e:
            print(f"   ❌ FAILED to load Cog 'AIphcbot': {e}")
        print("⚙️ [AI BOT] Khởi động Cogs hoàn tất!")


bot = KatAIBot(command_prefix=['ai!', 'AI!'], case_insensitive=True, intents=intents)
bot.remove_command('help')


@tasks.loop(minutes=2)
async def update_watching_status():
    await bot.wait_until_ready()
    guild_count = len(bot.guilds)
    member_count = sum(guild.member_count for guild in bot.guilds if guild.member_count)

    if not hasattr(update_watching_status, 'index'):
        update_watching_status.index = 0

    status_list = [
        f"{guild_count} server và {member_count:,} thành viên",
        "Tag hoặc Reply để chat với em AI 🥰",
        "bot AI nhưng mà AI lạ lắm 🤡",
        "AI Moderation đang bảo vệ server 🛡️"
    ]

    current_status = status_list[update_watching_status.index % len(status_list)]
    update_watching_status.index += 1

    activity = discord.Activity(
        type=discord.ActivityType.watching,
        name=current_status
    )

    try:
        await bot.change_presence(activity=activity)
    except Exception as e:
        print(f"❌ [PRESENCE ERROR] {e}")


@bot.event
async def on_message(message):
    await bot.process_commands(message)


@bot.event
async def on_ready():
    print("==================================================")
    print("🤖 KatBot AI đã trực tuyến thành công!")
    print(f"🌟 Đăng nhập dưới tên: {bot.user}")
    print(f"🔑 Bot ID: {bot.user.id}")
    print("==================================================")

    try:
        synced = await bot.tree.sync()
        print(f"⚡ [AI BOT] Đã đồng bộ {len(synced)} Slash Commands.")
    except Exception as e:
        print(f"❌ [AI BOT] Lỗi đồng bộ Slash Commands: {e}")

    if not update_watching_status.is_running():
        update_watching_status.start()


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, (commands.CommandNotFound, commands.CommandOnCooldown)):
        return
    raise error


if __name__ == '__main__':
    bot.run(TOKEN)
