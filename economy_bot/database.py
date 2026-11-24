# economy_bot/database.py
import os
import json
import sqlite3
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'data.json')
DB_FILE = os.path.join(BASE_DIR, 'economy.db')
QUIZ_FILE = os.path.join(BASE_DIR, 'quiz_questions.json')

owner_id = "1135806949527670835"
subowner_id = ["1138020979348606996"]

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
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    money INTEGER NOT NULL DEFAULT 0,
                    data TEXT NOT NULL DEFAULT '{}'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS system_data (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            _migrate_from_json_if_needed(conn)


def _migrate_from_json_if_needed(conn):
    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    sys_count = conn.execute("SELECT COUNT(*) FROM system_data").fetchone()[0]
    if (user_count > 0 or sys_count > 0) or not os.path.exists(DATA_FILE):
        return

    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
    except Exception as e:
        print(f"⚠️ [DATABASE] Không thể đọc {DATA_FILE} để migrate sang SQLite: {e}")
        return

    if not isinstance(raw_data, dict) or not raw_data:
        return

    sys_dict = raw_data.get("SYSTEM_DATA")
    if isinstance(sys_dict, dict):
        for k, v in sys_dict.items():
            conn.execute(
                "INSERT OR REPLACE INTO system_data (key, value) VALUES (?, ?)",
                (str(k), json.dumps(v, ensure_ascii=False))
            )

    migrated_users = 0
    for uid, udata in raw_data.items():
        if uid == "SYSTEM_DATA" or not isinstance(udata, dict):
            continue
        money = int(udata.get("money", 0) or 0)
        conn.execute(
            "INSERT OR REPLACE INTO users (user_id, money, data) VALUES (?, ?, ?)",
            (str(uid), money, json.dumps(udata, ensure_ascii=False))
        )
        migrated_users += 1

    print(f"✅ [DATABASE] Đã tự động chuyển {migrated_users} người chơi từ data.json sang SQLite ({os.path.basename(DB_FILE)}).")


def load_data():
    init_db()
    result = {}
    with _db_lock:
        with _get_connection() as conn:
            sys_rows = conn.execute("SELECT key, value FROM system_data").fetchall()
            if sys_rows:
                sys_dict = {}
                for row in sys_rows:
                    try:
                        sys_dict[row["key"]] = json.loads(row["value"])
                    except json.JSONDecodeError:
                        sys_dict[row["key"]] = row["value"]
                result["SYSTEM_DATA"] = sys_dict

            user_rows = conn.execute("SELECT user_id, money, data FROM users").fetchall()
            for row in user_rows:
                try:
                    udata = json.loads(row["data"])
                    if not isinstance(udata, dict):
                        udata = {}
                except json.JSONDecodeError:
                    udata = {}
                if "money" not in udata:
                    udata["money"] = row["money"]
                if "inventory" not in udata:
                    udata["inventory"] = {}
                result[row["user_id"]] = udata
    return result


def save_data(data):
    if not isinstance(data, dict):
        return
    init_db()
    with _db_lock:
        with _get_connection() as conn:
            sys_dict = data.get("SYSTEM_DATA")
            if isinstance(sys_dict, dict):
                existing_sys = {r["key"] for r in conn.execute("SELECT key FROM system_data").fetchall()}
                current_sys = {str(k) for k in sys_dict.keys()}
                for stale_key in existing_sys - current_sys:
                    conn.execute("DELETE FROM system_data WHERE key = ?", (stale_key,))
                for k, v in sys_dict.items():
                    conn.execute(
                        "INSERT INTO system_data (key, value) VALUES (?, ?) "
                        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                        (str(k), json.dumps(v, ensure_ascii=False))
                    )
            else:
                conn.execute("DELETE FROM system_data")

            existing_users = {r["user_id"] for r in conn.execute("SELECT user_id FROM users").fetchall()}
            current_users = {
                str(k) for k, v in data.items()
                if k != "SYSTEM_DATA" and isinstance(v, dict)
            }
            for stale_uid in existing_users - current_users:
                conn.execute("DELETE FROM users WHERE user_id = ?", (stale_uid,))

            for uid, udata in data.items():
                if uid == "SYSTEM_DATA" or not isinstance(udata, dict):
                    continue
                money = int(udata.get("money", 0) or 0)
                conn.execute(
                    "INSERT INTO users (user_id, money, data) VALUES (?, ?, ?) "
                    "ON CONFLICT(user_id) DO UPDATE SET money = excluded.money, data = excluded.data",
                    (str(uid), money, json.dumps(udata, ensure_ascii=False))
                )


def get_user_count() -> int:
    init_db()
    with _db_lock:
        with _get_connection() as conn:
            return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


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
