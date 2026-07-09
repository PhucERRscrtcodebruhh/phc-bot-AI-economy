# helpers.py
import math
import discord
from discord.ui import View

def create_inventory_pages(title: str, lines: list, per_page: int, color=discord.Color.blue()):
    pages = []
    total_pages = math.ceil(len(lines) / per_page)
    if total_pages == 0:
        return pages
    for i in range(total_pages):
        start = i * per_page
        end = (i + 1) * per_page
        page_lines = lines[start:end]
        embed = discord.Embed(
            title=f"{title} (Trang {i + 1}/{total_pages})",
            description="\n".join(page_lines),
            color=color
        )
        pages.append(embed)
    return pages

class InventoryPaginationView(View):
    def __init__(self, pages: list[discord.Embed], author_id: int):
        super().__init__(timeout=180)
        self.pages = pages
        self.current_page = 0
        self.message = None
        self.author_id = author_id
        self.update_buttons()

    async def on_timeout(self):
        if self.message:
            for item in self.children:
                item.disabled = True
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Bạn không phải là người đã gọi lệnh này.", ephemeral=True)
            return False
        return True

    def update_buttons(self):
        self.children[0].disabled = self.current_page == 0
        self.children[1].disabled = self.current_page == len(self.pages) - 1

    @discord.ui.button(label="Trang Trước", style=discord.ButtonStyle.blurple, emoji="⬅️")
    async def prev_button(self, interaction: discord.Interaction, button: discord.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    @discord.ui.button(label="Trang Sau", style=discord.ButtonStyle.blurple, emoji="➡️")
    async def next_button(self, interaction: discord.Interaction, button: discord.Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    @discord.ui.button(label="Kết Thúc", style=discord.ButtonStyle.red, emoji="🛑")
    async def stop_button(self, interaction: discord.Interaction, button: discord.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

async def send_paginated_via_ctx(ctx, title: str, lines: list, per_page: int):
    if not lines:
        return
    pages = create_inventory_pages(title, lines, per_page, color=discord.Color.blue())
    if not pages:
        return
    if len(pages) == 1:
        await ctx.send(embed=pages[0])
        return
    view = InventoryPaginationView(pages, ctx.author.id)
    message = await ctx.send(embed=pages[0], view=view)
    view.message = message
    return message