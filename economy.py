
import random
import datetime
import discord
from discord.ext import commands
from discord.ui import View

# Import từ các file định nghĩa và helper chung thư mục
from constants import ore, price, emoji_icon, PICKAXES, PICKAXE_ALIASES, crops, KESLING_ICON
from helpers import send_paginated_via_ctx
from AIphcbot import (
    get_user_data, save_data, get_total_ore_count, 
    add_ore_with_quality, remove_ore_units, player_inventory
)

# ============ WORK UI VIEWS ============

class CropSelectView(View):
    def __init__(self, author: discord.User, user_id: str):
        super().__init__(timeout=30)
        self.author = author
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.author

    @discord.ui.select(
        placeholder="Chọn loại cây muốn gieo hạt...",
        options=[
            discord.SelectOption(label=name.capitalize(), value=name, emoji=data['emoji'], 
                                 description=f"Lớn trong {data['grow_time']}s. Thu hoạch: ~{data['base_yield']} cái")
            for name, data in crops.items()
        ]
    )
    async def select_crop(self, interaction: discord.Interaction, select: discord.ui.Select):
        crop_name = select.values[0]
        crop_data = crops[crop_name]
        ready_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=crop_data['grow_time'])
        
        user_data = get_user_data(self.user_id)
        user_data['farm_data'] = {
            'crop': crop_name,
            'ready_at': ready_at.isoformat()
        }
        save_data(player_inventory)

        embed = discord.Embed(
            title=f"🌱 Đã gieo hạt {crop_name.capitalize()}",
            description=f"Hạt giống đã được gieo xuống ruộng của oniichan! Hãy quay lại thu hoạch sau **{crop_data['grow_time']//60} phút** nhé. ✨",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed, view=None)

class WorkSelectionView(View):
    def __init__(self, author: discord.User, user_id: str):
        super().__init__(timeout=60)
        self.author = author
        self.user_id = user_id
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Đây không phải nút của bạn!", ephemeral=True)
            return False
        return True

    async def _finalize(self, interaction: discord.Interaction, title: str, description: str, fields: list):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

        embed = discord.Embed(title=title, description=description, color=discord.Color.green())
        for field_name, field_value in fields:
            embed.add_field(name=field_name, value=field_value, inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

    async def _process_job(self, interaction: discord.Interaction, job_name: str, job_desc: str, pay_range: tuple[int, int]):
        pay = random.randint(pay_range[0], pay_range[1])
        user_data = get_user_data(self.user_id)
        user_data['money'] = user_data.get('money', 0) + pay
        save_data(player_inventory)

        title = f"✅ Hoàn thành công việc: {job_name}"
        field_value = f"Thu nhập: **{pay:,} {KESLING_ICON}**\nLàm việc cực kỳ chăm chỉ và nhận phần thưởng."
        await self._finalize(interaction, title, job_desc, [("Kết quả", field_value)])

    @discord.ui.button(label="🌾 Làm nông", style=discord.ButtonStyle.primary)
    async def farmer(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_data = get_user_data(self.user_id)
        inv = user_data.get('inventory', {})
        
        if inv.get('ruong', 0) <= 0:
            return await interaction.response.send_message(
                "🚫 **Oniichan chưa có ruộng!** Hãy vào `p shop buy ruong` để mua đất canh tác trước khi làm nông nha.", 
                ephemeral=True
            )

        farm_data = user_data.get('farm_data')
        if not farm_data:
            view = CropSelectView(self.author, self.user_id)
            embed = discord.Embed(
                title="🚜 Ruộng đang trống",
                description="Oniichan muốn trồng cây gì trong ca làm việc này nè?",
                color=discord.Color.dark_green()
            )
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            ready_at = datetime.datetime.fromisoformat(farm_data['ready_at'])
            now = datetime.datetime.now(datetime.timezone.utc)
            
            if now < ready_at:
                wait_time = (ready_at - now).total_seconds()
                await interaction.response.send_message(
                    f"⏳ Cây **{farm_data['crop']}** vẫn đang lớn oniichan ơi! Còn khoảng **{int(wait_time//60)} phút** nữa mới chín.", 
                    ephemeral=True
                )
            else:
                crop_name = farm_data['crop']
                crop_info = crops[crop_name]
                yield_qty = crop_info['base_yield'] + random.randint(1, 3)
                
                inv[crop_name] = inv.get(crop_name, 0) + yield_qty
                user_data['farm_data'] = None
                save_data(player_inventory)
                
                title = f"🎉 Thu hoạch thành công: {crop_name.capitalize()}"
                desc = f"Ruộng lúa trĩu bông! Oniichan đã thu hoạch được **{yield_qty}x {crop_info['emoji']} {crop_name}**."
                field_val = f"Sản phẩm đã được cất vào túi (`p bag`). Oniichan có thể đem bán bằng lệnh `p sell {crop_name} all` nha!"
                await self._finalize(interaction, title, desc, [("Kết quả", field_val)])

    @discord.ui.button(label="📊 Kế toán", style=discord.ButtonStyle.success)
    async def accountant(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._process_job(
            interaction, "Kế toán", 
            "Oniichan đã dành cả buổi sáng để cân đối bảng thu chi cho khu mỏ.", (1500, 3500)
        )

# ============ COG MODULE ============

class EconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="mine")
    @commands.cooldown(rate=1, per=15, type=commands.BucketType.user)
    async def mine(self, ctx):
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        inv = user_data['inventory']

        best_pickaxe = 'default_pickaxe'
        ownable_pickaxes = {k: v for k, v in PICKAXES.items() if k != 'default_pickaxe'}
        for pickaxe_name, props in ownable_pickaxes.items():
            if get_total_ore_count(inv, pickaxe_name) > 0:
                current_best_multiplier = PICKAXES[best_pickaxe]['max_multiplier']
                if props['max_multiplier'] > current_best_multiplier:
                    best_pickaxe = pickaxe_name

        props = PICKAXES[best_pickaxe]
        best_multiplier = (props['min_multiplier'], props['max_multiplier'])
        multiplier = random.uniform(best_multiplier[0], best_multiplier[1])
        pickaxe_emoji = emoji_icon.get(best_pickaxe, "❓")

        rarity_reduction_factor = props['min_multiplier']
        dynamic_weights = {}
        for ore_name, original_weight in ore.items():
            if 0 < original_weight < 30:
                new_weight = max(1, int(original_weight * rarity_reduction_factor))
                dynamic_weights[ore_name] = new_weight
            else:
                dynamic_weights[ore_name] = original_weight

        found_ore = random.choices(list(dynamic_weights.keys()), weights=list(dynamic_weights.values()), k=1)[0]
        base_amount = random.randint(1, 10)
        final_amount = int(base_amount * multiplier)
        if final_amount == 0:
            final_amount = 1

        emoji = emoji_icon.get(found_ore, "")
        original_weight_check = ore.get(found_ore, 0)

        if found_ore in ('dirt', 'stone'):
            quality_percent = 100
            quality_msg = ""
        else:
            if best_pickaxe == 'default_pickaxe':
                quality_percent = random.randint(5, 75)
            else:
                quality_percent = random.randint(75, 100)
            quality_msg = f" ({quality_percent}% chất lượng)"

        add_ore_with_quality(inv, found_ore, quality_percent=quality_percent, qty=final_amount)
        save_data(player_inventory)

        ore_name_display = found_ore.replace('_', ' ').title()
        pick_name_display = best_pickaxe.replace('_', ' ').title() if best_pickaxe != 'default_pickaxe' else "Xẻng mặc định"
        await ctx.send(f"{ctx.author.mention} oniichan đào được **{final_amount}x** {emoji} **{ore_name_display}**{quality_msg} bằng {pickaxe_emoji} **{pick_name_display}** nè! ✨")

    @mine.error
    async def mine_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏳ **{ctx.author.mention}**, đợi **{error.retry_after:.1f} giây** nữa.")

    @commands.command(name="pwork")
    @commands.cooldown(rate=1, per=1800, type=commands.BucketType.user)
    async def pwork(self, ctx):
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        current_money = user_data.get('money', 0)

        embed = discord.Embed(
            title="🏭 Công việc kinh tế vi mô",
            description="Chọn một nghề để thực hiện. Mỗi công việc yêu cầu công cụ làm việc riêng.",
            color=discord.Color.green()
        )
        embed.add_field(name="🌾 Làm nông", value="Yêu cầu mua Ruộng đất (`ruong`). Trồng và thu hoạch nông sản.", inline=False)
        embed.add_field(name="📊 Kế toán", value="Không yêu cầu dụng cụ. Nhận lương cố định.", inline=False)
        embed.set_footer(text=f"Tiền hiện tại: {current_money:,} {KESLING_ICON}")

        view = WorkSelectionView(ctx.author, user_id)
        message = await ctx.send(embed=embed, view=view)
        view.message = message

    @pwork.error
    async def pwork_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏳ **{ctx.author.mention}**, oniichan nghỉ ngơi tí đi! Đợi **{error.retry_after/60:.1f} phút** nữa nha. 🥰")

    @commands.group(name="shop", invoke_without_command=True)
    async def shop(self, ctx):
        embed = discord.Embed(title="🛍️ Cửa Hàng Cuốc Đào (Pickaxe Shop)", color=discord.Color.gold())
        item_list = ""
        for name, props in PICKAXES.items():
            if name == 'default_pickaxe':
                continue
            emoji = emoji_icon.get(name, "❓")
            alias_name = next((vn_name for vn_name, key in PICKAXE_ALIASES.items() if key == name), name)
            item_list += f"**{emoji} {name.upper()}**\n> Price: {props['price']:,} {KESLING_ICON} | Buy: `shop buy {alias_name}`\n\n"
        embed.add_field(name="⛏️ Danh Sách Cuốc Đào", value=item_list, inline=False)
        
        job_items = (
            f"**🚜 RUỘNG ĐẤT**: {price['ruong']:,} {KESLING_ICON} (Mua: `shop buy ruong`)\n"
            f"**📚 GIÁO ÁN**: {price['giao_an']:,} {KESLING_ICON} (Mua: `shop buy  giaoan`)\n"
            f"**🔧 BỘ DỤNG CỤ**: {price['bo_dung_cu']:,} {KESLING_ICON} (Mua: `shop buy  bodungcu`)\n"
            f"**🩺 TÚI Y TẾ**: {price['tui_y_te']:,} {KESLING_ICON} (Mua: `shop buy  tuiyte`)\n"
        )
        embed.add_field(name="💼 Đồ Nghề Kinh Doanh", value=job_items, inline=False)
        await ctx.send(embed=embed)

    @shop.command(name="buy")
    async def shop_buy(self, ctx, item_name: str = None):
        if item_name is None:
            return await ctx.send("❌ Ví dụ: `p shop buy cuocgo`")
        
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        input_key = item_name.lower().replace(" ", "")
        
        REVERSE_ALIASES = {v: k for k, v in PICKAXE_ALIASES.items()}
        item_key = REVERSE_ALIASES.get(input_key, input_key)
        
        item_price = price.get(item_key)
        if not item_price and item_key in PICKAXES:
            item_price = PICKAXES[item_key]['price']
            
        if not item_price:
            return await ctx.send(f"❌ Không tìm thấy vật phẩm **{item_name}**.")
            
        if user_data.get('money', 0) < item_price:
            return await ctx.send(f"💰 Bạn không đủ tiền! Cần **{item_price:,} {KESLING_ICON}**.")
            
        user_data['money'] -= item_price
        inv = user_data['inventory']
        inv[item_key] = inv.get(item_key, 0) + 1
        save_data(player_inventory)
        
        emoji = emoji_icon.get(item_key, "❓")
        await ctx.send(f"✅ Bạn đã mua thành công **{emoji} {item_key}** với giá **{item_price:,} {KESLING_ICON}**!")

    @commands.command(name="bag")
    async def bag(self, ctx, member: discord.Member = None):
        target = member or ctx.author
        user_id = str(target.id)
        user_data = get_user_data(user_id)
        inv = user_data.get('inventory', {})
        money = user_data.get('money', 0)
        
        money_embed = discord.Embed(
            title=f"🎒 Kho của {target.display_name}",
            description=f"💰 Tiền: **{money:,} {KESLING_ICON}**\n\n--- Danh Sách Tài Nguyên ---",
            color=discord.Color.gold()
        )
        await ctx.send(embed=money_embed)
        
        if not inv:
            return await ctx.send("Kho tài nguyên trống rỗng.")
            
        ore_lines = []
        for ore_name, amount in sorted(inv.items()):
            emoji = emoji_icon.get(ore_name, "")
            display_name = ore_name.replace('_', ' ').capitalize()
            if isinstance(amount, dict):
                total_count = sum(int(v) for v in amount.values())
                parts = [f"{cnt}x{q}%" for q, cnt in sorted(amount.items(), key=lambda x: int(x[0]), reverse=True)]
                line = f"{emoji} **{display_name}**\n> **Tổng**: {total_count:,} - *({', '.join(parts)})*"
            else:
                line = f"{emoji} **{display_name}**\n> **Số lượng**: {amount:,}"
            ore_lines.append(line)
            
        await send_paginated_via_ctx(ctx, f"Chi Tiết Kho Tài Nguyên", ore_lines, per_page=7)

    @commands.command(name="sell")
    async def sell(self, ctx, ore_type: str = None, quantity_to_sell: str = None):
        if ore_type is None or quantity_to_sell is None:
            return await ctx.send(f"{ctx.author.mention} dùng: `psell <tên quặng> <số lượng/all>`")
            
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        inv = user_data['inventory']
        
        ore_type = ore_type.lower()
        base_price = price.get(ore_type)
        if base_price is None:
            return await ctx.send(f"❌ Không tìm thấy giá cho **{ore_type}**.")
            
        total_available = get_total_ore_count(inv, ore_type)
        if quantity_to_sell.lower() == 'all':
            amount_to_sell = total_available
        else:
            try:
                amount_to_sell = int(quantity_to_sell)
            except ValueError:
                return await ctx.send("Số lượng không hợp lệ.")
                
        if amount_to_sell <= 0 or amount_to_sell > total_available:
            return await ctx.send("Số lượng không hợp lệ hoặc bạn không đủ tài nguyên.")
            
        removed = remove_ore_units(inv, ore_type, amount_to_sell, strategy='lowest')
        total_price = 0
        parts = []
        for q_str, cnt in removed.items():
            q = int(q_str)
            price_per_unit = base_price * (q / 100.0)
            total_price += int(price_per_unit * cnt)
            parts.append(f"{cnt}x{q}%")
            
        user_data['money'] = user_data.get('money', 0) + total_price
        save_data(player_inventory)
        await ctx.send(f"✅ {ctx.author.mention} đã bán thành công **{amount_to_sell}x {ore_type}** ({', '.join(parts)}) lấy **{total_price:,} {KESLING_ICON}**!")

    @commands.command(name="listore")
    async def listore(self, ctx):
        ore_items = []
        for k, weight in sorted(ore.items(), key=lambda item: item[1], reverse=True):
            emoji = emoji_icon.get(k, '')
            base_price = price.get(k, 0)
            ore_items.append(f"{emoji} **{k}** (Trọng số: {weight} | Giá: {base_price:,} {KESLING_ICON})")
        await send_paginated_via_ctx(ctx, "Danh Sách Quặng Có Thể Khai Thác", ore_items, per_page=15)

    @commands.command(name="luyenkim")
    async def luyenkim(self, ctx, ore_name: str = None, qty: str = "1"):
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        inv = user_data.get('inventory', {})
        smelt_map_data = {
            'iron': ('iron_ingot', 1, 1, True), 'magnetite': ('iron_ingot', 1, 1, True),
            'hematite': ('iron_ingot', 1, 1, True), 'copper': ('copper_ingot', 1, 1, True),
            'gold_ore': ('gold_ingot', 1, 1, True), 'silver': ('silver_ingot', 1, 1, True),
            'stone': ('stone_brick', 1, 0, False), 'dirt': ('clay', 1, 0, False),
        }
        
        if ore_name is None:
            # Luyện kim nhanh không nhập tham số:
            return await ctx.send("💡 Dùng lệnh: `p luyenkim <tên_quặng> <số_lượng/all>` để bắt đầu nung.")
            
        ore_key = ore_name.lower()
        if ore_key not in smelt_map_data:
            return await ctx.send(f"Không thể luyện kim loại quặng **{ore_key}**.")
            
        total_ore = get_total_ore_count(inv, ore_key)
        if qty.lower() == 'all':
            amount = total_ore
        else:
            try:
                amount = int(qty)
            except ValueError:
                return await ctx.send("Số lượng không hợp lệ.")
                
        if amount <= 0 or amount > total_ore:
            return await ctx.send("Số lượng quặng trong kho không đủ.")
            
        out_item, out_qty, coal_cost, needs_coal = smelt_map_data[ore_key]
        coal_needed = amount * coal_cost
        have_coal = get_total_ore_count(inv, 'coal')
        
        if needs_coal and have_coal < coal_needed:
            return await ctx.send(f"🔥 Bạn cần **{coal_needed}** than (`coal`) để luyện kim {amount} {ore_key}.")
            
        removed = remove_ore_units(inv, ore_key, amount, strategy='highest')
        if needs_coal:
            inv['coal'] = have_coal - coal_needed
            if inv['coal'] == 0:
                del inv['coal']
                
        produced, slag_count = 0, 0
        for q_str, cnt in removed.items():
            q = int(q_str)
            for _ in range(cnt):
                if ore_key in ('dirt', 'stone'):
                    produced += out_qty
                else:
                    success_chance = 0.10 + (q / 200.0)
                    if random.random() < success_chance:
                        produced += out_qty
                    else:
                        slag_count += 1
                        
        if produced > 0:
            inv[out_item] = inv.get(out_item, 0) + produced
        if slag_count > 0:
            inv['slag'] = inv.get('slag', 0) + slag_count
            
        save_data(player_inventory)
        
        embed = discord.Embed(title="🔥 Kết Quả Luyện Kim", color=discord.Color.green())
        embed.add_field(name="Sản Phẩm nhận được", value=f"✅ **{produced}x** {emoji_icon.get(out_item, '')} {out_item}")
        if slag_count > 0:
            embed.add_field(name="Xỉ hàn thất bại", value=f"⚠️ **{slag_count}x** {emoji_icon.get('slag', '')} slag (xỉ)")
        await ctx.send(embed=embed)

    @commands.command(name="taiche")
    async def taiche(self, ctx, qty: str = '1'):
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        inv = user_data.get('inventory', {})
        
        have_slag = inv.get('slag', 0)
        if qty.lower() == 'all':
            amount = have_slag // 10
        else:
            try:
                amount = int(qty)
            except ValueError:
                return await ctx.send("Số lượng không hợp lệ.")
                
        if amount <= 0:
            return await ctx.send("Số lượng tái chế tối thiểu là 1.")
            
        need = amount * 10
        if have_slag < need:
            return await ctx.send(f"Bạn cần ít nhất {need} xỉ (`slag`) để tái chế {amount} lần.")
            
        metal_options = ['iron', 'copper', 'gold', 'silver']
        results = {}
        for _ in range(amount):
            chosen = random.choice(metal_options)
            inv[chosen] = inv.get(chosen, 0) + 1
            results[chosen] = results.get(chosen, 0) + 1
            
        inv['slag'] = have_slag - need
        if inv['slag'] == 0:
            del inv['slag']
            
        save_data(player_inventory)
        parts = [f"**{v}x** {emoji_icon.get(k, '')} {k}" for k, v in results.items()]
        await ctx.send(f"♻️ **Tái chế thành công!** Oniichan đã đổi {need}x xỉ thành: {', '.join(parts)}")

async def setup(bot):
    await bot.add_cog(EconomyCog(bot))