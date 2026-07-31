# masoi.py
import asyncio
import random
import math
import discord
from discord.ext import commands

from werewolf_data import ROLES_INFO, send_fancy_event_message, calculate_wolf_count
from werewolf_views import (
    WerewolfLobbyView, NightActionView, DayActionView, WerewolfVotingView, 
    HunterShootView, VictorySummaryView, SkipDiscussionView, run_phase_timer
)

try:
    from AIphcbot import owner_id, subowner_id, get_user_data, save_data, player_inventory
except ImportError:
    owner_id = "0"
    subowner_id = []
    def get_user_data(uid): return {"money": 0}
    def save_data(data): pass
    player_inventory = {}

class WerewolfCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_games = {}

    async def send_werewolf_victory_summary(self, ctx, winning_side: str, winning_title: str, all_players: list, alive_players: list, player_roles: dict, lovers_tuple: tuple = None):
        winners_lines = []
        for p in all_players:
            p_role = player_roles[p.id]
            is_winner = (winning_side == "lovers" and lovers_tuple and p.id in lovers_tuple) or (winning_side != "lovers" and ROLES_INFO[p_role]["side"] == winning_side)
            if is_winner:
                winners_lines.append(f"• {p.mention} - `{p.id}` ➔ **{ROLES_INFO[p_role]['emoji']} {ROLES_INFO[p_role]['name']}**")

        roster_lines = [f"• {p.mention} (`{p.id}`) ➔ **{ROLES_INFO[player_roles[p.id]]['emoji']} {ROLES_INFO[player_roles[p.id]]['name']}** ({'💚 Còn sống' if p in alive_players else '💀 Đã chết'})" for p in all_players]
        view = VictorySummaryView(ctx, winning_side, winning_title, winners_lines, roster_lines)
        await send_fancy_event_message(ctx, view.generate_embed(), "dawn.png", view=view if view.total_pages > 1 else None)

    @commands.hybrid_command(name="stopmasoi", aliases=["dungmasoi"], description="Dừng khẩn cấp ván Ma Sói")
    async def stopmasoi(self, ctx):
        cid = ctx.channel.id
        if cid not in self.active_games: return await ctx.send("❌ Không có trận Ma Sói nào đang diễn ra!")

        game_data = self.active_games[cid]
        if not (ctx.author.id == game_data["host_id"] or ctx.author.guild_permissions.manage_messages or str(ctx.author.id) in [owner_id] + subowner_id):
            return await ctx.send("❌ Không có quyền dừng!", ephemeral=True)

        game_data["stopped"] = True
        embed = discord.Embed(title="🛑 TRẬN ĐẤU BỊ DỪNG KHẨN CẤP", color=discord.Color.red())
        role_lines = [f"• {p.mention}: **{ROLES_INFO[game_data['player_roles'][p.id]]['name']}**" for p in game_data["all_players"]]
        embed.add_field(name="🔮 Vai trò chi tiết", value="\n".join(role_lines), inline=False)
        del self.active_games[cid]
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="masoi", aliases=["werewolf"], description="Mở sảnh chơi Ma Sói")
    async def masoi(self, ctx):
        cid = ctx.channel.id
        if cid in self.active_games: return await ctx.send("❌ Đã có trận đấu trong kênh này!")

        lobby_view = WerewolfLobbyView(ctx.author)
        await ctx.send(embed=lobby_view.generate_embed(), view=lobby_view)
        await lobby_view.wait()

        if not lobby_view.game_started: return await ctx.send("⏰ **Sảnh game bị hủy!**")

        all_players = list(lobby_view.players.values())
        disc_mins, night_mins = lobby_view.discussion_minutes, lobby_view.night_minutes
        mod_mode, show_votes = lobby_view.modified_mode, lobby_view.show_votes
        player_roles = {p.id: lobby_view.forced_roles[p.id] for p in all_players if p.id in lobby_view.forced_roles}
        unassigned = [p for p in all_players if p.id not in player_roles]

        num_wolves = calculate_wolf_count(lobby_view.wolf_setting, len(all_players))
        role_pool = ["wolf"] * num_wolves + ["seer", "doctor", "witch", "mayor", "cupid", "hunter"]
        if mod_mode:
            if random.random() < 0.30: role_pool.append("vampire")
            role_pool.extend(["chemist", "psychiatrist", "addict"])
            if random.random() < 0.5: role_pool.append("corrupted")

        while len(role_pool) < len(unassigned): role_pool.append("villager")
        random.shuffle(role_pool)

        for i, p in enumerate(unassigned): player_roles[p.id] = role_pool[i]
        game_data = {"type": "werewolf", "host_id": ctx.author.id, "stopped": False, "player_roles": player_roles, "all_players": all_players}
        self.active_games[cid] = game_data

        for p in all_players:
            r_info = ROLES_INFO[player_roles[p.id]]
            try: await p.send(embed=discord.Embed(title=f"🔮 VAI TRÒ: {r_info['emoji']} {r_info['name']}", description=r_info['desc'], color=discord.Color.gold()))
            except Exception: pass

        await send_fancy_event_message(ctx, discord.Embed(title="🐺 TRẬN ĐẤU BẮT ĐẦU!", color=discord.Color.dark_red()), "night.png")
        await asyncio.sleep(2)

        alive_players, day_count, lovers_tuple = list(all_players), 1, None
        witch_state, chemist_state, gian_dan_last_used = {"heal_used": False, "poison_used": False}, {"nuke_used": False, "revive_cd": 0}, {}

        # ---------------- MAIN GAME LOOP ----------------
        while True:
            if game_data.get("stopped"): break
            if chemist_state["revive_cd"] > 0: chemist_state["revive_cd"] -= 1

            night_event = "normal"
            if mod_mode:
                if day_count % 15 == 0: night_event = "blood_moon"
                elif day_count % 7 == 0: night_event = "blue_moon"
                elif day_count % 5 == 0: night_event = "full_moon"

            # ---------------- BAN ĐÊM ----------------
            await send_fancy_event_message(
                ctx, 
                discord.Embed(title="🌙 ĐÊM PHỦ XUỐNG NGÔI LÀNG", description="Mọi người nhắm mắt đi ngủ...", color=discord.Color.dark_purple()), 
                "moon.png"
            )

            night_data = {"event": night_event, "wolf_votes": {}, "protected_id": None, "cured_ids": [], "avenger_kill_id": None, "vampire_infect_id": None, "corrupted_stab_id": None, "witch_poison_id": None, "lovers": lovers_tuple, "witch_heal_action": False, "chemist_heal_action": False, "chemist_nuke_wolf": False, "chemist_nuke_civ": False, "current_wolf_target": None, "acted_players": set()}
            night_view = NightActionView(player_roles, alive_players, night_data, day_count, witch_state, chemist_state, gian_dan_last_used, game_data, self.bot)

            night_embed = discord.Embed(
                title=f"━━━━━━━ ■ □ ━━━━━━━\n🌙 BAN ĐÊM THỨ {day_count}", 
                description=f"Các vai trò đặc biệt hãy bấm nút bên dưới để thực hiện kỹ năng đêm! ({night_mins} Phút)", 
                color=discord.Color.dark_purple()
            )
            night_msg = await send_fancy_event_message(ctx, night_embed, "night.png", view=night_view)

            # Đếm ngược thời gian Ban Đêm
            night_total_secs = night_mins * 60
            await run_phase_timer(ctx.channel, night_total_secs, "BAN ĐÊM", stop_checker=lambda: game_data.get("stopped"))
            
            try: await night_msg.edit(view=None)
            except Exception: pass

            if game_data.get("stopped"): break
            if night_data.get("lovers"): lovers_tuple = night_data["lovers"]

            # XỬ LÝ ĐÊM (Killed List)
            killed_players = []
            if night_data["wolf_votes"]:
                all_t = [t for v, targets in night_data["wolf_votes"].items() for t in targets]
                if all_t:
                    target_id = max(set(all_t), key=all_t.count)
                    if not (target_id == night_data["protected_id"] or night_data["witch_heal_action"] or night_data["chemist_heal_action"]):
                        tp = ctx.guild.get_member(target_id)
                        if tp: killed_players.append(tp)

            if night_data["witch_poison_id"]:
                wp = ctx.guild.get_member(night_data["witch_poison_id"])
                if wp: killed_players.append(wp)

            # ---------------- BAN NGÀY ----------------
            if killed_players:
                death_names = ", ".join([kp.mention for kp in set(killed_players)])
                day_start_embed = discord.Embed(
                    title="☀️ MẶT TRỜI ĐÃ MỌC",
                    description=f"Một tiếng hét thất thanh vang lên!\n🩸 Dân làng **{death_names}** đã chết trong vũng máu đêm qua!",
                    color=discord.Color.red()
                )
            else:
                day_start_embed = discord.Embed(
                    title="☀️ MẶT TRỜI ĐÃ MỌC",
                    description="🛡️ Đêm qua là một đêm hoàn toàn bình yên, không ai qua đời!",
                    color=discord.Color.gold()
                )

            await send_fancy_event_message(ctx, day_start_embed, "dawn.png")

            # Xử lý thợ săn & Cập nhật danh sách sống
            if killed_players:
                for kp in set(killed_players):
                    alive_players = [p for p in alive_players if p.id != kp.id]
                    if player_roles[kp.id] == "hunter":
                        h_view = HunterShootView(kp.id, alive_players, alive_players)
                        h_msg = await ctx.channel.send(
                            f"🏹 **THỢ SĂN ({kp.mention}) ĐÃ CHẾT!** Bấm nút bên dưới để bắn kéo theo 1 người!", 
                            view=h_view
                        )
                        h_view.message = h_msg
                        
                        # Chờ Thợ Săn bấm nút chọn hoặc hết thời gian
                        await h_view.wait()
                        
                        if h_view.target_id:
                            killed_target = ctx.guild.get_member(h_view.target_id)
                            alive_players = [ap for ap in alive_players if ap.id != h_view.target_id]
                            await ctx.channel.send(
                                f"💥 **Thợ Săn {kp.mention}** đã bắn nổ sọ **{killed_target.mention}** trước khi nhắm mắt!"
                            )

            # CHECK WIN BAN ĐẦU
            wolves_left = [p for p in alive_players if ROLES_INFO[player_roles[p.id]]["side"] == "evil"]
            civs_left = [p for p in alive_players if ROLES_INFO[player_roles[p.id]]["side"] == "good"]
            if len(wolves_left) == 0:
                await self.send_werewolf_victory_summary(ctx, "good", "🎉 PHE DÂN LÀNG CHIẾN THẮNG!", all_players, alive_players, player_roles, lovers_tuple)
                break
            elif len(wolves_left) >= len(civs_left):
                await self.send_werewolf_victory_summary(ctx, "evil", "🐺 PHE MA SÓI CHIẾN THẮNG!", all_players, alive_players, player_roles, lovers_tuple)
                break

            # GỬI BẢNG HÀNH ĐỘNG NGÀY (Nút Tiên Tri + Tình Hình Làng)
            day_data = {"event": night_event, "acted_seers": set()}
            day_view = DayActionView(player_roles, alive_players, day_data, day_count, game_data, self.bot)
            day_panel_embed = discord.Embed(
                title=f"━━━━━━━ ■ □ ━━━━━━━\n☀️ BAN NGÀY THỨ {day_count}",
                description="🔮 **Tiên Tri** và cư dân hãy bấm các nút bên dưới để thực hiện kỹ năng ban ngày!",
                color=discord.Color.gold()
            )
            day_msg = await send_fancy_event_message(ctx, day_panel_embed, "day.png", view=day_view)

            # GỬI BẢNG BÀN LUẬN & BỎ QUA
            skip_discussion_view = SkipDiscussionView(alive_players, ctx.author.id)
            disc_embed = discord.Embed(
                title="💬 PHÒNG THẢO LUẬN LÀNG",
                description=f"Cả làng có **{disc_mins} PHÚT** để thảo luận tìm Ma Sói!\nNếu muốn bỏ qua thảo luận nhanh, bấm nút **[⏩ Bỏ qua bàn luận]** bên dưới.",
                color=discord.Color.blue()
            )
            disc_msg = await ctx.channel.send(embed=disc_embed, view=skip_discussion_view)

            # Đếm ngược thời gian thảo luận Ban Ngày
            day_total_secs = disc_mins * 60
            await run_phase_timer(
                ctx.channel, 
                day_total_secs, 
                "BAN NGÀY", 
                stop_checker=lambda: game_data.get("stopped") or skip_discussion_view.skipped
            )

            try: await day_msg.edit(view=None)
            except Exception: pass
            try: await disc_msg.edit(view=None)
            except Exception: pass

            if game_data.get("stopped"): break

            # ---------------- TÒA ÁN TREO CỔ (VOTE) ----------------
            vote_view = WerewolfVotingView(alive_players)
            vote_embed = discord.Embed(
                title=f"━━━━━━━ ■ □ ━━━━━━━\n⚖️ TÒA ÁN DÂN LÀNG (NGÀY {day_count})",
                description="Mọi người có **45 GIÂY** để bỏ phiếu treo cổ kẻ nghi ngờ!",
                color=discord.Color.gold()
            )
            vote_msg = await send_fancy_event_message(ctx, vote_embed, "vote.png", view=vote_view)
            
            await run_phase_timer(ctx.channel, 45, "BỎ PHIẾU", stop_checker=lambda: game_data.get("stopped"))
            
            try: await vote_msg.edit(view=None)
            except Exception: pass

            if vote_view.votes:
                tally = {}
                for voter_id, target in vote_view.votes.items():
                    if target != "skip": tally[target] = tally.get(target, 0) + 1
                if tally:
                    max_target_id = max(tally, key=tally.get)
                    vout_p = ctx.guild.get_member(int(max_target_id))
                    alive_players = [p for p in alive_players if p.id != vout_p.id]
                    await ctx.channel.send(f"🔥 **Dân làng đã treo cổ {vout_p.mention} ({ROLES_INFO[player_roles[vout_p.id]]['name']})!**")

                    # KÍCH HOẠT KỸ NĂNG BẮN NẾU BỊ TREO CỔ LÀ THỢ SĂN
                    if player_roles[vout_p.id] == "hunter":
                        h_view = HunterShootView(vout_p.id, alive_players, alive_players)
                        h_msg = await ctx.channel.send(
                            f"🏹 **THỢ SĂN ({vout_p.mention}) BỊ TREO CỔ!** Bấm nút bên dưới để kéo 1 người chết theo!", 
                            view=h_view
                        )
                        h_view.message = h_msg
                        await h_view.wait()
                        
                        if h_view.target_id:
                            killed_target = ctx.guild.get_member(h_view.target_id)
                            alive_players = [ap for ap in alive_players if ap.id != h_view.target_id]
                            await ctx.channel.send(
                                f"💥 Trước khi bị xiết cổ, **Thợ Săn {vout_p.mention}** đã kịp bóp cò kéo theo **{killed_target.mention}** xuống mồ!"
                            )
                            

            # CHECK WIN CUỐI NGÀY
            wolves_left = [p for p in alive_players if ROLES_INFO[player_roles[p.id]]["side"] == "evil"]
            civs_left = [p for p in alive_players if ROLES_INFO[player_roles[p.id]]["side"] == "good"]
            if len(wolves_left) == 0:
                await self.send_werewolf_victory_summary(ctx, "good", "🎉 PHE DÂN LÀNG CHIẾN THẮNG!", all_players, alive_players, player_roles, lovers_tuple)
                break
            elif len(wolves_left) >= len(civs_left):
                await self.send_werewolf_victory_summary(ctx, "evil", "🐺 PHE MA SÓI CHIẾN THẮNG!", all_players, alive_players, player_roles, lovers_tuple)
                break

            day_count += 1
            await asyncio.sleep(3)

        if cid in self.active_games: del self.active_games[cid]

async def setup(bot):
    await bot.add_cog(WerewolfCog(bot))