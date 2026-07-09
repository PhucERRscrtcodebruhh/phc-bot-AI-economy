# lifesim.py
import os
import json
import random
import re
import html
import discord
from discord.ext import commands
from discord.ui import View, Modal, TextInput, Select

from constants import KESLING_ICON
from AIphcbot import ask_gemini, get_user_data, save_data, load_quiz_questions, player_inventory, get_system_data

# ==================== HELPERS ====================

def make_bar(value: int) -> str:
    clamped = max(0, min(100, value))
    num_filled = round(clamped / 10)
    bar = "■" * num_filled + "□" * (10 - num_filled)
    return f"`[{bar}]` ({clamped}%)"

def generate_childhood_math_quiz():
    op = random.choice(["+", "-", "*"])
    if op == "+":
        a, b = random.randint(5, 50), random.randint(5, 50)
        ans = a + b
    elif op == "-":
        a, b = random.randint(15, 60), random.randint(1, 15)
        ans = a - b
    else:
        a, b = random.randint(2, 9), random.randint(2, 9)
        ans = a * b
    
    wrong = list({ans + random.randint(1, 5), ans - random.randint(1, 5), ans + random.randint(6, 10)} - {ans})
    while len(wrong) < 3:
        wrong.append(ans + random.randint(11, 20))
    
    choices = [ans, wrong[0], wrong[1], wrong[2]]
    random.shuffle(choices)
    return f"Nhanh trí giải phép tính: **{a} {op} {b} = ?**", choices, choices.index(ans)

def get_scenario_from_db(age_range):
    db_file = "life_scenarios.json"
    if not os.path.exists(db_file):
        return None
    try:
        with open(db_file, "r", encoding="utf-8") as f:
            scenarios = json.load(f)
        matching = [s for s in scenarios if s.get("age_range") == age_range]
        if not matching:
            return None
        return random.choice(matching)
    except Exception:
        return None

def append_scenario_to_db(age_range, situation, choices):
    db_file = "life_scenarios.json"
    try:
        scenarios = []
        if os.path.exists(db_file):
            with open(db_file, "r", encoding="utf-8") as f:
                try:
                    scenarios = json.load(f)
                except Exception:
                    scenarios = []
        
        new_id = f"ai_gen_{random.randint(100000, 999999)}"
        new_scenario = {
            "event_id": new_id,
            "age_range": age_range,
            "situation": situation,
            "choices": choices
        }
        scenarios.append(new_scenario)
        
        temp_file = f"{db_file}.tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(scenarios, f, indent=4, ensure_ascii=False)
        os.replace(temp_file, db_file)
    except Exception:
        pass

# ==================== MODALS & VIEWS ====================

class LifeCustomChoiceModal(Modal, title="Quyết định của bạn"):
    custom_input = TextInput(
        label="Hành động của bạn trong thời gian qua?",
        placeholder="Ví dụ: Tôi quyết định đi làm thêm kiếm tiền phụ giúp bố mẹ...",
        style=discord.TextStyle.paragraph,
        max_length=150,
        required=True
    )

    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.parent_view.progress_year(interaction, custom_action=self.custom_input.value.strip())

class CustomSyndromeModal(Modal, title="Nhập hội chứng của bạn"):
    syndrome_input = TextInput(
        label="Hội chứng của bạn (Ví dụ: Sợ đàn bà...)",
        placeholder="Hội chứng này sẽ đi theo bạn suốt cả cuộc đời...",
        max_length=50,
        required=True
    )

    def __init__(self, parent_start_view):
        super().__init__()
        self.parent_start_view = parent_start_view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.parent_start_view.setup_hardcore_game(interaction, self.syndrome_input.value.strip())

class ModelSelectDropdown(Select):
    def __init__(self, current_model):
        options = [
            discord.SelectOption(label="Gemma 4 31B", value="gemma-4-31b-it", description="Model mặc định thông minh", emoji="🧠"),
            discord.SelectOption(label="Gemini 3.5 Flash", value="gemini-3.5-flash", description="Tốc độ cao, tối ưu cực tốt", emoji="☄️"),
            discord.SelectOption(label="Gemini 3 Flash Review", value="gemini-3.0-flash-review", description="Phiên bản thử nghiệm mới", emoji="🔬"),
            discord.SelectOption(label="Gemini 2.5 Flash", value="gemini-2.5-flash", description="Ổn định, nhanh nhạy", emoji="⚡"),
        ]
        super().__init__(placeholder=f"🤖 Đang chạy: {current_model}", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.author_id:
            return await interaction.response.send_message("❌ Bạn không điều khiển cuộc đời này!", ephemeral=True)
        chosen_model = self.values[0]
        self.view.active_model = chosen_model
        self.placeholder = f"🤖 Đang chạy: {chosen_model}"
        await interaction.response.send_message(f"🤖 Đã chuyển nóng Model AI sang **{chosen_model}**!", ephemeral=True)

class LifeCareerSelectView(View):
    def __init__(self, author, career_options, callback_func):
        super().__init__(timeout=60)
        self.author = author
        self.callback_func = callback_func
        select = Select(
            placeholder="Chọn nghề nghiệp tương lai...",
            options=[discord.SelectOption(label=job, value=job) for job in career_options]
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            return await interaction.response.send_message("❌ Đây không phải cuộc đời của bạn!", ephemeral=True)
        chosen_job = interaction.data["values"][0]
        self.stop()
        await self.callback_func(interaction, chosen_job)

class LifeSimView(View):
    def __init__(self, ctx, author_id, mode="Thường", syndrome="Bình thường", time_step_months=3):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.author_id = author_id
        self.mode = mode
        self.syndrome = syndrome
        self.personality = "Chưa bộc lộ (Chờ lên 3 tuổi) 👶"
        self.active_model = "gemma-4-31b-it" 
        self.time_step_months = time_step_months 
        self.years = 0
        self.months = 0
        self.gender = self.roll_gender()
        self.kataviet = 100  
        self.health = 100
        self.happiness = 100
        self.career = "Trẻ sơ sinh"
        self.salary = 0
        self.education_score = 0  
        self.highschool_type = ""  
        self.is_student = False
        self.dead = False
        self.father_name, self.mother_name = self.roll_parents()
        self.context_history = []
        self.update_role_for_age()
        self.current_event = ""
        self.current_choices = {}
        self.message = None
        self.add_item(ModelSelectDropdown(self.active_model))

    def roll_gender(self) -> str:
        r = random.uniform(0, 100)
        if r < 1.0:
            return random.choice(["Đồng tính nam (Gay) 🌈", "Đồng tính nữ (Les) 🌈", "Song tính (Bisexual) 🌈", "Chuyển giới (Transgender) ⚧️"])
        return "Nam ♂️" if r < 56.0 else "Nữ ♀️"

    def roll_parents(self) -> tuple:
        vietnamese_surnames = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Phan", "Vũ", "Võ", "Đặng", "Bùi"]
        f_middles = ["Văn", "Đình", "Hữu", "Minh", "Quốc", "Đức", "Thế", "Anh"]
        f_names = ["Hùng", "Cường", "Tuấn", "Dũng", "Sơn", "Hải", "Phong", "Nam", "Phúc", "Khang"]
        m_middles = ["Thị", "Hồng", "Mai", "Ngọc", "Thu", "Phương", "Khánh"]
        m_names = ["Hoa", "Lan", "Hương", "Trang", "Linh", "Hạnh", "Dung", "Anh", "Vy", "Thảo"]
        father = f"{random.choice(vietnamese_surnames)} {random.choice(f_middles)} {random.choice(f_names)}"
        mother = f"{random.choice(vietnamese_surnames)} {random.choice(m_middles)} {random.choice(m_names)}"
        return father, mother

    def get_pronoun(self) -> str:
        if self.years < 3: return "bé"
        if self.years < 10: return "con"
        if self.years < 18: return "bạn"
        if self.years < 65:
            return "anh" if "Nam" in self.gender else "chị" if "Nữ" in self.gender else "bạn"
        return "ông" if "Nam" in self.gender else "bà" if "Nữ" in self.gender else "cụ"

    def get_stage(self) -> str:
        if self.years < 3: return "Em bé (Nhà trẻ)"
        if self.years < 6: return "Mẫu giáo"
        if self.years < 10: return "Tiểu học"
        if self.years < 15: return "Trung học Cơ sở (THCS)"
        if self.years < 18: return "Cấp 3 - THPT"
        if self.years < 22 and self.is_student: return "Sinh viên Đại học"
        return "Người trưởng thành" if self.years < 65 else "Người già"

    def get_age_range_for_db(self) -> str:
        if self.years < 3: return "0-3"
        if self.years < 6: return "3-6"
        if self.years < 10: return "6-10"
        if self.years < 18: return "10-18"
        return "18-65" if self.years < 65 else "65+"

    def update_role_for_age(self):
        if self.years < 18 or (self.years < 22 and self.is_student):
            if self.years < 3: self.career = "Trẻ sơ sinh"
            elif self.years < 6: self.career = "Học sinh Mầm non"
            elif self.years < 10: self.career = "Học sinh Tiểu học"
            elif self.years < 15: self.career = "Học sinh THCS"
            elif self.years < 18: self.career = f"Học sinh Cấp 3 (Hệ {self.highschool_type or 'Mới nhập học'})"
            elif self.years < 22 and self.is_student: self.career = "Sinh viên Đại học"

    def get_age_display(self) -> str:
        if self.time_step_months == 12: return f"**{self.years} tuổi** (Hệ chơi nhanh)"
        return f"**{self.years} tuổi {self.months} tháng**"

    def add_to_context(self, event, outcome):
        self.context_history.append({"event": event, "outcome": outcome})
        if len(self.context_history) > 4: self.context_history.pop(0)

    async def fetch_ai_event(self, last_outcome_text="", force_crisis=False):
        age_range_db = self.get_age_range_for_db()
        use_database = False

        if not force_crisis and random.random() < 0.01:
            db_scenario = get_scenario_from_db(age_range_db)
            if db_scenario:
                use_database = True
                self.current_event = db_scenario["situation"]
                self.current_choices = db_scenario["choices"]
                self.btn_choice1.label = self.current_choices.get("choice_1", {}).get("text", "Lựa chọn A")[:40]
                self.btn_choice2.label = self.current_choices.get("choice_2", {}).get("text", "Lựa chọn B")[:40]
                self.btn_choice3.label = self.current_choices.get("choice_3", {}).get("text", "Lựa chọn C")[:40]

        if not use_database:
            time_unit = "1 năm qua" if self.time_step_months == 12 else "3 tháng qua"
            history_str = "".join([f"Tình huống: {step['event']} -> Quyết định: {step['outcome']}\n" for step in self.context_history])
            prompt = (
                f"Thông tin nhân vật hiện tại:\n"
                f"- Chế độ: {self.mode} | Hội chứng sinh ra: {self.syndrome} | Tính cách: {self.personality}\n"
                f"- Đại từ nhân xưng: \"{self.get_pronoun()}\"\n"
                f"- Gia đình: Bố tên là {self.father_name}, Mẹ tên là {self.mother_name}\n"
                f"- Giới tính: {self.gender}\n"
                f"- Tuổi: {self.get_age_display()} (Giai đoạn: {self.get_stage()})\n"
                f"- Vai trò/Nghề nghiệp: {self.career} (Học phí/Thu nhập: {self.salary} kataviet/{time_unit})\n"
                f"- Tiền mặt: {self.kataviet} kataviet | Sức khỏe: {self.health}% | Hạnh phúc: {self.happiness}%\n"
                f"- Lịch sử:\n{history_str or 'Vừa mới chào đời!'}\n"
                f"- Diễn biến {time_unit} trước: {last_outcome_text or 'Chào đời thành công!'}\n\n"
            )

            if force_crisis:
                prompt += f"🚨 SỰ KIỆN HUNG TIN SÉT ĐÁNH! Viết một biến cố bất ngờ cực xấu dở khóc dở cười diễn ra trong {time_unit}.\n\n"
            else:
                prompt += f"Hãy tạo ra biến cố ngắn gọn diễn ra trong {time_unit} bám sát lứa tuổi: {self.get_stage()}.\n\n"

            prompt += (
                f"Hãy sinh ra cấu trúc dữ liệu JSON chính xác sau:\n"
                f"{{\n"
                f"  \"event\": \"Mô tả tình huống {time_unit} (Gọi người chơi là '{self.get_pronoun()}', lồng ghép tính cách '{self.personality}' và hội chứng '{self.syndrome}', dưới 3 dòng)\",\n"
                f"  \"choice_1\": \"Nút 1 (ngắn gọn)\",\n"
                f"  \"choice_2\": \"Nút 2 (ngắn gọn)\",\n"
                f"  \"choice_3\": \"Nút 3 (ngắn gọn)\",\n"
                f"  \"outcomes\": {{\n"
                f"     \"choice_1\": {{\"money\": 10, \"health\": -5, \"happiness\": 15, \"text\": \"Kết quả lựa chọn 1\"}},\n"
                f"     \"choice_2\": {{\"money\": -20, \"health\": 5, \"happiness\": -10, \"text\": \"Kết quả lựa chọn 2\"}},\n"
                f"     \"choice_3\": {{\"money\": 0, \"health\": -5, \"happiness\": 5, \"text\": \"Kết quả lựa chọn 3\"}}\n"
                f"  }}\n"
                f"}}"
            )

            backup_model = get_system_data().get("active_ai_model")
            get_system_data()["active_ai_model"] = self.active_model

            try:
                from AIphcbot import strip_thinking_process
                raw_res = await ask_gemini(prompt, self.ctx.channel.id)
                if not raw_res: raise ValueError("AI offline")
                cleaned = re.sub(r"```json\s*|```", "", strip_thinking_process(raw_res)).strip()
                data = json.loads(cleaned)
                self.current_event = data["event"]
                self.current_choices = data["outcomes"]
                self.btn_choice1.label = data.get("choice_1", "Lựa chọn A")[:40]
                self.btn_choice2.label = data.get("choice_2", "Lựa chọn B")[:40]
                self.btn_choice3.label = data.get("choice_3", "Lựa chọn C")[:40]
                append_scenario_to_db(age_range_db, self.current_event, self.current_choices)
            except Exception:
                self.current_event = f"Thời gian trôi qua trong bình yên của giai đoạn {self.get_stage()}."
                self.btn_choice1.label = "An phận nghỉ ngơi"
                self.btn_choice2.label = "Cố gắng nỗ lực"
                self.btn_choice3.label = "Kiếm niềm vui"
                self.current_choices = {
                    "choice_1": {"money": 0, "health": 10, "happiness": 5, "text": "Nằm im lười biếng giúp bạn tích lũy sinh lực."},
                    "choice_2": {"money": -10, "health": -5, "happiness": 10, "text": "Lao động là vinh quang!"},
                    "choice_3": {"money": -15, "health": 5, "happiness": 15, "text": "Tiêu pha mua vui mang lại tiếng cười cho bạn."}
                }
            finally:
                if backup_model: get_system_data()["active_ai_model"] = backup_model

    async def fetch_ai_custom_choice(self, custom_action: str):
        time_unit = "1 năm" if self.time_step_months == 12 else "3 tháng"
        prompt = (
            f"Nhân vật {self.get_age_display()} (Hội chứng: {self.syndrome}, vai trò: {self.career}) quyết định:\n"
            f"\"{custom_action}\" trong {time_unit} qua.\n\n"
            f"Sinh kết quả dạng JSON:\n"
            f"{{\n"
            f"  \"text\": \"Mô tả kết quả\",\n"
            f"  \"money\": thay_đổi_tiền,\n"
            f"  \"health\": thay_đổi_sức_khỏe,\n"
            f"  \"happiness\": thay_đổi_hạnh_phúc\n"
            f"}}"
        )
        try:
            from AIphcbot import strip_thinking_process
            raw_res = await ask_gemini(prompt, self.ctx.channel.id)
            cleaned = re.sub(r"```json\s*|```", "", strip_thinking_process(raw_res)).strip()
            return json.loads(cleaned)
        except Exception:
            return {"text": f"Hành động '{custom_action}' tạo ra bước ngoặt kỳ quặc nhưng bình an!", "money": 0, "health": -5, "happiness": 5}

    def generate_embed(self, last_outcome="Chào đời thành công!"):
        embed = discord.Embed(
            title=f"🎮 TRÒ CHƠI CUỘC ĐỜI: {self.get_age_display()}",
            description=(
                f"🛡️ **Chế độ:** `{self.mode}` | **Hội chứng:** `{self.syndrome}`\n"
                f"🧠 **Tính cách:** `{self.personality}`\n"
                f"🏠 **Gia đình:** Bố: `{self.father_name}` | Mẹ: `{self.mother_name}`\n"
                f"### 📍 Diễn biến hiện tại:\n{self.current_event}"
            ),
            color=discord.Color.green() if not self.dead else discord.Color.red()
        )
        embed.add_field(name="🧬 Giới tính", value=f"**{self.gender}**", inline=True)
        embed.add_field(name="🎒 Vai trò / Nghề", value=f"`{self.career}`", inline=True)
        embed.add_field(name="💰 Ví tiền (Kataviet)", value=f"**{self.kataviet:,} KV**", inline=True)
        embed.add_field(name="❤️ Sức khỏe", value=make_bar(self.health), inline=True)
        embed.add_field(name="😊 Hạnh phúc", value=make_bar(self.happiness), inline=True)
        embed.add_field(name="🔔 Diễn biến kỳ trước", value=f"*{last_outcome}*", inline=False)
        if self.dead:
            embed.title = "🪦 TRÒ CHƠI CUỘC ĐỜI: Điểm Kết Thúc"
            embed.color = discord.Color.dark_red()
        return embed

    async def check_death_status(self):
        if self.health <= 0:
            self.dead = True
            return "Bạn đã kiệt quệ sức khỏe và qua đời tại giường bệnh..."
        if self.years >= 65:
            factor = 3 if self.mode == "Hardcore 🔥" else 1.5
            death_chance = int((self.years - 65) * factor + (self.months // 3))
            if random.randint(1, 150) < death_chance:
                self.dead = True
                return f"Tuổi cao sức yếu, cơ thể bạn suy kiệt đột ngột tại mốc {self.years} tuổi..."
        if self.years >= 95:
            self.dead = True
            return "Bạn đạt thọ giới hạn 95 tuổi và ra đi thanh thản..."
        return None

    async def end_life_game(self, interaction, final_outcome_text):
        self.dead = True
        for item in self.children: item.disabled = True
        converted_cash = max(50, int(self.kataviet / 8))  
        
        # Lưu thẳng tiền gốc thừa kế vào database một cách an toàn
        user_data = get_user_data(str(self.author_id))
        user_data['money'] = user_data.get('money', 0) + converted_cash
        save_data(player_inventory)

        embed = self.generate_embed(final_outcome_text)
        embed.add_field(name="💰 Di Sản Thừa Kế Thực Tế", value=f"Gia tài ảo quy đổi thành **{converted_cash:,}** {KESLING_ICON} chuyển vào ví!", inline=False)
        await interaction.edit_original_response(embed=embed, view=self)
        self.stop()

    async def progress_year(self, interaction, choice_key=None, custom_action=None, force_crisis=False):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ Đây không phải cuộc sống của bạn!", ephemeral=True)

        outcome_desc = ""
        if custom_action:
            data = await self.fetch_ai_custom_choice(custom_action)
            outcome_desc = data.get("text", "")
            self.kataviet += data.get("money", 0)
            self.health = max(0, min(100, self.health + data.get("health", 0)))
            self.happiness = max(0, min(100, self.happiness + data.get("happiness", 0)))
        elif choice_key:
            res = self.current_choices.get(choice_key, {"money": 0, "health": 0, "happiness": 0, "text": "Trôi qua êm đềm."})
            outcome_desc = res["text"]
            self.kataviet += res["money"]
            self.health = max(0, min(100, self.health + res["health"]))
            self.happiness = max(0, min(100, self.happiness + res["happiness"]))

        if self.salary != 0:
            self.kataviet += (self.salary * 4) if self.time_step_months == 12 else self.salary

        self.months += self.time_step_months
        if self.months >= 12:
            self.years += self.months // 12
            self.months = self.months % 12

        if self.years == 3 and self.months == 0:
            self.personality = random.choice(["Vô tri tấu hài 🤡", "Lì lợm bướng bỉnh 🐂", "Nhút nhát nhạy cảm 🥺", "Thông thái cụ non 🧠", "Cục súc thẳng thắn 💢"])
            outcome_desc = f"✨ **[TÍNH CÁCH]** Ở tuổi lên 3, bạn bộc lộ tính cách: **{self.personality}**!\n" + outcome_desc

        self.add_to_context(self.current_event, outcome_desc)
        self.update_role_for_age()

        death_cause = await self.check_death_status()
        if death_cause: return await self.end_life_game(interaction, death_cause)

        if 6 <= self.years < 10 and random.random() < 0.15:
            return await self.trigger_primary_math_quiz(interaction)
        if self.years == 15 and self.months == 0:
            return await self.trigger_highschool_entrance_exam(interaction, outcome_desc)
        if self.years == 18 and self.months == 0:
            return await self.trigger_university_exam_intro(interaction, outcome_desc)

        await self.fetch_ai_event(outcome_desc, force_crisis=force_crisis)
        await interaction.edit_original_response(embed=self.generate_embed(outcome_desc), view=self)

    async def trigger_primary_math_quiz(self, interaction):
        question, choices, correct_idx = generate_childhood_math_quiz()
        embed = discord.Embed(title="🏫 BÀI KIỂM TRA ĐỘT XUẤT", description=f"Cô giáo chỉ định bạn lên bảng giải toán!\n\n🔹 {question}", color=discord.Color.blue())
        
        class MathQuizView(discord.ui.View):
            def __init__(self, parent):
                super().__init__(timeout=30)
                self.parent = parent
            async def process_ans(self, btn_interaction, idx):
                self.stop()
                if idx == correct_idx:
                    self.parent.happiness = min(100, self.parent.happiness + 15)
                    self.parent.kataviet += 20
                    msg = "🎉 Trả lời đúng xuất sắc! Được cô giáo khen điểm 10."
                else:
                    self.parent.happiness = max(0, self.parent.happiness - 15)
                    self.parent.health = max(0, self.parent.health - 5)
                    msg = "❌ Ôi không, sai bét rồi! Bạn bị cô phạt đứng góc lớp."
                await btn_interaction.response.send_message(msg, ephemeral=True)
                await self.parent.fetch_ai_event(msg)
                await btn_interaction.edit_original_response(embed=self.parent.generate_embed(msg), view=self.parent)

        quiz_view = MathQuizView(self)
        for idx, choice in enumerate(choices):
            btn = discord.ui.Button(label=str(choice), style=discord.ButtonStyle.secondary, custom_id=str(idx))
            async def make_callback(val_idx):
                return lambda i: quiz_view.process_ans(i, val_idx)
            btn.callback = await make_callback(idx)
            quiz_view.add_item(btn)
        await interaction.edit_original_response(embed=embed, view=quiz_view)

    async def trigger_highschool_entrance_exam(self, interaction, outcome_desc):
        for item in self.children: item.disabled = True
        await interaction.edit_original_response(view=self)
        questions = [
            ("Trong hóa học, nguyên tố 'Fe' có tên gọi là gì?", ["Sắt", "Đồng", "Kẽm", "Nhôm"], 0),
            ("Tác phẩm văn học 'Tắt Đèn' do ai sáng tác?", ["Ngô Tất Tố", "Nam Cao", "Nguyễn Du", "Tô Hoài"], 0),
            ("Đại dương nào có diện tích rộng lớn nhất?", ["Thái Bình Dương", "Ấn Độ Dương", "Đại Tây Dương", "Bắc Băng Dương"], 0)
        ]
        score = 0
        for idx, (q_text, original_choices, correct_ans_idx) in enumerate(questions):
            indexed_choices = list(enumerate(original_choices))
            random.shuffle(indexed_choices)
            shuffled_choices = [c for _, c in indexed_choices]
            new_correct_idx = next(i for i, (o_idx, _) in enumerate(indexed_choices) if o_idx == correct_ans_idx)
            choices_str = "".join([f"**{chr(65+i)}.** {choice}\n" for i, choice in enumerate(shuffled_choices)])
            embed = discord.Embed(title=f"📝 THI LỚP 10: Câu {idx + 1}/3", description=f"**{q_text}**\n\n{choices_str}", color=discord.Color.orange())
            
            from sinkhole import QuizView as GlobalQuizView
            view = GlobalQuizView(author=self.ctx.author)
            await self.message.edit(embed=embed, view=view)
            view.message = self.message
            chosen = await view.wait_for_choice()
            if chosen is not None and chosen == new_correct_idx: score += 1

        final_grade = (score / 3) * 10
        self.months += 3
        if final_grade >= 6:
            self.highschool_type = "Công Lập"
            self.career = "Học sinh Cấp 3 (Trường Công)"
            result_msg = f"🎉 Đạt **{final_grade:.1f}/10** điểm! Bạn đỗ vào trường Công lập."
        else:
            self.highschool_type = "Tư Thục"
            self.career = "Học sinh Cấp 3 (Trường Tư)"
            self.salary = -50
            result_msg = f"😭 Đạt **{final_grade:.1f}/10** điểm. Bạn đóng học phí cao học trường tư."

        for item in self.children: item.disabled = False
        await self.fetch_ai_event(result_msg)
        await self.message.edit(embed=self.generate_embed(result_msg), view=self)

    async def trigger_university_exam_intro(self, interaction, outcome_desc):
        for item in self.children: item.disabled = True
        embed = discord.Embed(
            title="🎓 KỲ THI THPT QUỐC GIA (MỐC 18 TUỔI)",
            description=(
                f"Bạn bước sang tuổi rực rỡ nhất: **18 tuổi!** Hãy lựa chọn tương lai:\n\n"
                f"📚 **Thi Đại Học:** Trả lời THPTQG 10 câu để ứng tuyển ngành cao cấp.\n"
                f"⚒️ **Đi Làm Ngay:** Học trường đời, kiếm cơm bươn chải ngay lập tức!"
            ),
            color=discord.Color.gold()
        )
        
        class HighSchoolCrossroad(discord.ui.View):
            def __init__(self, parent):
                super().__init__(timeout=60)
                self.parent = parent
            @discord.ui.button(label="Thi THPT Quốc Gia 📚", style=discord.ButtonStyle.primary)
            async def college(self, btn_i, btn):
                self.stop()
                await self.parent.start_university_exam(btn_i)
            @discord.ui.button(label="Đi làm ngay ⚒️", style=discord.ButtonStyle.success)
            async def work(self, btn_i, btn):
                self.stop()
                await self.parent.choose_career_path(btn_i, is_college=False)
                
        await interaction.edit_original_response(embed=embed, view=HighSchoolCrossroad(self))

    async def start_university_exam(self, interaction):
        await interaction.response.defer()
        quiz_data = load_quiz_questions()
        easy_questions = quiz_data.get("easy", [])
        if not easy_questions:
            self.education_score = 10
            return await self.choose_career_path_direct(10)

        random.shuffle(easy_questions)
        exam_questions = easy_questions[:10]
        score = 0
        
        from sinkhole import QuizView as GlobalQuizView
        for idx, q in enumerate(exam_questions):
            q_text = html.unescape(q["question"])
            choices = [html.unescape(c) for c in q["choices"]]
            indexed_choices = list(enumerate(choices))
            random.shuffle(indexed_choices)
            shuffled_choices = [c for _, c in indexed_choices]
            new_correct_idx = next(i for i, (o_idx, _) in enumerate(indexed_choices) if o_idx == q["correct_index"])
            choices_str = "".join([f"**{chr(65+i)}.** {choice}\n" for i, choice in enumerate(shuffled_choices)])
            embed = discord.Embed(title=f"📝 THPT QUỐC GIA: Câu {idx + 1}/10", description=f"**{q_text}**\n\n{choices_str}", color=discord.Color.blue())
            
            view = GlobalQuizView(author=self.ctx.author)
            await self.message.edit(embed=embed, view=view)
            view.message = self.message
            chosen = await view.wait_for_choice()
            if chosen is not None and chosen == new_correct_idx: score += 1

        self.education_score = score
        self.years = 22  
        self.months = 0
        self.is_student = False
        await self.choose_career_path_direct(score)

    async def choose_career_path_direct(self, education_score):
        careers = {
            "Chuyên Gia AI": 450, "Bác Sĩ Trưởng Khoa": 400, "Chủ Tịch Tập Đoàn": 500
        } if education_score >= 8 else {
            "Kỹ Sư Phần Mềm": 250, "Giáo Viên Cấp 3": 180, "Chuyên Viên Tài Chính": 220
        } if education_score >= 5 else {
            "Nhân Viên Văn Phòng": 100, "Kỹ Thuật Viên": 120, "Thực Tập Sinh": 80
        }
        
        async def career_done_callback(job_interaction, chosen_job):
            self.career = chosen_job
            self.salary = careers[chosen_job]
            for item in self.children: item.disabled = False
            await self.fetch_ai_event(f"Nhận việc: {chosen_job}!")
            await job_interaction.response.edit_message(embed=self.generate_embed("Sự nghiệp bắt đầu!"), view=self)

        embed = discord.Embed(title="💼 ĐỊNH HƯỚNG NGHỀ NGHIỆP", description=f"Tốt nghiệp tuổi 22 (Điểm: {education_score}/10). Chọn công việc:", color=discord.Color.green())
        view = LifeCareerSelectView(self.ctx.author, list(careers.keys()), career_done_callback)
        await self.message.edit(embed=embed, view=view)

    async def choose_career_path(self, interaction, is_college=False):
        await interaction.response.defer()
        careers = {"Tài Xế Công Nghệ": 90, "Nhân Viên Bán Trà Sữa": 70, "Công Nhân": 80, "Streamer Vô Tri": 110}
        
        async def career_done_callback(job_interaction, chosen_job):
            self.career = chosen_job
            self.salary = careers[chosen_job]
            for item in self.children: item.disabled = False
            await self.fetch_ai_event(f"Bắt đầu đi làm: {chosen_job}!")
            await job_interaction.response.edit_message(embed=self.generate_embed("Bắt đầu kiếm sống!"), view=self)

        embed = discord.Embed(title="💼 ĐỊNH HƯỚNG NGHỀ NGHIỆP", description="Bươn chải trường đời tuổi 18. Chọn công việc:", color=discord.Color.green())
        view = LifeCareerSelectView(self.ctx.author, list(careers.keys()), career_done_callback)
        await self.message.edit(embed=embed, view=view)

    @discord.ui.button(label="Lựa chọn A", style=discord.ButtonStyle.secondary, row=0)
    async def btn_choice1(self, interaction, button):
        await interaction.response.defer(); await self.progress_year(interaction, choice_key="choice_1")

    @discord.ui.button(label="Lựa chọn B", style=discord.ButtonStyle.secondary, row=0)
    async def btn_choice2(self, interaction, button):
        await interaction.response.defer(); await self.progress_year(interaction, choice_key="choice_2")

    @discord.ui.button(label="Lựa chọn C", style=discord.ButtonStyle.secondary, row=0)
    async def btn_choice3(self, interaction, button):
        await interaction.response.defer(); await self.progress_year(interaction, choice_key="choice_3")

    @discord.ui.button(label="💚 Điều trị y tế (-500 KV)", style=discord.ButtonStyle.success, row=1)
    async def btn_heal(self, interaction, button):
        if interaction.user.id != self.author_id: return await interaction.response.send_message("❌ Lỗi!", ephemeral=True)
        if self.kataviet < 500: return await interaction.response.send_message("❌ Bạn không đủ tiền mặt!", ephemeral=True)
        await interaction.response.defer()
        self.kataviet -= 500
        old_h = self.health
        self.health = min(100, self.health + 30)
        msg = f"🏥 Điều trị y tế: Bạn hồi phục được **+{self.health - old_h}%** sức khỏe!"
        await self.progress_year(interaction, custom_action=msg)

    @discord.ui.button(label="⚠️ Hung tin", style=discord.ButtonStyle.danger, emoji="⚡", row=1)
    async def btn_crisis(self, interaction, button):
        await interaction.response.defer(); await self.progress_year(interaction, force_crisis=True)

    @discord.ui.button(label="💡 Hành động tự do...", style=discord.ButtonStyle.primary, emoji="✍️", row=2)
    async def btn_custom(self, interaction, button):
        if interaction.user.id != self.author_id: return await interaction.response.send_message("❌!", ephemeral=True)
        await interaction.response.send_modal(LifeCustomChoiceModal(self))

    @discord.ui.button(label="🪦 Từ bỏ số phận", style=discord.ButtonStyle.danger, emoji="💀", row=2)
    async def btn_giveup(self, interaction, button):
        if interaction.user.id != self.author_id: return await interaction.response.send_message("❌!", ephemeral=True)
        await interaction.response.defer(); await self.end_life_game(interaction, "Bạn đầu hàng số phận...")

class LifeStartView(View):
    def __init__(self, ctx, author_id):
        super().__init__(timeout=90)
        self.ctx = ctx
        self.author_id = author_id
        self.time_step_months = 3 

    def get_speed_label(self) -> str:
        return "Nhanh (1 năm/lượt) ⚡" if self.time_step_months == 12 else "Thường (3 tháng/lượt) ⏱️"

    def get_setup_embed(self) -> discord.Embed:
        return discord.Embed(
            title="👶 MÔ PHỎNG CUỘC ĐỜI MỚI",
            description=(
                f"⚙️ **Tốc độ chơi hiện tại:** `{self.get_speed_label()}`\n\n"
                "🟢 **Chế độ thường:** Trải nghiệm cuộc sống bình thường.\n"
                "💀 **Hardcore:** Độ khó cao, bắt đầu với một **hội chứng dị hợm**!"
            ),
            color=discord.Color.blue()
        )

    async def setup_hardcore_game(self, interaction, custom_syndrome=None):
        if custom_syndrome:
            syndrome = custom_syndrome
        else:
            syndrome = random.choice(["Tourette (Phát ngôn vô tri)", "Trầm cảm (Khởi đầu hạnh phúc thấp)", "Savant (Siêu trí tuệ, khó ở)"])
        await interaction.followup.edit_message(message_id=interaction.message.id, content="👶 *Đang nén gen... Vui lòng chờ...*", embed=None, view=None)
        sim_view = LifeSimView(self.ctx, self.author_id, mode="Hardcore 🔥", syndrome=syndrome, time_step_months=self.time_step_months)
        if "Trầm cảm" in syndrome: sim_view.happiness = 25
        await sim_view.fetch_ai_event()
        sim_view.message = await interaction.followup.edit_message(message_id=interaction.message.id, content=None, embed=sim_view.generate_embed(), view=sim_view)
        self.stop()

    @discord.ui.button(label="Thường (3 tháng)", style=discord.ButtonStyle.secondary, row=0)
    async def toggle_normal_speed(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(); self.time_step_months = 3
        await interaction.edit_original_response(embed=self.get_setup_embed(), view=self)

    @discord.ui.button(label="Nhanh (1 năm)", style=discord.ButtonStyle.secondary, row=0)
    async def toggle_fast_speed(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(); self.time_step_months = 12
        await interaction.edit_original_response(embed=self.get_setup_embed(), view=self)

    @discord.ui.button(label="🟢 Vào đời (Thường)", style=discord.ButtonStyle.success, row=1)
    async def normal_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.followup.edit_message(message_id=interaction.message.id, content="👶 *Đang khởi tạo tế bào...*", embed=None, view=None)
        sim_view = LifeSimView(self.ctx, self.author_id, mode="Thường", syndrome="Bình thường", time_step_months=self.time_step_months)
        await sim_view.fetch_ai_event()
        sim_view.message = await interaction.followup.edit_message(message_id=interaction.message.id, content=None, embed=sim_view.generate_embed(), view=sim_view)
        self.stop()

    @discord.ui.button(label="Hardcore: Random hội chứng 💀", style=discord.ButtonStyle.danger, row=1)
    async def hardcore_random(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(); await self.setup_hardcore_game(interaction)

    @discord.ui.button(label="Hardcore: Tự viết hội chứng ✍️", style=discord.ButtonStyle.primary, row=1)
    async def hardcore_custom(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CustomSyndromeModal(self))

# ==================== COG MODULE ====================

class LifeSimCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="cuocdoi", aliases=["life"])
    async def cuocdoi_command(self, ctx):
        """Hệ thống mô phỏng cuộc sống RPG vô tận sử dụng AI."""
        view = LifeStartView(ctx, ctx.author.id)
        embed = view.get_setup_embed()
        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(LifeSimCog(bot))