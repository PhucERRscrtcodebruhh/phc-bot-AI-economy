import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import re
import random
import time

def parse_time(duration: str):
    match = re.match(r"^(\d+)(s|m|h|d|mo|y)$", duration.lower())
    if not match:
        return None
    
    amount, unit = match.groups()
    amount = int(amount)
    
    mapping = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400,
        "mo": 2592000, 
        "y": 31536000
    }
    return amount * mapping[unit]

class CommandCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="pgiveaway", description="Tổ chức giveaway nhanh trên server")
    @app_commands.describe(reward="Phần thưởng", winners="Số lượng người thắng cuộc", duration="Thời gian chạy (VD: 10s, 5m, 2h, 1d)")
    async def pgiveaway(self, ctx, reward: str, winners: int, duration: str):
        seconds = parse_time(duration)
        if not seconds:
            await ctx.send("❌ Định dạng thời gian không hợp lệ! Hãy dùng s, m, h, d, mo, y (Ví dụ: 30m, 2h).", ephemeral=True)
            return

        end_time = int(time.time() + seconds)

        embed = discord.Embed(
            title="🎉 SỰ KIỆN GIVEAWAY 🎉",
            description=f"**Phần thưởng:** {reward}\n**Số người thắng:** {winners}\n**Thời gian kết thúc:** <t:{end_time}:R>\n\nThả cảm xúc 🎉 để tham gia!",
            color=discord.Color.from_rgb(102, 204, 255)
        )
        msg = await ctx.send(embed=embed)
        await msg.add_reaction("🎉")

        await asyncio.sleep(seconds)

        try:
            msg = await ctx.channel.fetch_message(msg.id)
        except discord.NotFound:
            await ctx.send(f"❌ Lỗi: Tin nhắn giveaway của phần thưởng **{reward}** đã bị xóa mất tiêu rồi!")
            return

        reaction = discord.utils.get(msg.reactions, emoji="🎉")
        if not reaction:
            await ctx.send(f"😢 Không tìm thấy lượt tương tác nào cho giveaway **{reward}**.")
            return

        users = [user async for user in reaction.users() if not user.bot]

        if not users:
            await ctx.send(f"😢 Không có ai tham gia giveaway phần thưởng **{reward}** hết!")
            return

        actual_winners = random.sample(users, min(len(users), winners))
        winner_mentions = ", ".join([w.mention for w in actual_winners])
        
        await ctx.send(f"🎉 Chúc mừng {winner_mentions} đã xuất sắc trúng thưởng **{reward}**!")

    @commands.hybrid_command(name="phelp", description="Hiển thị danh sách các lệnh của hệ thống")
    async def phelp(self, ctx):
        embed = discord.Embed(
            title="📋 DANH SÁCH LỆNH BOT",
            description="Dưới đây là các lệnh cậu có thể sử dụng:",
            color=discord.Color.green()
        )
        embed.add_field(name="/pgiveaway", value="Tạo giveaway mới.\n*Cú pháp:* `/pgiveaway reward: <quà> winners: <số người> duration: <thời gian>`", inline=False)
        embed.add_field(name="/phelp", value="Hiển thị bảng hướng dẫn này.", inline=False)
        embed.add_field(name="/ban", value="Trục xuất vĩnh viễn thành viên khỏi server.", inline=False)
        embed.add_field(name="/kick", value="Sút thành viên ra khỏi server.", inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="ban", description="Ban một thành viên ra khỏi máy chủ")
    @commands.has_permissions(ban_members=True)
    @app_commands.describe(member="Thành viên cần ban", reason="Lý do xử lý")
    async def ban(self, ctx, member: discord.Member, *, reason: str = "Không có lý do cụ thể"):
        try:
            await member.ban(reason=reason)
            await ctx.send(f"🛑 Đã thực hiện ban thành viên {member.mention}. Lý do: {reason}")
        except discord.Forbidden:
            await ctx.send("❌ Tớ không đủ quyền hạn để ban thành viên này!", ephemeral=True)

    @commands.hybrid_command(name="kick", description="Kick một thành viên ra khỏi máy chủ")
    @commands.has_permissions(kick_members=True)
    @app_commands.describe(member="Thành viên cần kick", reason="Lý do xử lý")
    async def kick(self, ctx, member: discord.Member, *, reason: str = "Không có lý do cụ thể"):
        try:
            await member.kick(reason=reason)
            await ctx.send(f"🥾 Đã thực hiện kick thành viên {member.mention}. Lý do: {reason}")
        except discord.Forbidden:
            await ctx.send("❌ Tớ không đủ quyền hạn để kick thành viên này!", ephemeral=True)

    @ban.error
    @kick.error
    async def mod_errors(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ Cậu không có quyền hạn điều hành để thực hiện lệnh này nha!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(CommandCog(bot))