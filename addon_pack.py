import discord
import sys
import random
from datetime import datetime, timezone, timedelta

m = sys.modules["__main__"]
JST = timezone(timedelta(hours=9))

# ==========================================
# 0. MCR 2体組み込み（No.199, No.200 を初期MCR化）
# ==========================================
for _mcr_id in (199, 200):
    if _mcr_id in m.CHARACTERS and not m.CHARACTERS[_mcr_id].get("is_god_custom"):
        m.CHARACTERS[_mcr_id]["base_rarity"] = "MCR"
        m.CHARACTERS[_mcr_id]["base_hp"] = int(m.CHARACTERS[_mcr_id]["base_hp"] * 1.45)
        m.CHARACTERS[_mcr_id]["base_atk"] = int(m.CHARACTERS[_mcr_id]["base_atk"] * 1.45)
        m.CHARACTERS[_mcr_id]["base_def"] = int(m.CHARACTERS[_mcr_id]["base_def"] * 1.45)


def init_addon_tables():
    conn = m.get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_addons (
            user_id INTEGER PRIMARY KEY,
            last_login_date TEXT DEFAULT '',
            login_streak INTEGER DEFAULT 0,
            tower_floor INTEGER DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS title_conditions (
            title_name TEXT PRIMARY KEY,
            condition_text TEXT NOT NULL
        )
    """)
    base_conds = [
        ("【竜帝（ドラゴンエンペラー）】", "常設超強敵『星界の古竜王・バハムート改』を撃破する"),
        ("【絶対強者（アブソリュート）】", "常設超強敵『虚無の破壊神・アザトース』を撃破する"),
        ("【塔の支配者（タワーマスター）】", "無限の試練の塔・第100階層を完全制覇する"),
        ("【不屈の開拓者（7日連続達成）】", "7日連続でログインボーナスを受け取る"),
    ]
    for t_name, c_txt in base_conds:
        conn.execute("INSERT OR IGNORE INTO title_conditions (title_name, condition_text) VALUES (?, ?)", (t_name, c_txt))
    conn.commit()
    conn.close()


def ensure_addon_user(uid: int):
    init_addon_tables()
    conn = m.get_db()
    conn.execute("INSERT OR IGNORE INTO user_addons (user_id) VALUES (?)", (uid,))
    conn.commit()
    conn.close()


def register_title_condition(title_name: str, condition_text: str):
    init_addon_tables()
    conn = m.get_db()
    conn.execute("INSERT OR REPLACE INTO title_conditions (title_name, condition_text) VALUES (?, ?)", (title_name, condition_text))
    conn.commit()
    conn.close()


# ==========================================
# 1. 詰み防止：臨時キャラ削除モーダル
# ==========================================
class DeleteGodCharModal(discord.ui.Modal, title="🗑️ 創造神権限：臨時キャラの完全削除"):
    target_id = discord.ui.TextInput(
        label="削除するキャラ番号（201以上の数字）",
        placeholder="201",
        required=True,
        max_length=5
    )

    async def on_submit(self, interaction: discord.Interaction):
        val = self.target_id.value.strip()
        if not val.isdigit() or int(val) <= 200:
            await interaction.response.send_message("❌ 削除できるのは臨時キャラ（No.201以上）のみです。", ephemeral=True)
            return

        cid = int(val)
        conn = m.get_db()
        row = conn.execute("SELECT name FROM custom_chars WHERE id = ?", (cid,)).fetchone()
        if not row:
            conn.close()
            await interaction.response.send_message(f"❌ No.{cid} の臨時キャラは見つかりませんでした。", ephemeral=True)
            return

        c_name = row["name"]
        conn.execute("DELETE FROM custom_chars WHERE id = ?", (cid,))
        conn.execute("DELETE FROM user_chars WHERE char_id = ?", (cid,))
        conn.execute("UPDATE players SET equipped_char_id = 1 WHERE equipped_char_id = ?", (cid,))
        conn.commit()
        conn.close()

        m.CHARACTERS.pop(cid, None)
        await interaction.response.send_message(
            f"🗑️ 臨時キャラ **No.{cid}『{c_name}』** をデータベースおよび全プレイヤーの手持ちから完全削除しました。",
            ephemeral=True
        )


# ==========================================
# 2. コラボ開催管理（自作キャラ指定＋称号＆条件自動生成）
# ==========================================
def auto_generate_collab_title(event_name: str, boss_name: str) -> str:
    keyword_map = [
        ("ミリム", "【暴君】"),
        ("リムル", "【八星魔王】"),
        ("ヴェルドラ", "【暴風竜】"),
        ("シャドウ", "【陰の実力者】"),
        ("アルファ", "【七陰第一席】"),
        ("アインズ", "【死の支配者】"),
        ("ギルガメッシュ", "【英雄王】"),
        ("五条", "【現代最強】"),
        ("宿儺", "【呪いの王】"),
        ("キリト", "【黒の剣士】"),
        ("魔王", "【魔王殺し】"),
        ("竜", "【竜殺しの覇者】"),
        ("神", "【神殺し】"),
    ]
    for kw, title in keyword_map:
        if kw in boss_name or kw in event_name:
            return title
    short_boss = boss_name.split("・")[-1][:8]
    return f"【{short_boss}の征服者】"


class StartCollabModal(discord.ui.Modal, title="🎪 期間限定コラボイベント開催"):
    ev_name = discord.ui.TextInput(label="コラボ名（例：転生したらスライムだった件コラボ）", required=True, max_length=35)
    boss_name = discord.ui.TextInput(label="超強敵枠のボス名（例：ミリム＝ナーヴァ）", required=True, max_length=25)
    pu_cid = discord.ui.TextInput(label="ガチャPUにする自作キャラ番号（例：201）", default="201", required=True, max_length=5)
    boss_pwr = discord.ui.TextInput(label="超強敵の推奨戦闘力（例：180000）", default="180000", required=True, max_length=9)

    async def on_submit(self, interaction: discord.Interaction):
        ev = self.ev_name.value.strip()
        boss = self.boss_name.value.strip()
        cid = int(self.pu_cid.value.strip()) if self.pu_cid.value.strip().isdigit() else 201
        pwr = int(self.boss_pwr.value.strip()) if self.boss_pwr.value.strip().isdigit() else 180000

        auto_title = auto_generate_collab_title(ev, boss)
        cond_text = f"{ev}にて、超強敵枠{boss}を倒す"

        m.set_state("collab_active", "1")
        m.set_state("collab_name", ev)
        m.set_state("collab_boss_name", boss)
        m.set_state("collab_boss_pwr", str(pwr))
        m.set_state("collab_reward_title", auto_title)
        m.set_state("collab_reward_cond", cond_text)
        register_title_condition(auto_title, cond_text)

        m.set_state("limited_gacha_active", "1")
        m.set_state("limited_gacha_title", f"【コラボ限定】{ev}")
        m.set_state("limited_gacha_char_id", str(cid))
        m.set_state("limited_gacha_rate_permille", "40")

        c_name = m.CHARACTERS[cid]["name"] if cid in m.CHARACTERS else f"No.{cid}"
        await interaction.response.send_message(
            f"🎪 **『{ev}』** を開催しました！\n"
            f"・限定ガチャPU：**No.{cid} {c_name}**（排出率 4.0%）\n"
            f"・超強敵枠：**{boss}**（推奨戦闘力：`{pwr:,}`）\n"
            f"・自動生成された限定称号：**`{auto_title}`**\n"
            f"・入手条件記録：`{cond_text}`",
            ephemeral=True
        )


class CollabManageView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.button(label="🎪 コラボを開催する（名前＆超強敵設定）", style=discord.ButtonStyle.success, row=0)
    async def start_collab_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(StartCollabModal())

    @discord.ui.button(label="🛑 コラボイベントを終了する", style=discord.ButtonStyle.danger, row=0)
    async def end_collab_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        m.set_state("collab_active", "0")
        m.set_state("limited_gacha_active", "0")
        await interaction.response.send_message(
            "🛑 開催中のコラボイベントおよびコラボ限定ガチャを終了しました。（獲得済みのキャラ・称号はそのまま残ります）",
            ephemeral=True
        )
# ==========================================
# 3. 超強敵討伐 ＆ 入手条件付き称号図鑑システム
# ==========================================
PERMANENT_SUPER_BOSSES = [
    {
        "id": "perm_dragon",
        "name": "星界の古竜王・バハムート改",
        "pwr": 120000,
        "title": "【竜帝（ドラゴンエンペラー）】",
        "cond": "常設超強敵『星界の古竜王・バハムート改』を撃破する",
        "gems": 1500,
        "crys": 15,
    },
    {
        "id": "perm_azathoth",
        "name": "虚無の破壊神・アザトース",
        "pwr": 350000,
        "title": "【絶対強者（アブソリュート）】",
        "cond": "常設超強敵『虚無の破壊神・アザトース』を撃破する",
        "gems": 3000,
        "crys": 30,
    }
]


class SuperBossSelect(discord.ui.Select):
    def __init__(self, bosses: list[dict]):
        options = [
            discord.SelectOption(
                label=f"👹 {b['name']}（報酬称号: {b['title']}）"[:100],
                value=b["id"],
                description=f"推奨戦闘力: {b['pwr']:,}"
            )
            for b in bosses
        ]
        super().__init__(placeholder="挑戦する超強敵を選択してください", min_values=1, max_values=1, options=options)
        self.boss_map = {b["id"]: b for b in bosses}

    async def callback(self, interaction: discord.Interaction):
        uid = interaction.user.id
        m.ensure_player(uid)
        b = self.boss_map[next(iter(self.values))]
        _, _, _, my_pwr = m.get_player_combat_stats(uid)

        if my_pwr >= b["pwr"]:
            register_title_condition(b["title"], b["cond"])
            m.unlock_title(uid, b["title"])
            await m.sync_rank_and_badges(interaction.guild, uid)

            conn = m.get_db()
            conn.execute("UPDATE players SET gems = gems + ?, crystals = crystals + ? WHERE user_id = ?", (b["gems"], b["crys"], uid))
            conn.commit()
            conn.close()

            embed = discord.Embed(
                title=f"🎊 超強敵『{b['name']}』完全撃破！！",
                description=(
                    f"あなたの戦闘力：**`{my_pwr:,}`** vs 超強敵：**`{b['pwr']:,}`**\n\n"
                    f"🏅 **限定称号獲得**：**`{b['title']}`**\n"
                    f"📜 **入手条件**：`{b['cond']}`\n"
                    f"🎁 **討伐報酬**：💎`+{b['gems']:,}石` ＋ 🔮`+{b['crys']}結晶`"
                ),
                color=discord.Color.gold()
            )
            await interaction.response.edit_message(embed=embed, view=None)
        else:
            embed = discord.Embed(
                title=f"💀 超強敵『{b['name']}』に圧倒された…",
                description=(
                    f"・あなたの戦闘力：**`{my_pwr:,}`**\n"
                    f"・超強敵の推奨戦闘力：**`{b['pwr']:,}`**\n"
                    f"・討伐時獲得称号：**`{b['title']}`**（条件：`{b['cond']}`）\n\n"
                    "▶ キャラのMCR進化・武器精錬・領地施設を極限まで鍛えて再挑戦しよう！"
                ),
                color=discord.Color.dark_red()
            )
            await interaction.response.edit_message(embed=embed, view=None)


async def open_super_boss_panel(interaction: discord.Interaction):
    uid = interaction.user.id
    m.ensure_player(uid)
    bosses = list(PERMANENT_SUPER_BOSSES)

    if m.get_state("collab_active", "0") == "1":
        bosses.insert(0, {
            "id": "collab_super",
            "name": f"【コラボ超強敵】{m.get_state('collab_boss_name', '異界の覇者')}",
            "pwr": int(m.get_state("collab_boss_pwr", "180000")),
            "title": m.get_state("collab_reward_title", "【異界の征服者】"),
            "cond": m.get_state("collab_reward_cond", "コラボイベントにて超強敵を撃破する"),
            "gems": 2500,
            "crys": 25,
        })

    desc_lines = [
        f"・**{b['name']}**（推奨戦闘力 `{b['pwr']:,}`）\n　└ 称号：**`{b['title']}`**（条件：`{b['cond']}`）"
        for b in bosses
    ]
    embed = discord.Embed(
        title="👹 超強敵討伐ゲート（限定称号獲得）",
        description="常識外れの強さを誇る『超強敵』を撃破すると、専用の希少称号が解放されます！\n\n" + "\n\n".join(desc_lines),
        color=discord.Color.dark_purple()
    )
    view = discord.ui.View(timeout=120)
    view.add_item(SuperBossSelect(bosses))
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def open_title_codex(interaction: discord.Interaction):
    uid = interaction.user.id
    m.ensure_player(uid)
    init_addon_tables()
    conn = m.get_db()
    p = conn.execute("SELECT unlocked_titles FROM players WHERE user_id = ?", (uid,)).fetchone()
    conds = conn.execute("SELECT title_name, condition_text FROM title_conditions").fetchall()
    conn.close()

    owned = set(t for t in p["unlocked_titles"].split("|") if t)
    lines = []
    for c in conds:
        mark = "✅【所持】" if c["title_name"] in owned else "🔒【未獲得】"
        lines.append(f"{mark} **`{c['title_name']}`**\n　└ 入手条件：{c['condition_text']}")

    embed = discord.Embed(
        title="🏅 特別称号図鑑 ＆ 入手条件一覧",
        description="\n".join(lines[:20]) or "登録された特別称号はまだありません。",
        color=discord.Color.gold()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)
# ==========================================
# 4. 1日1回ログインボーナス ＆ 100階層タワー
# ==========================================
async def claim_daily_login(interaction: discord.Interaction):
    uid = interaction.user.id
    m.ensure_player(uid)
    ensure_addon_user(uid)

    now_jst = datetime.now(JST)
    today_str = now_jst.strftime("%Y-%m-%d")
    yesterday_str = (now_jst - timedelta(days=1)).strftime("%Y-%m-%d")

    conn = m.get_db()
    row = conn.execute("SELECT last_login_date, login_streak FROM user_addons WHERE user_id = ?", (uid,)).fetchone()
    if row["last_login_date"] == today_str:
        conn.close()
        await interaction.response.send_message(
            f"✅ 本日分（{today_str}）のログインボーナスは受け取り済みです！（現在 **{row['login_streak']}日連続** ログイン中）",
            ephemeral=True
        )
        return

    new_streak = (row["login_streak"] + 1) if row["last_login_date"] == yesterday_str else 1
    bonus_gems = 300
    bonus_crys = 2
    special_msg = ""

    if new_streak % 7 == 0:
        bonus_gems += 1500
        bonus_crys += 10
        m.unlock_title(uid, "【不屈の開拓者（7日連続達成）】")
        await m.sync_rank_and_badges(interaction.guild, uid)
        special_msg = "\n🎉 **7日連続ログイン達成ボーナス！** 追加で **💎1,500石 ＋ 🔮10結晶 ＋ 限定称号** を獲得！"

    conn.execute("UPDATE user_addons SET last_login_date = ?, login_streak = ? WHERE user_id = ?", (today_str, new_streak, uid))
    conn.execute("UPDATE players SET gems = gems + ?, crystals = crystals + ? WHERE user_id = ?", (bonus_gems, bonus_crys, uid))
    conn.commit()
    conn.close()

    await interaction.response.send_message(
        f"📅 **ログインボーナス獲得！（連続 {new_streak}日目）**\n"
        f"・💎 ガチャ石：**`+{bonus_gems:,} 個`**\n"
        f"・🔮 進化結晶：**`+{bonus_crys} 個`**{special_msg}",
        ephemeral=True
    )


class TowerChallengeView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=180)
        self.user_id = user_id

    @discord.ui.button(label="⚔️ 次の階層へ挑む！", style=discord.ButtonStyle.danger)
    async def climb_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 本人のみ操作できます。", ephemeral=True)
            return

        uid = self.user_id
        ensure_addon_user(uid)
        conn = m.get_db()
        row = conn.execute("SELECT tower_floor FROM user_addons WHERE user_id = ?", (uid,)).fetchone()
        floor = row["tower_floor"]

        if floor > 100:
            conn.close()
            await interaction.response.send_message("👑 すでに全100階層を完全制覇しています！", ephemeral=True)
            return

        _, _, _, my_pwr = m.get_player_combat_stats(uid)
        req_pwr = int(800 * (1.072 ** (floor - 1)))

        if my_pwr >= req_pwr:
            rw_gems = 100 if floor % 10 != 0 else 1000
            rw_crys = 1 if floor % 10 != 0 else 10
            rw_gold = floor * 300
            next_floor = floor + 1

            conn.execute("UPDATE user_addons SET tower_floor = ? WHERE user_id = ?", (next_floor, uid))
            conn.execute("UPDATE players SET gems = gems + ?, crystals = crystals + ?, gold = gold + ? WHERE user_id = ?", (rw_gems, rw_crys, rw_gold, uid))
            conn.commit()
            conn.close()

            title_note = ""
            if floor == 100:
                m.unlock_title(uid, "【塔の支配者（タワーマスター）】")
                await m.sync_rank_and_badges(interaction.guild, uid)
                title_note = "\n👑 **全100階層制覇達成！限定称号『【塔の支配者（タワーマスター）】』を獲得！**"
            elif floor % 10 == 0:
                title_note = f"\n🎉 **{floor}階ボス撃破記念ボーナス** 獲得！"

            embed = discord.Embed(
                title=f"🗼 試練の塔 第{floor}階 — 突破成功！！",
                description=(
                    f"あなたの戦闘力：`{my_pwr:,}` vs 守護者：`{req_pwr:,}`\n\n"
                    f"🎁 **階層突破報酬**：💎`+{rw_gems:,}石` / 🔮`+{rw_crys}結晶` / 💰`+{rw_gold:,}G`{title_note}\n"
                    f"▶ 次の挑戦階層：**第{min(100, next_floor)}階**"
                ),
                color=discord.Color.gold()
            )
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            conn.close()
            embed = discord.Embed(
                title=f"💀 試練の塔 第{floor}階 — 敗北...",
                description=(
                    f"・あなたの戦闘力：**`{my_pwr:,}`**\n"
                    f"・第{floor}階 推奨戦闘力：**`{req_pwr:,}`**\n\n"
                    "キャラの進化・武器強化・施設レベルアップをして再挑戦しよう！"
                ),
                color=discord.Color.dark_grey()
            )
            await interaction.response.edit_message(embed=embed, view=self)


async def open_tower_panel(interaction: discord.Interaction):
    uid = interaction.user.id
    m.ensure_player(uid)
    ensure_addon_user(uid)
    conn = m.get_db()
    row = conn.execute("SELECT tower_floor FROM user_addons WHERE user_id = ?", (uid,)).fetchone()
    top5 = conn.execute("SELECT user_id, tower_floor FROM user_addons ORDER BY tower_floor DESC LIMIT 5").fetchall()
    conn.close()

    floor = row["tower_floor"]
    _, _, _, my_pwr = m.get_player_combat_stats(uid)
    req_pwr = int(800 * (1.072 ** (min(100, floor) - 1)))
    rank_txt = "\n".join([f"`{i+1}位` <@{r['user_id']}> — **第{min(100, r['tower_floor']-1)}階突破**" for i, r in enumerate(top5)])

    embed = discord.Embed(
        title="🗼 無限の試練の塔（全100階層）",
        description=(
            f"📍 **現在の挑戦階層**：**第{min(100, floor)}階**（{'制覇済' if floor > 100 else f'推奨戦闘力 `{req_pwr:,}`'}）\n"
            f"⚔️ **あなたの戦闘力**：**`{my_pwr:,}`**\n\n"
            f"**【🏆 試練の塔 踏破ランキング TOP5】**\n{rank_txt}"
        ),
        color=discord.Color.purple()
    )
    await interaction.response.send_message(embed=embed, view=TowerChallengeView(uid), ephemeral=True)
# ==========================================
# 5. 騎士団対抗戦（ランキング閲覧 ＆ 優勝報酬配布）
# ==========================================
async def open_guild_war_panel(interaction: discord.Interaction):
    conn = m.get_db()
    guilds = conn.execute("SELECT id, name, level, stars, leader_id FROM guilds ORDER BY stars DESC, level DESC LIMIT 10").fetchall()
    conn.close()

    if not guilds:
        await interaction.response.send_message("📭 現在創設されている騎士団はまだありません。", ephemeral=True)
        return

    lines = []
    for i, g in enumerate(guilds, 1):
        crown = "👑 " if i == 1 else f"`{i}位` "
        lines.append(f"{crown}**『{g['name']}』**（Lv.{g['level']}）— 功績：**`{g['stars']:,} ★`**（団長：<@{g['leader_id']}>）")

    embed = discord.Embed(
        title="🏆 王国騎士団対抗戦 — 現在の覇権ランキング",
        description=(
            "各騎士団の総功績（`★`）で競う対抗戦ランキングです！\n"
            "集計確定時、**1位の騎士団メンバー全員** に限定称号 **`【王国の守護騎士団】`** ＋ **💎ガチャ石 2,000個** が贈呈されます！\n\n"
            + "\n".join(lines)
        ),
        color=discord.Color.gold()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


async def settle_guild_war(guild: discord.Guild | None) -> str:
    conn = m.get_db()
    top_g = conn.execute("SELECT id, name, stars FROM guilds WHERE stars > 0 ORDER BY stars DESC, level DESC LIMIT 1").fetchone()
    if not top_g:
        conn.close()
        return "⚠️ 功績（★）を獲得している騎士団がまだいないため、対抗戦集計をスキップしました。"

    members = conn.execute("SELECT user_id FROM players WHERE guild_id = ?", (top_g["id"],)).fetchall()
    register_title_condition("【王国の守護騎士団】", "騎士団対抗戦にて総合1位に輝く")

    for r in members:
        uid = r["user_id"]
        conn.execute("UPDATE players SET gems = gems + 2000 WHERE user_id = ?", (uid,))
        m.unlock_title(uid, "【王国の守護騎士団】")
        if guild:
            await m.sync_rank_and_badges(guild, uid)

    conn.commit()
    conn.close()
    return f"🏆 **騎士団対抗戦 結果確定！**\n優勝騎士団 **『{top_g['name']}』**（`{top_g['stars']:,} ★`）のメンバー **{len(members)}名** に **💎2,000石 ＋ 限定称号『【王国の守護騎士団】』** を配布しました！"


# ==========================================
# 6. 既存パネル・創造神パネル・騎士団パネルへの安全統合
# ==========================================
class ExtendedQuestView(m.QuestOnlyView):
    @discord.ui.button(label="🗼 試練の塔(100階)", style=discord.ButtonStyle.primary, custom_id="persist_panel:quest_tower", row=1)
    async def btn_tower(self, interaction: discord.Interaction, button: discord.ui.Button):
        await open_tower_panel(interaction)

    @discord.ui.button(label="👹 超強敵(限定称号)", style=discord.ButtonStyle.danger, custom_id="persist_panel:quest_superboss", row=1)
    async def btn_superboss(self, interaction: discord.Interaction, button: discord.ui.Button):
        await open_super_boss_panel(interaction)


class ExtendedGuildView(m.GuildOnlyView):
    @discord.ui.button(label="🏆 騎士団対抗戦順位", style=discord.ButtonStyle.primary, custom_id="persist_panel:guild_war", row=0)
    async def btn_guild_war(self, interaction: discord.Interaction, button: discord.ui.Button):
        await open_guild_war_panel(interaction)


class ExtendedProfileView(m.ProfileOnlyView):
    @discord.ui.button(label="📅 今日のログボ", style=discord.ButtonStyle.success, custom_id="persist_panel:profile_login", row=0)
    async def btn_login(self, interaction: discord.Interaction, button: discord.ui.Button):
        await claim_daily_login(interaction)

    @discord.ui.button(label="🏅 称号図鑑・条件", style=discord.ButtonStyle.primary, custom_id="persist_panel:profile_titles", row=1)
    async def btn_title_codex(self, interaction: discord.Interaction, button: discord.ui.Button):
        await open_title_codex(interaction)


class SafeGodControlView(m.GodControlView):
    @discord.ui.button(label="🎪 コラボ開催・終了", style=discord.ButtonStyle.primary, row=2)
    async def collab_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        status = f"🟢 開催中：{m.get_state('collab_name', '')}" if m.get_state("collab_active", "0") == "1" else "🔴 未開催"
        await interaction.response.send_message(
            f"🎪 **コラボイベント管理パネル**（現在：{status}）\nあなたが「🧬 臨時強キャラを創造する」で作ったキャラ番号を指定して開催できます。",
            view=CollabManageView(),
            ephemeral=True
        )

    @discord.ui.button(label="🗑️ 臨時キャラ削除", style=discord.ButtonStyle.danger, row=2)
    async def delete_char_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DeleteGodCharModal())

    @discord.ui.button(label="🏆 対抗戦結果確定", style=discord.ButtonStyle.success, row=3)
    async def settle_war_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        msg = await settle_guild_war(interaction.guild)
        await interaction.response.send_message(msg, ephemeral=True)

    @discord.ui.button(label="🛑 レイド強制終了", style=discord.ButtonStyle.secondary, row=3)
    async def stop_raid_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        m.set_state("raid_active", "0")
        m.set_state("raid_hp", "0")
        await interaction.response.send_message("🛑 開催中の運営レイドボスを強制終了（撤退）させました。", ephemeral=True)

    @discord.ui.button(label="❄️ ゲリラ即時終了", style=discord.ButtonStyle.secondary, row=3)
    async def stop_guerrilla_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        m.set_state("guerrilla_active", "0")
        m.set_state("guerrilla_end_ts", "0")
        await interaction.response.send_message("❄️ 開催中のゲリライベントを即時終了しました。", ephemeral=True)


class SafeGuildPanelView(m.GuildPanelView):
    def _latest(self, uid: int):
        conn = m.get_db()
        p = conn.execute("SELECT guild_id, guild_role FROM players WHERE user_id = ?", (uid,)).fetchone()
        conn.close()
        return (p["guild_id"], p["guild_role"]) if p else (0, "")

    async def lvup_g_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid, g_role = self._latest(interaction.user.id)
        if gid == 0 or g_role not in ("団長", "副団長"):
            await interaction.response.send_message("❌ この操作は【団長】または【副団長】のみ実行できます。", ephemeral=True)
            return
        self.guild_id, self.guild_role = gid, g_role
        await super().lvup_g_btn.callback(self, interaction)

    async def vice_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid, g_role = self._latest(interaction.user.id)
        if gid == 0 or g_role != "団長":
            await interaction.response.send_message("❌ 副団長の任命は【団長】のみ可能です。", ephemeral=True)
            return
        self.guild_id, self.guild_role = gid, g_role
        await super().vice_btn.callback(self, interaction)

    async def leave_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        gid, g_role = self._latest(interaction.user.id)
        if gid == 0:
            await interaction.response.send_message("❌ 騎士団に所属していません。", ephemeral=True)
            return

        conn = m.get_db()
        g = conn.execute("SELECT * FROM guilds WHERE id = ?", (gid,)).fetchone()
        others = conn.execute(
            "SELECT user_id FROM players WHERE guild_id = ? AND user_id != ? ORDER BY CASE guild_role WHEN '副団長' THEN 1 ELSE 2 END",
            (gid, interaction.user.id)
        ).fetchall()

        if g_role == "団長" and others:
            next_leader = others["user_id"]
            if interaction.guild and g and g["role_id"]:
                rl = interaction.guild.get_role(g["role_id"])
                if rl:
                    try:
                        await interaction.user.remove_roles(rl)
                    except Exception:
                        pass
            conn.execute("UPDATE players SET guild_id = 0, guild_role = '' WHERE user_id = ?", (interaction.user.id,))
            conn.execute("UPDATE players SET guild_role = '団長' WHERE user_id = ?", (next_leader,))
            conn.execute("UPDATE guilds SET leader_id = ?, vice_leader_id = CASE WHEN vice_leader_id = ? THEN 0 ELSE vice_leader_id END WHERE id = ?", (next_leader, next_leader, gid))
            conn.commit()
            conn.close()
            await interaction.response.edit_message(
                content=f"👑 次の団長を <@{next_leader}> に引き継ぎ、あなたは騎士団を退団しました！",
                embed=None,
                view=None
            )
            return

        conn.close()
        self.guild_id, self.guild_role = gid, g_role
        await super().leave_btn.callback(self, interaction)


# main.py 側の各Viewを拡張版へ自動差し替え
m.QuestOnlyView = ExtendedQuestView
m.GuildOnlyView = ExtendedGuildView
m.ProfileOnlyView = ExtendedProfileView
m.GodControlView = SafeGodControlView
m.GuildPanelView = SafeGuildPanelView
print("✨ addon_pack.py: 全5大機能（コラボ・超強敵称号・ログボ・100階層・対抗戦）＋MCR2体＋詰み防止の適用完了！")
