# economy_bot/main.py
import os
import datetime
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

from database import get_system_data, save_data, player_inventory, get_user_count

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)

# Ưu tiên nạp .env trong thư mục economy_bot/, nếu không có sẽ nạp .env ở thư mục gốc
local_env = os.path.join(BASE_DIR, '.env')
root_env = os.path.join(ROOT_DIR, '.env')
if os.path.exists(local_env):
    load_dotenv(local_env)
elif os.path.exists(root_env):
    load_dotenv(root_env)
else:
    load_dotenv()

TOKEN = os.getenv('ECONOMY_TOKEN') or os.getenv('TOKEN')

if not TOKEN or TOKEN == "None":
    print("❌ [ECONOMY BOT ERROR] Chưa cài đặt ECONOMY_TOKEN (hoặc TOKEN) trong file .env!")
    exit(1)

OWNER_ID = 1135806949527670835
SUBOWNER_ID = [1138020979348606996]
WELCOME_CHANNEL_ID = 1297128688801808434

intents = discord.Intents.default()
intents.message_content = False
intents.members = False
intents.presences = False


class KatEconomyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def setup_hook(self):
        print("🛰️ [ECONOMY BOT] Đang khởi động hệ thống Cogs...")
        extensions = [
            'economy', 'sinkhole', 'lifesim', 'other',
            'command', 'pet', 'whoisspy', 'masoi', 'admin_economy'
        ]

        for ext in extensions:
            try:
                await self.load_extension(ext)
                print(f"   🔹 Loaded Cog: {ext} -> OK")
            except commands.ExtensionNotFound:
                print(f"   ⚠️ Skipping: File {ext}.py chưa được khởi tạo.")
            except Exception as e:
                print(f"   ❌ FAILED to load Cog '{ext}': {e}")

        print("⚙️ [ECONOMY BOT] Tất cả các Cogs đã được đồng bộ hóa thành công!")


bot = KatEconomyBot(command_prefix=['p', 'P'], case_insensitive=True, intents=intents)
bot.remove_command('help')


@tasks.loop(minutes=2)
async def update_watching_status():
    await bot.wait_until_ready()

    real_user_count = 0
    try:
        real_user_count = get_user_count()
    except Exception:
        pass

    guild_count = len(bot.guilds)
    member_count = sum(guild.member_count for guild in bot.guilds if guild.member_count)

    if not hasattr(update_watching_status, 'index'):
        update_watching_status.index = 0

    status_list = [
        f"{guild_count} server và {member_count:,} thành viên",
        f"{real_user_count:,} người đang đào mỏ & cày cuốc ⛏️",
        f"{real_user_count:,} người ra cầu ở (Tài Xỉu/Bầu Cua) 🎲",
        "ko bt bot này xài ntn | Gõ /phelp nha!"
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


@tasks.loop(minutes=10)
async def check_renew_server():
    system_data = get_system_data()
    now = datetime.datetime.now(datetime.timezone.utc)
    saved_time_str = system_data.get("next_renew_time")

    if not saved_time_str:
        next_time = now + datetime.timedelta(days=7)
        system_data["next_renew_time"] = next_time.isoformat()
        save_data(player_inventory)
        return

    try:
        next_time = datetime.datetime.fromisoformat(saved_time_str)
    except Exception:
        next_time = now + datetime.timedelta(days=7)
        system_data["next_renew_time"] = next_time.isoformat()
        save_data(player_inventory)
        return

    if now >= next_time:
        channel_id = system_data.get("notification_channel_id")
        channel = bot.get_channel(channel_id) if channel_id else None
        if channel:
            mentions = f"<@{OWNER_ID}> " + " ".join([f"<@{sid}>" for sid in SUBOWNER_ID])
            embed = discord.Embed(
                title="🚨 BÁO ĐỘNG GIA HẠN SERVER 🚨",
                description="Đã đến mốc gia hạn VPS! Mau vào panel gia hạn server ngay kẻo bị tắt máy mất dữ liệu!\n\n*(Gia hạn xong gõ lệnh `p renewed` hoặc `/renewed` để reset bộ đếm nhé)*",
                color=discord.Color.red()
            )
            embed.set_thumbnail(url="https://media.giphy.com/media/l41YkFIiBxQdRlvwc/giphy.gif")
            try:
                await channel.send(content=mentions, embed=embed)
            except Exception as e:
                print(f"❌ [RENEWAL ERROR] {e}")

        new_next_time = now + datetime.timedelta(days=5)
        system_data["next_renew_time"] = new_next_time.isoformat()
        save_data(player_inventory)


@bot.event
async def on_message(message):
    await bot.process_commands(message)


@bot.event
async def on_ready():
    print("==================================================")
    print("💰 KatBot Economy đã trực tuyến thành công!")
    print(f"🌟 Đăng nhập dưới tên: {bot.user}")
    print(f"🔑 Bot ID: {bot.user.id}")
    print("==================================================")

    try:
        synced = await bot.tree.sync()
        print(f"⚡ [ECONOMY BOT] Đã đồng bộ {len(synced)} Slash Commands.")
    except Exception as e:
        print(f"❌ [ECONOMY BOT] Lỗi đồng bộ Slash Commands: {e}")

    if not update_watching_status.is_running():
        update_watching_status.start()

    if not check_renew_server.is_running():
        check_renew_server.start()


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, (commands.CommandNotFound, commands.CommandOnCooldown)):
        return
    raise error


@bot.event
async def on_member_join(member):
    if not WELCOME_CHANNEL_ID:
        return
    channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
    if channel is None:
        return

    embed = discord.Embed(
        title=f"🎉 Chào Mừng {member.name}!",
        description=f"Cảm ơn cậu đã tham gia server **{member.guild.name}**!\nHãy đọc <#1303933198912192532> và tải KVGDPS tại <#1291732977595973792> nhé!",
        color=discord.Color.from_rgb(102, 204, 255),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    embed.add_field(name="Cậu là thành viên thứ:", value=f"**{len(member.guild.members):,}**", inline=True)
    if member.avatar:
        embed.set_thumbnail(url=member.avatar.url)
    embed.set_footer(text=f"ID: {member.id}", icon_url=member.guild.icon.url if member.guild.icon else None)

    try:
        await channel.send(f"Xin chào mừng {member.mention} đã đến với server! <a:tada:>", embed=embed)
    except Exception as e:
        print(f"❌ [WELCOME ERROR] {e}")


if __name__ == '__main__':
    bot.run(TOKEN)
