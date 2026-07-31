# whoisspy.py
import asyncio
import random
import math
import os
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Modal, TextInput, Select, Button

try:
    from AIphcbot import owner_id, subowner_id, get_user_data, save_data, player_inventory
except ImportError:
    owner_id = "0"
    subowner_id = []
    def get_user_data(uid): return {"money": 0}
    def save_data(data): pass
    player_inventory = {}

ASSETS_DIR = "/home/container/assets"

def get_asset_file(image_name: str):
    """Safely retrieves image files from /home/container/assets"""
    path = os.path.join(ASSETS_DIR, image_name)
    if os.path.exists(path):
        return discord.File(path, filename=image_name)
    return None

async def send_fancy_event_message(ctx, embed: discord.Embed, image_name: str = None, view: discord.ui.View = None):
    """Sends a fancy embed with image attachment from /home/container/assets"""
    if image_name:
        file = get_asset_file(image_name)
        if file:
            embed.set_image(url=f"attachment://{image_name}")
            return await ctx.channel.send(embed=embed, file=file, view=view)
    return await ctx.channel.send(embed=embed, view=view)

# ==============================================================================
#                               DATA & CONSTANTS
# ==============================================================================

DEFAULT_WORD_PAIRS = [
    ("Cà phê", "Trà sữa"), ("Mèo", "Chó"), ("Máy tính", "Điện thoại"),
    ("Bóng đá", "Bóng rổ"), ("Mặt trời", "Mặt trăng"), ("Máy bay", "Tàu hỏa"),
    ("Sách", "Vở"), ("Táo", "Lê"), ("Bún chả", "Phở"), ("Bánh mì", "Hamburger"),
    ("Bikini", "Áo tắm"), ("Trà đá", "Nước mía"), ("Bút bi", "Bút chì"),
    ("Xe máy", "Xe đạp"), ("Đồng hồ", "Vòng tay"), ("Mưa", "Tuyết"),
    ("Bia", "Rượu"), ("Giày", "Dép"), ("Áo sơ mi", "Áo thun"),
    ("Mì tôm", "Hủ tiếu"), ("Nhà lầu", "Biệt thự"), ("Xem phim", "Nghe nhạc"),
    ("Ca sĩ", "Diễn viên"), ("Biển", "Sông"), ("Núi", "Đồi"),
    ("Bún đậu mắm tôm", "Bún riêu"), ("Son môi", "Phấn phủ"), ("Kính râm", "Kính cận"),
    ("Khách sạn", "Resort"), ("Răng giả", "Hàm niềng"), ("Vàng", "Kim cương"),
    ("Mặt nạ", "Khẩu trang"), ("Tai nghe", "Loa thùng"), ("Tủ lạnh", "Máy giặt"),
    ("Mút xốp", "Bông bón"), ("Kem đánh răng", "Nước súc miệng"), ("Máy ảnh", "Cam quay phim"),
    ("Bánh trung thu", "Bánh chưng"), ("Sô cô la", "Kẹo dẻo"), ("Cây kem", "Sữa chua")
]

CROSS_EXAM_QUESTIONS = [
    "Vật/Khái niệm này có hình dáng, màu sắc hoặc trạng thái cơ bản như thế nào?",
    "Vật/Khái niệm này thường được con người sử dụng khi nào hoặc ở đâu?",
    "Lợi ích hoặc vai trò nổi bật nhất của vật/khái niệm này là gì?",
    "Cảm giác của bạn khi tiếp xúc hoặc sở hữu vật/khái niệm này là gì?",
    "Giá thành hoặc công sức để có được vật/khái niệm này là đắt hay rẻ?",
    "Người lớn hay trẻ em thường thích sử dụng vật/khái niệm này hơn?",
    "Vật/Khái niệm này có thể cầm nắm trên tay được không hay là vô hình?",
    "Nếu thiếu đi vật/khái niệm này trong 1 ngày, cuộc sống bạn sẽ ra sao?",
    "Vật/Khái niệm này có mùi vị hay âm thanh đặc trưng nào không?",
    "Vật/Khái niệm này xuất hiện nhiều ở vùng nông thôn hay thành thị?",
    "Bạn thường thấy vật/khái niệm này vào ban ngày hay ban đêm?",
    "Nó có liên quan đến đồ ăn, thức uống hay sinh hoạt hàng ngày không?",
    "Vật/Khái niệm này có độ bền cao hay dễ bị hư hỏng/biến mất theo thời gian?",
    "Có cần phải dùng điện hoặc pin để vật/khái niệm này hoạt động không?",
    "Lần gần đây nhất bạn nhìn thấy hoặc sử dụng nó là khi nào?",
    "Vật/Khái niệm này có thể làm bằng chất liệu gì (kim loại, nhựa, chất lỏng...)?",
    "Hành động chính mà con người thực hiện với vật/khái niệm này là gì?",
    "Khi nhắc tới vật/khái niệm này, bạn nghĩ ngay tới mùa nào trong năm?",
    "Vật/Khái niệm này là sản phẩm của tự nhiên hay do con người tạo ra?",
    "Nếu được tặng vật/khái niệm này làm quà, bạn có vui không?"
]

# ==============================================================================
#                               MODALS & VIEWS
# ==============================================================================

class CustomWordModal(Modal, title="✍️ Nhập Cặp Từ Khóa Tùy Chỉnh"):
    word_civilian = TextInput(label="Từ khóa cho Dân Thường", placeholder="Ví dụ: Cà phê", required=True, max_length=30)
    word_spy = TextInput(label="Từ khóa cho Gián Điệp", placeholder="Ví dụ: Trà sữa", required=True, max_length=30)

    def __init__(self, lobby_view):
        super().__init__()
        self.lobby_view = lobby_view

    async def on_submit(self, interaction: discord.Interaction):
        w_civ = self.word_civilian.value.strip()
        w_spy = self.word_spy.value.strip()
        if w_civ.lower() == w_spy.lower():
            return await interaction.response.send_message("❌ Hai từ khóa không được giống nhau!", ephemeral=True)
        self.lobby_view.custom_pair = (w_civ, w_spy)
        await interaction.response.send_message("✅ Đã đặt cặp từ khóa bí mật thành công!", ephemeral=True)
        try: await interaction.message.edit(embed=self.lobby_view.generate_embed(), view=self.lobby_view)
        except Exception: pass


class SpySettingsModal(Modal, title="⚙️ Cài Đặt Game Gián Điệp"):
    minutes_input = TextInput(label="Số phút thảo luận mỗi ngày (1-10 phút)", placeholder="Mặc định: 3", required=True, max_length=2)
    cross_time_input = TextInput(label="Thời gian trả lời Hỏi Vặn (Giây)", placeholder="Mặc định: 40", required=True, max_length=3)

    def __init__(self, lobby_view):
        super().__init__()
        self.lobby_view = lobby_view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            mins = int(self.minutes_input.value.strip())
            ctime = int(self.cross_time_input.value.strip())
            if not (1 <= mins <= 10) or not (10 <= ctime <= 120): raise ValueError
        except ValueError:
            return await interaction.response.send_message("❌ Số phút (1-10), Hỏi vặn (10-120s)!", ephemeral=True)

        self.lobby_view.discussion_minutes = mins
        self.lobby_view.cross_exam_time = ctime
        await interaction.response.send_message("✅ Đã cập nhật cài đặt!", ephemeral=True)
        try: await interaction.message.edit(embed=self.lobby_view.generate_embed(), view=self.lobby_view)
        except Exception: pass


class CounterSpyInspectView(View):
    def __init__(self, counter_spy_id: int, spy_ids: list, alive_players: list, inspected_dict: dict):
        super().__init__(timeout=30)
        self.counter_spy_id = counter_spy_id
        self.spy_ids = spy_ids
        self.inspected_dict = inspected_dict

        options = [discord.SelectOption(label=p.display_name, value=str(p.id), emoji="🔍") for p in alive_players[:25] if p.id != counter_spy_id]
        select = Select(placeholder="🔍 Chọn người bạn muốn kiểm tra...", options=options)
        select.callback = self.inspect_callback
        self.add_item(select)

    async def inspect_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.counter_spy_id:
            return await interaction.response.send_message("❌ Bạn không phải Kẻ Phản Gián!", ephemeral=True)

        if self.inspected_dict.get("done"):
            return await interaction.response.send_message("❌ Hôm nay bạn đã dùng kỹ năng soi rồi!", ephemeral=True)

        target_id = int(interaction.data["values"][0])
        target_p = interaction.guild.get_member(target_id)
        self.inspected_dict["done"] = True

        if target_id in self.spy_ids:
            await interaction.response.send_message(f"🎯 **KẾT QUẢ SOI:** {target_p.mention} chính là **GIÁN ĐIỆP 🕵️**!", ephemeral=True)
        else:
            await interaction.response.send_message(f"🛡️ **KẾT QUẢ SOI:** {target_p.mention} **KHÔNG PHẢI** Gián Điệp!", ephemeral=True)


class SpyVotingView(View):
    def __init__(self, alive_players: list):
        super().__init__(timeout=60)
        self.alive_players = alive_players
        self.votes = {}
        self.page = 0
        self.per_page = 20
        self.update_components()

    def update_components(self):
        self.clear_items()
        start = self.page * self.per_page
        end = start + self.per_page
        current_batch = self.alive_players[start:end]

        options = [discord.SelectOption(label=p.display_name, value=str(p.id), emoji="🕵️") for p in current_batch]
        total_pages = math.ceil(len(self.alive_players) / self.per_page)

        select = Select(
            placeholder=f"🗳️ Chọn người nghi ngờ (Trang {self.page + 1}/{total_pages})...",
            min_values=1, max_values=1, options=options, row=0
        )
        select.callback = self.select_callback
        self.add_item(select)

        if self.page > 0:
            btn_prev = Button(label="◀ Trang Trước", style=discord.ButtonStyle.secondary, row=1)
            btn_prev.callback = self.prev_page
            self.add_item(btn_prev)

        if end < len(self.alive_players):
            btn_next = Button(label="▶ Trang Sau", style=discord.ButtonStyle.secondary, row=1)
            btn_next.callback = self.next_page
            self.add_item(btn_next)

        btn_skip = Button(label="⚪ Bỏ Phiếu Trắng", style=discord.ButtonStyle.danger, row=1)
        btn_skip.callback = self.skip_callback
        self.add_item(btn_skip)

    async def prev_page(self, interaction: discord.Interaction):
        self.page -= 1
        self.update_components()
        await interaction.response.edit_message(view=self)

    async def next_page(self, interaction: discord.Interaction):
        self.page += 1
        self.update_components()
        await interaction.response.edit_message(view=self)

    async def select_callback(self, interaction: discord.Interaction):
        voter_id = interaction.user.id
        if voter_id not in [p.id for p in self.alive_players]:
            return await interaction.response.send_message("❌ Bạn không còn sống!", ephemeral=True)
        if voter_id in self.votes:
            return await interaction.response.send_message("❌ Bạn đã bỏ phiếu rồi!", ephemeral=True)

        val = interaction.data["values"][0]
        self.votes[voter_id] = val
        target_member = interaction.guild.get_member(int(val))
        await interaction.response.send_message(f"🗳️ Đã bỏ phiếu nghi ngờ **{target_member.display_name}**!", ephemeral=True)

    async def skip_callback(self, interaction: discord.Interaction):
        voter_id = interaction.user.id
        if voter_id not in [p.id for p in self.alive_players]:
            return await interaction.response.send_message("❌ Bạn không còn sống!", ephemeral=True)
        if voter_id in self.votes:
            return await interaction.response.send_message("❌ Bạn đã bỏ phiếu rồi!", ephemeral=True)

        self.votes[voter_id] = "skip"
        await interaction.response.send_message("⚪ Bạn đã chọn **Bỏ phiếu trắng**!", ephemeral=True)


class SpyLobbyView(View):
    def __init__(self, host: discord.Member):
        super().__init__(timeout=300)
        self.host = host
        self.players = {host.id: host}
        self.custom_pair = None
        self.discussion_minutes = 3
        self.cross_exam_mode = False
        self.cross_exam_time = 40
        self.modified_mode = False
        self.game_started = False

    def generate_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🕵️ TRÒ CHƠI: AI LÀ GIÁN ĐIỆP (WHO IS THE SPY)",
            description=(
                "**Luật chơi thể thức Nhiều Ngày:**\n"
                "• Lần lượt từng người đưa ra câu mô tả/trả lời câu hỏi vặn.\n"
                f"• Cả nhóm có **{self.discussion_minutes} phút** thảo luận tìm Gián điệp.\n"
                "• **Phe Dân thắng:** Bắt hết Gián điệp.\n"
                "• **Phe Gián Điệp thắng:** Loại hết Dân thường.\n\n"
                "👉 Bấm **[🎉 Tham Gia]** bên dưới để gia nhập!"
            ),
            color=discord.Color.purple()
        )
        p_list = "\n".join([f"• {p.mention} (**{p.display_name}**)" for p in self.players.values()])
        embed.add_field(name=f"👥 Người Tham Gia ({len(self.players)} - Tối thiểu 4)", value=p_list, inline=False)
        
        custom_status = "✅ Cặp từ tùy chỉnh (Bí mật)" if self.custom_pair else "🎲 Mặc định"
        exam_status = f"🔥 BẬT ({self.cross_exam_time}s)" if self.cross_exam_mode else "❄️ TẮT"
        mod_status = "⚡ BẬT (Kẻ Phản Gián + Gợi Ý)" if self.modified_mode else "❄️ TẮT"
        
        embed.add_field(name="⚙️ Từ Khóa", value=custom_status, inline=True)
        embed.add_field(name="⏱️ Thảo Luận", value=f"**{self.discussion_minutes} phút**", inline=True)
        embed.add_field(name="❓ Hỏi Vặn", value=exam_status, inline=True)
        embed.add_field(name="🔀 Chế Độ Modified", value=mod_status, inline=False)
        return embed

    @discord.ui.button(label="Tham Gia / Rời Khỏi", style=discord.ButtonStyle.success, emoji="🎉", row=0)
    async def join_toggle(self, interaction: discord.Interaction, button: Button):
        user = interaction.user
        if user.id in self.players:
            if user.id == self.host.id: return await interaction.response.send_message("❌ Chủ phòng không thể rời sảnh!", ephemeral=True)
            del self.players[user.id]
            await interaction.response.send_message("🏃 Đã rời sảnh.", ephemeral=True)
        else:
            self.players[user.id] = user
            await interaction.response.send_message("🎉 Đã tham gia sảnh!", ephemeral=True)
        try: await interaction.message.edit(embed=self.generate_embed(), view=self)
        except Exception: pass

    @discord.ui.button(label="Modified: BẬT/TẮT", style=discord.ButtonStyle.primary, emoji="🔀", row=0)
    async def toggle_modified(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.host.id: return await interaction.response.send_message("❌ Chỉ chủ phòng!", ephemeral=True)
        self.modified_mode = not self.modified_mode
        status_str = "BẬT ⚡ (Kẻ Phản Gián + Gợi ý)" if self.modified_mode else "TẮT ❄️"
        await interaction.response.send_message(f"✅ Đã chuyển Chế Độ Modified sang: **{status_str}**", ephemeral=True)
        try: await interaction.message.edit(embed=self.generate_embed(), view=self)
        except Exception: pass

    @discord.ui.button(label="Hỏi Vặn: BẬT/TẮT", style=discord.ButtonStyle.secondary, emoji="❓", row=0)
    async def toggle_cross_exam(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.host.id: return await interaction.response.send_message("❌ Chỉ chủ phòng!", ephemeral=True)
        self.cross_exam_mode = not self.cross_exam_mode
        status_str = "BẬT 🔥" if self.cross_exam_mode else "TẮT ❄️"
        await interaction.response.send_message(f"✅ Đã chuyển Chế Độ Hỏi Vặn sang: **{status_str}**", ephemeral=True)
        try: await interaction.message.edit(embed=self.generate_embed(), view=self)
        except Exception: pass

    @discord.ui.button(label="Cặp Từ Custom", style=discord.ButtonStyle.secondary, emoji="✍️", row=1)
    async def set_custom_word(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.host.id: return await interaction.response.send_message("❌ Chỉ chủ phòng!", ephemeral=True)
        await interaction.response.send_modal(CustomWordModal(self))

    @discord.ui.button(label="Cài Đặt Game", style=discord.ButtonStyle.secondary, emoji="⚙️", row=1)
    async def set_config(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.host.id: return await interaction.response.send_message("❌ Chỉ chủ phòng!", ephemeral=True)
        await interaction.response.send_modal(SpySettingsModal(self))

    @discord.ui.button(label="BẮT ĐẦU GAME", style=discord.ButtonStyle.danger, emoji="🚀", row=1)
    async def start_game(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.host.id: return await interaction.response.send_message("❌ Chỉ chủ phòng!", ephemeral=True)
        if len(self.players) < 4: return await interaction.response.send_message("❌ Cần ít nhất 4 người chơi!", ephemeral=True)
        self.game_started = True
        for child in self.children: child.disabled = True
        try: await interaction.response.edit_message(embed=self.generate_embed(), view=self)
        except Exception: pass
        self.stop()

# ==============================================================================
#                               COG SYSTEM CLASS
# ==============================================================================

class WhoIsSpyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_games = {}

    @commands.hybrid_command(name="stopspy", aliases=["dungspy"], description="Dừng khẩn cấp ván Ai Là Gián Điệp đang diễn ra")
    async def stopspy(self, ctx):
        cid = ctx.channel.id
        if cid not in self.active_games:
            return await ctx.send("❌ Không có trận đấu Gián Điệp nào đang diễn ra trong kênh này!")

        game_data = self.active_games[cid]
        is_host = ctx.author.id == game_data["host_id"]
        is_admin = ctx.author.guild_permissions.manage_messages or str(ctx.author.id) in [owner_id] + subowner_id

        if not (is_host or is_admin):
            return await ctx.send("❌ Chỉ Chủ Phòng hoặc Admin mới có quyền dừng!", ephemeral=True)

        game_data["stopped"] = True
        embed = discord.Embed(title="🛑 TRẬN ĐẤU GIÁN ĐIỆP ĐÃ BỊ DỪNG KHẨN CẤP", description="Bảng công khai toàn bộ bí mật của trận đấu:", color=discord.Color.red())
        embed.add_field(name="📜 Cặp từ", value=f"• Dân: **{game_data['word_civ']}**\n• Sói/Gián: **{game_data['word_spy']}**", inline=False)
        embed.add_field(name="🕵️ Phe Gián Điệp", value=", ".join([p.mention for p in game_data["spies"]]) or "Không", inline=False)
        embed.add_field(name="👨‍🌾 Phe Dân", value=", ".join([p.mention for p in game_data["civs"]]) or "Không", inline=False)

        del self.active_games[cid]
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="whoisspy", aliases=["spy", "giandiep"], description="Trò chơi Ai Là Gián Điệp nhóm đông người")
    async def whoisspy(self, ctx):
        cid = ctx.channel.id
        if cid in self.active_games: return await ctx.send("❌ Đã có một trận đấu đang diễn ra trong kênh này!")

        lobby_view = SpyLobbyView(ctx.author)
        await ctx.send(embed=lobby_view.generate_embed(), view=lobby_view)
        await lobby_view.wait()

        if not lobby_view.game_started: return await ctx.send("⏰ **Sảnh game đã hết thời gian chờ hoặc bị hủy!**")

        all_players = list(lobby_view.players.values())
        total_players = len(all_players)
        discussion_mins = lobby_view.discussion_minutes
        cross_exam_mode = lobby_view.cross_exam_mode
        cross_time = lobby_view.cross_exam_time
        modified_mode = lobby_view.modified_mode

        word_civ, word_spy = lobby_view.custom_pair or random.choice(DEFAULT_WORD_PAIRS)
        num_spies = 2 if total_players >= 8 else 1
        spies = random.sample(all_players, num_spies)
        spy_ids = [s.id for s in spies]

        alive_players = list(all_players)
        alive_spies = list(spies)
        alive_civs = [p for p in all_players if p.id not in spy_ids]

        counter_spy = random.choice(alive_civs) if modified_mode and len(alive_civs) >= 2 else None

        game_data = {"type": "spy", "host_id": ctx.author.id, "stopped": False, "word_civ": word_civ, "word_spy": word_spy, "spies": spies, "civs": alive_civs, "counter_spy": counter_spy}
        self.active_games[cid] = game_data

        await ctx.channel.send("🕵️ **Đang phát từ khóa bí mật cho từng người qua DM...**")
        confirmed_civ = random.choice(alive_civs) if modified_mode else None

        for p in all_players:
            is_spy = p.id in spy_ids
            is_counter = counter_spy and p.id == counter_spy.id

            secret_word = word_spy if (is_spy or is_counter) else word_civ

            desc_text = (
                f"🤫 **Từ khóa của bạn là:** **{secret_word}**\n\n"
                "⚠️ *Lưu ý: Hệ thống KHÔNG thông báo bạn là Dân Thường hay Gián Điệp! "
                "Hãy lắng nghe câu mô tả của người khác để phát hiện xem từ của mình có khác biệt không!*"
            )

            if is_counter:
                desc_text += "\n\n💡 *(Bạn là Kẻ Phản Gián! Cầm từ Gián Điệp nhưng thuộc Phe Dân. Hãy dùng nút Soi mỗi ngày để giúp Dân)*"
            elif not is_spy and modified_mode and confirmed_civ:
                desc_text += f"\n\n💡 **GỢI Ý:** Người chơi {confirmed_civ.mention} chắc chắn là **DÂN THƯỜNG**!"

            try: await p.send(embed=discord.Embed(title="🤫 TỪ KHÓA BÍ MẬT CỦA BẠN", description=desc_text, color=discord.Color.blue()))
            except Exception: pass

        day_count = 1
        while True:
            if game_data.get("stopped"): break
            await ctx.channel.send(f"\n☀️ ==================== **NGÀY THỨ {day_count}** ==================== ☀️")

            if counter_spy and counter_spy in alive_players:
                inspected_dict = {"done": False}
                cs_view = CounterSpyInspectView(counter_spy.id, spy_ids, alive_players, inspected_dict)
                cs_msg = await ctx.channel.send(f"🕵️‍♂️ **Kẻ Phản Gián ({counter_spy.mention})**: Bấm nút dưới đây để SOI 1 người!", view=cs_view)
                await asyncio.sleep(15)
                for c in cs_view.children: c.disabled = True
                try: await cs_msg.edit(view=cs_view)
                except Exception: pass

            if game_data.get("stopped"): break
            await ctx.channel.send("📢 **LẦN LƯỢT ĐƯA RA CÂU MÔ TẢ TỪ KHÓA:**")
            
            for idx, p in enumerate(list(alive_players), start=1):
                if game_data.get("stopped"): break
                if p not in alive_players: continue

                if cross_exam_mode:
                    q_prompt = random.choice(CROSS_EXAM_QUESTIONS)
                    await ctx.channel.send(f"👉 **Lượt {idx}/{len(alive_players)}:** {p.mention}\n❓ **CÂU HỎI VẶN:** *{q_prompt}*\n⏱️ *Bạn có **{cross_time} giây** để trả lời, nếu không sẽ **BỊ TREO CỔ NGAY**!*")
                    def check_msg(m): return m.author.id == p.id and m.channel.id == ctx.channel.id

                    try:
                        reply_m = await self.bot.wait_for('message', check=check_msg, timeout=cross_time)
                        await ctx.channel.send(f"✅ {p.mention} đã trả lời: *\"{reply_m.content}\"*")
                    except asyncio.TimeoutError:
                        await ctx.channel.send(f"💥 **HẾT GIỜ!** {p.mention} không trả lời ➔ **BỊ TREO CỔ NGAY LẬP TỨC!**")
                        alive_players = [ap for ap in alive_players if ap.id != p.id]
                        if p.id in spy_ids: alive_spies = [s for s in alive_spies if s.id != p.id]
                        else: alive_civs = [c for c in alive_civs if c.id != p.id]
                else:
                    await ctx.channel.send(f"👉 **Lượt {idx}/{len(alive_players)}:** {p.mention} — Hãy gõ câu mô tả từ khóa vào chat! *(20 giây)*")
                    await asyncio.sleep(20)

            if game_data.get("stopped"): break
            if len(alive_spies) == 0 or len(alive_spies) >= len(alive_civs): break

            disc_embed = discord.Embed(title=f"💬 THẢO LUẬN TỰ DO (NGÀY {day_count})", description=f"👥 **Số lượng dân còn sống:** **{len(alive_players)} người**\n⏱️ Cả nhóm có **{discussion_mins} PHÚT** để thảo luận!", color=discord.Color.green())
            await ctx.channel.send(embed=disc_embed)

            total_sleep = discussion_mins * 60
            if total_sleep > 60:
                await asyncio.sleep(total_sleep - 60)
                await ctx.channel.send("⏳ **CÒN 1 PHÚT CUỐI CÙNG ĐỂ THẢO LUẬN TRƯỚC KHI VOTE!**")
                await asyncio.sleep(60)
            else: await asyncio.sleep(total_sleep)

            if game_data.get("stopped"): break

            vote_view = SpyVotingView(alive_players)
            vote_msg = await ctx.channel.send(embed=discord.Embed(title=f"🗳️ BỎ PHIẾU VOTE TREO CỔ (NGÀY {day_count})", description="Dùng Menu chọn người nghi ngờ hoặc Bỏ phiếu trắng trong 45 giây!", color=discord.Color.gold()), view=vote_view)
            await asyncio.sleep(45)

            for child in vote_view.children: child.disabled = True
            try: await vote_msg.edit(view=vote_view)
            except Exception: pass

            if game_data.get("stopped"): break

            if vote_view.votes:
                vote_detail_lines, tally = [], {}
                for voter_id, target in vote_view.votes.items():
                    voter = ctx.guild.get_member(voter_id)
                    if target == "skip": vote_detail_lines.append(f"• **{voter.display_name}** ➔ *⚪ Bỏ phiếu trắng*")
                    else:
                        t_member = ctx.guild.get_member(int(target))
                        vote_detail_lines.append(f"• **{voter.display_name}** ➔ **{t_member.display_name}**")
                    tally[target] = tally.get(target, 0) + 1

                max_v = max(tally.values())
                elim_ids = [tid for tid, c in tally.items() if c == max_v]
                result_vote_embed = discord.Embed(title=f"📊 KẾT QUẢ BỎ PHIẾU (NGÀY {day_count})", description="**Chi tiết phiếu bầu:**\n" + "\n".join(vote_detail_lines), color=discord.Color.purple())

                if len(elim_ids) == 1:
                    max_target = elim_ids[0]
                    if max_target == "skip": result_vote_embed.add_field(name="⚪ Quyết định cuối cùng", value="**Đa số bầu phiếu trắng! Không ai bị loại hôm nay.**", inline=False)
                    else:
                        vout_id = int(max_target)
                        vout_p = ctx.guild.get_member(vout_id)
                        alive_players = [p for p in alive_players if p.id != vout_id]

                        if vout_id in spy_ids:
                            alive_spies = [s for s in alive_spies if s.id != vout_id]
                            result_vote_embed.add_field(name="🔥 Quyết định cuối cùng", value=f"Đã loại {vout_p.mention} (**{max_v} phiếu**)! Anh ấy chính là **GIÁN ĐIỆP 🕵️**!", inline=False)
                        else:
                            alive_civs = [c for c in alive_civs if c.id != vout_id]
                            result_vote_embed.add_field(name="💀 Quyết định cuối cùng", value=f"Đã loại {vout_p.mention}! Anh ấy là **DÂN THƯỜNG BỊ NGHI OAN 😭**!", inline=False)
                else: result_vote_embed.add_field(name="⚖️ Quyết định cuối cùng", value="**Hòa phiếu!** Không ai bị loại hôm nay.", inline=False)

                await ctx.channel.send(embed=result_vote_embed)

            spy_names = ", ".join([f"**{s.display_name}**" for s in spies])
            if len(alive_spies) == 0:
                await ctx.channel.send(embed=discord.Embed(title="🎉 PHE DÂN THƯỜNG CHIẾN THẮNG!", description=f"Gián Điệp ({spy_names}) đã bị diệt sạch!", color=discord.Color.green()))
                break
            elif len(alive_spies) >= len(alive_civs):
                await ctx.channel.send(embed=discord.Embed(title="🕵️ PHE GIÁN ĐIỆP CHIẾN THẮNG!", description=f"Gián Điệp (**{spy_names}**) đã thống trị trò chơi!", color=discord.Color.red()))
                break

            day_count += 1
            await asyncio.sleep(3)

        if cid in self.active_games: del self.active_games[cid]


async def setup(bot):
    await bot.add_cog(WhoIsSpyCog(bot))