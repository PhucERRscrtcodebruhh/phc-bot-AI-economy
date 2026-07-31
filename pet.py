# pet.py
import random
import datetime
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Select

from constants import KESLING_ICON, PET_SHOP, price, emoji_icon, ore, FISH_POOL
from AIphcbot import get_user_data, save_data, player_inventory, add_ore_with_quality, get_total_ore_count


# ==================== CẤU HÌNH ĐỒ ĂN & PET ====================

PET_FOODS = {
    "pate_meo": {
        "name": "Pát-tê Mèo",
        "emoji": "🥫",
        "price": 2500,
        "restore_hunger": 50,
        "for_pet": "meo_than_tai"
    },
    "thuc_an_ca": {
        "name": "Thức Ăn Cho Cá",
        "emoji": "🧆",
        "price": 3000,
        "restore_hunger": 50,
        "for_pet": "ca_kesling"
    }
}

# Các loại cá tươi từ lệnh /cauca có thể cho Mèo ăn trực tiếp
RAW_FISH_FEED = {
    "ca_ro": {"name": "Cá Rô", "restore": 15},
    "ca_diec": {"name": "Cá Diếc", "restore": 20},
    "ca_chep": {"name": "Cá Chép", "restore": 25},
    "ca_me": {"name": "Cá Mè", "restore": 15}
}


def make_bar(value: int) -> str:
    """Vẽ thanh độ no 10 ô"""
    clamped = max(0, min(100, value))
    num_filled = round(clamped / 10)
    bar = "█" * num_filled + "░" * (10 - num_filled)
    return f"`[{bar}]` ({clamped}%)"


# ==================== LOGIC THU HOẠCH & ĐỘ NO ====================

def process_pet_rewards(user_id: str):
    """Tính toán phần thưởng AFK & Trừ độ no của Pet theo thời gian"""
    user_data = get_user_data(user_id)
    pets = user_data.setdefault("pets", {})
    now = datetime.datetime.now(datetime.timezone.utc)
    
    rewards_summary = []
    total_money_earned = 0
    
    # 1. MÈO THẦN TÀI (Mỗi 5 phút = 300s -> -1% Độ no / 1-2 Coins)
    if "meo_than_tai" in pets:
        cat = pets["meo_than_tai"]
        hunger = cat.get("hunger", 100)
        last_claim = datetime.datetime.fromisoformat(cat.get("last_claim", now.isoformat()))
        elapsed_sec = (now - last_claim).total_seconds()
        
        total_cycles = min(int(elapsed_sec // 300), 288) # Tối đa 24h
        
        if total_cycles > 0:
            # Mỗi chu kỳ tốn 1% độ no. Tính số chu kỳ Pet đủ no để làm việc:
            productive_cycles = min(total_cycles, hunger)
            
            if productive_cycles > 0:
                coins = sum(random.randint(1, 2) for _ in range(productive_cycles))
                total_money_earned += coins
                
                # Trừ độ no tương ứng
                cat["hunger"] = max(0, hunger - productive_cycles)
                cat["last_claim"] = (last_claim + datetime.timedelta(seconds=total_cycles * 300)).isoformat()
                
                rewards_summary.append(f"🐱 **Mèo Thần Tài**: Thu hoạch được **+{coins:,}** {KESLING_ICON} *(Làm việc {productive_cycles * 5} phút)*")
            else:
                rewards_summary.append("🐱 **Mèo Thần Tài**: 😵 *Đang đói lả (0% no)! Mèo đã ngừng làm việc, hãy cho ăn ngay.*")

    # 2. CÁ KESLING (Mỗi 1 tiếng = 3600s -> -10% Độ no / Quặng)
    if "ca_kesling" in pets:
        fish = pets["ca_kesling"]
        hunger = fish.get("hunger", 100)
        last_claim = datetime.datetime.fromisoformat(fish.get("last_claim", now.isoformat()))
        elapsed_sec = (now - last_claim).total_seconds()
        
        total_cycles = min(int(elapsed_sec // 3600), 24) # Tối đa 24h
        
        if total_cycles > 0:
            # Mỗi tiếng tốn 10% độ no. Tính số giờ Pet đủ no để làm việc:
            max_possible_hours = hunger // 10
            productive_cycles = min(total_cycles, max_possible_hours)
            
            if productive_cycles > 0:
                kesling_stones_found = 0
                other_ores = {}
                inv = user_data.setdefault("inventory", {})
                
                for _ in range(productive_cycles):
                    if random.random() < 0.10: # 10% ra Kesling Stone
                        qty = random.randint(20, 100)
                        kesling_stones_found += qty
                    else:
                        random_ore = random.choice(list(ore.keys()))
                        qty = random.randint(1, 3)
                        other_ores[random_ore] = other_ores.get(random_ore, 0) + qty
                
                if kesling_stones_found > 0:
                    add_ore_with_quality(inv, "kesling_stone", quality_percent=100, qty=kesling_stones_found)
                    
                for o_name, o_qty in other_ores.items():
                    add_ore_with_quality(inv, o_name, quality_percent=100, qty=o_qty)
                    
                # Trừ độ no (10% mỗi giờ)
                fish["hunger"] = max(0, hunger - (productive_cycles * 10))
                fish["last_claim"] = (last_claim + datetime.timedelta(seconds=total_cycles * 3600)).isoformat()
                
                parts = []
                if kesling_stones_found > 0:
                    ks_emoji = emoji_icon.get('kesling_stone', '🪙')
                    parts.append(f"✨ **{kesling_stones_found}x** {ks_emoji} Kesling Stone")
                if other_ores:
                    parts.append(f"🪨 **{sum(other_ores.values())}x** quặng khác")
                    
                rewards_summary.append(f"🐟 **Cá Kesling**: Đào được {', '.join(parts)} *(Lặn làm việc {productive_cycles} giờ)*")
            else:
                rewards_summary.append("🐟 **Cá Kesling**: 😵 *Đang đói lả (0% no)! Cá đã ngừng lặn đào mỏ, hãy cho ăn ngay.*")

    if total_money_earned > 0:
        user_data["money"] = user_data.get("money", 0) + total_money_earned
        
    save_data(player_inventory)
    return rewards_summary


# ==================== INTERACTION VIEWS ====================

class FeedSelectView(Select):
    def __init__(self, user_id: str):
        self.user_id = user_id
        user_data = get_user_data(user_id)
        inv = user_data.get("inventory", {})
        pets = user_data.get("pets", {})
        
        options = []
        
        # Kiểm tra Pát-tê Mèo
        if "meo_than_tai" in pets and inv.get("pate_meo", 0) > 0:
            options.append(discord.SelectOption(
                label=f"Cho Mèo ăn Pát-tê (Còn: {inv['pate_meo']}x)",
                value="feed_cat_pate",
                emoji="🥫",
                description="+50% Độ no cho Mèo Thần Tài"
            ))
            
        # Kiểm tra Cá tươi từ hồ câu cho Mèo ăn
        if "meo_than_tai" in pets:
            for fish_key, f_info in RAW_FISH_FEED.items():
                cnt = get_total_ore_count(inv, fish_key)
                if cnt > 0:
                    options.append(discord.SelectOption(
                        label=f"Cho Mèo ăn {f_info['name']} tươi (Còn: {cnt}x)",
                        value=f"feed_cat_raw_{fish_key}",
                        emoji="🐟",
                        description=f"+{f_info['restore']}% Độ no cho Mèo Thần Tài"
                    ))
                    
        # Kiểm tra Thức ăn cho Cá Kesling
        if "ca_kesling" in pets and inv.get("thuc_an_ca", 0) > 0:
            options.append(discord.SelectOption(
                label=f"Cho Cá Kesling ăn Thức Ăn Cá (Còn: {inv['thuc_an_ca']}x)",
                value="feed_fish_pellets",
                emoji="🧆",
                description="+50% Độ no cho Cá Kesling"
            ))
            
        if not options:
            options.append(discord.SelectOption(
                label="Túi đồ không có thức ăn nào!",
                value="none",
                description="Hãy mua thức ăn tại /pet shop hoặc đi câu cá nhé!"
            ))
            
        super().__init__(placeholder="Chọn món ăn muốn cho Pet ăn...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            return await interaction.response.send_message("❌ Oniichan không có thức ăn phù hợp trong túi!", ephemeral=True)
            
        user_data = get_user_data(self.user_id)
        inv = user_data.get("inventory", {})
        pets = user_data.get("pets", {})
        val = self.values[0]
        
        # 1. Feed Cat with Pate
        if val == "feed_cat_pate":
            if inv.get("pate_meo", 0) <= 0: return await interaction.response.send_message("❌ Hết Pát-tê rồi!", ephemeral=True)
            inv["pate_meo"] -= 1
            if inv["pate_meo"] == 0: del inv["pate_meo"]
            
            cat = pets["meo_than_tai"]
            cat["hunger"] = min(100, cat.get("hunger", 0) + 50)
            save_data(player_inventory)
            return await interaction.response.send_message(f"🥫 Oniichan đã cho Mèo Thần Tài ăn Pát-tê! Độ no hiện tại: {make_bar(cat['hunger'])}")

        # 2. Feed Cat with Raw Fish
        elif val.startswith("feed_cat_raw_"):
            fish_key = val.replace("feed_cat_raw_", "")
            f_info = RAW_FISH_FEED[fish_key]
            
            if get_total_ore_count(inv, fish_key) <= 0:
                return await interaction.response.send_message("❌ Bạn không còn con cá này!", ephemeral=True)
                
            inv[fish_key] -= 1
            if inv[fish_key] == 0: del inv[fish_key]
            
            cat = pets["meo_than_tai"]
            cat["hunger"] = min(100, cat.get("hunger", 0) + f_info["restore"])
            save_data(player_inventory)
            return await interaction.response.send_message(f"🐟 Mèo Thần Tài khoái chí xơi tái 1x **{f_info['name']}**! Độ no hiện tại: {make_bar(cat['hunger'])}")

        # 3. Feed Fish with Pellets
        elif val == "feed_fish_pellets":
            if inv.get("thuc_an_ca", 0) <= 0: return await interaction.response.send_message("❌ Hết Thức ăn cá rồi!", ephemeral=True)
            inv["thuc_an_ca"] -= 1
            if inv["thuc_an_ca"] == 0: del inv["thuc_an_ca"]
            
            fish = pets["ca_kesling"]
            fish["hunger"] = min(100, fish.get("hunger", 0) + 50)
            save_data(player_inventory)
            return await interaction.response.send_message(f"🧆 Oniichan đã rải thức ăn cho Cá Kesling! Độ no hiện tại: {make_bar(fish['hunger'])}")


class PetActionView(View):
    def __init__(self, author: discord.User):
        super().__init__(timeout=60)
        self.author = author
        self.add_item(FeedSelectView(str(author.id)))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Bạn không điều khiển thú cưng này!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🎁 Thu Hoạch Sản Vật", style=discord.ButtonStyle.success, emoji="🧺", row=1)
    async def claim_rewards(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(self.author.id)
        rewards = process_pet_rewards(user_id)
        
        if not rewards:
            return await interaction.response.send_message("⏳ Thú cưng chưa đào thêm được gì mới!", ephemeral=True)
            
        embed = discord.Embed(
            title="🎉 THU HOẠCH THÚ CƯNG THÀNH CÔNG",
            description="\n".join(rewards),
            color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed)


# ==================== COG MODULE ====================

class PetCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_group(name="pet", fallback="status", description="Xem trạng thái, độ no và thu hoạch sản vật Thú Cưng")
    async def pet_group(self, ctx):
        user_id = str(ctx.author.id)
        
        # Tự động tính toán phần thưởng & cập nhật độ no
        process_pet_rewards(user_id)
        
        user_data = get_user_data(user_id)
        pets = user_data.get("pets", {})
        
        embed = discord.Embed(
            title=f"🐾 TRẠI THÚ CƯNG CỦA {ctx.author.display_name.upper()}",
            color=discord.Color.teal()
        )
        
        if not pets:
            embed.description = "🕸️ Oniichan chưa sở hữu Thú Cưng nào cả!\nHãy dùng lệnh `/pet shop` để nhận nuôi một chú Pet đáng yêu nhé."
            view = None
        else:
            pet_lines = []
            now = datetime.datetime.now(datetime.timezone.utc)
            
            if "meo_than_tai" in pets:
                cat = pets["meo_than_tai"]
                hunger = cat.get("hunger", 100)
                status_text = "⚡ Đang nhặt coin" if hunger > 0 else "😵 Đang đói lả (Đã dừng)"
                pet_lines.append(f"🐱 **Mèo Thần Tài** — {make_bar(hunger)}\n> Trạng thái: *{status_text}*")
                
            if "ca_kesling" in pets:
                fish = pets["ca_kesling"]
                hunger = fish.get("hunger", 100)
                status_text = "⚡ Đang lặn đào mỏ" if hunger > 0 else "😵 Đang đói lả (Đã dừng)"
                pet_lines.append(f"🐟 **Cá Kesling** — {make_bar(hunger)}\n> Trạng thái: *{status_text}*")
                
            embed.description = "\n\n".join(pet_lines)
            embed.set_footer(text="Dùng Menu xổ xuống bên dưới để cho Pet ăn hoặc bấm nút Thu Hoạch!")
            view = PetActionView(ctx.author)
            
        await ctx.send(embed=embed, view=view)

    @pet_group.command(name="shop", description="Cửa hàng mua Pet và Đồ ăn cho Pet")
    async def pet_shop(self, ctx):
        embed = discord.Embed(
            title="🏪 CỬA HÀNG THÚ CƯNG & ĐỒ ĂN",
            description="Nhận nuôi Pet và mua thức ăn để Pet duy trì cày AFK!",
            color=discord.Color.gold()
        )
        
        # Danh sách Pet
        pet_list = []
        for pet_id, info in PET_SHOP.items():
            pet_list.append(f"**{info['emoji']} {info['name']}** — `{info['price']:,}` {KESLING_ICON}\n> {info['description']}\n> *Mua:* `/pet buy_pet pet_id: {pet_id}`")
        embed.add_field(name="🐾 Danh Sách Thú Cưng", value="\n\n".join(pet_list), inline=False)
        
        # Danh sách Đồ ăn
        food_list = []
        for food_id, info in PET_FOODS.items():
            food_list.append(f"**{info['emoji']} {info['name']}** — `{info['price']:,}` {KESLING_ICON}\n> Phục hồi: +{info['restore_hunger']}% Độ no\n> *Mua:* `/pet buy_food food_id: {food_id}`")
        food_list.append("🐟 **Cá tươi (Cá Rô, Cá Diếc...)**: Có thể đi câu tại `/cauca` để cho Mèo ăn miễn phí!")
        embed.add_field(name="🍖 Thức Ăn Cho Pet", value="\n\n".join(food_list), inline=False)
            
        await ctx.send(embed=embed)

    @pet_group.command(name="buy_pet", description="Nhận nuôi Thú Cưng mới")
    @app_commands.describe(pet_id="Chọn loại Pet muốn mua")
    @app_commands.choices(pet_id=[
        app_commands.Choice(name="🐱 Mèo Thần Tài (50,000 Kesling)", value="meo_than_tai"),
        app_commands.Choice(name="🐟 Cá Kesling (200,000 Kesling)", value="ca_kesling")
    ])
    async def pet_buy(self, ctx, pet_id: str):
        if pet_id not in PET_SHOP:
            return await ctx.send("❌ Loại Thú Cưng này không tồn tại!")
            
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        pets = user_data.setdefault("pets", {})
        
        if pet_id in pets:
            return await ctx.send(f"❌ Oniichan đã sở hữu **{PET_SHOP[pet_id]['name']}** rồi!")
            
        cost = PET_SHOP[pet_id]["price"]
        current_money = user_data.get("money", 0)
        
        if current_money < cost:
            return await ctx.send(f"💰 Oniichan hông đủ tiền! Cần **{cost:,} {KESLING_ICON}** để mua Pet này.")
            
        user_data["money"] -= cost
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        pets[pet_id] = {
            "owned": True,
            "hunger": 100, # Bắt đầu với 100% no
            "last_claim": now_str
        }
        
        save_data(player_inventory)
        info = PET_SHOP[pet_id]
        await ctx.send(f"🎉 Chúc mừng {ctx.author.mention} đã nhận nuôi thành công **{info['emoji']} {info['name']}**! Bé Pet đã được cho ăn no 100% và bắt đầu đi làm việc rồi nè!")

    @pet_group.command(name="buy_food", description="Mua thức ăn cho Thú Cưng")
    @app_commands.describe(food_id="Chọn loại thức ăn", amount="Số lượng mua")
    @app_commands.choices(food_id=[
        app_commands.Choice(name="🥫 Pát-tê Mèo (2,500 Kesling)", value="pate_meo"),
        app_commands.Choice(name="🧆 Thức Ăn Cá (3,000 Kesling)", value="thuc_an_ca")
    ])
    async def buy_food(self, ctx, food_id: str, amount: int = 1):
        if food_id not in PET_FOODS or amount <= 0:
            return await ctx.send("❌ Đồ ăn hoặc số lượng không hợp lệ!")
            
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        total_cost = PET_FOODS[food_id]["price"] * amount
        
        if user_data.get("money", 0) < total_cost:
            return await ctx.send(f"💰 Oniichan hông đủ tiền! Mua {amount}x {PET_FOODS[food_id]['name']} cần **{total_cost:,} {KESLING_ICON}**.")
            
        user_data["money"] -= total_cost
        inv = user_data.setdefault("inventory", {})
        inv[food_id] = inv.get(food_id, 0) + amount
        save_data(player_inventory)
        
        info = PET_FOODS[food_id]
        await ctx.send(f"✅ Mua thành công **{amount}x {info['emoji']} {info['name']}** với giá **{total_cost:,} {KESLING_ICON}**! Mở `/pet` để cho Pet ăn nha.")

    @pet_group.command(name="claim", description="Thu hoạch toàn bộ sản vật từ Thú cưng")
    async def pet_claim(self, ctx):
        user_id = str(ctx.author.id)
        rewards = process_pet_rewards(user_id)
        
        if not rewards:
            return await ctx.send("⏳ Thú cưng chưa tìm thêm được gì mới, quay lại sau nhé oniichan!")
            
        embed = discord.Embed(
            title="🎉 THU HOẠCH THÚ CƯNG THÀNH CÔNG",
            description="\n".join(rewards),
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(PetCog(bot))