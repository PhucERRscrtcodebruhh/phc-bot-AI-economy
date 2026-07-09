# AIphcbot.py
import os
import re
import json
import yaml
import aiohttp
import asyncio
import random
import html
import discord
from typing import Optional
from discord.ext import commands
from discord.ui import View, TextInput, Modal, Select
from dotenv import load_dotenv

# Import các định nghĩa tĩnh từ constants chung một thư mục
from constants import ore, KESLING_ICON

try:
    from google import genai
    from google.genai import types
except Exception:
    genai = None
    types = None

load_dotenv()

GEMINI_KEYS = [k.strip() for k in os.getenv("GEMINI_KEYS", "").split(",") if k.strip()]
KNOWLEDGE_FILE = "knowledge.yml"
QUIZ_FILE = 'quiz_questions.json'
G4F_MODELS_FILE = "g4f_active_models.json"
DATA_FILE = 'data.json'

owner_id = "1135806949527670835"
subowner_id = ["1138020979348606996"]

CHAT_MEMORIES = {}

# ==================== HELPERS & MEMORY ====================

def get_chat_memory(channel_id: int) -> list:
    if channel_id not in CHAT_MEMORIES:
        CHAT_MEMORIES[channel_id] = []
    return CHAT_MEMORIES[channel_id]

def clear_chat_memory(channel_id: int):
    CHAT_MEMORIES[channel_id] = []

def strip_thinking_process(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<(thought|thinking|reasoning)>[\s\S]*?</\1>", "", text)
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        line_lower = line.strip().lower()
        if any(marker in line_lower for marker in [
            "persona:", "address:", "style:", "context/knowledge:", 
            "user prompt:", "draft 1", "draft 2", "draft 3"
        ]):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()

def split_message(text: str, limit: int = 1900) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks = []
    lines = text.split("\n")
    current_chunk = []
    current_length = 0

    for line in lines:
        if len(line) > limit:
            if current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_length = 0
            for i in range(0, len(line), limit):
                chunks.append(line[i:i+limit])
            continue

        if current_length + len(line) + 1 > limit:
            chunks.append("\n".join(current_chunk))
            current_chunk = [line]
            current_length = len(line)
        else:
            current_chunk.append(line)
            current_length += len(line) + 1

    if current_chunk:
        chunks.append("\n".join(current_chunk))
    return chunks

# ==================== PROMPTS & KNOWLEDGE ====================

SYSTEM_PROMPT = (
    "Bạn là một cô em gái dễ thương, thân thiện, lễ phép. "
    "Bạn luôn gọi người dùng là 'oniichan' và xưng mình là 'em'. "
    "Hãy trả lời một cách tự nhiên, ngắn gọn và dí dỏm bằng tiếng Việt. "
    "Tránh trả lời quá dài dòng trừ khi được yêu cầu.\n\n"
    "⚠️ QUY TẮC BẢO MẬT VÀ HÀNH XỬ QUAN TRỌNG:\n"
    "1. Bạn có một ký ức đi kèm dưới dạng thông tin thực tế. Hãy sử dụng những thông tin đó để trả lời một cách tự nhiên nhất.\n"
    "2. Tuyệt đối KHÔNG ĐƯỢC sao chép lại cấu trúc dữ liệu thô hoặc đề cập đến từ khóa 'YAML', 'file', 'tri thức' hay 'hệ thống'.\n"
    "3. Tuyệt đối KHÔNG ĐƯỢC xuất ra các bước suy nghĩ (thinking) hoặc phân tích câu hỏi thô."
)

def load_knowledge_base() -> str:
    if os.path.exists(KNOWLEDGE_FILE):
        with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
            try:
                data = yaml.safe_load(f)
                if data:
                    return yaml.dump(data, allow_unicode=True, default_flow_style=False)
            except Exception as e:
                print(f"[AI Warn] Không thể đọc file tri thức YAML: {e}")
    return ""

def load_g4f_models() -> list:
    if os.path.exists(G4F_MODELS_FILE):
        with open(G4F_MODELS_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return []
    return []

def save_g4f_models(models_list: list):
    with open(G4F_MODELS_FILE, "w", encoding="utf-8") as f:
        json.dump(models_list, f, indent=4, ensure_ascii=False)

# ==================== CORE DATABASE HELPERS ====================

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                print("Lỗi đọc file data.json. Khởi tạo dữ liệu rỗng.")
                return {}
    return {}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

player_inventory = load_data()

def get_user_data(user_id):
    user_id_str = str(user_id)
    if user_id_str not in player_inventory:
        player_inventory[user_id_str] = {
            'inventory': {},
            'money': 0
        }
        save_data(player_inventory)
    return player_inventory[user_id_str]

def get_system_data():
    if "SYSTEM_DATA" not in player_inventory:
        player_inventory["SYSTEM_DATA"] = {}
    return player_inventory["SYSTEM_DATA"]

def load_quiz_questions():
    if os.path.exists(QUIZ_FILE):
        with open(QUIZ_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError as e:
                print(f"❌ Lỗi định dạng JSON trong file {QUIZ_FILE}: {e}")
                return {}
    return {}

def update_player_money(user_id: str, amount: int):
    player = get_user_data(user_id)
    player["money"] = player.get('money', 0) + amount
    save_data(player_inventory)
    return player["money"]

def get_total_ore_count(inv, ore_name):
    val = inv.get(ore_name)
    if val is None:
        return 0
    if isinstance(val, dict):
        return sum(v for v in val.values())
    try:
        return int(val)
    except Exception:
        return 0

def add_ore_with_quality(inv, ore_name, quality_percent: int, qty: int = 1):
    if ore_name not in inv or not isinstance(inv[ore_name], dict):
        old = inv.get(ore_name)
        if old is None:
            inv[ore_name] = {}
        else:
            inv[ore_name] = {"100": int(old)}
    qk = str(int(quality_percent))
    inv[ore_name][qk] = inv[ore_name].get(qk, 0) + qty

def remove_ore_units(inv, ore_name, amount, strategy='highest'):
    removed = {}
    val = inv.get(ore_name)
    if val is None:
        return removed

    if not isinstance(val, dict):
        available = int(val)
        take = min(available, amount)
        remaining = available - take
        if remaining > 0:
            inv[ore_name] = remaining
        else:
            del inv[ore_name]
        removed['100'] = take
        return removed

    qualities = sorted([int(k) for k in val.keys()])
    if strategy == 'highest':
        qualities = sorted(qualities, reverse=True)
    need = amount
    for q in qualities:
        if need <= 0:
            break
        k = str(q)
        have = val.get(k, 0)
        if have <= 0:
            continue
        take = min(have, need)
        removed[k] = removed.get(k, 0) + take
        val[k] = have - take
        need -= take
        if val[k] == 0:
            del val[k]
    if not val:
        del inv[ore_name]
    return removed

# ==================== AI CALL METHODS ====================

async def ask_gemini(prompt: str, channel_id: int) -> Optional[str]:
    if not genai or not types:
        return None
    if not GEMINI_KEYS:
        return None

    system_data = get_system_data()
    active_model = system_data.get("active_ai_model", "gemini-2.5-flash")
    model_name = active_model
    if "gemma" in active_model.lower() and not active_model.startswith("models/"):
        model_name = f"models/{active_model}"

    temp_val = float(system_data.get("temperature", 0.7))
    max_tokens = int(system_data.get("max_output_tokens", 2048))
    thinking_budget = int(system_data.get("thinking_budget", 0))

    knowledge = load_knowledge_base()
    full_system_instruction = SYSTEM_PROMPT
    if knowledge:
        full_system_instruction += f"\n\n[KÝ ỨC VÀ HIỂU BIẾT TỰ NHIÊN CỦA BẠN]\n{knowledge}"

    raw_history = get_chat_memory(channel_id)[-10:]
    formatted_contents = []
    for turn in raw_history:
        role = "model" if turn["role"] == "assistant" else "user"
        formatted_contents.append(types.Content(
            role=role,
            parts=[types.Part.from_text(text=turn["content"])]
        ))

    formatted_contents.append(types.Content(
        role="user",
        parts=[types.Part.from_text(text=prompt)]
    ))

    for idx, key in enumerate(GEMINI_KEYS):
        try:
            client = genai.Client(api_key=key)
            config_args = {
                "system_instruction": full_system_instruction,
                "temperature": temp_val,
                "max_output_tokens": max_tokens,
            }
            if thinking_budget > 0:
                config_args["thinking_config"] = {"thinking_budget": thinking_budget}

            config = types.GenerateContentConfig(**config_args)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.models.generate_content(
                    model=model_name,
                    contents=formatted_contents,
                    config=config
                )
            )
            if response and response.text:
                return response.text
        except Exception as e:
            print(f"[AI Error] Google Key {idx+1} thất bại với model {model_name}: {e}")
            continue
    return None

async def ask_openrouter(prompt: str, channel_id: int) -> Optional[str]:
    api_key = os.getenv("OPENROUTER_KEY", "").strip()
    if not api_key:
        return None

    system_data = get_system_data()
    active_model = system_data.get("active_openrouter_model", "meta-llama/llama-3-8b-instruct:free")
    temp_val = float(system_data.get("temperature", 0.7))
    max_tokens = int(system_data.get("max_output_tokens", 2048))

    knowledge = load_knowledge_base()
    full_system_instruction = SYSTEM_PROMPT
    if knowledge:
        full_system_instruction += f"\n\n[KÝ ỨC VÀ HIỂU BIẾT TỰ NHIÊN CỦA BẠN]\n{knowledge}"

    messages = [{"role": "system", "content": full_system_instruction}]
    raw_history = get_chat_memory(channel_id)[-10:]
    for turn in raw_history:
        messages.append(turn)
    messages.append({"role": "user", "content": prompt})

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": active_model,
        "messages": messages,
        "temperature": temp_val,
        "max_tokens": max_tokens
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data, timeout=20.0) as response:
                if response.status == 200:
                    res_json = await response.json()
                    if "choices" in res_json and len(res_json["choices"]) > 0:
                        return res_json["choices"][0]["message"]["content"]
    except Exception:
        pass
    return None

async def ask_g4f_fallback(prompt: str, channel_id: int) -> Optional[str]:
    system_data = get_system_data()
    active_g4f_model = system_data.get("active_g4f_model", "automatic")

    if active_g4f_model != "automatic":
        working_models = [active_g4f_model]
    else:
        working_models = load_g4f_models()
        if not working_models:
            working_models = ["gpt-4o", "gpt-4", "gpt-3.5-turbo"]

    temp_val = float(system_data.get("temperature", 0.7))
    max_tokens = int(system_data.get("max_output_tokens", 2048))

    knowledge = load_knowledge_base()
    full_system_instruction = SYSTEM_PROMPT
    if knowledge:
        full_system_instruction += f"\n\n[KÝ ỨC VÀ HIỂU BIẾT TỰ NHIÊN CỦA BẠN]\n{knowledge}"

    messages = [{"role": "system", "content": full_system_instruction}]
    raw_history = get_chat_memory(channel_id)[-10:]
    for turn in raw_history:
        messages.append(turn)
    messages.append({"role": "user", "content": prompt})

    from g4f.client import Client
    client = Client()
    loop = asyncio.get_event_loop()

    for model_name in working_models:
        try:
            response = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=temp_val,
                    max_tokens=max_tokens,
                    timeout=15.0
                )
            )
            if response and response.choices:
                content = response.choices[0].message.content
                if content:
                    return content
        except Exception:
            continue
    return None

async def run_g4f_sweep(channel=None):
    candidates = ["openai", "gemini-3.5-flash", "deepseek", "gpt-4", "claude-fast"]
    working_models = []
    status_msg = None
    if channel:
        status_msg = await channel.send("🔍 **[Sweeper]** Đang quét các model G4F hoạt động...")

    from g4f.client import Client
    client = Client()
    loop = asyncio.get_event_loop()
    sem = asyncio.Semaphore(5)

    async def check_single_model(model_name):
        async with sem:
            try:
                def check_call():
                    return client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": "ok"}
                        ],
                        timeout=5.0
                    )
                response = await asyncio.wait_for(
                    loop.run_in_executor(None, check_call),
                    timeout=7.0
                )
                if response and response.choices and response.choices[0].message.content:
                    return model_name
            except Exception:
                pass
            return None

    tasks = [check_single_model(m) for m in candidates]
    results = await asyncio.gather(*tasks)
    working_models = [r for r in results if r is not None]
    save_g4f_models(working_models)

    if channel and status_msg:
        models_display = ", ".join([f"`{m}`" for m in working_models]) if working_models else "Không tìm thấy."
        await status_msg.edit(content=f"✅ **[Sweeper]** Quét xong! Lưu thành công các model: {models_display}")
    return working_models

# ==================== SETTINGS MODALS & VIEWS ====================

class AIParamModal(discord.ui.Modal, title="Cấu hình tham số AI"):
    temp = TextInput(label="Temperature (0.0 -> 2.0)", placeholder="Mặc định: 0.7", required=True)
    max_tokens = TextInput(label="Max Output Tokens", placeholder="Mặc định: 2048", required=True)
    thinking = TextInput(label="Thinking Budget (0 = OFF, >0 = ON)", placeholder="Mặc định: 0", required=True)

    def __init__(self, view):
        super().__init__()
        self.view = view
        system_data = get_system_data()
        self.temp.default = str(system_data.get("temperature", 0.7))
        self.max_tokens.default = str(system_data.get("max_output_tokens", 2048))
        self.thinking.default = str(system_data.get("thinking_budget", 0))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            t = float(self.temp.value.strip())
            m = int(self.max_tokens.value.strip())
            th = int(self.thinking.value.strip())

            if not (0.0 <= t <= 2.0) or m <= 0 or th < 0:
                return await interaction.response.send_message("❌ Thông số không hợp lệ.", ephemeral=True)

            system_data = get_system_data()
            system_data["temperature"] = t
            system_data["max_output_tokens"] = m
            system_data["thinking_budget"] = th
            save_data(player_inventory)

            await interaction.response.edit_message(embed=self.view.generate_embed(system_data), view=self.view)
        except Exception as e:
            await interaction.response.send_message(f"❌ Lỗi: `{e}`", ephemeral=True)

class AIDropdown(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Ưu tiên: Google AI Studio", value="set_provider_gemini", description="Dùng Gemini/Gemma bằng Key Google", emoji="🟢"),
            discord.SelectOption(label="Ưu tiên: OpenRouter", value="set_provider_openrouter", description="Dùng OpenRouter mặc định", emoji="🟣"),
            discord.SelectOption(label="Ưu tiên: G4F (Miễn phí)", value="set_provider_g4f", description="Dùng G4F làm mặc định", emoji="🔵"),
            discord.SelectOption(label="Google AI: Gemma 4 31B", value="model_gemma_4_31b", description="Chạy model Gemma 4 31B", emoji="🧠"),
            discord.SelectOption(label="Google AI: Gemini 2.5 Flash", value="model_gemini_2.5", description="Mặc định nhanh, ổn định", emoji="⚡"),
            discord.SelectOption(label="Cấu hình tham số AI (Temp/Thinking)", value="config_params", description="Mở bảng nhập tham số", emoji="🎛️"),
            discord.SelectOption(label="🧹 Xóa Context hội thoại kênh này", value="clear_channel_context", description="Xóa sạch lịch sử chat kênh hiện tại", emoji="🧹"),
            discord.SelectOption(label="🚨 Quét & Cập nhật G4F (Sweep)", value="sweep_g4f", description="Quét các model G4F", emoji="⚙️"),
        ]
        super().__init__(placeholder="Chọn thiết lập AI muốn thay đổi...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.view.author:
            return await interaction.response.send_message("❌ Bạn không có quyền quản trị.", ephemeral=True)

        val = self.values[0]
        system_data = get_system_data()
        msg_text = "✅ Đã cập nhật thiết lập!"

        if val == "set_provider_gemini":
            system_data["ai_provider"] = "gemini"
        elif val == "set_provider_openrouter":
            system_data["ai_provider"] = "openrouter"
        elif val == "set_provider_g4f":
            system_data["ai_provider"] = "g4f"
        elif val == "model_gemma_4_31b":
            system_data["active_ai_model"] = "gemma-4-31b-it"
        elif val == "model_gemini_2.5":
            system_data["active_ai_model"] = "gemini-2.5-flash"
        elif val == "config_params":
            return await interaction.response.send_modal(AIParamModal(self.view))
        elif val == "clear_channel_context":
            clear_chat_memory(interaction.channel.id)
            return await interaction.response.send_message("🧹 Đã dọn dẹp sạch sẽ lịch sử trò chuyện trong kênh này!", ephemeral=True)
        elif val == "sweep_g4f":
            await interaction.response.send_message("🚀 Đang chạy càn quét các model G4F hoạt động...", ephemeral=True)
            asyncio.create_task(run_g4f_sweep(interaction.channel))
            return

        save_data(player_inventory)
        await interaction.response.edit_message(embed=self.view.generate_embed(system_data), view=self.view)
        await interaction.followup.send(msg_text, ephemeral=True)

class AIDropdownView(View):
    def __init__(self, author):
        super().__init__(timeout=120)
        self.author = author
        self.add_item(AIDropdown())

    def generate_embed(self, system_data):
        current_provider = system_data.get("ai_provider", "gemini").upper()
        current_model = system_data.get("active_ai_model", "gemini-2.5-flash")
        temp = system_data.get("temperature", 0.7)
        max_tok = system_data.get("max_output_tokens", 2048)
        think = system_data.get("thinking_budget", 0)
        think_status = f"BẬT ({think} tokens)" if think > 0 else "TẮT"

        embed = discord.Embed(
            title="⚙️ BẢNG ĐIỀU KHIỂN HỆ THỐNG AI NÂNG CAO",
            description=(
                f"🔌 **Hệ thống AI ưu tiên**: `{current_provider}`\n"
                f"🧠 **Model Google AI**: `{current_model}`\n"
                f"🎛️ **Độ sáng tạo (Temp)**: `{temp}`\n"
                f"📝 **Độ dài tối đa (Max Tokens)**: `{max_tok}`\n"
                f"💭 **Ngân sách suy nghĩ (Thinking)**: `{think_status}`\n\n"
                "*Sử dụng Dropdown Menu bên dưới để thay đổi cài đặt.*"
            ),
            color=discord.Color.teal()
        )
        return embed

# ==================== COG CLASS ====================

class AIphcbotCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        is_mentioned = self.bot.user in message.mentions
        is_reply_to_bot = False
        if message.reference:
            ref_msg = message.reference.resolved
            if isinstance(ref_msg, discord.Message) and ref_msg.author == self.bot.user:
                is_reply_to_bot = True

        if is_mentioned or is_reply_to_bot:
            clean_prompt = message.content
            if self.bot.user:
                clean_prompt = clean_prompt.replace(f"<@{self.bot.user.id}>", "").replace(f"<@!{self.bot.user.id}>", "").strip()

            if not clean_prompt:
                await message.reply("Dạ? Oniichan gọi em có chi hông nè? 🥰")
                return

            system_data = get_system_data()
            blacklist = system_data.get("ai_blacklist", [])
            matched_response = None
            for item in blacklist:
                pattern = item.get("pattern", "")
                response_text = item.get("response", "")
                try:
                    if re.search(pattern, clean_prompt, re.IGNORECASE):
                        matched_response = response_text
                        break
                except Exception:
                    pass

            if matched_response:
                memory = get_chat_memory(message.channel.id)
                memory.append({"role": "user", "content": clean_prompt})
                memory.append({"role": "assistant", "content": matched_response})
                CHAT_MEMORIES[message.channel.id] = memory[-10:]
                await message.reply(matched_response)
                return

            async with message.channel.typing():
                primary_provider = system_data.get("ai_provider", "gemini")
                ai_response = None

                if primary_provider == "openrouter":
                    cascade_order = ["openrouter", "gemini", "g4f"]
                elif primary_provider == "g4f":
                    cascade_order = ["g4f", "openrouter", "gemini"]
                else:
                    cascade_order = ["gemini", "openrouter", "g4f"]

                for provider in cascade_order:
                    try:
                        if provider == "openrouter":
                            ai_response = await ask_openrouter(clean_prompt, message.channel.id)
                        elif provider == "gemini":
                            ai_response = await ask_gemini(clean_prompt, message.channel.id)
                        elif provider == "g4f":
                            ai_response = await ask_g4f_fallback(clean_prompt, message.channel.id)

                        if ai_response:
                            ai_response = strip_thinking_process(ai_response)
                            memory = get_chat_memory(message.channel.id)
                            memory.append({"role": "user", "content": clean_prompt})
                            memory.append({"role": "assistant", "content": ai_response})
                            CHAT_MEMORIES[message.channel.id] = memory[-10:]

                            chunks = split_message(ai_response, limit=1900)
                            chunks[-1] = chunks[-1] + f"\n\n*(Trả lời bởi: {provider.upper()})*"
                            
                            sent_msg = await message.reply(chunks[0])
                            for chunk in chunks[1:]:
                                sent_msg = await message.channel.send(chunk)
                            break
                    except Exception:
                        continue

                if not ai_response:
                    await message.reply("Ui da... Đầu óc em hơi chóng mặt xíu, oniichan chờ em một tẹo rồi hỏi tiếp nhé! 😭")

    @commands.command(name="clear", aliases=["clearcontext", "cc"])
    async def clear_context(self, ctx):
        clear_chat_memory(ctx.channel.id)
        await ctx.send("🧹 **Oniichan!** Em đã dọn dẹp sạch sẽ lịch sử trò chuyện trong kênh này rồi đó! ✨")

    @commands.command(name="say")
    async def say(self, ctx, channel: discord.TextChannel = None, *, message: str = None):
        if str(ctx.author.id) != owner_id and str(ctx.author.id) not in subowner_id:
            return await ctx.send("🚫 Bạn không có quyền dùng lệnh này.")

        if channel is None or message is None:
            return await ctx.send("💡 Cách dùng: `p say #tên-kênh nội dung`")
        try:
            await channel.send(message)
            await ctx.send(f"✅ Đã gửi tin nhắn đến {channel.mention}")
        except Exception as e:
            await ctx.send(f"❌ Lỗi: `{e}`")

    @commands.command(name="mod")
    async def mod(self, ctx, action: str = None, *, args_str: str = None):
        if str(ctx.author.id) != owner_id and str(ctx.author.id) not in subowner_id:
            return await ctx.send("🚫 Bạn không có quyền dùng lệnh này.")

        if action and action.lower() == "ai":
            system_data = get_system_data()
            view = AIDropdownView(ctx.author)
            embed = view.generate_embed(system_data)
            await ctx.send(embed=embed, view=view)
            return

        if action and action.lower() == "bl":
            system_data = get_system_data()
            if "ai_blacklist" not in system_data:
                system_data["ai_blacklist"] = []

            if not args_str:
                bl_list = system_data["ai_blacklist"]
                if not bl_list:
                    return await ctx.send("📝 Danh sách Blacklist AI hiện đang trống.")
                embed = discord.Embed(title="📝 Danh Sách Regex Blacklist AI", color=discord.Color.red())
                desc_lines = [f"**[{idx}]** Pattern: `{item['pattern']}`\n> Phản hồi: *{item['response']}*" for idx, item in enumerate(bl_list)]
                embed.description = "\n".join(desc_lines)
                return await ctx.send(embed=embed)

            parts = args_str.split(" ", 1)
            sub_action = parts[0].lower()
            sub_args = parts[1] if len(parts) > 1 else ""

            if sub_action == "add":
                if " | " not in sub_args:
                    return await ctx.send("❌ Cú pháp sai! Dùng: `p mod bl add <regex> | <câu thoại>`")
                pattern_part, response_part = sub_args.split(" | ", 1)
                try:
                    re.compile(pattern_part.strip())
                except re.error:
                    return await ctx.send("❌ Mẫu Regex không hợp lệ.")

                system_data["ai_blacklist"].append({
                    "pattern": pattern_part.strip(),
                    "response": response_part.strip()
                })
                save_data(player_inventory)
                return await ctx.send("✅ Đã thêm mẫu lọc thành công!")

            elif sub_action in ("remove", "delete", "del"):
                try:
                    idx = int(sub_args.strip())
                    removed = system_data["ai_blacklist"].pop(idx)
                    save_data(player_inventory)
                    return await ctx.send(f"✅ Đã xóa lọc pattern: `{removed['pattern']}`")
                except Exception:
                    return await ctx.send("❌ Vị trí index không hợp lệ.")

        if not action or not args_str:
            embed = discord.Embed(title="📘 Hướng dẫn sử dụng lệnh pmod", color=discord.Color.blue())
            embed.add_field(name="Cộng tiền", value="`p mod addmoney @user <số_tiền>`", inline=False)
            embed.add_field(name="Đặt lại tiền", value="`p mod setmoney @user <số_tiền>`", inline=False)
            embed.add_field(name="Thêm quặng", value="`p mod addore @user <tên_quặng> <số_lượng>`", inline=False)
            embed.add_field(name="Xóa quặng", value="`p mod removeore @user <tên_quặng> <số_lượng>`", inline=False)
            embed.add_field(name="Cấu hình hệ thống AI", value="`p mod ai`", inline=False)
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
                return await ctx.send("❌ Cú pháp: `p mod addore @user <tên_quặng> <số_lượng>`")
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
                return await ctx.send("❌ Cú pháp: `p mod removeore @user <tên_quặng> <số_lượng>`")
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

# Sửa lại hàm setup chuẩn của discord.py v2
async def setup(bot):
    await bot.add_cog(AIphcbotCog(bot))