import asyncio
import random
import string
import html
import datetime
import discord
from discord.ext import commands
from discord.ui import View, TextInput, Modal
import re 

from constants import KESLING_ICON, FISH_POOL, price, emoji_icon, DICE_EMOJIS, BAUCUA_MAP
from AIphcbot import get_user_data, save_data, load_quiz_questions, player_inventory, owner_id, subowner_id

class LobbyDirectBetModal(Modal, title="Xác nhận tiền cược"):
    amount_input = TextInput(label="Số tiền muốn cược", placeholder="Ví dụ: 10k, 5m, 10000", required=True)

    def __init__(self, lobby_view, choice):
        super().__init__()
        self.lobby_view = lobby_view
        self.choice = choice

    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        if user_id in self.lobby_view.active_bets:
            return await interaction.response.send_message("❌ Bạn đã đặt cược trong phiên này rồi!", ephemeral=True)

        from other import parse_amount
        bet_amount = parse_amount(self.amount_input.value.strip())

        if bet_amount <= 0:
            return await interaction.response.send_message("❌ Số tiền cược không hợp lệ.", ephemeral=True)

        if bet_amount > 10000000:
            return await interaction.response.send_message("❌ Tiền cược Tài Xỉu tối đa là **10,000,000**!", ephemeral=True)

        player = get_user_data(user_id)
        current_money = player.get("money", 0)

        if bet_amount > current_money:
            return await interaction.response.send_message(f"❌ Bạn không đủ tiền! Ví hiện tại: **{current_money:,} {KESLING_ICON}**.", ephemeral=True)

        player["money"] -= bet_amount
        save_data(player_inventory)

        self.lobby_view.active_bets[user_id] = {
            "choice": self.choice,
            "amount": bet_amount,
            "display_name": interaction.user.display_name,
            "mention": interaction.user.mention
        }
        await interaction.response.send_message(f"✅ Đặt cược thành công **{bet_amount:,}**!", ephemeral=True)
        await self.lobby_view.refresh_lobby_msg()


class LobbyNumberBetModal(Modal, title="Cược Số Chính Xác (3-18)"):
    number_input = TextInput(label="Nhập một số chính xác (3 đến 18)", placeholder="Ví dụ: 10", required=True, max_length=2)
    amount_input = TextInput(label="Số tiền muốn cược", placeholder="Ví dụ: 5k, 10m", required=True)

    def __init__(self, lobby_view):
        super().__init__()
        self.lobby_view = lobby_view

    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        if user_id in self.lobby_view.active_bets:
            return await interaction.response.send_message("❌ Bạn đã đặt cược trong phiên này rồi!", ephemeral=True)

        try:
            num = int(self.number_input.value.strip())
            if not (3 <= num <= 18): raise ValueError
        except ValueError:
            return await interaction.response.send_message("❌ Số đặt cược phải từ 3 đến 18.", ephemeral=True)

        from other import parse_amount
        bet_amount = parse_amount(self.amount_input.value.strip())

        if bet_amount <= 0:
            return await interaction.response.send_message("❌ Số tiền cược không hợp lệ.", ephemeral=True)

        if bet_amount > 10000000:
            return await interaction.response.send_message("❌ Tiền cược Tài Xỉu tối đa là **10,000,000**!", ephemeral=True)

        player = get_user_data(user_id)
        current_money = player.get("money", 0)

        if bet_amount > current_money:
            return await interaction.response.send_message(f"❌ Bạn không đủ tiền!", ephemeral=True)

        player["money"] -= bet_amount
        save_data(player_inventory)

        self.lobby_view.active_bets[user_id] = {
            "choice": num,
            "amount": bet_amount,
            "display_name": interaction.user.display_name,
            "mention": interaction.user.mention
        }
        await interaction.response.send_message(f"✅ Đặt cược thành công **{bet_amount:,}**!", ephemeral=True)
        await self.lobby_view.refresh_lobby_msg()


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
        lobby_display = "\n".join([f"• **{i['display_name']}**: cược **{i['amount']:}** {KESLING_ICON} vào **{str(i['choice']).upper()}**" for i in self.active_bets.values()]) if self.active_bets else "*Chưa có ai đặt cược.*"
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


class BaucuaBetModal(Modal, title="Đặt Cược Bầu Cua"):
    amount_input = TextInput(label="Số tiền muốn cược", placeholder="Ví dụ: 20k, 1m", required=True)

    def __init__(self, lobby_view, choice):
        super().__init__()
        self.lobby_view = lobby_view
        self.choice = choice

    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        if user_id in self.lobby_view.active_bets:
            return await interaction.response.send_message("❌ Bạn đã đặt cược trong phiên này rồi!", ephemeral=True)

        from other import parse_amount
        bet_amount = parse_amount(self.amount_input.value.strip())

        if bet_amount <= 0:
            return await interaction.response.send_message("❌ Số tiền cược không hợp lệ.", ephemeral=True)

        if bet_amount > 10000000:
            return await interaction.response.send_message("❌ Tiền cược Bầu Cua tối đa là **10,000,000**!", ephemeral=True)

        player = get_user_data(user_id)
        current_money = player.get("money", 0)

        if bet_amount > current_money:
            return await interaction.response.send_message(f"❌ Bạn không đủ tiền!", ephemeral=True)

        player["money"] -= bet_amount
        save_data(player_inventory)

        self.lobby_view.active_bets[user_id] = {
            "choice": self.choice,
            "amount": bet_amount,
            "display_name": interaction.user.display_name,
            "mention": interaction.user.mention
        }
        await interaction.response.send_message(f"✅ Đặt cược thành công **{bet_amount:,}**!", ephemeral=True)
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
        lobby_display = "\n".join([f"• **{i['display_name']}**: cược **{i['amount']:}** {KESLING_ICON} vào {BAUCUA_MAP[i['choice']]['emoji']} **{BAUCUA_MAP[i['choice']]['name']}**" for i in self.active_bets.values()]) if self.active_bets else "*Chưa có ai đặt cược.*"
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


class RussianRouletteJoinView(View):
    def __init__(self, author, bet_amount, session_id):
        super().__init__(timeout=60)
        self.author = author
        self.bet_amount = bet_amount
        self.session_id = session_id
        self.players = {}
        self.message = None
        self.is_closed = False

    def generate_embed(self, time_remaining=None):
        embed = discord.Embed(
            title="🔫 SẢNH CÒ QUAY NGA (DEATHMATCH) 🔫",
            description=(
                f"**Mức cược tham gia bắt buộc:** **{self.bet_amount:}** {KESLING_ICON}\n"
                "**Luật chơi:**\n"
                "• Toàn bộ người chơi sẽ đặt cược cùng số tiền.\n"
                "• Sảnh chờ kết thúc, người chơi sẽ bấm nút bóp cò tuần tự theo lượt.\n"
                "• Người bị bắn trúng sẽ bị loại. Người sống sót cuối cùng ăn trọn quỹ thưởng!\n\n"
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
        await interaction.response.send_message(f"✅ Cậu gia nhập sảnh tử thần thành công!", ephemeral=True)
        try:
            await self.message.edit(embed=self.generate_embed(time_remaining=None))
        except Exception:
            pass

class RussianRouletteGameView(View):
    def __init__(self, duel_list, original_players_dict, bet_amount, session_id):
        super().__init__(timeout=180)
        self.duel_list = duel_list
        self.original_players_dict = original_players_dict
        self.bet_amount = bet_amount
        self.session_id = session_id
        self.chambers = 6
        self.bullet_index = random.randint(1, 6)
        self.current_chamber_pointer = 1
        self.step = 0
        self.logs = [
            f"🔥 **Trận đấu súng bắt đầu!** Tổng số đấu sĩ: {len(duel_list)}",
            f"🔫 Viên đạn chết chóc đã nằm trong 1 trong 6 ổ đạn."
        ]

    def get_current_player_id(self):
        return self.duel_list[self.step % len(self.duel_list)]

    def generate_embed(self):
        current_player_id = self.get_current_player_id()
        current_name = self.original_players_dict[current_player_id]
        
        embed = discord.Embed(
            title="🎯 LƯỢT BÓP CÒ SÚNG TRỰC TIẾP",
            description=f"👉 Lượt hiện tại: <@{current_player_id}> (**{current_name}**)\n*Vui lòng nhấn nút dưới đây để kề súng vào đầu và bóp cò...*",
            color=discord.Color.red()
        )
        embed.add_field(name="📜 Nhật ký trận đấu", value="\n".join(self.logs[-8:]), inline=False)
        return embed

    @discord.ui.button(label="BÓP CÒ! 🔫", style=discord.ButtonStyle.danger, custom_id="trigger_shoot")
    async def shoot_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        current_player_id = self.get_current_player_id()
        if str(interaction.user.id) != current_player_id:
            return await interaction.response.send_message("❌ Không phải lượt của cậu! Đừng bấm bậy nha.", ephemeral=True)

        await interaction.response.defer()
        player_name = self.original_players_dict[current_player_id]
        self.logs.append(f"⏱️ **Lượt {self.step+1}:** Đấu sĩ **{player_name}** bóp cò...")

        if self.current_chamber_pointer == self.bullet_index:
            self.logs.append(f"💥 **ĐOÀNG!** Đầu óc **{player_name}** nổ tung! Bị LOẠI.")
            self.duel_list.remove(current_player_id)
            self.chambers = 6
            self.bullet_index = random.randint(1, 6)
            self.current_chamber_pointer = 1
        else:
            self.logs.append(f"❌ *Cạch!* Súng không nổ! **{player_name}** sống sót qua lượt.")
            self.chambers -= 1
            self.current_chamber_pointer += 1
            self.step += 1

        if len(self.duel_list) == 1:
            self.stop()
            winner_id = self.duel_list[0]
            winner_name = self.original_players_dict[winner_id]
            
            total_players_count = len(self.original_players_dict)
            total_pool = total_players_count * self.bet_amount
            bonus_profit = int((total_players_count - 1) * self.bet_amount * 0.25)
            prize = total_pool + bonus_profit

            winner_data = get_user_data(winner_id)
            winner_data["money"] = winner_data.get("money", 0) + prize
            save_data(player_inventory)

            for child in self.children:
                child.disabled = True
            await interaction.message.edit(embed=self.generate_embed(), view=self)

            final_embed = discord.Embed(
                title="👑 ĐẤU SĨ SỐNG SÓT DUY NHẤT 👑",
                description=(
                    f"🎉 Xin chúc mừng đấu sĩ kiên cường <@{winner_id}> (**{winner_name}**)!\n"
                    f"Cậu đã thắng cuộc chơi cân não này.\n\n"
                    f"💰 **Quỹ tiền thưởng nhận được:** **{prize:,}** {KESLING_ICON}"
                ),
                color=discord.Color.gold()
            )
            final_embed.set_footer(text=f"Phiên đấu: {self.session_id} | Hoàn tất.")
            return await interaction.channel.send(embed=final_embed)

        await interaction.message.edit(embed=self.generate_embed(), view=self)


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


class SnakeGameView(View):
    def __init__(self, author, money_icon):
        super().__init__(timeout=300)
        self.author = author
        self.money_icon = money_icon
        self.width = 16  
        self.height = 12
        self.snake = [(7, 5), (7, 6), (7, 7)]
        self.direction = (0, -1)
        self.score = 0
        self.game_over = False
        self.food = self.spawn_food()
        self.message = None
        self.loop_task = None

    async def start_loop(self):
        self.loop_task = asyncio.create_task(self.game_loop())

    async def game_loop(self):
        while not self.game_over:
            await asyncio.sleep(1) 
            if self.game_over:
                break
            await self.step_game_logic()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ Đây không phải lượt chơi của cậu!", ephemeral=True)
            return False
        return True

    def spawn_food(self):
        while True:
            pos = (random.randint(0, self.width - 1), random.randint(0, self.height - 1))
            if pos not in self.snake:
                return pos

    def generate_render(self):
        if self.game_over:
            kesling_reward = self.score * 10
            embed = discord.Embed(
                title="🪦 GAME OVER - RẮN CHẾT RỒI!",
                description=f"Oniichan đã tử trận!\n\n🍎 **Số điểm đạt được:** `{self.score}`\n💰 **Tiền thưởng nhận được:** **{kesling_reward:,}** {self.money_icon}",
                color=discord.Color.red()
            )
            return embed

        grid = [["." for _ in range(self.width)] for _ in range(self.height)]
        
        fx, fy = self.food
        grid[fy][fx] = "O"  

        for idx, (sx, sy) in enumerate(self.snake):
            if idx == 0:
                grid[sy][sx] = "X"  
            else:
                grid[sy][sx] = "#"  

        map_render = "\n".join([" ".join(row) for row in grid])
        map_text = f"```\n{map_render}\n```"
        
        embed = discord.Embed(
            title="🐍 MINIGAME SNAKE CONSOLE 🐍",
            description=map_text,
            color=discord.Color.green()
        )
        embed.add_field(name="🏆 Điểm số", value=f"`{self.score}` điểm (= {self.score * 10:,} {self.money_icon})")
        embed.set_footer(text="Bấm các nút điều hướng bên dưới để đổi hướng đi!")
        return embed

    async def step_game_logic(self):
        hx, hy = self.snake[0]
        dx, dy = self.direction
        new_head = (hx + dx, hy + dy)

        if (new_head[0] < 0 or new_head[0] >= self.width or 
            new_head[1] < 0 or new_head[1] >= self.height or 
            new_head in self.snake):
            self.game_over = True
            
            kesling_reward = self.score * 10
            user_data = get_user_data(str(self.author.id))
            user_data["money"] = user_data.get("money", 0) + kesling_reward
            save_data(player_inventory)

            for child in self.children:
                child.disabled = True
            self.stop()
            if self.loop_task:
                self.loop_task.cancel()
            try:
                await self.message.edit(embed=self.generate_render(), view=self)
            except Exception:
                pass
            return

        self.snake.insert(0, new_head)

        if new_head == self.food:
            self.score += 1
            self.food = self.spawn_food()
        else:
            self.snake.pop()

        try:
            await self.message.edit(embed=self.generate_render(), view=self)
        except Exception:
            pass

    @discord.ui.button(label="🔼", style=discord.ButtonStyle.primary, row=0)
    async def up(self, interaction: discord.Interaction, button: discord.Button):
        if self.direction != (0, 1):
            self.direction = (0, -1)
        await interaction.response.defer()

    @discord.ui.button(label="◀️", style=discord.ButtonStyle.primary, row=1)
    async def left(self, interaction: discord.Interaction, button: discord.Button):
        if self.direction != (1, 0):
            self.direction = (-1, 0)
        await interaction.response.defer()

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.primary, row=1)
    async def right(self, interaction: discord.Interaction, button: discord.Button):
        if self.direction != (-1, 0):
            self.direction = (1, 0)
        await interaction.response.defer()

    @discord.ui.button(label="🔽", style=discord.ButtonStyle.primary, row=2)
    async def down(self, interaction: discord.Interaction, button: discord.Button):
        if self.direction != (0, -1):
            self.direction = (0, 1)
        await interaction.response.defer()


class SinkholeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id != 1401577898338684988:
            return

        content = message.content
        
        custom_dices = re.findall(re.escape("msb_dice_") + r"(\d)", content)
        unicode_map = {"⚀": 1, "⚁": 2, "⚂": 3, "⚃": 4, "⚄": 5, "⚅": 6}
        unicode_dices = [unicode_map[char] for char in content if char in unicode_map]
        dice_results = [int(x) for x in custom_dices] if custom_dices else unicode_dices

        if len(dice_results) == 3:
            session_match = re.search(r"(?:ID phiên|Phiên|Session):\s*`?([a-zA-Z0-9_-]+)`?", content, re.IGNORECASE)
            session_id = session_match.group(1) if session_match else f"snap_{message.id}"
            total_score = sum(dice_results)
            timestamp = datetime.datetime.now().strftime("%H:%M %d/%m")
            file_name = f"dice_data_{message.channel.id}.txt"
            with open(file_name, "a", encoding="utf-8") as f:
                f.write(f"{session_id},{dice_results[0]},{dice_results[1]},{dice_results[2]},{total_score},{timestamp}\n")
            return

        if "KẾT QUẢ VÁN #" in content and "Đèn đã chuyển sang:" in content:
            color_label = "unknown"
            if "XANH" in content or "🟢" in content:
                color_label = "XANH"
            elif "VÀNG" in content or "🟡" in content:
                color_label = "VÀNG"
            elif "ĐỎ" in content or "🔴" in content:
                color_label = "ĐỎ"
            elif "NỔ" in content or "⚡" in content or "💥" in content:
                color_label = "NỔ"

            if color_label != "unknown":
                timestamp = datetime.datetime.now().strftime("%H:%M %d/%m")
                file_name_gt = f"gt_data_{message.channel.id}.txt"
                with open(file_name_gt, "a", encoding="utf-8") as f:
                    f.write(f"{color_label},{timestamp}\n")

    @commands.command(name="checkseed", aliases=["tkseed", "thongke", "pthongke","tk"])
    async def check_seed_command(self, ctx):
        file_name = f"dice_data_{ctx.channel.id}.txt"
        try:
            with open(file_name, "r", encoding="utf-8") as f:
                lines = [line for line in f if line.strip()]
        except FileNotFoundError:
            return await ctx.send("📊 **Tư liệu trống!** Kênh này chưa thu thập được phiên Tài Xỉu nào hết.")

        if not lines:
            return await ctx.send("📊 Hiện tại dữ liệu của kênh này đang trống, chờ phiên tiếp theo nha.")

        total_sessions = len(lines)
        tai_count = 0
        xiu_count = 0
        chan_count = 0
        le_count = 0
        
        triple_3_counter = 0
        triple_18_counter = 0
        all_parsed_sessions = []

        for line in lines:
            parts = line.strip().split(",")
            if len(parts) < 5:
                continue
            
            d1, d2, d3, total = int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4])
            v_timestamp = parts[5] if len(parts) >= 6 else "Không rõ"
            
            if total >= 11:
                tai_count += 1
                tx_label = "Tài"
            else:
                xiu_count += 1
                tx_label = "Xỉu"
                
            if total % 2 == 0:
                chan_count += 1
                cl_label = "Chẵn"
            else:
                le_count += 1
                cl_label = "Lẻ"
            
            if total == 3:
                triple_3_counter += 1
            elif total == 18:
                triple_18_counter += 1

            all_parsed_sessions.append(f"<{v_timestamp}> ➔ {d1}-{d2}-{d3} ({total}) ➔ **{tx_label}** / **{cl_label}**")

        recent_sessions = all_parsed_sessions[-10:]

        tai_pct = (tai_count / total_sessions) * 100 if total_sessions else 0
        xiu_pct = (xiu_count / total_sessions) * 100 if total_sessions else 0
        chan_pct = (chan_count / total_sessions) * 100 if total_sessions else 0
        le_pct = (le_count / total_sessions) * 100 if total_sessions else 0

        embed = discord.Embed(
            title=f"📊 PHÂN TÍCH SEED XÚC XẮC - KÊNH #{ctx.channel.name}",
            description=f"Tổng số phiên đã ghi nhận tại kênh này: **{total_sessions}**",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="📈 Tỷ lệ Tài / Xỉu", 
            value=f"• **Tài:** {tai_count} ({tai_pct:.1f}%)\n• **Xỉu:** {xiu_count} ({xiu_pct:.1f}%)", 
            inline=True
        )
        embed.add_field(
            name="📈 Tỷ lệ Chẵn / Lẻ", 
            value=f"• **Chẵn:** {chan_count} ({chan_pct:.1f}%)\n• **Lẻ:** {le_count} ({le_pct:.1f}%)", 
            inline=True
        )
        
        embed.add_field(name="🚨 Số ván ra 3 (1-1-1)", value=f"**{triple_3_counter} ván**", inline=True)
        embed.add_field(name="🚨 Số ván ra 18 (6-6-6)", value=f"**{triple_18_counter} ván**", inline=True)
        
        history_display = "\n".join(recent_sessions) if recent_sessions else "*Chưa có lịch sử*"
        embed.add_field(name="📜 Dòng chảy lịch sử (Mới nhất tự động cuộn xuống đáy ↓)", value=history_display, inline=False)
        
        await ctx.send(embed=embed)

    @commands.command(name="thongkegt", aliases=["tkgt", "pkgt"])
    async def thong_ke_giao_thong_command(self, ctx):
        file_name = f"gt_data_{ctx.channel.id}.txt"
        try:
            with open(file_name, "r", encoding="utf-8") as f:
                lines = [line for line in f if line.strip()]
        except FileNotFoundError:
            return await ctx.send("🚦 **Tư liệu trống!** Kênh này chưa thu thập được phiên Đèn Giao Thông nào.")

        if not lines:
            return await ctx.send("🚦 Hiện tại dữ liệu Đèn Giao Thông của kênh này đang trống.")

        total_sessions = len(lines)
        xanh_count = 0
        vang_count = 0
        do_count = 0
        no_count = 0
        all_parsed_sessions = []

        for line in lines:
            parts = line.strip().split(",")
            if len(parts) < 2:
                continue
            
            color = parts[0]
            v_timestamp = parts[1]

            if color == "XANH":
                xanh_count += 1
                emoji = "🟢"
            elif color == "VÀNG":
                vang_count += 1
                emoji = "🟡"
            elif color == "ĐỎ":
                do_count += 1
                emoji = "🔴"
            elif color == "NỔ":
                no_count += 1
                emoji = "⚡"

            all_parsed_sessions.append(f"<{v_timestamp}> ➔ {emoji} **{color}**")

        recent_sessions = all_parsed_sessions[-10:]

        xanh_pct = (xanh_count / total_sessions) * 100 if total_sessions else 0
        vang_pct = (vang_count / total_sessions) * 100 if total_sessions else 0
        do_pct = (do_count / total_sessions) * 100 if total_sessions else 0
        no_pct = (no_count / total_sessions) * 100 if total_sessions else 0

        embed = discord.Embed(
            title=f"🚦 PHÂN TÍCH ĐÈN GIAO THÔNG - KÊNH #{ctx.channel.name}",
            description=f"Tổng số phiên đã ghi nhận tại kênh này: **{total_sessions}**",
            color=discord.Color.green()
        )
        embed.add_field(
            name="📊 Tỷ lệ thực tế", 
            value=(
                f"• 🟢 **Xanh:** {xanh_count} ({xanh_pct:.1f}%) | *Mục tiêu: 50%*\n"
                f"• 🟡 **Vàng:** {vang_count} ({vang_pct:.1f}%) | *Mục tiêu: 30%*\n"
                f"• 🔴 **Đỏ:** {do_count} ({do_pct:.1f}%) | *Mục tiêu: 15%*\n"
                f"• ⚡ **Nổ:** {no_count} ({no_pct:.1f}%) | *Mục tiêu: 5%*"
            ), 
            inline=False
        )
        
        history_display = "\n".join(recent_sessions) if recent_sessions else "*Chưa có lịch sử*"
        embed.add_field(name="📜 Dòng chảy lịch sử (Mới nhất tự động cuộn xuống đáy ↓)", value=history_display, inline=False)
        
        await ctx.send(embed=embed)
        
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

        view.is_closed = True
        for item in view.children:
            item.disabled = True
        try:
            await msg.edit(view=view)
        except Exception:
            pass

        rolling_embed = discord.Embed(
            title="🎲 LẮC BÁT - PHIÊN ĐANG CHẠY 🎲",
            description="Thời gian đặt cược đã kết thúc! Vui lòng đợi trong giây lát...",
            color=discord.Color.blurple()
        )
        rolling_embed.set_thumbnail(url="https://i.imgur.com/KBy6E9O.gif")

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
                await msg.edit(embed=rolling_embed, view=None)
            except Exception:
                pass
            await asyncio.sleep(1.6)

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

        await msg.edit(embed=result_embed, view=None)

    @commands.command(name="baucua", aliases=["bc"])
    async def baucua_command(self, ctx):
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

        result_embed = discord.Embed(title="🧉 KẾT QUẢ BẦU CUA TÔM CÁ MAKERS", color=discord.Color.green())
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
    async def coquay_command(self, ctx, bet_amount_str: str = None):
        if bet_amount_str is None:
            return await ctx.send("❌ Dùng lệnh: `p coquay <số_tiền_cược>` để thiết lập phòng chơi.")

        from other import parse_amount
        bet_amount = parse_amount(bet_amount_str)

        if bet_amount <= 0:
            return await ctx.send("❌ Số tiền cược không hợp lệ.")

        if bet_amount > 100000000:
            return await ctx.send("❌ Tiền cược Cò Quay tối đa là **100,000,000** (100m)!")

        user_id = str(ctx.author.id)
        player_data = get_user_data(user_id)
        if player_data.get("money", 0) < bet_amount:
            return await ctx.send(f"❌ Ví của bạn hông đủ tiền khởi tạo sảnh cược **{bet_amount:,} {KESLING_ICON}**!")

        session_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        view = RussianRouletteJoinView(ctx.author, bet_amount, session_id)
        
        player_data["money"] -= bet_amount
        save_data(player_inventory)
        view.players[user_id] = ctx.author.display_name

        embed = view.generate_embed(time_remaining=45)
        msg = await ctx.send(embed=embed, view=view)
        view.message = msg

        countdown_time = 45
        while countdown_time > 0:
            await asyncio.sleep(5)
            countdown_time -= 5
            if countdown_time > 0:
                try: await msg.edit(embed=view.generate_embed(time_remaining=countdown_time))
                except Exception: pass

        view.is_closed = True
        for item in view.children: item.disabled = True
        try: await msg.edit(view=view)
        except Exception: pass

        active_ids = list(view.players.keys())
        total_players_count = len(active_ids)
        if total_players_count < 2:
            for uid in active_ids:
                p_data = get_user_data(uid)
                p_data["money"] = p_data.get("money", 0) + bet_amount
            save_data(player_inventory)
            return await msg.edit(content="❌ **Sảnh hủy:** Hông có ai chịu cược đối đầu với oniichan cả, đã hoàn tiền cược!", embed=None, view=None)

        logs = []
        original_players_dict = dict(view.players)
        chambers = 6
        bullet_index = random.randint(1, chambers)
        current_chamber_pointer = 1

        logs.append(f"🔥 **Sảnh đấu súng bắt đầu!** Tổng cộng có {total_players_count} đấu sĩ.")
        logs.append(f"🔫 Viên đạn chết chóc đã nạp vào 1 trong {chambers} ổ đạn.")

        duel_list = list(active_ids)
        random.shuffle(duel_list)

        step = 0
        while len(duel_list) > 1:
            current_player_id = duel_list[step % len(duel_list)]
            player_name = original_players_dict[current_player_id]
            logs.append(f"⏱️ **Lượt {step+1}:** Đấu sĩ **{player_name}** áp súng lên thái dương và bóp cò...")
            
            if current_chamber_pointer == bullet_index:
                logs.append(f"💥 **ĐOÀNG!** Đầu óc **{player_name}** nổ tung! Anh ta đã bị LOẠI.")
                duel_list.remove(current_player_id)
                chambers = 6
                bullet_index = random.randint(1, chambers)
                current_chamber_pointer = 1
            else:
                logs.append(f"❌ *Cạch!* Thật may mắn, súng hông nổ! **{player_name}** sống sót qua lượt.")
                chambers -= 1
                current_chamber_pointer += 1
                step += 1

            game_embed = discord.Embed(title="🔫 DIỄN BIẾN SÚNG NỔ 🔫", description="\n".join(logs[-8:]), color=discord.Color.red())
            await msg.edit(embed=game_embed)
            await asyncio.sleep(2.5)

        winner_id = duel_list[0]
        winner_name = original_players_dict[winner_id]
        winner_mention = f"<@{winner_id}>"

        total_pool = total_players_count * bet_amount
        bonus_profit = int((total_players_count - 1) * bet_amount * 0.25)
        prize = total_pool + bonus_profit

        winner_data = get_user_data(winner_id)
        winner_data["money"] = winner_data.get("money", 0) + prize
        save_data(player_inventory)

        final_embed = discord.Embed(
            title="👑 ĐẤU SĨ SỐNG SÓT DUY NHẤT 👑",
            description=(
                f"🎉 Xin chúc mừng đấu sĩ kiên cường {winner_mention} (**{winner_name}**)!\n"
                f"Anh ta là người sống sót duy nhất sau loạt bóp cò súng tàn bạo.\n\n"
                f"💰 **Quỹ tiền thưởng nhận được (Đã tối ưu lạm phát):** **{prize:,}** {KESLING_ICON}\n"
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
        session_id = "ERR-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))

        for q in questions_data:
            level_prize = local_prizes[current_level]
            question_text = html.unescape(q["question"])
            original_choices = [html.unescape(c) for c in q["choices"]]
            original_correct_index = q["correct_index"]

            indexed_choices = list(enumerate(original_choices))
            random.shuffle(indexed_choices)
            choices_text = [choice for _, choice in indexed_choices]
            correct_index = next(new_idx for new_idx, (old_idx, _) in enumerate(indexed_choices) if old_idx == original_correct_index)

            choices_str = "\n".join([f"**{chr(65+i)}.** {choice}" for i, choice in enumerate(choices_text)])

            q_embed = discord.Embed(
                title=f"Câu Hỏi {current_level + 1}/10 (Giải thưởng: {level_prize:,} {KESLING_ICON})",
                description=f"**{question_text}**\n",
                color=discord.Color.blue()
            )
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

    @commands.command(name="snake", aliases=["ransanmoi"])
    async def snake_command(self, ctx):
        view = SnakeGameView(ctx.author, KESLING_ICON)
        embed = view.generate_render()
        msg = await ctx.send(embed=embed, view=view)
        view.message = msg
        await view.start_loop() 

    @commands.command(name="renewed")
    async def renewed_command(self, ctx):
        if str(ctx.author.id) != owner_id and str(ctx.author.id) not in subowner_id:
            return await ctx.send("❌ Oniichan hông có quyền gọi lệnh này đâu nè!")
            
        from AIphcbot import get_system_data
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