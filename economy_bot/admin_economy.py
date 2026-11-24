# economy_bot/admin_economy.py
import discord
from discord import app_commands
from discord.ext import commands

from constants import ore, KESLING_ICON
from database import (
    owner_id, subowner_id, get_user_data, save_data, player_inventory,
    add_ore_with_quality, get_total_ore_count, remove_ore_units
)


class AdminEconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(
        name="say",
        description="Gửi tin nhắn nhân danh bot đến một kênh văn bản chỉ định (Chỉ Admin)"
    )
    @app_commands.describe(
        channel="Kênh văn bản cần gửi tin nhắn",
        message="Nội dung tin nhắn muốn gửi"
    )
    async def say(self, ctx, channel: discord.TextChannel = None, *, message: str = None):
        if str(ctx.author.id) != owner_id and str(ctx.author.id) not in subowner_id:
            return await ctx.send("🚫 Bạn không có quyền dùng lệnh này.", ephemeral=True)

        if channel is None or message is None:
            return await ctx.send("💡 Cách dùng: `/say channel: #tên-kênh message: <nội dung>`")
        try:
            await channel.send(message)
            await ctx.send(f"✅ Đã gửi tin nhắn đến {channel.mention}")
        except Exception as e:
            await ctx.send(f"❌ Lỗi: `{e}`")

    @commands.hybrid_command(
        name="reload",
        aliases=["rl"],
        description="Tải lại (reload) các Cog Economy để cập nhật tính năng (Chỉ Admin)"
    )
    @app_commands.describe(extension="Tên Cog muốn reload (vd: economy, sinkhole, pet...)")
    async def reload_cogs(self, ctx, extension: str = None):
        if str(ctx.author.id) != owner_id and str(ctx.author.id) not in subowner_id:
            return await ctx.send("🚫 Bạn không có quyền dùng lệnh này.", ephemeral=True)

        extensions = [
            'economy', 'sinkhole', 'lifesim', 'other',
            'command', 'pet', 'whoisspy', 'masoi', 'admin_economy'
        ]

        if extension:
            ext_lower = extension.lower()
            target_ext = next((ext for ext in extensions if ext.lower() == ext_lower), None)
            if not target_ext:
                return await ctx.send(f"❌ Không tìm thấy Cog nào có tên `{extension}`.")
            try:
                await self.bot.reload_extension(target_ext)
                return await ctx.send(f"✅ Đã reload thành công Cog: `{target_ext}`!")
            except Exception as e:
                return await ctx.send(f"❌ Lỗi khi reload Cog `{target_ext}`: `{e}`")

        success_cogs = []
        failed_cogs = []
        for ext in extensions:
            try:
                await self.bot.reload_extension(ext)
                success_cogs.append(f"`{ext}`")
            except Exception as e:
                failed_cogs.append(f"`{ext}` (Lỗi: {e})")

        msg = ""
        if success_cogs:
            msg += f"✅ Đã reload thành công các Cogs: {', '.join(success_cogs)}\n"
        if failed_cogs:
            msg += f"❌ Thất bại tại các Cogs: {', '.join(failed_cogs)}"
        await ctx.send(msg)

    @commands.hybrid_command(
        name="mod",
        description="Bảng điều khiển quản lý tiền và quặng (Chỉ Admin)"
    )
    @app_commands.describe(
        action="Hành động: addmoney, setmoney, addore, removeore",
        args_str="Tham số chi tiết (@user, số lượng, tên quặng...)"
    )
    async def mod(self, ctx, action: str = None, *, args_str: str = None):
        if str(ctx.author.id) != owner_id and str(ctx.author.id) not in subowner_id:
            return await ctx.send("🚫 Bạn không có quyền dùng lệnh này.", ephemeral=True)

        if not action or not args_str:
            embed = discord.Embed(title="📘 Hướng dẫn sử dụng lệnh /mod (Economy)", color=discord.Color.blue())
            embed.add_field(name="Cộng tiền", value="`/mod action: addmoney args_str: @user <số_tiền>`", inline=False)
            embed.add_field(name="Đặt lại tiền", value="`/mod action: setmoney args_str: @user <số_tiền>`", inline=False)
            embed.add_field(name="Thêm quặng", value="`/mod action: addore args_str: @user <tên_quặng> <số_lượng>`", inline=False)
            embed.add_field(name="Xóa quặng", value="`/mod action: removeore args_str: @user <tên_quặng> <số_lượng>`", inline=False)
            return await ctx.send(embed=embed)

        args_list = args_str.split()
        if len(args_list) < 2:
            return await ctx.send("❌ Thiếu tham số.")

        member_arg = args_list[0]
        try:
            member = await commands.MemberConverter().convert(ctx, member_arg)
        except Exception:
            return await ctx.send(f"❌ Không tìm thấy thành viên `{member_arg}`.")

        remaining_args = args_list[1:]
        action = action.lower()
        user_id = str(member.id)
        user_data = get_user_data(user_id)

        if action == "addmoney":
            try:
                amount = int(remaining_args[-1])
                user_data['money'] = user_data.get('money', 0) + amount
                save_data(player_inventory)
                await ctx.send(f"✅ Đã cộng **{amount:,} {KESLING_ICON}** cho **{member.display_name}**.")
            except ValueError:
                await ctx.send("❌ Số tiền không hợp lệ.")

        elif action == "setmoney":
            try:
                amount = int(remaining_args[-1])
                user_data['money'] = amount
                save_data(player_inventory)
                await ctx.send(f"✅ Đã set tiền của **{member.display_name}** thành **{amount:,} {KESLING_ICON}**.")
            except ValueError:
                await ctx.send("❌ Số tiền không hợp lệ.")

        elif action == "addore":
            if len(remaining_args) < 2:
                return await ctx.send("❌ Cú pháp: `/mod action: addore args_str: @user <tên_quặng> <số_lượng>`")
            target_ore = remaining_args[0].lower()
            if target_ore not in ore:
                return await ctx.send("❌ Tên quặng không tồn tại.")
            try:
                amount = int(remaining_args[1])
                inv = user_data.get('inventory', {})
                add_ore_with_quality(inv, target_ore, quality_percent=100, qty=amount)
                save_data(player_inventory)
                await ctx.send(f"✅ Đã cộng **{amount:,}** quặng **{target_ore}** (100% chất lượng) cho **{member.display_name}**.")
            except ValueError:
                await ctx.send("❌ Số lượng không hợp lệ.")

        elif action == "removeore":
            if len(remaining_args) < 2:
                return await ctx.send("❌ Cú pháp: `/mod action: removeore args_str: @user <tên_quặng> <số_lượng>`")
            target_ore = remaining_args[0].lower()
            if target_ore not in ore:
                return await ctx.send("❌ Tên quặng không tồn tại.")
            try:
                amount = int(remaining_args[1])
                inv = user_data.get('inventory', {})
                total_have = get_total_ore_count(inv, target_ore)
                if total_have < amount:
                    return await ctx.send(f"❌ Người chơi không đủ quặng (chỉ có {total_have}).")
                remove_ore_units(inv, target_ore, amount, strategy='lowest')
                save_data(player_inventory)
                await ctx.send(f"✅ Đã xóa **{amount:,}** quặng **{target_ore}** của **{member.display_name}**.")
            except ValueError:
                await ctx.send("❌ Số lượng không hợp lệ.")
        else:
            await ctx.send("❌ Hành động không hợp lệ. Chọn: `addmoney`, `setmoney`, `addore`, `removeore`.")


async def setup(bot):
    await bot.add_cog(AdminEconomyCog(bot))
