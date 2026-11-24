import discord
from discord import app_commands
from discord.ext import commands, tasks
import sqlite3
import os
import random
import asyncio
from datetime import datetime, timezone, timedelta
import sys
from gacha import GachaPanelView

# ==========================================
# 1. 基本設定・環境変数
# ==========================================
TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
DB_PATH = "commander_rpg.db"
JST = timezone(timedelta(hours=9))

GOD_TITLE = "【👑創造神（ワールドメーカー）】"

RARITIES = ["C", "R", "SR", "SSR", "UR", "LR", "MCR"]
RARITY_MULT = {
    "C": 1.0,
    "R": 1.35,
    "SR": 1.8,
    "SSR": 2.4,
    "UR": 3.3,
    "LR": 4.6,
    "MCR": 6.8,
}
EVOLVE_COST = {
    "C": (1, 500),
    "R": (3, 1500),
    "SR": (8, 5000),
    "SSR": (20, 15000),
    "UR": (50, 50000),
    "LR": (120, 150000),
}
SELL_REWARD = {
    "C": (150, 0),
    "R": (400, 1),
    "SR": (1200, 2),
    "SSR": (3500, 5),
    "UR": (10000, 12),
    "LR": (30000, 30),
    "MCR": (100000, 80),
}

RANK_TIERS = [
    (0, "見習い冒険者"),
    (1000, "駆け出しの剣士"),
    (1200, "熟練の戦士"),
    (1500, "王宮騎士"),
    (1900, "英雄候補"),
    (2400, "伝説の勇者"),
    (3000, "神話の超越者"),
    (4000, "暗黒の騎士"),
    (5500, "無戦無敗の武将"),
]

GENERATION_TIERS = [
    (10, "【創世の勇者】"),
    (100, "【第一世代】"),
    (1000, "【第二世代】"),
]

# ==========================================
# 2. 全200キャラ ＆ 全50武器 マスタ定義
# ==========================================
RACES = ["人間", "エルフ", "竜人", "魔族", "機甲兵", "神族", "獣人", "精霊", "不死王", "星界人"]
JOBS = ["剣聖", "大魔導士", "暗殺者", "聖騎士", "竜騎士", "召喚士", "狂戦士", "機工師", "死霊術師", "覇王"]

FIRST_NAMES = [
    "アレス", "ゼクス", "カイン", "ルシウス", "レオン", "ヴァル", "セフィロス", "ジーク", "アルト", "クロノ",
    "リリス", "セレス", "フレイヤ", "アテナ", "ルナ", "ステラ", "イリス", "ミコト", "カグラ", "シオン",
    "ラグナ", "ソル", "ノクス", "ゼロ", "オメガ", "カイザー", "ドラグ", "フェンリル", "バハムート", "オーディン",
    "セラフィム", "ベリアル", "アザゼル", "メフィスト", "リヴァイア", "イフリート", "シヴァ", "ラムウ", "タイタン", "ディアボロス"
]
EPITHETS = [
    "紅蓮の", "蒼穹の", "漆黒の", "白銀の", "黄金の", "終焉の", "創世の", "雷鳴の", "氷結の", "星屑の",
    "深淵の", "閃光の", "混沌の", "聖なる", "狂乱の", "不滅の", "幻影の", "覇道の", "天翔る", "絶望の"
]
PASSIVE_SKILLS = [
    ("竜殺しの闘気", "atk_up", 0.20, "攻撃力+20%"),
    ("絶対防御陣", "def_up", 0.25, "防御力+25%"),
    ("必殺の極意", "crit_up", 30, "会心率+30%"),
    ("吸血の呪印", "lifesteal", 0.15, "与ダメージの15%HP回復"),
    ("背水の陣", "berserk", 0.45, "HP50%以下で攻撃力+45%"),
    ("神速の加護", "evade", 20, "回避率+20%"),
    ("魔力暴走", "ult_up", 0.35, "必殺技ダメージ+35%"),
    ("不屈の魂", "guts", 1, "致死ダメージを1度だけHP1で耐える"),
    ("覇王の威圧", "pierce", 0.30, "敵の防御力を30%無視"),
    ("再生の祝福", "regen", 0.10, "毎ターン最大HPの10%回復"),
]
ULTIMATE_PREFIX = ["極限奥義・", "神罰・", "滅界剣・", "禁呪・", "龍王咆哮・", "星辰崩壊・", "無双連撃・", "終末の", "天照・", "深淵蝕・"]
ULTIMATE_NOUNS = [
    "ラグナロク", "エクスカリバー", "メギドフレア", "ゼロレクイエム", "天元突破",
    "次元断絶", "神羅万象", "黒棺", "インフィニティ", "アルテマウェポン",
    "星天爆裂", "絶対零度", "紅蓮地獄", "雷神一閃", "虚無の波動",
    "覇王翔吼拳", "創世の光", "エンドオブワールド", "ソウルイーター", "グランドクロス"
]
WEAPON_TYPES = ["大剣", "魔導書", "双剣", "聖槍", "神弓", "戦斧", "魔銃", "妖刀", "神杖", "籠手"]
WEAPON_PREFIX = ["古びた", "鋼鉄の", "銀光の", "竜鱗の", "魔導の", "聖騎士の", "深淵の", "覇王の", "神話の", "創世神の"]
def generate_all_200_characters() -> dict[int, dict]:
    rng = random.Random(20261124)
    chars = {}
    used_names = set()
    for cid in range(1, 201):
        while True:
            ep = EPITHETS[(cid + rng.randint(0, 19)) % len(EPITHETS)]
            fn = FIRST_NAMES[(cid * 3 + rng.randint(0, 39)) % len(FIRST_NAMES)]
            full_name = f"{ep}{fn}"
            if full_name not in used_names:
                used_names.add(full_name)
                break

        if cid <= 70:
            base_rarity = "C"
        elif cid <= 125:
            base_rarity = "R"
        elif cid <= 165:
            base_rarity = "SR"
        elif cid <= 188:
            base_rarity = "SSR"
        elif cid <= 197:
            base_rarity = "UR"
        else:
            base_rarity = "LR"

        race = RACES[(cid - 1) % len(RACES)]
        job = JOBS[((cid - 1) // 2 + rng.randint(0, 9)) % len(JOBS)]
        p_name, p_type, p_val, p_desc = PASSIVE_SKILLS[(cid + rng.randint(0, 9)) % len(PASSIVE_SKILLS)]
        ult_name = f"{ULTIMATE_PREFIX[cid % len(ULTIMATE_PREFIX)]}{ULTIMATE_NOUNS[(cid * 7) % len(ULTIMATE_NOUNS)]}"

        base_hp = 520 + (cid * 4) + rng.randint(40, 180)
        base_atk = 85 + (cid // 2) + rng.randint(10, 40)
        base_def = 55 + (cid // 3) + rng.randint(5, 25)

        chars[cid] = {
            "id": cid,
            "name": full_name,
            "base_rarity": base_rarity,
            "race": race,
            "job": job,
            "passive_name": p_name,
            "passive_type": p_type,
            "passive_val": p_val,
            "passive_desc": p_desc,
            "ult_name": ult_name,
            "base_hp": base_hp,
            "base_atk": base_atk,
            "base_def": base_def,
            "is_god_custom": False,
        }
    return chars

def generate_all_50_weapons() -> dict[int, dict]:
    rng = random.Random(998877)
    weapons = {}
    for wid in range(1, 51):
        if wid <= 18:
            rar = "C"
        elif wid <= 30:
            rar = "R"
        elif wid <= 39:
            rar = "SR"
        elif wid <= 45:
            rar = "SSR"
        elif wid <= 48:
            rar = "UR"
        else:
            rar = "LR"
        w_pref = WEAPON_PREFIX[(wid - 1) // 5]
        w_type = WEAPON_TYPES[(wid - 1) % 10]
        w_name = f"{w_pref}{w_type}"
        atk_bonus = 30 + (wid * 12) + rng.randint(5, 25)
        hp_bonus = 100 + (wid * 35) + rng.randint(20, 80)
        weapons[wid] = {
            "id": wid,
            "name": w_name,
            "rarity": rar,
            "atk_bonus": atk_bonus,
            "hp_bonus": hp_bonus,
        }
    return weapons

CHARACTERS = generate_all_200_characters()
WEAPONS = generate_all_50_weapons()

STORY_CHAPTERS = [
    (1, "第1章：辺境の覚醒", "魔物溢れる静寂の草原で、名もなき冒険者が最初の剣を振るう。", "草原の暴君・キングスライム", 1200, 120, "【草原の開拓者（フロンティア）】", 300),
    (2, "第2章：霧深き古樹の迷宮", "太陽の光すら届かぬ呪われた樹海で、古代の守護者が牙を剥く。", "呪縛の古樹・エルダートレント", 3200, 300, "【迷宮の踏破者（ラビリンス）】", 500),
    (3, "第3章：紅蓮の溶岩渓谷", "大地が裂けマグマが噴き上がる灼熱の谷に、炎の魔神が降臨する。", "業火の魔神・イフリートロード", 8000, 660, "【業火の征服者（ブレイズロード）】", 800),
    (4, "第4章：永久凍土の氷結神殿", "すべてを凍てつかせる極寒の神殿最奥で、氷の女王が眠りから覚める。", "絶対零度・コキュートス", 20000, 1500, "【氷河の支配者（フロストルーラー）】", 1200),
    (5, "第5章：雲海を越える天空城", "雷鳴轟く天空の浮遊要塞で、誇り高き古竜との空中決戦が幕を開ける。", "天空の覇竜・バハムート", 50000, 3500, "【竜殺しの英雄（ドラゴンスレイヤー）】", 2000),
    (6, "第6章：深淵の魔界門", "異界へと繋がる巨大な黒門が開かれ、魔界の軍勢を率いる将軍が立ち塞がる。", "魔界大将軍・ベリアル", 120000, 8000, "【深淵の討伐者（アビスハンター）】", 3000),
    (7, "第7章：黄昏の血塗られた王都", "陥落したかつての王都で、闇に堕ちた伝説の騎士団長と刃を交える。", "堕天の黒騎士・カイン", 260000, 16000, "【王都の解放者（セイヴァー）】", 4000),
    (8, "第8章：終焉の魔王城・玉座", "世界を闇に染めようとする魔王との最終決戦。真の王の座を懸けた死闘！", "終焉の魔王・ルシファー", 550000, 34000, "【覚醒魔王（トゥルーロード）】", 6000),
    (9, "第9章：次元の狭間・星界回廊", "魔王を倒した先に現れた次元の亀裂。世界の理を守る機神が審判を下す。", "星界の審判者・メタトロン", 1200000, 75000, "【次元を超えし者（ディメンション）】", 8000),
    (10, "最終章：創世の神域", "創造神の試練の最終段階。すべてを超越した者だけが真の頂点へ辿り着く！", "創世の守護神・オメガ", 2500000, 150000, "【星王神（アストラルゴッド）】", 15000),
]
# ==========================================
# 3. データベース初期化 ＆ 創造神カスタムキャラ読込
# ==========================================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS players (
            user_id INTEGER PRIMARY KEY,
            gems INTEGER DEFAULT 1500,
            gold INTEGER DEFAULT 1500,
            crystals INTEGER DEFAULT 0,
            story_chapter INTEGER DEFAULT 1,
            rank_points INTEGER DEFAULT 1000,
            equipped_char_id INTEGER DEFAULT 1,
            equipped_weapon_id INTEGER DEFAULT 0,
            guild_id INTEGER DEFAULT 0,
            guild_role TEXT DEFAULT '',
            active_title TEXT DEFAULT '【異世界転生者（アザーワールド）】',
            unlocked_titles TEXT DEFAULT '【異世界転生者（アザーワールド）】',
            gen_role TEXT DEFAULT ''
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_chars (
            user_id INTEGER NOT NULL,
            char_id INTEGER NOT NULL,
            rarity TEXT NOT NULL,
            level INTEGER DEFAULT 1,
            exp INTEGER DEFAULT 0,
            limit_break INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, char_id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_weapons (
            user_id INTEGER NOT NULL,
            weapon_id INTEGER NOT NULL,
            plus_level INTEGER DEFAULT 0,
            count INTEGER DEFAULT 1,
            PRIMARY KEY (user_id, weapon_id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS custom_chars (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            base_rarity TEXT NOT NULL,
            race TEXT NOT NULL,
            job TEXT NOT NULL,
            passive_name TEXT NOT NULL,
            passive_type TEXT NOT NULL,
            passive_val REAL NOT NULL,
            passive_desc TEXT NOT NULL,
            ult_name TEXT NOT NULL,
            base_hp INTEGER NOT NULL,
            base_atk INTEGER NOT NULL,
            base_def INTEGER NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS guilds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            leader_id INTEGER NOT NULL,
            vice_leader_id INTEGER DEFAULT 0,
            role_id INTEGER DEFAULT 0,
            channel_id INTEGER DEFAULT 0,
            stars INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS server_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS raid_damage (
            user_id INTEGER PRIMARY KEY,
            damage INTEGER DEFAULT 0
        )
    """)
    defaults = {
        "guerrilla_active": "0",
        "guerrilla_end_ts": "0",
        "raid_active": "0",
        "raid_name": "",
        "raid_max_hp": "0",
        "raid_hp": "0",
        "champion_id": "0",
        "limited_gacha_active": "0",
        "limited_gacha_title": "【期間限定】創造神降臨ピックアップ召喚",
        "limited_gacha_char_id": "200",
        "limited_gacha_rate_permille": "30",
        "normal_lr_rate_permille": "5",
        "normal_ur_rate_permille": "30"
    }
    for k, v in defaults.items():
        c.execute("INSERT OR IGNORE INTO server_state (key, value) VALUES (?, ?)", (k, v))
    conn.commit()
    conn.close()
    ensure_facility_table()
    reload_custom_characters()
def reload_custom_characters():
    conn = get_db()
    rows = conn.execute("SELECT * FROM custom_chars").fetchall()
    conn.close()
    for r in rows:
        CHARACTERS[r["id"]] = {
            "id": r["id"],
            "name": r["name"],
            "base_rarity": r["base_rarity"],
            "race": r["race"],
            "job": r["job"],
            "passive_name": r["passive_name"],
            "passive_type": r["passive_type"],
            "passive_val": r["passive_val"],
            "passive_desc": r["passive_desc"],
            "ult_name": r["ult_name"],
            "base_hp": r["base_hp"],
            "base_atk": r["base_atk"],
            "base_def": r["base_def"],
            "is_god_custom": True,
        }

def ensure_facility_table():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_facilities (
            user_id INTEGER PRIMARY KEY,
            training_lv INTEGER DEFAULT 1,
            blacksmith_lv INTEGER DEFAULT 1,
            lab_lv INTEGER DEFAULT 1,
            trade_lv INTEGER DEFAULT 1
        )
    """)
    conn.commit()
    conn.close()

def get_state(key: str, default: str = "0") -> str:
    conn = get_db()
    row = conn.execute("SELECT value FROM server_state WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default

def set_state(key: str, value: str):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO server_state (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def ensure_player(user_id: int):
    ensure_facility_table()
    conn = get_db()
    row = conn.execute("SELECT user_id FROM players WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        total_players = conn.execute("SELECT COUNT(*) AS c FROM players").fetchone()["c"] + 1
        gen_name = "【第二世代】"
        for limit, g_title in GENERATION_TIERS:
            if total_players <= limit:
                gen_name = g_title
                break
        init_title = GOD_TITLE if user_id == OWNER_ID else "【異世界転生者（アザーワールド）】"
        conn.execute(
            "INSERT INTO players (user_id, gen_role, active_title, unlocked_titles) VALUES (?, ?, ?, ?)",
            (user_id, gen_name, init_title, init_title)
        )
        c1 = CHARACTERS.get(1)
        conn.execute(
            "INSERT INTO user_chars (user_id, char_id, rarity, level, exp, limit_break) VALUES (?, 1, ?, 1, 0, 0)",
            (user_id, c1["base_rarity"])
        )
    conn.execute("INSERT OR IGNORE INTO user_facilities (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def get_max_level(limit_break: int) -> int:
    return 100 + (limit_break * 20)

def get_facility_bonuses(user_id: int) -> tuple[float, float, float, float]:
    ensure_facility_table()
    conn = get_db()
    f = conn.execute("SELECT * FROM user_facilities WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if not f:
        return 1.0, 1.0, 1.0, 1.0
    atk_b = 1.0 + (f["training_lv"] - 1) * 0.03
    def_b = 1.0 + (f["blacksmith_lv"] - 1) * 0.03
    exp_b = 1.0 + (f["lab_lv"] - 1) * 0.05
    gold_b = 1.0 + (f["trade_lv"] - 1) * 0.05
    return atk_b, def_b, exp_b, gold_b

def get_player_combat_stats(user_id: int) -> tuple[int, int, int, int]:
    conn = get_db()
    p = conn.execute("SELECT * FROM players WHERE user_id = ?", (user_id,)).fetchone()
    cid = p["equipped_char_id"]
    wid = p["equipped_weapon_id"]
    gid = p["guild_id"]
    uc = conn.execute("SELECT * FROM user_chars WHERE user_id = ? AND char_id = ?", (user_id, cid)).fetchone()
    uw = conn.execute("SELECT * FROM user_weapons WHERE user_id = ? AND weapon_id = ?", (user_id, wid)).fetchone() if wid > 0 else None
    g_row = conn.execute("SELECT level FROM guilds WHERE id = ?", (gid,)).fetchone() if gid > 0 else None
    conn.close()

    base = CHARACTERS.get(cid, CHARACTERS.get(1))
    rm = RARITY_MULT.get(uc["rarity"], 1.0)
    lv_mult = 1.0 + (uc["level"] - 1) * 0.08

    hp = int(base["base_hp"] * rm * lv_mult)
    atk = int(base["base_atk"] * rm * lv_mult)
    df = int(base["base_def"] * rm * lv_mult)

    if uw and wid in WEAPONS:
        w_base = WEAPONS[wid]
        w_mult = 1.0 + (uw["plus_level"] * 0.12)
        hp += int(w_base["hp_bonus"] * w_mult)
        atk += int(w_base["atk_bonus"] * w_mult)

    f_atk, f_def, _, _ = get_facility_bonuses(user_id)
    atk = int(atk * f_atk)
    hp = int(hp * f_def)
    df = int(df * f_def)

    if g_row:
        g_buff = 1.0 + (g_row["level"] - 1) * 0.03
        hp = int(hp * g_buff)
        atk = int(atk * g_buff)
        df = int(df * g_buff)

    if base["passive_type"] == "atk_up":
        atk = int(atk * (1.0 + base["passive_val"]))
    elif base["passive_type"] == "def_up":
        df = int(df * (1.0 + base["passive_val"]))

    power = hp // 5 + atk * 3 + df * 2
    return hp, atk, df, power
def add_exp_to_char(user_id: int, char_id: int, gained_exp: int) -> tuple[int, int, bool]:
    conn = get_db()
    uc = conn.execute("SELECT * FROM user_chars WHERE user_id = ? AND char_id = ?", (user_id, char_id)).fetchone()
    if not uc:
        conn.close()
        return 1, 100, False

    lv = uc["level"]
    exp = uc["exp"] + gained_exp
    max_lv = get_max_level(uc["limit_break"])
    leveled_up = False

    while lv < max_lv:
        need = lv * 100
        if exp >= need:
            exp -= need
            lv += 1
            leveled_up = True
        else:
            break

    if lv >= max_lv:
        exp = 0

    conn.execute("UPDATE user_chars SET level = ?, exp = ? WHERE user_id = ? AND char_id = ?", (lv, exp, user_id, char_id))
    conn.commit()
    conn.close()
    return lv, max_lv, leveled_up

def add_guild_stars(user_id: int, stars: int):
    conn = get_db()
    p = conn.execute("SELECT guild_id FROM players WHERE user_id = ?", (user_id,)).fetchone()
    if p and p["guild_id"] > 0:
        conn.execute("UPDATE guilds SET stars = stars + ? WHERE id = ?", (stars, p["guild_id"]))
        conn.commit()
    conn.close()

def unlock_title(user_id: int, new_title: str):
    conn = get_db()
    row = conn.execute("SELECT unlocked_titles FROM players WHERE user_id = ?", (user_id,)).fetchone()
    if row:
        titles = row["unlocked_titles"].split("|")
        if new_title not in titles:
            titles.append(new_title)
            conn.execute(
                "UPDATE players SET unlocked_titles = ?, active_title = ? WHERE user_id = ?",
                ("|".join(titles), new_title, user_id)
            )
            conn.commit()
    conn.close()

async def sync_rank_and_badges(guild: discord.Guild, user_id: int):
    if not guild:
        return
    member = guild.get_member(user_id)
    if not member or member.bot:
        return

    if user_id == OWNER_ID:
        god_role = discord.utils.get(guild.roles, name=GOD_TITLE)
        if not god_role:
            try:
                god_role = await guild.create_role(name=GOD_TITLE, colour=discord.Colour.purple(), hoist=True)
            except Exception:
                god_role = None
        if god_role and god_role not in member.roles:
            try:
                await member.add_roles(god_role)
            except Exception:
                pass
        return

    conn = get_db()
    p = conn.execute("SELECT * FROM players WHERE user_id = ?", (user_id,)).fetchone()
    top_player = conn.execute("SELECT user_id FROM players WHERE user_id != ? ORDER BY rank_points DESC LIMIT 1", (OWNER_ID,)).fetchone()
    top_guild = conn.execute("SELECT leader_id FROM guilds ORDER BY stars DESC LIMIT 1").fetchone()
    conn.close()
    if not p:
        return

    rp = p["rank_points"]
    target_rank_name = "見習い冒険者"
    for req_rp, r_name in RANK_TIERS:
        if rp >= req_rp:
            target_rank_name = r_name

    target_role = discord.utils.get(guild.roles, name=target_rank_name)
    if not target_role:
        try:
            target_role = await guild.create_role(name=target_rank_name, colour=discord.Colour.gold(), hoist=True)
        except Exception:
            target_role = None

    if target_role and target_role not in member.roles:
        try:
            all_tier_names = {r_n for _, r_n in RANK_TIERS}
            to_rem = [r for r in member.roles if r.name in all_tier_names and r.name != target_rank_name]
            if to_rem:
                await member.remove_roles(*to_rem)
            await member.add_roles(target_role)
        except Exception:
            pass

    if p["gen_role"]:
        g_role = discord.utils.get(guild.roles, name=p["gen_role"])
        if not g_role:
            try:
                g_role = await guild.create_role(name=p["gen_role"], colour=discord.Colour.teal())
            except Exception:
                g_role = None
        if g_role and g_role not in member.roles:
            try:
                await member.add_roles(g_role)
            except Exception:
                pass

    old_champ_id = int(get_state("champion_id", "0"))
    new_champ_id = top_player["user_id"] if top_player else 0
    if new_champ_id != 0 and new_champ_id != old_champ_id:
        set_state("champion_id", str(new_champ_id))
        if old_champ_id != 0:
            await sync_rank_and_badges(guild, old_champ_id)

    is_champ = (new_champ_id == user_id)
    is_top_gl = (top_guild and top_guild["leader_id"] == user_id)

    if is_champ:
        prefix = "【👑現・勇者王】"
    elif is_top_gl:
        prefix = "【👑最強騎士団長】"
    else:
        prefix = p["active_title"]

    clean_name = member.display_name
    if clean_name.startswith("【") and "】" in clean_name:
        clean_name = clean_name.split("】", 1)[-1].strip()
    new_nick = f"{prefix}{clean_name}"[:32]
    try:
        if member.nick != new_nick:
            await member.edit(nick=new_nick)
    except Exception:
        pass

def is_guerrilla_now() -> bool:
    if get_state("guerrilla_active", "0") == "1":
        end_ts = int(get_state("guerrilla_end_ts", "0"))
        if int(datetime.now(timezone.utc).timestamp()) < end_ts:
            return True
        set_state("guerrilla_active", "0")
    return False
# ==========================================
# 4. ランクマッチ待機キュー ＆ キャンセルUI
# ==========================================
MATCH_QUEUE: dict[int, discord.Interaction] = {}

class MatchmakingView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=120)
        self.user_id = user_id

    @discord.ui.button(label="❌ マッチングキャンセル", style=discord.ButtonStyle.danger)
    async def cancel_match_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 本人のみキャンセルできます。", ephemeral=True)
            return
        if self.user_id in MATCH_QUEUE:
            del MATCH_QUEUE[self.user_id]
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="✅ ランクマッチの待機をキャンセルしました。", embed=None, view=self)

# ==========================================
# 5. 出撃（経験値狩り連戦 ＆ ストーリーモード）UI【整列リッチ版】
# ==========================================
def make_hp_bar(cur: int, max_v: int, length: int = 10) -> str:
    ratio = max(0.0, min(1.0, cur / max(1, max_v)))
    filled = int(round(ratio * length))
    sq = "🟩" if ratio > 0.5 else ("🟨" if ratio > 0.2 else "🟥")
    return sq * filled + "⬛" * (length - filled)

def build_battle_embed(
    title: str,
    color: discord.Color,
    enemy_name: str,
    e_hp: int,
    e_max_hp: int,
    char_name: str,
    passive_name: str,
    p_hp: int,
    p_max_hp: int,
    log_lines: list[str]
) -> discord.Embed:
    e_bar = make_hp_bar(e_hp, e_max_hp, 10)
    p_bar = make_hp_bar(p_hp, p_max_hp, 10)
    log_text = "\n".join(log_lines) if log_lines else "▶ 行動ボタンを選択してください！"

    embed = discord.Embed(title=title, color=color)
    embed.add_field(
        name=f"👾 【ENEMY】 {enemy_name}",
        value=f"{e_bar}\nHP ： **`{e_hp:,} / {e_max_hp:,}`**",
        inline=False
    )
    embed.add_field(
        name="📜 バトルログ",
        value=f"```text\n{log_text}\n```",
        inline=False
    )
    embed.add_field(
        name=f"🛡️ 【YOU】 {char_name}（固有：{passive_name}）",
        value=f"{p_bar}\nHP ： **`{p_hp:,} / {p_max_hp:,}`**",
        inline=False
    )
    return embed

class HuntBattleView(discord.ui.View):
    def __init__(self, user_id: int, enemy_name: str, e_hp: int, e_max_hp: int, e_atk: int, p_hp: int, p_max_hp: int):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.enemy_name = enemy_name
        self.e_hp = e_hp
        self.e_max_hp = e_max_hp
        self.e_atk = e_atk
        self.p_hp = p_hp
        self.p_max_hp = p_max_hp
        self.guts_used = False

    async def _turn(self, interaction: discord.Interaction, is_ult: bool):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 他の人の戦闘は操作できません。", ephemeral=True)
            return

        conn = get_db()
        p = conn.execute("SELECT equipped_char_id FROM players WHERE user_id = ?", (self.user_id,)).fetchone()
        cid = p["equipped_char_id"]
        conn.close()

        c_data = CHARACTERS.get(cid, CHARACTERS.get(1))
        _, atk, df, _ = get_player_combat_stats(self.user_id)

        crit_chance = 20 + (c_data["passive_val"] if c_data["passive_type"] == "crit_up" else 0)
        crit = random.randint(1, 100) <= crit_chance
        mult = (2.3 + (c_data["passive_val"] if c_data["passive_type"] == "ult_up" else 0)) if is_ult else 1.0
        if c_data["passive_type"] == "berserk" and self.p_hp <= (self.p_max_hp // 2):
            mult *= (1.0 + c_data["passive_val"])

        dmg = int(atk * mult * (1.5 if crit else 1.0) * random.uniform(0.9, 1.15))
        self.e_hp = max(0, self.e_hp - dmg)

        logs = [
            f"{'🔥 必殺【' + c_data['ult_name'] + '】' if is_ult else '⚔️ 通常攻撃'} {'【💥会心！】' if crit else ''}",
            f"▶ {self.enemy_name} に {dmg:,} ダメージ！"
        ]
        if c_data["passive_type"] == "lifesteal":
            heal = int(dmg * c_data["passive_val"])
            self.p_hp = min(self.p_max_hp, self.p_hp + heal)
            logs.append(f"🩸 吸血効果：HPが {heal:,} 回復！")
        if self.e_hp <= 0:
            guerrilla = is_guerrilla_now()
            g_mult = 3 if guerrilla else 1
            _, _, f_exp, f_gold = get_facility_bonuses(self.user_id)

            conn = get_db()
            uc = conn.execute("SELECT level FROM user_chars WHERE user_id = ? AND char_id = ?", (self.user_id, cid)).fetchone()
            conn.close()

            gained_exp = int((95 + uc["level"] * 24) * g_mult * f_exp)
            gained_gold = int(random.randint(160, 320) * g_mult * f_gold)
            gained_gems = random.randint(10, 30)
            crys_chance = min(95, int(50 * f_gold))
            gained_crys = (1 if random.randint(1, 100) <= crys_chance else 0) * g_mult
            gained_stars = 1 * g_mult

            lv, max_lv, lv_up = add_exp_to_char(self.user_id, cid, gained_exp)
            add_guild_stars(self.user_id, gained_stars)

            conn = get_db()
            conn.execute(
                "UPDATE players SET gold = gold + ?, gems = gems + ?, crystals = crystals + ? WHERE user_id = ?",
                (gained_gold, gained_gems, gained_crys, self.user_id)
            )
            conn.commit()
            conn.close()

            g_tag = " 🔥【ゲリラ3倍中！】" if guerrilla else ""
            lv_line = f"🎉 LEVEL UP!! ➡ Lv.{lv} / {max_lv}" if lv_up else f"📊 現在レベル ➡ Lv.{lv} / {max_lv}"
            embed = discord.Embed(title=f"🏆 討伐勝利！ {self.enemy_name} を撃破！{g_tag}", color=discord.Color.gold())
            embed.add_field(name="📜 フィニッシュログ", value=f"```text\n{chr(10).join(logs)}\n```", inline=False)
            embed.add_field(
                name="🎁 獲得リザルト",
                value=(
                    f"✨ **経験値**　：`+{gained_exp:,} EXP`\n"
                    f"💰 **資金**　　：`+{gained_gold:,} G`\n"
                    f"💎 **ガチャ石**：`+{gained_gems} 個`\n"
                    f"🔮 **進化結晶**：`+{gained_crys} 個`\n"
                    f"⭐ **団の星**　：`+{gained_stars} ★`\n"
                    f"━━━━━━━━━━━━━━\n"
                    f"**{lv_line}**"
                ),
                inline=False
            )
            await interaction.response.edit_message(embed=embed, view=NextHuntView(self.user_id))
            return

        evade = c_data["passive_val"] if c_data["passive_type"] == "evade" else 0
        if random.randint(1, 100) <= evade:
            logs.append(f"💨 {c_data['name']} は攻撃を華麗に回避！")
        else:
            e_dmg = max(1, int(self.e_atk * random.uniform(0.85, 1.15)) - (df // 2))
            self.p_hp = max(0, self.p_hp - e_dmg)
            if self.p_hp == 0 and c_data["passive_type"] == "guts" and not self.guts_used:
                self.p_hp = 1
                self.guts_used = True
                logs.append("🔥 固有【不屈の魂】発動！HP1で耐えた！")
            else:
                logs.append(f"💢 {self.enemy_name} の反撃！ {e_dmg:,} ダメージ！")

        if self.p_hp <= 0:
            embed = build_battle_embed(
                "💀 敗北……目の前が真っ暗になった",
                discord.Color.dark_grey(),
                self.enemy_name, self.e_hp, self.e_max_hp,
                c_data["name"], c_data["passive_name"], 0, self.p_max_hp,
                logs + ["▶ 進化・武器装備・施設強化をして再挑戦しよう！"]
            )
            await interaction.response.edit_message(embed=embed, view=NextHuntView(self.user_id))
            return

        if c_data["passive_type"] == "regen":
            reg = int(self.p_max_hp * c_data["passive_val"])
            self.p_hp = min(self.p_max_hp, self.p_hp + reg)
            logs.append(f"🌿 再生の祝福：HPが {reg:,} 回復！")

        embed = build_battle_embed(
            f"⚔️ 野生の {self.enemy_name} と交戦中！",
            discord.Color.red(),
            self.enemy_name, self.e_hp, self.e_max_hp,
            c_data["name"], c_data["passive_name"], self.p_hp, self.p_max_hp,
            logs
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⚔️ たたかう", style=discord.ButtonStyle.primary)
    async def atk_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._turn(interaction, False)

    @discord.ui.button(label="🔥 固有必殺技", style=discord.ButtonStyle.danger)
    async def ult_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._turn(interaction, True)
class NextHuntView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=120)
        self.user_id = user_id

    @discord.ui.button(label="⚔️ 続けて次の敵を狩る（連戦）", style=discord.ButtonStyle.success)
    async def next_hunt_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 本人のみ操作可能です。", ephemeral=True)
            return
        await start_hunt_encounter(interaction, edit=True)

async def start_hunt_encounter(interaction: discord.Interaction, edit: bool = False):
    uid = interaction.user.id
    ensure_player(uid)
    conn = get_db()
    p = conn.execute("SELECT equipped_char_id FROM players WHERE user_id = ?", (uid,)).fetchone()
    cid = p["equipped_char_id"]
    conn.close()

    c_data = CHARACTERS.get(cid, CHARACTERS.get(1))
    hp, atk, df, _ = get_player_combat_stats(uid)
    e_name = random.choice(["メタルスライム", "アークデーモン", "カオスドラゴン", "暗黒騎士", "古代兵器ゴーレム", "深淵の魔王兵"])
    e_hp = int(hp * random.uniform(0.75, 1.15))
    e_atk = int(atk * random.uniform(0.55, 0.85))
    g_txt = " 🔥【ゲリラ3倍発生中】" if is_guerrilla_now() else ""

    embed = build_battle_embed(
        f"⚔️ 野生の {e_name} が現れた！{g_txt}",
        discord.Color.red(),
        e_name, e_hp, e_hp,
        c_data["name"], c_data["passive_name"], hp, hp,
        [f"▶ {e_name} が立ちはだかる！コマンドを選択せよ！"]
    )
    view = HuntBattleView(uid, e_name, e_hp, e_hp, e_atk, hp, hp)
    if edit:
        await interaction.response.edit_message(embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class SortieSelectView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=120)
        self.user_id = user_id

    @discord.ui.button(label="⚔️ 経験値・素材狩り（連戦OK）", style=discord.ButtonStyle.primary)
    async def hunt_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await start_hunt_encounter(interaction, edit=True)

    @discord.ui.button(label="📖 ストーリーモードを進める", style=discord.ButtonStyle.success)
    async def story_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        ensure_player(uid)
        conn = get_db()
        p = conn.execute("SELECT story_chapter, equipped_weapon_id FROM players WHERE user_id = ?", (uid,)).fetchone()
        chap = p["story_chapter"]
        target_chap = min(chap, len(STORY_CHAPTERS))
        is_first_clear = (chap <= len(STORY_CHAPTERS))

        _, _, _, pwr = get_player_combat_stats(uid)
        _, ch_title, ch_synopsis, boss_name, b_hp, b_atk, reward_title, reward_gems = STORY_CHAPTERS[target_chap - 1]
        req_pwr = (b_hp // 5) + (b_atk * 2)

        if pwr >= req_pwr:
            drop_crys = target_chap + (random.randint(1, 3) if random.randint(1, 100) <= 75 else 0)
            drop_gold = target_chap * random.randint(400, 800)
            bonus_refine_txt = ""
            if p["equipped_weapon_id"] > 0 and random.randint(1, 100) <= 50:
                conn.execute("UPDATE user_weapons SET plus_level = plus_level + 1 WHERE user_id = ? AND weapon_id = ?", (uid, p["equipped_weapon_id"]))
                bonus_refine_txt = "\n⚒️ **レアドロップ**：装備武器が **+1精錬強化** された！"

            gained_gems = reward_gems if is_first_clear else (target_chap * 30)
            next_chap = chap + 1 if is_first_clear else chap

            conn.execute(
                "UPDATE players SET story_chapter = ?, gems = gems + ?, gold = gold + ?, crystals = crystals + ? WHERE user_id = ?",
                (next_chap, gained_gems, drop_gold, drop_crys, uid)
            )
            conn.commit()
            conn.close()

            if is_first_clear:
                unlock_title(uid, reward_title)
            add_guild_stars(uid, 5)
            await sync_rank_and_badges(interaction.guild, uid)

            embed = discord.Embed(title=f"📖 {ch_title} — 制覇！！", description=f"*{ch_synopsis}*", color=discord.Color.gold())
            embed.add_field(
                name=f"🏆 ボス『{boss_name}』撃破報酬",
                value=(
                    f"{'🎖️ **新肩書き解放**：**`' + reward_title + '`**' if is_first_clear else '🔄 **周回クリア報酬**'}\n"
                    f"💎 **ガチャ石**　：`+{gained_gems:,} 個`\n"
                    f"💰 **強化資金**　：`+{drop_gold:,} G`\n"
                    f"🔮 **進化結晶**　：`+{drop_crys} 個`（確率追加ドロップ込）\n"
                    f"⭐ **騎士団貢献**：`+5 ★`{bonus_refine_txt}"
                ),
                inline=False
            )
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            conn.close()
            embed = discord.Embed(title=f"📖 {ch_title} — ボス『{boss_name}』に敗北", description=f"*{ch_synopsis}*", color=discord.Color.dark_red())
            embed.add_field(
                name="📊 戦力分析",
                value=f"・あなたの戦闘力：**`{pwr:,}`**\n・ボス推奨戦闘力：**`{req_pwr:,}`**\n\n▶ 狩り・段階進化・武器装備・施設強化をして再挑戦しよう！",
                inline=False
            )
            await interaction.response.edit_message(embed=embed, view=self)
# ==========================================
# 6. ガチャパネル（恒常キャラ・限定ピックアップ・武器ガチャ）UI
# ==========================================
class GachaPanelView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=180)
        self.user_id = user_id

    async def _roll_char(self, interaction: discord.Interaction, count: int, is_limited: bool = False):
        uid = interaction.user.id
        ensure_player(uid)
        if is_limited and get_state("limited_gacha_active", "0") != "1":
            await interaction.response.send_message("❌ 現在開催中の期間限定ピックアップガチャはありません。", ephemeral=True)
            return

        cost = count * 100
        conn = get_db()
        p = conn.execute("SELECT gems FROM players WHERE user_id = ?", (uid,)).fetchone()
        if p["gems"] < cost:
            conn.close()
            await interaction.response.send_message(f"❌ ガチャ石不足（所持:`{p['gems']}` / 必要:`{cost}`）", ephemeral=True)
            return

        conn.execute("UPDATE players SET gems = gems - ? WHERE user_id = ?", (cost, uid))
        pools = {r: [c for c in CHARACTERS.values() if c["base_rarity"] == r and not c.get("is_god_custom")] for r in ["C", "R", "SR", "SSR", "UR", "LR"]}

        lr_rate = int(get_state("normal_lr_rate_permille", "5"))
        ur_rate = int(get_state("normal_ur_rate_permille", "30"))
        pu_cid = int(get_state("limited_gacha_char_id", "200"))
        pu_rate = int(get_state("limited_gacha_rate_permille", "30"))
        pu_title = get_state("limited_gacha_title", "【期間限定】ピックアップ召喚")

        lines = []
        for _ in range(count):
            roll = random.randint(1, 1000)
            if is_limited and pu_cid in CHARACTERS and roll <= pu_rate:
                ch = CHARACTERS[pu_cid]
                rar = ch["base_rarity"]
                pu_mark = "🌟【PU確定!!】"
            else:
                pu_mark = ""
                if roll <= lr_rate:
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
                lines.append(f"{pu_mark}🔄 **[{rar}] No.{cid:03d} {ch['name']}**（被り凸！上限 **Lv.{get_max_level(new_lb)}** 解放）")
            else:
                conn.execute("INSERT INTO user_chars (user_id, char_id, rarity, level, exp, limit_break) VALUES (?, ?, ?, 1, 0, 0)", (uid, cid, rar))
                lines.append(f"{pu_mark}🆕 **[{rar}] No.{cid:03d} {ch['name']}**（{ch['race']} / {ch['job']}）")

        conn.commit()
        conn.close()
        header = f"🌟 {pu_title} {count}連結果！" if is_limited else f"🎰 恒常キャラ召喚 {count}連結果！"
        embed = discord.Embed(title=header, description="\n".join(lines), color=discord.Color.gold() if is_limited else discord.Color.purple())
        await interaction.response.edit_message(embed=embed, view=self)

    async def _roll_weapon(self, interaction: discord.Interaction, count: int):
        uid = interaction.user.id
        ensure_player(uid)
        cost = count * 100
        conn = get_db()
        p = conn.execute("SELECT gems FROM players WHERE user_id = ?", (uid,)).fetchone()
        if p["gems"] < cost:
            conn.close()
            await interaction.response.send_message(f"❌ ガチャ石不足（所持:`{p['gems']}` / 必要:`{cost}`）", ephemeral=True)
            return

        conn.execute("UPDATE players SET gems = gems - ? WHERE user_id = ?", (cost, uid))
        pools = {r: [w for w in WEAPONS.values() if w["rarity"] == r] for r in ["C", "R", "SR", "SSR", "UR", "LR"]}
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
        await interaction.response.edit_message(embed=embed, view=self)
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
        lim_on = get_state("limited_gacha_active", "0") == "1"
        lim_title = get_state("limited_gacha_title", "【期間限定】ピックアップ召喚")
        pu_cid = int(get_state("limited_gacha_char_id", "200"))
        pu_rate = int(get_state("limited_gacha_rate_permille", "30"))
        lr_rate = int(get_state("normal_lr_rate_permille", "5"))
        ur_rate = int(get_state("normal_ur_rate_permille", "30"))

        embed = discord.Embed(title="📜 召喚ガチャ 排出キャラ＆確率一覧", color=discord.Color.gold())

        if lim_on and pu_cid in CHARACTERS:
            pu = CHARACTERS[pu_cid]
            embed.add_field(
                name=f"🌟 開催中PU：{lim_title}",
                value=(
                    f"・対象：**`[{pu['base_rarity']}] No.{pu_cid:03d} {pu['name']}`**（排出率：**`{pu_rate/10:.1f}%`**）\n"
                    f"・種族/職：`{pu['race']}` / `{pu['job']}` ｜ 必殺：**{pu['ult_name']}**\n"
                    f"・基礎ステ：HP `{pu['base_hp']:,}` / ATK `{pu['base_atk']:,}` / DEF `{pu['base_def']:,}`"
                ),
                inline=False
            )

        god_chars = [c for c in CHARACTERS.values() if c.get("is_god_custom")]
        if god_chars:
            g_lines = [
                f"・`[{c['base_rarity']}] No.{c['id']:03d} {c['name']}`（HP:{c['base_hp']:,} / ATK:{c['base_atk']:,} / 必殺:{c['ult_name']}）"
                for c in god_chars[-10:]
            ]
            embed.add_field(name="👑 創造神が追加した特別キャラ一覧", value="\n".join(g_lines), inline=False)

        lr_chars = [c for c in CHARACTERS.values() if c["base_rarity"] == "LR" and not c.get("is_god_custom")]
        lr_lines = [f"・`[LR] No.{c['id']:03d} {c['name']}`（{c['passive_name']} / {c['ult_name']}）" for c in lr_chars]
        embed.add_field(
            name=f"🌈 恒常LRキャラ一覧（基本排出率: {lr_rate/10:.1f}% / UR: {ur_rate/10:.1f}%）",
            value="\n".join(lr_lines) or "なし",
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
# ==========================================
# 7. 編成・1段階進化（C→MCR）・売却パネル UI
# ==========================================
class CharManageSelect(discord.ui.Select):
    def __init__(self, owned_chars: list):
        options = []
        for uc in owned_chars[:25]:
            cid = uc["char_id"]
            c = CHARACTERS.get(cid, CHARACTERS.get(1))
            label = f"[{uc['rarity']}] No.{cid:03d} {c['name']} (Lv.{uc['level']}/{get_max_level(uc['limit_break'])})"[:100]
            desc = f"{c['race']} / {c['job']} / {uc['limit_break']}凸"
            options.append(discord.SelectOption(label=label, value=str(cid), description=desc))
        super().__init__(placeholder="操作するキャラクターを選択（装備・進化・売却）", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        cid = int(next(iter(self.values)))
        await interaction.response.edit_message(
            embed=build_char_detail_embed(interaction.user.id, cid),
            view=CharActionView(interaction.user.id, cid)
        )

class WeaponManageSelect(discord.ui.Select):
    def __init__(self, owned_weapons: list):
        options = []
        for uw in owned_weapons[:25]:
            wid = uw["weapon_id"]
            w = WEAPONS[wid]
            label = f"[{w['rarity']}] {w['name']} (+{uw['plus_level']})"[:100]
            desc = f"ATK+{w['atk_bonus']} / HP+{w['hp_bonus']}"
            options.append(discord.SelectOption(label=label, value=str(wid), description=desc))
        super().__init__(placeholder="装備・売却する武器を選択", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        wid = int(next(iter(self.values)))
        await interaction.response.edit_message(
            embed=build_weapon_detail_embed(interaction.user.id, wid),
            view=WeaponActionView(interaction.user.id, wid)
        )

def build_char_detail_embed(user_id: int, cid: int) -> discord.Embed:
    conn = get_db()
    uc = conn.execute("SELECT * FROM user_chars WHERE user_id = ? AND char_id = ?", (user_id, cid)).fetchone()
    conn.close()
    c = CHARACTERS.get(cid, CHARACTERS.get(1))
    rar = uc["rarity"]
    next_rar = RARITIES[RARITIES.index(rar) + 1] if rar != "MCR" else "MAX(MCR)"
    n_crys, n_gold = EVOLVE_COST.get(rar, (0, 0))
    evo_info = f"必要素材：結晶 `{n_crys}個` ＋ `{n_gold:,}G`" if rar != "MCR" else "最高レアリティ到達済み！"
    s_gold, s_crys = SELL_REWARD[rar]

    embed = discord.Embed(
        title=f"🛡️ キャラ詳細・管理：[{rar}] No.{cid:03d} {c['name']}",
        description=(
            f"🧬 種族：`{c['race']}` ｜ ジョブ：`{c['job']}`\n"
            f"📊 レベル：**`Lv.{uc['level']} / {get_max_level(uc['limit_break'])}`**（{uc['limit_break']}凸）\n"
            f"💠 固有スキル：**{c['passive_name']}**（{c['passive_desc']}）\n"
            f"🔥 固有必殺技：**{c['ult_name']}**\n\n"
            f"✨ **次の1段階進化（{rar} ➡ {next_rar}）**：{evo_info}\n"
            f"💰 **売却時の還元**：`{s_gold:,}G` ＋ 進化の結晶 `{s_crys}個`"
        ),
        color=discord.Color.blue()
    )
    return embed

class CharActionView(discord.ui.View):
    def __init__(self, user_id: int, cid: int):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.cid = cid

    @discord.ui.button(label="⚔️ 出撃キャラに装備", style=discord.ButtonStyle.primary)
    async def equip_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = get_db()
        conn.execute("UPDATE players SET equipped_char_id = ? WHERE user_id = ?", (self.cid, self.user_id))
        conn.commit()
        conn.close()
        c = CHARACTERS.get(self.cid, CHARACTERS.get(1))
        await interaction.response.send_message(f"✅ **No.{self.cid:03d} {c['name']}** を出撃キャラにセットしました！", ephemeral=True)

    @discord.ui.button(label="✨ 1段階進化させる", style=discord.ButtonStyle.success)
    async def evolve_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = get_db()
        p = conn.execute("SELECT crystals, gold FROM players WHERE user_id = ?", (self.user_id,)).fetchone()
        uc = conn.execute("SELECT rarity FROM user_chars WHERE user_id = ? AND char_id = ?", (self.user_id, self.cid)).fetchone()
        rar = uc["rarity"]
        if rar == "MCR":
            conn.close()
            await interaction.response.send_message("👑 すでに最高ランク `MCR` です！", ephemeral=True)
            return
        n_crys, n_gold = EVOLVE_COST[rar]
        if p["crystals"] < n_crys or p["gold"] < n_gold:
            conn.close()
            await interaction.response.send_message(f"❌ 素材不足（必要: 結晶`{n_crys}` / `{n_gold:,}G`）", ephemeral=True)
            return
        next_rar = RARITIES[RARITIES.index(rar) + 1]
        conn.execute("UPDATE players SET crystals = crystals - ?, gold = gold - ? WHERE user_id = ?", (n_crys, n_gold, self.user_id))
        conn.execute("UPDATE user_chars SET rarity = ? WHERE user_id = ? AND char_id = ?", (next_rar, self.user_id, self.cid))
        conn.commit()
        conn.close()

        if next_rar == "MCR":
            unlock_title(self.user_id, "【究極能力者（アルティメットスキル）】")
            await sync_rank_and_badges(interaction.guild, self.user_id)

        await interaction.response.edit_message(embed=build_char_detail_embed(self.user_id, self.cid), view=self)
    @discord.ui.button(label="🗑️ キャラを売却する", style=discord.ButtonStyle.danger)
    async def sell_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = get_db()
        p = conn.execute("SELECT equipped_char_id FROM players WHERE user_id = ?", (self.user_id,)).fetchone()
        cnt = conn.execute("SELECT COUNT(*) AS c FROM user_chars WHERE user_id = ?", (self.user_id,)).fetchone()["c"]
        if p["equipped_char_id"] == self.cid or cnt <= 1:
            conn.close()
            await interaction.response.send_message("❌ 現在装備中のキャラ、または最後の1体は売却できません！", ephemeral=True)
            return
        uc = conn.execute("SELECT rarity FROM user_chars WHERE user_id = ? AND char_id = ?", (self.user_id, self.cid)).fetchone()
        s_gold, s_crys = SELL_REWARD[uc["rarity"]]
        conn.execute("DELETE FROM user_chars WHERE user_id = ? AND char_id = ?", (self.user_id, self.cid))
        conn.execute("UPDATE players SET gold = gold + ?, crystals = crystals + ? WHERE user_id = ?", (s_gold, s_crys, self.user_id))
        conn.commit()
        conn.close()
        c = CHARACTERS.get(self.cid, CHARACTERS.get(1))
        await interaction.response.edit_message(
            content=f"💰 **No.{self.cid:03d} {c['name']}** を売却し、**`+{s_gold:,}G`** と **進化の結晶 `+{s_crys}個`** を獲得しました！",
            embed=None,
            view=None
        )

def build_weapon_detail_embed(user_id: int, wid: int) -> discord.Embed:
    conn = get_db()
    uw = conn.execute("SELECT * FROM user_weapons WHERE user_id = ? AND weapon_id = ?", (user_id, wid)).fetchone()
    conn.close()
    w = WEAPONS[wid]
    s_gold, s_crys = SELL_REWARD[w["rarity"]]
    return discord.Embed(
        title=f"🗡️ 武器管理：[{w['rarity']}] {w['name']} (+{uw['plus_level']})",
        description=(
            f"⚔️ 攻撃力補正：`+{w['atk_bonus']}` ｜ ❤️ HP補正：`+{w['hp_bonus']}`\n"
            f"💰 売却時の還元：`{s_gold:,}G` ＋ 進化の結晶 `{s_crys}個`"
        ),
        color=discord.Color.teal()
    )

class WeaponActionView(discord.ui.View):
    def __init__(self, user_id: int, wid: int):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.wid = wid

    @discord.ui.button(label="🗡️ この武器を装備する", style=discord.ButtonStyle.primary)
    async def equip_w_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = get_db()
        conn.execute("UPDATE players SET equipped_weapon_id = ? WHERE user_id = ?", (self.wid, self.user_id))
        conn.commit()
        conn.close()
        await interaction.response.send_message(f"✅ **{WEAPONS[self.wid]['name']}** を装備しました！", ephemeral=True)

    @discord.ui.button(label="🗑️ 武器を売却する", style=discord.ButtonStyle.danger)
    async def sell_w_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = get_db()
        p = conn.execute("SELECT equipped_weapon_id FROM players WHERE user_id = ?", (self.user_id,)).fetchone()
        if p["equipped_weapon_id"] == self.wid:
            conn.execute("UPDATE players SET equipped_weapon_id = 0 WHERE user_id = ?", (self.user_id,))
        w = WEAPONS[self.wid]
        s_gold, s_crys = SELL_REWARD[w["rarity"]]
        conn.execute("DELETE FROM user_weapons WHERE user_id = ? AND weapon_id = ?", (self.user_id, self.wid))
        conn.execute("UPDATE players SET gold = gold + ?, crystals = crystals + ? WHERE user_id = ?", (s_gold, s_crys, self.user_id))
        conn.commit()
        conn.close()
        await interaction.response.edit_message(
            content=f"💰 **{w['name']}** を売却し、**`+{s_gold:,}G`** と **進化の結晶 `+{s_crys}個`** を獲得しました！",
            embed=None,
            view=None
        )

class ArmoryRootView(discord.ui.View):
    def __init__(self, owned_chars: list, owned_weapons: list):
        super().__init__(timeout=180)
        if owned_chars:
            self.add_item(CharManageSelect(owned_chars))
        if owned_weapons:
            self.add_item(WeaponManageSelect(owned_weapons))

# ==========================================
# 8. 領地施設強化パネル（4施設レベルアップ）UI
# ==========================================
def build_facility_embed(user_id: int) -> discord.Embed:
    ensure_facility_table()
    conn = get_db()
    p = conn.execute("SELECT gold, crystals FROM players WHERE user_id = ?", (user_id,)).fetchone()
    f = conn.execute("SELECT * FROM user_facilities WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()

    def cost_str(lv: int) -> str:
        if lv >= 20:
            return "MAX (Lv.20)"
        return f"`{lv * 1000:,}G` ＋ 結晶 `{lv}個`"

    return discord.Embed(
        title="🏛️ 領地施設・拠点開発パネル（最大 Lv.20）",
        description=(
            f"💰 所持ゴールド：**`{p['gold']:,}G`** ｜ 🔮 進化の結晶：**`{p['crystals']:,}個`**\n\n"
            f"⚔️ **訓練場 Lv.{f['training_lv']}**（全キャラATK `+{(f['training_lv']-1)*3}%`）\n"
            f"└ 次の強化：{cost_str(f['training_lv'])}\n\n"
            f"🛡️ **鍛冶工房 Lv.{f['blacksmith_lv']}**（全キャラHP・DEF `+{(f['blacksmith_lv']-1)*3}%`）\n"
            f"└ 次の強化：{cost_str(f['blacksmith_lv'])}\n\n"
            f"🔮 **魔導研究所 Lv.{f['lab_lv']}**（獲得EXP `+{(f['lab_lv']-1)*5}%`）\n"
            f"└ 次の強化：{cost_str(f['lab_lv'])}\n\n"
            f"💰 **商業ギルド Lv.{f['trade_lv']}**（獲得G・結晶率 `+{(f['trade_lv']-1)*5}%`）\n"
            f"└ 次の強化：{cost_str(f['trade_lv'])}"
        ),
        color=discord.Color.teal()
    )
class FacilityPanelView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=180)
        self.user_id = user_id

    async def _upgrade(self, interaction: discord.Interaction, col: str, label: str):
        ensure_facility_table()
        conn = get_db()
        p = conn.execute("SELECT gold, crystals FROM players WHERE user_id = ?", (self.user_id,)).fetchone()
        f = conn.execute("SELECT * FROM user_facilities WHERE user_id = ?", (self.user_id,)).fetchone()
        cur_lv = f[col]
        if cur_lv >= 20:
            conn.close()
            await interaction.response.send_message(f"👑 **{label}** はすでに最大レベル（Lv.20）です！", ephemeral=True)
            return
        need_g = cur_lv * 1000
        need_c = cur_lv
        if p["gold"] < need_g or p["crystals"] < need_c:
            conn.close()
            await interaction.response.send_message(f"❌ 素材不足（必要: `{need_g:,}G` ＋ 結晶 `{need_c}個`）", ephemeral=True)
            return
        conn.execute("UPDATE players SET gold = gold - ?, crystals = crystals - ? WHERE user_id = ?", (need_g, need_c, self.user_id))
        conn.execute(f"UPDATE user_facilities SET {col} = {col} + 1 WHERE user_id = ?", (self.user_id,))
        conn.commit()
        total_lv = f["training_lv"] + f["blacksmith_lv"] + f["lab_lv"] + f["trade_lv"] + 1
        conn.close()

        if total_lv >= 40:
            unlock_title(self.user_id, "【魔国連邦の盟主（フェデレーション）】")
            await sync_rank_and_badges(interaction.guild, self.user_id)
        elif total_lv >= 15:
            unlock_title(self.user_id, "【開拓領主（フロンティアロード）】")
            await sync_rank_and_badges(interaction.guild, self.user_id)

        await interaction.response.edit_message(embed=build_facility_embed(self.user_id), view=self)

    @discord.ui.button(label="⚔️ 訓練場強化", style=discord.ButtonStyle.primary, row=0)
    async def up_train(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._upgrade(interaction, "training_lv", "訓練場")

    @discord.ui.button(label="🛡️ 鍛冶工房強化", style=discord.ButtonStyle.primary, row=0)
    async def up_smith(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._upgrade(interaction, "blacksmith_lv", "鍛冶工房")

    @discord.ui.button(label="🔮 魔導研究所強化", style=discord.ButtonStyle.success, row=1)
    async def up_lab(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._upgrade(interaction, "lab_lv", "魔導研究所")

    @discord.ui.button(label="💰 商業ギルド強化", style=discord.ButtonStyle.success, row=1)
    async def up_trade(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._upgrade(interaction, "trade_lv", "商業ギルド")

# ==========================================
# 9. ブラクロ風「騎士団（ギルド）」専用ロール＆専用チャンネル自動作成UI
# ==========================================
class CreateGuildModal(discord.ui.Modal, title="🏰 新規騎士団の創設（費用: 3,000G）"):
    guild_name = discord.ui.TextInput(label="騎士団名（例：黒の暴牛 / 金色の夜明け）", required=True, max_length=20)

    async def on_submit(self, interaction: discord.Interaction):
        uid = interaction.user.id
        conn = get_db()
        p = conn.execute("SELECT gold, guild_id FROM players WHERE user_id = ?", (uid,)).fetchone()
        if p["guild_id"] > 0:
            conn.close()
            await interaction.response.send_message("❌ すでに別の騎士団に所属しています。", ephemeral=True)
            return
        if p["gold"] < 3000:
            conn.close()
            await interaction.response.send_message("❌ 創設費用（3,000G）が足りません。", ephemeral=True)
            return

        g_name = self.guild_name.value.strip()
        guild = interaction.guild
        role_id = 0
        ch_id = 0

        if guild:
            try:
                g_role = await guild.create_role(name=f"🛡️{g_name}", colour=discord.Colour.blue(), hoist=True)
                role_id = g_role.id
                await interaction.user.add_roles(g_role)
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    g_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                    guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
                }
                owner_m = guild.get_member(OWNER_ID)
                if owner_m:
                    overwrites[owner_m] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                ch = await guild.create_text_channel(name=f"🏰｜{g_name}-団本部", overwrites=overwrites)
                ch_id = ch.id
                await ch.send(f"🎉 **{interaction.user.mention} 団長によって魔法騎士団『{g_name}』が創設されました！**\nここは団員だけが閲覧・会話できる専用アジトです！")
            except Exception:
                pass

        try:
            cur = conn.execute(
                "INSERT INTO guilds (name, leader_id, vice_leader_id, role_id, channel_id, stars, level) VALUES (?, ?, 0, ?, ?, 0, 1)",
                (g_name, uid, role_id, ch_id)
            )
            new_gid = cur.lastrowid
            conn.execute("UPDATE players SET gold = gold - 3000, guild_id = ?, guild_role = '団長' WHERE user_id = ?", (new_gid, uid))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            await interaction.response.send_message("❌ その騎士団名はすでに使われています。", ephemeral=True)
            return
        conn.close()
        ch_note = f"\n専用ロール＆専用チャンネル（<#{ch_id}>）も自動作成しました！" if ch_id else ""
        await interaction.response.send_message(f"🎉 騎士団 **『{g_name}』** を創設し、あなたが **【団長】** に就任しました！{ch_note}", ephemeral=True)
class JoinGuildSelect(discord.ui.Select):
    def __init__(self, guilds: list):
        options = [
            discord.SelectOption(
                label=f"【Lv.{g['level']}】{g['name']}（★{g['stars']:,}）"[:100],
                value=str(g["id"]),
                description=f"団長ID: {g['leader_id']}"
            )
            for g in guilds[:25]
        ]
        super().__init__(placeholder="入団する騎士団を選択してください", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        gid = int(next(iter(self.values)))
        uid = interaction.user.id
        conn = get_db()
        cnt = conn.execute("SELECT COUNT(*) AS c FROM players WHERE guild_id = ?", (gid,)).fetchone()["c"]
        if cnt >= 15:
            conn.close()
            await interaction.response.send_message("❌ この騎士団は定員（15名）に達しています。", ephemeral=True)
            return
        g = conn.execute("SELECT * FROM guilds WHERE id = ?", (gid,)).fetchone()
        conn.execute("UPDATE players SET guild_id = ?, guild_role = '団員' WHERE user_id = ?", (gid, uid))
        conn.commit()
        conn.close()

        if interaction.guild and g["role_id"]:
            g_role = interaction.guild.get_role(g["role_id"])
            if g_role:
                try:
                    await interaction.user.add_roles(g_role)
                except Exception:
                    pass

        ch_msg = f"\n団員専用チャンネル（<#{g['channel_id']}>）が解放されました！" if g["channel_id"] else ""
        await interaction.response.edit_message(content=f"✅ 騎士団 **『{g['name']}』** に【団員】として入団しました！{ch_msg}", embed=None, view=None)

class AppointViceSelect(discord.ui.Select):
    def __init__(self, members: list):
        options = [
            discord.SelectOption(label=f"メンバーID: {m['user_id']}（現在: {m['guild_role']}）", value=str(m["user_id"]))
            for m in members[:25]
        ]
        super().__init__(placeholder="【副団長】に任命する団員を選択", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        target_id = int(next(iter(self.values)))
        conn = get_db()
        p = conn.execute("SELECT guild_id FROM players WHERE user_id = ?", (interaction.user.id,)).fetchone()
        gid = p["guild_id"]
        conn.execute("UPDATE players SET guild_role = '団員' WHERE guild_id = ? AND guild_role = '副団長'", (gid,))
        conn.execute("UPDATE players SET guild_role = '副団長' WHERE user_id = ?", (target_id,))
        conn.execute("UPDATE guilds SET vice_leader_id = ? WHERE id = ?", (target_id, gid))
        conn.commit()
        conn.close()
        await interaction.response.edit_message(content=f"🎖️ <@{target_id}> を **【副団長】** に任命しました！", embed=None, view=None)

class GuildPanelView(discord.ui.View):
    def __init__(self, user_id: int, guild_id: int, guild_role: str):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.guild_id = guild_id
        self.guild_role = guild_role

    @discord.ui.button(label="🏰 騎士団を創設(3000G)", style=discord.ButtonStyle.success, row=0)
    async def create_g_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.guild_id > 0:
            await interaction.response.send_message("❌ すでに騎士団に所属しています。", ephemeral=True)
            return
        await interaction.response.send_modal(CreateGuildModal())

    @discord.ui.button(label="🤝 既存の騎士団に入団", style=discord.ButtonStyle.primary, row=0)
    async def join_g_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.guild_id > 0:
            await interaction.response.send_message("❌ すでに騎士団に所属しています。", ephemeral=True)
            return
        conn = get_db()
        guilds = conn.execute("SELECT * FROM guilds ORDER BY stars DESC LIMIT 25").fetchall()
        conn.close()
        if not guilds:
            await interaction.response.send_message("📭 まだ創設されている騎士団がありません。最初の団長になろう！", ephemeral=True)
            return
        v = discord.ui.View(timeout=120)
        v.add_item(JoinGuildSelect(guilds))
        await interaction.response.edit_message(content="入団したい騎士団を選んでください：", embed=None, view=v)

    @discord.ui.button(label="⬆️ 団レベル強化（団長・副団長）", style=discord.ButtonStyle.primary, row=1)
    async def lvup_g_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.guild_id == 0 or self.guild_role not in ("団長", "副団長"):
            await interaction.response.send_message("❌ この操作は【団長】または【副団長】のみ実行できます。", ephemeral=True)
            return
        conn = get_db()
        g = conn.execute("SELECT * FROM guilds WHERE id = ?", (self.guild_id,)).fetchone()
        need_stars = g["level"] * 20
        if g["stars"] < need_stars:
            conn.close()
            await interaction.response.send_message(f"❌ 団の功績の星が足りません（現在:`{g['stars']}★` / 必要:`{need_stars}★`）。", ephemeral=True)
            return
        conn.execute("UPDATE guilds SET stars = stars - ?, level = level + 1 WHERE id = ?", (need_stars, self.guild_id))
        conn.commit()
        conn.close()
        await interaction.response.send_message(f"🎉 騎士団レベルが **Lv.{g['level'] + 1}** に上昇！団員全員のステータスがさらに強化されました！", ephemeral=True)

    @discord.ui.button(label="🎖️ 副団長を任命（団長専用）", style=discord.ButtonStyle.secondary, row=1)
    async def vice_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.guild_id == 0 or self.guild_role != "団長":
            await interaction.response.send_message("❌ 副団長の任命は【団長】のみ可能です。", ephemeral=True)
            return
        conn = get_db()
        members = conn.execute("SELECT user_id, guild_role FROM players WHERE guild_id = ? AND user_id != ?", (self.guild_id, self.user_id)).fetchall()
        conn.close()
        if not members:
            await interaction.response.send_message("❌ 任命できる団員がまだいません。", ephemeral=True)
            return
        v = discord.ui.View(timeout=120)
        v.add_item(AppointViceSelect(members))
        await interaction.response.edit_message(content="副団長に任命するメンバーを選択してください：", embed=None, view=v)

    @discord.ui.button(label="🚪 退団 / 解散する", style=discord.ButtonStyle.danger, row=1)
    async def leave_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.guild_id == 0:
            await interaction.response.send_message("❌ 騎士団に所属していません。", ephemeral=True)
            return
        conn = get_db()
        g = conn.execute("SELECT * FROM guilds WHERE id = ?", (self.guild_id,)).fetchone()
        if self.guild_role == "団長":
            if interaction.guild and g:
                if g["channel_id"]:
                    ch = interaction.guild.get_channel(g["channel_id"])
                    if ch:
                        try:
                            await ch.delete(reason="騎士団解散")
                        except Exception:
                            pass
                if g["role_id"]:
                    rl = interaction.guild.get_role(g["role_id"])
                    if rl:
                        try:
                            await rl.delete(reason="騎士団解散")
                        except Exception:
                            pass
            conn.execute("UPDATE players SET guild_id = 0, guild_role = '' WHERE guild_id = ?", (self.guild_id,))
            conn.execute("DELETE FROM guilds WHERE id = ?", (self.guild_id,))
            msg = "💥 あなたが団長だったため、騎士団（専用ロール＆チャンネル含む）を解散しました。"
        else:
            if interaction.guild and g and g["role_id"]:
                rl = interaction.guild.get_role(g["role_id"])
                if rl:
                    try:
                        await interaction.user.remove_roles(rl)
                    except Exception:
                        pass
            conn.execute("UPDATE players SET guild_id = 0, guild_role = '' WHERE user_id = ?", (self.user_id,))
            conn.execute("UPDATE guilds SET vice_leader_id = 0 WHERE id = ? AND vice_leader_id = ?", (self.guild_id, self.user_id))
            msg = "🚪 騎士団を退団し、団専用ロールを返却しました。"
        conn.commit()
        conn.close()
        await interaction.response.edit_message(content=msg, embed=None, view=None)

class TitleChangeSelect(discord.ui.Select):
    def __init__(self, titles: list[str]):
        options = [discord.SelectOption(label=t, value=t) for t in titles[:25]]
        super().__init__(placeholder="名前の横に表示する肩書きを選択", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        chosen = next(iter(self.values))
        uid = interaction.user.id
        conn = get_db()
        conn.execute("UPDATE players SET active_title = ? WHERE user_id = ?", (chosen, uid))
        conn.commit()
        conn.close()
        await sync_rank_and_badges(interaction.guild, uid)
        await interaction.response.edit_message(content=f"✅ 肩書きを **`{chosen}`** に変更し、ニックネームへ反映しました！", embed=None, view=None)
# ==========================================
# 10. 月1回・神出鬼没 運営レイドボスUI
# ==========================================
class RaidBossView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="⚔️ 運営レイドボスに総攻撃！", style=discord.ButtonStyle.danger, custom_id="cmd_raid_atk_btn")
    async def raid_atk_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if get_state("raid_active", "0") != "1":
            await interaction.response.send_message("❌ 現在出現中の運営レイドボスはいません。", ephemeral=True)
            return

        uid = interaction.user.id
        ensure_player(uid)
        _, atk, _, _ = get_player_combat_stats(uid)
        dmg = int(atk * random.uniform(1.2, 2.0))

        cur_hp = int(get_state("raid_hp", "0"))
        max_hp = int(get_state("raid_max_hp", "1"))
        boss_name = get_state("raid_name", "運営降臨ボス")

        if cur_hp <= 0:
            await interaction.response.send_message("⚠️ すでにボスは討伐されています！", ephemeral=True)
            return

        new_hp = max(0, cur_hp - dmg)
        set_state("raid_hp", str(new_hp))

        conn = get_db()
        conn.execute(
            "INSERT INTO raid_damage (user_id, damage) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET damage = damage + ?",
            (uid, dmg, dmg)
        )
        conn.commit()

        if new_hp == 0:
            set_state("raid_active", "0")
            mvp_row = conn.execute("SELECT user_id, damage FROM raid_damage ORDER BY damage DESC LIMIT 1").fetchone()
            top3 = conn.execute("SELECT user_id, damage FROM raid_damage ORDER BY damage DESC LIMIT 3").fetchall()
            conn.close()

            unlock_title(uid, "【神殺しの一撃（ゴッドスレイヤー）】")
            if mvp_row:
                unlock_title(mvp_row["user_id"], "【災厄の討伐者（カタストロフ）】")
            await sync_rank_and_badges(interaction.guild, uid)

            mvp_text = f"<@{mvp_row['user_id']}>（総ダメージ: **`{mvp_row['damage']:,}`**）" if mvp_row else "なし"
            rank_lines = "\n".join([f"{i+1}位：<@{r['user_id']}> (`{r['damage']:,}` DMG)" for i, r in enumerate(top3)])
            for item in self.children:
                item.disabled = True

            win_embed = discord.Embed(
                title="🎊🎉 【緊急速報】運営レイドボス完全討伐達成！！ 🎉🎊",
                description=(
                    f"サーバー全員の総力戦により、**『{boss_name}』** を撃破しました！！\n\n"
                    f"🗡️ **ラストアタック（トドメ）**：<@{uid}>\n"
                    f"🏆 **総ダメージ1位（MVP）**：{mvp_text}\n\n"
                    f"**【ダメージランキング TOP3】**\n{rank_lines}\n\n"
                    f"🎁 **報酬確定**：創造神（<@{OWNER_ID}>）より **PayPay 5,000円プレゼント** が贈呈されます！！"
                ),
                color=discord.Color.gold()
            )
            await interaction.response.edit_message(embed=win_embed, view=self)
            return

        conn.close()
        hp_bar = make_hp_bar(new_hp, max_hp, 15)
        embed = discord.Embed(
            title="🚨 【月1回・神出鬼没】運営レイドボス降臨中！！",
            description=(
                f"👑 **ボス名**：**{boss_name}**\n"
                f"🎁 **討伐報酬**：**PayPay 5,000円プレゼント！！**\n\n"
                f"❤️ **残りHP**：**`{new_hp:,} / {max_hp:,}`**\n"
                f"{hp_bar}\n\n"
                f"⚔️ 直近の攻撃：{interaction.user.mention} が **`{dmg:,}`** ダメージ！"
            ),
            color=discord.Color.dark_red()
        )
        await interaction.response.edit_message(embed=embed, view=self)

# ==========================================
# 11. 【創造神専用】臨時強キャラ創造 ＆ ガチャ中身・確率操作UI
# ==========================================
class CreateGodCharModal(discord.ui.Modal, title="👑 創造神権限：臨時強キャラの創造"):
    c_name = discord.ui.TextInput(label="キャラ名（例：終焉の創造神・アザトース）", required=True, max_length=30)
    c_rarity = discord.ui.TextInput(label="初期レアリティ（SR / SSR / UR / LR / MCR）", default="MCR", required=True, max_length=5)
    c_ult = discord.ui.TextInput(label="固有必殺技名（例：創世崩壊・ビッグバン）", required=True, max_length=30)
    c_stats = discord.ui.TextInput(label="基礎ステ（HP,ATK,DEF をカンマ区切り）", default="5000,1200,800", required=True, max_length=30)

    async def on_submit(self, interaction: discord.Interaction):
        rar = self.c_rarity.value.strip().upper()
        if rar not in RARITIES:
            rar = "MCR"
        try:
            b_hp, b_atk, b_def = [int(x.strip()) for x in self.c_stats.value.split(",")]
        except Exception:
            b_hp, b_atk, b_def = 5000, 1200, 800

        conn = get_db()
        max_row = conn.execute("SELECT COALESCE(MAX(id), 200) AS m FROM custom_chars").fetchone()
        new_id = max(201, max_row["m"] + 1)

        conn.execute(
            """INSERT INTO custom_chars
            (id, name, base_rarity, race, job, passive_name, passive_type, passive_val, passive_desc, ult_name, base_hp, base_atk, base_def)
            VALUES (?, ?, ?, '創造神族', '超越者', '創造神の権能', 'atk_up', 0.50, '攻撃力+50%', ?, ?, ?, ?)""",
            (new_id, self.c_name.value.strip(), rar, self.c_ult.value.strip(), b_hp, b_atk, b_def)
        )
        conn.execute(
            "INSERT OR REPLACE INTO user_chars (user_id, char_id, rarity, level, exp, limit_break) VALUES (?, ?, ?, 1, 0, 5)",
            (interaction.user.id, new_id, rar)
        )
        conn.commit()
        conn.close()
        reload_custom_characters()

        await interaction.response.send_message(
            f"👑 **新キャラクター『No.{new_id} [{rar}] {self.c_name.value.strip()}』を創造しました！**\n"
            f"・基礎ステ：HP `{b_hp:,}` / ATK `{b_atk:,}` / DEF `{b_def:,}`（必殺：`{self.c_ult.value.strip()}`）\n"
            f"・創造神（あなた）の手持ちにも **5凸（Lv上限200）** で自動付与済み！限定ガチャのPU対象＆ガチャ排出一覧にも自動反映されます。",
            ephemeral=True
        )
class ConfigLimitedGachaModal(discord.ui.Modal, title="🌟 期間限定ピックアップガチャ設定"):
    g_title = discord.ui.TextInput(label="限定ガチャのバナー名", default="【期間限定】創造神降臨ピックアップ召喚", required=True, max_length=40)
    pu_id = discord.ui.TextInput(label="ピックアップするキャラ番号（例：200 や 201）", default="200", required=True, max_length=5)
    pu_rate = discord.ui.TextInput(label="PU排出率（1000分率：例 50 = 5.0%）", default="50", required=True, max_length=4)
    active_flag = discord.ui.TextInput(label="開催状態（1 = 開催ON / 0 = 終了OFF）", default="1", required=True, max_length=1)

    async def on_submit(self, interaction: discord.Interaction):
        cid = int(self.pu_id.value.strip()) if self.pu_id.value.strip().isdigit() else 200
        rate = min(1000, max(1, int(self.pu_rate.value.strip()))) if self.pu_rate.value.strip().isdigit() else 50
        act = "1" if self.active_flag.value.strip() == "1" else "0"

        set_state("limited_gacha_title", self.g_title.value.strip())
        set_state("limited_gacha_char_id", str(cid))
        set_state("limited_gacha_rate_permille", str(rate))
        set_state("limited_gacha_active", act)

        ch_name = CHARACTERS[cid]["name"] if cid in CHARACTERS else f"ID:{cid}"
        status_str = "🟢 開催ON" if act == "1" else "🔴 終了OFF"
        await interaction.response.send_message(
            f"✅ **限定ガチャ設定を更新しました！**\n"
            f"・状態：**{status_str}** ／ タイトル：**{self.g_title.value.strip()}**\n"
            f"・PU対象：**No.{cid} {ch_name}**（排出率：`{rate / 10:.1f}%`）",
            ephemeral=True
        )

class GodControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="🧬 臨時強キャラを創造する", style=discord.ButtonStyle.danger, row=0)
    async def create_char_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CreateGodCharModal())

    @discord.ui.button(label="🌟 限定ガチャ中身・確率操作", style=discord.ButtonStyle.primary, row=0)
    async def cfg_gacha_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ConfigLimitedGachaModal())

    @discord.ui.button(label="💎 無限リソース生成（石・G・結晶）", style=discord.ButtonStyle.success, row=1)
    async def inf_res_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        ensure_player(uid)
        conn = get_db()
        conn.execute("UPDATE players SET gems = gems + 99999, gold = gold + 9999999, crystals = crystals + 9999 WHERE user_id = ?", (uid,))
        conn.commit()
        conn.close()
        await interaction.response.send_message("✅ **創造神の権能発動！** ガチャ石 `+99,999` / ゴールド `+9,999,999G` / 進化結晶 `+9,999個` を生成しました！", ephemeral=True)

    @discord.ui.button(label="⚡ 装備中キャラ即LvMAX＆MCR化", style=discord.ButtonStyle.secondary, row=1)
    async def max_char_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        ensure_player(uid)
        conn = get_db()
        p = conn.execute("SELECT equipped_char_id FROM players WHERE user_id = ?", (uid,)).fetchone()
        cid = p["equipped_char_id"]
        uc = conn.execute("SELECT limit_break FROM user_chars WHERE user_id = ? AND char_id = ?", (uid, cid)).fetchone()
        m_lv = get_max_level(uc["limit_break"])
        conn.execute("UPDATE user_chars SET rarity = 'MCR', level = ?, exp = 0 WHERE user_id = ? AND char_id = ?", (m_lv, uid, cid))
        conn.commit()
        conn.close()
        await interaction.response.send_message(f"⚡ 装備中キャラ（No.{cid}）を最高レア **`MCR`** ＆ **`Lv.{m_lv}`** へ一瞬で覚醒させました！", ephemeral=True)

# ==========================================
# 12. 課金ショップ ＆ 創造神ワンタップ承認システム
# ==========================================
SHOP_PACKS = {
    "pack_500": ("💎 お試しパック（500円）", 600, 0, ""),
    "pack_1500": ("💎 冒険者パック（1,500円）", 2000, 10, ""),
    "pack_5000": ("👑 覇王パック（5,000円）", 7500, 40, "【黄金の支援者（パトロン）】"),
}

class BillingApproveView(discord.ui.View):
    def __init__(self, buyer_id: int, pack_key: str):
        super().__init__(timeout=None)
        self.buyer_id = buyer_id
        self.pack_key = pack_key

    @discord.ui.button(label="✅ 入金確認・即時付与する", style=discord.ButtonStyle.success)
    async def approve_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("❌ 創造神（オーナー）のみ承認可能です。", ephemeral=True)
            return
        p_name, gems, crys, title = SHOP_PACKS[self.pack_key]
        ensure_player(self.buyer_id)
        conn = get_db()
        conn.execute("UPDATE players SET gems = gems + ?, crystals = crystals + ? WHERE user_id = ?", (gems, crys, self.buyer_id))
        conn.commit()
        conn.close()
        if title:
            unlock_title(self.buyer_id, title)
            await sync_rank_and_badges(interaction.guild, self.buyer_id)
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content=f"✅ **承認完了！** <@{self.buyer_id}> に **{p_name}** の特典を自動付与しました！", view=self)
class BillingApplyModal(discord.ui.Modal, title="💎 課金パック購入申請（PayPay送金リンク）"):
    pay_link = discord.ui.TextInput(
        label="PayPay送金リンク（または受取ID・送金メモ）",
        placeholder="https://paypay.ne.jp...",
        required=True,
        max_length=200
    )

    def __init__(self, pack_key: str):
        super().__init__()
        self.pack_key = pack_key

    async def on_submit(self, interaction: discord.Interaction):
        p_name, gems, crys, title = SHOP_PACKS[self.pack_key]
        owner_user = interaction.client.get_user(OWNER_ID) or await interaction.client.fetch_user(OWNER_ID)

        embed = discord.Embed(
            title="💰 【新規課金申請】PayPay送金が届きました！",
            description=(
                f"👤 **購入者**：{interaction.user.mention} (`{interaction.user.id}`)\n"
                f"📦 **選択パック**：**{p_name}**\n"
                f"🎁 **付与予定**：ガチャ石 `{gems:,}個` / 進化結晶 `{crys}個` {f'/ 肩書き `{title}`' if title else ''}\n"
                f"🔗 **送金リンク/情報**：\n{self.pay_link.value.strip()}"
            ),
            color=discord.Color.gold()
        )
        try:
            await owner_user.send(embed=embed, view=BillingApproveView(interaction.user.id, self.pack_key))
            await interaction.response.send_message(
                f"✅ **{p_name}** の購入申請を創造神へ送信しました！\n入金確認ボタンが押され次第、自動でガチャ石と特典が付与されます。",
                ephemeral=True
            )
        except Exception:
            await interaction.response.send_message(
                "❌ 創造神へのDM送信に失敗しました。サーバー管理者へ直接お問い合わせください。",
                ephemeral=True
            )

class BillingPackSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="💎 お試しパック（500円）", value="pack_500", description="ガチャ石 600個（単発6回分）"),
            discord.SelectOption(label="💎 冒険者パック（1,500円）", value="pack_1500", description="ガチャ石 2,000個 ＋ 進化結晶 10個"),
            discord.SelectOption(label="👑 覇王パック（5,000円）", value="pack_5000", description="ガチャ石 7,500個 ＋ 結晶 40個 ＋ 限定肩書き"),
        ]
        super().__init__(custom_id="billing_pack_select", placeholder="購入する課金パックを選択してください", min_values=1, max_values=1, options=options)


    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(BillingApplyModal(next(iter(self.values))))

class BillingShopView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(BillingPackSelect())
# ==========================================
# 13. 機能別専用パネル（全7種）オープン処理
# ==========================================

async def open_sortie_panel(interaction: discord.Interaction):
    uid = interaction.user.id
    user = get_user(uid, interaction.user.display_name)
    stamina = user.get("stamina", 100)
    max_stamina = user.get("max_stamina", 100)
    chapter = user.get("chapter", 1)

    embed = discord.Embed(
        title="⚔️ 出撃・クエスト選択",
        description=(
            f"指揮官 **{interaction.user.display_name}**、出撃先を選択してください。\n"
            f"⚡ スタミナ: **{stamina} / {max_stamina}**\n"
            f"📖 現在のストーリー進行度: **第{chapter}章**"
        ),
        color=discord.Color.red()
    )
    if GUERRILLA_ACTIVE:
        embed.add_field(
            name="🔥 ゲリライベント開催中！",
            value="現在、獲得経験値＆魔晶石が **3倍** になっています！",
            inline=False
        )
    view = SortieView(uid)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def open_gacha_panel(interaction: discord.Interaction):
    uid = interaction.user.id
    user = get_user(uid, interaction.user.display_name)
    crystals = user.get("crystals", 0)
    tickets = user.get("gacha_tickets", 0)

    embed = discord.Embed(
        title="🔮 次元召喚（ガチャ）",
        description=(
            f"所持魔晶石: **💎 {crystals:,}個** / 召喚チケット: **🎫 {tickets}枚**\n"
            "下のボタンから召喚するガチャの種類を選択してください。"
        ),
        color=discord.Color.purple()
    )
    view = GachaPanelView(uid, sys.modules[__name__])
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def open_armory_panel(interaction: discord.Interaction):
    uid = interaction.user.id
    user = get_user(uid, interaction.user.display_name)
    party = json.loads(user.get("party", "[]"))
    gold = user.get("gold", 0)

    party_names = []
    for idx, cid in enumerate(party, 1):
        c_data = get_char_instance(uid, cid)
        if c_data:
            party_names.append(f"`枠{idx}` ★{c_data['rarity']} **{c_data['name']}** (Lv.{c_data['level']})")
        else:
            party_names.append(f"`枠{idx}` *(未編成)*")

    embed = discord.Embed(
        title="🛡️ 兵舎・武装庫（編成・進化・売却）",
        description=(
            f"所持資金: **🪙 {gold:,} G**\n\n"
            "**【現在の出撃部隊】**\n" + ("\n".join(party_names) if party_names else "未編成")
        ),
        color=discord.Color.blue()
    )
    view = ArmoryView(uid)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
async def open_facility_panel(interaction: discord.Interaction):
    uid = interaction.user.id
    user = get_user(uid, interaction.user.display_name)
    gold = user.get("gold", 0)
    f_lv = json.loads(user.get("facilities", '{"barracks":1,"mine":1,"library":1,"wall":1}'))

    embed = discord.Embed(
        title="🏰 領地開発・施設強化",
        description=(
            f"所持資金: **🪙 {gold:,} G**\n"
            "施設を強化すると全キャラの基礎ステータスや資源生産効率が上昇します。\n\n"
            f"⚔️ **兵舎**: Lv.{f_lv.get('barracks', 1)}（攻撃力ボーナス）\n"
            f"⛏️ **魔晶鉱山**: Lv.{f_lv.get('mine', 1)}（資金・結晶獲得量UP）\n"
            f"📚 **大図書館**: Lv.{f_lv.get('library', 1)}（獲得経験値UP）\n"
            f"🛡️ **城壁**: Lv.{f_lv.get('wall', 1)}（HP・防御力ボーナス）"
        ),
        color=discord.Color.gold()
    )
    view = FacilityView(uid)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def open_rank_panel(interaction: discord.Interaction):
    uid = interaction.user.id
    user = get_user(uid, interaction.user.display_name)
    rp = user.get("rank_points", 1000)
    rank_name = get_rank_title(rp)
    wins = user.get("pvp_wins", 0)
    losses = user.get("pvp_losses", 0)

    embed = discord.Embed(
        title="🏆 帝国闘技場（ランクマッチ・下剋上）",
        description=(
            f"現在の階級: **{rank_name}** (`{rp} RP`)\n"
            f"対戦戦績: **{wins}勝 {losses}敗**\n\n"
            "上位階級の指揮官に勝利すると「下剋上ボーナス」で大量RPを獲得！\n"
            "下のボタンからマッチング待機列に参加してください。"
        ),
        color=discord.Color.dark_red()
    )
    view = RankMatchControlView(uid)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def open_guild_panel(interaction: discord.Interaction):
    uid = interaction.user.id
    user = get_user(uid, interaction.user.display_name)
    guild_id = user.get("guild_id")

    if guild_id:
        g_info = get_guild(guild_id)
        g_name = g_info["name"] if g_info else "所属騎士団"
        g_lv = g_info["level"] if g_info else 1
        desc = f"所属騎士団: **⚜️ {g_name}** (団ランク Lv.{g_lv})\n団員との協力任務や騎士団資金の寄付が可能です。"
    else:
        desc = "現在どの騎士団にも所属していません。\n既存の騎士団へ入団するか、新たな騎士団を創設できます。"

    embed = discord.Embed(
        title="⚜️ 王国騎士団本部",
        description=desc,
        color=discord.Color.teal()
    )
    view = GuildControlView(uid)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def open_profile_panel(interaction: discord.Interaction):
    uid = interaction.user.id
    user = get_user(uid, interaction.user.display_name)
    rp = user.get("rank_points", 1000)
    title_str = user.get("equipped_title", "新米指揮官")
    level = user.get("level", 1)
    crystals = user.get("crystals", 0)
    gold = user.get("gold", 0)

    embed = discord.Embed(
        title=f"📜 指揮官戦績カード｜{interaction.user.display_name}",
        description=(
            f"🏷️ 装備中の肩書き: **【{title_str}】**\n"
            f"🎖️ 指揮官Lv: **{level}** / 階級: **{get_rank_title(rp)}** (`{rp} RP`)\n"
            f"💎 魔晶石: **{crystals:,}** / 🪙 資金: **{gold:,} G**"
        ),
        color=discord.Color.blurple()
    )
    view = ProfileControlView(uid)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
# ==========================================
# 14. 永続Viewクラス群（チャンネル常設パネル用）
# ==========================================

class QuestOnlyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="⚔️ 出撃・ストーリー",
        style=discord.ButtonStyle.danger,
        custom_id="persist_panel:quest_sortie"
    )
    async def btn_sortie(self, interaction: discord.Interaction, button: discord.ui.Button):
        await open_sortie_panel(interaction)

    @discord.ui.button(
        label="🐉 運営レイド挑戦",
        style=discord.ButtonStyle.secondary,
        custom_id="persist_panel:quest_raid"
    )
    async def btn_raid(self, interaction: discord.Interaction, button: discord.ui.Button):
        await open_raid_panel(interaction)


class GachaOnlyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🔮 次元召喚（ガチャ）を開く",
        style=discord.ButtonStyle.primary,
        custom_id="persist_panel:gacha_open"
    )
    async def btn_gacha(self, interaction: discord.Interaction, button: discord.ui.Button):
        await open_gacha_panel(interaction)


class ArmoryOnlyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🛡️ 編成・進化・売却",
        style=discord.ButtonStyle.primary,
        custom_id="persist_panel:armory_open"
    )
    async def btn_armory(self, interaction: discord.Interaction, button: discord.ui.Button):
        await open_armory_panel(interaction)

    @discord.ui.button(
        label="🏰 領地施設強化",
        style=discord.ButtonStyle.success,
        custom_id="persist_panel:facility_open"
    )
    async def btn_facility(self, interaction: discord.Interaction, button: discord.ui.Button):
        await open_facility_panel(interaction)


class RankMatchOnlyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🏆 ランクマッチ・下剋上へ",
        style=discord.ButtonStyle.danger,
        custom_id="persist_panel:rank_open"
    )
    async def btn_rank(self, interaction: discord.Interaction, button: discord.ui.Button):
        await open_rank_panel(interaction)


class GuildOnlyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="⚜️ 騎士団本部を開く",
        style=discord.ButtonStyle.success,
        custom_id="persist_panel:guild_open"
    )
    async def btn_guild(self, interaction: discord.Interaction, button: discord.ui.Button):
        await open_guild_panel(interaction)


class ProfileOnlyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="📜 戦績・ランキング・肩書き",
        style=discord.ButtonStyle.secondary,
        custom_id="persist_panel:profile_open"
    )
    async def btn_profile(self, interaction: discord.Interaction, button: discord.ui.Button):
        await open_profile_panel(interaction)
# ==========================================
# 15. RPGCommandBot 本体 & 4時間自動ゲリラループ
# ==========================================

GUERRILLA_ACTIVE = False
GUERRILLA_END_TIME = None


class RPGCommandBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # 永続Viewの全登録（再起動後もボタンを有効化）
        self.add_view(QuestOnlyView())
        self.add_view(GachaOnlyView())
        self.add_view(ArmoryOnlyView())
        self.add_view(RankMatchOnlyView())
        self.add_view(GuildOnlyView())
        self.add_view(ProfileOnlyView())
        self.add_view(BillingShopView())

        # 4時間ごとの自動ゲリラループ開始
        if not self.auto_guerrilla_loop.is_running():
            self.auto_guerrilla_loop.start()

        # スラッシュコマンド同期
        await self.tree.sync()
        print("✅ スラッシュコマンドと全永続Viewの同期が完了しました。")

    async def on_ready(self):
        print(f"🚀 Logged in as {self.user} (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Game(name="⚔️ 帝国戦記RPG｜各チャンネルのパネルから出撃！")
        )

    @tasks.loop(hours=4)
    async def auto_guerrilla_loop(self):
        global GUERRILLA_ACTIVE, GUERRILLA_END_TIME
        GUERRILLA_ACTIVE = True
        GUERRILLA_END_TIME = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=30)
        print("🔥 [AUTO] 30分間の経験値＆結晶3倍ゲリラが自動発動しました！")
        await asyncio.sleep(1800)
        GUERRILLA_ACTIVE = False
        GUERRILLA_END_TIME = None
        print("❄️ [AUTO] 自動ゲリライベントが終了しました。")

    @auto_guerrilla_loop.before_loop
    async def before_guerrilla_loop(self):
        await self.wait_until_ready()


bot = RPGCommandBot()
@bot.tree.command(name="guerrilla", description="【運営専用】経験値＆魔晶石3倍ゲリラを即時発動します")
@app_commands.describe(minutes="開催時間（分・デフォルト30分）")
@is_owner()
async def cmd_guerrilla(interaction: discord.Interaction, minutes: int = 30):
    global GUERRILLA_ACTIVE, GUERRILLA_END_TIME
    GUERRILLA_ACTIVE = True
    GUERRILLA_END_TIME = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=minutes)

    embed = discord.Embed(
        title="🔥 【緊急ゲリラ発動】経験値＆魔晶石 3倍フィーバー！",
        description=f"創造神の恩寵により、今から **{minutes}分間** 全クエストの獲得経験値と魔晶石が **3倍** になります！",
        color=discord.Color.orange()
    )
    await interaction.response.send_message(embed=embed)

    async def _end_timer(sec: int):
        global GUERRILLA_ACTIVE, GUERRILLA_END_TIME
        await asyncio.sleep(sec)
        GUERRILLA_ACTIVE = False
        GUERRILLA_END_TIME = None

    asyncio.create_task(_end_timer(minutes * 60))


@bot.tree.command(name="spawn_raid", description="【運営専用】月1回の運営レイドボスを降臨させます")
@app_commands.describe(boss_name="レイドボス名", max_hp="ボスの最大HP")
@is_owner()
async def cmd_spawn_raid(
    interaction: discord.Interaction,
    boss_name: str = "終焉の魔竜・バハムート",
    max_hp: int = 5000000
):
    init_raid_boss(boss_name, max_hp)
    embed = discord.Embed(
        title="🐉 【緊急警告】運営レイドボス降臨！",
        description=(
            f"災厄の巨獣 **{boss_name}** が戦場に現れました！\n"
            f"❤️ 総HP: **{max_hp:,}**\n\n"
            "出撃パネルの「🐉 運営レイド挑戦」から全指揮官で討伐に挑んでください！"
        ),
        color=discord.Color.dark_purple()
    )
    await interaction.response.send_message(embed=embed)


# ==========================================
# 17. Render用ヘルスチェックサーバー & Bot起動
# ==========================================

async def handle_health(request):
    return web.Response(text="Commander RPG Bot is running!", status=200)


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_health)
    app.router.add_get("/health", handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 Render Health Check Server listening on port {port}")


async def main():
    init_db()
    await start_web_server()
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("環境変数 DISCORD_TOKEN が設定されていません。")
    async with bot:
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
