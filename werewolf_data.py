# werewolf_data.py
import os
import discord

ASSETS_DIR = "/home/container/assets"

ROLES_INFO = {
    "wolf": {"name": "Ma Sói", "emoji": "🐺", "side": "evil", "desc": "Đêm đến chọn duy nhất 1 người để cắn chết cùng phe Sói."},
    "alpha_wolf": {"name": "Sói Đầu Đàn", "emoji": "🐺👑", "side": "evil", "desc": "Trùm Ma Sói đột biến! Có sức mạnh lãnh đạo phe Sói, phiếu bầu tính gấp đôi."},
    "seer": {"name": "Tiên Tri", "emoji": "🔮", "side": "good", "desc": "Chỉ soi ban ngày! Soi người chơi xem thuộc Phe Thiện hay Phe Ác (Trăng Tròn soi 2 người, Trăng Non bị phế)."},
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

def get_asset_file(image_name: str):
    path = os.path.join(ASSETS_DIR, image_name)
    if os.path.exists(path):
        return discord.File(path, filename=image_name)
    return None

async def send_fancy_event_message(ctx, embed: discord.Embed, image_name: str = None, view: discord.ui.View = None):
    if image_name:
        file = get_asset_file(image_name)
        if file:
            embed.set_image(url=f"attachment://{image_name}")
            return await ctx.channel.send(embed=embed, file=file, view=view)
    return await ctx.channel.send(embed=embed, view=view)

def calculate_wolf_count(setting_str: str, total_players: int) -> int:
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