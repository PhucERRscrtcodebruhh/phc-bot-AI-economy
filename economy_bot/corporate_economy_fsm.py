# economy_bot/corporate_economy_fsm.py
"""Corporate Organization FSM, Marxian Political Economy Simulation & Hostile Takeover Engine."""

from __future__ import annotations

import datetime
import math
import os
import random
import re
import uuid
from typing import Any, Optional

import aiosqlite
import discord
from discord import app_commands, ui
from discord.ext import commands


# ==============================================================================
# 1. CONSTANTS & DOMAIN CONFIGURATION
# ==============================================================================

PAR_VALUE = 10_000
IPO_FEE = 100_000_000
POISON_PILL_COST = 50_000_000
REPAIR_COST_PER_10_PCT = 5_000
MAX_STRIKE_EXPLOITATION_THRESHOLD = 5.0

COMPANY_FSM_TRANSITIONS: dict[str, list[str]] = {
    "ACTIVE": ["DELINQUENT", "ON_STRIKE", "UNDER_TAKEOVER", "PRE_IPO", "DISSOLVED"],
    "DELINQUENT": ["ACTIVE", "ON_STRIKE", "UNDER_TAKEOVER", "DISSOLVED"],
    "ON_STRIKE": ["ACTIVE", "DELINQUENT", "DISSOLVED"],
    "UNDER_TAKEOVER": ["ACTIVE", "DISSOLVED"],
    "PRE_IPO": ["PUBLIC_LISTED", "ACTIVE", "DISSOLVED"],
    "PUBLIC_LISTED": ["DELINQUENT", "ON_STRIKE", "UNDER_TAKEOVER", "DISSOLVED"],
    "DISSOLVED": [],
}

FSM_DISPLAY: dict[str, tuple[str, discord.Color]] = {
    "ACTIVE": ("🟢 HOẠT ĐỘNG BÌNH THƯỜNG (ACTIVE)", discord.Color.green()),
    "DELINQUENT": ("🟠 NỢ LƯƠNG / MẤT THANH KHOẢN (DELINQUENT)", discord.Color.orange()),
    "ON_STRIKE": ("🔴 ĐÌNH CÔNG TẬP THỂ (ON_STRIKE)", discord.Color.red()),
    "UNDER_TAKEOVER": ("🟣 ĐANG BỊ THÂU TÓM THÙ ĐỊCH (UNDER_TAKEOVER)", discord.Color.purple()),
    "PRE_IPO": ("🔵 TIỀN NIÊM YẾT IPO (PRE_IPO)", discord.Color.blue()),
    "PUBLIC_LISTED": ("🟡 ĐẠI CHÚNG NIÊM YẾT (PUBLIC_LISTED)", discord.Color.gold()),
    "DISSOLVED": ("⚫ ĐÃ GIẢI THỂ (DISSOLVED)", discord.Color.dark_grey()),
}

LEGAL_MODELS: dict[str, str] = {
    "TNHH_1TV": "Công ty TNHH Một Thành Viên",
    "TNHH_2TV": "Công ty TNHH Hai Thành Viên trở lên",
    "CTCP": "Công ty Cổ Phần (CTCP)",
}

SCALE_INFO: dict[str, dict[str, Any]] = {
    "SME": {
        "name": "Doanh Nghiệp Vừa & Nhỏ (SME)",
        "min_capital": 100_000_000,
        "max_capital": 200_000_000,
        "allowed_models": ("TNHH_1TV",),
        "license_tax_rate": 0.05,
    },
    "ENTERPRISE": {
        "name": "Tập Đoàn / Doanh Nghiệp Lớn (ENTERPRISE)",
        "min_capital": 1_000_000_000,
        "max_capital": 2_000_000_000,
        "allowed_models": ("TNHH_1TV", "TNHH_2TV", "CTCP"),
        "license_tax_rate": 0.03,
    },
}

INDUSTRY_INFO: dict[str, dict[str, Any]] = {
    "FOOD": {
        "name": "Ẩm Thực & Đồ Uống (F&B)",
        "raw_cost": 10_000,
        "depreciation": 2_000,
        "surplus_mult": 0.6,
        "settlement": "IMMEDIATE",
        "net_minutes": 0,
        "labor_type": "MANUAL_LABOR",
        "requires_intellectual": False,
        "intellectual_bonus_mult": 1.0,
        "facility_type": "FOOD_KITCHEN",
    },
    "TECH": {
        "name": "Công Nghệ Phần Mềm / AI (SaaS/AI)",
        "raw_cost": 25_000,
        "depreciation": 1_000,
        "surplus_mult": 3.0,
        "settlement": "IMMEDIATE",
        "net_minutes": 0,
        "labor_type": "INTELLECTUAL_LABOR",
        "requires_intellectual": True,
        "intellectual_bonus_mult": 1.0,
        "facility_type": "TECH_LAB",
    },
    "LIGHT_IND": {
        "name": "Công Nghiệp Nhẹ (Dệt May / Da Giày)",
        "raw_cost": 15_000,
        "depreciation": 2_000,
        "surplus_mult": 1.2,
        "settlement": "NET_60",
        "net_minutes": 60,
        "labor_type": "MANUAL_LABOR",
        "requires_intellectual": False,
        "intellectual_bonus_mult": 1.0,
        "facility_type": "LIGHT_FACTORY",
    },
    "HEAVY_IND": {
        "name": "Công Nghiệp Nặng (Luyện Kim / Cơ Khí)",
        "raw_cost": 40_000,
        "depreciation": 5_000,
        "surplus_mult": 2.5,
        "settlement": "NET_90",
        "net_minutes": 90,
        "labor_type": "HYBRID",
        "requires_intellectual": False,
        "intellectual_bonus_mult": 2.0,
        "facility_type": "HEAVY_PLANT",
    },
}

EXAM_QUESTION_BANK: list[dict[str, Any]] = [
    {
        "question": "Trong công thức giá trị hàng hóa Mác-xít W = c + v + m, ký hiệu 'c' biểu thị cho thành phần nào?",
        "options": [
            "Tư bản bất biến (chi phí nguyên vật liệu và khấu hao tư liệu sản xuất)",
            "Tư bản khả biến (tiền lương trả cho người lao động)",
            "Giá trị thặng dư thu được sau chu kỳ sản xuất",
            "Thuế môn bài doanh nghiệp nộp cho Nhà nước",
        ],
        "answer_index": 0,
        "explanation": "c (Constant Capital) gồm giá trị nguyên vật liệu và khấu hao máy móc chuyển dịch vào sản phẩm.",
    },
    {
        "question": "Tỷ suất giá trị thặng dư (tỷ suất bóc lột) m' được tính theo công thức nào?",
        "options": [
            "m' = c / v",
            "m' = m / v",
            "m' = v / (c + m)",
            "m' = (c + v) / m",
        ],
        "answer_index": 1,
        "explanation": "Tỷ suất giá trị thặng dư phản ánh mức độ bóc lột sức lao động: m' = m / v.",
    },
    {
        "question": "Theo quy định pháp lý mô phỏng, mô hình doanh nghiệp nào được phép thực hiện IPO và bị chào mua thù địch (Raid)?",
        "options": [
            "TNHH Một Thành Viên (TNHH_1TV)",
            "TNHH Hai Thành Viên (TNHH_2TV)",
            "Công Ty Cổ Phần (CTCP)",
            "Hộ kinh doanh cá thể",
        ],
        "answer_index": 2,
        "explanation": "Chỉ Công ty Cổ Phần (CTCP) mới có quyền niêm yết đại chúng (IPO) và giao dịch cổ phần mở.",
    },
    {
        "question": "Cơ chế thanh toán Net 60 / Net 90 trong công nghiệp nhẹ và nặng có ý nghĩa tài chính gì?",
        "options": [
            "Doanh thu được cộng trực tiếp ngay lập tức vào Két Công Ty",
            "Doanh thu bị treo thành khoản phải thu có kỳ hạn (60 hoặc 90 phút thực) trước khi đối soát thành tiền mặt",
            "Nhân viên phải làm việc không lương trong 60 hoặc 90 ngày",
            "Doanh nghiệp được miễn thuế môn bài trong 60 hoặc 90 ngày",
        ],
        "answer_index": 1,
        "explanation": "Net 60/90 tạo rủi ro dòng tiền: công ty có lãi trên sổ sách nhưng có thể thiếu tiền mặt trả lương đúng hạn.",
    },
    {
        "question": "Trong ngành HEAVY_IND, người lao động có chứng chỉ INTELLECTUAL_LABOR (Kỹ Sư Trưởng) tạo ra tác động gì?",
        "options": [
            "Giảm 50% chi phí nguyên vật liệu",
            "Nhân đôi hệ số thặng dư (2.0x) cho ca sản xuất",
            "Biến thanh toán Net 90 thành thanh toán tức thì",
            "Miễn hoàn toàn hao mòn độ bền máy móc",
        ],
        "answer_index": 1,
        "explanation": "Kỹ Sư Trưởng mang lại hệ số thưởng 2.0x lên surplus_mult trong ngành Công nghiệp Nặng.",
    },
    {
        "question": "Chiến lược phòng vệ 'Thuốc Độc' (Poison Pill) trong M&A hoạt động như thế nào?",
        "options": [
            "Tự động giải thể công ty để xóa toàn bộ cổ phần",
            "Chi 50,000,000 gold từ Két để pha loãng cổ phần không thuộc Raider lên 1.5x, đẩy lùi cuộc thâu tóm",
            "Cắt toàn bộ tiền lương nhân viên để tăng dự trữ Két",
            "Chuyển toàn bộ nợ phải thu thành tiền mặt ngay lập tức",
        ],
        "answer_index": 1,
        "explanation": "Poison Pill làm pha loãng tỷ lệ sở hữu của Raider, hoàn trả escrow còn lại và khôi phục trạng thái ACTIVE.",
    },
    {
        "question": "Khi Két Công Ty không đủ tiền trả lương 'v' cho người lao động sau ca làm việc, hệ thống FSM chuyển sang trạng thái nào?",
        "options": [
            "PRE_IPO",
            "PUBLIC_LISTED",
            "DELINQUENT",
            "DISSOLVED",
        ],
        "answer_index": 2,
        "explanation": "Mất thanh khoản trả lương kích hoạt ghi nợ lương và chuyển doanh nghiệp sang DELINQUENT.",
    },
    {
        "question": "Quyền hạn 'Hoán Đổi Nợ - Cổ Phần' (Debt-to-Equity Swap) thuộc về ai và làm thay đổi bảng cân đối ra sao?",
        "options": [
            "Chủ nợ chuyển khoản gốc nợ quá hạn chưa thanh toán thành cổ phần phổ thông mới phát hành theo mệnh giá",
            "Nhân viên tự đổi lương thành cổ phần ưu đãi",
            "Kế toán tự hủy bỏ toàn bộ nợ công ty mà không cần cổ phần",
            "Raider lấy tiền trong Két công ty để trả nợ cho chính mình",
        ],
        "answer_index": 0,
        "explanation": "Debt-to-Equity Swap biến chủ nợ thành cổ đông thông qua phát hành cổ phần mới theo par_value.",
    },
    {
        "question": "Nguyên tắc 'Trách Nhiệm Hữu Hạn' khi giải thể doanh nghiệp bảo vệ Chủ sở hữu như thế nào?",
        "options": [
            "Chủ sở hữu phải bán hết tài sản cá nhân để trả đủ 100% nợ lương",
            "Công ty chỉ dùng số dư Két Công Ty hiện có để thanh toán nợ lương; không trừ vào tiền cá nhân của Chủ sở hữu",
            "Két Công Ty bị tịch thu toàn bộ kể cả khi còn dư sau khi trả nợ",
            "Nhân viên phải nộp phạt để bù lỗ cho doanh nghiệp",
        ],
        "answer_index": 1,
        "explanation": "Trách nhiệm hữu hạn giới hạn nghĩa vụ tài chính của chủ sở hữu trong phạm vi vốn góp tại doanh nghiệp.",
    },
    {
        "question": "Theo cơ chế Bỏ Phiếu Đình Công, người lao động được phép kích hoạt đình công khi nào?",
        "options": [
            "Bất kỳ lúc nào ngay cả khi công ty trả đủ lương và m/v <= 5.0",
            "Chỉ khi công ty đang DELINQUENT / còn nợ lương hoặc tỷ suất bóc lột m/v > 5.0",
            "Chỉ khi doanh nghiệp đang trong quá trình PRE_IPO",
            "Chỉ khi độ bền máy móc đạt 100%",
        ],
        "answer_index": 1,
        "explanation": "Đình công đòi hỏi điều kiện khách quan: nợ lương (DELINQUENT/unpaid_wages) hoặc bóc lột cực đoan (m/v > 5.0).",
    },
]


# ==============================================================================
# 2. HELPER BUILDERS & UTILITIES
# ==============================================================================


def utc_now() -> datetime.datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.datetime.now(datetime.timezone.utc)


def parse_iso_dt(value: str) -> datetime.datetime:
    """Parse an ISO-8601 string into a timezone-aware UTC datetime."""
    dt = datetime.datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def format_gold(amount: int | float) -> str:
    """Format gold amount cleanly with thousands separator."""
    return f"{int(amount):,} gold"


def extract_user_id_from_mention(raw: str) -> Optional[str]:
    """Extract numeric Discord user ID from a mention (<@123>, <@!123>) or raw digit string."""
    if not raw:
        return None
    cleaned = raw.strip()
    match = re.fullmatch(r"<@!?(\d{15,22})>", cleaned)
    if match:
        return match.group(1)
    if re.fullmatch(r"\d{15,22}", cleaned):
        return cleaned
    return None


def make_corp_embed(
    title: str,
    description: str = "",
    color: Optional[discord.Color] = None,
    fields: Optional[list[tuple[str, str, bool]]] = None,
    footer: Optional[str] = None,
) -> discord.Embed:
    """Build a standardized corporate economy embed."""
    embed = discord.Embed(
        title=title,
        description=description,
        color=color or discord.Color.blue(),
        timestamp=utc_now(),
    )
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
    if footer:
        embed.set_footer(text=footer)
    return embed


def make_error_embed(title: str, description: str) -> discord.Embed:
    """Build a standardized error embed."""
    return make_corp_embed(
        title=f"❌ {title}",
        description=description,
        color=discord.Color.red(),
        footer="Hệ Thống Kinh Tế Chính Trị & Doanh Nghiệp",
    )


def make_success_embed(
    title: str,
    description: str,
    fields: Optional[list[tuple[str, str, bool]]] = None,
) -> discord.Embed:
    """Build a standardized success receipt embed."""
    return make_corp_embed(
        title=f"✅ {title}",
        description=description,
        color=discord.Color.green(),
        fields=fields,
        footer="Chứng Từ Giao Dịch Doanh Nghiệp",
    )


def format_countdown(target_dt: datetime.datetime, now: Optional[datetime.datetime] = None) -> str:
    """Format remaining duration until target_dt."""
    current = now or utc_now()
    delta = target_dt - current
    total_seconds = max(0, int(delta.total_seconds()))
    hours, rem = divmod(total_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours > 0:
        return f"{hours} giờ {minutes} phút {seconds} giây"
    if minutes > 0:
        return f"{minutes} phút {seconds} giây"
    return f"{seconds} giây"


def parse_positive_int(raw: str) -> Optional[int]:
    """Parse human-formatted positive integer (supports commas/underscores)."""
    cleaned = raw.strip().replace(",", "").replace("_", "").replace(".", "")
    if not cleaned.isdigit():
        return None
    val = int(cleaned)
    return val if val > 0 else None


# ==============================================================================
# 3. DATABASE SCHEMA & FSM VALIDATION CORE
# ==============================================================================


async def ensure_corporate_tables(db: aiosqlite.Connection) -> None:
    """Initialize WAL mode and all 10 required corporate economy tables."""
    await db.execute("PRAGMA journal_mode=WAL;")
    await db.execute("PRAGMA foreign_keys=ON;")

    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            gold INTEGER DEFAULT 0
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS companies (
            company_id TEXT PRIMARY KEY,
            name TEXT,
            model_type TEXT,
            scale_type TEXT,
            industry_type TEXT,
            fsm_state TEXT,
            vault_balance INTEGER,
            capital_registration INTEGER,
            total_shares INTEGER,
            par_value INTEGER,
            owner_id TEXT,
            ceo_id TEXT,
            accountant_id TEXT,
            total_capital_c INTEGER DEFAULT 0,
            total_wages_v INTEGER DEFAULT 0,
            total_surplus_m INTEGER DEFAULT 0,
            unpaid_wages INTEGER DEFAULT 0
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS company_shareholders (
            company_id TEXT,
            user_id TEXT,
            shares_count INTEGER,
            capital_contributed INTEGER,
            share_type TEXT,
            PRIMARY KEY (company_id, user_id)
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS production_facilities (
            company_id TEXT PRIMARY KEY,
            facility_type TEXT,
            tier INTEGER,
            durability INTEGER,
            raw_materials_stock INTEGER,
            finished_goods_stock INTEGER
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS employees (
            employee_id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id TEXT,
            user_id TEXT,
            role_title TEXT,
            daily_wage INTEGER,
            unpaid_wage INTEGER,
            energy_cost INTEGER,
            is_on_strike INTEGER
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS intellectual_certificates (
            cert_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE,
            cert_type TEXT,
            score INTEGER,
            issued_at TEXT,
            is_valid INTEGER
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS invoices_receivable (
            invoice_id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id TEXT,
            amount INTEGER,
            net_type TEXT,
            due_at TEXT,
            settled INTEGER
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS share_market_orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id TEXT,
            seller_id TEXT,
            shares_count INTEGER,
            price_per_share INTEGER,
            market_scope TEXT,
            status TEXT,
            expires_at TEXT
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS hostile_takeover_bids (
            bid_id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_company_id TEXT,
            raider_id TEXT,
            offered_price_per_share INTEGER,
            target_share_count INTEGER,
            acquired_share_count INTEGER,
            escrow_vault INTEGER,
            status TEXT,
            expires_at TEXT
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS company_corporate_debts (
            debt_id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id TEXT,
            creditor_id TEXT,
            principal_amount INTEGER,
            interest_rate REAL,
            due_date TEXT,
            is_settled INTEGER
        )
        """
    )
    await db.commit()


def can_fsm_transition(current_state: str, target_state: str) -> bool:
    """Validate whether current_state can transition to target_state under COMPANY_FSM_TRANSITIONS."""
    allowed = COMPANY_FSM_TRANSITIONS.get(current_state, [])
    return target_state in allowed


async def transition_company_fsm(
    db: aiosqlite.Connection,
    company_id: str,
    target_state: str,
) -> tuple[bool, str]:
    """Safely validate and execute an FSM state transition for a company."""
    async with db.execute(
        "SELECT fsm_state FROM companies WHERE company_id = ?",
        (company_id,),
    ) as cur:
        row = await cur.fetchone()

    if row is None:
        return False, "Không tìm thấy doanh nghiệp."

    current_state = row["fsm_state"]
    if current_state == target_state:
        return True, f"Doanh nghiệp đang ở trạng thái {target_state}."

    if not can_fsm_transition(current_state, target_state):
        return (
            False,
            f"Chuyển trạng thái không hợp lệ: `{current_state}` ➔ `{target_state}`.",
        )

    await db.execute(
        "UPDATE companies SET fsm_state = ? WHERE company_id = ?",
        (target_state, company_id),
    )
    return True, f"Đã chuyển trạng thái doanh nghiệp: `{current_state}` ➔ `{target_state}`."


async def ensure_user(db: aiosqlite.Connection, user_id: str) -> None:
    """Ensure a user row exists in users table."""
    await db.execute(
        "INSERT OR IGNORE INTO users (user_id, gold) VALUES (?, 0)",
        (str(user_id),),
    )


async def get_user_gold(db: aiosqlite.Connection, user_id: str) -> int:
    """Return user gold balance (creates row with 0 if missing)."""
    await ensure_user(db, str(user_id))
    async with db.execute(
        "SELECT gold FROM users WHERE user_id = ?",
        (str(user_id),),
    ) as cur:
        row = await cur.fetchone()
    return int(row["gold"] or 0) if row else 0


async def adjust_user_gold(db: aiosqlite.Connection, user_id: str, delta: int) -> int:
    """Atomically adjust user gold balance and return updated amount."""
    uid = str(user_id)
    await ensure_user(db, uid)
    await db.execute(
        "UPDATE users SET gold = COALESCE(gold, 0) + ? WHERE user_id = ?",
        (int(delta), uid),
    )
    return await get_user_gold(db, uid)


async def get_company(db: aiosqlite.Connection, company_id: str) -> Optional[dict[str, Any]]:
    """Fetch company record by ID."""
    async with db.execute(
        "SELECT * FROM companies WHERE company_id = ?",
        (company_id,),
    ) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None


async def find_company_by_query(db: aiosqlite.Connection, query: str) -> Optional[dict[str, Any]]:
    """Find company by exact company_id or case-insensitive substring on name."""
    cleaned = query.strip()
    if not cleaned:
        return None
    async with db.execute(
        "SELECT * FROM companies WHERE UPPER(company_id) = UPPER(?)",
        (cleaned,),
    ) as cur:
        row = await cur.fetchone()
    if row:
        return dict(row)

    async with db.execute(
        "SELECT * FROM companies WHERE LOWER(name) LIKE LOWER(?) ORDER BY capital_registration DESC LIMIT 1",
        (f"%{cleaned}%",),
    ) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None


async def get_facility(db: aiosqlite.Connection, company_id: str) -> Optional[dict[str, Any]]:
    """Fetch production facility for a company."""
    async with db.execute(
        "SELECT * FROM production_facilities WHERE company_id = ?",
        (company_id,),
    ) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None


async def get_shareholding(
    db: aiosqlite.Connection,
    company_id: str,
    user_id: str,
) -> Optional[dict[str, Any]]:
    """Fetch shareholding row for a user in a company."""
    async with db.execute(
        "SELECT * FROM company_shareholders WHERE company_id = ? AND user_id = ?",
        (company_id, str(user_id)),
    ) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None


async def upsert_shareholding(
    db: aiosqlite.Connection,
    company_id: str,
    user_id: str,
    shares_delta: int,
    capital_delta: int = 0,
    share_type: str = "COMMON",
) -> int:
    """Add or subtract shares for a shareholder; deletes row if remaining <= 0."""
    uid = str(user_id)
    existing = await get_shareholding(db, company_id, uid)
    if existing is None:
        new_shares = max(0, int(shares_delta))
        if new_shares > 0:
            await db.execute(
                """
                INSERT INTO company_shareholders
                    (company_id, user_id, shares_count, capital_contributed, share_type)
                VALUES (?, ?, ?, ?, ?)
                """,
                (company_id, uid, new_shares, max(0, int(capital_delta)), share_type),
            )
        return new_shares

    new_shares = int(existing["shares_count"]) + int(shares_delta)
    new_cap = max(0, int(existing["capital_contributed"]) + int(capital_delta))
    if new_shares <= 0:
        await db.execute(
            "DELETE FROM company_shareholders WHERE company_id = ? AND user_id = ?",
            (company_id, uid),
        )
        return 0

    await db.execute(
        """
        UPDATE company_shareholders
        SET shares_count = ?, capital_contributed = ?, share_type = ?
        WHERE company_id = ? AND user_id = ?
        """,
        (new_shares, new_cap, existing["share_type"] or share_type, company_id, uid),
    )
    return new_shares


async def get_employee(
    db: aiosqlite.Connection,
    company_id: str,
    user_id: str,
) -> Optional[dict[str, Any]]:
    """Fetch contracted employee row for a user in a company."""
    async with db.execute(
        "SELECT * FROM employees WHERE company_id = ? AND user_id = ?",
        (company_id, str(user_id)),
    ) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None


async def has_valid_intellectual_cert(db: aiosqlite.Connection, user_id: str) -> bool:
    """Check whether user holds a valid INTELLECTUAL_LABOR certificate."""
    async with db.execute(
        """
        SELECT is_valid FROM intellectual_certificates
        WHERE user_id = ? AND cert_type = 'INTELLECTUAL_LABOR' AND is_valid = 1
        """,
        (str(user_id),),
    ) as cur:
        row = await cur.fetchone()
    return row is not None


async def get_active_takeover_bid(
    db: aiosqlite.Connection,
    company_id: str,
) -> Optional[dict[str, Any]]:
    """Return active ACQUIRING hostile takeover bid if any (auto-expiring stale bids)."""
    async with db.execute(
        """
        SELECT * FROM hostile_takeover_bids
        WHERE target_company_id = ? AND status = 'ACQUIRING'
        ORDER BY bid_id DESC LIMIT 1
        """,
        (company_id,),
    ) as cur:
        row = await cur.fetchone()

    if not row:
        return None

    bid = dict(row)
    if parse_iso_dt(bid["expires_at"]) <= utc_now():
        # Auto-expire and refund remaining escrow
        remaining_escrow = int(bid["escrow_vault"] or 0)
        if remaining_escrow > 0:
            await adjust_user_gold(db, bid["raider_id"], remaining_escrow)
        await db.execute(
            "UPDATE hostile_takeover_bids SET status = 'EXPIRED', escrow_vault = 0 WHERE bid_id = ?",
            (bid["bid_id"],),
        )
        comp = await get_company(db, company_id)
        if comp and comp["fsm_state"] == "UNDER_TAKEOVER":
            await transition_company_fsm(db, company_id, "ACTIVE")
        await db.commit()
        return None

    return bid


async def get_user_role_in_company(
    db: aiosqlite.Connection,
    company_id: str,
    user_id: str,
) -> str:
    """Resolve user's strict role within a company: BOARD, ACCOUNTANT, WORKER, or SPECULATOR."""
    uid = str(user_id)
    comp = await get_company(db, company_id)
    if not comp:
        return "SPECULATOR"
    if uid == comp["owner_id"] or (comp["ceo_id"] and uid == comp["ceo_id"]):
        return "BOARD"
    if comp["accountant_id"] and uid == comp["accountant_id"]:
        return "ACCOUNTANT"
    emp = await get_employee(db, company_id, uid)
    if emp:
        return "WORKER"
    return "SPECULATOR"


async def get_user_related_companies(
    db: aiosqlite.Connection,
    user_id: str,
) -> list[dict[str, Any]]:
    """Find all companies where user is Owner/CEO, Accountant, Employee, or Shareholder."""
    uid = str(user_id)
    async with db.execute(
        """
        SELECT DISTINCT c.*
        FROM companies c
        LEFT JOIN employees e ON c.company_id = e.company_id
        LEFT JOIN company_shareholders s ON c.company_id = s.company_id
        WHERE c.owner_id = ?
           OR c.ceo_id = ?
           OR c.accountant_id = ?
           OR e.user_id = ?
           OR s.user_id = ?
        ORDER BY CASE WHEN c.fsm_state = 'DISSOLVED' THEN 1 ELSE 0 END, c.capital_registration DESC
        """,
        (uid, uid, uid, uid, uid),
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


# ==============================================================================
# 4. TRANSACTIONAL DOMAIN SERVICES (MARXIAN ECONOMY & M&A ENGINE)
# ==============================================================================


async def create_company_service(
    db: aiosqlite.Connection,
    owner_id: str,
    name: str,
    model_type: str,
    scale_type: str,
    industry_type: str,
    capital: int,
) -> tuple[bool, str, dict[str, Any]]:
    """Register a new legal corporate entity, deduct capital + license tax, and initialize facility."""
    uid = str(owner_id)
    clean_name = name.strip()
    model = model_type.strip().upper()
    scale = scale_type.strip().upper()
    industry = industry_type.strip().upper()

    if len(clean_name) < 3 or len(clean_name) > 50:
        return False, "Tên doanh nghiệp phải từ 3 đến 50 ký tự.", {}
    if model not in LEGAL_MODELS:
        return False, f"Mô hình pháp lý không hợp lệ. Chọn: {', '.join(LEGAL_MODELS.keys())}.", {}
    if scale not in SCALE_INFO:
        return False, f"Quy mô không hợp lệ. Chọn: {', '.join(SCALE_INFO.keys())}.", {}
    if industry not in INDUSTRY_INFO:
        return False, f"Ngành nghề không hợp lệ. Chọn: {', '.join(INDUSTRY_INFO.keys())}.", {}

    scale_cfg = SCALE_INFO[scale]
    if model not in scale_cfg["allowed_models"]:
        return (
            False,
            f"Quy mô `{scale}` chỉ cho phép mô hình: {', '.join(scale_cfg['allowed_models'])}.",
            {},
        )
    if not (scale_cfg["min_capital"] <= capital <= scale_cfg["max_capital"]):
        return (
            False,
            (
                f"Vốn điều lệ cho quy mô `{scale}` phải từ "
                f"{format_gold(scale_cfg['min_capital'])} đến {format_gold(scale_cfg['max_capital'])}."
            ),
            {},
        )
    if capital % PAR_VALUE != 0:
        return False, f"Vốn điều lệ phải chia hết cho mệnh giá cổ phần ({format_gold(PAR_VALUE)}).", {}

    license_tax = int(round(capital * scale_cfg["license_tax_rate"]))
    total_required = capital + license_tax
    user_gold = await get_user_gold(db, uid)
    if user_gold < total_required:
        return (
            False,
            (
                f"Không đủ tiền thành lập doanh nghiệp. Cần {format_gold(total_required)} "
                f"(Vốn {format_gold(capital)} + Thuế môn bài {format_gold(license_tax)}), "
                f"hiện có {format_gold(user_gold)}."
            ),
            {},
        )

    company_id = f"CORP-{uuid.uuid4().hex[:6].upper()}"
    total_shares = capital // PAR_VALUE
    ind_cfg = INDUSTRY_INFO[industry]

    await adjust_user_gold(db, uid, -total_required)
    await db.execute(
        """
        INSERT INTO companies (
            company_id, name, model_type, scale_type, industry_type,
            fsm_state, vault_balance, capital_registration, total_shares,
            par_value, owner_id, ceo_id, accountant_id,
            total_capital_c, total_wages_v, total_surplus_m, unpaid_wages
        ) VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?, ?, ?, ?, NULL, 0, 0, 0, 0)
        """,
        (
            company_id,
            clean_name,
            model,
            scale,
            industry,
            capital,
            capital,
            total_shares,
            PAR_VALUE,
            uid,
            uid,
        ),
    )
    await upsert_shareholding(db, company_id, uid, total_shares, capital, "COMMON")
    await db.execute(
        """
        INSERT INTO production_facilities (
            company_id, facility_type, tier, durability, raw_materials_stock, finished_goods_stock
        ) VALUES (?, ?, 1, 100, 5, 0)
        """,
        (company_id, ind_cfg["facility_type"]),
    )
    await db.commit()

    return (
        True,
        f"Đã thành lập **{clean_name}** (`{company_id}`) thành công!",
        {
            "company_id": company_id,
            "capital": capital,
            "license_tax": license_tax,
            "total_shares": total_shares,
        },
    )


async def hire_employee_service(
    db: aiosqlite.Connection,
    actor_id: str,
    company_id: str,
    target_user_id: str,
    role_title: str,
    daily_wage: int,
) -> tuple[bool, str, dict[str, Any]]:
    """Hire an employee with strict 4-role separation and TECH intellectual labor certificate checks."""
    actor = str(actor_id)
    target = str(target_user_id)
    comp = await get_company(db, company_id)
    if not comp:
        return False, "Không tìm thấy doanh nghiệp.", {}
    if actor not in (comp["owner_id"], comp["ceo_id"]):
        return False, "Chỉ Chủ Sở Hữu / CEO mới có quyền tuyển dụng nhân sự.", {}
    if comp["fsm_state"] == "DISSOLVED":
        return False, "Doanh nghiệp đã giải thể, không thể tuyển dụng.", {}
    if daily_wage <= 0:
        return False, "Mức lương mỗi ca phải lớn hơn 0.", {}

    clean_title = role_title.strip()
    if not clean_title or len(clean_title) > 40:
        return False, "Chức danh công việc phải từ 1 đến 40 ký tự.", {}

    # Strict 4-Role Separation
    if target in (comp["owner_id"], comp["ceo_id"]):
        return False, "Vi phạm phân tách 4 vai trò: Chủ sở hữu / CEO không thể tự ký hợp đồng làm Công Nhân.", {}
    if comp["accountant_id"] and target == comp["accountant_id"]:
        return False, "Vi phạm phân tách 4 vai trò: Kế toán trưởng đang giữ vai trò tài chính độc lập.", {}
    if await get_employee(db, company_id, target):
        return False, "Người này đã có hợp đồng lao động tại doanh nghiệp.", {}

    ind_cfg = INDUSTRY_INFO[comp["industry_type"]]
    if ind_cfg["requires_intellectual"]:
        has_cert = await has_valid_intellectual_cert(db, target)
        if not has_cert:
            return (
                False,
                (
                    f"Ngành **{ind_cfg['name']}** yêu cầu 100% Lao động Trí tuệ (`INTELLECTUAL_LABOR`). "
                    f"<@{target}> chưa có chứng chỉ hợp lệ (hãy thi tại mục **Thi Chứng Chỉ**)."
                ),
                {},
            )

    await ensure_user(db, target)
    await db.execute(
        """
        INSERT INTO employees (
            company_id, user_id, role_title, daily_wage, unpaid_wage, energy_cost, is_on_strike
        ) VALUES (?, ?, ?, ?, 0, 10, 0)
        """,
        (company_id, target, clean_title, int(daily_wage)),
    )
    await db.commit()
    return (
        True,
        f"Đã tuyển dụng <@{target}> vào vị trí **{clean_title}** với lương ca {format_gold(daily_wage)}.",
        {"target_user_id": target, "daily_wage": daily_wage},
    )


async def appoint_accountant_service(
    db: aiosqlite.Connection,
    actor_id: str,
    company_id: str,
    target_user_id: str,
) -> tuple[bool, str, dict[str, Any]]:
    """Appoint an independent Accountant enforcing 4-role isolation."""
    actor = str(actor_id)
    target = str(target_user_id)
    comp = await get_company(db, company_id)
    if not comp:
        return False, "Không tìm thấy doanh nghiệp.", {}
    if actor not in (comp["owner_id"], comp["ceo_id"]):
        return False, "Chỉ Chủ Sở Hữu / CEO mới có quyền bổ nhiệm Kế Toán.", {}
    if comp["fsm_state"] == "DISSOLVED":
        return False, "Doanh nghiệp đã giải thể.", {}

    if target in (comp["owner_id"], comp["ceo_id"]):
        return False, "Vi phạm phân tách 4 vai trò: Chủ Sở Hữu / CEO không thể kiêm nhiệm Kế Toán.", {}
    if await get_employee(db, company_id, target):
        return False, "Vi phạm phân tách 4 vai trò: Công nhân sản xuất không thể kiêm nhiệm Kế Toán.", {}

    await ensure_user(db, target)
    await db.execute(
        "UPDATE companies SET accountant_id = ? WHERE company_id = ?",
        (target, company_id),
    )
    await db.commit()
    return True, f"Đã bổ nhiệm <@{target}> làm Kế Toán độc lập cho **{comp['name']}**.", {"accountant_id": target}


async def buy_raw_and_repair_service(
    db: aiosqlite.Connection,
    actor_id: str,
    company_id: str,
    raw_qty: int,
    repair_tens: int,
) -> tuple[bool, str, dict[str, Any]]:
    """Accountant-only procurement of raw materials and machine durability repair."""
    actor = str(actor_id)
    comp = await get_company(db, company_id)
    if not comp:
        return False, "Không tìm thấy doanh nghiệp.", {}
    if actor != comp["accountant_id"]:
        return False, "Từ chối truy cập: Chỉ **Kế Toán** được bổ nhiệm mới được phép nhập TLSX & bảo trì.", {}
    if comp["fsm_state"] == "DISSOLVED":
        return False, "Doanh nghiệp đã giải thể.", {}
    if raw_qty < 0 or repair_tens < 0 or (raw_qty == 0 and repair_tens == 0):
        return False, "Số lượng nhập nguyên liệu hoặc gói bảo trì phải >= 0 và có ít nhất 1 hạng mục > 0.", {}

    fac = await get_facility(db, company_id)
    if not fac:
        return False, "Không tìm thấy cơ sở sản xuất.", {}

    ind_cfg = INDUSTRY_INFO[comp["industry_type"]]
    raw_cost_total = raw_qty * ind_cfg["raw_cost"]

    current_durability = int(fac["durability"])
    max_repair_pct = max(0, 100 - current_durability)
    requested_repair_pct = repair_tens * 10
    actual_repair_pct = min(max_repair_pct, requested_repair_pct)
    actual_repair_blocks = math.ceil(actual_repair_pct / 10) if actual_repair_pct > 0 else 0
    repair_cost_total = actual_repair_blocks * REPAIR_COST_PER_10_PCT

    total_cost = raw_cost_total + repair_cost_total
    if total_cost <= 0:
        return False, "Máy móc đã đạt 100% độ bền và không có đơn nhập vật tư.", {}

    if int(comp["vault_balance"]) < total_cost:
        return (
            False,
            f"Két Công Ty không đủ tiền. Cần {format_gold(total_cost)}, Két hiện có {format_gold(comp['vault_balance'])}.",
            {},
        )

    await db.execute(
        "UPDATE companies SET vault_balance = vault_balance - ? WHERE company_id = ?",
        (total_cost, company_id),
    )
    await db.execute(
        """
        UPDATE production_facilities
        SET raw_materials_stock = raw_materials_stock + ?,
            durability = MIN(100, durability + ?)
        WHERE company_id = ?
        """,
        (raw_qty, actual_repair_pct, company_id),
    )
    await db.commit()

    return (
        True,
        (
            f"Đã nhập **{raw_qty} nguyên liệu** ({format_gold(raw_cost_total)}) và phục hồi "
            f"**+{actual_repair_pct}% độ bền** ({format_gold(repair_cost_total)})."
        ),
        {"total_cost": total_cost, "raw_added": raw_qty, "repaired_pct": actual_repair_pct},
    )


async def execute_production_shift_service(
    db: aiosqlite.Connection,
    actor_id: str,
    company_id: str,
) -> tuple[bool, str, dict[str, Any]]:
    """Execute one Marxian production shift W = c + v + m for a contracted worker."""
    actor = str(actor_id)
    comp = await get_company(db, company_id)
    if not comp:
        return False, "Không tìm thấy doanh nghiệp.", {}

    emp = await get_employee(db, company_id, actor)
    if not emp:
        return False, "Bạn không phải người lao động ký hợp đồng của doanh nghiệp này.", {}
    if comp["fsm_state"] == "DISSOLVED":
        return False, "Doanh nghiệp đã giải thể.", {}
    if comp["fsm_state"] == "ON_STRIKE" or int(emp["is_on_strike"]) == 1:
        return False, "Không thể vào ca: Doanh nghiệp hoặc cá nhân bạn đang trong trạng thái ĐÌNH CÔNG (`ON_STRIKE`).", {}

    fac = await get_facility(db, company_id)
    if not fac:
        return False, "Không tìm thấy nhà máy / cơ sở sản xuất.", {}
    if int(fac["durability"]) <= 5:
        return False, "Máy móc hư hỏng nặng (độ bền <= 5%). Yêu cầu Kế Toán bảo trì trước khi sản xuất.", {}
    if int(fac["raw_materials_stock"]) < 1:
        return False, "Kho nguyên vật liệu đã cạn (< 1). Yêu cầu Kế Toán nhập TLSX.", {}

    ind_cfg = INDUSTRY_INFO[comp["industry_type"]]
    has_cert = await has_valid_intellectual_cert(db, actor)
    if ind_cfg["requires_intellectual"] and not has_cert:
        return False, f"Ngành `{comp['industry_type']}` bắt buộc chứng chỉ `INTELLECTUAL_LABOR` hợp lệ.", {}

    c_val = int(ind_cfg["raw_cost"]) + int(ind_cfg["depreciation"])
    v_val = int(emp["daily_wage"])
    effective_mult = float(ind_cfg["surplus_mult"])
    bonus_applied = False
    if comp["industry_type"] == "HEAVY_IND" and has_cert:
        effective_mult *= float(ind_cfg["intellectual_bonus_mult"])
        bonus_applied = True

    m_val = math.floor(v_val * effective_mult)
    w_val = c_val + v_val + m_val

    # Consume 1 raw material, 1% durability, produce 1 finished good
    await db.execute(
        """
        UPDATE production_facilities
        SET raw_materials_stock = raw_materials_stock - 1,
            durability = MAX(0, durability - 1),
            finished_goods_stock = finished_goods_stock + 1
        WHERE company_id = ?
        """,
        (company_id,),
    )

    # Update Marxian aggregates
    await db.execute(
        """
        UPDATE companies
        SET total_capital_c = total_capital_c + ?,
            total_wages_v = total_wages_v + ?,
            total_surplus_m = total_surplus_m + ?
        WHERE company_id = ?
        """,
        (c_val, v_val, m_val, company_id),
    )

    # Settlement logic: IMMEDIATE vs NET_60 / NET_90
    settlement_type = ind_cfg["settlement"]
    invoice_due_at_str: Optional[str] = None
    if settlement_type == "IMMEDIATE":
        await db.execute(
            "UPDATE companies SET vault_balance = vault_balance + ? WHERE company_id = ?",
            (w_val, company_id),
        )
    else:
        due_dt = utc_now() + datetime.timedelta(minutes=int(ind_cfg["net_minutes"]))
        invoice_due_at_str = due_dt.isoformat()
        await db.execute(
            """
            INSERT INTO invoices_receivable (company_id, amount, net_type, due_at, settled)
            VALUES (?, ?, ?, ?, 0)
            """,
            (company_id, w_val, settlement_type, invoice_due_at_str),
        )

    # Re-fetch updated vault balance and enforce Liquidity & Wage Default Rule
    updated_comp = await get_company(db, company_id)
    assert updated_comp is not None
    vault = int(updated_comp["vault_balance"])

    wage_paid = False
    fsm_changed_to_delinquent = False
    if vault >= v_val:
        await db.execute(
            "UPDATE companies SET vault_balance = vault_balance - ? WHERE company_id = ?",
            (v_val, company_id),
        )
        await adjust_user_gold(db, actor, v_val)
        wage_paid = True
    else:
        await db.execute(
            "UPDATE employees SET unpaid_wage = unpaid_wage + ? WHERE employee_id = ?",
            (v_val, emp["employee_id"]),
        )
        await db.execute(
            "UPDATE companies SET unpaid_wages = unpaid_wages + ? WHERE company_id = ?",
            (v_val, company_id),
        )
        if updated_comp["fsm_state"] != "DELINQUENT" and can_fsm_transition(updated_comp["fsm_state"], "DELINQUENT"):
            await transition_company_fsm(db, company_id, "DELINQUENT")
            fsm_changed_to_delinquent = True

    await db.commit()
    exploitation_rate = (m_val / v_val) if v_val > 0 else 0.0

    return (
        True,
        "Hoàn thành ca lao động sản xuất.",
        {
            "c": c_val,
            "v": v_val,
            "m": m_val,
            "W": w_val,
            "exploitation_rate": exploitation_rate,
            "bonus_applied": bonus_applied,
            "settlement_type": settlement_type,
            "invoice_due_at": invoice_due_at_str,
            "wage_paid": wage_paid,
            "fsm_changed_to_delinquent": fsm_changed_to_delinquent,
        },
    )


async def reconcile_invoices_service(
    db: aiosqlite.Connection,
    actor_id: str,
    company_id: str,
) -> tuple[bool, str, dict[str, Any]]:
    """Accountant-only settlement of matured Net 60/90 invoices into company Vault."""
    actor = str(actor_id)
    comp = await get_company(db, company_id)
    if not comp:
        return False, "Không tìm thấy doanh nghiệp.", {}
    if actor != comp["accountant_id"]:
        return False, "Chỉ **Kế Toán** được bổ nhiệm mới có quyền đối soát công nợ Net 60/90.", {}

    async with db.execute(
        "SELECT * FROM invoices_receivable WHERE company_id = ? AND settled = 0 ORDER BY due_at ASC",
        (company_id,),
    ) as cur:
        pending = [dict(r) for r in await cur.fetchall()]

    if not pending:
        return True, "Hiện không có hóa đơn Net 60/90 nào đang chờ thu.", {"settled_count": 0, "settled_amount": 0}

    now = utc_now()
    matured_ids: list[int] = []
    matured_amount = 0
    next_due: Optional[datetime.datetime] = None

    for inv in pending:
        due_dt = parse_iso_dt(inv["due_at"])
        if due_dt <= now:
            matured_ids.append(int(inv["invoice_id"]))
            matured_amount += int(inv["amount"])
        elif next_due is None or due_dt < next_due:
            next_due = due_dt

    if not matured_ids:
        countdown = format_countdown(next_due, now) if next_due else "N/A"
        return (
            False,
            f"Chưa có hóa đơn nào đáo hạn. Hóa đơn gần nhất còn **{countdown}** nữa mới thu được tiền ({len(pending)} hóa đơn đang treo).",
            {"settled_count": 0, "settled_amount": 0, "pending_count": len(pending), "countdown": countdown},
        )

    placeholders = ",".join("?" for _ in matured_ids)
    await db.execute(
        f"UPDATE invoices_receivable SET settled = 1 WHERE invoice_id IN ({placeholders})",
        tuple(matured_ids),
    )
    await db.execute(
        "UPDATE companies SET vault_balance = vault_balance + ? WHERE company_id = ?",
        (matured_amount, company_id),
    )
    await db.commit()

    return (
        True,
        f"Đã đối soát thành công **{len(matured_ids)} hóa đơn**, thu về Két **{format_gold(matured_amount)}**.",
        {"settled_count": len(matured_ids), "settled_amount": matured_amount},
    )


async def pay_unpaid_wages_service(
    db: aiosqlite.Connection,
    actor_id: str,
    company_id: str,
) -> tuple[bool, str, dict[str, Any]]:
    """Accountant-only disbursement of unpaid wages; restores DELINQUENT -> ACTIVE on full settlement."""
    actor = str(actor_id)
    comp = await get_company(db, company_id)
    if not comp:
        return False, "Không tìm thấy doanh nghiệp.", {}
    if actor != comp["accountant_id"]:
        return False, "Chỉ **Kế Toán** được bổ nhiệm mới có quyền chi trả lương.", {}

    async with db.execute(
        "SELECT * FROM employees WHERE company_id = ? AND unpaid_wage > 0",
        (company_id,),
    ) as cur:
        debt_emps = [dict(r) for r in await cur.fetchall()]

    total_owed = sum(int(e["unpaid_wage"]) for e in debt_emps)
    if total_owed <= 0:
        if comp["fsm_state"] == "DELINQUENT":
            await transition_company_fsm(db, company_id, "ACTIVE")
            await db.commit()
            return True, "Không còn nợ lương tồn đọng; đã khôi phục trạng thái `ACTIVE`.", {"paid_total": 0}
        return True, "Hiện doanh nghiệp không nợ lương nhân viên nào.", {"paid_total": 0}

    vault = int(comp["vault_balance"])
    if vault < total_owed:
        return (
            False,
            f"Két Công Ty chưa đủ để tất toán nợ lương. Cần {format_gold(total_owed)}, Két hiện có {format_gold(vault)}.",
            {"needed": total_owed, "vault": vault},
        )

    await db.execute(
        "UPDATE companies SET vault_balance = vault_balance - ?, unpaid_wages = 0 WHERE company_id = ?",
        (total_owed, company_id),
    )
    for emp in debt_emps:
        owed = int(emp["unpaid_wage"])
        await adjust_user_gold(db, emp["user_id"], owed)
        await db.execute(
            "UPDATE employees SET unpaid_wage = 0 WHERE employee_id = ?",
            (emp["employee_id"],),
        )

    restored_active = False
    if comp["fsm_state"] == "DELINQUENT":
        ok, _ = await transition_company_fsm(db, company_id, "ACTIVE")
        restored_active = ok

    await db.commit()
    return (
        True,
        f"Đã chi trả đủ **{format_gold(total_owed)}** nợ lương cho {len(debt_emps)} nhân viên.",
        {"paid_total": total_owed, "employees_paid": len(debt_emps), "restored_active": restored_active},
    )


async def toggle_strike_service(
    db: aiosqlite.Connection,
    actor_id: str,
    company_id: str,
) -> tuple[bool, str, dict[str, Any]]:
    """Toggle employee strike vote; transitions company to ON_STRIKE if >= 50% employees strike."""
    actor = str(actor_id)
    comp = await get_company(db, company_id)
    if not comp:
        return False, "Không tìm thấy doanh nghiệp.", {}

    emp = await get_employee(db, company_id, actor)
    if not emp:
        return False, "Chỉ người lao động có hợp đồng mới có quyền bỏ phiếu đình công.", {}
    if comp["fsm_state"] == "DISSOLVED":
        return False, "Doanh nghiệp đã giải thể.", {}

    total_v = int(comp["total_wages_v"] or 0)
    total_m = int(comp["total_surplus_m"] or 0)
    avg_exploitation = (total_m / total_v) if total_v > 0 else 0.0
    ind_exploitation = float(INDUSTRY_INFO[comp["industry_type"]]["surplus_mult"])
    effective_exploitation = max(avg_exploitation, ind_exploitation)

    currently_striking = int(emp["is_on_strike"]) == 1
    if not currently_striking:
        can_strike = (
            comp["fsm_state"] == "DELINQUENT"
            or int(comp["unpaid_wages"] or 0) > 0
            or int(emp["unpaid_wage"] or 0) > 0
            or effective_exploitation > MAX_STRIKE_EXPLOITATION_THRESHOLD
        )
        if not can_strike:
            return (
                False,
                (
                    "Không đủ điều kiện đình công! Chỉ được đình công khi công ty **DELINQUENT / nợ lương** "
                    f"hoặc tỷ suất bóc lột **m/v > {MAX_STRIKE_EXPLOITATION_THRESHOLD:.1f}** "
                    f"(hiện tại: `{effective_exploitation:.2f}`)."
                ),
                {},
            )

    new_strike_flag = 0 if currently_striking else 1
    await db.execute(
        "UPDATE employees SET is_on_strike = ? WHERE employee_id = ?",
        (new_strike_flag, emp["employee_id"]),
    )

    async with db.execute(
        "SELECT COUNT(*) AS total_cnt, SUM(CASE WHEN is_on_strike = 1 THEN 1 ELSE 0 END) AS strike_cnt FROM employees WHERE company_id = ?",
        (company_id,),
    ) as cur:
        counts = await cur.fetchone()

    total_cnt = int(counts["total_cnt"] or 0)
    strike_cnt = int(counts["strike_cnt"] or 0)
    strike_ratio = (strike_cnt / total_cnt) if total_cnt > 0 else 0.0

    fsm_note = ""
    if strike_ratio >= 0.5 and comp["fsm_state"] != "ON_STRIKE":
        ok, msg = await transition_company_fsm(db, company_id, "ON_STRIKE")
        if ok:
            fsm_note = f" ({msg})"
    elif strike_ratio < 0.5 and comp["fsm_state"] == "ON_STRIKE":
        target = "DELINQUENT" if int(comp["unpaid_wages"] or 0) > 0 else "ACTIVE"
        ok, msg = await transition_company_fsm(db, company_id, target)
        if ok:
            fsm_note = f" ({msg})"

    await db.commit()
    action_text = "tham gia ĐÌNH CÔNG" if new_strike_flag == 1 else "RÚT PHIẾU đình công"
    return (
        True,
        f"Bạn đã **{action_text}**. Tỷ lệ đình công hiện tại: **{strike_cnt}/{total_cnt} ({strike_ratio*100:.0f}%)**{fsm_note}.",
        {"is_on_strike": new_strike_flag, "strike_cnt": strike_cnt, "total_cnt": total_cnt},
    )


async def resign_employee_service(
    db: aiosqlite.Connection,
    actor_id: str,
    company_id: str,
) -> tuple[bool, str, dict[str, Any]]:
    """Allow an employee to resign from the company."""
    actor = str(actor_id)
    comp = await get_company(db, company_id)
    if not comp:
        return False, "Không tìm thấy doanh nghiệp.", {}

    emp = await get_employee(db, company_id, actor)
    if not emp:
        return False, "Bạn không phải nhân viên của doanh nghiệp này.", {}

    forfeited_unpaid = int(emp["unpaid_wage"] or 0)
    await db.execute("DELETE FROM employees WHERE employee_id = ?", (emp["employee_id"],))
    if forfeited_unpaid > 0:
        await db.execute(
            "UPDATE companies SET unpaid_wages = MAX(0, unpaid_wages - ?) WHERE company_id = ?",
            (forfeited_unpaid, company_id),
        )
    await db.commit()
    return (
        True,
        f"Bạn đã chấm dứt hợp đồng lao động tại **{comp['name']}**.",
        {"forfeited_unpaid": forfeited_unpaid},
    )


async def distribute_dividend_service(
    db: aiosqlite.Connection,
    actor_id: str,
    company_id: str,
    div_per_share: int,
) -> tuple[bool, str, dict[str, Any]]:
    """Board-only dividend distribution from Vault to all shareholders."""
    actor = str(actor_id)
    comp = await get_company(db, company_id)
    if not comp:
        return False, "Không tìm thấy doanh nghiệp.", {}
    if actor not in (comp["owner_id"], comp["ceo_id"]):
        return False, "Chỉ Chủ Sở Hữu / CEO mới có quyền phê duyệt chia cổ tức.", {}
    if comp["fsm_state"] in ("DELINQUENT", "ON_STRIKE", "DISSOLVED"):
        return False, f"Không thể chia cổ tức khi doanh nghiệp đang ở trạng thái `{comp['fsm_state']}`.", {}
    if div_per_share <= 0:
        return False, "Cổ tức trên mỗi cổ phần phải lớn hơn 0.", {}

    total_shares = int(comp["total_shares"])
    total_payout = div_per_share * total_shares
    if int(comp["vault_balance"]) < total_payout:
        return (
            False,
            f"Két Công Ty không đủ chia cổ tức. Cần {format_gold(total_payout)}, Két hiện có {format_gold(comp['vault_balance'])}.",
            {},
        )

    async with db.execute(
        "SELECT user_id, shares_count FROM company_shareholders WHERE company_id = ? AND shares_count > 0",
        (company_id,),
    ) as cur:
        holders = [dict(r) for r in await cur.fetchall()]

    await db.execute(
        "UPDATE companies SET vault_balance = vault_balance - ? WHERE company_id = ?",
        (total_payout, company_id),
    )
    distributed_actual = 0
    for h in holders:
        payout = int(h["shares_count"]) * div_per_share
        await adjust_user_gold(db, h["user_id"], payout)
        distributed_actual += payout

    await db.commit()
    return (
        True,
        f"Đã chi cổ tức **{format_gold(div_per_share)}/CP** (tổng {format_gold(distributed_actual)}) cho {len(holders)} cổ đông.",
        {"total_payout": distributed_actual, "holders_count": len(holders)},
    )


async def launch_ipo_service(
    db: aiosqlite.Connection,
    actor_id: str,
    company_id: str,
    offer_shares: int,
    price_per_share: int,
) -> tuple[bool, str, dict[str, Any]]:
    """Launch IPO for a CTCP in ACTIVE state: deducts 100M fee, moves to PRE_IPO, creates 7-day PUBLIC_IPO order."""
    actor = str(actor_id)
    comp = await get_company(db, company_id)
    if not comp:
        return False, "Không tìm thấy doanh nghiệp.", {}
    if actor not in (comp["owner_id"], comp["ceo_id"]):
        return False, "Chỉ Chủ Sở Hữu / CEO mới có quyền nộp hồ sơ IPO.", {}
    if comp["model_type"] != "CTCP":
        return False, "Chỉ mô hình Công Ty Cổ Phần (`CTCP`) mới được phép niêm yết IPO.", {}
    if comp["fsm_state"] != "ACTIVE":
        return False, f"Hồ sơ IPO chỉ hợp lệ khi công ty ở trạng thái `ACTIVE` (hiện tại: `{comp['fsm_state']}`).", {}
    if offer_shares <= 0 or price_per_share <= 0:
        return False, "Số cổ phần chào bán và giá phát hành phải > 0.", {}

    holder = await get_shareholding(db, company_id, actor)
    available = int(holder["shares_count"]) if holder else 0
    async with db.execute(
        "SELECT COALESCE(SUM(shares_count), 0) AS locked FROM share_market_orders WHERE company_id = ? AND seller_id = ? AND status = 'OPEN'",
        (company_id, actor),
    ) as cur:
        locked = int((await cur.fetchone())["locked"] or 0)
    if available - locked < offer_shares:
        return (
            False,
            f"Bạn chỉ có {available - locked:,} cổ phần khả dụng (Sở hữu: {available:,}, Đang treo bán: {locked:,}), không đủ chào bán IPO {offer_shares:,} CP.",
            {},
        )

    if int(comp["vault_balance"]) < IPO_FEE:
        return False, f"Két Công Ty cần tối thiểu {format_gold(IPO_FEE)} để nộp phí hồ sơ IPO.", {}

    await db.execute(
        "UPDATE companies SET vault_balance = vault_balance - ? WHERE company_id = ?",
        (IPO_FEE, company_id),
    )
    ok, msg = await transition_company_fsm(db, company_id, "PRE_IPO")
    if not ok:
        await db.rollback()
        return False, msg, {}

    expires_at = (utc_now() + datetime.timedelta(days=7)).isoformat()
    await db.execute(
        """
        INSERT INTO share_market_orders (
            company_id, seller_id, shares_count, price_per_share, market_scope, status, expires_at
        ) VALUES (?, ?, ?, ?, 'PUBLIC_IPO', 'OPEN', ?)
        """,
        (company_id, actor, offer_shares, price_per_share, expires_at),
    )
    await db.commit()
    return (
        True,
        f"Đã nộp hồ sơ IPO thành công (phí {format_gold(IPO_FEE)}). Niêm yết **{offer_shares:,} CP** giá **{format_gold(price_per_share)}/CP** trong 7 ngày (`PRE_IPO`).",
        {"offer_shares": offer_shares, "price_per_share": price_per_share, "expires_at": expires_at},
    )


async def list_internal_share_order_service(
    db: aiosqlite.Connection,
    actor_id: str,
    company_id: str,
    shares_count: int,
    price_per_share: int,
) -> tuple[bool, str, dict[str, Any]]:
    """Create a 72-hour INTERNAL_ONLY share sell order for an existing shareholder."""
    actor = str(actor_id)
    comp = await get_company(db, company_id)
    if not comp:
        return False, "Không tìm thấy doanh nghiệp.", {}
    if comp["fsm_state"] == "DISSOLVED":
        return False, "Doanh nghiệp đã giải thể.", {}
    if shares_count <= 0 or price_per_share <= 0:
        return False, "Số lượng và giá cổ phần phải > 0.", {}

    holder = await get_shareholding(db, company_id, actor)
    owned = int(holder["shares_count"]) if holder else 0
    async with db.execute(
        "SELECT COALESCE(SUM(shares_count), 0) AS locked FROM share_market_orders WHERE company_id = ? AND seller_id = ? AND status = 'OPEN'",
        (company_id, actor),
    ) as cur:
        locked = int((await cur.fetchone())["locked"] or 0)

    if owned - locked < shares_count:
        return False, f"Số cổ phần khả dụng không đủ (Sở hữu: {owned:,}, Đang treo bán: {locked:,}).", {}

    expires_at = (utc_now() + datetime.timedelta(hours=72)).isoformat()
    await db.execute(
        """
        INSERT INTO share_market_orders (
            company_id, seller_id, shares_count, price_per_share, market_scope, status, expires_at
        ) VALUES (?, ?, ?, ?, 'INTERNAL_ONLY', 'OPEN', ?)
        """,
        (company_id, actor, shares_count, price_per_share, expires_at),
    )
    await db.commit()
    return (
        True,
        f"Đã niêm yết bán nội bộ **{shares_count:,} CP** giá **{format_gold(price_per_share)}/CP** (hiệu lực 72 giờ).",
        {"shares_count": shares_count, "price_per_share": price_per_share},
    )


async def buy_share_order_service(
    db: aiosqlite.Connection,
    buyer_id: str,
    order_id: int,
    buy_shares: int,
) -> tuple[bool, str, dict[str, Any]]:
    """Execute a share purchase from an open market order (INTERNAL_ONLY or PUBLIC_IPO)."""
    buyer = str(buyer_id)
    if buy_shares <= 0:
        return False, "Số cổ phần mua phải > 0.", {}

    async with db.execute(
        "SELECT * FROM share_market_orders WHERE order_id = ? AND status = 'OPEN'",
        (order_id,),
    ) as cur:
        row = await cur.fetchone()
    if not row:
        return False, "Không tìm thấy lệnh bán cổ phần đang mở.", {}

    order = dict(row)
    if parse_iso_dt(order["expires_at"]) <= utc_now():
        await db.execute("UPDATE share_market_orders SET status = 'EXPIRED' WHERE order_id = ?", (order_id,))
        await db.commit()
        return False, "Lệnh chào bán cổ phần này đã hết hạn.", {}

    if buyer == order["seller_id"]:
        return False, "Bạn không thể tự mua cổ phần của chính mình.", {}

    comp = await get_company(db, order["company_id"])
    if not comp or comp["fsm_state"] == "DISSOLVED":
        return False, "Doanh nghiệp không tồn tại hoặc đã giải thể.", {}

    if order["market_scope"] == "INTERNAL_ONLY":
        is_member = (
            buyer in (comp["owner_id"], comp["ceo_id"], comp["accountant_id"])
            or await get_shareholding(db, comp["company_id"], buyer) is not None
            or await get_employee(db, comp["company_id"], buyer) is not None
        )
        if not is_member:
            return False, "Lệnh `INTERNAL_ONLY` chỉ dành cho cổ đông hoặc thành viên nội bộ công ty.", {}

    available_order_shares = int(order["shares_count"])
    if buy_shares > available_order_shares:
        return False, f"Lệnh chỉ còn {available_order_shares:,} cổ phần.", {}

    total_cost = buy_shares * int(order["price_per_share"])
    buyer_gold = await get_user_gold(db, buyer)
    if buyer_gold < total_cost:
        return False, f"Không đủ tiền mua cổ phần. Cần {format_gold(total_cost)}, hiện có {format_gold(buyer_gold)}.", {}

    await adjust_user_gold(db, buyer, -total_cost)
    await adjust_user_gold(db, order["seller_id"], total_cost)
    await upsert_shareholding(db, comp["company_id"], order["seller_id"], -buy_shares, 0)
    await upsert_shareholding(db, comp["company_id"], buyer, buy_shares, total_cost, "COMMON")

    remaining = available_order_shares - buy_shares
    if remaining == 0:
        await db.execute(
            "UPDATE share_market_orders SET shares_count = 0, status = 'FILLED' WHERE order_id = ?",
            (order_id,),
        )
    else:
        await db.execute(
            "UPDATE share_market_orders SET shares_count = ? WHERE order_id = ?",
            (remaining, order_id),
        )

    listed_now = False
    if order["market_scope"] == "PUBLIC_IPO" and comp["fsm_state"] == "PRE_IPO":
        ok, _ = await transition_company_fsm(db, comp["company_id"], "PUBLIC_LISTED")
        listed_now = ok

    await db.commit()
    return (
        True,
        f"Đã mua thành công **{buy_shares:,} CP** của **{comp['name']}** với tổng giá **{format_gold(total_cost)}**.",
        {"total_cost": total_cost, "buy_shares": buy_shares, "listed_now": listed_now},
    )


async def launch_hostile_takeover_service(
    db: aiosqlite.Connection,
    raider_id: str,
    company_id: str,
    offered_price_per_share: int,
    target_share_count: int,
) -> tuple[bool, str, dict[str, Any]]:
    """Initiate a 48-hour Hostile Takeover bid against a CTCP, locking escrow gold."""
    raider = str(raider_id)
    comp = await get_company(db, company_id)
    if not comp:
        return False, "Không tìm thấy doanh nghiệp mục tiêu.", {}
    if comp["model_type"] != "CTCP":
        return False, "Chỉ có thể chào mua thù địch đối với **Công Ty Cổ Phần (`CTCP`)**.", {}
    if raider == comp["owner_id"]:
        return False, "Chủ sở hữu hiện tại không thể tự mở cuộc thâu tóm thù địch chính công ty mình.", {}
    if not can_fsm_transition(comp["fsm_state"], "UNDER_TAKEOVER"):
        return False, f"Không thể phát động thâu tóm khi công ty đang ở trạng thái `{comp['fsm_state']}`.", {}
    if await get_active_takeover_bid(db, company_id):
        return False, "Doanh nghiệp này đang có một lệnh chào mua thù địch (`ACQUIRING`) đang diễn ra.", {}
    if offered_price_per_share <= 0 or target_share_count <= 0:
        return False, "Giá chào mua và số lượng cổ phần mục tiêu phải > 0.", {}
    if target_share_count > int(comp["total_shares"]):
        return False, f"Số cổ phần mục tiêu vượt quá tổng cổ phần công ty ({comp['total_shares']:,}).", {}

    escrow_required = offered_price_per_share * target_share_count
    raider_gold = await get_user_gold(db, raider)
    if raider_gold < escrow_required:
        return (
            False,
            f"Không đủ tiền ký quỹ Escrow 48h. Cần {format_gold(escrow_required)}, bạn có {format_gold(raider_gold)}.",
            {},
        )

    await adjust_user_gold(db, raider, -escrow_required)
    expires_at = (utc_now() + datetime.timedelta(hours=48)).isoformat()
    await db.execute(
        """
        INSERT INTO hostile_takeover_bids (
            target_company_id, raider_id, offered_price_per_share,
            target_share_count, acquired_share_count, escrow_vault, status, expires_at
        ) VALUES (?, ?, ?, ?, 0, ?, 'ACQUIRING', ?)
        """,
        (company_id, raider, offered_price_per_share, target_share_count, escrow_required, expires_at),
    )
    await transition_company_fsm(db, company_id, "UNDER_TAKEOVER")
    await db.commit()

    return (
        True,
        (
            f"Đã phát động chiến dịch **Hostile Takeover** vào **{comp['name']}** (`{company_id}`): "
            f"Chào mua **{target_share_count:,} CP** giá **{format_gold(offered_price_per_share)}/CP** (Escrow: {format_gold(escrow_required)})."
        ),
        {"escrow_vault": escrow_required, "expires_at": expires_at},
    )


async def tender_sell_to_raider_service(
    db: aiosqlite.Connection,
    seller_id: str,
    company_id: str,
    shares_to_sell: int,
) -> tuple[bool, str, dict[str, Any]]:
    """Tender shares to an active ACQUIRING hostile takeover bid; transfers ownership if target met."""
    seller = str(seller_id)
    comp = await get_company(db, company_id)
    if not comp:
        return False, "Không tìm thấy doanh nghiệp.", {}

    bid = await get_active_takeover_bid(db, company_id)
    if not bid:
        return False, "Hiện không có chiến dịch chào mua thù địch (`ACQUIRING`) nào đang mở.", {}
    if seller == bid["raider_id"]:
        return False, "Raider không thể tự bán cổ phần cho chính lệnh chào mua của mình.", {}
    if shares_to_sell <= 0:
        return False, "Số cổ phần bán phải > 0.", {}

    holder = await get_shareholding(db, company_id, seller)
    owned = int(holder["shares_count"]) if holder else 0
    if owned < shares_to_sell:
        return False, f"Bạn chỉ sở hữu {owned:,} cổ phần.", {}

    remaining_needed = int(bid["target_share_count"]) - int(bid["acquired_share_count"])
    actual_sold = min(shares_to_sell, remaining_needed)
    if actual_sold <= 0:
        return False, "Chiến dịch chào mua đã đạt đủ số lượng mục tiêu.", {}

    payout = actual_sold * int(bid["offered_price_per_share"])
    if int(bid["escrow_vault"]) < payout:
        return False, "Lỗi ký quỹ Escrow không đủ để thanh toán.", {}

    await upsert_shareholding(db, company_id, seller, -actual_sold, 0)
    await upsert_shareholding(db, company_id, bid["raider_id"], actual_sold, payout, "COMMON")
    await adjust_user_gold(db, seller, payout)

    new_acquired = int(bid["acquired_share_count"]) + actual_sold
    new_escrow = int(bid["escrow_vault"]) - payout
    takeover_completed = new_acquired >= int(bid["target_share_count"])

    if takeover_completed:
        if new_escrow > 0:
            await adjust_user_gold(db, bid["raider_id"], new_escrow)
        await db.execute(
            """
            UPDATE hostile_takeover_bids
            SET acquired_share_count = ?, escrow_vault = 0, status = 'COMPLETED'
            WHERE bid_id = ?
            """,
            (new_acquired, bid["bid_id"]),
        )
        await db.execute(
            "UPDATE companies SET owner_id = ?, ceo_id = ? WHERE company_id = ?",
            (bid["raider_id"], bid["raider_id"], company_id),
        )
        await transition_company_fsm(db, company_id, "ACTIVE")
    else:
        await db.execute(
            """
            UPDATE hostile_takeover_bids
            SET acquired_share_count = ?, escrow_vault = ?
            WHERE bid_id = ?
            """,
            (new_acquired, new_escrow, bid["bid_id"]),
        )

    await db.commit()
    extra = (
        f" 🚨 **THÂU TÓM THÀNH CÔNG!** Quyền Owner & CEO đã chuyển giao cho <@{bid['raider_id']}>."
        if takeover_completed
        else f" (Tiến độ Raid: {new_acquired:,}/{bid['target_share_count']:,} CP)"
    )
    return (
        True,
        f"Bạn đã bán **{actual_sold:,} CP** cho Raider, thu về **{format_gold(payout)}**.{extra}",
        {"actual_sold": actual_sold, "payout": payout, "takeover_completed": takeover_completed},
    )


async def trigger_poison_pill_service(
    db: aiosqlite.Connection,
    actor_id: str,
    company_id: str,
) -> tuple[bool, str, dict[str, Any]]:
    """Owner-only Poison Pill defense: costs 50M Vault, dilutes non-raider shares by 1.5x, refunds escrow."""
    actor = str(actor_id)
    comp = await get_company(db, company_id)
    if not comp:
        return False, "Không tìm thấy doanh nghiệp.", {}
    if actor != comp["owner_id"]:
        return False, "Chỉ **Chủ Sở Hữu (Owner)** mới được quyền kích hoạt Poison Pill.", {}

    bid = await get_active_takeover_bid(db, company_id)
    if not bid:
        return False, "Không có cuộc thâu tóm thù địch (`ACQUIRING`) nào đang diễn ra để phòng vệ.", {}
    if int(comp["vault_balance"]) < POISON_PILL_COST:
        return (
            False,
            f"Két Công Ty cần {format_gold(POISON_PILL_COST)} để kích hoạt Poison Pill (hiện có {format_gold(comp['vault_balance'])}).",
            {},
        )

    await db.execute(
        "UPDATE companies SET vault_balance = vault_balance - ? WHERE company_id = ?",
        (POISON_PILL_COST, company_id),
    )

    async with db.execute(
        "SELECT user_id, shares_count FROM company_shareholders WHERE company_id = ?",
        (company_id,),
    ) as cur:
        holders = [dict(r) for r in await cur.fetchall()]

    new_total_shares = 0
    for h in holders:
        uid = h["user_id"]
        old_shares = int(h["shares_count"])
        if uid == bid["raider_id"]:
            new_shares = old_shares
        else:
            new_shares = math.floor(old_shares * 1.5)
            await db.execute(
                "UPDATE company_shareholders SET shares_count = ? WHERE company_id = ? AND user_id = ?",
                (new_shares, company_id, uid),
            )
        new_total_shares += new_shares

    await db.execute(
        "UPDATE companies SET total_shares = ? WHERE company_id = ?",
        (new_total_shares, company_id),
    )

    escrow_refund = int(bid["escrow_vault"] or 0)
    if escrow_refund > 0:
        await adjust_user_gold(db, bid["raider_id"], escrow_refund)

    await db.execute(
        "UPDATE hostile_takeover_bids SET status = 'POISON_PILL_DEFENDED', escrow_vault = 0 WHERE bid_id = ?",
        (bid["bid_id"],),
    )
    await transition_company_fsm(db, company_id, "ACTIVE")
    await db.commit()

    return (
        True,
        (
            f"🛡️ **POISON PILL THÀNH CÔNG!** Đã chi {format_gold(POISON_PILL_COST)} từ Két, "
            f"pha loãng cổ phần không thuộc Raider lên **1.5x** (Tổng CP mới: {new_total_shares:,}), "
            f"hoàn trả {format_gold(escrow_refund)} Escrow cho Raider và khôi phục trạng thái `ACTIVE`."
        ),
        {"new_total_shares": new_total_shares, "escrow_refund": escrow_refund},
    )


async def dissolve_company_service(
    db: aiosqlite.Connection,
    actor_id: str,
    company_id: str,
) -> tuple[bool, str, dict[str, Any]]:
    """Owner-only dissolution with strict limited liability (personal gold is never seized)."""
    actor = str(actor_id)
    comp = await get_company(db, company_id)
    if not comp:
        return False, "Không tìm thấy doanh nghiệp.", {}
    if actor != comp["owner_id"]:
        return False, "Chỉ **Chủ Sở Hữu (Owner)** mới có quyền giải thể doanh nghiệp.", {}
    if comp["fsm_state"] == "DISSOLVED":
        return False, "Doanh nghiệp đã được giải thể trước đó.", {}

    # Refund active takeover escrow & cancel open share market orders
    bid = await get_active_takeover_bid(db, company_id)
    if bid:
        if int(bid["escrow_vault"] or 0) > 0:
            await adjust_user_gold(db, bid["raider_id"], int(bid["escrow_vault"]))
        await db.execute(
            "UPDATE hostile_takeover_bids SET status = 'CANCELLED', escrow_vault = 0 WHERE bid_id = ?",
            (bid["bid_id"],),
        )
    await db.execute(
        "UPDATE share_market_orders SET status = 'CANCELLED' WHERE company_id = ? AND status = 'OPEN'",
        (company_id,),
    )

    vault = max(0, int(comp["vault_balance"] or 0))
    async with db.execute(
        "SELECT employee_id, user_id, unpaid_wage FROM employees WHERE company_id = ?",
        (company_id,),
    ) as cur:
        emps = [dict(r) for r in await cur.fetchall()]

    total_wage_debt = sum(int(e["unpaid_wage"] or 0) for e in emps)
    wages_paid = 0
    if total_wage_debt > 0 and vault > 0:
        if vault >= total_wage_debt:
            for e in emps:
                owed = int(e["unpaid_wage"] or 0)
                if owed > 0:
                    await adjust_user_gold(db, e["user_id"], owed)
                    wages_paid += owed
            vault -= wages_paid
        else:
            # Limited liability: distribute remaining vault proportionally to workers; owner's personal gold is untouched
            for e in emps:
                owed = int(e["unpaid_wage"] or 0)
                if owed > 0:
                    share_pay = math.floor(vault * (owed / total_wage_debt))
                    if share_pay > 0:
                        await adjust_user_gold(db, e["user_id"], share_pay)
                        wages_paid += share_pay
            vault = 0

    # Any remaining vault goes to shareholders proportionally
    shareholder_payout = 0
    if vault > 0 and int(comp["total_shares"] or 0) > 0:
        async with db.execute(
            "SELECT user_id, shares_count FROM company_shareholders WHERE company_id = ? AND shares_count > 0",
            (company_id,),
        ) as cur:
            holders = [dict(r) for r in await cur.fetchall()]
        total_shares = sum(int(h["shares_count"]) for h in holders)
        if total_shares > 0:
            for h in holders:
                amt = math.floor(vault * (int(h["shares_count"]) / total_shares))
                if amt > 0:
                    await adjust_user_gold(db, h["user_id"], amt)
                    shareholder_payout += amt

    await db.execute("DELETE FROM employees WHERE company_id = ?", (company_id,))
    await db.execute(
        "UPDATE companies SET vault_balance = 0, unpaid_wages = 0 WHERE company_id = ?",
        (company_id,),
    )
    await transition_company_fsm(db, company_id, "DISSOLVED")
    await db.commit()

    return (
        True,
        (
            f"Đã giải thể **{comp['name']}** (`DISSOLVED`). "
            f"Thanh toán nợ lương từ Két: **{format_gold(wages_paid)}**/{format_gold(total_wage_debt)}. "
            f"Hoàn vốn cổ đông: **{format_gold(shareholder_payout)}** (Trách nhiệm hữu hạn được bảo vệ)."
        ),
        {
            "wages_paid": wages_paid,
            "total_wage_debt": total_wage_debt,
            "shareholder_payout": shareholder_payout,
        },
    )


async def create_corporate_debt_service(
    db: aiosqlite.Connection,
    creditor_id: str,
    company_id: str,
    principal_amount: int,
    interest_rate: float,
) -> tuple[bool, str, dict[str, Any]]:
    """Create a 14-day B2P corporate loan transferring creditor gold into company Vault."""
    creditor = str(creditor_id)
    comp = await get_company(db, company_id)
    if not comp:
        return False, "Không tìm thấy doanh nghiệp.", {}
    if comp["fsm_state"] == "DISSOLVED":
        return False, "Không thể cho doanh nghiệp đã giải thể vay vốn.", {}
    if principal_amount < PAR_VALUE:
        return False, f"Khoản vay tối thiểu là {format_gold(PAR_VALUE)}.", {}
    if not (0.0 <= interest_rate <= 100.0):
        return False, "Lãi suất (%) phải nằm trong khoảng 0 - 100%.", {}

    creditor_gold = await get_user_gold(db, creditor)
    if creditor_gold < principal_amount:
        return False, f"Bạn không đủ tiền cho vay. Cần {format_gold(principal_amount)}, hiện có {format_gold(creditor_gold)}.", {}

    due_date = (utc_now() + datetime.timedelta(days=14)).isoformat()
    await adjust_user_gold(db, creditor, -principal_amount)
    await db.execute(
        "UPDATE companies SET vault_balance = vault_balance + ? WHERE company_id = ?",
        (principal_amount, company_id),
    )
    cur = await db.execute(
        """
        INSERT INTO company_corporate_debts (
            company_id, creditor_id, principal_amount, interest_rate, due_date, is_settled
        ) VALUES (?, ?, ?, ?, ?, 0)
        """,
        (company_id, creditor, principal_amount, float(interest_rate), due_date),
    )
    debt_id = cur.lastrowid
    await db.commit()
    return (
        True,
        f"Hợp đồng vay B2P `#{debt_id}` thành công: Đã bơm **{format_gold(principal_amount)}** vào Két **{comp['name']}** (lãi {interest_rate:.1f}%, kỳ hạn 14 ngày).",
        {"debt_id": debt_id, "principal_amount": principal_amount, "due_date": due_date},
    )


async def debt_to_equity_swap_service(
    db: aiosqlite.Connection,
    creditor_id: str,
    debt_id: int,
) -> tuple[bool, str, dict[str, Any]]:
    """Convert an unsettled corporate debt principal into newly minted common shares at par_value."""
    creditor = str(creditor_id)
    async with db.execute(
        "SELECT * FROM company_corporate_debts WHERE debt_id = ? AND is_settled = 0",
        (debt_id,),
    ) as cur:
        row = await cur.fetchone()
    if not row:
        return False, "Không tìm thấy hợp đồng nợ chưa tất toán với mã này.", {}

    debt = dict(row)
    if debt["creditor_id"] != creditor:
        return False, "Chỉ chủ nợ đứng tên hợp đồng mới có quyền thực hiện Hoán Đổi Nợ - Cổ Phần.", {}

    comp = await get_company(db, debt["company_id"])
    if not comp or comp["fsm_state"] == "DISSOLVED":
        return False, "Doanh nghiệp không tồn tại hoặc đã giải thể.", {}

    par_val = int(comp["par_value"] or PAR_VALUE)
    minted_shares = int(debt["principal_amount"]) // par_val
    if minted_shares <= 0:
        return False, f"Giá trị nợ gốc nhỏ hơn mệnh giá 1 cổ phần ({format_gold(par_val)}).", {}

    await upsert_shareholding(
        db,
        comp["company_id"],
        creditor,
        minted_shares,
        int(debt["principal_amount"]),
        "COMMON",
    )
    await db.execute(
        "UPDATE companies SET total_shares = total_shares + ? WHERE company_id = ?",
        (minted_shares, comp["company_id"]),
    )
    await db.execute(
        "UPDATE company_corporate_debts SET is_settled = 1 WHERE debt_id = ?",
        (debt_id,),
    )
    await db.commit()
    return (
        True,
        f"Hoán đổi Nợ ➔ Cổ Phần thành công! Hợp đồng `#{debt_id}` ({format_gold(debt['principal_amount'])}) đã chuyển thành **{minted_shares:,} CP** mới phát hành.",
        {"minted_shares": minted_shares, "company_id": comp["company_id"]},
    )


# ==============================================================================
# 5. DISCORD UI COMPONENTS V2 MODALS
# ==============================================================================


class CompanyCreateModal(ui.Modal, title="Thành Lập Doanh Nghiệp Mới"):
    name_input = ui.TextInput(
        label="Tên Doanh Nghiệp",
        placeholder="VD: Tập Đoàn Công Nghệ Phượng Hoàng",
        min_length=3,
        max_length=50,
    )
    model_input = ui.TextInput(
        label="Mô Hình (TNHH_1TV / TNHH_2TV / CTCP)",
        placeholder="TNHH_1TV hoặc CTCP",
        default="TNHH_1TV",
        max_length=15,
    )
    scale_input = ui.TextInput(
        label="Quy Mô (SME / ENTERPRISE)",
        placeholder="SME (100M-200M) hoặc ENTERPRISE (1B-2B)",
        default="SME",
        max_length=15,
    )
    industry_input = ui.TextInput(
        label="Ngành (FOOD / TECH / LIGHT_IND / HEAVY_IND)",
        placeholder="FOOD, TECH, LIGHT_IND hoặc HEAVY_IND",
        default="FOOD",
        max_length=15,
    )
    capital_input = ui.TextInput(
        label="Vốn Điều Lệ Đăng Ký (gold)",
        placeholder="VD: 100000000",
        default="100000000",
        max_length=20,
    )

    def __init__(self, db: aiosqlite.Connection) -> None:
        super().__init__()
        self.db = db

    async def on_submit(self, interaction: discord.Interaction) -> None:
        capital = parse_positive_int(self.capital_input.value)
        if capital is None:
            await interaction.response.send_message(
                embed=make_error_embed("Dữ Liệu Không Hợp Lệ", "Vốn điều lệ phải là số nguyên dương."),
                ephemeral=True,
            )
            return

        ok, msg, data = await create_company_service(
            self.db,
            str(interaction.user.id),
            self.name_input.value,
            self.model_input.value,
            self.scale_input.value,
            self.industry_input.value,
            capital,
        )
        if not ok:
            await interaction.response.send_message(embed=make_error_embed("Thành Lập Thất Bại", msg), ephemeral=True)
            return

        embed = make_success_embed(
            "Giấy Phép Đăng Ký Kinh Doanh",
            msg,
            fields=[
                ("Mã Doanh Nghiệp", f"`{data['company_id']}`", True),
                ("Vốn Điều Lệ", format_gold(data["capital"]), True),
                ("Thuế Môn Bài", format_gold(data["license_tax"]), True),
                ("Tổng Cổ Phần", f"{data['total_shares']:,} CP", True),
            ],
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class CompanySearchModal(ui.Modal, title="Tra Cứu Doanh Nghiệp"):
    query_input = ui.TextInput(
        label="Mã Công Ty hoặc Tên Công Ty",
        placeholder="VD: CORP-A1B2C3 hoặc Phượng Hoàng",
        max_length=60,
    )

    def __init__(self, db: aiosqlite.Connection) -> None:
        super().__init__()
        self.db = db

    async def on_submit(self, interaction: discord.Interaction) -> None:
        comp = await find_company_by_query(self.db, self.query_input.value)
        if not comp:
            await interaction.response.send_message(
                embed=make_error_embed("Không Tìm Thấy", "Không tìm thấy doanh nghiệp khớp với từ khóa tra cứu."),
                ephemeral=True,
            )
            return
        view = await CompanyDashboardV2.resolve_role_view(self.db, comp["company_id"], interaction.user.id)
        await interaction.response.send_message(view=view, ephemeral=True)


class CompanyHireModal(ui.Modal, title="Tuyển Dụng Nhân Sự"):
    target_input = ui.TextInput(
        label="Người Lao Động (@Mention hoặc User ID)",
        placeholder="VD: @nguoi_choi hoặc 1135806949527670835",
        max_length=40,
    )
    role_title_input = ui.TextInput(
        label="Chức Danh Công Việc",
        placeholder="VD: Kỹ Sư Phần Mềm / Công Nhân Dây Chuyền",
        max_length=40,
    )
    wage_input = ui.TextInput(
        label="Lương Mỗi Ca (v)",
        placeholder="VD: 50000",
        max_length=15,
    )

    def __init__(self, db: aiosqlite.Connection, company_id: str) -> None:
        super().__init__()
        self.db = db
        self.company_id = company_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        uid = extract_user_id_from_mention(self.target_input.value)
        wage = parse_positive_int(self.wage_input.value)
        if not uid or wage is None:
            await interaction.response.send_message(
                embed=make_error_embed("Dữ Liệu Không Hợp Lệ", "User ID/@Mention hoặc mức lương ca không hợp lệ."),
                ephemeral=True,
            )
            return

        ok, msg, _ = await hire_employee_service(
            self.db,
            str(interaction.user.id),
            self.company_id,
            uid,
            self.role_title_input.value,
            wage,
        )
        embed = make_success_embed("Hợp Đồng Lao Động", msg) if ok else make_error_embed("Tuyển Dụng Thất Bại", msg)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class CompanyAppointAccountantModal(ui.Modal, title="Bổ Nhiệm Kế Toán Trưởng"):
    target_input = ui.TextInput(
        label="Nhân Sự Đảm Nhiệm (@Mention hoặc User ID)",
        placeholder="Không được trùng Owner, CEO hoặc Công nhân",
        max_length=40,
    )

    def __init__(self, db: aiosqlite.Connection, company_id: str) -> None:
        super().__init__()
        self.db = db
        self.company_id = company_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        uid = extract_user_id_from_mention(self.target_input.value)
        if not uid:
            await interaction.response.send_message(
                embed=make_error_embed("Dữ Liệu Không Hợp Lệ", "Vui lòng nhập @Mention hoặc Discord User ID hợp lệ."),
                ephemeral=True,
            )
            return

        ok, msg, _ = await appoint_accountant_service(self.db, str(interaction.user.id), self.company_id, uid)
        embed = make_success_embed("Quyết Định Bổ Nhiệm", msg) if ok else make_error_embed("Bổ Nhiệm Thất Bại", msg)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class CompanyDividendModal(ui.Modal, title="Phê Duyệt Chia Cổ Tức"):
    div_input = ui.TextInput(
        label="Cổ Tức Mỗi Cổ Phần (gold/CP)",
        placeholder="VD: 1000",
        max_length=15,
    )

    def __init__(self, db: aiosqlite.Connection, company_id: str) -> None:
        super().__init__()
        self.db = db
        self.company_id = company_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        div_val = parse_positive_int(self.div_input.value)
        if div_val is None:
            await interaction.response.send_message(
                embed=make_error_embed("Dữ Liệu Không Hợp Lệ", "Mức cổ tức phải là số nguyên dương."),
                ephemeral=True,
            )
            return

        ok, msg, _ = await distribute_dividend_service(self.db, str(interaction.user.id), self.company_id, div_val)
        embed = make_success_embed("Biên Bản Chia Cổ Tức", msg) if ok else make_error_embed("Chia Cổ Tức Thất Bại", msg)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class CompanyIPOModal(ui.Modal, title="Nộp Hồ Sơ Niêm Yết IPO (Phí 100M)"):
    shares_input = ui.TextInput(
        label="Số Cổ Phần Chào Bán IPO",
        placeholder="VD: 20000",
        max_length=15,
    )
    price_input = ui.TextInput(
        label="Giá Chào Bán Mỗi Cổ Phần (gold)",
        placeholder="VD: 15000",
        max_length=15,
    )

    def __init__(self, db: aiosqlite.Connection, company_id: str) -> None:
        super().__init__()
        self.db = db
        self.company_id = company_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        shares = parse_positive_int(self.shares_input.value)
        price = parse_positive_int(self.price_input.value)
        if shares is None or price is None:
            await interaction.response.send_message(
                embed=make_error_embed("Dữ Liệu Không Hợp Lệ", "Số cổ phần và giá IPO phải là số nguyên dương."),
                ephemeral=True,
            )
            return

        ok, msg, _ = await launch_ipo_service(self.db, str(interaction.user.id), self.company_id, shares, price)
        embed = make_success_embed("Hồ Sơ IPO Được Chấp Thuận", msg) if ok else make_error_embed("IPO Thất Bại", msg)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class CompanyShareSellModal(ui.Modal, title="Chào Bán Cổ Phần Nội Bộ (72h)"):
    shares_input = ui.TextInput(
        label="Số Lượng Cổ Phần Muốn Bán",
        placeholder="VD: 1000",
        max_length=15,
    )
    price_input = ui.TextInput(
        label="Giá Mỗi Cổ Phần (gold)",
        placeholder="VD: 12000",
        max_length=15,
    )

    def __init__(self, db: aiosqlite.Connection, company_id: str) -> None:
        super().__init__()
        self.db = db
        self.company_id = company_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        shares = parse_positive_int(self.shares_input.value)
        price = parse_positive_int(self.price_input.value)
        if shares is None or price is None:
            await interaction.response.send_message(
                embed=make_error_embed("Dữ Liệu Không Hợp Lệ", "Số cổ phần và giá bán phải là số nguyên dương."),
                ephemeral=True,
            )
            return

        ok, msg, _ = await list_internal_share_order_service(
            self.db, str(interaction.user.id), self.company_id, shares, price
        )
        embed = make_success_embed("Lệnh Chào Bán Nội Bộ", msg) if ok else make_error_embed("Đặt Lệnh Thất Bại", msg)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class CompanyShareBuyModal(ui.Modal, title="Mua Cổ Phần Trên Sàn Giao Dịch"):
    order_id_input = ui.TextInput(
        label="Mã Lệnh Chào Bán (Order ID)",
        placeholder="Xem Order ID ở Bảng Lệnh Sàn Cổ Phần",
        max_length=15,
    )
    shares_input = ui.TextInput(
        label="Số Lượng Cổ Phần Muốn Mua",
        placeholder="VD: 500",
        max_length=15,
    )

    def __init__(self, db: aiosqlite.Connection) -> None:
        super().__init__()
        self.db = db

    async def on_submit(self, interaction: discord.Interaction) -> None:
        order_id = parse_positive_int(self.order_id_input.value)
        shares = parse_positive_int(self.shares_input.value)
        if order_id is None or shares is None:
            await interaction.response.send_message(
                embed=make_error_embed("Dữ Liệu Không Hợp Lệ", "Order ID và số cổ phần phải là số nguyên dương."),
                ephemeral=True,
            )
            return

        ok, msg, _ = await buy_share_order_service(self.db, str(interaction.user.id), order_id, shares)
        embed = make_success_embed("Khớp Lệnh Cổ Phần", msg) if ok else make_error_embed("Mua Cổ Phần Thất Bại", msg)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class CompanyBuyRawModal(ui.Modal, title="Nhập Nguyên Liệu & Bảo Trì Máy"):
    raw_input = ui.TextInput(
        label="Số Lượng Nguyên Vật Liệu Nhập",
        placeholder="VD: 20 (nhập 0 nếu chỉ bảo trì)",
        default="10",
        max_length=12,
    )
    repair_blocks_input = ui.TextInput(
        label="Số Gói Bảo Trì (+10% độ bền / 5,000 gold)",
        placeholder="VD: 2 (tức +20% độ bền = 10,000 gold)",
        default="0",
        max_length=10,
    )

    def __init__(self, db: aiosqlite.Connection, company_id: str) -> None:
        super().__init__()
        self.db = db
        self.company_id = company_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw_str = self.raw_input.value.strip().replace(",", "")
        rep_str = self.repair_blocks_input.value.strip().replace(",", "")
        if not raw_str.isdigit() or not rep_str.isdigit():
            await interaction.response.send_message(
                embed=make_error_embed("Dữ Liệu Không Hợp Lệ", "Số lượng phải là số nguyên không âm."),
                ephemeral=True,
            )
            return

        ok, msg, _ = await buy_raw_and_repair_service(
            self.db,
            str(interaction.user.id),
            self.company_id,
            int(raw_str),
            int(rep_str),
        )
        embed = make_success_embed("Phiếu Nhập Kho & Bảo Trì", msg) if ok else make_error_embed("Nghiệp Vụ Thất Bại", msg)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class CompanyRaidModal(ui.Modal, title="Chào Mua Thù Địch (Hostile Takeover)"):
    price_input = ui.TextInput(
        label="Giá Chào Mua Mỗi Cổ Phần (gold)",
        placeholder="VD: 18000",
        max_length=15,
    )
    target_shares_input = ui.TextInput(
        label="Số Cổ Phần Mục Tiêu (thường > 50% tổng CP)",
        placeholder="VD: 50001",
        max_length=15,
    )

    def __init__(self, db: aiosqlite.Connection, company_id: str) -> None:
        super().__init__()
        self.db = db
        self.company_id = company_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        price = parse_positive_int(self.price_input.value)
        target_shares = parse_positive_int(self.target_shares_input.value)
        if price is None or target_shares is None:
            await interaction.response.send_message(
                embed=make_error_embed("Dữ Liệu Không Hợp Lệ", "Giá chào mua và số cổ phần mục tiêu phải > 0."),
                ephemeral=True,
            )
            return

        ok, msg, _ = await launch_hostile_takeover_service(
            self.db, str(interaction.user.id), self.company_id, price, target_shares
        )
        if not ok:
            await interaction.response.send_message(embed=make_error_embed("Raid Thất Bại", msg), ephemeral=True)
            return

        alert_view = await HostileTakeoverAlertV2.build(self.db, self.company_id)
        await interaction.response.send_message(view=alert_view)


class CompanyTenderSellModal(ui.Modal, title="Bán Cổ Phần Cho Raider"):
    shares_input = ui.TextInput(
        label="Số Lượng Cổ Phần Bán Cho Raider",
        placeholder="VD: 5000",
        max_length=15,
    )

    def __init__(self, db: aiosqlite.Connection, company_id: str) -> None:
        super().__init__()
        self.db = db
        self.company_id = company_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        shares = parse_positive_int(self.shares_input.value)
        if shares is None:
            await interaction.response.send_message(
                embed=make_error_embed("Dữ Liệu Không Hợp Lệ", "Số cổ phần phải là số nguyên dương."),
                ephemeral=True,
            )
            return

        ok, msg, _ = await tender_sell_to_raider_service(
            self.db, str(interaction.user.id), self.company_id, shares
        )
        embed = make_success_embed("Chuyển Nhượng Tender Offer", msg) if ok else make_error_embed("Giao Dịch Thất Bại", msg)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class CompanyDebtBorrowModal(ui.Modal, title="Hợp Đồng Cho Vay Doanh Nghiệp (B2P)"):
    amount_input = ui.TextInput(
        label="Số Tiền Cho Vay (gold)",
        placeholder="VD: 5000000",
        max_length=15,
    )
    rate_input = ui.TextInput(
        label="Lãi Suất Hợp Đồng (%)",
        placeholder="VD: 12.5",
        default="10.0",
        max_length=10,
    )

    def __init__(self, db: aiosqlite.Connection, company_id: str) -> None:
        super().__init__()
        self.db = db
        self.company_id = company_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        amount = parse_positive_int(self.amount_input.value)
        try:
            rate = float(self.rate_input.value.strip())
        except ValueError:
            rate = -1.0

        if amount is None or rate < 0:
            await interaction.response.send_message(
                embed=make_error_embed("Dữ Liệu Không Hợp Lệ", "Số tiền vay hoặc lãi suất không hợp lệ."),
                ephemeral=True,
            )
            return

        ok, msg, _ = await create_corporate_debt_service(
            self.db, str(interaction.user.id), self.company_id, amount, rate
        )
        embed = make_success_embed("Hợp Đồng Tín Dụng B2P", msg) if ok else make_error_embed("Cho Vay Thất Bại", msg)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class CompanyDebtSwapModal(ui.Modal, title="Hoán Đổi Nợ - Cổ Phần (Debt Swap)"):
    debt_id_input = ui.TextInput(
        label="Mã Hợp Đồng Nợ (Debt ID)",
        placeholder="Nhập Debt ID chưa tất toán của bạn",
        max_length=15,
    )

    def __init__(self, db: aiosqlite.Connection) -> None:
        super().__init__()
        self.db = db

    async def on_submit(self, interaction: discord.Interaction) -> None:
        debt_id = parse_positive_int(self.debt_id_input.value)
        if debt_id is None:
            await interaction.response.send_message(
                embed=make_error_embed("Dữ Liệu Không Hợp Lệ", "Mã hợp đồng nợ phải là số nguyên dương."),
                ephemeral=True,
            )
            return

        ok, msg, _ = await debt_to_equity_swap_service(self.db, str(interaction.user.id), debt_id)
        embed = make_success_embed("Hoán Đổi Nợ Thành Vốn", msg) if ok else make_error_embed("Hoán Đổi Thất Bại", msg)
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ==============================================================================
# 6. DISCORD UI COMPONENTS V2 VIEWS (STRICT RBAC & LAYOUTVIEW)
# ==============================================================================


class _BaseCorpLayoutView(ui.LayoutView):
    """Base Components V2 LayoutView enforcing author interaction_check."""

    def __init__(self, db: aiosqlite.Connection, author_id: Optional[int], *, timeout: float = 300.0) -> None:
        super().__init__(timeout=timeout)
        self.db = db
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.author_id is not None and interaction.user.id != self.author_id:
            await interaction.response.send_message(
                embed=make_error_embed("Không Có Quyền Tương Tác", "Bảng điều khiển này thuộc phiên làm việc của người chơi khác."),
                ephemeral=True,
            )
            return False
        return True


class CompanyMacroGuideV2(_BaseCorpLayoutView):
    """2-page toggle Macro Political Economy & Corporate Law Guide."""

    def __init__(self, db: aiosqlite.Connection, author_id: int, page: int = 1) -> None:
        super().__init__(db, author_id, timeout=300.0)
        self.page = 1 if page not in (1, 2) else page
        self._render()

    def _render(self) -> None:
        self.clear_items()
        if self.page == 1:
            body = (
                "## 📚 Cẩm Nang Kinh Tế Chính Trị & Doanh Nghiệp (Trang 1/2)\n"
                "### 1. Công Thức Giá Trị Hàng Hóa Mác-xít ($W = c + v + m$)\n"
                "- **c (Tư bản bất biến):** Nguyên vật liệu (`raw_cost`) + Khấu hao máy móc (`depreciation`).\n"
                "- **v (Tư bản khả biến):** Tiền lương trả cho sức lao động mỗi ca (`daily_wage`).\n"
                "- **m (Giá trị thặng dư):** $\\lfloor v \\times \\text{surplus\\_mult} \\rfloor$.\n"
                "- **Tỷ suất bóc lột:** $m' = m / v$. Khi $m/v > 5.0$ hoặc công ty nợ lương (`DELINQUENT`), công nhân có quyền **Đình Công**.\n\n"
                "### 2. Ngành Nghề & Thanh Toán\n"
                "- **FOOD:** Thanh toán tức thì (`IMMEDIATE`), hệ số `0.6x`, lao động phổ thông.\n"
                "- **TECH:** Thanh toán tức thì, hệ số `3.0x`, **bắt buộc 100% Chứng chỉ Trí Tuệ**.\n"
                "- **LIGHT_IND:** Công nợ **Net 60** (60 phút), hệ số `1.2x`.\n"
                "- **HEAVY_IND:** Công nợ **Net 90** (90 phút), hệ số `2.5x` (**x2.0** nếu có Kỹ Sư Trưởng)."
            )
        else:
            body = (
                "## 📚 Cẩm Nang Kinh Tế Chính Trị & Doanh Nghiệp (Trang 2/2)\n"
                "### 3. Phân Tách 4 Vai Trò Độc Lập (RBAC)\n"
                "- **HĐQT (Owner/CEO):** Tuyển dụng, bổ nhiệm Kế Toán, chia cổ tức, IPO, Poison Pill, giải thể. **Cấm** tự vào ca/đình công hay trực tiếp nhập nguyên liệu.\n"
                "- **Kế Toán (Accountant):** Độc quyền nhập TLSX, bảo trì máy, đối soát Net 60/90 và giải ngân trả lương.\n"
                "- **Người Lao Động (Worker):** Vào ca sản xuất tạo $W$, bỏ phiếu đình công (đạt >= 50% -> `ON_STRIKE`), thôi việc.\n"
                "- **Nhà Đầu Cơ / Chủ Nợ (Speculator):** Chào mua thù địch (Raid `CTCP`), mua cổ phần sàn, cho vay B2P và Hoán đổi Nợ - Cổ phần.\n\n"
                "### 4. M&A, Poison Pill & Trách Nhiệm Hữu Hạn\n"
                "- **Hostile Takeover:** Khóa Escrow 48h để thu gom cổ phần CTCP; đủ mục tiêu sẽ tiếp quản `owner_id` & `ceo_id`.\n"
                "- **Poison Pill:** Owner chi `50M` từ Két pha loãng cổ phần không thuộc Raider `1.5x` và đẩy lùi cuộc thâu tóm.\n"
                "- **Trách Nhiệm Hữu Hạn:** Khi giải thể, nợ lương chỉ trả trong phạm vi Két Công Ty, không đụng vào tiền cá nhân."
            )

        btn_toggle = ui.Button(
            label="Trang 2: M&A & RBAC ➡️" if self.page == 1 else "⬅️ Trang 1: Kinh Tế Mác-xít",
            style=discord.ButtonStyle.primary,
        )
        btn_toggle.callback = self._on_toggle_page

        btn_hub = ui.Button(label="🏠 Về Hub", style=discord.ButtonStyle.secondary)
        btn_hub.callback = self._on_back_hub

        self.add_item(
            ui.Container(
                ui.TextDisplay(body),
                ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                ui.ActionRow(btn_toggle, btn_hub),
                accent_colour=discord.Colour.blurple(),
            )
        )

    async def _on_toggle_page(self, interaction: discord.Interaction) -> None:
        self.page = 2 if self.page == 1 else 1
        self._render()
        await interaction.response.edit_message(view=self)

    async def _on_back_hub(self, interaction: discord.Interaction) -> None:
        hub = await CompanyHubV2.build(self.db, interaction.user.id)
        await interaction.response.edit_message(view=hub)


class IntellectualExamView(_BaseCorpLayoutView):
    """5-question randomized Marxian Economics & Corporate Finance certification quiz."""

    def __init__(self, db: aiosqlite.Connection, author_id: int) -> None:
        super().__init__(db, author_id, timeout=300.0)
        self.questions = random.sample(EXAM_QUESTION_BANK, 5)
        self.current_idx = 0
        self.score = 0
        self.feedback_lines: list[str] = []
        self._render()

    def _render(self) -> None:
        self.clear_items()
        if self.current_idx < len(self.questions):
            q = self.questions[self.current_idx]
            opts_text = "\n".join(f"**{chr(65 + idx)}.** {opt}" for idx, opt in enumerate(q["options"]))
            content = (
                f"## 🎓 Kỳ Thi Chứng Chỉ Lao Động Trí Tuệ ({self.current_idx + 1}/5)\n"
                f"Điểm hiện tại: **{self.score}/5** (Cần >= **4/5** để đạt `INTELLECTUAL_LABOR`)\n\n"
                f"**Câu {self.current_idx + 1}:** {q['question']}\n\n"
                f"{opts_text}"
            )
            buttons = []
            for idx in range(4):
                btn = ui.Button(label=f"Đáp án {chr(65 + idx)}", style=discord.ButtonStyle.primary)
                btn.callback = self._make_answer_callback(idx)
                buttons.append(btn)

            btn_hub = ui.Button(label="🏠 Thoát Về Hub", style=discord.ButtonStyle.secondary)
            btn_hub.callback = self._on_back_hub

            self.add_item(
                ui.Container(
                    ui.TextDisplay(content),
                    ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                    ui.ActionRow(*buttons),
                    ui.ActionRow(btn_hub),
                    accent_colour=discord.Colour.blue(),
                )
            )
        else:
            passed = self.score >= 4
            status_header = "🏆 CHÚC MỪNG: ĐẠT CHỨNG CHỈ `INTELLECTUAL_LABOR`" if passed else "❌ CHƯA ĐẠT CHỨNG CHỈ"
            summary = "\n".join(self.feedback_lines)
            content = (
                f"## {status_header}\n"
                f"Kết quả bài thi: **{self.score}/5** câu trả lời chính xác.\n\n"
                f"### Chi tiết đáp án:\n{summary}"
            )
            btn_retry = ui.Button(label="🔄 Thi Lại", style=discord.ButtonStyle.primary)
            btn_retry.callback = self._on_retry
            btn_hub = ui.Button(label="🏠 Về Hub", style=discord.ButtonStyle.secondary)
            btn_hub.callback = self._on_back_hub

            self.add_item(
                ui.Container(
                    ui.TextDisplay(content),
                    ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                    ui.ActionRow(btn_retry, btn_hub),
                    accent_colour=discord.Colour.green() if passed else discord.Colour.red(),
                )
            )

    def _make_answer_callback(self, chosen_idx: int):
        async def _callback(interaction: discord.Interaction) -> None:
            q = self.questions[self.current_idx]
            correct_idx = int(q["answer_index"])
            if chosen_idx == correct_idx:
                self.score += 1
                self.feedback_lines.append(f"- Câu {self.current_idx + 1}: ✅ Chính xác ({chr(65 + correct_idx)})")
            else:
                self.feedback_lines.append(
                    f"- Câu {self.current_idx + 1}: ❌ Chọn {chr(65 + chosen_idx)}, đúng là {chr(65 + correct_idx)} — *{q['explanation']}*"
                )
            self.current_idx += 1

            if self.current_idx >= len(self.questions) and self.score >= 4:
                uid = str(interaction.user.id)
                await ensure_user(self.db, uid)
                await self.db.execute(
                    """
                    INSERT INTO intellectual_certificates (user_id, cert_type, score, issued_at, is_valid)
                    VALUES (?, 'INTELLECTUAL_LABOR', ?, ?, 1)
                    ON CONFLICT(user_id) DO UPDATE SET
                        cert_type = excluded.cert_type,
                        score = excluded.score,
                        issued_at = excluded.issued_at,
                        is_valid = 1
                    """,
                    (uid, self.score, utc_now().isoformat()),
                )
                await self.db.commit()

            self._render()
            await interaction.response.edit_message(view=self)

        return _callback

    async def _on_retry(self, interaction: discord.Interaction) -> None:
        fresh = IntellectualExamView(self.db, interaction.user.id)
        await interaction.response.edit_message(view=fresh)

    async def _on_back_hub(self, interaction: discord.Interaction) -> None:
        hub = await CompanyHubV2.build(self.db, interaction.user.id)
        await interaction.response.edit_message(view=hub)


class CompanyHubV2(_BaseCorpLayoutView):
    """Entry Hub for Corporate Organization FSM & Marxian Political Economy."""

    def __init__(
        self,
        db: aiosqlite.Connection,
        author_id: int,
        user_gold: int,
        has_cert: bool,
        related_count: int,
        total_companies: int,
    ) -> None:
        super().__init__(db, author_id, timeout=300.0)
        cert_badge = "✅ Đã có (`INTELLECTUAL_LABOR`)" if has_cert else "❌ Chưa có"
        header = (
            "## 🏛️ TRUNG TÂM KINH TẾ DOANH NGHIỆP & M&A\n"
            f"- **Tài khoản cá nhân:** {format_gold(user_gold)}\n"
            f"- **Chứng chỉ Trí Tuệ:** {cert_badge}\n"
            f"- **Doanh nghiệp liên quan của bạn:** `{related_count}` | **Tổng công ty trên sàn:** `{total_companies}`\n\n"
            "*Hệ thống vận hành theo Máy Trạng Thái Hữu Hạn (FSM), Kinh tế Chính trị Mác-xít ($W = c + v + m$) và phân tách 4 vai trò nghiêm ngặt.*"
        )

        btn_create = ui.Button(label="🏗️ Thành Lập", style=discord.ButtonStyle.success)
        btn_create.callback = self._on_create

        btn_mine = ui.Button(label="🏢 Công Ty Của Tôi", style=discord.ButtonStyle.primary)
        btn_mine.callback = self._on_my_company

        btn_exam = ui.Button(label="🎓 Thi Chứng Chỉ", style=discord.ButtonStyle.primary)
        btn_exam.callback = self._on_exam

        btn_guide = ui.Button(label="📘 Cẩm Nang Vĩ Mô", style=discord.ButtonStyle.secondary)
        btn_guide.callback = self._on_guide

        btn_search = ui.Button(label="🔍 Tra Cứu", style=discord.ButtonStyle.secondary)
        btn_search.callback = self._on_search

        self.add_item(
            ui.Container(
                ui.TextDisplay(header),
                ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                ui.ActionRow(btn_create, btn_mine, btn_exam),
                ui.ActionRow(btn_guide, btn_search),
                accent_colour=discord.Colour.gold(),
            )
        )

    @classmethod
    async def build(cls, db: aiosqlite.Connection, user_id: int) -> "CompanyHubV2":
        uid = str(user_id)
        gold = await get_user_gold(db, uid)
        has_cert = await has_valid_intellectual_cert(db, uid)
        related = await get_user_related_companies(db, uid)
        async with db.execute("SELECT COUNT(*) FROM companies") as cur:
            total_companies = int((await cur.fetchone())[0])
        return cls(db, user_id, gold, has_cert, len(related), total_companies)

    async def _on_create(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(CompanyCreateModal(self.db))

    async def _on_my_company(self, interaction: discord.Interaction) -> None:
        companies = await get_user_related_companies(self.db, str(interaction.user.id))
        if not companies:
            await interaction.response.send_message(
                embed=make_error_embed(
                    "Chưa Có Doanh Nghiệp",
                    "Bạn chưa sở hữu, điều hành, làm kế toán, làm việc hay nắm cổ phần ở doanh nghiệp nào. Hãy nhấn **Thành Lập** hoặc **Tra Cứu**.",
                ),
                ephemeral=True,
            )
            return

        if len(companies) == 1:
            view = await CompanyDashboardV2.resolve_role_view(
                self.db, companies[0]["company_id"], interaction.user.id
            )
            await interaction.response.edit_message(view=view)
            return

        picker = CompanyDashboardV2(self.db, interaction.user.id, companies)
        await interaction.response.edit_message(view=picker)

    async def _on_exam(self, interaction: discord.Interaction) -> None:
        exam = IntellectualExamView(self.db, interaction.user.id)
        await interaction.response.edit_message(view=exam)

    async def _on_guide(self, interaction: discord.Interaction) -> None:
        guide = CompanyMacroGuideV2(self.db, interaction.user.id, page=1)
        await interaction.response.edit_message(view=guide)

    async def _on_search(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(CompanySearchModal(self.db))


class CompanyDashboardV2(_BaseCorpLayoutView):
    """Router & Multi-Company Selector V2 view routing strictly by user's role."""

    def __init__(self, db: aiosqlite.Connection, author_id: int, companies: list[dict[str, Any]]) -> None:
        super().__init__(db, author_id, timeout=300.0)
        lines = ["## 🗂️ Chọn Doanh Nghiệp Để Điều Hướng Theo Vai Trò"]
        for comp in companies[:8]:
            lines.append(
                f"- **{comp['name']}** (`{comp['company_id']}`) | `{comp['model_type']}` | `{comp['fsm_state']}` | Két: {format_gold(comp['vault_balance'])}"
            )

        rows: list[ui.ActionRow] = []
        current_btns: list[ui.Button] = []
        for comp in companies[:8]:
            btn = ui.Button(label=f"Vào {comp['company_id']}", style=discord.ButtonStyle.primary)
            btn.callback = self._make_open_callback(comp["company_id"])
            current_btns.append(btn)
            if len(current_btns) == 4:
                rows.append(ui.ActionRow(*current_btns))
                current_btns = []
        if current_btns:
            rows.append(ui.ActionRow(*current_btns))

        btn_hub = ui.Button(label="🏠 Về Hub", style=discord.ButtonStyle.secondary)
        btn_hub.callback = self._on_back_hub
        rows.append(ui.ActionRow(btn_hub))

        self.add_item(
            ui.Container(
                ui.TextDisplay("\n".join(lines)),
                ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                *rows,
                accent_colour=discord.Colour.blurple(),
            )
        )

    def _make_open_callback(self, company_id: str):
        async def _callback(interaction: discord.Interaction) -> None:
            view = await CompanyDashboardV2.resolve_role_view(self.db, company_id, interaction.user.id)
            await interaction.response.edit_message(view=view)

        return _callback

    async def _on_back_hub(self, interaction: discord.Interaction) -> None:
        hub = await CompanyHubV2.build(self.db, interaction.user.id)
        await interaction.response.edit_message(view=hub)

    @staticmethod
    async def resolve_role_view(
        db: aiosqlite.Connection,
        company_id: str,
        user_id: int,
    ) -> _BaseCorpLayoutView:
        """Strictly route user to Board, Accountant, Worker, or Speculator panel based on RBAC."""
        role = await get_user_role_in_company(db, company_id, str(user_id))
        if role == "BOARD":
            return await CompanyBoardDashboardV2.build(db, company_id, user_id)
        if role == "ACCOUNTANT":
            return await CompanyAccountantDashboardV2.build(db, company_id, user_id)
        if role == "WORKER":
            return await CompanyWorkerPanelV2.build(db, company_id, user_id)
        return await CompanySpeculatorMarketPanelV2.build(db, company_id, user_id)


class CompanyBoardDashboardV2(_BaseCorpLayoutView):
    """Owner / CEO Only Board Dashboard (strictly separated from Accountant & Worker actions)."""

    def __init__(
        self,
        db: aiosqlite.Connection,
        author_id: int,
        comp: dict[str, Any],
        fac: Optional[dict[str, Any]],
        emp_count: int,
        active_bid: Optional[dict[str, Any]],
    ) -> None:
        super().__init__(db, author_id, timeout=300.0)
        self.company_id = comp["company_id"]
        fsm_label, accent = FSM_DISPLAY.get(comp["fsm_state"], (comp["fsm_state"], discord.Color.default()))
        acc_text = f"<@{comp['accountant_id']}>" if comp["accountant_id"] else "*Chưa bổ nhiệm*"
        durability = fac["durability"] if fac else 0
        raw_stock = fac["raw_materials_stock"] if fac else 0

        takeover_banner = ""
        if active_bid:
            takeover_banner = (
                f"\n\n🚨 **CẢNH BÁO THÂU TÓM THÙ ĐỊCH:** Raider <@{active_bid['raider_id']}> "
                f"đang chào mua `{active_bid['acquired_share_count']:,}/{active_bid['target_share_count']:,}` CP "
                f"giá **{format_gold(active_bid['offered_price_per_share'])}/CP**!"
            )

        body = (
            f"## 👔 HỘI ĐỒNG QUẢN TRỊ — {comp['name']} (`{comp['company_id']}`)\n"
            f"- **Trạng thái FSM:** {fsm_label}\n"
            f"- **Mô hình / Quy mô / Ngành:** `{comp['model_type']}` | `{comp['scale_type']}` | `{comp['industry_type']}`\n"
            f"- **Chủ sở hữu:** <@{comp['owner_id']}> | **Kế toán:** {acc_text} | **Nhân sự:** `{emp_count}`\n"
            f"- **Két Công Ty:** {format_gold(comp['vault_balance'])} | **Nợ lương:** {format_gold(comp['unpaid_wages'])}\n"
            f"- **Tổng cổ phần:** `{comp['total_shares']:,} CP` | **Kho TLSX:** `{raw_stock}` NL, độ bền `{durability}%`"
            f"{takeover_banner}"
        )

        is_dissolved = comp["fsm_state"] == "DISSOLVED"
        is_owner = str(author_id) == comp["owner_id"]

        btn_hire = ui.Button(label="👥 Tuyển Dụng", style=discord.ButtonStyle.primary, disabled=is_dissolved)
        btn_hire.callback = self._on_hire

        btn_acc = ui.Button(label="🧮 Bổ Nhiệm Kế Toán", style=discord.ButtonStyle.primary, disabled=is_dissolved)
        btn_acc.callback = self._on_appoint_acc

        btn_div = ui.Button(
            label="💸 Chia Cổ Tức",
            style=discord.ButtonStyle.success,
            disabled=comp["fsm_state"] in ("DELINQUENT", "ON_STRIKE", "DISSOLVED"),
        )
        btn_div.callback = self._on_dividend

        btn_ipo = ui.Button(
            label="🔔 Hồ Sơ IPO",
            style=discord.ButtonStyle.primary,
            disabled=not (comp["model_type"] == "CTCP" and comp["fsm_state"] == "ACTIVE"),
        )
        btn_ipo.callback = self._on_ipo

        btn_poison = ui.Button(
            label="🛡️ Poison Pill",
            style=discord.ButtonStyle.danger,
            disabled=not (is_owner and active_bid is not None),
        )
        btn_poison.callback = self._on_poison_pill

        btn_sell_share = ui.Button(label="📜 Bán Cổ Phần", style=discord.ButtonStyle.secondary, disabled=is_dissolved)
        btn_sell_share.callback = self._on_sell_share

        btn_dissolve = ui.Button(
            label="⚖️ Giải Thể",
            style=discord.ButtonStyle.danger,
            disabled=not is_owner or is_dissolved,
        )
        btn_dissolve.callback = self._on_dissolve

        btn_market = ui.Button(label="📈 Thị Trường / Sàn", style=discord.ButtonStyle.secondary)
        btn_market.callback = self._on_open_market

        btn_refresh = ui.Button(label="🔄 Làm Mới", style=discord.ButtonStyle.secondary)
        btn_refresh.callback = self._on_refresh

        btn_hub = ui.Button(label="🏠 Về Hub", style=discord.ButtonStyle.secondary)
        btn_hub.callback = self._on_hub

        self.add_item(
            ui.Container(
                ui.TextDisplay(body),
                ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                ui.ActionRow(btn_hire, btn_acc, btn_div, btn_ipo),
                ui.ActionRow(btn_poison, btn_sell_share, btn_dissolve),
                ui.ActionRow(btn_market, btn_refresh, btn_hub),
                accent_colour=accent,
            )
        )

    @classmethod
    async def build(cls, db: aiosqlite.Connection, company_id: str, user_id: int) -> "CompanyBoardDashboardV2":
        comp = await get_company(db, company_id)
        assert comp is not None
        fac = await get_facility(db, company_id)
        async with db.execute("SELECT COUNT(*) FROM employees WHERE company_id = ?", (company_id,)) as cur:
            emp_count = int((await cur.fetchone())[0])
        active_bid = await get_active_takeover_bid(db, company_id)
        return cls(db, user_id, comp, fac, emp_count, active_bid)

    async def _ensure_board_access(self, interaction: discord.Interaction) -> bool:
        role = await get_user_role_in_company(self.db, self.company_id, str(interaction.user.id))
        if role != "BOARD":
            await interaction.response.send_message(
                embed=make_error_embed("Từ Chối Truy Cập (RBAC)", "Chỉ Chủ Sở Hữu / CEO mới được sử dụng Bảng HĐQT."),
                ephemeral=True,
            )
            return False
        return True

    async def _on_hire(self, interaction: discord.Interaction) -> None:
        if await self._ensure_board_access(interaction):
            await interaction.response.send_modal(CompanyHireModal(self.db, self.company_id))

    async def _on_appoint_acc(self, interaction: discord.Interaction) -> None:
        if await self._ensure_board_access(interaction):
            await interaction.response.send_modal(CompanyAppointAccountantModal(self.db, self.company_id))

    async def _on_dividend(self, interaction: discord.Interaction) -> None:
        if await self._ensure_board_access(interaction):
            await interaction.response.send_modal(CompanyDividendModal(self.db, self.company_id))

    async def _on_ipo(self, interaction: discord.Interaction) -> None:
        if await self._ensure_board_access(interaction):
            await interaction.response.send_modal(CompanyIPOModal(self.db, self.company_id))

    async def _on_sell_share(self, interaction: discord.Interaction) -> None:
        if await self._ensure_board_access(interaction):
            await interaction.response.send_modal(CompanyShareSellModal(self.db, self.company_id))

    async def _on_poison_pill(self, interaction: discord.Interaction) -> None:
        if not await self._ensure_board_access(interaction):
            return
        ok, msg, _ = await trigger_poison_pill_service(self.db, str(interaction.user.id), self.company_id)
        embed = make_success_embed("Phòng Vệ Poison Pill", msg) if ok else make_error_embed("Poison Pill Thất Bại", msg)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _on_dissolve(self, interaction: discord.Interaction) -> None:
        if not await self._ensure_board_access(interaction):
            return
        ok, msg, _ = await dissolve_company_service(self.db, str(interaction.user.id), self.company_id)
        embed = make_success_embed("Quyết Định Giải Thể", msg) if ok else make_error_embed("Giải Thể Thất Bại", msg)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _on_open_market(self, interaction: discord.Interaction) -> None:
        market = await CompanySpeculatorMarketPanelV2.build(self.db, self.company_id, interaction.user.id)
        await interaction.response.edit_message(view=market)

    async def _on_refresh(self, interaction: discord.Interaction) -> None:
        fresh = await CompanyBoardDashboardV2.build(self.db, self.company_id, interaction.user.id)
        await interaction.response.edit_message(view=fresh)

    async def _on_hub(self, interaction: discord.Interaction) -> None:
        hub = await CompanyHubV2.build(self.db, interaction.user.id)
        await interaction.response.edit_message(view=hub)


class CompanyAccountantDashboardV2(_BaseCorpLayoutView):
    """Accountant-only financial authority dashboard."""

    def __init__(
        self,
        db: aiosqlite.Connection,
        author_id: int,
        comp: dict[str, Any],
        fac: Optional[dict[str, Any]],
        pending_invoices_total: int,
        pending_invoices_count: int,
    ) -> None:
        super().__init__(db, author_id, timeout=300.0)
        self.company_id = comp["company_id"]
        fsm_label, accent = FSM_DISPLAY.get(comp["fsm_state"], (comp["fsm_state"], discord.Color.default()))
        ind_cfg = INDUSTRY_INFO[comp["industry_type"]]

        body = (
            f"## 🧮 BÀN LÀM VIỆC KẾ TOÁN — {comp['name']} (`{comp['company_id']}`)\n"
            f"- **Trạng thái FSM:** {fsm_label}\n"
            f"- **Ngành:** `{comp['industry_type']}` (Đơn giá nhập NL: {format_gold(ind_cfg['raw_cost'])})\n"
            f"- **Số dư Két Công Ty:** {format_gold(comp['vault_balance'])}\n"
            f"- **Tổng nợ lương phải trả:** {format_gold(comp['unpaid_wages'])}\n"
            f"- **Công nợ Net 60/90 chờ thu:** `{pending_invoices_count}` hóa đơn ({format_gold(pending_invoices_total)})\n"
            f"- **Kho TLSX:** Nguyên liệu `{fac['raw_materials_stock'] if fac else 0}` | Độ bền `{fac['durability'] if fac else 0}%`"
        )

        is_dissolved = comp["fsm_state"] == "DISSOLVED"
        btn_buy = ui.Button(label="📦 Nhập TLSX", style=discord.ButtonStyle.primary, disabled=is_dissolved)
        btn_buy.callback = self._on_buy_raw

        btn_net = ui.Button(label="🧾 Đối Soát Net 60/90", style=discord.ButtonStyle.success, disabled=is_dissolved)
        btn_net.callback = self._on_reconcile

        btn_pay = ui.Button(label="💵 Chi Trả Lương", style=discord.ButtonStyle.success, disabled=is_dissolved)
        btn_pay.callback = self._on_pay_wages

        btn_report = ui.Button(label="📊 Báo Cáo Tài Chính", style=discord.ButtonStyle.primary)
        btn_report.callback = self._on_report

        btn_refresh = ui.Button(label="🔄 Làm Mới", style=discord.ButtonStyle.secondary)
        btn_refresh.callback = self._on_refresh

        btn_hub = ui.Button(label="🏠 Về Hub", style=discord.ButtonStyle.secondary)
        btn_hub.callback = self._on_hub

        self.add_item(
            ui.Container(
                ui.TextDisplay(body),
                ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                ui.ActionRow(btn_buy, btn_net, btn_pay, btn_report),
                ui.ActionRow(btn_refresh, btn_hub),
                accent_colour=accent,
            )
        )

    @classmethod
    async def build(cls, db: aiosqlite.Connection, company_id: str, user_id: int) -> "CompanyAccountantDashboardV2":
        comp = await get_company(db, company_id)
        assert comp is not None
        fac = await get_facility(db, company_id)
        async with db.execute(
            "SELECT COUNT(*) AS cnt, COALESCE(SUM(amount), 0) AS amt FROM invoices_receivable WHERE company_id = ? AND settled = 0",
            (company_id,),
        ) as cur:
            inv_row = await cur.fetchone()
        return cls(db, user_id, comp, fac, int(inv_row["amt"] or 0), int(inv_row["cnt"] or 0))

    async def _ensure_accountant_access(self, interaction: discord.Interaction) -> bool:
        role = await get_user_role_in_company(self.db, self.company_id, str(interaction.user.id))
        if role != "ACCOUNTANT":
            await interaction.response.send_message(
                embed=make_error_embed("Từ Chối Truy Cập (RBAC)", "Chỉ Kế Toán được bổ nhiệm mới được thực hiện nghiệp vụ này."),
                ephemeral=True,
            )
            return False
        return True

    async def _on_buy_raw(self, interaction: discord.Interaction) -> None:
        if await self._ensure_accountant_access(interaction):
            await interaction.response.send_modal(CompanyBuyRawModal(self.db, self.company_id))

    async def _on_reconcile(self, interaction: discord.Interaction) -> None:
        if not await self._ensure_accountant_access(interaction):
            return
        ok, msg, _ = await reconcile_invoices_service(self.db, str(interaction.user.id), self.company_id)
        embed = make_success_embed("Đối Soát Công Nợ Net 60/90", msg) if ok else make_error_embed("Chưa Thể Tất Toán", msg)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _on_pay_wages(self, interaction: discord.Interaction) -> None:
        if not await self._ensure_accountant_access(interaction):
            return
        ok, msg, _ = await pay_unpaid_wages_service(self.db, str(interaction.user.id), self.company_id)
        embed = make_success_embed("Giải Ngân Nợ Lương", msg) if ok else make_error_embed("Chi Trả Lương Thất Bại", msg)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _on_report(self, interaction: discord.Interaction) -> None:
        if not await self._ensure_accountant_access(interaction):
            return
        comp = await get_company(self.db, self.company_id)
        fac = await get_facility(self.db, self.company_id)
        async with db_exec(
            self.db,
            "SELECT COALESCE(SUM(amount), 0) AS amt, COUNT(*) AS cnt FROM invoices_receivable WHERE company_id = ? AND settled = 0",
            (self.company_id,),
        ) as inv:
            pending_amt = int(inv["amt"] or 0)
            pending_cnt = int(inv["cnt"] or 0)

        assert comp is not None
        c_sum = int(comp["total_capital_c"] or 0)
        v_sum = int(comp["total_wages_v"] or 0)
        m_sum = int(comp["total_surplus_m"] or 0)
        w_sum = c_sum + v_sum + m_sum
        mv_ratio = (m_sum / v_sum) if v_sum > 0 else 0.0

        embed = make_corp_embed(
            title=f"📊 BÁO CÁO TÀI CHÍNH MÁC-XÍT — {comp['name']}",
            description=f"Mã DN: `{comp['company_id']}` | Trạng thái: `{comp['fsm_state']}`",
            color=discord.Color.blue(),
            fields=[
                ("Tư bản bất biến (c)", format_gold(c_sum), True),
                ("Tư bản khả biến / Lương (v)", format_gold(v_sum), True),
                ("Giá trị thặng dư (m)", format_gold(m_sum), True),
                ("Tổng giá trị hàng hóa (W = c+v+m)", format_gold(w_sum), True),
                ("Tỷ suất bóc lột (m/v)", f"{mv_ratio:.2f} ({mv_ratio*100:.1f}%)", True),
                ("Số dư Két Công Ty", format_gold(comp["vault_balance"]), True),
                ("Phải thu Net 60/90", f"{format_gold(pending_amt)} ({pending_cnt} hóa đơn)", True),
                ("Nợ lương tồn đọng", format_gold(comp["unpaid_wages"]), True),
                (
                    "Kho vật tư & Thành phẩm",
                    f"NL: `{fac['raw_materials_stock'] if fac else 0}` | TP: `{fac['finished_goods_stock'] if fac else 0}` | Độ bền: `{fac['durability'] if fac else 0}%`",
                    True,
                ),
            ],
            footer="Báo Cáo Kế Toán Chuẩn Mác-xít",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _on_refresh(self, interaction: discord.Interaction) -> None:
        fresh = await CompanyAccountantDashboardV2.build(self.db, self.company_id, interaction.user.id)
        await interaction.response.edit_message(view=fresh)

    async def _on_hub(self, interaction: discord.Interaction) -> None:
        hub = await CompanyHubV2.build(self.db, interaction.user.id)
        await interaction.response.edit_message(view=hub)


async def db_exec(db: aiosqlite.Connection, sql: str, params: tuple[Any, ...]):
    """Context manager helper returning a single fetched dict row."""

    class _RowCtx:
        def __init__(self) -> None:
            self._row: dict[str, Any] = {}

        async def __aenter__(self) -> dict[str, Any]:
            async with db.execute(sql, params) as cur:
                row = await cur.fetchone()
            self._row = dict(row) if row else {}
            return self._row

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    return _RowCtx()


class CompanyWorkerPanelV2(_BaseCorpLayoutView):
    """Contracted Employee panel for production shifts, strike votes, wage status, and resignation."""

    def __init__(
        self,
        db: aiosqlite.Connection,
        author_id: int,
        comp: dict[str, Any],
        emp: dict[str, Any],
        fac: Optional[dict[str, Any]],
        has_cert: bool,
    ) -> None:
        super().__init__(db, author_id, timeout=300.0)
        self.company_id = comp["company_id"]
        fsm_label, accent = FSM_DISPLAY.get(comp["fsm_state"], (comp["fsm_state"], discord.Color.default()))
        strike_text = "🔴 ĐANG ĐÌNH CÔNG" if int(emp["is_on_strike"]) == 1 else "🟢 Sẵn sàng lao động"
        cert_text = "✅ Có (`INTELLECTUAL_LABOR`)" if has_cert else "❌ Chưa có"

        body = (
            f"## 👷 BẢNG CÔNG NHÂN — {comp['name']} (`{comp['company_id']}`)\n"
            f"- **Trạng thái công ty:** {fsm_label}\n"
            f"- **Chức danh của bạn:** **{emp['role_title']}** ({strike_text})\n"
            f"- **Lương mỗi ca (v):** {format_gold(emp['daily_wage'])} | **Lương đang bị nợ:** {format_gold(emp['unpaid_wage'])}\n"
            f"- **Chứng chỉ Trí Tuệ:** {cert_text}\n"
            f"- **Tình trạng dây chuyền:** Nguyên liệu `{fac['raw_materials_stock'] if fac else 0}` | Độ bền `{fac['durability'] if fac else 0}%`"
        )

        is_dissolved = comp["fsm_state"] == "DISSOLVED"
        btn_shift = ui.Button(label="⚒️ Vào Ca Lao Động", style=discord.ButtonStyle.success, disabled=is_dissolved)
        btn_shift.callback = self._on_work_shift

        btn_strike = ui.Button(label="✊ Bỏ Phiếu Đình Công", style=discord.ButtonStyle.danger, disabled=is_dissolved)
        btn_strike.callback = self._on_strike

        btn_wage = ui.Button(label="💰 Xem Số Dư Lương", style=discord.ButtonStyle.primary)
        btn_wage.callback = self._on_check_wage

        btn_resign = ui.Button(label="🚪 Xin Thôi Việc", style=discord.ButtonStyle.secondary)
        btn_resign.callback = self._on_resign

        btn_refresh = ui.Button(label="🔄 Làm Mới", style=discord.ButtonStyle.secondary)
        btn_refresh.callback = self._on_refresh

        btn_hub = ui.Button(label="🏠 Về Hub", style=discord.ButtonStyle.secondary)
        btn_hub.callback = self._on_hub

        self.add_item(
            ui.Container(
                ui.TextDisplay(body),
                ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                ui.ActionRow(btn_shift, btn_strike, btn_wage, btn_resign),
                ui.ActionRow(btn_refresh, btn_hub),
                accent_colour=accent,
            )
        )

    @classmethod
    async def build(cls, db: aiosqlite.Connection, company_id: str, user_id: int) -> "CompanyWorkerPanelV2":
        comp = await get_company(db, company_id)
        emp = await get_employee(db, company_id, str(user_id))
        assert comp is not None and emp is not None
        fac = await get_facility(db, company_id)
        has_cert = await has_valid_intellectual_cert(db, str(user_id))
        return cls(db, user_id, comp, emp, fac, has_cert)

    async def _ensure_worker_access(self, interaction: discord.Interaction) -> bool:
        role = await get_user_role_in_company(self.db, self.company_id, str(interaction.user.id))
        if role != "WORKER":
            await interaction.response.send_message(
                embed=make_error_embed("Từ Chối Truy Cập (RBAC)", "Bạn không còn là nhân sự hợp đồng tại công ty này."),
                ephemeral=True,
            )
            return False
        return True

    async def _on_work_shift(self, interaction: discord.Interaction) -> None:
        if not await self._ensure_worker_access(interaction):
            return
        ok, msg, data = await execute_production_shift_service(self.db, str(interaction.user.id), self.company_id)
        if not ok:
            await interaction.response.send_message(embed=make_error_embed("Không Thể Vào Ca", msg), ephemeral=True)
            return

        wage_status = (
            f"✅ Đã nhận ngay {format_gold(data['v'])}"
            if data["wage_paid"]
            else f"⚠️ Công ty mất thanh khoản! Ghi nợ lương +{format_gold(data['v'])}"
        )
        settlement_info = (
            f"Cộng ngay {format_gold(data['W'])} vào Két"
            if data["settlement_type"] == "IMMEDIATE"
            else f"Treo hóa đơn `{data['settlement_type']}` ({format_gold(data['W'])})"
        )
        bonus_note = " (Kỹ Sư Trưởng x2.0)" if data["bonus_applied"] else ""
        embed = make_success_embed(
            "Biên Bản Ca Sản Xuất (W = c + v + m)",
            f"Sản lượng hoàn tất{bonus_note}.",
            fields=[
                ("Tư bản bất biến (c)", format_gold(data["c"]), True),
                ("Lương công nhân (v)", format_gold(data["v"]), True),
                ("Giá trị thặng dư (m)", format_gold(data["m"]), True),
                ("Tổng giá trị (W)", format_gold(data["W"]), True),
                ("Tỷ suất bóc lột (m/v)", f"{data['exploitation_rate']:.2f}", True),
                ("Thanh toán doanh thu", settlement_info, True),
                ("Trạng thái lương", wage_status, False),
            ],
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _on_strike(self, interaction: discord.Interaction) -> None:
        if not await self._ensure_worker_access(interaction):
            return
        ok, msg, _ = await toggle_strike_service(self.db, str(interaction.user.id), self.company_id)
        embed = make_success_embed("Bỏ Phiếu Đình Công", msg) if ok else make_error_embed("Đình Công Bị Từ Chối", msg)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _on_check_wage(self, interaction: discord.Interaction) -> None:
        if not await self._ensure_worker_access(interaction):
            return
        emp = await get_employee(self.db, self.company_id, str(interaction.user.id))
        gold = await get_user_gold(self.db, str(interaction.user.id))
        assert emp is not None
        embed = make_corp_embed(
            title="💰 Phiếu Lương Người Lao Động",
            description=f"Nhân sự: <@{interaction.user.id}>",
            color=discord.Color.gold(),
            fields=[
                ("Lương mỗi ca (v)", format_gold(emp["daily_wage"]), True),
                ("Lương bị nợ chưa trả", format_gold(emp["unpaid_wage"]), True),
                ("Số dư cá nhân hiện tại", format_gold(gold), True),
            ],
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _on_resign(self, interaction: discord.Interaction) -> None:
        if not await self._ensure_worker_access(interaction):
            return
        ok, msg, _ = await resign_employee_service(self.db, str(interaction.user.id), self.company_id)
        embed = make_success_embed("Chấm Dứt Hợp Đồng", msg) if ok else make_error_embed("Lỗi", msg)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _on_refresh(self, interaction: discord.Interaction) -> None:
        emp = await get_employee(self.db, self.company_id, str(interaction.user.id))
        if not emp:
            hub = await CompanyHubV2.build(self.db, interaction.user.id)
            await interaction.response.edit_message(view=hub)
            return
        fresh = await CompanyWorkerPanelV2.build(self.db, self.company_id, interaction.user.id)
        await interaction.response.edit_message(view=fresh)

    async def _on_hub(self, interaction: discord.Interaction) -> None:
        hub = await CompanyHubV2.build(self.db, interaction.user.id)
        await interaction.response.edit_message(view=hub)


class HostileTakeoverAlertV2(_BaseCorpLayoutView):
    """Public/Interactive Hostile Takeover alert card with Tender Sell & Owner-only Poison Pill."""

    def __init__(
        self,
        db: aiosqlite.Connection,
        comp: dict[str, Any],
        bid: Optional[dict[str, Any]],
        author_id: Optional[int] = None,
    ) -> None:
        super().__init__(db, author_id, timeout=300.0)
        self.company_id = comp["company_id"]
        self.owner_id_str = comp["owner_id"]

        if bid:
            countdown = format_countdown(parse_iso_dt(bid["expires_at"]))
            body = (
                f"## 🚨 BÁO ĐỘNG THÂU TÓM THÙ ĐỊCH (HOSTILE TAKEOVER) — {comp['name']}\n"
                f"- **Mã DN:** `{comp['company_id']}` | **Raider:** <@{bid['raider_id']}>\n"
                f"- **Giá chào mua (Tender Offer):** **{format_gold(bid['offered_price_per_share'])}/CP**\n"
                f"- **Tiến độ thu gom:** `{bid['acquired_share_count']:,} / {bid['target_share_count']:,} CP`\n"
                f"- **Quỹ Escrow còn lại:** {format_gold(bid['escrow_vault'])} | **Thời hạn:** `{countdown}`\n\n"
                "*Cổ đông có thể bán cổ phần trực tiếp cho Raider. Chỉ Chủ Sở Hữu (Owner) mới kích hoạt được **Poison Pill** (50M gold từ Két).*"
            )
            btn_tender = ui.Button(label="🤝 Bán Cho Raider", style=discord.ButtonStyle.success)
            btn_tender.callback = self._on_tender_sell

            btn_poison = ui.Button(label="🛡️ Poison Pill (Owner)", style=discord.ButtonStyle.danger)
            btn_poison.callback = self._on_poison_pill

            row = ui.ActionRow(btn_tender, btn_poison)
            accent = discord.Colour.purple()
        else:
            body = (
                f"## 🕊️ KHÔNG CÓ CHIẾN DỊCH THÂU TÓM ĐANG MỞ — {comp['name']}\n"
                f"Doanh nghiệp `{comp['company_id']}` hiện không có lệnh chào mua thù địch (`ACQUIRING`)."
            )
            btn_back = ui.Button(label="📈 Quay Lại Thị Trường", style=discord.ButtonStyle.secondary)
            btn_back.callback = self._on_back_market
            row = ui.ActionRow(btn_back)
            accent = discord.Colour.greyple()

        self.add_item(
            ui.Container(
                ui.TextDisplay(body),
                ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                row,
                accent_colour=accent,
            )
        )

    @classmethod
    async def build(
        cls,
        db: aiosqlite.Connection,
        company_id: str,
        author_id: Optional[int] = None,
    ) -> "HostileTakeoverAlertV2":
        comp = await get_company(db, company_id)
        assert comp is not None
        bid = await get_active_takeover_bid(db, company_id)
        return cls(db, comp, bid, author_id=author_id)

    async def _on_tender_sell(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(CompanyTenderSellModal(self.db, self.company_id))

    async def _on_poison_pill(self, interaction: discord.Interaction) -> None:
        if str(interaction.user.id) != self.owner_id_str:
            await interaction.response.send_message(
                embed=make_error_embed("Từ Chối Quyền Lực", "Chỉ Chủ Sở Hữu (`owner_id`) mới được kích hoạt Poison Pill."),
                ephemeral=True,
            )
            return
        ok, msg, _ = await trigger_poison_pill_service(self.db, str(interaction.user.id), self.company_id)
        embed = make_success_embed("Phòng Vệ Poison Pill", msg) if ok else make_error_embed("Poison Pill Thất Bại", msg)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _on_back_market(self, interaction: discord.Interaction) -> None:
        market = await CompanySpeculatorMarketPanelV2.build(self.db, self.company_id, interaction.user.id)
        await interaction.response.edit_message(view=market)


class CompanySpeculatorMarketPanelV2(_BaseCorpLayoutView):
    """Public Market / Speculator / Creditor / Raider Panel."""

    def __init__(
        self,
        db: aiosqlite.Connection,
        author_id: int,
        comp: dict[str, Any],
        user_shares: int,
        active_bid: Optional[dict[str, Any]],
        open_orders: list[dict[str, Any]],
        user_debts: list[dict[str, Any]],
    ) -> None:
        super().__init__(db, author_id, timeout=300.0)
        self.company_id = comp["company_id"]
        fsm_label, accent = FSM_DISPLAY.get(comp["fsm_state"], (comp["fsm_state"], discord.Color.default()))

        orders_lines = (
            "\n".join(
                f"- Order `#{o['order_id']}` [{o['market_scope']}]: **{o['shares_count']:,} CP** @ {format_gold(o['price_per_share'])}/CP"
                for o in open_orders[:5]
            )
            if open_orders
            else "*Không có lệnh chào bán cổ phần đang mở.*"
        )

        debts_lines = (
            "\n".join(
                f"- Debt `#{d['debt_id']}`: Gốc **{format_gold(d['principal_amount'])}** | Lãi `{d['interest_rate']:.1f}%`"
                for d in user_debts[:4]
            )
            if user_debts
            else "*Bạn không nắm hợp đồng nợ chưa tất toán nào tại đây.*"
        )

        bid_summary = (
            f"🚨 Đang bị Raid bởi <@{active_bid['raider_id']}> @ {format_gold(active_bid['offered_price_per_share'])}/CP "
            f"({active_bid['acquired_share_count']:,}/{active_bid['target_share_count']:,} CP)"
            if active_bid
            else "Không có lệnh thâu tóm đang mở."
        )

        body = (
            f"## 📈 THỊ TRƯỜNG VỐN & M&A — {comp['name']} (`{comp['company_id']}`)\n"
            f"- **Mô hình / Trạng thái:** `{comp['model_type']}` | {fsm_label}\n"
            f"- **Tổng CP:** `{comp['total_shares']:,}` (Mệnh giá: {format_gold(comp['par_value'])}) | **Cổ phần bạn giữ:** `{user_shares:,} CP`\n"
            f"- **Chào mua thù địch:** {bid_summary}\n\n"
            f"### Sổ Lệnh Cổ Phần Đang Mở\n{orders_lines}\n\n"
            f"### Hợp Đồng Tín Dụng B2P Của Bạn\n{debts_lines}"
        )

        is_dissolved = comp["fsm_state"] == "DISSOLVED"
        btn_raid = ui.Button(
            label="⚔️ Chào Mua Thù Địch (Raid)",
            style=discord.ButtonStyle.danger,
            disabled=is_dissolved or comp["model_type"] != "CTCP" or active_bid is not None,
        )
        btn_raid.callback = self._on_raid

        btn_tender = ui.Button(
            label="🤝 Bán Cho Raider",
            style=discord.ButtonStyle.success,
            disabled=active_bid is None or user_shares <= 0,
        )
        btn_tender.callback = self._on_tender

        btn_buy_order = ui.Button(
            label="🛒 Mua Cổ Phần",
            style=discord.ButtonStyle.primary,
            disabled=is_dissolved or not open_orders,
        )
        btn_buy_order.callback = self._on_buy_share

        btn_lend = ui.Button(label="🏦 Cho Vay B2P", style=discord.ButtonStyle.primary, disabled=is_dissolved)
        btn_lend.callback = self._on_lend

        btn_swap = ui.Button(
            label="🔁 Hoán Đổi Nợ - Cổ Phần",
            style=discord.ButtonStyle.success,
            disabled=is_dissolved or not user_debts,
        )
        btn_swap.callback = self._on_swap

        btn_alert = ui.Button(
            label="🚨 Thẻ Báo Động Raid",
            style=discord.ButtonStyle.secondary,
            disabled=active_bid is None,
        )
        btn_alert.callback = self._on_view_alert

        btn_refresh = ui.Button(label="🔄 Làm Mới", style=discord.ButtonStyle.secondary)
        btn_refresh.callback = self._on_refresh

        btn_hub = ui.Button(label="🏠 Về Hub", style=discord.ButtonStyle.secondary)
        btn_hub.callback = self._on_hub

        self.add_item(
            ui.Container(
                ui.TextDisplay(body),
                ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                ui.ActionRow(btn_raid, btn_tender, btn_buy_order),
                ui.ActionRow(btn_lend, btn_swap, btn_alert),
                ui.ActionRow(btn_refresh, btn_hub),
                accent_colour=accent,
            )
        )

    @classmethod
    async def build(cls, db: aiosqlite.Connection, company_id: str, user_id: int) -> "CompanySpeculatorMarketPanelV2":
        comp = await get_company(db, company_id)
        assert comp is not None
        holder = await get_shareholding(db, company_id, str(user_id))
        user_shares = int(holder["shares_count"]) if holder else 0
        active_bid = await get_active_takeover_bid(db, company_id)

        async with db.execute(
            "SELECT * FROM share_market_orders WHERE company_id = ? AND status = 'OPEN' ORDER BY order_id DESC",
            (company_id,),
        ) as cur:
            open_orders = [dict(r) for r in await cur.fetchall()]

        async with db.execute(
            "SELECT * FROM company_corporate_debts WHERE company_id = ? AND creditor_id = ? AND is_settled = 0 ORDER BY debt_id DESC",
            (company_id, str(user_id)),
        ) as cur:
            user_debts = [dict(r) for r in await cur.fetchall()]

        return cls(db, user_id, comp, user_shares, active_bid, open_orders, user_debts)

    async def _on_raid(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(CompanyRaidModal(self.db, self.company_id))

    async def _on_tender(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(CompanyTenderSellModal(self.db, self.company_id))

    async def _on_buy_share(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(CompanyShareBuyModal(self.db))

    async def _on_lend(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(CompanyDebtBorrowModal(self.db, self.company_id))

    async def _on_swap(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(CompanyDebtSwapModal(self.db))

    async def _on_view_alert(self, interaction: discord.Interaction) -> None:
        alert = await HostileTakeoverAlertV2.build(self.db, self.company_id, author_id=interaction.user.id)
        await interaction.response.edit_message(view=alert)

    async def _on_refresh(self, interaction: discord.Interaction) -> None:
        fresh = await CompanySpeculatorMarketPanelV2.build(self.db, self.company_id, interaction.user.id)
        await interaction.response.edit_message(view=fresh)

    async def _on_hub(self, interaction: discord.Interaction) -> None:
        hub = await CompanyHubV2.build(self.db, interaction.user.id)
        await interaction.response.edit_message(view=hub)


# ==============================================================================
# 7. COG & EXTENSION ENTRYPOINT
# ==============================================================================


class CorporateEconomyCog(commands.Cog):
    """Cog exposing Corporate Organization FSM, Marxian Economy & M&A Engine."""

    def __init__(self, bot: commands.Bot) -> None:
        self.client = bot
        self.bot = bot

    @commands.hybrid_command(
        name="company",
        aliases=["corp", "congty"],
        description="Mở Trung Tâm Doanh Nghiệp, Kinh Tế Chính Trị & Thâu Tóm M&A",
    )
    async def company(self, ctx: commands.Context) -> None:
        await ensure_corporate_tables(self.client.db)  # type: ignore[attr-defined]
        hub = await CompanyHubV2.build(self.client.db, ctx.author.id)  # type: ignore[attr-defined]
        await ctx.send(view=hub, ephemeral=ctx.interaction is not None)


async def setup(bot: commands.Bot) -> None:
    """Register CorporateEconomyCog and ensure aiosqlite WAL database schema exists."""
    if getattr(bot, "db", None) is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(base_dir, "corporate_economy.db")
        bot.db = await aiosqlite.connect(db_path)  # type: ignore[attr-defined]
        bot.db.row_factory = aiosqlite.Row  # type: ignore[attr-defined]
    await ensure_corporate_tables(bot.db)  # type: ignore[attr-defined]
    await bot.add_cog(CorporateEconomyCog(bot))
