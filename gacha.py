import discord
import random


class GachaPanelView(discord.ui.View):
    def __init__(self, user_id: int, db_mod):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.db = db_mod

    async def _roll_char(self, interaction: discord.Interaction, count: int, is_limited: bool = False):
        await interaction.response.defer()
        uid = interaction.user.id
        self.db.ensure_player(uid)

        if is_limited and self.db.get_state("limited_gacha_active", "0") != "1":
            await interaction.followup.send("❌ 現在開催中の期間限定ピックアップガチャはありません。", ephemeral=True)
            return

        cost = count * 100
        conn = self.db.get_db()
        p = conn.execute("SELECT gems FROM players WHERE user_id = ?", (uid,)).fetchone()
        if p["gems"] < cost:
            conn.close()
            await interaction.followup.send(f"❌ ガチャ石不足（所持:`{p['gems']}` / 必要:`{cost}`）", ephemeral=True)
            return

        conn.execute("UPDATE players SET gems = gems - ? WHERE user_id = ?", (cost, uid))
        pools = {
            r: [c for c in self.db.CHARACTERS.values() if c["base_rarity"] == r and not c.get("is_god_custom")]
            for r in ["C", "R", "SR", "SSR", "UR", "LR", "MCR"]
        }

        mcr_rate = 2 if pools["MCR"] else 0  # 0.2%
        lr_rate = int(self.db.get_state("normal_lr_rate_permille", "5"))
        ur_rate = int(self.db.get_state("normal_ur_rate_permille", "30"))
        pu_cid = int(self.db.get_state("limited_gacha_char_id", "200"))
        pu_rate = int(self.db.get_state("limited_gacha_rate_permille", "30"))
        pu_title = self.db.get_state("limited_gacha_title", "【期間限定】ピックアップ召喚")

        lines = []
        for _ in range(count):
            roll = random.randint(1, 1000)
            if is_limited and pu_cid in self.db.CHARACTERS and roll <= pu_rate:
                ch = self.db.CHARACTERS[pu_cid]
                rar = ch["base_rarity"]
                pu_mark = "🌟【PU確定!!】"
            else:
                pu_mark = ""
                if roll <= mcr_rate:
                    rar = "MCR"
                elif roll <= (mcr_rate + lr_rate):
                    rar = "LR"
                elif roll <= ur_rate:
                    rar = "UR"
                elif roll <= 110:
                    rar = "SSR"
                elif roll <= 300:
                    rar = "SR"
                elif roll <= 600:
                    rar = "R"
                else:
                    rar = "C"
                ch = random.choice(pools[rar])

            cid = ch["id"]
            ex = conn.execute("SELECT * FROM user_chars WHERE user_id = ? AND char_id = ?", (uid, cid)).fetchone()
            if ex:
                new_lb = ex["limit_break"] + 1
                conn.execute("UPDATE user_chars SET limit_break = ? WHERE user_id = ? AND char_id = ?", (new_lb, uid, cid))
                lines.append(f"{pu_mark}🔄 **[{rar}] No.{cid:03d} {ch['name']}**（被り凸！上限 **Lv.{self.db.get_max_level(new_lb)}** 解放）")
            else:
                conn.execute("INSERT INTO user_chars (user_id, char_id, rarity, level, exp, limit_break) VALUES (?, ?, ?, 1, 0, 0)", (uid, cid, rar))
                lines.append(f"{pu_mark}🆕 **[{rar}] No.{cid:03d} {ch['name']}**（{ch['race']} / {ch['job']}）")

        conn.commit()
        conn.close()
        header = f"🌟 {pu_title} {count}連結果！" if is_limited else f"🎰 恒常キャラ召喚 {count}連結果！"
        embed = discord.Embed(title=header, description="\n".join(lines), color=discord.Color.gold() if is_limited else discord.Color.purple())
        await interaction.edit_original_response(embed=embed, view=self)

    async def _roll_weapon(self, interaction: discord.Interaction, count: int):
        await interaction.response.defer()
        uid = interaction.user.id
        self.db.ensure_player(uid)
        cost = count * 100
        conn = self.db.get_db()
        p = conn.execute("SELECT gems FROM players WHERE user_id = ?", (uid,)).fetchone()
        if p["gems"] < cost:
            conn.close()
            await interaction.followup.send(f"❌ ガチャ石不足（所持:`{p['gems']}` / 必要:`{cost}`）", ephemeral=True)
            return

        conn.execute("UPDATE players SET gems = gems - ? WHERE user_id = ?", (cost, uid))
        pools = {r: [w for w in self.db.WEAPONS.values() if w["rarity"] == r] for r in ["C", "R", "SR", "SSR", "UR", "LR"]}
        lines = []

        for _ in range(count):
            roll = random.randint(1, 1000)
            rar = "LR" if roll <= 8 else ("UR" if roll <= 40 else ("SSR" if roll <= 140 else ("SR" if roll <= 350 else ("R" if roll <= 650 else "C"))))
            wp = random.choice(pools[rar])
            wid = wp["id"]
            ex = conn.execute("SELECT * FROM user_weapons WHERE user_id = ? AND weapon_id = ?", (uid, wid)).fetchone()
            if ex:
                conn.execute("UPDATE user_weapons SET plus_level = plus_level + 1, count = count + 1 WHERE user_id = ? AND weapon_id = ?", (uid, wid))
                lines.append(f"⚒️ **[{rar}] {wp['name']}**（自動精錬！**+{ex['plus_level']+1}** に強化）")
            else:
                conn.execute("INSERT INTO user_weapons (user_id, weapon_id, plus_level, count) VALUES (?, ?, 0, 1)", (uid, wid))
                lines.append(f"🗡️ **[{rar}] {wp['name']}**（ATK+{wp['atk_bonus']} / HP+{wp['hp_bonus']}）")

        conn.commit()
        conn.close()
        embed = discord.Embed(title=f"⚔️ 武器召喚 {count}連結果！", description="\n".join(lines), color=discord.Color.teal())
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="👤 恒常単発(100石)", style=discord.ButtonStyle.primary, row=0)
    async def c1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._roll_char(interaction, 1, is_limited=False)

    @discord.ui.button(label="👤 恒常10連(1000石)", style=discord.ButtonStyle.success, row=0)
    async def c10(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._roll_char(interaction, 10, is_limited=False)

    @discord.ui.button(label="🌟 限定PU単発(100石)", style=discord.ButtonStyle.danger, row=1)
    async def lim1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._roll_char(interaction, 1, is_limited=True)

    @discord.ui.button(label="🌟 限定PU10連(1000石)", style=discord.ButtonStyle.danger, row=1)
    async def lim10(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._roll_char(interaction, 10, is_limited=True)

    @discord.ui.button(label="🗡️ 武器10連(1000石)", style=discord.ButtonStyle.secondary, row=2)
    async def w10(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._roll_weapon(interaction, 10)

    @discord.ui.button(label="📜 排出キャラ・PU一覧", style=discord.ButtonStyle.secondary, row=2)
    async def list_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        lim_on = self.db.get_state("limited_gacha_active", "0") == "1"
        lim_title = self.db.get_state("limited_gacha_title", "【期間限定】ピックアップ召喚")
        pu_cid = int(self.db.get_state("limited_gacha_char_id", "200"))
        pu_rate = int(self.db.get_state("limited_gacha_rate_permille", "30"))
        lr_rate = int(self.db.get_state("normal_lr_rate_permille", "5"))
        ur_rate = int(self.db.get_state("normal_ur_rate_permille", "30"))

        embed = discord.Embed(title="📜 召喚ガチャ 排出キャラ＆確率一覧", color=discord.Color.gold())
        if lim_on and pu_cid in self.db.CHARACTERS:
            pu = self.db.CHARACTERS[pu_cid]
            embed.add_field(
                name=f"🌟 開催中PU：{lim_title}",
                value=(
                    f"・対象：**`[{pu['base_rarity']}] No.{pu_cid:03d} {pu['name']}`**（排出率：**`{pu_rate/10:.1f}%`**）\n"
                    f"・種族/職：`{pu['race']}` / `{pu['job']}` ｜ 必殺：**{pu['ult_name']}**\n"
                    f"・基礎ステ：HP `{pu['base_hp']:,}` / ATK `{pu['base_atk']:,}` / DEF `{pu['base_def']:,}`"
                ),
                inline=False
            )

        god_chars = [c for c in self.db.CHARACTERS.values() if c.get("is_god_custom")]
        if god_chars:
            g_lines = [
                f"・`[{c['base_rarity']}] No.{c['id']:03d} {c['name']}`（HP:{c['base_hp']:,} / ATK:{c['base_atk']:,} / 必殺:{c['ult_name']}）"
                for c in god_chars[-10:]
            ]
            embed.add_field(name="👑 創造神が追加した特別キャラ一覧", value="\n".join(g_lines), inline=False)

        mcr_chars = [c for c in self.db.CHARACTERS.values() if c["base_rarity"] == "MCR" and not c.get("is_god_custom")]
        if mcr_chars:
            m_lines = [f"・`[MCR] No.{c['id']:03d} {c['name']}`（{c['passive_name']} / {c['ult_name']}）" for c in mcr_chars]
            embed.add_field(name="🌌 恒常MCRキャラ一覧（基本排出率: 0.2%）", value="\n".join(m_lines), inline=False)

        lr_chars = [c for c in self.db.CHARACTERS.values() if c["base_rarity"] == "LR" and not c.get("is_god_custom")]
        lr_lines = [f"・`[LR] No.{c['id']:03d} {c['name']}`（{c['passive_name']} / {c['ult_name']}）" for c in lr_chars]
        embed.add_field(
            name=f"🌈 恒常LRキャラ一覧（基本排出率: {lr_rate/10:.1f}% / UR: {ur_rate/10:.1f}%）",
            value="\n".join(lr_lines) or "なし",
            inline=False
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
