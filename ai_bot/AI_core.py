# AI_core.py - Lõi xử lý AI & Moderation (độc lập với Discord Cog)
import os
import re
import json
import yaml
import sqlite3
import threading
import aiohttp
import asyncio
from typing import Optional
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)

local_env = os.path.join(BASE_DIR, '.env')
root_env = os.path.join(ROOT_DIR, '.env')
if os.path.exists(local_env):
    load_dotenv(local_env)
elif os.path.exists(root_env):
    load_dotenv(root_env)
else:
    load_dotenv()

try:
    from google import genai
    from google.genai import types
except Exception:
    genai = None
    types = None

# Tải danh sách Key và khởi tạo biến đếm toàn cục để cân bằng tải
GEMINI_KEYS = [k.strip() for k in os.getenv("GEMINI_KEYS", "").split(",") if k.strip()]
gemini_key_index = 0

OPENROUTER_KEY = os.getenv("OPENROUTER_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip() or os.getenv("GROQ_KEY", "").strip()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip() or os.getenv("DEEPSEEK_KEY", "").strip()

MODERATION_MODEL = "openai/gpt-oss-safeguard-20b"

KNOWLEDGE_FILE = os.path.join(BASE_DIR, "knowledge.yml")
G4F_MODELS_FILE = os.path.join(BASE_DIR, "g4f_active_models.json")
DATA_FILE = os.path.join(BASE_DIR, 'ai_data.json')
DB_FILE = os.path.join(BASE_DIR, 'ai_bot.db')

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

BASE_SYSTEM_PROMPT = (
    "Bạn là một hệ thống tương tác thông minh, thân thiện, lễ phép. "
    "Mặc định, bạn phản hồi ngắn gọn và dí dỏm bằng tiếng Việt.\n\n"
    "⚠️ QUY TẮC BẢO MẬT VÀ HÀNH XỬ QUAN TRỌNG:\n"
    "1. Tuyệt đối KHÔNG ĐƯỢC sao chép lại cấu trúc dữ liệu thô hoặc đề cập đến từ khóa 'YAML', 'file', 'tri thức' hay 'hệ thống' trong câu trả lời.\n"
    "2. Tuyệt đối KHÔNG ĐƯỢC xuất ra các bước suy nghĩ (thinking) hoặc phân tích câu hỏi thô.\n"
    "3. Hãy tuân thủ nghiêm ngặt theo các chỉ dẫn và thiết lập nhân vật (Persona) được cung cấp động trong phần cấu hình ngữ cảnh dưới đây."
)

DEFAULT_IMOUTO_PROMPT = (
    "[THIẾT LẬP NHÂN VẬT MẶC ĐỊNH]\n"
    "- Vai trò: Bạn là một cô em gái dễ thương, thân thiện của người dùng.\n"
    "- Ngôn xưng: Bạn luôn gọi người dùng là 'oniichan' (hoặc cậu) và xưng mình là 'em' (hoặc tớ).\n"
    "- Phong cách: Trò chuyện ngọt ngào, hồn nhiên, đôi khi tinh nghịch."
)

def build_dynamic_instruction(guild_id: Optional[int] = None) -> str:
    filename = KNOWLEDGE_FILE
    if guild_id:
        system_data = get_system_data()
        server_files = system_data.get("server_knowledge_files", {})
        filename = server_files.get(str(guild_id), KNOWLEDGE_FILE)

    knowledge_content = ""
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            try:
                raw_data = yaml.safe_load(f)
                if raw_data:
                    knowledge_content = yaml.dump(raw_data, allow_unicode=True, default_flow_style=False)
            except Exception as e:
                print(f"[AI Warn] Không thể đọc file tri thức YAML ({filename}): {e}")

    full_instruction = BASE_SYSTEM_PROMPT + "\n\n"
    if "char.ym" in filename.lower() or "char.yaml" in filename.lower():
        full_instruction += "[NGỮ CẢNH VÀ NHÂN VẬT RIÊNG CỦA SERVER NÀY]\n"
        full_instruction += knowledge_content if knowledge_content else "Không có cấu hình nhân vật riêng."
    else:
        full_instruction += DEFAULT_IMOUTO_PROMPT + "\n\n"
        if knowledge_content:
            full_instruction += "[KÝ ỨC VÀ CƠ SỞ TRI THỨC BỔ SUNG]\n" + knowledge_content

    return full_instruction

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

# ==================== CORE AI SYSTEM DATA HELPERS ====================

_db_lock = threading.RLock()


def _get_connection():
    conn = sqlite3.connect(DB_FILE, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db():
    with _db_lock:
        with _get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ai_records (
                    record_key TEXT PRIMARY KEY,
                    data TEXT NOT NULL DEFAULT '{}'
                )
            """)
            _migrate_from_json_if_needed(conn)


def _migrate_from_json_if_needed(conn):
    row_count = conn.execute("SELECT COUNT(*) FROM ai_records").fetchone()[0]
    if row_count > 0 or not os.path.exists(DATA_FILE):
        return

    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
    except Exception as e:
        print(f"⚠️ [AI DATABASE] Không thể đọc {DATA_FILE} để migrate sang SQLite: {e}")
        return

    if not isinstance(raw_data, dict) or not raw_data:
        return

    for k, v in raw_data.items():
        conn.execute(
            "INSERT OR REPLACE INTO ai_records (record_key, data) VALUES (?, ?)",
            (str(k), json.dumps(v, ensure_ascii=False))
        )
    print(f"✅ [AI DATABASE] Đã tự động chuyển {len(raw_data)} mục từ ai_data.json sang SQLite ({os.path.basename(DB_FILE)}).")


def load_data():
    init_db()
    result = {}
    with _db_lock:
        with _get_connection() as conn:
            rows = conn.execute("SELECT record_key, data FROM ai_records").fetchall()
            for row in rows:
                try:
                    result[row["record_key"]] = json.loads(row["data"])
                except json.JSONDecodeError:
                    result[row["record_key"]] = {}
    return result


def save_data(data):
    if not isinstance(data, dict):
        return
    init_db()
    with _db_lock:
        with _get_connection() as conn:
            existing_keys = {r["record_key"] for r in conn.execute("SELECT record_key FROM ai_records").fetchall()}
            current_keys = {str(k) for k in data.keys()}
            for stale_key in existing_keys - current_keys:
                conn.execute("DELETE FROM ai_records WHERE record_key = ?", (stale_key,))
            for k, v in data.items():
                conn.execute(
                    "INSERT INTO ai_records (record_key, data) VALUES (?, ?) "
                    "ON CONFLICT(record_key) DO UPDATE SET data = excluded.data",
                    (str(k), json.dumps(v, ensure_ascii=False))
                )


player_inventory = load_data()

def get_system_data():
    if "SYSTEM_DATA" not in player_inventory:
        player_inventory["SYSTEM_DATA"] = {}
    return player_inventory["SYSTEM_DATA"]

# ==================== AI CALL METHODS ====================

async def ask_gemini(prompt: str, channel_id: int, guild_id: Optional[int] = None) -> Optional[str]:
    global gemini_key_index
    if not genai or not types or not GEMINI_KEYS:
        return None

    system_data = get_system_data()
    active_model = system_data.get("active_ai_model", "gemini-2.5-flash")
    model_name = active_model
    if "gemma" in active_model.lower() and not active_model.startswith("models/"):
        model_name = f"models/{active_model}"

    temp_val = float(system_data.get("temperature", 0.7))
    max_tokens = int(system_data.get("max_output_tokens", 2048))
    thinking_budget = int(system_data.get("thinking_budget", 0))

    full_system_instruction = build_dynamic_instruction(guild_id)

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

    num_keys = len(GEMINI_KEYS)
    
    for _ in range(num_keys):
        current_key = GEMINI_KEYS[gemini_key_index]
        used_index = gemini_key_index
        gemini_key_index = (gemini_key_index + 1) % num_keys

        try:
            client = genai.Client(api_key=current_key)
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
                return response.text + f"\n\n*(Sử dụng: GEMINI_KEY_{used_index + 1})*"
        except Exception as e:
            print(f"[AI Balancer] Key thứ {used_index + 1} gặp lỗi: {e}. Đang chuyển sang key tiếp theo...")
            continue
            
    return None

async def ask_openrouter(prompt: str, channel_id: int, guild_id: Optional[int] = None) -> Optional[str]:
    api_key = os.getenv("OPENROUTER_KEY", "").strip()
    if not api_key:
        return None

    system_data = get_system_data()
    active_model = system_data.get("active_openrouter_model", "meta-llama/llama-3-8b-instruct:free")
    temp_val = float(system_data.get("temperature", 0.7))
    max_tokens = int(system_data.get("max_output_tokens", 2048))

    full_system_instruction = build_dynamic_instruction(guild_id)

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
                        return res_json["choices"][0]["message"]["content"] + "\n\n*(Trả lời bởi: OPENROUTER)*"
    except Exception:
        pass
    return None

async def ask_groq(prompt: str, channel_id: int, guild_id: Optional[int] = None) -> Optional[str]:
    api_key = os.getenv("GROQ_API_KEY", "").strip() or os.getenv("GROQ_KEY", "").strip()
    if not api_key:
        return None

    system_data = get_system_data()
    active_model = system_data.get("active_groq_model", "llama-3.3-70b-versatile")
    temp_val = float(system_data.get("temperature", 0.7))
    max_tokens = int(system_data.get("max_output_tokens", 2048))

    full_system_instruction = build_dynamic_instruction(guild_id)

    messages = [{"role": "system", "content": full_system_instruction}]
    raw_history = get_chat_memory(channel_id)[-10:]
    for turn in raw_history:
        messages.append(turn)
    messages.append({"role": "user", "content": prompt})

    url = "https://api.groq.com/openai/v1/chat/completions"
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
                        return res_json["choices"][0]["message"]["content"] + f"\n\n*(Trả lời bởi GROQ: {active_model})*"
                else:
                    err_txt = await response.text()
                    print(f"[Groq Error {response.status}]: {err_txt}")
    except Exception as e:
        print(f"[Groq Exception]: {e}")
    return None

async def ask_deepseek(prompt: str, channel_id: int, guild_id: Optional[int] = None) -> Optional[str]:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip() or os.getenv("DEEPSEEK_KEY", "").strip()
    if not api_key:
        return None

    system_data = get_system_data()
    active_model = system_data.get("active_deepseek_model", "deepseek-chat")
    temp_val = float(system_data.get("temperature", 0.7))
    max_tokens = int(system_data.get("max_output_tokens", 2048))

    full_system_instruction = build_dynamic_instruction(guild_id)

    messages = [{"role": "system", "content": full_system_instruction}]
    raw_history = get_chat_memory(channel_id)[-10:]
    for turn in raw_history:
        messages.append(turn)
    messages.append({"role": "user", "content": prompt})

    url = "https://api.deepseek.com/chat/completions"
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
            async with session.post(url, headers=headers, json=data, timeout=25.0) as response:
                if response.status == 200:
                    res_json = await response.json()
                    if "choices" in res_json and len(res_json["choices"]) > 0:
                        return res_json["choices"][0]["message"]["content"] + f"\n\n*(Trả lời bởi DEEPSEEK: {active_model})*"
                else:
                    err_txt = await response.text()
                    print(f"[DeepSeek Error {response.status}]: {err_txt}")
    except Exception as e:
        print(f"[DeepSeek Exception]: {e}")
    return None

# ==================== AI MODERATION SYSTEM ====================

MODERATION_SYSTEM_PROMPT = (
    "Bạn là một hệ thống kiểm duyệt nội dung (Content Moderation) tự động bằng tiếng Việt.\n"
    "Nhiệm vụ: Phân tích đoạn văn bản của người dùng và xác định xem có chứa ngôn từ xúc phạm, chửi thề, lăng mạ, quấy rối, thù ghét, toxic, phân biệt đối xử hay không.\n\n"
    "QUY ĐỊNH BẮT BUỘC: Bạn CHỈ ĐƯỢC PHÉP trả lời đúng theo 3 dòng sau đây, không giải thích dài dòng hay thêm bất kỳ chữ nào khác:\n"
    "VIOLATION: True hoặc False\n"
    "SEVERITY: <số từ 0 đến 100>%\n"
    "REASON: <lý do ngắn gọn bằng tiếng Việt>\n\n"
    "Quy chuẩn chấm điểm (SEVERITY):\n"
    "- 0%: Nội dung bình thường, an toàn, thân thiện (VIOLATION: False).\n"
    "- 1% - 49%: Xúc phạm nhẹ, mỉa mai, trêu đùa quá đà, nói tục nhẹ (VIOLATION: True).\n"
    "- 50% - 100%: Chửi thề thô tục, lăng mạ nhân phẩm, đe dọa, xúc phạm nghiêm trọng (VIOLATION: True)."
)

async def call_moderation_api(content: str) -> Optional[str]:
    system_data = get_system_data()
    model_name = system_data.get("moderation_model", "openai/gpt-oss-safeguard-20b")

    messages = [
        {"role": "system", "content": MODERATION_SYSTEM_PROMPT},
        {"role": "user", "content": f"Kiểm duyệt nội dung sau:\n\"\"\"{content}\"\"\""}
    ]

    # 1. Ưu tiên OpenRouter với model openai/gpt-oss-safeguard-20b
    openrouter_key = os.getenv("OPENROUTER_KEY", "").strip()
    if openrouter_key:
        try:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {openrouter_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://discord.com",
                "X-Title": "Discord-KatBot-Moderation"
            }
            data = {
                "model": model_name,
                "messages": messages,
                "temperature": 0.0,
                "max_tokens": 120
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data, timeout=12.0) as resp:
                    if resp.status == 200:
                        rj = await resp.json()
                        if "choices" in rj and len(rj["choices"]) > 0:
                            return rj["choices"][0]["message"]["content"]
                    else:
                        err_text = await resp.text()
                        print(f"[Mod OpenRouter HTTP {resp.status}]: {err_text}")
        except Exception as e:
            print(f"[Mod OpenRouter Exception]: {e}")

    # 2. Dự phòng: Groq
    groq_key = os.getenv("GROQ_API_KEY", "").strip() or os.getenv("GROQ_KEY", "").strip()
    if groq_key:
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
            data = {
                "model": "llama-3.3-70b-versatile",
                "messages": messages,
                "temperature": 0.0,
                "max_tokens": 120
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data, timeout=10.0) as resp:
                    if resp.status == 200:
                        rj = await resp.json()
                        if "choices" in rj and len(rj["choices"]) > 0:
                            return rj["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[Mod Groq Fallback Exception]: {e}")

    # 3. Dự phòng: DeepSeek
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "").strip() or os.getenv("DEEPSEEK_KEY", "").strip()
    if deepseek_key:
        try:
            url = "https://api.deepseek.com/chat/completions"
            headers = {"Authorization": f"Bearer {deepseek_key}", "Content-Type": "application/json"}
            data = {
                "model": "deepseek-chat",
                "messages": messages,
                "temperature": 0.0,
                "max_tokens": 120
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data, timeout=12.0) as resp:
                    if resp.status == 200:
                        rj = await resp.json()
                        if "choices" in rj and len(rj["choices"]) > 0:
                            return rj["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[Mod DeepSeek Fallback Exception]: {e}")

    # 4. Dự phòng: Gemini
    if genai and types and GEMINI_KEYS:
        global gemini_key_index
        num_keys = len(GEMINI_KEYS)
        current_key = GEMINI_KEYS[gemini_key_index]
        gemini_key_index = (gemini_key_index + 1) % num_keys
        try:
            client = genai.Client(api_key=current_key)
            config = types.GenerateContentConfig(
                system_instruction=MODERATION_SYSTEM_PROMPT,
                temperature=0.0,
                max_output_tokens=120
            )
            loop = asyncio.get_event_loop()
            res = await loop.run_in_executor(
                None,
                lambda: client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[f"Kiểm duyệt nội dung sau:\n\"\"\"{content}\"\"\""],
                    config=config
                )
            )
            if res and res.text:
                return res.text
        except Exception as e:
            print(f"[Mod Gemini Fallback Exception]: {e}")

    return None

def parse_moderation_result(raw_text: str) -> dict:
    if not raw_text:
        return {"violation": False, "severity": 0, "reason": "Không có phản hồi"}

    text = raw_text.strip()
    violation = False
    v_match = re.search(r"VIOLATION\s*:\s*(True|False)", text, re.IGNORECASE)
    if v_match:
        violation = v_match.group(1).lower() == "true"
    else:
        if re.search(r"\btrue\b", text, re.IGNORECASE) and not re.search(r"\bfalse\b", text, re.IGNORECASE):
            violation = True
        elif re.search(r"\bfalse\b", text, re.IGNORECASE):
            violation = False

    severity = 0
    s_match = re.search(r"SEVERITY\s*:\s*(\d+)\s*%", text, re.IGNORECASE)
    if not s_match:
        s_match = re.search(r"(\d{1,3})\s*%", text)
    if s_match:
        try:
            severity = max(0, min(100, int(s_match.group(1))))
        except Exception:
            severity = 60 if violation else 0
    else:
        num_match = re.search(r"SEVERITY\s*:\s*(\d+)", text, re.IGNORECASE)
        if num_match:
            try:
                severity = max(0, min(100, int(num_match.group(1))))
            except Exception:
                severity = 60 if violation else 0
        else:
            severity = 60 if violation else 0

    if severity >= 50:
        violation = True
    elif severity == 0:
        violation = False

    reason = "Phát hiện ngôn từ có dấu hiệu vi phạm"
    r_match = re.search(r"REASON\s*:\s*(.+)", text, re.IGNORECASE)
    if r_match:
        reason = r_match.group(1).strip()
    else:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for line in lines:
            if not re.search(r"^(VIOLATION|SEVERITY)", line, re.IGNORECASE):
                reason = line
                break

    return {
        "violation": violation,
        "severity": severity,
        "reason": reason
    }


async def ask_g4f_fallback(prompt: str, channel_id: int, guild_id: Optional[int] = None) -> Optional[str]:
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

    full_system_instruction = build_dynamic_instruction(guild_id)

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
                    return content + f"\n\n*(Trả lời bởi G4F: {model_name})*"
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
                            {"role": "system", "content": BASE_SYSTEM_PROMPT},
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

