# sinkhole.py
import asyncio
import random
import string
import html
import datetime
import discord
from discord.ext import commands
from discord.ui import View, TextInput, Modal

# Import sạch sẽ từ các file chung thư mục
from constants import KESLING_ICON, FISH_POOL, price, emoji_icon, DICE_EMOJIS, BAUCUA_MAP
from AIphcbot import get_user_data, save_data, load_quiz_questions, player_inventory, owner_id, subowner_id

# ==================== CASINO MODALS ====================

class LobbyDirectBetModal(Modal, title="Xác nhận tiền cược"):
    amount_input = TextInput(label="Số tiền muốn cược", placeholder="Ví dụ: 10000", required=True)

    def __init__(self, lobby_view, choice):
        super().__init__()
        self.lobby_view = lobby_view
        self.choice = choice

    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        
        if user_id in self.lobby_view.active_bets:
            return await interaction.response.send_message("❌ Bạn đã đặt cược trong phiên này rồi!", ephemeral=True)

        try:
            bet_amount = int(self.amount_input.value.strip())
        except ValueError:
            return await interaction.response.send_message("❌ Số tiền cược phải là số nguyên dương.", ephemeral=True)

        if bet_amount <= 0:
            return await interaction.response.send_message("❌ Tiền cược phải lớn hơn 0.", ephemeral=True)

        player = get_user_data(user_id)
        current_money = player.get("money", 0)

        if bet_amount > current_money:
            return await interaction.response.send_message(f"❌ Bạn không đủ tiền! Ví hiện tại: **{current_money:,} {KESLING_ICON}**.", ephemeral=True)

        player["money"] -= bet_amount
        save_data(player_inventory)

        bet_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        self.lobby_view.active_bets[user_id] = {
            "choice": self.choice,
            "amount": bet_amount,
            "display_name": interaction.user.display_name,
            "mention": interaction.user.mention
        }

        choice_display = str(self.choice).upper()
        await interaction.response.send_message(
            f"✅ **Đặt cược thành công!**\n"
            f"Oniichan đã đặt cược cửa **{choice_display}** với số tiền **{bet_amount:,} {KESLING_ICON}**.\n"
            f"ID cược: `{bet_id}`", 
            ephemeral=True
        )
        await self.lobby_view.refresh_lobby_msg()


class LobbyNumberBetModal(Modal, title="Cược Số Chính Xác (3-18)"):
    number_input = TextInput(label="Nhập một số chính xác (3 đến 18)", placeholder="Ví dụ: 10", required=True, max_length=2)
    amount_input = TextInput(label="Số tiền muốn cược", placeholder="Ví dụ: 5000", required=True)

    def __init__(self, lobby_view):
        super().__init__()
        self.lobby_view = lobby_view

    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        if user_id in self.lobby_view.active_bets:
            return await interaction.response.send_message("❌ Bạn đã đặt cược trong phiên này rồi!", ephemeral=True)

        try:
            num = int(self.number_input.value.strip())
            if not (3 <= num <= 18):
                raise ValueError
        except ValueError:
            return await interaction.response.send_message("❌ Số đặt cược phải nằm trong khoảng từ 3 đến 18.", ephemeral=True)

        try:
            bet_amount = int(self.amount_input.value.strip())
        except ValueError:
            return await interaction.response.send_message("❌ Số tiền cược không hợp lệ.", ephemeral=True)

        if bet_amount <= 0:
            return await interaction.response.send_message("❌ Tiền cược phải lớn hơn 0.", ephemeral=True)

        player = get_user_data(user_id)
        current_money = player.get("money", 0)

        if bet_amount > current_money:
            return await interaction.response.send_message(f"❌ Bạn không đủ tiền! Ví hiện tại: **{current_money:,} {KESLING_ICON}**.", ephemeral=True)

        player["money"] -= bet_amount
        save_data(player_inventory)

        bet_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        self.lobby_view.active_bets[user_id] = {
            "choice": num,
            "amount": bet_amount,
            "display_name": interaction.user.display_name,
            "mention": interaction.user.mention
        }

        await interaction.response.send_message(
            f"✅ **Đặt cược thành công!**\n"
            f"Oniichan đã đặt cược vào số **{num}** với số tiền **{bet_amount:,} {KESLING_ICON}**.\n"
            f"ID cược: `{bet_id}`", 
            ephemeral=True
        )
        await self.lobby_view.refresh_lobby_msg()


# ==================== CASINO LOBBY VIEW ====================

class TaiXiuLobbyView(View):
    def __init__(self, author, session_id):
        super().__init__(timeout=60)
        self.author = author
        self.session_id = session_id
        self.active_bets = {}
        self.message = None
        self.is_closed = False

    async def refresh_lobby_msg(self):
        if self.message and not self.is_closed:
            try:
                await self.message.edit(embed=self.generate_embed(time_remaining=None))
            except Exception:
                pass

    def generate_embed(self, time_remaining=None):
        embed = discord.Embed(
            title="🎲 SẢNH TÀI XỈU HOÀNG GIA 🎲",
            description=(
                "**Tỉ lệ trả thưởng:**\n"
                "• **Tài/Xỉu/Chẵn/Lẻ:** `x2` tiền cược\n"
                "• **Cược số cụ thể:**\n"
                "  > `10, 11`: **x6** | `9, 12`: **x7** | `8, 13`: **x8** | `7, 14`: **x12**\n"
                "  > `6, 15`: **x15** | `5, 16`: **x20** | `4, 17`: **x50** | `3, 18`: **x150**\n\n"
                f"🆔 **ID Phiên:** `{self.session_id}`"
            ),
            color=discord.Color.purple()
        )
        lobby_display = "\n".join([f"• **{i['display_name']}**: cược **{i['amount']:,}** {KESLING_ICON} vào **{str(i['choice']).upper()}**" for i in self.active_bets.values()]) if self.active_bets else "*Chưa có ai đặt cược.*"
        embed.add_field(name="👥 Danh Sách Đặt Cược", value=lobby_display, inline=False)
        
        if time_remaining is not None:
            embed.set_footer(text=f"⏰ Thời gian cược còn lại: {time_remaining} giây...")
        else:
            embed.set_footer(text="⏰ Phiên cược đang diễn ra sôi nổi...")
            
        return embed

    @discord.ui.button(label="TÀI", style=discord.ButtonStyle.secondary, emoji="⬆️", row=0)
    async def cược_tai(self, interaction: discord.Interaction, button: discord.Button):
        if self.is_closed: return await interaction.response.send_message("❌ Phiên cược đã đóng!", ephemeral=True)
        await interaction.response.send_modal(LobbyDirectBetModal(self, "tai"))

    @discord.ui.button(label="XỈU", style=discord.ButtonStyle.secondary, emoji="⬇️", row=0)
    async def cược_xiu(self, interaction: discord.Interaction, button: discord.Button):
        if self.is_closed: return await interaction.response.send_message("❌ Phiên cược đã đóng!", ephemeral=True)
        await interaction.response.send_modal(LobbyDirectBetModal(self, "xiu"))

    @discord.ui.button(label="CHẴN", style=discord.ButtonStyle.primary, emoji="⚫", row=0)
    async def cược_chan(self, interaction: discord.Interaction, button: discord.Button):
        if self.is_closed: return await interaction.response.send_message("❌ Phiên cược đã đóng!", ephemeral=True)
        await interaction.response.send_modal(LobbyDirectBetModal(self, "chan"))

    @discord.ui.button(label="LẺ", style=discord.ButtonStyle.danger, emoji="🔴", row=0)
    async def cược_le(self, interaction: discord.Interaction, button: discord.Button):
        if self.is_closed: return await interaction.response.send_message("❌ Phiên cược đã đóng!", ephemeral=True)
        await interaction.response.send_modal(LobbyDirectBetModal(self, "le"))

    @discord.ui.button(label="CƯỢC SỐ (3-18)", style=discord.ButtonStyle.success, emoji="🎯", row=1)
    async def cược_số(self, interaction: discord.Interaction, button: discord.Button):
        if self.is_closed: return await interaction.response.send_message("❌ Phiên cược đã đóng!", ephemeral=True)
        await interaction.response.send_modal(LobbyNumberBetModal(self))


# ==================== MULTIPLAYER BẦU CUA TÔM CÁ ====================

class BaucuaBetModal(Modal, title="Đặt Cược Bầu Cua"):
    amount_input = TextInput(label="Số tiền muốn cược", placeholder="Ví dụ: 20000", required=True)

    def __init__(self, lobby_view, choice):
        super().__init__()
        self.lobby_view = lobby_view
        self.choice = choice

    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        if user_id in self.lobby_view.active_bets:
            return await interaction.response.send_message("❌ Bạn đã đặt cược trong phiên này rồi!", ephemeral=True)

        try:
            bet_amount = int(self.amount_input.value.strip())
        except ValueError:
            return await interaction.response.send_message("❌ Số tiền cược phải là số nguyên dương.", ephemeral=True)

        if bet_amount <= 0:
            return await interaction.response.send_message("❌ Tiền cược phải lớn hơn 0.", ephemeral=True)

        player = get_user_data(user_id)
        current_money = player.get("money", 0)

        if bet_amount > current_money:
            return await interaction.response.send_message(f"❌ Bạn không đủ tiền! Ví hiện tại: **{current_money:,} {KESLING_ICON}**.", ephemeral=True)

        player["money"] -= bet_amount
        save_data(player_inventory)

        bet_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        self.lobby_view.active_bets[user_id] = {
            "choice": self.choice,
            "amount": bet_amount,
            "display_name": interaction.user.display_name,
            "mention": interaction.user.mention
        }

        emoji_choice = BAUCUA_MAP[self.choice]['emoji']
        name_choice = BAUCUA_MAP[self.choice]['name']
        await interaction.response.send_message(
            f"✅ **Đặt cược thành công!**\n"
            f"Oniichan đã đặt cửa **{emoji_choice} {name_choice}** với số tiền **{bet_amount:,} {KESLING_ICON}**.\n"
            f"Mã cược: `{bet_id}`", 
            ephemeral=True
        )
        await self.lobby_view.refresh_lobby_msg()


class BaucuaLobbyView(View):
    def __init__(self, author, session_id):
        super().__init__(timeout=60)
        self.author = author
        self.session_id = session_id
        self.active_bets = {}
        self.message = None
        self.is_closed = False

    async def refresh_lobby_msg(self):
        if self.message and not self.is_closed:
            try:
                await self.message.edit(embed=self.generate_embed(time_remaining=None))
            except Exception:
                pass

    def generate_embed(self, time_remaining=None):
        embed = discord.Embed(
            title="🧉 SẢNH BẦU CUA TÔM CÁ 🧉",
            description=(
                "**Luật chơi:**\n"
                "• Đoán trúng 1 hình: `x2` tiền cược (hoàn vốn + thắng x1)\n"
                "• Đoán trúng 2 hình: `x3` tiền cược (hoàn vốn + thắng x2)\n"
                "• Đoán trúng 3 hình: `x4` tiền cược (hoàn vốn + thắng x3)\n\n"
                f"🆔 **ID Phiên:** `{self.session_id}`"
            ),
            color=discord.Color.green()
        )
        lobby_display = "\n".join([f"• **{i['display_name']}**: cược **{i['amount']:,}** {KESLING_ICON} vào {BAUCUA_MAP[i['choice']]['emoji']} **{BAUCUA_MAP[i['choice']]['name']}**" for i in self.active_bets.values()]) if self.active_bets else "*Chưa có ai đặt cược.*"
        embed.add_field(name="👥 Danh Sách Đặt Cược", value=lobby_display, inline=False)
        
        if time_remaining is not None:
            embed.set_footer(text=f"⏰ Thời gian cược còn lại: {time_remaining} giây...")
        else:
            embed.set_footer(text="⏰ Phiên cược đang diễn ra...")
        return embed

    async def check_and_bet(self, interaction, choice_key):
        if self.is_closed:
            return await interaction.response.send_message("❌ Phiên cược đã đóng!", ephemeral=True)
        await interaction.response.send_modal(BaucuaBetModal(self, choice_key))

    @discord.ui.button(label="Nai", style=discord.ButtonStyle.secondary, emoji="🦌", row=0)
    async def bet_nai(self, interaction, button): await self.check_and_bet(interaction, 'nai')

    @discord.ui.button(label="Bầu", style=discord.ButtonStyle.secondary, emoji="🧉", row=0)
    async def bet_bau(self, interaction, button): await self.check_and_bet(interaction, 'bau')

    @discord.ui.button(label="Gà", style=discord.ButtonStyle.secondary, emoji="🐓", row=0)
    async def bet_ga(self, interaction, button): await self.check_and_bet(interaction, 'ga')

    @discord.ui.button(label="Tôm", style=discord.ButtonStyle.secondary, emoji="🦐", row=1)
    async def bet_tom(self, interaction, button): await self.check_and_bet(interaction, 'tom')

    @discord.ui.button(label="Cá", style=discord.ButtonStyle.secondary, emoji="🐟", row=1)
    async def bet_ca(self, interaction, button): await self.check_and_bet(interaction, 'ca')

    @discord.ui.button(label="Cua", style=discord.ButtonStyle.secondary, emoji="🦀", row=1)
    async def bet_cua(self, interaction, button): await self.check_and_bet(interaction, 'cua')


# ==================== MULTIPLAYER COQUAY NGA (REVOLVER DEATHMATCH) ====================

class RussianRouletteJoinView(View):
    def __init__(self, author, bet_amount, session_id):
        super().__init__(timeout=60)
        self.author = author
        self.bet_amount = bet_amount
        self.session_id = session_id
        self.players = {}  # user_id -> display_name
        self.message = None
        self.is_closed = False

    def generate_embed(self, time_remaining=None):
        embed = discord.Embed(
            title="🔫 SẢNH CÒ QUAY NGA (DEATHMATCH) 🔫",
            description=(
                f"**Mức cược tham gia bắt buộc:** **{self.bet_amount:,}** {KESLING_ICON}\n"
                "**Luật chơi:**\n"
                "• Toàn bộ người chơi tham gia sẽ đặt cược cùng 1 số tiền.\n"
                "• Bot sẽ nạp 1 viên đạn vào ổ xoay và bóp cò tuần tự xoay tua.\n"
                "• Người bị bắn trúng sẽ bị loại (mất tiền cược).\n"
                "• **Người sống sót duy nhất** ăn trọn quỹ tiền thưởng theo công thức tỉ lệ nghịch xác suất!\n\n"
                f"🆔 **ID Phiên:** `{self.session_id}`"
            ),
            color=discord.Color.red()
        )
        lobby_display = "\n".join([f"• **{name}** 🔫" for name in self.players.values()]) if self.players else "*Chưa có đấu sĩ nào tham gia sảnh tử thần.*"
        embed.add_field(name="👥 Danh Sách Đấu Sĩ", value=lobby_display, inline=False)
        
        if time_remaining is not None:
            embed.set_footer(text=f"⏰ Sảnh sẽ khóa để nạp đạn sau: {time_remaining} giây...")
        else:
            embed.set_footer(text="⏰ Đang chuẩn bị xoay ổ đạn...")
        return embed

    @discord.ui.button(label="Tham Gia Đấu Sĩ", style=discord.ButtonStyle.danger, emoji="🔫")
    async def join_lobby(self, interaction: discord.Interaction, button: discord.Button):
        if self.is_closed:
            return await interaction.response.send_message("❌ Sảnh đấu đã đóng băng để nạp đạn rồi!", ephemeral=True)
            
        user_id = str(interaction.user.id)
        if user_id in self.players:
            return await interaction.response.send_message("❌ Bạn đã tham gia sảnh đấu sĩ rồi!", ephemeral=True)

        player_data = get_user_data(user_id)
        current_money = player_data.get("money", 0)

        if current_money < self.bet_amount:
            return await interaction.response.send_message(f"❌ Số dư ví của bạn không đủ để tham gia sảnh cược **{self.bet_amount:,} {KESLING_ICON}**.", ephemeral=True)

        player_data["money"] -= self.bet_amount
        save_data(player_inventory)

        self.players[user_id] = interaction.user.display_name
        
        await interaction.response.send_message(f"✅ Oniichan gia nhập sảnh tử thần thành công! Đã nạp **{self.bet_amount:,} {KESLING_ICON}** vào quỹ cược.", ephemeral=True)
        
        try:
            await self.message.edit(embed=self.generate_embed(time_remaining=None))
        except Exception:
            pass


# ==================== TRIỆU PHÚ & COINFLIP ====================

class QuizView(View):
    def __init__(self, author, timeout: int = 30):
        super().__init__(timeout=timeout)
        self.author = author
        self.choice = None
        self.is_processed = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ Đây không phải phần chơi của bạn.", ephemeral=True)
            return False
        if self.is_processed:
            return False
        return True

    def _disable_all(self):
        self.is_processed = True
        for item in self.children:
            item.disabled = True

    async def handle_choice(self, interaction: discord.Interaction, choice_idx: int):
        self._disable_all()
        self.choice = choice_idx
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label="A", style=discord.ButtonStyle.primary)
    async def choose_a(self, interaction: discord.Interaction, button: discord.Button):
        await self.handle_choice(interaction, 0)

    @discord.ui.button(label="B", style=discord.ButtonStyle.primary)
    async def choose_b(self, interaction: discord.Interaction, button: discord.Button):
        await self.handle_choice(interaction, 1)

    @discord.ui.button(label="C", style=discord.ButtonStyle.primary)
    async def choose_c(self, interaction: discord.Interaction, button: discord.Button):
        await self.handle_choice(interaction, 2)

    @discord.ui.button(label="D", style=discord.ButtonStyle.primary)
    async def choose_d(self, interaction: discord.Interaction, button: discord.Button):
        await self.handle_choice(interaction, 3)

    async def wait_for_choice(self):
        await self.wait()
        return self.choice


class DifficultyView(View):
    def __init__(self, author):
        super().__init__(timeout=30)
        self.author = author
        self.difficulty = None
        self.is_processed = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            return False
        if self.is_processed:
            return False
        return True

    def _disable_all(self):
        self.is_processed = True
        for item in self.children:
            item.disabled = True

    @discord.ui.button(label="Dễ", style=discord.ButtonStyle.success)
    async def easy(self, interaction: discord.Interaction, button: discord.Button):
        self._disable_all()
        self.difficulty = "easy"
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Trung Binh", style=discord.ButtonStyle.primary)
    async def medium(self, interaction: discord.Interaction, button: discord.Button):
        self._disable_all()
        self.difficulty = "medium"
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Khó", style=discord.ButtonStyle.secondary)
    async def hard(self, interaction: discord.Interaction, button: discord.Button):
        self._disable_all()
        self.difficulty = "hard"
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Cực Khó", style=discord.ButtonStyle.danger)
    async def extreme(self, interaction: discord.Interaction, button: discord.Button):
        self._disable_all()
        self.difficulty = "extreme"
        self.stop()
        await interaction.response.defer()


# ==================== COG CLASS ====================

class SinkholeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="cf", aliases=["coinflip"])
    async def coin_flip(self, ctx, guess: str = None, bet: int = None):
        if guess is None or bet is None:
            return await ctx.send(f"❌ Dùng lệnh: `p cf <h/t> <tiền_cược>`")
            
        guess = guess.lower()
        if guess not in ["h", "t", "ngua", "sap"]:
            return await ctx.send("❌ Vui lòng chỉ đoán `h` (ngửa) hoặc `t` (sấp).")
            
        if bet <= 0:
            return await ctx.send("❌ Tiền cược phải lớn hơn 0.")
            
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        if user_data['money'] < bet:
            return await ctx.send("❌ Số dư ví của bạn không đủ.")

        user_data['money'] -= bet
        save_data(player_inventory)

        result = random.choice(["ngua", "sap"])
        user_guess = "ngua" if guess in ["h", "ngua"] else "sap"

        await ctx.send("🪙 *Đang tung đồng xu...*")
        await asyncio.sleep(1.5)

        if user_guess == result:
            prize = bet * 2
            user_data['money'] += prize
            save_data(player_inventory)
            await ctx.send(f"🎉 **Đoán đúng!** Đồng xu ra **{result}**. Bạn nhận được **+{bet:,} {KESLING_ICON}**!")
        else:
            await ctx.send(f"😭 **Đoán sai mất rồi!** Đồng xu ra **{result}**. Bạn mất **-{bet:,} {KESLING_ICON}**.")

    @commands.command(name="taixiu", aliases=["tx"])
    async def taixiu_command(self, ctx):
        session_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        
        view = TaiXiuLobbyView(ctx.author, session_id)
        embed = view.generate_embed(time_remaining=45)
        
        msg = await ctx.send(embed=embed, view=view)
        view.message = msg

        countdown_time = 45
        while countdown_time > 0:
            await asyncio.sleep(5)
            countdown_time -= 5
            if countdown_time > 0:
                try:
                    await msg.edit(embed=view.generate_embed(time_remaining=countdown_time))
                except Exception:
                    pass

        # Khóa cược và vô hiệu hóa các nút bấm của view đặt cược
        view.is_closed = True
        for item in view.children:
            item.disabled = True
        try:
            await msg.edit(view=view)
        except Exception:
            pass

        # ==================== EMBED MỚI: MÀN HÌNH LẮC XÚC XẮC (10 GIÂY) ====================
        rolling_embed = discord.Embed(
            title="🎲 LẮC BÁT - PHIÊN ĐANG CHẠY 🎲",
            description="Thời gian đặt cược đã kết thúc! Vui lòng đợi trong giây lát...",
            color=discord.Color.blurple()
        )
        rolling_embed.set_thumbnail(url="https://i.imgur.com/KBy6E9O.gif") # Cậu có thể thay link gif xúc xắc lắc nếu thích

        for _ in range(6): 
            td1, td2, td3 = random.randint(1, 6), random.randint(1, 6), random.randint(1, 6)
            rolling_embed.clear_fields()
            rolling_embed.add_field(
                name="Status:", 
                value="⚡ *Đang lắc xúc xắc nhiệt tình...*"
            )
            rolling_embed.add_field(
                name="Xúc xắc:", 
                value=f"{DICE_EMOJIS[td1]} {DICE_EMOJIS[td2]} {DICE_EMOJIS[td3]}",
                inline=False
            )
            try:
                # Edit đè Embed lắc bát mới này lên tin nhắn cũ và xóa View đặt cược đi
                await msg.edit(embed=rolling_embed, view=None)
            except Exception:
                pass
            await asyncio.sleep(1.6)

        # ==================== EMBED MỚI: CÔNG BỐ KẾT QUẢ CUỐI CÙNG ====================
        d1, d2, d3 = random.randint(1, 6), random.randint(1, 6), random.randint(1, 6)
        total = d1 + d2 + d3
        is_triple = (d1 == d2 == d3)

        result_taixiu = "Xiu" if total <= 10 else "Tai"
        result_chanle = "Chẵn" if total % 2 == 0 else "Lẻ"

        NUM_MULTIPLIERS = {
            10: 6, 11: 6, 9: 7, 12: 7, 8: 8, 13: 8, 7: 12, 14: 12,
            6: 15, 15: 15, 5: 20, 16: 20, 4: 50, 17: 50, 3: 150, 18: 150
        }

        dice_result_str = f"{DICE_EMOJIS[d1]} {DICE_EMOJIS[d2]} {DICE_EMOJIS[d3]} = **{total}**"

        result_embed = discord.Embed(
            title="🏁 KẾT QUẢ PHIÊN CƯỢC 🏁",
            color=discord.Color.gold()
        )
        result_embed.add_field(
            name="Kết quả là:", 
            value=f"{dice_result_str}\n\n**Tài/Xỉu:** `{result_taixiu}`\n**Chẵn/Lẻ:** `{result_chanle}`", 
            inline=False
        )

        summary_lines = []
        for uid, bet_info in view.active_bets.items():
            user_data = get_user_data(uid)
            bet_choice = bet_info["choice"]
            bet_amount = bet_info["amount"]
            user_mention = bet_info["mention"]

            win = False
            multiplier = 2

            if is_triple:
                if bet_choice == str(total):
                    win = True
                    multiplier = 10
            else:
                if bet_choice == 'tai' and total >= 11:
                    win = True
                elif bet_choice == 'xiu' and total <= 10:
                    win = True
                elif bet_choice == 'chan' and total % 2 == 0:
                    win = True
                elif bet_choice == 'le' and total % 2 == 1:
                    win = True
                elif isinstance(bet_choice, int) and bet_choice == total:
                    win = True
                    multiplier = NUM_MULTIPLIERS.get(total, 10)

            if win:
                prize_payout = bet_amount * multiplier
                user_data['money'] = user_data.get('money', 0) + prize_payout
                summary_lines.append(f"🎉 {user_mention} đã cược **{bet_amount:,}** vào **{str(bet_choice).upper()}** và THẮNG **+{prize_payout:,}** {KESLING_ICON}!")
            else:
                summary_lines.append(f"👎 {user_mention} đã cược **{bet_amount:,}** vào **{str(bet_choice).upper()}** và THUA **-{bet_amount:,}** {KESLING_ICON}!")

        save_data(player_inventory)

        if summary_lines:
            summary_display = "\n".join(summary_lines)
        else:
            summary_display = "*Không có ai đặt cược trong phiên này.*"

        result_embed.add_field(name="📊 Bảng Tổng Kết Phiên Đấu", value=summary_display, inline=False)
        
        current_time = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        result_embed.set_footer(text=f"Kết thúc lúc: {current_time} | ID phiên: {session_id}")

        # Edit đè kết quả cuối cùng lên tin nhắn
        await msg.edit(embed=result_embed, view=None)

    @commands.command(name="baucua", aliases=["bc"])
    async def baucua_command(self, ctx):
        """Hệ thống sảnh chờ Bầu Cua Tôm Cá 45s."""
        session_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        view = BaucuaLobbyView(ctx.author, session_id)
        embed = view.generate_embed(time_remaining=45)
        
        msg = await ctx.send(embed=embed, view=view)
        view.message = msg

        countdown_time = 45
        while countdown_time > 0:
            await asyncio.sleep(5)
            countdown_time -= 5
            if countdown_time > 0:
                try:
                    await msg.edit(embed=view.generate_embed(time_remaining=countdown_time))
                except Exception:
                    pass

        view.is_closed = True
        for item in view.children:
            item.disabled = True
        try:
            await msg.edit(view=view)
        except Exception:
            pass

        keys = list(BAUCUA_MAP.keys())
        r1, r2, r3 = random.choice(keys), random.choice(keys), random.choice(keys)
        rolled = [r1, r2, r3]

        result_str = (
            f"{BAUCUA_MAP[r1]['emoji']} **{BAUCUA_MAP[r1]['name']}** | "
            f"{BAUCUA_MAP[r2]['emoji']} **{BAUCUA_MAP[r2]['name']}** | "
            f"{BAUCUA_MAP[r3]['emoji']} **{BAUCUA_MAP[r3]['name']}**"
        )

        result_embed = discord.Embed(title="🧉 KẾT QUẢ BẦU CUA TÔM CÁ 🧉", color=discord.Color.green())
        result_embed.add_field(name="Kết quả mở bát là:", value=result_str, inline=False)

        summary_lines = []
        for uid, bet_info in view.active_bets.items():
            user_data = get_user_data(uid)
            bet_choice = bet_info["choice"]
            bet_amount = bet_info["amount"]
            user_mention = bet_info["mention"]

            matches = rolled.count(bet_choice)
            if matches > 0:
                prize_payout = bet_amount * (matches + 1)
                user_data['money'] = user_data.get('money', 0) + prize_payout
                summary_lines.append(f"🎉 {user_mention} đoán trúng **{matches}x** {BAUCUA_MAP[bet_choice]['emoji']} và thắng **+{bet_amount * matches:,}** {KESLING_ICON}!")
            else:
                summary_lines.append(f"👎 {user_mention} cược sai cửa {BAUCUA_MAP[bet_choice]['emoji']} và mất **-{bet_amount:,}** {KESLING_ICON}!")

        save_data(player_inventory)

        if summary_lines:
            summary_display = "\n".join(summary_lines)
        else:
            summary_display = "*Không có ai đặt cược trong phiên này.*"

        result_embed.add_field(name="📊 Bảng Tổng Kết Giao Dịch", value=summary_display, inline=False)
        current_time = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        result_embed.set_footer(text=f"Kết thúc lúc: {current_time} | ID phiên: {session_id}")

        await msg.edit(embed=result_embed, view=None)

    @commands.command(name="coquay", aliases=["pcr", "roulette"])
    async def coquay_command(self, ctx, bet_amount: int = None):
        """Hệ thống sảnh chờ Cò Quay Nga sát phạt cực lớn theo công thức toán học."""
        if bet_amount is None or bet_amount <= 0:
            return await ctx.send("❌ Dùng lệnh: `p coquay <số_tiền_cược>` để thiết lập phòng chơi.")

        user_id = str(ctx.author.id)
        player_data = get_user_data(user_id)
        if player_data.get("money", 0) < bet_amount:
            return await ctx.send(f"❌ Ví của bạn hông đủ tiền khởi tạo sảnh cược **{bet_amount:,} {KESLING_ICON}**!")

        session_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        view = RussianRouletteJoinView(ctx.author, bet_amount, session_id)
        
        # Admin khởi tạo phòng tự động được tham gia miễn phí (đã trừ cược)
        player_data["money"] -= bet_amount
        save_data(player_inventory)
        view.players[user_id] = ctx.author.display_name

        embed = view.generate_embed(time_remaining=45)
        msg = await ctx.send(embed=embed, view=view)
        view.message = msg

        # Đếm ngược sảnh đấu
        countdown_time = 45
        while countdown_time > 0:
            await asyncio.sleep(5)
            countdown_time -= 5
            if countdown_time > 0:
                try:
                    await msg.edit(embed=view.generate_embed(time_remaining=countdown_time))
                except Exception:
                    pass

        view.is_closed = True
        for item in view.children:
            item.disabled = True
        try:
            await msg.edit(view=view)
        except Exception:
            pass

        # Kiểm tra điều kiện số đấu sĩ tối thiểu
        active_ids = list(view.players.keys())
        total_players_count = len(active_ids)
        if total_players_count < 2:
            # Hoàn trả cược nếu hông đủ người chơi
            for uid in active_ids:
                p_data = get_user_data(uid)
                p_data["money"] = p_data.get("money", 0) + bet_amount
            save_data(player_inventory)
            return await msg.edit(content="❌ **Sảnh hủy:** Hông có ai chịu cược đối đầu với oniichan cả, đã hoàn tiền cược!", embed=None, view=None)

        # Tiến hành bóp cò súng luân phiên (Xoay tua ngẫu nhiên)
        logs = []
        original_players_dict = dict(view.players)
        chambers = 6
        bullet_index = random.randint(1, chambers) # Viên đạn nằm ở phòng ngẫu nhiên
        current_chamber_pointer = 1

        logs.append(f"🔥 **Sảnh đấu súng bắt đầu!** Tổng cộng có {total_players_count} đấu sĩ.")
        logs.append(f"🔫 Viên đạn chết chóc đã nạp vào 1 trong {chambers} ổ đạn.")

        duel_list = list(active_ids)
        random.shuffle(duel_list) # Tráo vị trí bắn

        step = 0
        while len(duel_list) > 1:
            current_player_id = duel_list[step % len(duel_list)]
            player_name = original_players_dict[current_player_id]

            logs.append(f"⏱️ **Lượt {step+1}:** Đấu sĩ **{player_name}** áp súng lên thái dương và bóp cò...")
            
            # Kiểm tra xem búa gõ trúng ổ chứa đạn không
            if current_chamber_pointer == bullet_index:
                # 💥 SÚNG NỔ!
                logs.append(f"💥 **ĐOÀNG!** Đầu óc **{player_name}** nổ tung! Anh ta đã bị LOẠI.")
                duel_list.remove(current_player_id)
                # Reset ổ xoay đạn cho vòng sau
                chambers = 6
                bullet_index = random.randint(1, chambers)
                current_chamber_pointer = 1
            else:
                # ❌ CLICK (Sống sót)
                logs.append(f"❌ *Cạch!* Thật may mắn, súng hông nổ! **{player_name}** sống sót qua lượt.")
                chambers -= 1
                current_chamber_pointer += 1
                step += 1

            game_embed = discord.Embed(
                title="🔫 DIỄN BIẾN SÚNG NỔ 🔫",
                description="\n".join(logs[-8:]),
                color=discord.Color.red()
            )
            await msg.edit(embed=game_embed)
            await asyncio.sleep(2.5)

        winner_id = duel_list[0]
        winner_name = original_players_dict[winner_id]
        winner_mention = f"<@{winner_id}>"

        prize = int((total_players_count * bet_amount * 2) / (1.0 / total_players_count))

        winner_data = get_user_data(winner_id)
        winner_data["money"] = winner_data.get("money", 0) + prize
        save_data(player_inventory)

        final_embed = discord.Embed(
            title="👑 ĐẤU SĨ SỐNG SÓT DUY NHẤT 👑",
            description=(
                f"🎉 Xin chúc mừng đấu sĩ kiên cường {winner_mention} (**{winner_name}**)!\n"
                f"Anh ta là người sống sót duy nhất sau loạt bóp cò súng tàn bạo.\n\n"
                f"💰 **Quỹ tiền thưởng khổng lồ:** **{prize:,}** {KESLING_ICON}\n"
                f"*(Xác suất sống sót ban đầu: 1/{total_players_count})*"
            ),
            color=discord.Color.gold()
        )
        final_embed.set_footer(text=f"Phiên đấu: {session_id} | Hoàn tất.")
        await msg.channel.send(embed=final_embed)

    @commands.command(name="trieuphu")
    @commands.cooldown(rate=1, per=60, type=commands.BucketType.user)
    async def trieuphu(self, ctx):
        user_id = str(ctx.author.id)
        diff_view = DifficultyView(ctx.author)
        diff_msg = await ctx.send("🎮 Oniichan muốn chinh phục Triệu Phú ở cấp độ nào nè?", view=diff_view)
        await diff_view.wait()
        
        if diff_view.difficulty is None:
            return await diff_msg.edit(content="⏰ Quá thời gian lựa chọn rồi oniichan!", view=None)

        DIFFICULTY_CONFIG = {
            "easy": {"prizes": [10, 15, 25, 40, 60, 90, 140, 220, 330, 500], "name": "Dễ"},
            "medium": {"prizes": [30, 45, 70, 110, 170, 270, 420, 650, 1000, 1500], "name": "Trung Bình"},
            "hard": {"prizes": [60, 90, 140, 220, 340, 540, 840, 1300, 2000, 3000], "name": "Khó"},
            "extreme": {"prizes": [200, 300, 450, 700, 1100, 1700, 2700, 4200, 6500, 10000], "name": "Cực Khó"}
        }
        config = DIFFICULTY_CONFIG[diff_view.difficulty]
        local_prizes = config["prizes"]
        
        all_quiz_data = load_quiz_questions()
        category_questions = all_quiz_data.get(diff_view.difficulty, [])
        if not category_questions:
            return await diff_msg.edit(content=f"❌ Không tìm thấy bộ câu hỏi cho độ khó này.", view=None)

        random.shuffle(category_questions)
        questions_data = category_questions[:10]
        
        await diff_msg.edit(content=f"💰 Trận đấu Triệu Phú chế độ **{config['name']}** chính thức bắt đầu!", view=None)
        await asyncio.sleep(1.0)

        won_amount = 0
        current_level = 0
        session_id = "ERR-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6)) # ID Phiên đấu

        for q in questions_data:
            level_prize = local_prizes[current_level]
            question_text = html.unescape(q["question"])
            original_choices = [html.unescape(c) for c in q["choices"]]
            original_correct_index = q["correct_index"]

            indexed_choices = list(enumerate(original_choices))
            random.shuffle(indexed_choices)
            choices_text = [choice for _, choice in indexed_choices]
            correct_index = next(new_idx for new_idx, (old_idx, _) in enumerate(indexed_choices) if old_idx == original_correct_index)

            q_embed = discord.Embed(
                title=f"Câu Hỏi {current_level + 1}/10 (Giải thưởng: {level_prize:,} {KESLING_ICON})",
                description=f"**{question_text}**\n",
                color=discord.Color.blue()
            )
            # Thêm Avatar của người chơi vào Embed
            if ctx.author.avatar:
                q_embed.set_thumbnail(url=ctx.author.avatar.url)
            q_embed.add_field(name="Đáp án lựa chọn:", value=choices_str, inline=False)
            q_embed.set_footer(text=f"Tiền tích lũy an toàn: {won_amount:,} {KESLING_ICON} | ID Phiên: {session_id}")

            view = QuizView(ctx.author)
            view.message = await ctx.send(embed=q_embed, view=view)
            
            idx = await view.wait_for_choice()
            if idx is None:
                await ctx.send(f"⏰ Hết thời gian suy nghĩ! Bạn mang về: **{won_amount:,} {KESLING_ICON}**")
                break

            if idx == correct_index:
                won_amount = level_prize
                current_level += 1
                await ctx.send(f"✅ **Chính xác!** Nâng mức thưởng an toàn lên **{won_amount:,} {KESLING_ICON}**!")
                await asyncio.sleep(1.2)
            else:
                await ctx.send(f"❌ **Sai rồi!** Đáp án đúng phải là: **{choices_text[correct_index]}**. Bạn ra về với mức thưởng: **{won_amount:,} {KESLING_ICON}**.")
                break

        final_result_embed = discord.Embed(
            title=f"🏆 TRẬN ĐẤU TRIỆU PHÚ KẾT THÚC 🏆",
            description="",
            color=discord.Color.gold() if won_amount > 0 else discord.Color.red()
        )
        if ctx.author.avatar:
            final_result_embed.set_thumbnail(url=ctx.author.avatar.url)

        if won_amount > 0:
            final_result_embed.description = f"🎉 Chúc mừng oniichan đã mang về tổng cộng **{won_amount:,} {KESLING_ICON}**!"
        else:
            final_result_embed.description = f"😭 Tiếc quá, oniichan ra về tay trắng hoặc với mức thưởng an toàn: **{won_amount:,} {KESLING_ICON}**."
        
        final_result_embed.set_footer(text=f"ID Phiên: {session_id}")
        
        await ctx.send(embed=final_result_embed)

    @commands.command(name="cauca", aliases=["pcauca", "fishing"])
    @commands.cooldown(rate=1, per=300, type=commands.BucketType.user)
    async def cauca_command(self, ctx):
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        inv = user_data.get('inventory', {})

        roll = random.random() * 100
        caught = {}
        common_keys = list(FISH_POOL["common"].keys())
        special_keys = list(FISH_POOL["special"].keys())

        if roll < 75.0:
            qty = random.randint(10, 50)
            fish_type = "Thường 🐟"
            for _ in range(qty):
                f = random.choice(common_keys)
                caught[f] = caught.get(f, 0) + 1
        else:
            qty = random.randint(3, 4)
            fish_type = "Đặc Biệt 🌟"
            for _ in range(qty):
                f = random.choice(special_keys)
                caught[f] = caught.get(f, 0) + 1

        for f_name, count in caught.items():
            inv[f_name] = inv.get(f_name, 0) + count

        user_data['inventory'] = inv
        save_data(player_inventory)

        result_lines = []
        for f_name, count in caught.items():
            category = "common" if f_name in common_keys else "special"
            info = FISH_POOL[category][f_name]
            result_lines.append(f"{info['emoji']} **{info['name']}**: `{count} con`")

        embed = discord.Embed(
            title="🎣 THẢ CẦN CÂU CÁ",
            description=(
                f"Oniichan {ctx.author.mention} vừa xách xô nước ra hồ!\n"
                f"Kéo lên được giỏ cá cực kỳ chất lượng:\n\n"
                f"✨ **Phân loại đàn:** `{fish_type}`\n"
                "----------------------------------------\n" + 
                "\n".join(result_lines)
            ),
            color=discord.Color.blue() if "Thường" in fish_type else discord.Color.gold()
        )
        embed.set_footer(text="Gõ 'p sell <tên_cá> all' để bán cá lấy tiền")
        await ctx.send(embed=embed)

    @commands.command(name="renewed")
    async def renewed_command(self, ctx):
        """Lệnh reset gia hạn server dành cho Owner và Subowner."""
        if str(ctx.author.id) != owner_id and str(ctx.author.id) not in subowner_id:
            return await ctx.send("❌ Oniichan hông có quyền gọi lệnh này đâu nè!")
            
        system_data = get_system_data()
        now = datetime.datetime.now(datetime.timezone.utc)
        next_time = now + datetime.timedelta(days=7)
        system_data["next_renew_time"] = next_time.isoformat()
        save_data(player_inventory)
        
        await ctx.send(f"✅ **Đã reset bộ đếm gia hạn VPS!** Mốc nhắc nhở tiếp theo sẽ diễn ra vào ngày: `{next_time.strftime('%d/%m/%Y %H:%M:%S')} UTC`")

    @cauca_command.error
    async def cauca_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            minutes = int(error.retry_after // 60)
            seconds = int(error.retry_after % 60)
            await ctx.send(f"⏳ **{ctx.author.mention}**, đợi **{minutes} phút {seconds} giây** nữa để thả cần tiếp nha! 🥰")


async def setup(bot):
    await bot.add_cog(SinkholeCog(bot))