# spygame.py
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

def calculate_wolf_count(setting_str: str, total_players: int) -> int:
    """Calculates the number of wolves based on host input (exact number or percentage)"""
    setting = str(setting_str).strip()
    if setting.endswith('%'):
        try:
            pct = float(setting[:-1].strip())
            calculated = int(total_players * (pct / 100.0))
            return max(1, min(total_players - 1, calculated))
        except ValueError:
            return max(1, int(total_players * 0.25))
    else:
        try:
            cnt = int(setting)
            return max(1, min(total_players - 1, cnt))
        except ValueError:
            return max(1, int(total_players * 0.25))

# ==============================================================================
#                               PART 1: AI LÀ GIÁN ĐIỆP
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
#                               PART 2: MINIGAME MA SÓI (WEREWOLF)
# ==============================================================================

ROLES_INFO = {
    "wolf": {"name": "Ma Sói", "emoji": "🐺", "side": "evil", "desc": "Đêm đến chọn duy nhất 1 người để cắn chết cùng phe Sói."},
    "alpha_wolf": {"name": "Sói Đầu Đàn", "emoji": "🐺👑", "side": "evil", "desc": "Trùm Ma Sói đột biến! Có sức mạnh lãnh đạo phe Sói, phiếu bầu tính gấp đôi."},
    "seer": {"name": "Tiên Tri", "emoji": "🔮", "side": "good", "desc": "Mỗi đêm được soi người chơi xem thuộc Phe Thiện hay Phe Ác (Trăng Tròn soi được 2 người, Trăng Non bị phế)."},
    "doctor": {"name": "Bảo Vệ", "emoji": "🛡️", "side": "good", "desc": "Mỗi đêm chọn duy nhất 1 người để bảo vệ khỏi Ma Sói."},
    "witch": {"name": "Phù Thủy", "emoji": "🧪", "side": "good", "desc": "Có đúng 1 bình thuốc cứu và 1 bình thuốc độc dùng 1 lần cả ván."},
    "villager": {"name": "Dân Làng", "emoji": "👨‍🌾", "side": "good", "desc": "Tranh luận tìm Ma Sói để treo cổ ban ngày."},
    "hunter": {"name": "Thợ Săn", "emoji": "🏹", "side": "good", "desc": "Khi chết (bị cắn hay treo cổ), được mở bảng kéo 1 người chết theo!"},
    "addict": {"name": "Nghiện Nhân", "emoji": "🌿", "side": "good", "desc": "Thức đêm thực hiện hành động phê pha để tìm Sói và Ma Cà Rồng."},
    "corrupted": {"name": "Gian Dân", "emoji": "🗡️💋", "side": "evil", "desc": "Là Dân nhưng lòng dạ độc ác! Cứ 2 ngày được chọn đâm chết 1 Dân Làng (Không đâm Sói)."},
    "vampire": {"name": "Ma Cà Rồng", "emoji": "🧛", "side": "neutral", "desc": "Phe 3 bí ẩn! Tri soi ra Dân, nhưng Nghẹo lại thấy. Đêm Trăng Máu có thể lây nhiễm biến nạn nhân thành Ma Cà Rồng!"},
    "psychiatrist": {"name": "Nhà Tâm Lý", "emoji": "🧠", "side": "good", "desc": "Trong đêm Trăng Xanh, chọn 2 người để chữa trị tâm lý không bị phát điên."},
    "chemist": {"name": "Hóa Học Gia", "emoji": "☣️", "side": "good", "desc": "Có 1 bình độc sinh học (Tiêu diệt 50% một phe) xài 1 lần ván, và 1 bình cứu cứ 2-3 đêm hồi 1 lần."},
    "drug_lord": {"name": "Buôn Mai Thúy", "emoji": "🧊", "side": "evil", "desc": "Phe Sói bá chủ! Có khả năng kinh doanh mai thúy cùng phe Sói (Sói không thể cắn)."},
    "mayor": {"name": "Trưởng Làng", "emoji": "📜", "side": "good", "desc": "Lá phiếu bầu treo cổ ban ngày tính là x2 Phiếu."},
    "furry": {"name": "Hội Chứng Lông Rậm", "emoji": "🦣", "side": "good", "desc": "Lớp lông cực dày giúp có 50% tỉ lệ sống sót khi bị Sói cắn."},
    "misanthrope": {"name": "Kỳ Thị Dân", "emoji": "☣️", "side": "good", "desc": "Phiếu bầu bằng 0, nhưng nếu bị bầu treo cổ sẽ tính x4 Phiếu phạt."},
    "cupid": {"name": "Thần Tình Yêu", "emoji": "💘", "side": "good", "desc": "Đêm đầu ghép đôi 2 người bất kỳ. Nếu ghép Dân + Sói sẽ tạo thành Phe Cặp Đôi (Phe 4)."},
    "avenger": {"name": "Kẻ Hận Thù", "emoji": "🗡️", "side": "neutral", "desc": "Mối tình đầu tan vỡ! Mỗi đêm được chọn giết 1 người để trả thù cho tình nhân."},
    "mad_scientist": {"name": "Nhà Khoa Học Điên", "emoji": "🧪⚡", "side": "neutral", "desc": "Kẻ biến thái! Có thuốc độc chọc Dân -> Sói, chọc Sói -> Sói Đầu Đàn."},
    "god": {"name": "CHÚA", "emoji": "⚡", "side": "god", "desc": "Đấng tối cao! Có nút [⚡ END GAME] và nút [🪄 BIẾN ĐỔI VAI TRÒ] tùy ý giữa trận!"}
}


class WerewolfSettingsModal(Modal, title="⚙️ Cài Đặt Phòng Ma Sói"):
    max_players_input = TextInput(label="Số người tối đa (Tối đa 100)", placeholder="Mặc định: 15", required=True, max_length=3)
    minutes_input = TextInput(label="Số phút thảo luận ban ngày (1-10 phút)", placeholder="Mặc định: 3", required=True, max_length=2)
    show_votes_input = TextInput(label="Hiển thị Chi Tiết Vote? (1: Có | 0: Ẩn)", placeholder="1 hoặc 0 (Mặc định 1)", required=True, max_length=1)
    wolf_count_input = TextInput(label="Số lượng/Tỉ lệ Sói (VD: 1, 6, hoặc 25%)", placeholder="Mặc định: 25%", required=False, max_length=5)

    def __init__(self, lobby_view):
        super().__init__()
        self.lobby_view = lobby_view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            max_p = int(self.max_players_input.value.strip())
            mins = int(self.minutes_input.value.strip())
            svote = int(self.show_votes_input.value.strip())
            w_setting = self.wolf_count_input.value.strip() or "25%"
            if not (4 <= max_p <= 100) or not (1 <= mins <= 10) or svote not in (0, 1): raise ValueError
        except ValueError:
            return await interaction.response.send_message("❌ Nhập sai! Số người (4-100), Phút (1-10), Vote (1 hoặc 0)!", ephemeral=True)

        self.lobby_view.max_players = max_p
        self.lobby_view.discussion_minutes = mins
        self.lobby_view.show_votes = bool(svote)
        self.lobby_view.wolf_setting = w_setting
        await interaction.response.send_message(f"✅ Đã lưu cài đặt! Cấu hình Sói: **{w_setting}**", ephemeral=True)
        try: await interaction.message.edit(embed=self.lobby_view.generate_embed(), view=self.lobby_view)
        except Exception: pass


class ForceRoleModal(Modal, title="🛠️ Force Role (Dev / Host Test)"):
    user_id_input = TextInput(label="Discord User ID của Người Chơi", placeholder="Nhập ID...", required=True, max_length=20)
    role_key_input = TextInput(label="Mã Role (Aliases)", placeholder="Ví dụ: god, vampire, hunter...", required=True, max_length=20)

    def __init__(self, lobby_view):
        super().__init__()
        self.lobby_view = lobby_view

    async def on_submit(self, interaction: discord.Interaction):
        uid_str = self.user_id_input.value.strip()
        rkey = self.role_key_input.value.strip().lower()

        try: uid = int(uid_str)
        except ValueError: return await interaction.response.send_message("❌ User ID phải là chuỗi số!", ephemeral=True)

        if uid not in self.lobby_view.players: return await interaction.response.send_message("❌ User ID này chưa tham gia phòng!", ephemeral=True)

        if rkey not in ROLES_INFO:
            valid_roles = ", ".join(ROLES_INFO.keys())
            return await interaction.response.send_message(f"❌ Mã Role không hợp lệ! Các role có sẵn:\n`{valid_roles}`", ephemeral=True)

        self.lobby_view.forced_roles[uid] = rkey
        user_obj = self.lobby_view.players[uid]
        await interaction.response.send_message(f"✅ Đã Force ép vai trò **{ROLES_INFO[rkey]['name']}** cho người chơi **{user_obj.display_name}**!", ephemeral=True)


class HunterShootView(View):
    def __init__(self, hunter_id: int, valid_targets: list, alive_players: list):
        super().__init__(timeout=20)
        self.hunter_id = hunter_id
        self.alive_players = alive_players
        self.target_id = None

        options = [discord.SelectOption(label=p.display_name, value=str(p.id), emoji="🏹") for p in valid_targets[:25] if p.id != hunter_id]
        if options:
            select = Select(placeholder="🏹 Chọn người bạn muốn giương cung bắn chết theo...", options=options)
            select.callback = self.select_cb
            self.add_item(select)

    async def select_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.hunter_id: return
        self.target_id = int(interaction.data["values"][0])
        target_p = interaction.guild.get_member(self.target_id)
        await interaction.response.send_message(f"🏹 Thợ Săn đã ngắm bắn vào **{target_p.display_name}**!", ephemeral=True)
        self.stop()


class GodModifyRoleView(View):
    def __init__(self, god_id: int, alive_players: list, player_roles: dict):
        super().__init__(timeout=30)
        self.god_id = god_id
        self.alive_players = alive_players
        self.player_roles = player_roles
        self.selected_uid = None

        p_options = [discord.SelectOption(label=p.display_name, value=str(p.id), emoji="👤") for p in alive_players[:25] if p.id != god_id]
        self.select_p = Select(placeholder="👤 Chọn người chơi muốn đổi Role...", options=p_options, row=0)
        self.select_p.callback = self.select_p_cb
        self.add_item(self.select_p)

        r_options = [discord.SelectOption(label=info['name'], value=r_key, emoji=info['emoji']) for r_key, info in list(ROLES_INFO.items())[:25]]
        self.select_r = Select(placeholder="🪄 Chọn Role mới muốn gán...", options=r_options, row=1)
        self.select_r.callback = self.select_r_cb
        self.add_item(self.select_r)

    async def select_p_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.god_id: return
        if interaction.user.id not in [p.id for p in self.alive_players]:
            return await interaction.response.send_message("❌ Bạn đã chết!", ephemeral=True)
        self.selected_uid = int(self.select_p.values[0])
        p_name = interaction.guild.get_member(self.selected_uid).display_name
        await interaction.response.send_message(f"✅ Đã chọn người chơi: **{p_name}**", ephemeral=True)

    async def select_r_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.god_id: return
        if interaction.user.id not in [p.id for p in self.alive_players]:
            return await interaction.response.send_message("❌ Bạn đã chết!", ephemeral=True)
        if not self.selected_uid: return await interaction.response.send_message("❌ Chưa chọn người chơi!", ephemeral=True)

        new_role = self.select_r.values[0]
        self.player_roles[self.selected_uid] = new_role
        target_p = interaction.guild.get_member(self.selected_uid)
        
        try: await target_p.send(f"⚡ **CHÚA ĐÃ PHÁN XÉT:** Vai trò của bạn đã bị biến đổi thành **{ROLES_INFO[new_role]['emoji']} {ROLES_INFO[new_role]['name']}**!")
        except Exception: pass

        await interaction.response.send_message(f"⚡ Đã biến đổi role của **{target_p.display_name}** thành **{ROLES_INFO[new_role]['name']}**!", ephemeral=True)


class CupidPairView(View):
    def __init__(self, cupid_id: int, valid_players: list, night_data: dict, alive_players: list):
        super().__init__(timeout=35)
        self.cupid_id = cupid_id
        self.valid_players = valid_players[:25]
        self.alive_players = alive_players
        self.night_data = night_data
        self.p1_id = None
        self.p2_id = None

        options = [discord.SelectOption(label=p.display_name, value=str(p.id), emoji="💖") for p in self.valid_players]

        self.select_1 = Select(placeholder="💖 [Người 1] Chọn người thứ nhất...", options=options, row=0)
        self.select_1.callback = self.select_1_cb
        self.add_item(self.select_1)

        self.select_2 = Select(placeholder="💖 [Người 2] Chọn người thứ hai...", options=options, row=1)
        self.select_2.callback = self.select_2_cb
        self.add_item(self.select_2)

    async def select_1_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.cupid_id: return
        if interaction.user.id not in [p.id for p in self.alive_players]:
            return await interaction.response.send_message("❌ Bạn đã chết! Hồn ma không thể ghép đôi.", ephemeral=True)

        self.p1_id = int(self.select_1.values[0])
        p1_name = interaction.guild.get_member(self.p1_id).display_name
        await interaction.response.send_message(f"✅ Đã chọn **Người 1**: **{p1_name}**", ephemeral=True)
        await self.check_and_pair(interaction)

    async def select_2_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.cupid_id: return
        if interaction.user.id not in [p.id for p in self.alive_players]:
            return await interaction.response.send_message("❌ Bạn đã chết! Hồn ma không thể ghép đôi.", ephemeral=True)

        self.p2_id = int(self.select_2.values[0])
        p2_name = interaction.guild.get_member(self.p2_id).display_name
        await interaction.response.send_message(f"✅ Đã chọn **Người 2**: **{p2_name}**", ephemeral=True)
        await self.check_and_pair(interaction)

    async def check_and_pair(self, interaction: discord.Interaction):
        if self.p1_id and self.p2_id:
            if self.p1_id == self.p2_id:
                return await interaction.followup.send("❌ Người 1 và Người 2 không được trùng nhau!", ephemeral=True)

            self.night_data["lovers"] = (self.p1_id, self.p2_id)
            p1 = interaction.guild.get_member(self.p1_id)
            p2 = interaction.guild.get_member(self.p2_id)

            try: await p1.send(f"💘 **THẦN TÌNH YÊU NỐI DÂY TƠ HỒNG:** Bạn đã được ghép đôi với **{p2.display_name}**! Hãy bảo vệ người yêu của mình đến cùng!")
            except Exception: pass
            try: await p2.send(f"💘 **THẦN TÌNH YÊU NỐI DÂY TƠ HỒNG:** Bạn đã được ghép đôi với **{p1.display_name}**! Hãy bảo vệ người yêu của mình đến cùng!")
            except Exception: pass

            await interaction.followup.send(f"💘 **KẾT DUYÊN THÀNH CÔNG:** **{p1.display_name}** 💖 **{p2.display_name}**!", ephemeral=True)


# ==============================================================================
#                      WEREWOLF SECRET COMMUNICATION MODAL
# ==============================================================================

class WerewolfCommModal(Modal, title="💬 Truyền Âm Đồng Bọn"):
    message_input = TextInput(
        label="Nội dung truyền âm",
        placeholder="Nhập lời muốn nói với đồng bọn bầy sói...",
        required=True,
        max_length=150
    )

    def __init__(self, bot, alive_players, player_roles, sender):
        super().__init__()
        self.bot = bot
        self.alive_players = alive_players
        self.player_roles = player_roles
        self.sender = sender

    async def on_submit(self, interaction: discord.Interaction):
        msg_text = self.message_input.value.strip()
        wolves = [p for p in self.alive_players if self.player_roles.get(p.id) in ("wolf", "alpha_wolf", "drug_lord")]
        
        success_count = 0
        for w in wolves:
            if w.id == self.sender.id:
                continue
            try:
                role_emoji = ROLES_INFO[self.player_roles[self.sender.id]]["emoji"]
                embed = discord.Embed(
                    title="💬 TIN TRUYỀN ÂM BẦY SÓI",
                    description=f"🐺 **{self.sender.display_name}** ({role_emoji}) gửi tín hiệu:\n💬 *\"{msg_text}\"*",
                    color=discord.Color.red()
                )
                await w.send(embed=embed)
                success_count += 1
            except Exception:
                pass
        
        await interaction.response.send_message(
            f"✅ Đã truyền âm thành công đến {success_count} đồng bọn trong bầy!", 
            ephemeral=True
        )


# ==============================================================================
#                     SUBVIEWS FOR ROLE HANDLERS
# ==============================================================================

class WerewolfNightActionsSubView(View):
    def __init__(self, outer, uid, valid_targets):
        super().__init__(timeout=30)
        self.outer = outer
        self.uid = uid
        self.valid_targets = valid_targets

        options = [discord.SelectOption(label=p.display_name, value=str(p.id), emoji="🩸") for p in valid_targets[:25]]
        select = Select(placeholder="🐺 Chọn duy nhất 1 người để cắn...", max_values=1, options=options)
        select.callback = self.vote_callback
        self.add_item(select)

    async def vote_callback(self, interaction: discord.Interaction):
        if len(interaction.data["values"]) > 1:
            return await interaction.response.send_message("❌ Bạn chỉ được chọn duy nhất 1 mục tiêu!", ephemeral=True)

        target_id = int(interaction.data["values"][0])
        self.outer.night_data["wolf_votes"][self.uid] = [target_id]
        
        embed = self.outer.generate_wolf_status_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="💬 Truyền Âm", style=discord.ButtonStyle.danger, row=1)
    async def transmit_sound(self, interaction: discord.Interaction, button: Button):
        modal = WerewolfCommModal(self.outer.bot, self.outer.alive_players, self.outer.player_roles, interaction.user)
        await interaction.response.send_modal(modal)


class SeerNightActionSubView(View):
    def __init__(self, outer, uid, other_players, max_inspect):
        super().__init__(timeout=30)
        self.outer = outer
        self.uid = uid
        self.max_inspect = max_inspect

        options = [discord.SelectOption(label=p.display_name, value=str(p.id), emoji="🔮") for p in other_players[:25]]
        select = Select(
            placeholder=f"🔮 Chọn tối đa {max_inspect} người bạn muốn soi...", 
            min_values=1, 
            max_values=min(max_inspect, len(options)), 
            options=options
        )
        select.callback = self.inspect_callback
        self.add_item(select)

    async def inspect_callback(self, interaction: discord.Interaction):
        if len(interaction.data["values"]) > self.max_inspect:
            return await interaction.response.send_message(f"❌ Bạn chỉ được chọn tối đa {self.max_inspect} người!", ephemeral=True)
        
        self.outer.night_data["acted_players"].add(self.uid)
        res_lines = []
        for val in interaction.data["values"]:
            target_id = int(val)
            target_role = self.outer.player_roles[target_id]
            target_p = interaction.guild.get_member(target_id)
            
            if target_role == "vampire" or ROLES_INFO[target_role]["side"] == "good":
                side_text = "🟢 **PHE THIỆN (DÂN LÀNG)**"
            else:
                side_text = "🔴 **PHE ÁC (MA SÓI)**"
            res_lines.append(f"• **{target_p.display_name}**: Anh ấy thuộc {side_text}!")
        
        await interaction.response.send_message("🔮 **KẾT QUẢ SOI KHẢO SÁT CHU KỲ TRĂNG:**\n" + "\n".join(res_lines), ephemeral=True)
        for child in self.children:
            child.disabled = True
        await interaction.edit_original_response(view=self)


class AddictNightActionSubView(View):
    def __init__(self, outer, uid):
        super().__init__(timeout=30)
        self.outer = outer
        self.uid = uid

    @discord.ui.button(label="🌿 Thực hiện hành động hít đá thức đêm", style=discord.ButtonStyle.success)
    async def smoke_action(self, interaction: discord.Interaction, button: Button):
        if self.outer.night_data["event"] == "new_moon":
            roll_chance = 1.0
        else:
            roll_chance = 0.30

        self.outer.night_data["acted_players"].add(self.uid)
        button.disabled = True
        await interaction.response.edit_message(view=self)

        if random.random() < roll_chance:
            vamps = [p for p in self.outer.alive_players if self.outer.player_roles.get(p.id) == "vampire"]
            wolves = [p for p in self.outer.alive_players if ROLES_INFO[self.outer.player_roles.get(p.id)]["side"] == "evil"]

            if vamps:
                hint_text = f"Mắt nhắm mắt mở phát hiện **{vamps[0].display_name}** chính là **MA CÀ RỒNG 🧛** đang lang thang hút máu!"
            elif wolves:
                random_wolf = random.choice(wolves)
                hint_text = f"Lờ mờ nhìn thấy **{random_wolf.display_name}** có hành tung mờ hờ giống Ma Sói!"
            else:
                hint_text = "Đêm nay im ắng quá..."
        else:
            hint_text = "Bú đá say khướt mắt mũi kèm nhèm không nhìn thấy gì cả!"

        extra_note = "\n🌑 *Đêm Trăng Non: Bạn là TIÊN TRI DUY NHẤT thức đêm nhìn thấu sự thật!*" if self.outer.night_data["event"] == "new_moon" else ""
        await interaction.followup.send(f"🌿 **CƠN NGHIỆN TRỖI DẬY:** Trong lúc thức đêm phê thuốc, bạn {hint_text}{extra_note}", ephemeral=True)


# ==============================================================================
#                       MAIN NIGHT ACTION CONTROL PANEL
# ==============================================================================

class NightActionView(View):
    """Bảng chọn kỹ năng Ban Đêm dạng rút gọn kết hợp Tình Hình Làng"""
    def __init__(self, player_roles: dict, alive_players: list, night_data: dict, day_count: int, witch_state: dict, chemist_state: dict, gian_dan_last_used: dict, game_data: dict, bot):
        super().__init__(timeout=45)
        self.player_roles = player_roles
        self.alive_players = alive_players
        self.night_data = night_data
        self.day_count = day_count
        self.witch_state = witch_state
        self.chemist_state = chemist_state
        self.gian_dan_last_used = gian_dan_last_used
        self.game_data = game_data
        self.bot = bot

    def generate_wolf_status_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🐺 GIAO DIỆN PHÒNG CHAT & VOTE CỦA BẦY SÓI",
            description="Thống nhất mục tiêu để tiêu diệt dân làng đêm nay!",
            color=discord.Color.red()
        )
        tally = {}
        for voter_id, targets in self.night_data["wolf_votes"].items():
            weight = 2 if self.player_roles.get(voter_id) == "alpha_wolf" else 1
            for t in targets:
                tally[t] = tally.get(t, 0) + weight
        
        tally_lines = []
        for target_id, weight in tally.items():
            target_p = discord.utils.get(self.alive_players, id=target_id)
            target_name = target_p.display_name if target_p else f"ID: {target_id}"
            tally_lines.append(f"• **{target_name}**: {weight} Phiếu (Điểm)")
        
        if tally_lines:
            embed.add_field(name="📊 Tiến độ bỏ phiếu hiện tại:", value="\n".join(tally_lines), inline=False)
        else:
            embed.add_field(name="📊 Tiến độ bỏ phiếu hiện tại:", value="Chưa có ai bỏ phiếu cắn.", inline=False)
            
        embed.add_field(
            name="💡 Gợi ý:", 
            value="• Bấm nút **[💬 Truyền Âm]** bên dưới để truyền tin mật đến DMs của tất cả Sói còn sống.\n• Sói Đầu Đàn (Alpha Wolf) có số phiếu bầu x2.", 
            inline=False
        )
        return embed

    @discord.ui.button(label="Xem Tiên Đoán", style=discord.ButtonStyle.primary, emoji="🔮", row=0)
    async def open_panel(self, interaction: discord.Interaction, button: Button):
        uid = interaction.user.id
        
        if uid not in [p.id for p in self.alive_players]:
            return await interaction.response.send_message("❌ Bạn đã chết! Hồn ma không thể thực hiện kỹ năng ban đêm.", ephemeral=True)

        if uid in self.night_data["acted_players"]:
            return await interaction.response.send_message("❌ Hôm nay bạn đã dùng kỹ năng ban đêm rồi! Hãy kiên nhẫn chờ sáng.", ephemeral=True)

        role = self.player_roles[uid]
        r_info = ROLES_INFO[role]

        # 0. CHÚA
        if role == "god":
            class GodControlView(View):
                def __init__(self, outer):
                    super().__init__(timeout=30)
                    self.outer = outer

                @discord.ui.button(label="⚡ END GAME KHẨN CẤP", style=discord.ButtonStyle.danger)
                async def god_end(self, i: discord.Interaction, b: Button):
                    if i.user.id not in [p.id for p in self.outer.alive_players]:
                        return await i.response.send_message("❌ Bạn đã chết!", ephemeral=True)
                    self.outer.game_data["stopped"] = True
                    god_embed = discord.Embed(
                        title="⚡ CHÚA ĐÃ PHÁN XÉT - KẾT THÚC GAME!",
                        description=f"👑 **{i.user.mention}** (CHÚA) đã phán xét hòa bình và dừng ván game ngay lập tức!",
                        color=discord.Color.gold()
                    )
                    await i.channel.send(embed=god_embed)
                    await i.response.send_message("⚡ Đã kết thúc game thành công!", ephemeral=True)

                @discord.ui.button(label="🪄 BIẾN ĐỔI VAI TRÒ NGƯỜI CHƠI", style=discord.ButtonStyle.primary)
                async def god_mod(self, i: discord.Interaction, b: Button):
                    if i.user.id not in [p.id for p in self.outer.alive_players]:
                        return await i.response.send_message("❌ Bạn đã chết!", ephemeral=True)
                    mod_view = GodModifyRoleView(uid, self.outer.alive_players, self.outer.player_roles)
                    await i.response.send_message("🪄 **BẢNG BIẾN ĐỔI VAI TRÒ CỦA CHÚA:**", view=mod_view, ephemeral=True)

            return await interaction.response.send_message("⚡ **BẢNG ĐIỀU HÀNH TỐI CAO CỦA CHÚA:**", view=GodControlView(self), ephemeral=True)

        # 1. PHÙ THỦY
        elif role == "witch":
            victim_id = self.night_data.get("current_wolf_target")
            victim_p = interaction.guild.get_member(victim_id) if victim_id else None
            status_text = f"Đêm nay Ma Sói đang cắm móng vào: **{victim_p.display_name if victim_p else 'Chưa rõ/Chưa cắn'}**"

            class WitchNightPanel(View):
                def __init__(self, outer):
                    super().__init__(timeout=30)
                    self.outer = outer

                @discord.ui.button(label="🧪 Dùng Thuốc Cứu (1 Lần/Ván)", style=discord.ButtonStyle.success)
                async def heal_btn(self, i: discord.Interaction, b: Button):
                    if i.user.id not in [p.id for p in self.outer.alive_players]:
                        return await i.response.send_message("❌ Bạn đã chết!", ephemeral=True)
                    if i.user.id in self.outer.night_data["acted_players"]:
                        return await i.response.send_message("❌ Đêm nay bạn đã hành động rồi!", ephemeral=True)
                    if self.outer.witch_state["heal_used"]:
                        return await i.response.send_message("❌ Bạn đã dùng hết bình thuốc cứu của cả ván game rồi!", ephemeral=True)

                    self.outer.night_data["witch_heal_action"] = True
                    self.outer.witch_state["heal_used"] = True
                    self.outer.night_data["acted_players"].add(i.user.id)
                    await i.response.send_message("🧪 Bạn đã dùng bình CỨU duy nhất để bảo vệ nạn nhân bị cắn đêm nay!", ephemeral=True)

                @discord.ui.button(label="☠️ Dùng Thuốc Độc (1 Lần/Ván)", style=discord.ButtonStyle.danger)
                async def poison_btn(self, i: discord.Interaction, b: Button):
                    if i.user.id not in [p.id for p in self.outer.alive_players]:
                        return await i.response.send_message("❌ Bạn đã chết!", ephemeral=True)
                    if i.user.id in self.outer.night_data["acted_players"]:
                        return await i.response.send_message("❌ Đêm nay bạn đã hành động rồi!", ephemeral=True)
                    if self.outer.witch_state["poison_used"]:
                        return await i.response.send_message("❌ Bạn đã dùng hết bình thuốc độc của cả ván game rồi!", ephemeral=True)

                    other_p = [p for p in self.outer.alive_players if p.id != uid][:25]
                    poison_options = [discord.SelectOption(label=p.display_name, value=str(p.id), emoji="☠️") for p in other_p]
                    poison_select = Select(placeholder="☠️ Chọn 1 người để đầu độc...", options=poison_options)

                    async def poison_cb(i_sub: discord.Interaction):
                        if len(poison_select.values) > 1:
                            return await i_sub.response.send_message("❌ Bạn chỉ được chọn duy nhất 1 mục tiêu!", ephemeral=True)

                        if i_sub.user.id not in [p.id for p in self.outer.alive_players]:
                            return await i_sub.response.send_message("❌ Bạn đã chết!", ephemeral=True)
                        if i_sub.user.id in self.outer.night_data["acted_players"]:
                            return await i_sub.response.send_message("❌ Đêm nay bạn đã hành động rồi!", ephemeral=True)

                        target_id = int(poison_select.values[0])
                        self.outer.night_data["witch_poison_id"] = target_id
                        self.outer.witch_state["poison_used"] = True
                        self.outer.night_data["acted_players"].add(i_sub.user.id)
                        t_p = i_sub.guild.get_member(target_id)
                        await i_sub.response.send_message(f"☠️ Bạn đã ném bình thuốc độc duy nhất vào **{t_p.display_name}**!", ephemeral=True)

                    poison_select.callback = poison_cb
                    sub_view = View(timeout=30); sub_view.add_item(poison_select)
                    await i.response.send_message("☠️ **CHỌN MỤC TIÊU ĐỂ NÉM THUỐC ĐỘC:**", view=sub_view, ephemeral=True)

            return await interaction.response.send_message(f"🧪 **BẢNG PHÙ THỦY (Chọn 1 trong 2 nút bên dưới):**\n{status_text}", view=WitchNightPanel(self), ephemeral=True)

        # 2. HÓA HỌC GIA
        elif role == "chemist":
            class ChemistNightPanel(View):
                def __init__(self, outer):
                    super().__init__(timeout=30)
                    self.outer = outer

                @discord.ui.button(label="🧪 Bình Hồi Sinh (Mỗi 2-3 Đêm)", style=discord.ButtonStyle.success)
                async def heal_chem(self, i: discord.Interaction, b: Button):
                    if i.user.id not in [p.id for p in self.outer.alive_players]:
                        return await i.response.send_message("❌ Bạn đã chết!", ephemeral=True)
                    if i.user.id in self.outer.night_data["acted_players"]:
                        return await i.response.send_message("❌ Đêm nay bạn đã hành động rồi!", ephemeral=True)
                    if self.outer.chemist_state["revive_cd"] > 0:
                        return await i.response.send_message(f"❌ Bình hồi sinh đang hồi chiêu! (Cần chờ {self.outer.chemist_state['revive_cd']} đêm nữa).", ephemeral=True)

                    self.outer.night_data["chemist_heal_action"] = True
                    self.outer.chemist_state["revive_cd"] = random.randint(2, 3)
                    self.outer.night_data["acted_players"].add(i.user.id)
                    await i.response.send_message("🧪 Bạn đã dùng thuốc hóa học CỨU nạn nhân bị cắn đêm nay!", ephemeral=True)

                @discord.ui.button(label="☣️ Siêu Độc Diệt 50% Phe (1 Lần/Ván)", style=discord.ButtonStyle.danger)
                async def nuke_chem(self, i: discord.Interaction, b: Button):
                    if i.user.id not in [p.id for p in self.outer.alive_players]:
                        return await i.response.send_message("❌ Bạn đã chết!", ephemeral=True)
                    if i.user.id in self.outer.night_data["acted_players"]:
                        return await i.response.send_message("❌ Đêm nay bạn đã hành động rồi!", ephemeral=True)
                    if self.outer.chemist_state["nuke_used"]:
                        return await i.response.send_message("❌ Bạn đã dùng hết bình siêu hóa chất của cả ván game rồi!", ephemeral=True)

                    class NukeSubView(View):
                        def __init__(self, c_outer):
                            super().__init__(timeout=30)
                            self.c_outer = c_outer

                        @discord.ui.button(label="🐺 Đầu Độc 50% Phe Sói", style=discord.ButtonStyle.danger)
                        async def nuke_w(self, i_sub: discord.Interaction, b_sub: Button):
                            if i_sub.user.id in self.c_outer.outer.night_data["acted_players"]:
                                return await i_sub.response.send_message("❌ Bạn đã hành động rồi!", ephemeral=True)
                            self.c_outer.outer.night_data["chemist_nuke_wolf"] = True
                            self.c_outer.outer.chemist_state["nuke_used"] = True
                            self.c_outer.outer.night_data["acted_players"].add(i_sub.user.id)
                            await i_sub.response.send_message("☣️ BÌNH ĐỘC TIÊU DIỆT 50% PHE SÓI ĐÃ KÍCH HOẠT!", ephemeral=True)

                        @discord.ui.button(label="👨‍🌾 Đầu Độc 50% Phe Dân", style=discord.ButtonStyle.danger)
                        async def nuke_c(self, i_sub: discord.Interaction, b_sub: Button):
                            if i_sub.user.id in self.c_outer.outer.night_data["acted_players"]:
                                return await i_sub.response.send_message("❌ Bạn đã hành động rồi!", ephemeral=True)
                            self.c_outer.outer.night_data["chemist_nuke_civ"] = True
                            self.c_outer.outer.chemist_state["nuke_used"] = True
                            self.c_outer.outer.night_data["acted_players"].add(i_sub.user.id)
                            await i_sub.response.send_message("☣️ BÌNH ĐỘC TIÊU DIỆT 50% PHE DÂN LÀNG ĐÃ KÍCH HOẠT!", ephemeral=True)

                    await i.response.send_message("☣️ **CHỌN PHE ĐỂ NÉM SIÊU ĐỘC (DIỆT 50% SỐ LƯỢNG):**", view=NukeSubView(self), ephemeral=True)

            return await interaction.response.send_message("☣️ **BẢNG HÓA HỌC GIA (Chọn 1 trong 2 nút bấm bên dưới):**", view=ChemistNightPanel(self), ephemeral=True)

        # 3. MA CÀ RỒNG
        elif role == "vampire":
            if self.night_data.get("event") != "blood_moon":
                return await interaction.response.send_message("🧛 Đêm nay không phải Trăng Máu! Bạn không thể đi lây nhiễm hút máu.", ephemeral=True)

            valid_targets = [p for p in self.alive_players if self.player_roles[p.id] != "vampire" and p.id != uid][:25]
            if not valid_targets:
                return await interaction.response.send_message("🧛 Toàn bộ người sống đã thành Ma Cà Rồng!", ephemeral=True)

            options = [discord.SelectOption(label=p.display_name, value=str(p.id), emoji="🧛") for p in valid_targets]
            select = Select(placeholder="🧛 Chọn 1 người để cắn biến thành Ma Cà Rồng...", options=options)

            async def vamp_cb(i: discord.Interaction):
                if len(select.values) > 1:
                    return await i.response.send_message("❌ Bạn chỉ được chọn duy nhất 1 mục tiêu!", ephemeral=True)

                if i.user.id not in [p.id for p in self.alive_players]:
                    return await i.response.send_message("❌ Bạn đã chết!", ephemeral=True)
                if i.user.id in self.night_data["acted_players"]:
                    return await i.response.send_message("❌ Đêm nay bạn đã hành động rồi!", ephemeral=True)

                target_id = int(select.values[0])
                self.night_data["vampire_infect_id"] = target_id
                self.night_data["acted_players"].add(i.user.id)
                target_p = i.guild.get_member(target_id)
                await i.response.send_message(f"🧛 Đêm nay bạn sẽ bí mật cắn lây nhiễm **{target_p.display_name}**!", ephemeral=True)

            select.callback = vamp_cb
            view = View(timeout=30); view.add_item(select)
            return await interaction.response.send_message("🧛 **BẢNG LÂY NHIỄM CỦA MA CÀ RỒNG (TRĂNG MÁU):**", view=view, ephemeral=True)

        # 4. GIAN DÂN
        elif role == "corrupted":
            last_used = self.gian_dan_last_used.get(uid, -2)
            if self.day_count - last_used < 2:
                return await interaction.response.send_message(f"🗡️💋 Gian Dân đang hồi chiêu đâm! (Cần chờ thêm {2 - (self.day_count - last_used)} đêm nữa).", ephemeral=True)

            valid_targets = [
                p for p in self.alive_players 
                if ROLES_INFO[self.player_roles[p.id]]["side"] != "evil" and p.id != uid
            ][:25]

            if not valid_targets:
                return await interaction.response.send_message("🗡️💋 Không còn người dân nào hợp lệ để đâm!", ephemeral=True)

            options = [discord.SelectOption(label=p.display_name, value=str(p.id), emoji="🗡️") for p in valid_targets]
            select = Select(placeholder="🗡️ Chọn 1 Dân Làng để đâm lén...", options=options)

            async def gian_dan_cb(i: discord.Interaction):
                if len(select.values) > 1:
                    return await i.response.send_message("❌ Bạn chỉ được chọn duy nhất 1 mục tiêu!", ephemeral=True)

                if i.user.id not in [p.id for p in self.alive_players]:
                    return await i.response.send_message("❌ Bạn đã chết!", ephemeral=True)
                if i.user.id in self.night_data["acted_players"]:
                    return await i.response.send_message("❌ Đêm nay bạn đã hành động rồi!", ephemeral=True)

                target_id = int(select.values[0])
                self.night_data["corrupted_stab_id"] = target_id
                self.gian_dan_last_used[uid] = self.day_count
                self.night_data["acted_players"].add(i.user.id)
                target_p = i.guild.get_member(target_id)
                await i.response.send_message(f"🗡️💋 Bạn đã ra tay đâm lén **{target_p.display_name}**!", ephemeral=True)

            select.callback = gian_dan_cb
            view = View(timeout=30); view.add_item(select)
            return await interaction.response.send_message("🗡️💋 **BẢNG SÁT HẠI CỦA GIAN DÂN:**", view=view, ephemeral=True)

        # 5. CUPID
        elif role == "cupid":
            if self.day_count > 1: return await interaction.response.send_message("💘 Thần Tình Yêu đã hoàn thành sứ mệnh ở đêm đầu tiên!", ephemeral=True)
            if self.night_data.get("lovers"): return await interaction.response.send_message("💘 Bạn đã chọn cặp đôi rồi!", ephemeral=True)

            all_other_players = [p for p in self.alive_players if p.id != uid]
            if len(all_other_players) < 2:
                all_other_players = list(self.alive_players)

            cupid_view = CupidPairView(uid, all_other_players, self.night_data, self.alive_players)
            return await interaction.response.send_message("💘 **BẢNG KẾT DUYÊN CỦA CUPID (Chọn 2 người bất kỳ):**", view=cupid_view, ephemeral=True)

        # 6. KẺ HẬN THÙ
        elif role == "avenger":
            options = [discord.SelectOption(label=p.display_name, value=str(p.id), emoji="🗡️") for p in self.alive_players if p.id != uid][:25]
            select = Select(placeholder="🗡️ Chọn 1 người để tiêu diệt trả thù...", options=options)

            async def avenger_cb(i: discord.Interaction):
                if len(select.values) > 1:
                    return await i.response.send_message("❌ Bạn chỉ được chọn duy nhất 1 mục tiêu!", ephemeral=True)

                if i.user.id not in [p.id for p in self.alive_players]:
                    return await i.response.send_message("❌ Bạn đã chết!", ephemeral=True)
                if i.user.id in self.night_data["acted_players"]:
                    return await i.response.send_message("❌ Đêm nay bạn đã hành động rồi!", ephemeral=True)

                target_id = int(select.values[0])
                self.night_data["avenger_kill_id"] = target_id
                self.night_data["acted_players"].add(i.user.id)
                target_p = i.guild.get_member(target_id)
                await i.response.send_message(f"🗡️ Bạn đã nhắm mũi dao trả thù vào **{target_p.display_name}**!", ephemeral=True)

            select.callback = avenger_cb
            view = View(timeout=30); view.add_item(select)
            return await interaction.response.send_message("🗡️ **BẢNG TRẢ THÙ CỦA KẺ HẬN THÙ:**", view=view, ephemeral=True)

        # 7. NHÀ KHOA HỌC ĐIÊN
        elif role == "mad_scientist":
            options = [discord.SelectOption(label=p.display_name, value=str(p.id), emoji="🧪") for p in self.alive_players if p.id != uid][:25]
            select = Select(placeholder="🧪 Chọn 1 người để tiêm thuốc đột biến...", options=options)

            async def mad_cb(i: discord.Interaction):
                if len(select.values) > 1:
                    return await i.response.send_message("❌ Bạn chỉ được chọn duy nhất 1 mục tiêu!", ephemeral=True)

                if i.user.id not in [p.id for p in self.alive_players]:
                    return await i.response.send_message("❌ Bạn đã chết!", ephemeral=True)
                if i.user.id in self.night_data["acted_players"]:
                    return await i.response.send_message("❌ Đêm nay bạn đã hành động rồi!", ephemeral=True)

                target_id = int(select.values[0])
                target_p = i.guild.get_member(target_id)
                curr_r = self.player_roles[target_id]

                if curr_r in ("wolf", "alpha_wolf"):
                    self.player_roles[target_id] = "alpha_wolf"
                    res_msg = f"🧪 Bạn đã tiêm thuốc đột biến biến **{target_p.display_name}** thành **SÓI ĐẦU ĐÀN 🐺👑**!"
                else:
                    self.player_roles[target_id] = "wolf"
                    res_msg = f"🧪 Bạn đã tiêm thuốc đột biến biến **{target_p.display_name}** thành **MA SÓI 🐺**!"

                self.night_data["acted_players"].add(i.user.id)
                await i.response.send_message(res_msg, ephemeral=True)

            select.callback = mad_cb
            view = View(timeout=30); view.add_item(select)
            return await interaction.response.send_message("🧪 **BẢNG THÍ NGHIỆM CỦA NHÀ KHOA HỌC ĐIÊN:**", view=view, ephemeral=True)

        # 8. PHE SÓI (DÙNG PANEL PHÂN TÍCH ĐỘNG)
        elif role in ("wolf", "alpha_wolf", "drug_lord"):
            if self.night_data.get("event") == "new_moon":
                return await interaction.response.send_message("🌑 **TRĂNG NON:** Ma Sói đã bị phế hoàn toàn công lực, không thể cắn ai đêm nay!", ephemeral=True)

            excluded_ids = set()
            for p in self.alive_players:
                if self.player_roles[p.id] in ("wolf", "alpha_wolf", "corrupted", "drug_lord"):
                    excluded_ids.add(p.id)

            lovers_tuple = self.night_data.get("lovers")
            if lovers_tuple and uid in lovers_tuple:
                p1, p2 = lovers_tuple
                partner_id = p2 if uid == p1 else p1
                excluded_ids.add(partner_id)

            valid_targets = [p for p in self.alive_players if p.id not in excluded_ids]
            
            if not valid_targets:
                return await interaction.response.send_message("❌ Không còn mục tiêu Dân Làng nào hợp lệ để cắn!", ephemeral=True)

            sub_view = WerewolfNightActionsSubView(self, uid, valid_targets)
            status_embed = self.generate_wolf_status_embed()
            return await interaction.response.send_message(embed=status_embed, view=sub_view, ephemeral=True)

        # 9. TIÊN TRI (RÀNG BUỘC KỸ NĂNG THEO CHU KỲ TRĂNG)
        elif role == "seer":
            if self.night_data.get("event") == "new_moon":
                return await interaction.response.send_message("🌑 **TRĂNG NON:** Đêm nay mất đi linh lực mặt trăng, Tiên Tri không thể soi ai!", ephemeral=True)

            other_players = [p for p in self.alive_players if p.id != uid]
            if not other_players: 
                return await interaction.response.send_message("❌ Không còn ai để soi!", ephemeral=True)

            max_inspect = 2 if self.night_data.get("event") == "full_moon" else 1
            seer_sub = SeerNightActionSubView(self, uid, other_players, max_inspect)
            return await interaction.response.send_message(
                f"🔮 **GIAO DIỆN SOI CỦA TIÊN TRI** (Đêm nay được chọn tối đa **{max_inspect}** người):", 
                view=seer_sub, 
                ephemeral=True
            )

        # 10. BẢO VỆ
        elif role == "doctor":
            options = [discord.SelectOption(label=p.display_name, value=str(p.id), emoji="🛡️") for p in self.alive_players[:25]]
            select = Select(placeholder="🛡️ Chọn duy nhất 1 người để bảo vệ đêm nay...", options=options)

            async def doctor_callback(i: discord.Interaction):
                if len(select.values) > 1:
                    return await i.response.send_message("❌ Bạn chỉ được chọn duy nhất 1 mục tiêu!", ephemeral=True)

                if i.user.id not in [p.id for p in self.alive_players]:
                    return await i.response.send_message("❌ Bạn đã chết!", ephemeral=True)
                if i.user.id in self.night_data["acted_players"]:
                    return await i.response.send_message("❌ Bạn đã bảo vệ đêm nay rồi!", ephemeral=True)

                target_id = int(select.values[0])
                self.night_data["protected_id"] = target_id
                self.night_data["acted_players"].add(i.user.id)
                target_p = i.guild.get_member(target_id)
                await i.response.send_message(f"🛡️ Đã chọn bảo vệ **{target_p.display_name}**!", ephemeral=True)

            select.callback = doctor_callback
            view = View(timeout=30); view.add_item(select)
            return await interaction.response.send_message("🛡️ **BẢNG BẢO VỆ:**", view=view, ephemeral=True)

        # 11. NHÀ TÂM LÝ
        elif role == "psychiatrist":
            if self.night_data.get("event") != "blue_moon":
                return await interaction.response.send_message("🧠 Đêm nay không có Trăng Xanh, tâm trí mọi người bình thường!", ephemeral=True)
            
            options = [discord.SelectOption(label=p.display_name, value=str(p.id), emoji="🧠") for p in self.alive_players[:25]]
            select = Select(placeholder="🧠 Chọn tối đa 2 người để chữa trị tâm lý...", min_values=1, max_values=min(2, len(options)), options=options)

            async def psych_callback(i: discord.Interaction):
                if len(select.values) > 2:
                    return await i.response.send_message("❌ Bạn chỉ được chọn tối đa 2 mục tiêu!", ephemeral=True)

                if i.user.id not in [p.id for p in self.alive_players]:
                    return await i.response.send_message("❌ Bạn đã chết!", ephemeral=True)
                if i.user.id in self.night_data["acted_players"]:
                    return await i.response.send_message("❌ Bạn đã chữa trị đêm nay rồi!", ephemeral=True)

                c_ids = [int(v) for v in select.values]
                self.night_data["cured_ids"] = c_ids
                self.night_data["acted_players"].add(i.user.id)
                c_names = ", ".join([i.guild.get_member(cid).display_name for cid in c_ids])
                await i.response.send_message(f"🧠 Bạn đã chữa trị giúp **{c_names}** không bị phát điên!", ephemeral=True)

            select.callback = psych_callback
            view = View(timeout=30); view.add_item(select)
            return await interaction.response.send_message("🧠 **BẢNG NHÀ TÂM LÝ (Được chọn 2 người):**", view=view, ephemeral=True)

        # 12. NGHIỆN NHÂN (NGHẸO CHỦ ĐỘNG)
        elif role == "addict":
            addict_sub = AddictNightActionSubView(self, uid)
            return await interaction.response.send_message(
                "🌿 **BẢNG ĐIỀU KHIỂN CỦA NGHIỆN NHÂN:** Nhấn nút dưới đây để thức đêm:",
                view=addict_sub,
                ephemeral=True
            )

        else:
            return await interaction.response.send_message(f"👨‍🌾 Bạn là **{r_info['name']}**. Hãy nhắm mắt ngủ ngoan chờ ban ngày nhé!", ephemeral=True)

    @discord.ui.button(label="Tình hình trong làng", style=discord.ButtonStyle.secondary, emoji="📜", row=0)
    async def village_status(self, interaction: discord.Interaction, button: Button):
        all_p = self.game_data.get("all_players", self.alive_players)
        alive_mentions = [p.mention for p in self.alive_players]
        dead_p_ids = [p.id for p in all_p if p.id not in [ap.id for ap in self.alive_players]]
        dead_mentions = [f"<@{pid}>" for pid in dead_p_ids]
        
        status_embed = discord.Embed(
            title=f"📜 BẢN TIN TÌNH HÌNH TRONG LÀNG (NGÀY {self.day_count})",
            color=discord.Color.blue()
        )
        status_embed.add_field(name="👥 Cư Dân Còn Sống", value=", ".join(alive_mentions) if alive_mentions else "Không có ai", inline=False)
        status_embed.add_field(name="💀 Linh Hồn Đã Lìa Xác", value=", ".join(dead_mentions) if dead_mentions else "Không có ai", inline=False)
        
        # Mô tả chu kỳ trăng hiện tại
        event_map = {
            "normal": "✨ Đêm bình thường không có biến động.",
            "blue_moon": "💙 Trăng Xanh: Tâm trí đảo lộn, dễ phát điên tàn sát nhau.",
            "blood_moon": "🩸 Trăng Máu: Sức mạnh Ma Sói tăng, Ma Cà Rồng hoạt động.",
            "full_moon": "🌕 Trăng Tròn: Quyến rũ dân thường hóa Sói, Tiên Tri mở thiên nhãn soi x2.",
            "new_moon": "🌑 Trăng Non: Ma Sói & Tiên Tri bị phế linh lực."
        }
        status_embed.add_field(name="🌙 Thời Tiết Đêm Nay", value=event_map.get(self.night_data.get("event"), "Bình thường"), inline=False)
        
        await interaction.response.send_message(embed=status_embed, ephemeral=True)


class WerewolfLobbyView(View):
    def __init__(self, host: discord.Member):
        super().__init__(timeout=600)
        self.host = host
        self.players = {host.id: host}
        self.max_players = 100
        self.discussion_minutes = 3
        self.show_votes = True
        self.wolf_setting = "25%"
        self.modified_mode = False
        self.game_started = False
        self.forced_roles = {}

    def generate_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🐺 TRÒ CHƠI: MA SÓI (WEREWOLF DISCORD)",
            description=(
                "═══════════════════════════════════\n"
                "📜 **LUẬT CHƠI MẶC ĐỊNH:**\n"
                "• **Ban đêm:** Các vai trò thực hiện kỹ năng bí mật.\n"
                f"• **Ban ngày:** Cả làng có **{self.discussion_minutes} phút** thảo luận tìm Ma Sói.\n"
                "• **Phe Dân thắng:** Loại sạch toàn bộ Ma Sói.\n"
                "• **Phe Sói thắng:** Số Sói bằng hoặc nhiều hơn Dân Làng còn sống.\n"
                "• **Phe Cặp Đôi (Sói + Dân):** Là 2 người sống sót cuối cùng!\n"
                "═══════════════════════════════════\n\n"
                "⏱️ *Sảnh chờ tự động hủy sau **10 phút** nếu chưa bắt đầu.*\n"
                "👉 Bấm nút **[🎉 Tham Gia]** bên dưới để gia nhập làng!"
            ),
            color=discord.Color.dark_red()
        )
        p_list = "\n".join([f"• {p.mention} (**{p.display_name}**)" for p in self.players.values()])
        embed.add_field(name=f"👥 NGƯỜI THAM GIA ({len(self.players)}/{self.max_players} - Tối thiểu 4)", value=p_list, inline=False)
        
        mod_status = "⚡ BẬT (Trăng Xanh, Trăng Máu, Trăng Tròn, Trăng Non + Roles Độc Lạ)" if self.modified_mode else "❄️ TẮT (Chế Độ Thường Chuẩn)"
        vote_status = "📊 Hiện Chi Tiết" if self.show_votes else "⚪ Ẩn Người Bầu"
        
        embed.add_field(name="🔀 Chế Độ Modified", value=mod_status, inline=True)
        embed.add_field(name="🗳️ Hiển Thị Vote", value=vote_status, inline=True)
        embed.add_field(name="🐺 Cấu Hình Sói", value=f"**{self.wolf_setting}**", inline=True)
        
        if self.forced_roles:
            f_lines = [f"• <@{uid}> ➔ **{ROLES_INFO[r]['name']}**" for uid, r in self.forced_roles.items()]
            embed.add_field(name="🛠️ Force Roles Đã Cài", value="\n".join(f_lines), inline=False)

        return embed

    @discord.ui.button(label="Tham Gia / Rời Khỏi", style=discord.ButtonStyle.success, emoji="🎉", row=0)
    async def join_toggle(self, interaction: discord.Interaction, button: Button):
        user = interaction.user
        if user.id in self.players:
            if user.id == self.host.id: return await interaction.response.send_message("❌ Chủ phòng không thể rời!", ephemeral=True)
            del self.players[user.id]
            if user.id in self.forced_roles: del self.forced_roles[user.id]
            await interaction.response.send_message("🏃 Đã rời làng.", ephemeral=True)
        else:
            if len(self.players) >= self.max_players: return await interaction.response.send_message("❌ Sảnh đã đầy!", ephemeral=True)
            self.players[user.id] = user
            await interaction.response.send_message("🎉 Đã gia nhập làng!", ephemeral=True)
        try: await interaction.message.edit(embed=self.generate_embed(), view=self)
        except Exception: pass

    @discord.ui.button(label="Modified: BẬT/TẮT", style=discord.ButtonStyle.primary, emoji="🔀", row=0)
    async def toggle_mod(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.host.id: return await interaction.response.send_message("❌ Chỉ chủ phòng!", ephemeral=True)
        self.modified_mode = not self.modified_mode
        status_str = "BẬT ⚡" if self.modified_mode else "TẮT ❄️"
        await interaction.response.send_message(f"✅ Đã chuyển Chế Độ Modified sang: **{status_str}**", ephemeral=True)
        try: await interaction.message.edit(embed=self.generate_embed(), view=self)
        except Exception: pass

    @discord.ui.button(label="Cài Đặt Phòng", style=discord.ButtonStyle.secondary, emoji="⚙️", row=0)
    async def config_room(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.host.id: return await interaction.response.send_message("❌ Chỉ chủ phòng!", ephemeral=True)
        await interaction.response.send_modal(WerewolfSettingsModal(self))

    @discord.ui.button(label="📖 Hướng Dẫn Roles", style=discord.ButtonStyle.secondary, emoji="📖", row=1)
    async def show_guide(self, interaction: discord.Interaction, button: Button):
        guide_embed = discord.Embed(title="📖 HƯỚNG DẪN CÁC VAI TRÒ MODIFIED DỊ", color=discord.Color.purple())
        for r_key, r_info in ROLES_INFO.items():
            guide_embed.add_field(name=f"{r_info['emoji']} {r_info['name']} (`{r_key}`)", value=f"• {r_info['desc']}", inline=False)
        await interaction.response.send_message(embed=guide_embed, ephemeral=True)

    @discord.ui.button(label="🛠️ Force Role (Dev)", style=discord.ButtonStyle.secondary, emoji="🛠️", row=1)
    async def force_role_btn(self, interaction: discord.Interaction, button: Button):
        is_admin = interaction.user.guild_permissions.manage_messages or str(interaction.user.id) in [owner_id] + subowner_id
        if interaction.user.id != self.host.id and not is_admin:
            return await interaction.response.send_message("❌ Chỉ Chủ Phòng hoặc Admin mới có quyền Force Role!", ephemeral=True)
        await interaction.response.send_modal(ForceRoleModal(self))

    @discord.ui.button(label="BẮT ĐẦU GAME", style=discord.ButtonStyle.danger, emoji="🚀", row=1)
    async def start_game(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.host.id: return await interaction.response.send_message("❌ Chỉ chủ phòng!", ephemeral=True)
        if len(self.players) < 4: return await interaction.response.send_message("❌ Cần ít nhất 4 người!", ephemeral=True)
        self.game_started = True
        for child in self.children: child.disabled = True
        try: await interaction.response.edit_message(embed=self.generate_embed(), view=self)
        except Exception: pass
        self.stop()


class WerewolfVotingView(View):
    def __init__(self, alive_players: list):
        super().__init__(timeout=60)
        self.alive_players = alive_players
        self.votes = {}
        self.page = 0
        self.per_page = 20
        self.update_components()

    def update_components(self):
        self.clear_items()
        start_idx = self.page * self.per_page
        end_idx = start_idx + self.per_page
        current_batch = self.alive_players[start_idx:end_idx]

        options = [discord.SelectOption(label=p.display_name, value=str(p.id), emoji="🗳️") for p in current_batch]
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

        if end_idx < len(self.alive_players):
            btn_next = Button(label="▶ Trang Sau", style=discord.ButtonStyle.secondary, row=1)
            btn_next.callback = self.next_page
            self.add_item(btn_next)

        btn_skip = Button(label="⚪ Bỏ Phiếu Trắng", style=discord.ButtonStyle.danger, row=1)
        btn_skip.callback = self.skip_callback
        self.add_item(btn_skip)

    async def prev_page(self, interaction: discord.Interaction):
        if interaction.user.id not in [p.id for p in self.alive_players]:
            return await interaction.response.send_message("❌ Bạn không còn sống!", ephemeral=True)
        self.page -= 1
        self.update_components()
        await interaction.response.edit_message(view=self)

    async def next_page(self, interaction: discord.Interaction):
        if interaction.user.id not in [p.id for p in self.alive_players]:
            return await interaction.response.send_message("❌ Bạn không còn sống!", ephemeral=True)
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
        await interaction.response.send_message(f"🗳️ Bạn đã bỏ phiếu treo cổ **{target_member.display_name}**!", ephemeral=True)

    async def skip_callback(self, interaction: discord.Interaction):
        voter_id = interaction.user.id
        if voter_id not in [p.id for p in self.alive_players]:
            return await interaction.response.send_message("❌ Bạn không còn sống!", ephemeral=True)
        if voter_id in self.votes:
            return await interaction.response.send_message("❌ Bạn đã bỏ phiếu rồi!", ephemeral=True)

        self.votes[voter_id] = "skip"
        await interaction.response.send_message("⚪ Bạn đã chọn **Bỏ phiếu trắng**!", ephemeral=True)


class VictorySummaryView(View):
    def __init__(self, ctx, winning_side: str, winning_title: str, winners_lines: list, roster_lines: list):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.winning_side = winning_side
        self.winning_title = winning_title
        self.winners_lines = winners_lines
        self.roster_lines = roster_lines
        self.page = 0
        self.per_page = 10
        self.total_pages = max(1, math.ceil(len(roster_lines) / self.per_page))
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        if self.total_pages > 1:
            btn_prev = Button(label="◀ Trang Trước", style=discord.ButtonStyle.secondary, disabled=(self.page == 0))
            btn_prev.callback = self.prev_page
            self.add_item(btn_prev)

            btn_next = Button(label="Trang Sau ▶", style=discord.ButtonStyle.secondary, disabled=(self.page == self.total_pages - 1))
            btn_next.callback = self.next_page
            self.add_item(btn_next)

    def generate_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"🏆 {self.winning_title}",
            description=f"═══════════════════════════════════\n**KẾT THÚC VÁN ĐẤU MA SÓI!** (Trang {self.page + 1}/{self.total_pages})\n═══════════════════════════════════",
            color=discord.Color.pink() if self.winning_side == "lovers" else (discord.Color.gold() if self.winning_side == "good" else discord.Color.red())
        )

        win_text = "\n".join(self.winners_lines) if self.winners_lines else "Không có ai"
        if len(win_text) > 1000:
            win_text = win_text[:990] + "\n..."
        embed.add_field(name="🎉 NGƯỜI CHIẾN THẮNG & DISCORD ID", value=win_text, inline=False)

        start = self.page * self.per_page
        end = start + self.per_page
        current_roster = self.roster_lines[start:end]
        roster_text = "\n".join(current_roster) if current_roster else "Không có dữ liệu"
        if len(roster_text) > 1000:
            roster_text = roster_text[:990] + "\n..."

        embed.add_field(name=f"📜 DANH SÁCH NGƯỜI CHƠI ({start + 1}-{min(end, len(self.roster_lines))}/{len(self.roster_lines)})", value=roster_text, inline=False)

        return embed

    async def prev_page(self, interaction: discord.Interaction):
        self.page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.generate_embed(), view=self)

    async def next_page(self, interaction: discord.Interaction):
        self.page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.generate_embed(), view=self)


# ==============================================================================
#                               COG SYSTEM CLASS
# ==============================================================================

class PartyGamesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_games = {}

    async def send_werewolf_victory_summary(self, ctx, winning_side: str, winning_title: str, all_players: list, alive_players: list, player_roles: dict, lovers_tuple: tuple = None):
        """Hàm dựng Bảng Tổng Kết Phân Trang hỗ trợ cả chiến thắng Phe Cặp Đôi (Lovers)"""
        winners_lines = []
        for p in all_players:
            p_role = player_roles[p.id]
            p_side = ROLES_INFO[p_role]["side"]
            
            is_winner = False
            if winning_side == "lovers" and lovers_tuple and p.id in lovers_tuple:
                is_winner = True
            elif winning_side != "lovers" and p_side == winning_side:
                is_winner = True

            if is_winner:
                role_info = ROLES_INFO[p_role]
                winners_lines.append(f"• {p.mention} - `{p.id}` ➔ **{role_info['emoji']} {role_info['name']}**")

        roster_lines = []
        for p in all_players:
            role_info = ROLES_INFO[player_roles[p.id]]
            status = "💚 Còn sống" if p in alive_players else "💀 Đã chết"
            roster_lines.append(f"• {p.mention} (`{p.id}`) ➔ **{role_info['emoji']} {role_info['name']}** ({status})")

        view = VictorySummaryView(ctx, winning_side, winning_title, winners_lines, roster_lines)
        embed = view.generate_embed()

        await send_fancy_event_message(ctx, embed, "day.png", view=view if view.total_pages > 1 else None)

    @commands.hybrid_command(name="stopgame", aliases=["dunggame"], description="Dừng khẩn cấp ván game đang diễn ra và công khai toàn bộ bí mật")
    async def stopgame(self, ctx):
        cid = ctx.channel.id
        if cid not in self.active_games:
            return await ctx.send("❌ Không có trận đấu nào đang diễn ra trong kênh này!")

        game_data = self.active_games[cid]
        is_host = ctx.author.id == game_data["host_id"]
        is_admin = ctx.author.guild_permissions.manage_messages or str(ctx.author.id) in [owner_id] + subowner_id

        if not (is_host or is_admin):
            return await ctx.send("❌ Chỉ Chủ Phòng hoặc Admin mới có quyền dừng!", ephemeral=True)

        game_data["stopped"] = True
        embed = discord.Embed(title="🛑 TRẬN ĐẤU ĐÃ BỊ DỪNG KHẨN CẤP", description="Bảng công khai toàn bộ bí mật của trận đấu:", color=discord.Color.red())

        if game_data["type"] == "spy":
            embed.add_field(name="📜 Cặp từ", value=f"• Dân: **{game_data['word_civ']}**\n• Sói: **{game_data['word_spy']}**", inline=False)
            embed.add_field(name="🕵️ Phe Gián Điệp", value=", ".join([p.mention for p in game_data["spies"]]) or "Không", inline=False)
            embed.add_field(name="👨‍🌾 Phe Dân", value=", ".join([p.mention for p in game_data["civs"]]) or "Không", inline=False)

        elif game_data["type"] == "werewolf":
            role_lines = [f"• {p.mention} (`{p.id}`): **{ROLES_INFO[game_data['player_roles'][p.id]]['emoji']} {ROLES_INFO[game_data['player_roles'][p.id]]['name']}**" for p in game_data["all_players"]]
            embed.add_field(name="🔮 Vai trò chi tiết", value="\n".join(role_lines), inline=False)

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


    @commands.hybrid_command(name="masoi", aliases=["werewolf"], description="Mở sảnh chơi Ma Sói (Werewolf)")
    async def masoi(self, ctx):
        cid = ctx.channel.id
        if cid in self.active_games: return await ctx.send("❌ Đã có một trận đấu đang diễn ra trong kênh này!")

        lobby_view = WerewolfLobbyView(ctx.author)
        await ctx.send(embed=lobby_view.generate_embed(), view=lobby_view)
        await lobby_view.wait()

        if not lobby_view.game_started: return await ctx.send("⏰ **Sảnh game đã hết thời gian chờ hoặc bị hủy!**")

        all_players = list(lobby_view.players.values())
        total_p = len(all_players)
        disc_mins = lobby_view.discussion_minutes
        mod_mode = lobby_view.modified_mode
        show_votes = lobby_view.show_votes

        player_roles = {}
        unassigned_players = []

        for p in all_players:
            if p.id in lobby_view.forced_roles:
                player_roles[p.id] = lobby_view.forced_roles[p.id]
            else:
                unassigned_players.append(p)

        num_wolves = calculate_wolf_count(lobby_view.wolf_setting, total_p)

        if not mod_mode:
            role_pool = ["wolf"] * num_wolves + ["seer", "doctor", "witch", "mayor", "cupid", "hunter"]
        else:
            role_pool = ["wolf"] * num_wolves + ["seer", "doctor", "witch", "mayor", "cupid", "hunter"]
            if random.random() < 0.30: role_pool.append("vampire")
            role_pool.append("chemist")
            role_pool.append("psychiatrist")
            role_pool.append("addict")
            if random.random() < 0.5: role_pool.append("corrupted")
            if random.random() < 0.01: role_pool.append("drug_lord")
            if random.random() < 0.02: role_pool.append("furry")
            if random.random() < 0.02: role_pool.append("misanthrope")

        while len(role_pool) < len(unassigned_players): role_pool.append("villager")
        random.shuffle(role_pool)

        for i, p in enumerate(unassigned_players):
            player_roles[p.id] = role_pool[i]

        game_data = {"type": "werewolf", "host_id": ctx.author.id, "stopped": False, "player_roles": player_roles, "all_players": all_players}
        self.active_games[cid] = game_data

        for p in all_players:
            r_info = ROLES_INFO[player_roles[p.id]]
            try: await p.send(embed=discord.Embed(title=f"🔮 VAI TRÒ CỦA BẠN: {r_info['emoji']} {r_info['name']}", description=r_info['desc'], color=discord.Color.gold()))
            except Exception: pass

        start_embed = discord.Embed(
            title="🐺 TRẬN ĐẤU MA SÓI BẮT ĐẦU!",
            description="═══════════════════════════════════\n*Màn đêm buông xuống ngôi làng... Mọi người hãy nhận vai trò bí mật qua DM!*\n═══════════════════════════════════",
            color=discord.Color.dark_red()
        )
        await send_fancy_event_message(ctx, start_embed, "night.png")
        await asyncio.sleep(2)

        alive_players = list(all_players)
        day_count = 1
        lovers_tuple = None

        witch_state = {"heal_used": False, "poison_used": False}
        chemist_state = {"nuke_used": False, "revive_cd": 0}
        gian_dan_last_used = {}

        while True:
            if game_data.get("stopped"): break

            if chemist_state["revive_cd"] > 0: chemist_state["revive_cd"] -= 1

            night_event = "normal"
            asset_img = "night.png"

            if mod_mode:
                if day_count % 15 == 0: 
                    night_event = "blood_moon"
                    asset_img = "blood_moon.png"
                elif day_count % 7 == 0: 
                    night_event = "blue_moon"
                    asset_img = "blue_moon.png"
                elif day_count == 10 or (day_count > 5 and (day_count - 5) % 10 == 0): 
                    night_event = "new_moon"
                    asset_img = "night.png"
                elif day_count % 5 == 0: 
                    night_event = "full_moon"
                    asset_img = "night.png"

            event_title = ""
            if night_event == "blue_moon": event_title = "\n💙 **SỰ KIỆN: TRĂNG XANH!** *(Làm tâm trí dân làng bị đảo lộn và phát điên!)*"
            elif night_event == "blood_moon": event_title = "\n🩸 **SỰ KIỆN: TRĂNG MÁU!** *(Ma Sói cắn đẫm máu & Ma Cà Rồng đi lây nhiễm!)*"
            elif night_event == "full_moon": event_title = "\n🌕 **SỰ KIỆN: TRĂNG TRÒN!** *(Tiên Tri soi 2 người. 1 Dân Làng bị lôi kéo theo Phe Sói!)*"
            elif night_event == "new_moon": event_title = "\n🌑 **SỰ KIỆN: TRĂNG NON (ĐÉO CÓ TRĂNG)!** *(Sói & Tri BỊ PHẾ! Chỉ có Nghẹo nhìn thấy sự thật!)*"

            if night_event == "full_moon":
                civs_alive = [p for p in alive_players if ROLES_INFO[player_roles[p.id]]["side"] == "good" and player_roles[p.id] != "seer"]
                if civs_alive:
                    converted = random.choice(civs_alive)
                    player_roles[converted.id] = "wolf"
                    try: await converted.send("🌕 **SỰ KIỆN TRĂNG TRÒN:** Bạn đã bị ma lực mặt trăng quyến rũ và bí mật biến thành **MA SÓI 🐺**!")
                    except Exception: pass

            night_data = {
                "event": night_event,
                "wolf_votes": {},
                "protected_id": None,
                "cured_ids": [],
                "avenger_kill_id": None,
                "vampire_infect_id": None,
                "corrupted_stab_id": None,
                "witch_poison_id": None,
                "lovers": lovers_tuple,
                "witch_heal_action": False,
                "chemist_heal_action": False,
                "chemist_nuke_wolf": False,
                "chemist_nuke_civ": False,
                "current_wolf_target": None,
                "acted_players": set()
            }

            night_view = NightActionView(player_roles, alive_players, night_data, day_count, witch_state, chemist_state, gian_dan_last_used, game_data, self.bot)
            night_embed = discord.Embed(
                title=f"🌙 ĐÊM THỨ {day_count}",
                description=f"═══════════════════════════════════{event_title}\n*Cả làng đi ngủ... Các vai trò bấm nút bên dưới để thực hiện kỹ năng! (30 giây)*\n═══════════════════════════════════",
                color=discord.Color.dark_purple()
            )

            night_msg = await send_fancy_event_message(ctx, night_embed, asset_img, view=night_view)

            await asyncio.sleep(30)

            for child in night_view.children: child.disabled = True
            try: await night_msg.edit(view=night_view)
            except Exception: pass

            if game_data.get("stopped"): break

            if night_data.get("lovers"): lovers_tuple = night_data["lovers"]

            if night_data["vampire_infect_id"]:
                inf_id = night_data["vampire_infect_id"]
                player_roles[inf_id] = "vampire"
                inf_p = ctx.guild.get_member(inf_id)
                try: await inf_p.send("🧛 **BẠN ĐÃ BỊ CẮN!** Bạn đã bị Ma Cà Rồng đồng hóa biến thành **MA CÀ RỒNG 🧛**!")
                except Exception: pass

            if night_data["chemist_nuke_wolf"]:
                wolves_alive = [p for p in alive_players if ROLES_INFO[player_roles[p.id]]["side"] == "evil"]
                if wolves_alive:
                    kill_count = max(1, math.ceil(len(wolves_alive) / 2))
                    nuked = random.sample(wolves_alive, kill_count)
                    alive_players = [p for p in alive_players if p not in nuked]
                    await ctx.channel.send(f"☣️ **SIÊU HÓA CHẤT PHÁT NỔ!** Hóa Học Gia đã ném bình độc tiêu diệt **50% số lượng Phe Ma Sói** ({', '.join([p.mention for p in nuked])})!")
            elif night_data["chemist_nuke_civ"]:
                civs_alive = [p for p in alive_players if ROLES_INFO[player_roles[p.id]]["side"] == "good"]
                if civs_alive:
                    kill_count = max(1, math.ceil(len(civs_alive) / 2))
                    nuked = random.sample(civs_alive, kill_count)
                    alive_players = [p for p in alive_players if p not in nuked]
                    await ctx.channel.send(f"☣️ **SIÊU HÓA CHẤT PHÁT NỔ!** Hóa Học Gia đã sẩy tay ném bình độc tiêu diệt **50% số lượng Phe Dân Làng** ({', '.join([p.mention for p in nuked])})!")

            killed_players = []
            addict_deal_text = ""

            if night_data["wolf_votes"]:
                all_targets = []
                for voter_id, t_list in night_data["wolf_votes"].items():
                    weight = 2 if player_roles.get(voter_id) == "alpha_wolf" else 1
                    for _ in range(weight):
                        all_targets.extend(t_list)

                from collections import Counter
                counts = Counter(all_targets)
                most_voted = [tid for tid, _ in counts.most_common(1)]

                for tid in most_voted:
                    night_data["current_wolf_target"] = tid
                    is_saved = (tid == night_data["protected_id"]) or night_data["witch_heal_action"] or night_data["chemist_heal_action"]
                    if not is_saved:
                        target_p = ctx.guild.get_member(tid)
                        target_role = player_roles[tid]

                        if target_role == "addict":
                            addict_user_data = get_user_data(str(tid))
                            if addict_user_data.get("money", 0) >= 2000:
                                addict_user_data["money"] -= 2000
                                save_data(player_inventory)
                                addict_deal_text += f"\n🌿 {target_p.mention} (**Nghiện Nhân**) đã xì **2,000 Kesling** mua mai thúy nên được tha mạng đêm nay!"
                            else:
                                killed_players.append(target_p)
                                addict_deal_text += f"\n🩸 {target_p.mention} (**Nghiện Nhân**) không đủ tiền mua hàng nên đã bị diệt khẩu!"
                        elif target_role == "furry" and random.random() < 0.5:
                            pass
                        else:
                            killed_players.append(target_p)

            if night_data["corrupted_stab_id"]:
                stab_id = night_data["corrupted_stab_id"]
                if stab_id != night_data["protected_id"]:
                    stab_p = ctx.guild.get_member(stab_id)
                    if stab_p: killed_players.append(stab_p)

            if night_data["witch_poison_id"]:
                pois_id = night_data["witch_poison_id"]
                pois_p = ctx.guild.get_member(pois_id)
                if pois_p: killed_players.append(pois_p)

            if night_data["avenger_kill_id"]:
                avg_target_id = night_data["avenger_kill_id"]
                if avg_target_id != night_data["protected_id"]:
                    avg_p = ctx.guild.get_member(avg_target_id)
                    if avg_p: killed_players.append(avg_p)

            mad_kill_text = ""
            if night_event == "blue_moon" and len(alive_players) >= 3:
                mad_person = random.choice(alive_players)
                cured_list = night_data.get("cured_ids", [])
                
                if mad_person.id in cured_list:
                    mad_kill_text = f"\n🛡️ Đêm qua {mad_person.mention} suýt nữa phát điên tàn sát, nhưng nhờ có Nhà Tâm Lý chữa trị kịp thời nên đã bình an!"
                else:
                    mad_victim = random.choice([p for p in alive_players if p.id != mad_person.id])
                    killed_players.append(mad_victim)
                    mad_kill_text = f"\n💙 Trong cơn điên Trăng Xanh, {mad_person.mention} đã cầm dao đâm chết {mad_victim.mention}!"

            lovers_death_text = ""
            if lovers_tuple:
                p1_id, p2_id = lovers_tuple
                killed_ids = [p.id for p in killed_players]

                if p1_id in killed_ids and p2_id not in killed_ids:
                    dead_partner_id, survivor_id = p1_id, p2_id
                elif p2_id in killed_ids and p1_id not in killed_ids:
                    dead_partner_id, survivor_id = p2_id, p1_id
                else:
                    dead_partner_id, survivor_id = None, None

                if survivor_id and survivor_id in [p.id for p in alive_players]:
                    survivor_p = ctx.guild.get_member(survivor_id)
                    if random.random() < 0.70:
                        killed_players.append(survivor_p)
                        lovers_death_text += f"\n💔 {survivor_p.mention} vì quá đau buồn khi người yêu qua đời nên đã tự sát chết theo!"
                    else:
                        player_roles[survivor_id] = "avenger"
                        lovers_death_text += f"\n🗡️ {survivor_p.mention} chứng kiến tình nhân bị sát hại đã hóa thành **KẺ HẬN THÙ (PHE 3)** để trả thù toàn bộ ngôi làng!"
                        try: await survivor_p.send("🗡️ **TRẢ THÙ:** Bạn đã biến thành **KẺ HẬN THÙ**! Mỗi đêm bạn sẽ được chọn giết 1 người để trả thù cho tình nhân!")
                        except Exception: pass

            # BAN NGÀY
            day_embed = discord.Embed(
                title=f"☀️ NGÀY THỨ {day_count}",
                description="═══════════════════════════════════\n*Mặt trời mọc, làng thức giấc!*\n═══════════════════════════════════",
                color=discord.Color.gold()
            )
            await send_fancy_event_message(ctx, day_embed, "day.png")

            if killed_players:
                killed_players = list(set(killed_players))
                for kp in killed_players:
                    alive_players = [p for p in alive_players if p.id != kp.id]

                    if player_roles[kp.id] == "hunter":
                        hunter_view = HunterShootView(kp.id, alive_players, alive_players)
                        await ctx.channel.send(f"🏹 **THỢ SĂN ({kp.mention}) ĐÃ CHẾT!** Bạn có 20 giây để chọn 1 người bắn chết theo!", view=hunter_view)
                        await asyncio.sleep(20)
                        if hunter_view.target_id:
                            shot_p = ctx.guild.get_member(hunter_view.target_id)
                            alive_players = [ap for ap in alive_players if ap.id != shot_p.id]
                            await ctx.channel.send(f"💥 **RẰM!** Trước khi trút hơi thở cuối cùng, Thợ Săn {kp.mention} đã giương cung bắn chết {shot_p.mention}!")

                k_mentions = ", ".join([kp.mention for kp in killed_players])
                await ctx.channel.send(f"🩸 **Tin buồn:** Đêm qua {k_mentions} đã bị sát hại đẫm máu!{mad_kill_text}{addict_deal_text}{lovers_death_text}")
            else:
                await ctx.channel.send(f"🛡️ **Tin vui:** Đêm qua trôi qua bình yên, không ai bị hại!{mad_kill_text}{addict_deal_text}")

            # CHECK WIN PHE CẶP ĐÔI (LOVERS WIN)
            if lovers_tuple and len(alive_players) == 2:
                alive_ids = set([p.id for p in alive_players])
                if alive_ids == set(lovers_tuple):
                    await self.send_werewolf_victory_summary(ctx, "lovers", "🎉 CẶP ĐÔI TÌNH NHÂN CHIẾN THẮNG!", all_players, alive_players, player_roles, lovers_tuple)
                    break

            current_wolves = [p for p in alive_players if ROLES_INFO[player_roles[p.id]]["side"] == "evil"]
            current_civs = [p for p in alive_players if ROLES_INFO[player_roles[p.id]]["side"] == "good"]

            if len(current_wolves) == 0:
                await self.send_werewolf_victory_summary(ctx, "good", "🎉 PHE DÂN LÀNG CHIẾN THẮNG!", all_players, alive_players, player_roles, lovers_tuple)
                break
            elif len(current_wolves) >= len(current_civs):
                await self.send_werewolf_victory_summary(ctx, "evil", "🐺 PHE MA SÓI CHIẾN THẮNG!", all_players, alive_players, player_roles, lovers_tuple)
                break

            disc_embed = discord.Embed(
                title=f"💬 THẢO LUẬN LÀNG (NGÀY {day_count})",
                description=f"👥 **Số lượng dân làng còn sống:** **{len(alive_players)} người**\n⏱️ Cả nhóm có **{disc_mins} PHÚT** để tranh luận!",
                color=discord.Color.green()
            )
            await ctx.channel.send(embed=disc_embed)

            total_sleep = disc_mins * 60
            if total_sleep > 60:
                await asyncio.sleep(total_sleep - 60)
                await ctx.channel.send("⏳ **CÒN 1 PHÚT ĐỂ BỎ PHIẾU TREO CỔ!**")
                await asyncio.sleep(60)
            else: await asyncio.sleep(total_sleep)

            if game_data.get("stopped"): break

            vote_view = WerewolfVotingView(alive_players)
            vote_embed = discord.Embed(
                title=f"⚖️ TÒA ÁN DÂN LÀNG VOTE TREO CỔ (NGÀY {day_count})",
                description="═══════════════════════════════════\nHãy dùng Menu chọn người nghi ngờ, bấm nút ◀ ▶ chuyển trang hoặc nút **[⚪ Bỏ Phiếu Trắng]** trong **45 giây**!\n═══════════════════════════════════",
                color=discord.Color.gold()
            )
            vote_msg = await send_fancy_event_message(ctx, vote_embed, "vote.png", view=vote_view)
            await asyncio.sleep(45)

            for child in vote_view.children: child.disabled = True
            try: await vote_msg.edit(view=vote_view)
            except Exception: pass

            if game_data.get("stopped"): break

            if vote_view.votes:
                tally = {}
                voted_by_map = {}

                for voter_id, target in vote_view.votes.items():
                    voter = ctx.guild.get_member(voter_id)
                    voter_role = player_roles[voter_id]
                    weight = 2 if voter_role == "mayor" else (0 if voter_role == "misanthrope" else 1)

                    if target == "skip":
                        target_key = "skip"
                        final_add = weight
                    else:
                        target_key = target
                        target_role = player_roles[int(target)]
                        final_add = weight * (4 if target_role == "misanthrope" else 1)

                    tally[target_key] = tally.get(target_key, 0) + final_add
                    if target_key not in voted_by_map: voted_by_map[target_key] = []
                    voted_by_map[target_key].append(voter.display_name)

                vote_stat_lines = []
                for target_key, count in tally.items():
                    voters_str = ", ".join(voted_by_map[target_key])
                    if target_key == "skip":
                        name_str = "⚪ Bỏ phiếu trắng"
                    else:
                        t_mem = ctx.guild.get_member(int(target_key))
                        name_str = f"**{t_mem.display_name}**"

                    if show_votes:
                        vote_stat_lines.append(f"• {name_str} ({count} phiếu) ➔ Bầu bởi: *{voters_str}*")
                    else:
                        vote_stat_lines.append(f"• {name_str}: **{count} phiếu**")

                max_v = max(tally.values())
                elim_ids = [tid for tid, c in tally.items() if c == max_v]

                result_vote_embed = discord.Embed(
                    title=f"📊 KẾT QUẢ BỎ PHIẾU (NGÀY {day_count})",
                    description="**Thống kê phiếu bầu:**\n" + "\n".join(vote_stat_lines),
                    color=discord.Color.purple()
                )

                if len(elim_ids) == 1:
                    max_target = elim_ids[0]
                    if max_target == "skip":
                        result_vote_embed.add_field(name="⚪ Quyết định cuối cùng", value="**Đa số bầu phiếu trắng! Hôm nay làng không treo cổ ai.**", inline=False)
                    else:
                        vout_id = int(max_target)
                        vout_p = ctx.guild.get_member(vout_id)
                        alive_players = [p for p in alive_players if p.id != vout_id]
                        role_name = ROLES_INFO[player_roles[vout_id]]["name"]
                        result_vote_embed.add_field(name="🔥 Quyết định cuối cùng", value=f"Dân làng đã treo cổ {vout_p.mention} (**{max_v} điểm**)! Anh ấy từng là: **{role_name}**!", inline=False)

                        if player_roles[vout_id] == "hunter":
                            hunter_view = HunterShootView(vout_id, alive_players, alive_players)
                            await ctx.channel.send(f"🏹 **THỢ SĂN ({vout_p.mention}) BỊ TREO CỔ!** Bạn có 20 giây để chọn 1 người bắn chết theo!", view=hunter_view)
                            await asyncio.sleep(20)
                            if hunter_view.target_id:
                                shot_p = ctx.guild.get_member(hunter_view.target_id)
                                alive_players = [ap for ap in alive_players if ap.id != shot_p.id]
                                await ctx.channel.send(f"💥 **RẰM!** Trước khi trút hơi thở cuối cùng, Thợ Săn {vout_p.mention} đã giương cung bắn chết {shot_p.mention}!")

                        if lovers_tuple and vout_id in lovers_tuple:
                            p1_id, p2_id = lovers_tuple
                            survivor_id = p2_id if vout_id == p1_id else p1_id
                            if survivor_id in [p.id for p in alive_players]:
                                survivor_p = ctx.guild.get_member(survivor_id)
                                if random.random() < 0.70:
                                    alive_players = [p for p in alive_players if p.id != survivor_id]
                                    result_vote_embed.add_field(name="💔 Tình Nhân Tự Sát", value=f"{survivor_p.mention} quá đau buồn khi người yêu bị treo cổ nên đã nhảy lên giàn giáo chết theo!", inline=False)
                                else:
                                    player_roles[survivor_id] = "avenger"
                                    result_vote_embed.add_field(name="🗡️ Kẻ Hận Thù Trỗi Dậy", value=f"{survivor_p.mention} phẫn uất vì người yêu bị làng treo cổ nên đã biến thành **KẺ HẬN THÙ (PHE 3)**!", inline=False)
                else:
                    result_vote_embed.add_field(name="⚖️ Quyết định cuối cùng", value="**Hòa phiếu!** Hôm nay làng không đưa được ai lên giàn giáo.", inline=False)

                await ctx.channel.send(embed=result_vote_embed)

            # CHECK WIN PHE CẶP ĐÔI (LOVERS WIN)
            if lovers_tuple and len(alive_players) == 2:
                alive_ids = set([p.id for p in alive_players])
                if alive_ids == set(lovers_tuple):
                    await self.send_werewolf_victory_summary(ctx, "lovers", "🎉 CẶP ĐÔI TÌNH NHÂN CHIẾN THẮNG!", all_players, alive_players, player_roles, lovers_tuple)
                    break

            current_wolves = [p for p in alive_players if ROLES_INFO[player_roles[p.id]]["side"] == "evil"]
            current_civs = [p for p in alive_players if ROLES_INFO[player_roles[p.id]]["side"] == "good"]

            if len(current_wolves) == 0:
                await self.send_werewolf_victory_summary(ctx, "good", "🎉 PHE DÂN LÀNG CHIẾN THẮNG!", all_players, alive_players, player_roles, lovers_tuple)
                break
            elif len(current_wolves) >= len(current_civs):
                await self.send_werewolf_victory_summary(ctx, "evil", "🐺 PHE MA SÓI CHIẾN THẮNG!", all_players, alive_players, player_roles, lovers_tuple)
                break

            day_count += 1
            await asyncio.sleep(3)

        if cid in self.active_games: del self.active_games[cid]


async def setup(bot):
    await bot.add_cog(PartyGamesCog(bot))