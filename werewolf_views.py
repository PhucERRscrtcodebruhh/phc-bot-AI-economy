# werewolf_views.py
import math
import random
import asyncio
import discord
from discord.ui import View, Modal, TextInput, Select, Button
from werewolf_data import ROLES_INFO

try:
    from AIphcbot import owner_id, subowner_id
except ImportError:
    owner_id = "0"
    subowner_id = []

async def run_phase_timer(channel, total_seconds: int, phase_name: str, stop_checker=None):
    """
    Hàm đếm ngược thời gian và tự động thông báo mốc thời gian còn lại:
    - Còn X phút / X-n phút
    - Còn 30 giây
    - Còn 5 giây khẩn cấp
    """
    start_time = asyncio.get_event_loop().time()
    half_time = total_seconds / 2

    announced_half = False
    announced_30s = False
    announced_5s = False

    while True:
        if stop_checker and stop_checker():
            break

        elapsed = asyncio.get_event_loop().time() - start_time
        remaining = total_seconds - elapsed

        if remaining <= 0:
            break

        # Cột mốc 1: Còn một nửa thời gian (nếu tổng thời gian >= 60s)
        if remaining <= half_time and not announced_half and total_seconds >= 60:
            announced_half = True
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            time_str = f"{mins} phút {secs} giây" if mins > 0 else f"{secs} giây"
            await channel.send(f"⏳ **[{phase_name}]** Thời gian trôi qua một nửa! Còn lại **{time_str}**...")

        # Cột mốc 2: Còn 30 giây
        elif remaining <= 30 and not announced_30s and total_seconds > 35:
            announced_30s = True
            await channel.send(f"⏰ **[{phase_name}]** Chỉ còn **30 giây** cuối cùng!")

        # Cột mốc 3: Còn 5 giây
        elif remaining <= 5 and not announced_5s:
            announced_5s = True
            await channel.send(f"⚠️ **[{phase_name}]** Khẩn cấp! Còn lại **5 giây**!")

        await asyncio.sleep(1)


class WerewolfSettingsModal(Modal, title="⚙️ Cài Đặt Phòng Ma Sói"):
    max_players_input = TextInput(label="Số người tối đa (4-100)", placeholder="Mặc định: 15", default="15", required=True, max_length=3)
    minutes_input = TextInput(label="Số phút thảo luận ban ngày (1-10)", placeholder="Mặc định: 3", default="3", required=True, max_length=2)
    night_minutes_input = TextInput(label="Số phút hành động ban đêm (1-5)", placeholder="Mặc định: 1", default="1", required=True, max_length=2)
    show_votes_input = TextInput(label="Hiển thị Chi Tiết Vote? (1: Có | 0: Ẩn)", placeholder="1 hoặc 0 (Mặc định 1)", default="1", required=True, max_length=1)
    wolf_count_input = TextInput(label="Số lượng/Tỉ lệ Sói (VD: 1, 6, hoặc 25%)", placeholder="Mặc định: 25%", default="25%", required=False, max_length=5)

    def __init__(self, lobby_view):
        super().__init__()
        self.lobby_view = lobby_view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            max_p = int(self.max_players_input.value.strip())
            mins = int(self.minutes_input.value.strip())
            n_mins = int(self.night_minutes_input.value.strip())
            svote = int(self.show_votes_input.value.strip())
            w_setting = self.wolf_count_input.value.strip() or "25%"
            if not (4 <= max_p <= 100) or not (1 <= mins <= 10) or not (1 <= n_mins <= 5) or svote not in (0, 1): raise ValueError
        except ValueError:
            return await interaction.response.send_message("❌ Nhập sai! Số người (4-100), Phút ngày (1-10), Phút đêm (1-5), Vote (1 hoặc 0)!", ephemeral=True)

        self.lobby_view.max_players = max_p
        self.lobby_view.discussion_minutes = mins
        self.lobby_view.night_minutes = n_mins
        self.lobby_view.show_votes = bool(svote)
        self.lobby_view.wolf_setting = w_setting
        await interaction.response.send_message(f"✅ Đã lưu cài đặt! Ngày: **{mins}P** | Đêm: **{n_mins}P** | Sói: **{w_setting}**", ephemeral=True)
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


class HunterTargetSelectSubView(View):
    """View ẩn chứa Dropdown danh sách mục tiêu cho Thợ Săn chọn"""
    def __init__(self, main_view, valid_targets: list):
        super().__init__(timeout=20)
        self.main_view = main_view

        options = [
            discord.SelectOption(label=p.display_name, value=str(p.id), emoji="🏹")
            for p in valid_targets[:25] if p.id != main_view.hunter_id
        ]
        if options:
            select = Select(placeholder="🏹 Chọn người bạn muốn bắn chết theo...", options=options)
            select.callback = self.select_cb
            self.add_item(select)

    async def select_cb(self, interaction: discord.Interaction):
        if interaction.user.id != self.main_view.hunter_id:
            return await interaction.response.send_message("❌ Bạn không phải Thợ Săn!", ephemeral=True)
        
        self.main_view.target_id = int(interaction.data["values"][0])
        target_p = interaction.guild.get_member(self.main_view.target_id)
        
        # Cập nhật phản hồi cho Thợ Săn
        await interaction.response.send_message(
            f"🎯 Bạn đã quyết định giương cung bắn vào **{target_p.display_name}**!", 
            ephemeral=True
        )
        
        # Đánh dấu hoàn thành và vô hiệu hóa nút ở View chính
        self.main_view.disabled_all()
        self.main_view.stop()
        self.stop()


class HunterShootView(View):
    """View chính chứa Nút bấm kích hoạt kỹ năng bắn của Thợ Săn"""
    def __init__(self, hunter_id: int, valid_targets: list, alive_players: list):
        super().__init__(timeout=25)
        self.hunter_id = hunter_id
        self.valid_targets = valid_targets
        self.alive_players = alive_players
        self.target_id = None
        self.message = None

    def disabled_all(self):
        for child in self.children:
            child.disabled = True

    @discord.ui.button(label="Bắn người chết theo", style=discord.ButtonStyle.danger, emoji="🏹")
    async def shoot_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.hunter_id:
            return await interaction.response.send_message("❌ Bạn không phải là Thợ Săn vừa nằm xuống!", ephemeral=True)

        if self.target_id is not None:
            return await interaction.response.send_message("❌ Bạn đã chọn mục tiêu bắn rồi!", ephemeral=True)

        # Mở Menu Dropdown ẩn (ephemeral) cho Thợ Săn chọn
        sub_view = HunterTargetSelectSubView(self, self.valid_targets)
        await interaction.response.send_message(
            "🏹 **DANH SÁCH MỤC TIÊU BAN NGÀY / ĐÊM:**\nHãy chọn 1 người chơi để kéo theo xuống mồ:",
            view=sub_view,
            ephemeral=True
        )

    async def on_timeout(self):
        self.disabled_all()
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass


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


class WerewolfCommModal(Modal, title="💬 Truyền Âm Đồng Bọn"):
    message_input = TextInput(label="Nội dung truyền âm", placeholder="Nhập lời muốn nói với đồng bọn bầy sói...", required=True, max_length=150)

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
            if w.id == self.sender.id: continue
            try:
                role_emoji = ROLES_INFO[self.player_roles[self.sender.id]]["emoji"]
                embed = discord.Embed(
                    title="💬 TIN TRUYỀN ÂM BẦY SÓI",
                    description=f"🐺 **{self.sender.display_name}** ({role_emoji}) gửi tín hiệu:\n💬 *\"{msg_text}\"*",
                    color=discord.Color.red()
                )
                embed.set_image(url="attachment://moon.png")
                await w.send(embed=embed)
                success_count += 1
            except Exception: pass
        
        await interaction.response.send_message(f"✅ Đã truyền âm thành công đến {success_count} đồng bọn trong bầy!", ephemeral=True)


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
        if len(interaction.data["values"]) > 1: return await interaction.response.send_message("❌ Bạn chỉ được chọn duy nhất 1 mục tiêu!", ephemeral=True)
        target_id = int(interaction.data["values"][0])
        self.outer.night_data["wolf_votes"][self.uid] = [target_id]
        embed = self.outer.generate_wolf_status_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="💬 Truyền Âm", style=discord.ButtonStyle.danger, row=1)
    async def transmit_sound(self, interaction: discord.Interaction, button: Button):
        modal = WerewolfCommModal(self.outer.bot, self.outer.alive_players, self.outer.player_roles, interaction.user)
        await interaction.response.send_modal(modal)


class SeerDayActionSubView(View):
    def __init__(self, outer, uid, other_players, max_inspect):
        super().__init__(timeout=30)
        self.outer = outer
        self.uid = uid
        self.max_inspect = max_inspect

        options = [discord.SelectOption(label=p.display_name, value=str(p.id), emoji="🔮") for p in other_players[:25]]
        select = Select(placeholder=f"🔮 Chọn tối đa {max_inspect} người bạn muốn soi...", min_values=1, max_values=min(max_inspect, len(options)), options=options)
        select.callback = self.inspect_callback
        self.add_item(select)

    async def inspect_callback(self, interaction: discord.Interaction):
        if len(interaction.data["values"]) > self.max_inspect: return await interaction.response.send_message(f"❌ Bạn chỉ được chọn tối đa {self.max_inspect} người!", ephemeral=True)
        
        if "acted_seers" not in self.outer.day_data:
            self.outer.day_data["acted_seers"] = set()
        self.outer.day_data["acted_seers"].add(self.uid)

        res_lines = []
        for val in interaction.data["values"]:
            target_id = int(val)
            target_role = self.outer.player_roles[target_id]
            target_p = interaction.guild.get_member(target_id)
            side_text = "🟢 **PHE THIỆN (DÂN LÀNG)**" if (target_role == "vampire" or ROLES_INFO[target_role]["side"] == "good") else "🔴 **PHE ÁC (MA SÓI)**"
            res_lines.append(f"• **{target_p.display_name}**: Anh ấy thuộc {side_text}!")

        embed = discord.Embed(
            title="🔮 KẾT QUẢ SOI KHẢO SÁT CHU KỲ TRĂNG",
            description="\n".join(res_lines),
            color=discord.Color.gold()
        )
        embed.set_image(url="attachment://dawn.png")

        await interaction.response.send_message(embed=embed, ephemeral=True)
        for child in self.children: child.disabled = True
        await interaction.edit_original_response(view=self)


class AddictNightActionSubView(View):
    def __init__(self, outer, uid):
        super().__init__(timeout=30)
        self.outer = outer
        self.uid = uid

    @discord.ui.button(label="🌿 Thực hiện hành động hít đá thức đêm", style=discord.ButtonStyle.success)
    async def smoke_action(self, interaction: discord.Interaction, button: Button):
        roll_chance = 1.0 if self.outer.night_data["event"] == "new_moon" else 0.30
        self.outer.night_data["acted_players"].add(self.uid)
        button.disabled = True
        await interaction.response.edit_message(view=self)

        if random.random() < roll_chance:
            vamps = [p for p in self.outer.alive_players if self.outer.player_roles.get(p.id) == "vampire"]
            wolves = [p for p in self.outer.alive_players if ROLES_INFO[self.outer.player_roles.get(p.id)]["side"] == "evil"]
            if vamps: hint_text = f"Mắt nhắm mắt mở phát hiện **{vamps[0].display_name}** chính là **MA CÀ RỒNG 🧛** đang lang thang hút máu!"
            elif wolves: hint_text = f"Lờ mờ nhìn thấy **{random.choice(wolves).display_name}** có hành tung mờ hờ giống Ma Sói!"
            else: hint_text = "Đêm nay im ắng quá..."
        else: hint_text = "Bú đá say khướt mắt mũi kèm nhèm không nhìn thấy gì cả!"

        extra_note = "\n🌑 *Đêm Trăng Non: Bạn là TIÊN TRI DUY NHẤT thức đêm nhìn thấu sự thật!*" if self.outer.night_data["event"] == "new_moon" else ""
        await interaction.followup.send(f"🌿 **CƠN NGHIỆN TRỖI DẬY:** Trong lúc thức đêm phê thuốc, bạn {hint_text}{extra_note}", ephemeral=True)


class NightActionView(View):
    def __init__(self, player_roles: dict, alive_players: list, night_data: dict, day_count: int, witch_state: dict, chemist_state: dict, gian_dan_last_used: dict, game_data: dict, bot):
        super().__init__(timeout=None)
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
        embed = discord.Embed(title="🐺 GIAO DIỆN PHÒNG CHAT & VOTE CỦA BẦY SÓI", description="Thống nhất mục tiêu để tiêu diệt dân làng đêm nay!", color=discord.Color.red())
        tally = {}
        for voter_id, targets in self.night_data["wolf_votes"].items():
            weight = 2 if self.player_roles.get(voter_id) == "alpha_wolf" else 1
            for t in targets: tally[t] = tally.get(t, 0) + weight
        tally_lines = [f"• **{(discord.utils.get(self.alive_players, id=tid) or f'ID: {tid}')}**: {w} Phiếu (Điểm)" for tid, w in tally.items()]
        embed.add_field(name="📊 Tiến độ bỏ phiếu hiện tại:", value="\n".join(tally_lines) if tally_lines else "Chưa có ai bỏ phiếu cắn.", inline=False)
        embed.add_field(name="💡 Gợi ý:", value="• Bấm nút **[💬 Truyền Âm]** bên dưới để truyền tin mật đến DMs của tất cả Sói còn sống.\n• Sói Đầu Đàn (Alpha Wolf) có số phiếu bầu x2.", inline=False)
        embed.set_image(url="attachment://moon.png")
        return embed

    @discord.ui.button(label="Hành động đêm", style=discord.ButtonStyle.primary, emoji="🌙", row=0)
    async def open_panel(self, interaction: discord.Interaction, button: Button):
        uid = interaction.user.id
        if uid not in [p.id for p in self.alive_players]: return await interaction.response.send_message("❌ Bạn đã chết!", ephemeral=True)
        if uid in self.night_data["acted_players"]: return await interaction.response.send_message("❌ Hôm nay bạn đã dùng kỹ năng ban đêm rồi!", ephemeral=True)

        role = self.player_roles[uid]

        if role == "seer":
            return await interaction.response.send_message("🔮 **Tiên Tri** chỉ có thể sử dụng kỹ năng tiên đoán vào **ban ngày**!", ephemeral=True)

        elif role == "god":
            class GodControlView(View):
                def __init__(self, outer): super().__init__(timeout=30); self.outer = outer
                @discord.ui.button(label="⚡ END GAME KHẨN CẤP", style=discord.ButtonStyle.danger)
                async def god_end(self, i, b):
                    if i.user.id not in [p.id for p in self.outer.alive_players]: return await i.response.send_message("❌ Bạn đã chết!", ephemeral=True)
                    self.outer.game_data["stopped"] = True
                    god_embed = discord.Embed(title="⚡ CHÚA ĐÃ PHÁN XÉT - KẾT THÚC GAME!", description=f"👑 **{i.user.mention}** (CHÚA) đã phán xét hòa bình!", color=discord.Color.gold())
                    god_embed.set_image(url="attachment://moon.png")
                    await i.channel.send(embed=god_embed)
                    await i.response.send_message("⚡ Đã kết thúc game thành công!", ephemeral=True)
                @discord.ui.button(label="🪄 BIẾN ĐỔI VAI TRÒ NGƯỜI CHƠI", style=discord.ButtonStyle.primary)
                async def god_mod(self, i, b):
                    if i.user.id not in [p.id for p in self.outer.alive_players]: return await i.response.send_message("❌ Bạn đã chết!", ephemeral=True)
                    await i.response.send_message("🪄 **BẢNG BIẾN ĐỔI VAI TRÒ CỦA CHÚA:**", view=GodModifyRoleView(uid, self.outer.alive_players, self.outer.player_roles), ephemeral=True)
            return await interaction.response.send_message("⚡ **BẢNG ĐIỀU HÀNH TỐI CAO CỦA CHÚA:**", view=GodControlView(self), ephemeral=True)

        elif role == "witch":
            victim_id = self.night_data.get("current_wolf_target")
            victim_p = interaction.guild.get_member(victim_id) if victim_id else None
            status_text = f"Đêm nay Ma Sói đang cắm móng vào: **{victim_p.display_name if victim_p else 'Chưa rõ/Chưa cắn'}**"
            class WitchNightPanel(View):
                def __init__(self, outer): super().__init__(timeout=30); self.outer = outer
                @discord.ui.button(label="🧪 Dùng Thuốc Cứu (1 Lần/Ván)", style=discord.ButtonStyle.success)
                async def heal_btn(self, i, b):
                    if i.user.id not in [p.id for p in self.outer.alive_players] or i.user.id in self.outer.night_data["acted_players"]: return await i.response.send_message("❌ Không thể dùng!", ephemeral=True)
                    if self.outer.witch_state["heal_used"]: return await i.response.send_message("❌ Hết bình cứu!", ephemeral=True)
                    self.outer.night_data["witch_heal_action"] = True; self.outer.witch_state["heal_used"] = True; self.outer.night_data["acted_players"].add(i.user.id)
                    await i.response.send_message("🧪 Bạn đã dùng bình CỨU!", ephemeral=True)
                @discord.ui.button(label="☠️ Dùng Thuốc Độc (1 Lần/Ván)", style=discord.ButtonStyle.danger)
                async def poison_btn(self, i, b):
                    if i.user.id not in [p.id for p in self.outer.alive_players] or i.user.id in self.outer.night_data["acted_players"]: return await i.response.send_message("❌ Không thể dùng!", ephemeral=True)
                    if self.outer.witch_state["poison_used"]: return await i.response.send_message("❌ Hết bình độc!", ephemeral=True)
                    other_p = [p for p in self.outer.alive_players if p.id != uid][:25]
                    poison_select = Select(placeholder="☠️ Chọn 1 người để đầu độc...", options=[discord.SelectOption(label=p.display_name, value=str(p.id), emoji="☠️") for p in other_p])
                    async def poison_cb(i_sub):
                        if len(poison_select.values) > 1: return await i_sub.response.send_message("❌ Chọn 1 người!", ephemeral=True)
                        target_id = int(poison_select.values[0])
                        self.outer.night_data["witch_poison_id"] = target_id; self.outer.witch_state["poison_used"] = True; self.outer.night_data["acted_players"].add(i_sub.user.id)
                        await i_sub.response.send_message(f"☠️ Bạn đã ném bình độc vào **{i_sub.guild.get_member(target_id).display_name}**!", ephemeral=True)
                    poison_select.callback = poison_cb
                    sub_view = View(timeout=30); sub_view.add_item(poison_select)
                    await i.response.send_message("☠️ **CHỌN MỤC TIÊU ĐỂ NÉM THUỐC ĐỘC:**", view=sub_view, ephemeral=True)
            return await interaction.response.send_message(f"🧪 **BẢNG PHÙ THỦY:**\n{status_text}", view=WitchNightPanel(self), ephemeral=True)

        elif role == "chemist":
            class ChemistNightPanel(View):
                def __init__(self, outer): super().__init__(timeout=30); self.outer = outer
                @discord.ui.button(label="🧪 Bình Hồi Sinh (Mỗi 2-3 Đêm)", style=discord.ButtonStyle.success)
                async def heal_chem(self, i, b):
                    if self.outer.chemist_state["revive_cd"] > 0: return await i.response.send_message(f"❌ Chờ {self.outer.chemist_state['revive_cd']} đêm!", ephemeral=True)
                    self.outer.night_data["chemist_heal_action"] = True; self.outer.chemist_state["revive_cd"] = random.randint(2, 3); self.outer.night_data["acted_players"].add(i.user.id)
                    await i.response.send_message("🧪 Đã CỨU nạn nhân!", ephemeral=True)
                @discord.ui.button(label="☣️ Siêu Độc Diệt 50% Phe (1 Lần/Ván)", style=discord.ButtonStyle.danger)
                async def nuke_chem(self, i, b):
                    if self.outer.chemist_state["nuke_used"]: return await i.response.send_message("❌ Hết bình nổ!", ephemeral=True)
                    class NukeSubView(View):
                        def __init__(self, c_outer): super().__init__(timeout=30); self.c_outer = c_outer
                        @discord.ui.button(label="🐺 Đầu Độc 50% Phe Sói", style=discord.ButtonStyle.danger)
                        async def nuke_w(self, i_sub, b_sub):
                            self.c_outer.outer.night_data["chemist_nuke_wolf"] = True; self.c_outer.outer.chemist_state["nuke_used"] = True; self.c_outer.outer.night_data["acted_players"].add(i_sub.user.id)
                            await i_sub.response.send_message("☣️ ĐÃ NÉM ĐỘC SÓI!", ephemeral=True)
                        @discord.ui.button(label="👨‍🌾 Đầu Độc 50% Phe Dân", style=discord.ButtonStyle.danger)
                        async def nuke_c(self, i_sub, b_sub):
                            self.c_outer.outer.night_data["chemist_nuke_civ"] = True; self.c_outer.outer.chemist_state["nuke_used"] = True; self.c_outer.outer.night_data["acted_players"].add(i_sub.user.id)
                            await i_sub.response.send_message("☣️ ĐÃ NÉM ĐỘC DÂN!", ephemeral=True)
                    await i.response.send_message("☣️ **CHỌN PHE ĐỂ NÉM SIÊU ĐỘC:**", view=NukeSubView(self), ephemeral=True)
            return await interaction.response.send_message("☣️ **BẢNG HÓA HỌC GIA:**", view=ChemistNightPanel(self), ephemeral=True)

        elif role == "vampire":
            if self.night_data.get("event") != "blood_moon": return await interaction.response.send_message("🧛 Chỉ Trăng Máu mới hút được máu!", ephemeral=True)
            valid_targets = [p for p in self.alive_players if self.player_roles[p.id] != "vampire" and p.id != uid][:25]
            if not valid_targets: return await interaction.response.send_message("🧛 Toàn bộ đã thành Ma Cà Rồng!", ephemeral=True)
            select = Select(placeholder="🧛 Chọn 1 người để cắn...", options=[discord.SelectOption(label=p.display_name, value=str(p.id), emoji="🧛") for p in valid_targets])
            async def vamp_cb(i):
                target_id = int(select.values[0])
                self.night_data["vampire_infect_id"] = target_id; self.night_data["acted_players"].add(i.user.id)
                await i.response.send_message(f"🧛 Đêm nay sẽ cắn **{i.guild.get_member(target_id).display_name}**!", ephemeral=True)
            select.callback = vamp_cb; view = View(timeout=30); view.add_item(select)
            return await interaction.response.send_message("🧛 **BẢNG LÂY NHIỄM (TRĂNG MÁU):**", view=view, ephemeral=True)

        elif role == "corrupted":
            if self.day_count - self.gian_dan_last_used.get(uid, -2) < 2: return await interaction.response.send_message("🗡️💋 Đang hồi chiêu!", ephemeral=True)
            valid_targets = [p for p in self.alive_players if ROLES_INFO[self.player_roles[p.id]]["side"] != "evil" and p.id != uid][:25]
            if not valid_targets: return await interaction.response.send_message("🗡️💋 Không còn ai để đâm!", ephemeral=True)
            select = Select(placeholder="🗡️ Chọn 1 Dân Làng...", options=[discord.SelectOption(label=p.display_name, value=str(p.id), emoji="🗡️") for p in valid_targets])
            async def gian_dan_cb(i):
                target_id = int(select.values[0])
                self.night_data["corrupted_stab_id"] = target_id; self.gian_dan_last_used[uid] = self.day_count; self.night_data["acted_players"].add(i.user.id)
                await i.response.send_message(f"🗡️💋 Đã đâm **{i.guild.get_member(target_id).display_name}**!", ephemeral=True)
            select.callback = gian_dan_cb; view = View(timeout=30); view.add_item(select)
            return await interaction.response.send_message("🗡️💋 **BẢNG GIAN DÂN:**", view=view, ephemeral=True)

        elif role == "cupid":
            if self.day_count > 1 or self.night_data.get("lovers"): return await interaction.response.send_message("💘 Đã chọn rồi!", ephemeral=True)
            all_other = [p for p in self.alive_players if p.id != uid]
            return await interaction.response.send_message("💘 **BẢNG KẾT DUYÊN CUPID:**", view=CupidPairView(uid, all_other or list(self.alive_players), self.night_data, self.alive_players), ephemeral=True)

        elif role == "avenger":
            options = [discord.SelectOption(label=p.display_name, value=str(p.id), emoji="🗡️") for p in self.alive_players if p.id != uid][:25]
            select = Select(placeholder="🗡️ Chọn 1 người để tiêu diệt...", options=options)
            async def avenger_cb(i):
                target_id = int(select.values[0])
                self.night_data["avenger_kill_id"] = target_id; self.night_data["acted_players"].add(i.user.id)
                await i.response.send_message(f"🗡️ Trả thù **{i.guild.get_member(target_id).display_name}**!", ephemeral=True)
            select.callback = avenger_cb; view = View(timeout=30); view.add_item(select)
            return await interaction.response.send_message("🗡️ **BẢNG KẺ HẬN THÙ:**", view=view, ephemeral=True)

        elif role == "mad_scientist":
            options = [discord.SelectOption(label=p.display_name, value=str(p.id), emoji="🧪") for p in self.alive_players if p.id != uid][:25]
            select = Select(placeholder="🧪 Chọn 1 người tiêm đột biến...", options=options)
            async def mad_cb(i):
                target_id = int(select.values[0])
                target_p = i.guild.get_member(target_id)
                self.player_roles[target_id] = "alpha_wolf" if self.player_roles[target_id] in ("wolf", "alpha_wolf") else "wolf"
                self.night_data["acted_players"].add(i.user.id)
                await i.response.send_message(f"🧪 Đã biến đổi **{target_p.display_name}** thành SÓI!", ephemeral=True)
            select.callback = mad_cb; view = View(timeout=30); view.add_item(select)
            return await interaction.response.send_message("🧪 **BẢNG THÍ NGHIỆM ĐIÊN:**", view=view, ephemeral=True)

        elif role in ("wolf", "alpha_wolf", "drug_lord"):
            if self.night_data.get("event") == "new_moon": return await interaction.response.send_message("🌑 TRĂNG NON: Sói bị phế!", ephemeral=True)
            excluded = {p.id for p in self.alive_players if self.player_roles[p.id] in ("wolf", "alpha_wolf", "corrupted", "drug_lord")}
            if self.night_data.get("lovers") and uid in self.night_data["lovers"]:
                excluded.add(self.night_data["lovers"][1] if uid == self.night_data["lovers"][0] else self.night_data["lovers"][0])
            valid = [p for p in self.alive_players if p.id not in excluded]
            if not valid: return await interaction.response.send_message("❌ Không còn ai để cắn!", ephemeral=True)
            return await interaction.response.send_message(embed=self.generate_wolf_status_embed(), view=WerewolfNightActionsSubView(self, uid, valid), ephemeral=True)

        elif role == "doctor":
            options = [discord.SelectOption(label=p.display_name, value=str(p.id), emoji="🛡️") for p in self.alive_players[:25]]
            select = Select(placeholder="🛡️ Chọn duy nhất 1 người để bảo vệ...", options=options)
            async def doctor_callback(i):
                target_id = int(select.values[0])
                self.night_data["protected_id"] = target_id; self.night_data["acted_players"].add(i.user.id)
                await i.response.send_message(f"🛡️ Đã bảo vệ **{i.guild.get_member(target_id).display_name}**!", ephemeral=True)
            select.callback = doctor_callback; view = View(timeout=30); view.add_item(select)
            return await interaction.response.send_message("🛡️ **BẢNG BẢO VỆ:**", view=view, ephemeral=True)

        elif role == "psychiatrist":
            if self.night_data.get("event") != "blue_moon": return await interaction.response.send_message("🧠 Chỉ Trăng Xanh mới chữa trị được!", ephemeral=True)
            options = [discord.SelectOption(label=p.display_name, value=str(p.id), emoji="🧠") for p in self.alive_players[:25]]
            select = Select(placeholder="🧠 Chọn tối đa 2 người...", min_values=1, max_values=min(2, len(options)), options=options)
            async def psych_callback(i):
                c_ids = [int(v) for v in select.values]
                self.night_data["cured_ids"] = c_ids; self.night_data["acted_players"].add(i.user.id)
                await i.response.send_message(f"🧠 Đã chữa trị thành công!", ephemeral=True)
            select.callback = psych_callback; view = View(timeout=30); view.add_item(select)
            return await interaction.response.send_message("🧠 **BẢNG TÂM LÝ:**", view=view, ephemeral=True)

        elif role == "addict":
            return await interaction.response.send_message("🌿 **BẢNG NGHIỆN NHÂN:**", view=AddictNightActionSubView(self, uid), ephemeral=True)

        else:
            return await interaction.response.send_message(f"👨‍🌾 Bạn là **{ROLES_INFO[role]['name']}**. Ngủ ngoan nhé!", ephemeral=True)


class DayActionView(View):
    def __init__(self, player_roles: dict, alive_players: list, day_data: dict, day_count: int, game_data: dict, bot):
        super().__init__(timeout=None)
        self.player_roles = player_roles
        self.alive_players = alive_players
        self.day_data = day_data
        self.day_count = day_count
        self.game_data = game_data
        self.bot = bot

    @discord.ui.button(label="Tiên Tri", style=discord.ButtonStyle.primary, emoji="🔮", row=0)
    async def seer_day_action(self, interaction: discord.Interaction, button: Button):
        uid = interaction.user.id
        if uid not in [p.id for p in self.alive_players]:
            return await interaction.response.send_message("❌ Bạn đã chết!", ephemeral=True)

        role = self.player_roles.get(uid)
        if role != "seer":
            return await interaction.response.send_message("❌ Chỉ có **Tiên Tri** mới có thể thực hiện tiên đoán!", ephemeral=True)

        if "acted_seers" not in self.day_data:
            self.day_data["acted_seers"] = set()

        if uid in self.day_data["acted_seers"]:
            return await interaction.response.send_message("❌ Hôm nay bạn đã dùng kỹ năng tiên đoán rồi!", ephemeral=True)

        if self.day_data.get("event") == "new_moon":
            return await interaction.response.send_message("🌑 TRĂNG NON: Tiên tri bị phế không thể soi!", ephemeral=True)

        others = [p for p in self.alive_players if p.id != uid]
        if not others:
            return await interaction.response.send_message("❌ Không còn ai để soi!", ephemeral=True)

        max_i = 2 if self.day_data.get("event") == "full_moon" else 1
        return await interaction.response.send_message(
            f"🔮 **BẢNG SOI TIÊN TRI (Tối đa {max_i} người):**",
            view=SeerDayActionSubView(self, uid, others, max_i),
            ephemeral=True
        )

    @discord.ui.button(label="Tình hình làng", style=discord.ButtonStyle.secondary, emoji="📜", row=0)
    async def village_status(self, interaction: discord.Interaction, button: Button):
        all_p = self.game_data.get("all_players", self.alive_players)
        alive_m = [p.mention for p in self.alive_players]
        dead_m = [f"<@{p.id}>" for p in all_p if p.id not in [ap.id for ap in self.alive_players]]
        status_embed = discord.Embed(title=f"📜 BẢN TIN TÌNH HÌNH TRONG LÀNG (NGÀY {self.day_count})", color=discord.Color.gold())
        status_embed.add_field(name="👥 Cư Dân Còn Sống", value=", ".join(alive_m) if alive_m else "Không có ai", inline=False)
        status_embed.add_field(name="💀 Linh Hồn Đã Lìa Xác", value=", ".join(dead_m) if dead_m else "Không có ai", inline=False)
        status_embed.set_image(url="attachment://dawn.png")
        await interaction.response.send_message(embed=status_embed, ephemeral=True)


class SkipDiscussionView(View):
    def __init__(self, alive_players: list, host_id: int):
        super().__init__(timeout=600)
        self.alive_players = alive_players
        self.host_id = host_id
        self.skips = set()
        self.skipped = False

    @discord.ui.button(label="⏩ Bỏ qua bàn luận", style=discord.ButtonStyle.secondary, emoji="⏩")
    async def skip_btn(self, interaction: discord.Interaction, button: Button):
        uid = interaction.user.id
        if uid not in [p.id for p in self.alive_players]:
            return await interaction.response.send_message("❌ Bạn đã chết!", ephemeral=True)

        self.skips.add(uid)
        needed = (len(self.alive_players) // 2) + 1

        if uid == self.host_id or len(self.skips) >= needed:
            self.skipped = True
            button.disabled = True
            await interaction.response.edit_message(content=f"⏩ **Đã biểu quyết bỏ qua bàn luận!** ({len(self.skips)}/{needed} phiếu)", view=self)
            self.stop()
        else:
            await interaction.response.send_message(f"✅ Bạn đã chọn bỏ qua thảo luận! ({len(self.skips)}/{needed} phiếu)", ephemeral=True)


class WerewolfLobbyView(View):
    def __init__(self, host: discord.Member):
        super().__init__(timeout=600)
        self.host = host
        self.players = {host.id: host}
        self.max_players = 100
        self.discussion_minutes = 3
        self.night_minutes = 1
        self.show_votes = True
        self.wolf_setting = "25%"
        self.modified_mode = False
        self.game_started = False
        self.forced_roles = {}

    def generate_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🐺 TRÒ CHƠI: MA SÓI (WEREWOLF DISCORD)",
            description=f"═══════════════════════════════════\n📜 **CẤU HÌNH THỜI GIAN:**\n• **Ban đêm:** **{self.night_minutes} phút** thực hiện kỹ năng.\n• **Ban ngày:** **{self.discussion_minutes} phút** thảo luận tìm Ma Sói.\n═══════════════════════════════════\n👉 Bấm nút **[🎉 Tham Gia]** bên dưới!",
            color=discord.Color.dark_red()
        )
        p_list = "\n".join([f"• {p.mention} (**{p.display_name}**)" for p in self.players.values()])
        embed.add_field(name=f"👥 NGƯỜI THAM GIA ({len(self.players)}/{self.max_players})", value=p_list, inline=False)
        embed.add_field(name="🔀 Chế Độ Modified", value="BẬT ⚡" if self.modified_mode else "TẮT ❄️", inline=True)
        embed.add_field(name="🗳️ Hiển Thị Vote", value="Hiện Chi Tiết" if self.show_votes else "Ẩn", inline=True)
        embed.add_field(name="🐺 Cấu Hình Sói", value=f"**{self.wolf_setting}**", inline=True)
        return embed

    @discord.ui.button(label="Tham Gia / Rời Khỏi", style=discord.ButtonStyle.success, emoji="🎉", row=0)
    async def join_toggle(self, interaction: discord.Interaction, button: Button):
        user = interaction.user
        if user.id in self.players:
            if user.id == self.host.id: return await interaction.response.send_message("❌ Chủ phòng không thể rời!", ephemeral=True)
            del self.players[user.id]
        else:
            self.players[user.id] = user
        try: await interaction.message.edit(embed=self.generate_embed(), view=self)
        except Exception: pass

    @discord.ui.button(label="Modified: BẬT/TẮT", style=discord.ButtonStyle.primary, emoji="🔀", row=0)
    async def toggle_mod(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.host.id: return await interaction.response.send_message("❌ Chỉ chủ phòng!", ephemeral=True)
        self.modified_mode = not self.modified_mode
        try: await interaction.message.edit(embed=self.generate_embed(), view=self)
        except Exception: pass

    @discord.ui.button(label="Cài Đặt Phòng", style=discord.ButtonStyle.secondary, emoji="⚙️", row=0)
    async def config_room(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.host.id: return await interaction.response.send_message("❌ Chỉ chủ phòng!", ephemeral=True)
        await interaction.response.send_modal(WerewolfSettingsModal(self))

    @discord.ui.button(label="📖 Hướng Dẫn Roles", style=discord.ButtonStyle.secondary, emoji="📖", row=1)
    async def show_guide(self, interaction: discord.Interaction, button: Button):
        guide_embed = discord.Embed(title="📖 HƯỚNG DẪN CÁC VAI TRÒ", color=discord.Color.purple())
        for r_key, r_info in ROLES_INFO.items(): guide_embed.add_field(name=f"{r_info['emoji']} {r_info['name']}", value=f"• {r_info['desc']}", inline=False)
        await interaction.response.send_message(embed=guide_embed, ephemeral=True)

    @discord.ui.button(label="🛠️ Force Role (Dev)", style=discord.ButtonStyle.secondary, emoji="🛠️", row=1)
    async def force_role_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(ForceRoleModal(self))

    @discord.ui.button(label="BẮT ĐẦU GAME", style=discord.ButtonStyle.danger, emoji="🚀", row=1)
    async def start_game(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.host.id: return await interaction.response.send_message("❌ Chỉ chủ phòng!", ephemeral=True)
        if len(self.players) < 4: return await interaction.response.send_message("❌ Cần ít nhất 4 người!", ephemeral=True)
        self.game_started = True; self.stop()


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
        current_batch = self.alive_players[self.page * self.per_page : (self.page + 1) * self.per_page]
        options = [discord.SelectOption(label=p.display_name, value=str(p.id), emoji="🗳️") for p in current_batch]
        select = Select(placeholder=f"🗳️ Chọn người nghi ngờ (Trang {self.page + 1})...", options=options, row=0)
        select.callback = self.select_callback
        self.add_item(select)
        btn_skip = Button(label="⚪ Bỏ Phiếu Trắng", style=discord.ButtonStyle.danger, row=1)
        btn_skip.callback = self.skip_callback
        self.add_item(btn_skip)

    async def select_callback(self, interaction: discord.Interaction):
        voter_id = interaction.user.id
        if voter_id not in [p.id for p in self.alive_players]: return await interaction.response.send_message("❌ Bạn đã chết!", ephemeral=True)
        if voter_id in self.votes: return await interaction.response.send_message("❌ Đã bỏ phiếu rồi!", ephemeral=True)
        self.votes[voter_id] = interaction.data["values"][0]
        await interaction.response.send_message(f"🗳️ Đã bỏ phiếu!", ephemeral=True)

    async def skip_callback(self, interaction: discord.Interaction):
        voter_id = interaction.user.id
        if voter_id not in [p.id for p in self.alive_players]: return await interaction.response.send_message("❌ Bạn đã chết!", ephemeral=True)
        if voter_id in self.votes: return await interaction.response.send_message("❌ Đã bỏ phiếu rồi!", ephemeral=True)
        self.votes[voter_id] = "skip"
        await interaction.response.send_message("⚪ Đã chọn Bỏ phiếu trắng!", ephemeral=True)


class VictorySummaryView(View):
    def __init__(self, ctx, winning_side: str, winning_title: str, winners_lines: list, roster_lines: list):
        super().__init__(timeout=300)
        self.winning_side = winning_side
        self.winning_title = winning_title
        self.winners_lines = winners_lines
        self.roster_lines = roster_lines
        self.page = 0
        self.per_page = 10
        self.total_pages = max(1, math.ceil(len(roster_lines) / self.per_page))

    def generate_embed(self) -> discord.Embed:
        embed = discord.Embed(title=f"🏆 {self.winning_title}", color=discord.Color.gold())
        embed.add_field(name="🎉 NGƯỜI CHIẾN THẮNG", value="\n".join(self.winners_lines) or "Không có ai", inline=False)
        start, end = self.page * self.per_page, (self.page + 1) * self.per_page
        embed.add_field(name="📜 DANH SÁCH NGƯỜI CHƠI", value="\n".join(self.roster_lines[start:end]), inline=False)
        return embed