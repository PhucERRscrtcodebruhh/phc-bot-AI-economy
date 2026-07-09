# other.py
import datetime
import random
import math
import html
import discord
from discord.ext import commands
from discord.ui import View, Select, Modal, TextInput

from constants import HELP_CATEGORIES, KESLING_ICON, price, emoji_icon, ore
from AIphcbot import get_user_data, save_data, player_inventory, get_system_data
from helpers import send_paginated_via_ctx

# ====================================================
#def 
def parse_amount(amount_str: str) -> int:
    if not amount_str:
        return 0
    amount_str = amount_str.lower().strip()
    multipliers = {'k': 1000, 'm': 1000000, 'b': 1000000000}
    
    if amount_str[-1] in multipliers:
        try:
            factor = multipliers[amount_str[-1]]
            return int(float(amount_str[:-1]) * factor)
        except ValueError:
            return 0
    try:
        return int(amount_str)
    except ValueError:
        return 0

        


# ==================== HELP MENU DROPDOWN ====================

class AnXinView(View):
    def __init__(self, beggar: discord.Member, giver: discord.Member, amount: int):
        super().__init__(timeout=60)
        self.beggar = beggar
        self.giver = giver
        self.amount = amount

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.giver:
            await interaction.response.send_message("❌ Cậu không phải là người được xin tiền!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Cho tiền", style=discord.ButtonStyle.success, emoji="💰")
    async def give_money(self, interaction: discord.Interaction, button: discord.ui.Button):
        giver_data = get_user_data(str(self.giver.id))
        beggar_data = get_user_data(str(self.beggar.id))
        
        if giver_data.get('money', 0) < self.amount:
            return await interaction.response.send_message("❌ Cậu không đủ tiền trong ví để cho rồi!", ephemeral=True)
            
        giver_data['money'] -= self.amount
        beggar_data['money'] = beggar_data.get('money', 0) + self.amount
        save_data(player_inventory)
        
        for item in self.children:
            item.disabled = True
            
        embed = discord.Embed(
            title="✅ Bố thí thành công",
            description=f"Đại gia {self.giver.mention} đã rủ lòng thương xót cho ăn xin {self.beggar.mention} số tiền **{self.amount:,} {KESLING_ICON}**!",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Từ chối", style=discord.ButtonStyle.danger, emoji="🙅‍♂️")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        embed = discord.Embed(
            title="❌ Xin tiền thất bại",
            description=f"Hic, đại gia {self.giver.mention} đã từ chối thẳng thừng lời van nài của {self.beggar.mention}...",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=self)




class HelpDropdown(Select):
    def __init__(self, bot: commands.Bot, author: discord.User):
        self.bot = bot
        self.author = author
        options = [
            discord.SelectOption(
                label=category_name,
                description=f"Xem các lệnh thuộc nhóm {category_name[2:]}"
            )
            for category_name in HELP_CATEGORIES.keys()
        ]
        super().__init__(placeholder="Chọn danh mục lệnh muốn xem...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            return await interaction.response.send_message("❌ Đây không phải menu của bạn!", ephemeral=True)
        selected_category = self.values[0]
        command_names = HELP_CATEGORIES[selected_category]
        
        embed = discord.Embed(
            title=f"{selected_category}",
            description="Dưới đây là danh sách các lệnh đang hoạt động. Prefix của bot là `p` hoặc `P`",
            color=discord.Color.blue()
        )
        for name in command_names:
            cmd = self.bot.get_command(name)
            if cmd:
                aliases = f" (hoặc {', '.join(cmd.aliases)})" if cmd.aliases else ""
                description = cmd.help or "Không có mô tả chi tiết."
                embed.add_field(name=f"`p{cmd.name}`{aliases}", value=description, inline=False)
        await interaction.response.edit_message(embed=embed)

class DynamicHelpView(View):
    def __init__(self, bot: commands.Bot, author: discord.User):
        super().__init__(timeout=60)
        self.author = author
        self.message = None
        self.add_item(HelpDropdown(bot, author))

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

# ==================== ENDLESS COMMUNITY QUIZ ====================

class AddCommunityQuestionModal(Modal, title="Đóng góp câu hỏi vô tri"):
    question = TextInput(
        label="Nội dung câu hỏi",
        style=discord.TextStyle.paragraph,
        placeholder="Ví dụ: Ai đẹp trai nhất server này?",
        required=True
    )
    choices_str = TextInput(
        label="4 Đáp án (Ngăn cách bằng dấu phẩy)",
        placeholder="Ví dụ: Sang béo, Hoanganh498, leminhphuc, Haubeo",
        required=True
    )
    correct_letter = TextInput(
        label="Đáp án đúng (Gõ duy nhất: A hoặc B hoặc C hoặc D)",
        placeholder="Ví dụ: C",
        max_length=1,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        q_text = self.question.value.strip()
        choices_raw = [c.strip() for c in self.choices_str.value.split(",") if c.strip()]
        letter = self.correct_letter.value.strip().upper()

        if len(choices_raw) != 4:
            return await interaction.response.send_message("❌ Lỗi: Cậu phải nhập chính xác đúng 4 đáp án ngăn cách bởi dấu phẩy!", ephemeral=True)

        letter_map = {"A": 0, "B": 1, "C": 2, "D": 3}
        if letter not in letter_map:
            return await interaction.response.send_message("❌ Lỗi: Đáp án đúng chỉ được phép ghi là một chữ cái A, B, C hoặc D!", ephemeral=True)

        system_data = get_system_data()
        if "community_questions" not in system_data:
            system_data["community_questions"] = []

        system_data["community_questions"].append({
            "question": q_text,
            "choices": choices_raw,
            "correct_index": letter_map[letter],
            "author": str(interaction.user.display_name)
        })
        save_data(player_inventory)

        await interaction.response.send_message(f"🎉 Cảm ơn {interaction.user.mention} đã đóng góp 1 câu hỏi vô tri vào kho lưu trữ cộng đồng!", ephemeral=False)

# ==================== COG MODULE ====================

class OtherCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="ping")
    async def ping(self, ctx):
        ws_latency = round(self.bot.latency * 1000)
        embed = discord.Embed(
            title="🛰️ KATBOT SYSTEM LATENCY",
            color=0x5865F2,
            description=f"📡 **Ping máy chủ:** `{ws_latency}ms`"
        )
        embed.set_footer(text=f"Kiểm tra bởi {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
        await ctx.reply(embed=embed)

    @commands.command(name="me", aliases=["acc", "user"])
    async def account_info(self, ctx, member: discord.Member = None):
        target = member or ctx.author
        user_id = str(target.id)
        user_data = get_user_data(user_id)
        money = user_data.get('money', 0)
        tickets = user_data.get('tickets', 0)
        
        embed = discord.Embed(title=f"💸 Ví Tiền của {target.display_name}", color=discord.Color.gold())
        embed.add_field(name="💰 Tiền mặt (Money)", value=f"**{money:,} {KESLING_ICON}**", inline=True)
        embed.add_field(name="🎟️ Vé (Tickets)", value=f"**{tickets:,} vé**", inline=True)
        if target.avatar:
            embed.set_thumbnail(url=target.avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name="anxin")
    async def anxin(self, ctx, giver: discord.Member = None, amount_str: str = None):
        if giver is None or amount_str is None:
            return await ctx.send("💡 Dùng lệnh: `p anxin <@người_cho> <số_tiền>` (Ví dụ: `p anxin @KatBot 50k`)")
            
        if giver.id == ctx.author.id:
            return await ctx.send("❌ Cậu không thể tự ăn xin chính mình được đâu!")
            
        amount = parse_amount(amount_str)
        if amount <= 0:
            return await ctx.send("❌ Số tiền ăn xin không hợp lệ nè.")
            
        embed = discord.Embed(
            title="🥺 Thao tác ăn xin",
            description=f"{ctx.author.mention} đang chìa tay xin đại gia {giver.mention} số tiền **{amount:,} {KESLING_ICON}**.\n\nĐại gia có đồng ý bố thí không ạ?",
            color=discord.Color.blue()
        )
        view = AnXinView(beggar=ctx.author, giver=giver, amount=amount)
        await ctx.send(content=giver.mention, embed=embed, view=view)

    @commands.command(name="give")
    async def give(self, ctx, receiver: discord.Member = None, amount_str: str = None):
        if receiver is None or amount_str is None:
            return await ctx.send("💡 Dùng lệnh: `p give <@người_nhận> <số_tiền>` (Ví dụ: `p give @KatBot 100k` hoặc `p give @KatBot 1.5m`)")
            
        if receiver.id == ctx.author.id:
            return await ctx.send("❌ Cậu không thể tự chuyển tiền cho bản thân!")
            
        amount = parse_amount(amount_str)
        if amount <= 0:
            return await ctx.send("❌ Số tiền chuyển không hợp lệ.")
            
        sender_id = str(ctx.author.id)
        receiver_id = str(receiver.id)
        
        sender_data = get_user_data(sender_id)
        receiver_data = get_user_data(receiver_id)
        
        if sender_data.get('money', 0) < amount:
            return await ctx.send(f"❌ Ví của cậu không đủ tiền! Cần **{amount:,} {KESLING_ICON}**.")
            
        sender_data['money'] -= amount
        receiver_data['money'] = receiver_data.get('money', 0) + amount
        save_data(player_inventory)
        
        await ctx.send(f"✅ Chuyển tiền thành công! {ctx.author.mention} đã gửi **{amount:,} {KESLING_ICON}** sang tài khoản của {receiver.mention}!")

    @commands.command(name="daily")
    async def daily(self, ctx):
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        times = datetime.datetime.utcnow()
        last_claim = user_data.get("last_claim")
        
        if last_claim:
            try:
                last_time = datetime.datetime.fromisoformat(last_claim)
                if (times - last_time).days < 1:
                    return await ctx.send("❌ Hôm nay oniichan đã nhận quà báo danh rồi, mai hãy quay lại nhé!")
            except Exception:
                pass
                
        amount = random.randint(20, 200)
        user_data["money"] = user_data.get('money', 0) + amount
        user_data["last_claim"] = times.isoformat()
        
        msg = f"💰 Bạn nhận được điểm danh hàng ngày: **{amount} {KESLING_ICON}**. Ngày mai nhớ tiếp tục báo danh đấy!"
        
        # Random rơi quà may mắn
        if random.random() < 0.1:
            ore_name = random.choice(list(ore.keys()))
            user_data["inventory"][ore_name] = user_data["inventory"].get(ore_name, 0) + 1
            msg += f"\n🎉 **Quá may mắn!** Bạn nhận thêm 1x {emoji_icon.get(ore_name, '')} {ore_name}."
        if random.random() < 0.02:
            user_data["inventory"]["ticket"] = user_data["inventory"].get("ticket", 0) + 1
            msg += f"\n🎫 **Nhân phẩm bùng nổ!** Bạn nhận thêm 1x Ticket."
            
        save_data(player_inventory)
        await ctx.send(msg)

    @commands.command(name="tktocoin")
    async def tktocoin(self, ctx):
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        inv = user_data["inventory"]
        if inv.get("ticket", 0) < 1:
            return await ctx.send("❌ Bạn không có bất kỳ tấm vé (`ticket`) nào để quy đổi.")
            
        inv["ticket"] -= 1
        amount = random.randint(200, 5000)
        user_data["money"] += amount
        save_data(player_inventory)
        await ctx.send(f"💸 Bạn đã quy đổi 1x Ticket lấy thành công **{amount:,} {KESLING_ICON}**!")

    @commands.command(name="checkgia")
    async def check_price(self, ctx, ore_name: str = None):
        if ore_name is None:
            return await ctx.send("💡 Dùng lệnh: `pcheckgia <tên_vật_phẩm>`")
        key = ore_name.lower()
        if key not in price:
            return await ctx.send("❌ Không tìm thấy giá của vật phẩm này.")
        await ctx.send(f"✅ Giá của {emoji_icon.get(key, '')} **{key}** hiện tại là: **{price[key]:,} {KESLING_ICON}** / 1 đơn vị.")

    @commands.command(name="quang")
    async def search_ore_image(self, ctx, *, ten_quang):
        url = f"https://www.bing.com/search?q={ten_quang}"
        await ctx.send(f"🔍 Đây là liên kết tìm kiếm hình ảnh thực tế về **{ten_quang}**: {url}")

    @commands.group(name="com", invoke_without_command=True)
    async def community_quiz_group(self, ctx):
        system_data = get_system_data()
        questions = system_data.get("community_questions", [])
        if not questions:
            return await ctx.send("😭 Kho câu hỏi cộng đồng hiện đang trống! Hãy dùng lệnh `p com add` để đóng góp câu hỏi đầu tiên đi nào!")
            
        await ctx.send("🏁 **Bắt đầu chế độ Endless Trivia Cộng Đồng!** Chơi giải trí thử thách trí khôn không mất tiền nha!")
        await asyncio.sleep(1.0)
        
        game_pool = list(questions)
        random.shuffle(game_pool)
        score = 0
        
        from sinkhole import QuizView as GlobalQuizView
        while True:
            if not game_pool:
                game_pool = list(questions)
                random.shuffle(game_pool)
                
            q = game_pool.pop(0)
            question_text = html.unescape(q["question"])
            choices_text = [html.unescape(c) for c in q["choices"]]
            correct_index = q["correct_index"]
            
            indexed_choices = list(enumerate(choices_text))
            random.shuffle(indexed_choices)
            shuffled_choices = [choice for _, choice in indexed_choices]
            new_correct_index = next(new_idx for new_idx, (old_idx, _) in enumerate(indexed_choices) if old_idx == correct_index)
            
            author_name = q.get("author", "Vô danh")
            embed = discord.Embed(
                title=f"🔥 Endless Quiz - Câu {score + 1}",
                description=f"**{question_text}**\n",
                color=discord.Color.purple()
            )
            choices_str = "".join([f"**{chr(65+i)}.** {c}\n" for i, c in enumerate(shuffled_choices)])
            embed.add_field(name="Các đáp án chọn lựa:", value=choices_str, inline=False)
            embed.set_footer(text=f"Người đóng góp câu hỏi: {author_name} | Điểm số hiện tại: {score}")
            
            view = GlobalQuizView(ctx.author)
            view.message = await ctx.send(embed=embed, view=view)
            idx = await view.wait_for_choice()
            
            if idx is None:
                await ctx.send(f"⏰ Quá thời gian suy nghĩ! Bạn dừng chân với tổng số câu đúng: **{score}**.")
                break
                
            if idx == new_correct_index:
                score += 1
                await ctx.send(f"✅ **Chuẩn luôn!** Tiến lên câu tiếp theo...")
                await asyncio.sleep(1.2)
            else:
                await ctx.send(f"❌ **Sai rồi!** Đáp án đúng là: **{shuffled_choices[new_correct_index]}**.\n🏁 Trò chơi kết thúc! Tổng điểm vô tận của bạn là: **{score}** câu đúng.")
                break

    @community_quiz_group.command(name="add")
    async def add_community_question(self, ctx):
        class TriggerView(View):
            def __init__(self):
                super().__init__(timeout=60)
            @discord.ui.button(label="Nhấn để mở Form nhập", style=discord.ButtonStyle.primary, emoji="📝")
            async def open_form(self, interaction: discord.Interaction, button: discord.Button):
                await interaction.response.send_modal(AddCommunityQuestionModal())
                self.stop()
        await ctx.send("📝 Oniichan hãy bấm nút dưới đây để mở biểu mẫu gửi câu hỏi lên hệ thống nhé!", view=TriggerView())

    # ============ BẢNG XẾP HẠNG (LEADERBOARD) ============

    def get_rarest_ore_score(self, inventory, ore_weights):
        rarest_score = 0
        rarest_ore_name = None
        player_ores = {n: count for n, count in inventory.items() if n in ore_weights and n not in ('dirt', 'stone') and isinstance(count, int)}
        for ore_name, count in player_ores.items():
            if count > 0:
                weight = ore_weights[ore_name]
                current_score = (1000 / weight) * count
                if current_score > rarest_score:
                    rarest_score = current_score
                    rarest_ore_name = ore_name
        if rarest_ore_name:
            return (rarest_score, rarest_ore_name, inventory[rarest_ore_name])
        return (0, None, 0)

    async def create_leaderboard_embed(self, ranking_data, lb_type, page_num, total_pages):
        PER_PAGE = 10
        start_index = (page_num - 1) * PER_PAGE
        page_data = ranking_data[start_index:start_index + PER_PAGE]
        
        if lb_type in ("money", "tiền"):
            embed = discord.Embed(title="🏆 BẢNG XẾP HẠNG ĐẠI PHÚ GIA 🏆", description=f"Bảng xếp hạng tài sản (Trang {page_num}/{total_pages})", color=discord.Color.gold())
        else:
            embed = discord.Embed(title="💎 BẢNG XẾP HẠNG ĐÀO MỎ HOÀNG GIA 💎", description=f"Bảng quặng hiếm (Trang {page_num}/{total_pages})", color=discord.Color.teal())
            
        for j, item in enumerate(page_data, start=1):
            i = start_index + j
            user_id = item[0]
            try:
                user = await self.bot.fetch_user(int(user_id))
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🏅" if i <= 10 else ""
                field_name = f"{medal} {i}. {user.name}"
                if lb_type in ("money", "tiền"):
                    field_value = f"💰 **{item[1]:,}** {KESLING_ICON}"
                else:
                    ore_display = emoji_icon.get(item[2], "") + " " + item[2].upper()
                    field_value = f"✨ **{item[3]}x {ore_display}** (Điểm: {item[1]:.0f})"
                embed.add_field(name=field_name, value=field_value, inline=False)
            except Exception:
                continue
        return embed

    @commands.command(name="lb", aliases=["leaderboard"])
    async def lb(self, ctx, lb_type: str = "money"):
        if not player_inventory:
            return await ctx.send("📉 Chưa có dữ liệu của người chơi nào.")
            
        valid_players = {u: d for u, d in player_inventory.items() if isinstance(d, dict)}
        if not valid_players:
            return await ctx.send("📉 Chưa tìm thấy người chơi hợp lệ.")
            
        lb_type = lb_type.lower()
        ranking_data = []
        
        if lb_type in ("money", "tiền"):
            money_players = {u: d.get('money', 0) for u, d in valid_players.items()}
            money_ranking = {k: v for k, v in money_players.items() if v > 0}
            if not money_ranking:
                return await ctx.send("📉 Hiện chưa ai có tiền mặt.")
            ranking_data = sorted(money_ranking.items(), key=lambda x: x[1], reverse=True)
            
        elif lb_type in ("ore", "quặng"):
            for u, d in valid_players.items():
                score, rarest_ore, count = self.get_rarest_ore_score(d.get('inventory', {}), ore)
                if score > 0:
                    ranking_data.append((u, score, rarest_ore, count))
            if not ranking_data:
                return await ctx.send("📉 Chưa ai sở hữu quặng hiếm để xếp hạng.")
            ranking_data = sorted(ranking_data, key=lambda x: x[1], reverse=True)
        else:
            return await ctx.send("❌ Vui lòng dùng: `p lb money` (tiền tài sản) hoặc `p lb ore` (quặng hiếm).")
            
        total_pages = math.ceil(len(ranking_data) / 10)
        initial_embed = await self.create_leaderboard_embed(ranking_data, lb_type, 1, total_pages)
        
        class LeaderboardView(View):
            def __init__(self, parent_cog, ranking_list, mode_type, max_p):
                super().__init__(timeout=180)
                self.parent_cog = parent_cog
                self.ranking_list = ranking_list
                self.mode_type = mode_type
                self.total_pages = max_p
                self.current_page = 1
                self.message = None
                self.update_buttons()

            def update_buttons(self):
                if self.total_pages <= 1:
                    for child in self.children:
                        child.disabled = True
                    return
                self.children[0].disabled = (self.current_page == 1)
                self.children[1].disabled = (self.current_page == self.total_pages)

            async def update_embed(self, interaction: discord.Interaction):
                if interaction.user != ctx.author:
                    return await interaction.response.send_message("❌ Bạn không gọi lệnh này.", ephemeral=True)
                new_embed = await self.parent_cog.create_leaderboard_embed(self.ranking_list, self.mode_type, self.current_page, self.total_pages)
                self.update_buttons()
                await interaction.response.edit_message(embed=new_embed, view=self)

            @discord.ui.button(label="⬅️ Trang Trước", style=discord.ButtonStyle.blurple)
            async def prev_page(self, interaction: discord.Interaction, button: discord.Button):
                if self.current_page > 1:
                    self.current_page -= 1
                    await self.update_embed(interaction)

            @discord.ui.button(label="Trang Sau ➡️", style=discord.ButtonStyle.blurple)
            async def next_page(self, interaction: discord.Interaction, button: discord.Button):
                if self.current_page < self.total_pages:
                    self.current_page += 1
                    await self.update_embed(interaction)

        view = LeaderboardView(self, ranking_data, lb_type, total_pages)
        view.message = await ctx.send(embed=initial_embed, view=view)

    # ============ HELP COMMAND ============

    @commands.command(name="help", aliases=["hlp"])
    async def new_help_command(self, ctx):
        embed = discord.Embed(
            title="📚 BẢNG HƯỚNG DẪN LỆNH (KATBOT HELP MENU)",
            description=(
                "Chào mừng oniichan đã quay trở lại!\n"
                "Hãy chọn một danh mục từ danh sách **Dropdown Menu** phía dưới để xem chi tiết nhé.\n\n"
                "📌 **Các danh mục tính năng hiện tại:**\n"
                "• ⛏️ *Khai Thác & Chế Tạo*: Đào quặng, luyện kim, bán quặng, túi đồ, shop...\n"
                "• 🎲 *Trò Chơi Giải Trí*: Tài xỉu chống hack, lật xu, câu cá, triệu phú...\n"
                "• 👤 *Tài Khoản & Tiền Tệ*: Điểm danh hàng ngày, bảng xếp hạng, chuyển tiền...\n"
                "• 🏭 *Kinh Tế Vi Mô*: Làm ruộng, kiếm tiền mưu sinh...\n"
                "• 🧬 *Giả Lập Số Phận*: Game cuộc đời bằng AI."
            ),
            color=discord.Color.gold()
        )
        embed.set_footer(text="Bảng menu sẽ tự động đóng sau 60 giây hoạt động.")
        view = DynamicHelpView(self.bot, ctx.author)
        view.message = await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(OtherCog(bot))