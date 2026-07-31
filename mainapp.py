# mainapp.py
import os
import json
import datetime
import dotenv
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

# Khởi tạo môi trường
load_dotenv()
TOKEN = os.getenv('TOKEN')

if not TOKEN or TOKEN == "None":
    print("❌ [SYSTEM ERROR] Oniichan chưa cài đặt TOKEN trong file .env rồi!")
    exit(1)

# Định nghĩa các hằng số hệ thống
OWNER_ID = 1135806949527670835
SUBOWNER_ID = [1138020979348606996]
WELCOME_CHANNEL_ID = 1297128688801808434

# Cấu hình Intents tối đa
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True


class KatBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def setup_hook(self):
        print("🛰️ [SYSTEM] Đang khởi động hệ thống Cogs...")
        extensions = [
            'AIphcbot', 'economy', 'sinkhole', 
            'lifesim', 'other', 'command', 
            'pet', 'whoisspy','masoi'
        ]
        
        for ext in extensions:
            try:
                await self.load_extension(ext)
                print(f"   🔹 Loaded Cog: {ext} -> OK")
            except commands.ExtensionNotFound:
                print(f"   ⚠️ Skipping: File {ext}.py chưa được khởi tạo.")
            except Exception as e:
                print(f"   ❌ FAILED to load Cog '{ext}': {e}")
        
        print("⚙️ [SYSTEM] Tất cả các Cogs đã được đồng bộ hóa thành công!")


bot = KatBot(command_prefix=['p', 'P'], case_insensitive=True, intents=intents)
bot.remove_command('help')


# ==================== TÁC VỤ STATUS XOAY VÒNG ĐỘNG ====================

@tasks.loop(minutes=2)
async def update_watching_status():
    """Tự động đếm số người trong data.json và xoay vòng Status hài hước"""
    await bot.wait_until_ready()

    # 1. Đếm số người chơi thực tế trong data.json
    real_user_count = 0
    if os.path.exists('data.json'):
        try:
            with open('data.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Lọc bỏ SYSTEM_DATA, chỉ đếm User ID thực tế
                real_user_count = len([k for k in data.keys() if k != "SYSTEM_DATA"])
        except Exception:
            pass

    # 2. Đếm số Server và Tổng thành viên Discord
    guild_count = len(bot.guilds)
    member_count = sum(guild.member_count for guild in bot.guilds if guild.member_count)

    # Biến đếm chỉ số vòng lặp
    if not hasattr(update_watching_status, 'index'):
        update_watching_status.index = 0

    # 3. Danh sách các câu Status xoay vòng theo đúng yêu cầu
    status_list = [
        f"{guild_count} server và {member_count:,} thành viên",
        f"{real_user_count:,} người ra chat em AI 🥰",
        f"{real_user_count:,} người ra cầu ở (Tài Xỉu/Bầu Cua) 🎲",
        "bot AI nhưng mà AI lạ lắm 🤡",
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
        print(f"📡 [PRESENCE] Cập nhật status: Watching '{current_status}'")
    except Exception as e:
        print(f"❌ [PRESENCE ERROR] Lỗi cập nhật status: {e}")


@tasks.loop(minutes=10)
async def check_renew_server():
    """Tác vụ ngầm kiểm tra hạn máy chủ VPS"""
    try:
        from AIphcbot import get_system_data, save_data, player_inventory
    except ImportError:
        return

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
        channel_ID = system_data.get("notification_channel_id")
        channel = bot.get_channel(channel_ID) if channel_ID else None
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
                print(f"❌ [RENEWAL ERROR] Lỗi gửi tin nhắn gia hạn: {e}")
        
        new_next_time = now + datetime.timedelta(days=5)
        system_data["next_renew_time"] = new_next_time.isoformat()
        save_data(player_inventory)


# ==================== BOT EVENTS ====================

@bot.event
async def on_message(message):
    await bot.process_commands(message)


@bot.event
async def on_ready():
    print("==================================================")
    print(f"🌟 KatBot / phc bot đã trực tuyến thành công!")
    print(f"🤖 Đăng nhập dưới tên: {bot.user}")
    print(f"🔑 Bot ID: {bot.user.id}")
    print("==================================================")
    
    # Đồng bộ Slash Command Tree lên Discord để hiển thị nút Lệnh trên Hồ sơ Bot
    try:
        synced = await bot.tree.sync()
        print(f"⚡ App Command Tree (Slash Commands) đã đồng bộ thành công {len(synced)} lệnh.")
    except Exception as e:
        print(f"❌ Lỗi đồng bộ Slash Commands: {e}")

    # Khởi chạy các luồng ngầm
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
        print(f"❌ [WELCOME ERROR] Không thể gửi tin nhắn chào mừng: {e}")


if __name__ == '__main__':
    bot.run(TOKEN)