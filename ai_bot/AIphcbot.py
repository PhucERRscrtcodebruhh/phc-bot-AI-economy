# AIphcbot.py - Discord Cog & UI cho Bot AI
import os
import re
import asyncio
import datetime
from datetime import timedelta
from typing import Optional
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, TextInput, Modal, Select

from AI_core import (
    GEMINI_KEYS, owner_id, subowner_id,
    CHAT_MEMORIES, get_chat_memory, clear_chat_memory,
    strip_thinking_process, split_message,
    load_data, save_data, player_inventory, get_system_data,
    ask_gemini, ask_openrouter, ask_groq, ask_deepseek,
    ask_g4f_fallback, run_g4f_sweep,
    call_moderation_api, parse_moderation_result
)

class AdminModerationView(discord.ui.View):
    def __init__(self, target_member: discord.Member, target_message: discord.Message, severity: int, reason: str):
        super().__init__(timeout=86400)
        self.target_member = target_member
        self.target_message = target_message
        self.severity = severity
        self.reason = reason

    @discord.ui.button(label="Mute 10 phút", style=discord.ButtonStyle.danger, emoji="🔇")
    async def mute_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not (interaction.user.guild_permissions.moderate_members or interaction.user.guild_permissions.administrator or str(interaction.user.id) == owner_id or str(interaction.user.id) in subowner_id):
            return await interaction.response.send_message("❌ Bạn không có quyền Moderate Members.", ephemeral=True)

        try:
            duration = timedelta(minutes=10)
            await self.target_member.timeout(duration, reason=f"Admin phạt theo AI Moderation: {self.reason} ({self.severity}%)")
            button.disabled = True
            button.label = f"Đã Mute 10p ({interaction.user.display_name})"
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(f"✅ Đã Mute {self.target_member.mention} 10 phút!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Bot không đủ quyền Mute thành viên này (kiểm tra Role Hierarchy).", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Lỗi: `{e}`", ephemeral=True)

    @discord.ui.button(label="Xóa tin nhắn", style=discord.ButtonStyle.secondary, emoji="🗑️")
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not (interaction.user.guild_permissions.manage_messages or interaction.user.guild_permissions.administrator or str(interaction.user.id) == owner_id or str(interaction.user.id) in subowner_id):
            return await interaction.response.send_message("❌ Bạn không có quyền Manage Messages.", ephemeral=True)

        try:
            await self.target_message.delete()
            button.disabled = True
            button.label = f"Đã xóa ({interaction.user.display_name})"
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("✅ Đã xóa tin nhắn vi phạm!", ephemeral=True)
        except discord.NotFound:
            button.disabled = True
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("⚠️ Tin nhắn này đã được xóa trước đó.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Bot không có quyền xóa tin nhắn trong kênh đó.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Lỗi: `{e}`", ephemeral=True)

    @discord.ui.button(label="Cảnh cáo DM", style=discord.ButtonStyle.primary, emoji="⚠️")
    async def warn_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not (interaction.user.guild_permissions.moderate_members or interaction.user.guild_permissions.administrator or str(interaction.user.id) == owner_id or str(interaction.user.id) in subowner_id):
            return await interaction.response.send_message("❌ Bạn không có quyền điều hành.", ephemeral=True)

        try:
            embed_dm = discord.Embed(
                title=f"⚠️ Cảnh cáo từ Ban Quản Trị {self.target_member.guild.name}",
                description=(
                    f"Tin nhắn của bạn trong kênh {self.target_message.channel.mention} có dấu hiệu xúc phạm.\n\n"
                    f"💬 **Nội dung**: *\"{self.target_message.content}\"*\n"
                    f"📊 **Độ xúc phạm**: `{self.severity}%`\n"
                    f"📝 **Lý do**: {self.reason}\n\n"
                    f"Vui lòng chú ý ngôn từ để tránh bị xử phạt nặng hơn!"
                ),
                color=discord.Color.gold(),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            await self.target_member.send(embed=embed_dm)
            button.disabled = True
            button.label = f"Đã cảnh cáo ({interaction.user.display_name})"
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(f"✅ Đã gửi DM cảnh cáo đến {self.target_member.mention}!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(f"⚠️ Không thể gửi DM cho {self.target_member.mention} (người dùng chặn DM).", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Lỗi: `{e}`", ephemeral=True)

    @discord.ui.button(label="Bỏ qua", style=discord.ButtonStyle.success, emoji="✅")
    async def ignore_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not (interaction.user.guild_permissions.manage_messages or interaction.user.guild_permissions.administrator or str(interaction.user.id) == owner_id or str(interaction.user.id) in subowner_id):
            return await interaction.response.send_message("❌ Bạn không có quyền điều hành.", ephemeral=True)

        for item in self.children:
            item.disabled = True
        button.label = f"Đã bỏ qua ({interaction.user.display_name})"
        await interaction.response.edit_message(view=self)
        await interaction.followup.send("✅ Đã bỏ qua báo cáo này.", ephemeral=True)

def get_admin_log_channel(guild: discord.Guild) -> Optional[discord.TextChannel]:
    system_data = get_system_data()
    saved_channels = system_data.get("moderation_log_channels", {})
    saved_id = saved_channels.get(str(guild.id))
    if saved_id:
        ch = guild.get_channel(int(saved_id))
        if ch and isinstance(ch, discord.TextChannel):
            return ch

    keywords = ["mod-log", "admin-log", "kiem-duyet", "kiểm-duyệt", "canh-bao", "cảnh-báo", "moderation", "logs"]
    for ch in guild.text_channels:
        lower_name = ch.name.lower()
        if any(kw in lower_name for kw in keywords):
            return ch

    if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
        return guild.system_channel

    return None

async def send_admin_report(message: discord.Message, severity: int, reason: str, action_taken: str = "Cần Admin duyệt (Mức độ thấp)"):
    guild = message.guild
    if not guild:
        return

    admin_channel = get_admin_log_channel(guild)
    if not admin_channel:
        return

    is_auto_muted = "Mute" in action_taken
    embed_color = discord.Color.red() if is_auto_muted else discord.Color.gold()
    title_text = "🚨 [AI MODERATION] XÚC PHẠM MỨC CAO - ĐÃ TỰ ĐỘNG XỬ LÝ" if is_auto_muted else "🛡️ [AI MODERATION] CẦN ADMIN DUYỆT - ĐỘ XÚC PHẠM THẤP"

    embed = discord.Embed(
        title=title_text,
        color=embed_color,
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    embed.add_field(name="👤 Người gửi", value=f"{message.author.mention} (`{message.author.name}`)\nID: `{message.author.id}`", inline=True)
    embed.add_field(name="📍 Kênh", value=message.channel.mention, inline=True)
    embed.add_field(name="📊 Độ xúc phạm", value=f"`{severity}%`", inline=True)
    embed.add_field(name="💬 Nội dung tin nhắn", value=f">>> {message.content[:1000]}", inline=False)
    embed.add_field(name="📝 Phân tích từ AI", value=f"• Lý do: {reason}\n• Trạng thái: **{action_taken}**", inline=False)
    embed.add_field(name="🔗 Tin nhắn gốc", value=f"[Nhấn vào đây để xem]({message.jump_url})", inline=False)

    system_data = get_system_data()
    mod_model = system_data.get("moderation_model", "openai/gpt-oss-safeguard-20b")
    embed.set_footer(text=f"Model: {mod_model} • AI Moderation System")

    view = AdminModerationView(message.author, message, severity, reason) if not is_auto_muted else None

    try:
        if view:
            await admin_channel.send(embed=embed, view=view)
        else:
            await admin_channel.send(embed=embed)
    except Exception as e:
        print(f"[Admin Report Send Error]: {e}")


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
            discord.SelectOption(label="Ưu tiên: Google AI Studio", value="set_provider_gemini", description="Dùng hệ thống cân bằng tải Gemini Keys", emoji="🟢"),
            discord.SelectOption(label="Ưu tiên: Groq (Siêu tốc)", value="set_provider_groq", description="Dùng Groq API (Llama 3.3 70B)", emoji="⚡"),
            discord.SelectOption(label="Ưu tiên: DeepSeek", value="set_provider_deepseek", description="Dùng DeepSeek API (V3 / R1)", emoji="🐳"),
            discord.SelectOption(label="Ưu tiên: OpenRouter", value="set_provider_openrouter", description="Dùng OpenRouter mặc định", emoji="🟣"),
            discord.SelectOption(label="Ưu tiên: G4F (Miễn phí)", value="set_provider_g4f", description="Dùng G4F làm mặc định", emoji="🔵"),
            discord.SelectOption(label="Google AI: Gemma 4 31B", value="model_gemma_4_31b", description="Chạy model Gemma 4 31B", emoji="🧠"),
            discord.SelectOption(label="Google AI: Gemini 2.5 Flash", value="model_gemini_2.5", description="Mặc định nhanh, ổn định", emoji="⚡"),
            discord.SelectOption(label="Groq: Llama 3.3 70B", value="model_groq_llama70b", description="Model Llama 3.3 70B trên Groq", emoji="🦙"),
            discord.SelectOption(label="DeepSeek: Chat (V3)", value="model_deepseek_chat", description="Model DeepSeek V3", emoji="🤖"),
            discord.SelectOption(label="Bật/Tắt AI Moderation", value="toggle_ai_moderation", description="Bật hoặc tắt hệ thống kiểm duyệt AI", emoji="🛡️"),
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
        elif val == "set_provider_groq":
            system_data["ai_provider"] = "groq"
        elif val == "set_provider_deepseek":
            system_data["ai_provider"] = "deepseek"
        elif val == "set_provider_openrouter":
            system_data["ai_provider"] = "openrouter"
        elif val == "set_provider_g4f":
            system_data["ai_provider"] = "g4f"
        elif val == "model_gemma_4_31b":
            system_data["active_ai_model"] = "gemma-4-31b-it"
        elif val == "model_gemini_2.5":
            system_data["active_ai_model"] = "gemini-2.5-flash"
        elif val == "model_groq_llama70b":
            system_data["active_groq_model"] = "llama-3.3-70b-versatile"
        elif val == "model_deepseek_chat":
            system_data["active_deepseek_model"] = "deepseek-chat"
        elif val == "toggle_ai_moderation":
            cur = system_data.get("moderation_enabled", True)
            system_data["moderation_enabled"] = not cur
            status_str = "BẬT" if not cur else "TẮT"
            msg_text = f"🛡️ Đã {status_str} tính năng AI Moderation toàn cục!"
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
        groq_model = system_data.get("active_groq_model", "llama-3.3-70b-versatile")
        deepseek_model = system_data.get("active_deepseek_model", "deepseek-chat")
        openrouter_model = system_data.get("active_openrouter_model", "meta-llama/llama-3-8b-instruct:free")
        temp = system_data.get("temperature", 0.7)
        max_tok = system_data.get("max_output_tokens", 2048)
        think = system_data.get("thinking_budget", 0)
        think_status = f"BẬT ({think} tokens)" if think > 0 else "TẮT"
        total_keys = len(GEMINI_KEYS)

        groq_key_stat = "Đã cấu hình" if (os.getenv("GROQ_API_KEY") or os.getenv("GROQ_KEY")) else "Chưa cài"
        deepseek_key_stat = "Đã cấu hình" if (os.getenv("DEEPSEEK_API_KEY") or os.getenv("DEEPSEEK_KEY")) else "Chưa cài"
        openrouter_key_stat = "Đã cấu hình" if os.getenv("OPENROUTER_KEY") else "Chưa cài"

        mod_enabled = "BẬT" if system_data.get("moderation_enabled", True) else "TẮT"
        mod_model = system_data.get("moderation_model", "openai/gpt-oss-safeguard-20b")
        mod_rep = system_data.get("moderation_report_threshold", 25)
        mod_mute = system_data.get("moderation_mute_threshold", 70)
        mod_dur = system_data.get("moderation_mute_duration", 10)

        embed = discord.Embed(
            title="⚙️ BẢNG ĐIỀU KHIỂN HỆ THỐNG AI & KIỂM DUYỆT",
            description=(
                f"🔌 **Hệ thống AI ưu tiên**: `{current_provider}`\n\n"
                f"**📡 Nhà cung cấp Model:**\n"
                f"• 🟢 **Google AI Studio**: `{total_keys} Keys` (Model: `{current_model}`)\n"
                f"• ⚡ **Groq**: `{groq_key_stat}` (Model: `{groq_model}`)\n"
                f"• 🐳 **DeepSeek**: `{deepseek_key_stat}` (Model: `{deepseek_model}`)\n"
                f"• 🟣 **OpenRouter**: `{openrouter_key_stat}` (Model: `{openrouter_model}`)\n"
                f"• 🔵 **G4F**: `Miễn phí (Tự động xoay vòng)`\n\n"
                f"**🛡️ AI Moderation (Tiếng Việt):**\n"
                f"• Trạng thái: `{mod_enabled}`\n"
                f"• Model kiểm duyệt: `{mod_model}`\n"
                f"• Ngưỡng Báo Admin (Thấp): `>= {mod_rep}%`\n"
                f"• Ngưỡng Mute (Cao): `>= {mod_mute}%` (Thời gian: `{mod_dur} phút`)\n\n"
                f"**🎛️ Tham số Chatbot:**\n"
                f"• Độ sáng tạo (Temp): `{temp}` | Max Tokens: `{max_tok}` | Thinking: `{think_status}`\n\n"
                "*Sử dụng Dropdown Menu bên dưới để thay đổi cài đặt nhanh.*"
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

        # AI Moderation kiểm duyệt tự động tiếng Việt (Chạy ngầm không chặn luồng)
        if message.guild:
            asyncio.create_task(self.handle_ai_moderation(message))

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
                await message.reply("Dạ? Có chi hông nè? 🥰")
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
                primary_provider = system_data.get("ai_provider", "gemini").lower()
                ai_response = None
                guild_id = message.guild.id if message.guild else None

                all_providers = ["gemini", "groq", "deepseek", "openrouter", "g4f"]
                if primary_provider in all_providers:
                    cascade_order = [primary_provider] + [p for p in all_providers if p != primary_provider]
                else:
                    cascade_order = ["gemini", "groq", "deepseek", "openrouter", "g4f"]

                for provider in cascade_order:
                    try:
                        if provider == "gemini":
                            ai_response = await ask_gemini(clean_prompt, message.channel.id, guild_id=guild_id)
                        elif provider == "groq":
                            ai_response = await ask_groq(clean_prompt, message.channel.id, guild_id=guild_id)
                        elif provider == "deepseek":
                            ai_response = await ask_deepseek(clean_prompt, message.channel.id, guild_id=guild_id)
                        elif provider == "openrouter":
                            ai_response = await ask_openrouter(clean_prompt, message.channel.id, guild_id=guild_id)
                        elif provider == "g4f":
                            ai_response = await ask_g4f_fallback(clean_prompt, message.channel.id, guild_id=guild_id)

                        if ai_response:
                            ai_response = strip_thinking_process(ai_response)
                            memory = get_chat_memory(message.channel.id)
                            memory.append({"role": "user", "content": clean_prompt})
                            memory.append({"role": "assistant", "content": ai_response})
                            CHAT_MEMORIES[message.channel.id] = memory[-10:]

                            chunks = split_message(ai_response, limit=1900)
                            
                            sent_msg = await message.reply(chunks[0])
                            for chunk in chunks[1:]:
                                sent_msg = await message.channel.send(chunk)
                            break
                    except Exception:
                        continue

                if not ai_response:
                    await message.reply("Ui da... Đầu óc em hơi chóng mặt xíu, oniichan chờ em một tẹo rồi hỏi tiếp nhé! 😭")

    async def handle_ai_moderation(self, message: discord.Message):
        try:
            if not message.guild or message.author.bot:
                return

            # Bỏ qua Admin và Bot Owners
            if message.author.guild_permissions.administrator:
                return
            if str(message.author.id) == owner_id or str(message.author.id) in subowner_id:
                return

            clean_text = message.content.strip()
            if not clean_text or len(clean_text) < 2:
                return

            # Bỏ qua nếu là lệnh hợp lệ của bot
            ctx = await self.bot.get_context(message)
            if ctx.valid:
                return

            system_data = get_system_data()
            if not system_data.get("moderation_enabled", True):
                return

            guild_mods = system_data.get("guild_moderation", {})
            if not guild_mods.get(str(message.guild.id), True):
                return

            raw_result = await call_moderation_api(clean_text)
            if not raw_result:
                return

            mod_result = parse_moderation_result(raw_result)
            is_violation = mod_result["violation"]
            severity = mod_result["severity"]
            reason = mod_result["reason"]

            mute_threshold = int(system_data.get("moderation_mute_threshold", 70))
            report_threshold = int(system_data.get("moderation_report_threshold", 25))

            if not is_violation and severity < report_threshold:
                return

            mute_duration = int(system_data.get("moderation_mute_duration", 10))

            # 1. MỨC ĐỘ CAO: TỰ ĐỘNG MUTE THÀNH VIÊN
            if severity >= mute_threshold:
                muted = False
                try:
                    duration = timedelta(minutes=mute_duration)
                    await message.author.timeout(duration, reason=f"AI Moderation ({severity}%): {reason}")
                    muted = True
                except discord.Forbidden:
                    muted = False
                except Exception as e:
                    print(f"[Mod Timeout Error]: {e}")
                    muted = False

                embed = discord.Embed(
                    title="🔇 [AI Moderation] Phát Hiện Ngôn Từ Xúc Phạm Nặng",
                    description=(
                        f"⚠️ Thành viên: {message.author.mention}\n"
                        f"📊 **Độ xúc phạm**: `{severity}%` *(Mức CAO)*\n"
                        f"⚖️ **Hình phạt**: " + (f"Tạm tắt tiếng (Mute) **{mute_duration} phút**" if muted else "Cảnh cáo (Bot thiếu quyền Mute thành viên)") + "\n"
                        f"📝 **Lý do**: {reason}\n\n"
                        "*Vui lòng chú ý ngôn từ và giữ gìn văn hóa máy chủ!*"
                    ),
                    color=discord.Color.red(),
                    timestamp=datetime.datetime.now(datetime.timezone.utc)
                )
                embed.set_footer(text=f"Model: {system_data.get('moderation_model', 'openai/gpt-oss-safeguard-20b')}")

                try:
                    await message.channel.send(embed=embed)
                except Exception:
                    pass

                try:
                    await message.delete()
                except Exception:
                    pass

                action_desc = f"Đã tự động Mute {mute_duration} phút & xóa tin" if muted else "Vi phạm mức cao (Chưa thể Mute do thiếu quyền)"
                await send_admin_report(message, severity, reason, action_taken=action_desc)

            # 2. MỨC ĐỘ THẤP: BÁO CÁO CHO ADMIN DUYỆT
            elif severity >= report_threshold or is_violation:
                await send_admin_report(message, severity, reason, action_taken="Cần Admin duyệt (Độ xúc phạm thấp)")

        except Exception as e:
            print(f"[Handle Moderation Exception]: {e}")

    @commands.hybrid_group(name="aimod", fallback="status", description="Hệ thống kiểm duyệt AI Moderation tiếng Việt")
    async def aimod_group(self, ctx):
        system_data = get_system_data()
        global_enabled = system_data.get("moderation_enabled", True)
        guild_mods = system_data.get("guild_moderation", {})
        guild_enabled = guild_mods.get(str(ctx.guild.id), global_enabled) if ctx.guild else global_enabled

        mod_model = system_data.get("moderation_model", "openai/gpt-oss-safeguard-20b")
        report_thresh = system_data.get("moderation_report_threshold", 25)
        mute_thresh = system_data.get("moderation_mute_threshold", 70)
        mute_duration = system_data.get("moderation_mute_duration", 10)

        admin_ch = get_admin_log_channel(ctx.guild) if ctx.guild else None
        ch_text = admin_ch.mention if admin_ch else "Chưa cài đặt (Tìm tự động theo tên mod-log/logs)"

        embed = discord.Embed(
            title="🛡️ BẢNG ĐIỀU KHIỂN AI MODERATION (TIẾNG VIỆT)",
            description=(
                f"⚙️ **Trạng thái máy chủ này**: `{'BẬT' if guild_enabled else 'TẮT'}`\n"
                f"🌐 **Trạng thái toàn cục**: `{'BẬT' if global_enabled else 'TẮT'}`\n"
                f"🧠 **Model kiểm duyệt**: `{mod_model}`\n"
                f"📍 **Kênh Mod-Log**: {ch_text}\n\n"
                f"**📊 Phân cấp xử lý độ xúc phạm:**\n"
                f"• 🟡 **Mức THẤP (`>= {report_thresh}%` và `< {mute_thresh}%`)**: Đem cho Admin duyệt (Kèm nút bấm tương tác Mute/Xóa/Cảnh cáo)\n"
                f"• 🔴 **Mức CAO (`>= {mute_thresh}%`)**: Tự động MUTE thành viên `{mute_duration} phút` và xóa tin nhắn\n"
                f"• 🟢 **An toàn (`< {report_thresh}%`)**: Bỏ qua\n\n"
                f"**📖 Các lệnh điều hành:**\n"
                f"• `/aimod toggle`: Bật/Tắt kiểm duyệt cho server\n"
                f"• `/aimod setchannel #kênh`: Đặt kênh nhận báo cáo cho Admin\n"
                f"• `/aimod setthreshold report: <%> mute: <%>`: Đặt ngưỡng độ xúc phạm\n"
                f"• `/aimod setduration minutes: <phút>`: Đặt thời gian tự động mute\n"
                f"• `/aimod test text: <nội dung>`: Thử nghiệm kiểm tra độ xúc phạm một câu"
            ),
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    @aimod_group.command(name="toggle", description="Bật hoặc tắt kiểm duyệt AI cho server này")
    @commands.has_permissions(administrator=True)
    async def aimod_toggle(self, ctx):
        if not ctx.guild:
            return await ctx.send("❌ Lệnh này chỉ dùng được trong server.")
        system_data = get_system_data()
        if "guild_moderation" not in system_data:
            system_data["guild_moderation"] = {}
        cur = system_data["guild_moderation"].get(str(ctx.guild.id), system_data.get("moderation_enabled", True))
        system_data["guild_moderation"][str(ctx.guild.id)] = not cur
        save_data(player_inventory)
        new_status = "BẬT" if not cur else "TẮT"
        await ctx.send(f"🛡️ Đã **{new_status}** tính năng AI Moderation cho máy chủ **{ctx.guild.name}**!")

    @aimod_group.command(name="setchannel", description="Đặt kênh nhận báo cáo xúc phạm cho Admin")
    @app_commands.describe(channel="Kênh văn bản nhận báo cáo kiểm duyệt")
    @commands.has_permissions(administrator=True)
    async def aimod_setchannel(self, ctx, channel: discord.TextChannel):
        if not ctx.guild:
            return await ctx.send("❌ Lệnh này chỉ dùng được trong server.")
        system_data = get_system_data()
        if "moderation_log_channels" not in system_data:
            system_data["moderation_log_channels"] = {}
        system_data["moderation_log_channels"][str(ctx.guild.id)] = channel.id
        save_data(player_inventory)
        await ctx.send(f"✅ Đã đặt kênh báo cáo AI Moderation thành {channel.mention}!")

    @aimod_group.command(name="setthreshold", description="Đặt ngưỡng % độ xúc phạm (Thấp -> Báo Admin, Cao -> Mute)")
    @app_commands.describe(report="Ngưỡng báo Admin (0-100%, mặc định 25)", mute="Ngưỡng tự động Mute (0-100%, mặc định 70)")
    @commands.has_permissions(administrator=True)
    async def aimod_setthreshold(self, ctx, report: int, mute: int):
        if not (0 <= report <= 100 and 0 <= mute <= 100 and report < mute):
            return await ctx.send("❌ Giá trị ngưỡng không hợp lệ! Yêu cầu: `0 <= report < mute <= 100`.")
        system_data = get_system_data()
        system_data["moderation_report_threshold"] = report
        system_data["moderation_mute_threshold"] = mute
        save_data(player_inventory)
        await ctx.send(f"✅ Đã cập nhật ngưỡng kiểm duyệt: Báo Admin khi `>= {report}%`, Tự động Mute khi `>= {mute}%`!")

    @aimod_group.command(name="setduration", description="Đặt thời gian tự động Mute (số phút)")
    @app_commands.describe(minutes="Số phút tắt tiếng (VD: 5, 10, 30, 60)")
    @commands.has_permissions(administrator=True)
    async def aimod_setduration(self, ctx, minutes: int):
        if minutes <= 0 or minutes > 40320:
            return await ctx.send("❌ Thời gian không hợp lệ (từ 1 đến 40320 phút).")
        system_data = get_system_data()
        system_data["moderation_mute_duration"] = minutes
        save_data(player_inventory)
        await ctx.send(f"✅ Đã đặt thời gian tự động Mute thành **{minutes} phút**!")

    @aimod_group.command(name="test", description="Thử nghiệm kiểm duyệt 1 câu với AI Moderation")
    @app_commands.describe(text="Nội dung cần kiểm tra độ xúc phạm")
    async def aimod_test(self, ctx, *, text: str):
        async with ctx.typing():
            raw_result = await call_moderation_api(text)
            if not raw_result:
                return await ctx.send("❌ Không nhận được phản hồi từ AI kiểm duyệt (hãy kiểm tra API keys trong file `.env`).")

            result = parse_moderation_result(raw_result)
            is_violation = result["violation"]
            severity = result["severity"]
            reason = result["reason"]

            system_data = get_system_data()
            report_thresh = int(system_data.get("moderation_report_threshold", 25))
            mute_thresh = int(system_data.get("moderation_mute_threshold", 70))
            mod_model = system_data.get("moderation_model", "openai/gpt-oss-safeguard-20b")

            if severity >= mute_thresh:
                action_text = "🚨 **HÀNH ĐỘNG DỰ KIẾN: TỰ ĐỘNG MUTE** (Độ xúc phạm mức CAO)"
                color = discord.Color.red()
            elif severity >= report_thresh or is_violation:
                action_text = "⚠️ **HÀNH ĐỘNG DỰ KIẾN: BÁO CÁO ADMIN DUYỆT** (Độ xúc phạm mức THẤP)"
                color = discord.Color.gold()
            else:
                action_text = "✅ **HÀNH ĐỘNG DỰ KIẾN: BỎ QUA** (Nội dung an toàn)"
                color = discord.Color.green()

            embed = discord.Embed(
                title="🧪 KẾT QUẢ TEST AI MODERATION",
                color=color,
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            embed.add_field(name="💬 Nội dung test", value=f"\"{text}\"", inline=False)
            embed.add_field(name="🚨 VIOLATION", value=f"`{is_violation}`", inline=True)
            embed.add_field(name="📊 SEVERITY (% Xúc phạm)", value=f"`{severity}%`", inline=True)
            embed.add_field(name="📝 REASON (Lý do)", value=f"{reason}", inline=False)
            embed.add_field(name="⚖️ Đánh giá hệ thống", value=action_text, inline=False)
            embed.set_footer(text=f"Model: {mod_model} • Test Mode")
            await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="cswitching", 
        aliases=["ngucanh"], 
        description="Chuyển đổi file tri thức/ngữ cảnh AI cho máy chủ hiện tại (Chỉ Admin)"
    )
    @app_commands.describe(
        server_id="ID của máy chủ Discord", 
        file_yaml="Tên file cấu hình YAML (mặc định char.yml)"
    )
    async def pcswitching(self, ctx, server_id: str = None, file_yaml: str = "char.yml"):
        if str(ctx.author.id) != owner_id and str(ctx.author.id) not in subowner_id:
            return await ctx.send("🚫 Bạn không có quyền dùng lệnh này.", ephemeral=True)

        if not server_id:
            return await ctx.send("💡 Cách dùng: `/cswitching server_id: <id_server> file_yaml: <file_yaml>`")

        if not (file_yaml.endswith(".yml") or file_yaml.endswith(".yaml")):
            return await ctx.send("❌ Hệ thống chỉ chấp nhận định dạng file `.yml` hoặc `.yaml` thôi!")

        system_data = get_system_data()
        if "server_knowledge_files" not in system_data:
            system_data["server_knowledge_files"] = {}

        system_data["server_knowledge_files"][str(server_id)] = file_yaml
        save_data(player_inventory)

        await ctx.send(f"✅ Đã chuyển đổi ngữ cảnh server `{server_id}` sang file cấu hình `{file_yaml}` thành công!")

    @commands.hybrid_command(
        name="clear", 
        aliases=["clearcontext", "cc"], 
        description="Xóa sạch lịch sử trò chuyện (memory) của AI trong kênh này"
    )
    async def clear_context(self, ctx):
        clear_chat_memory(ctx.channel.id)
        await ctx.send("🧹 **Oniichan!** Em đã dọn dẹp sạch sẽ lịch sử trò chuyện trong kênh này rồi đó! ✨")

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
        description="Tải lại (reload) Cog AI để cập nhật tính năng (Chỉ Admin)"
    )
    @app_commands.describe(extension="Tên Cog muốn reload (mặc định: AIphcbot)")
    async def reload_cogs(self, ctx, extension: str = None):
        if str(ctx.author.id) != owner_id and str(ctx.author.id) not in subowner_id:
            return await ctx.send("🚫 Bạn không có quyền dùng lệnh này.", ephemeral=True)

        extensions = ['AIphcbot']

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
        name="aimod_panel", 
        aliases=["modai"],
        description="Bảng điều khiển hệ thống AI & AI Moderation (Chỉ Admin)"
    )
    @app_commands.describe(
        action="Hành động: ai, bl, aimod, modlog, modthresh, modduration",
        args_str="Tham số chi tiết"
    )
    async def mod(self, ctx, action: str = None, *, args_str: str = None):
        if str(ctx.author.id) != owner_id and str(ctx.author.id) not in subowner_id:
            return await ctx.send("🚫 Bạn không có quyền dùng lệnh này.", ephemeral=True)

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
                    return await ctx.send("❌ Cú pháp sai! Dùng: `/mod action: bl args_str: add <regex> | <câu thoại>`")
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

        if action and action.lower() == "aimod":
            system_data = get_system_data()
            if not args_str:
                cur = system_data.get("moderation_enabled", True)
                system_data["moderation_enabled"] = not cur
                save_data(player_inventory)
                return await ctx.send(f"🛡️ Đã {'BẬT' if not cur else 'TẮT'} tính năng AI Moderation toàn cục!")
            if args_str.lower() in ("on", "bat", "enable"):
                system_data["moderation_enabled"] = True
                save_data(player_inventory)
                return await ctx.send("🛡️ Đã BẬT AI Moderation toàn cục!")
            elif args_str.lower() in ("off", "tat", "disable"):
                system_data["moderation_enabled"] = False
                save_data(player_inventory)
                return await ctx.send("🛡️ Đã TẮT AI Moderation toàn cục!")
            else:
                return await ctx.send("❌ Dùng: `/mod action: aimod args_str: <on|off>`")

        if action and action.lower() == "modlog":
            if not args_str:
                return await ctx.send("❌ Dùng: `/mod action: modlog args_str: <#kênh hoặc ID_kênh>`")
            cid = args_str.strip().replace("<#", "").replace(">", "")
            try:
                ch = ctx.guild.get_channel(int(cid)) if ctx.guild else None
                if not ch:
                    return await ctx.send("❌ Không tìm thấy kênh chỉ định.")
                system_data = get_system_data()
                if "moderation_log_channels" not in system_data:
                    system_data["moderation_log_channels"] = {}
                system_data["moderation_log_channels"][str(ctx.guild.id)] = ch.id
                save_data(player_inventory)
                return await ctx.send(f"✅ Đã đặt kênh Mod-Log cho AI Moderation thành {ch.mention}!")
            except Exception as e:
                return await ctx.send(f"❌ Lỗi: `{e}`")

        if action and action.lower() == "modthresh":
            if not args_str:
                return await ctx.send("❌ Dùng: `/mod action: modthresh args_str: <ngưỡng_báo_admin> <ngưỡng_mute>`")
            parts = args_str.split()
            if len(parts) < 2:
                return await ctx.send("❌ Cần nhập 2 số (Ví dụ: `25 70`).")
            try:
                rep_val, mute_val = int(parts[0]), int(parts[1])
                if not (0 <= rep_val <= 100 and 0 <= mute_val <= 100 and rep_val < mute_val):
                    return await ctx.send("❌ Ngưỡng không hợp lệ (0 <= report < mute <= 100).")
                system_data = get_system_data()
                system_data["moderation_report_threshold"] = rep_val
                system_data["moderation_mute_threshold"] = mute_val
                save_data(player_inventory)
                return await ctx.send(f"✅ Đã cập nhật: Báo Admin khi `>= {rep_val}%`, Mute khi `>= {mute_val}%`!")
            except ValueError:
                return await ctx.send("❌ Vui lòng nhập số nguyên hợp lệ.")

        if action and action.lower() == "modduration":
            if not args_str:
                return await ctx.send("❌ Dùng: `/mod action: modduration args_str: <số_phút>`")
            try:
                mins = int(args_str.strip())
                if mins <= 0:
                    return await ctx.send("❌ Số phút phải lớn hơn 0.")
                system_data = get_system_data()
                system_data["moderation_mute_duration"] = mins
                save_data(player_inventory)
                return await ctx.send(f"✅ Đã đặt thời gian Mute tự động thành {mins} phút!")
            except ValueError:
                return await ctx.send("❌ Vui lòng nhập số phút hợp lệ.")

        embed = discord.Embed(title="📘 Hướng dẫn sử dụng lệnh /aimod_panel", color=discord.Color.blue())
        embed.add_field(name="Cấu hình hệ thống AI", value="`/aimod_panel action: ai`", inline=False)
        embed.add_field(name="Quản lý Blacklist AI", value="`/aimod_panel action: bl`", inline=False)
        embed.add_field(name="Bật/Tắt AI Moderation", value="`/aimod_panel action: aimod args_str: on/off`", inline=False)
        embed.add_field(name="Đặt kênh Mod-Log", value="`/aimod_panel action: modlog args_str: #kênh`", inline=False)
        embed.add_field(name="Đặt ngưỡng kiểm duyệt", value="`/aimod_panel action: modthresh args_str: 25 70`", inline=False)
        embed.add_field(name="Đặt thời gian Mute", value="`/aimod_panel action: modduration args_str: 10`", inline=False)
        return await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(AIphcbotCog(bot))