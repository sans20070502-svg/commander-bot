import os
import sqlite3
import random
import asyncio
from datetime import datetime, timezone, timedelta
import discord
from discord import app_commands
from discord.ext import commands, tasks

JST = timezone(timedelta(hours=9))
TOKEN = os.environ.get("DISCORD_TOKEN", "").strip()
OWNER_ID = int(os.environ.get("OWNER_ID", "0").strip())  # 運営（創造主）専用ID
DB_PATH = "commander.db"

# 運営リアルタイム制御フラグ
FESTIVAL_ACTIVE = False
MAINTENANCE_MODE = False
WORLD_BUFF = "通常情勢（ボーナスなし）"

# ==========================================
# 1. 階級＆ランク戦ティア定義
# ==========================================
RANKS = [
    (0, "二等兵", "🪖"),
    (5000, "軍曹", "🎖️"),
    (25000, "少尉", "⚔️"),
    (100000, "大佐", "🦅"),
    (400000, "少将", "🛡️"),
    (1500000, "大将", "🔥"),
    (6000000, "元帥", "👑"),
    (25000000, "最高司令官", "⚡"),
    (100000000, "国家元首・覇王", "🌌"),
]

PVP_TIERS = [
    (0, "ブロンズ", "🥉"),
    (500, "シルバー", "🥈"),
    (1200, "ゴールド", "🥇"),
    (2200, "プラチナ", "💠"),
    (3500, "ダイヤモンド", "💎"),
    (5000, "マスター", "🔥"),
    (7500, "グランドマスター", "👑"),
    (10000, "覇王", "🌌"),
]

# 実在国の軍事力データ（弱→強の順：999ステージ自動生成のベース）
REAL_COUNTRIES = [
    ("アイスランド防衛警備隊", "🛡️", 0.5),
    ("ニュージーランド国防軍", "🇳🇿", 0.8),
    ("ノルウェー王国軍", "🇳🇴", 1.1),
    ("スウェーデン国防軍", "🇸🇪", 1.4),
    ("カナダ統合軍", "🇨🇦", 1.8),
    ("スペイン王国軍", "🇪🇸", 2.2),
    ("オーストラリア国防軍", "🇦🇺", 2.7),
    ("ポーランド共和国軍", "🇵🇱", 3.3),
    ("ドイツ連邦軍", "🇩🇪", 4.0),
    ("イスラエル国防軍（精鋭機甲＆防空網）", "🇮🇱", 4.8),
    ("トルコ共和国軍", "🇹🇷", 5.6),
    ("イタリア共和国軍", "🇮🇹", 6.5),
    ("フランス共和国軍（核保有・空母戦力）", "🇫🇷", 7.8),
    ("イギリス統合軍（王立海軍・戦略原潜）", "🇬🇧", 9.0),
    ("大韓民国国軍（大規模砲兵・機甲師団）", "🇰🇷", 10.5),
    ("日本国自衛隊（イージス艦隊・潜水艦・ハイテク防空）", "🇯🇵", 13.0),
    ("インド共和国軍（百万規模の陸軍・核ミサイル網）", "🇮🇳", 16.5),
    ("ロシア連邦軍（戦略核戦力・重機甲師団）", "🇷🇺", 21.0),
    ("中国人民解放軍（圧倒的物量・弾道ミサイル網・巨大海軍）", "🇨🇳", 26.0),
    ("アメリカ合衆国軍（世界最強・11個空母打撃群＆ステルス部隊）", "🇺🇸", 33.0),
]

# ==========================================
# 2. 全8レアリティ設定（R・SR主力 / UR 0.01%・LR 0.003%・MR 0.001%）
# ==========================================
RARITY_CONFIG = {
    "C":   {"name": "コモン",             "color": 0x2ECC71, "weight": 40.000, "fes": 38.000, "emoji": "🟢", "mat": "mat_parts"},
    "UC":  {"name": "アンコモン",         "color": 0xCD7F32, "weight": 28.000, "fes": 27.000, "emoji": "🟤", "mat": "mat_parts"},
    "R":   {"name": "レア",               "color": 0xBDC3C7, "weight": 20.000, "fes": 20.000, "emoji": "⚪", "mat": "mat_parts"},
    "SR":  {"name": "スーパーレア",       "color": 0xF1C40F, "weight": 10.500, "fes": 11.972, "emoji": "🟡", "mat": "mat_alloy"},
    "SSR": {"name": "スーパースペシャル", "color": 0x9B59B6, "weight": 1.486,  "fes": 3.000,  "emoji": "🌈", "mat": "mat_alloy"},
    "UR":  {"name": "ウルトラレア",       "color": 0xFF69B4, "weight": 0.010,  "fes": 0.020,  "emoji": "🩷", "mat": "mat_quantum"},
    "LR":  {"name": "レジェンドレア",     "color": 0xECF0F1, "weight": 0.003,  "fes": 0.006,  "emoji": "✨", "mat": "mat_quantum"},
    "MR":  {"name": "ミシックレア",       "color": 0x8B0000, "weight": 0.001,  "fes": 0.002,  "emoji": "🩸", "mat": "mat_mythic"},
}

MAT_NAMES = {
    "mat_parts":   "🔩 精密兵器パーツ（C〜R突破用）",
    "mat_alloy":   "⚙️ 超合金コア（SR・SSR突破用）",
    "mat_quantum": "💠 量子エネルギー結晶（UR・LR突破用）",
    "mat_mythic":  "🩸 深紅の覇王核（MR突破用）",
}

WEAPONS = {
    1: ("標準アサルトライフル", 1.05, "全能力+5%"),
    2: ("重装甲リアクティブシールド", 1.10, "全能力+10%"),
    3: ("マッハブースター推進機", 1.15, "全能力+15%"),
    4: ("戦術核弾頭ミサイルポッド", 1.25, "全能力+25%"),
    5: ("軌道衛星リンク・オメガシステム", 1.40, "全能力+40%"),
    6: ("【神話兵器】終末の紅蓮魔導機装", 1.75, "全能力+75%・運営級破壊力"),
}
# ==========================================
# 3. データベース初期化＆全20キャラ＋育成データ
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            funds INTEGER DEFAULT 15000,
            gems INTEGER DEFAULT 3000,
            free_ten_pull INTEGER DEFAULT 1,
            base_name TEXT DEFAULT '第1前線基地',
            base_hq INTEGER DEFAULT 1,
            base_factory INTEGER DEFAULT 1,
            base_nuke_lab INTEGER DEFAULT 1,
            base_defense INTEGER DEFAULT 1,
            nuke_count INTEGER DEFAULT 0,
            nuke_megaton INTEGER DEFAULT 0,
            equipped_title TEXT DEFAULT '名もなき新兵',
            custom_rank TEXT DEFAULT '',
            bonus_power INTEGER DEFAULT 0,
            rp INTEGER DEFAULT 0,
            story_stage INTEGER DEFAULT 1,
            mat_parts INTEGER DEFAULT 15,
            mat_alloy INTEGER DEFAULT 5,
            mat_quantum INTEGER DEFAULT 0,
            mat_mythic INTEGER DEFAULT 0,
            party_1 INTEGER DEFAULT 1,
            party_2 INTEGER DEFAULT 2,
            party_3 INTEGER DEFAULT 3,
            expedition_end TEXT DEFAULT '',
            last_collect TEXT DEFAULT ''
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_titles (
            user_id INTEGER,
            title TEXT,
            PRIMARY KEY (user_id, title)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rarity TEXT,
            name TEXT,
            role_title TEXT,
            atk INTEGER,
            dfn INTEGER,
            spd INTEGER,
            cmd INTEGER,
            power INTEGER,
            skill_name TEXT,
            skill_desc TEXT,
            ult_name TEXT,
            ult_desc TEXT,
            passive_ability TEXT,
            image_url TEXT DEFAULT ''
        )
    """)
    # level: 現在レベル(1〜100), max_level: 上限レベル(20/40/60/80/100), skill_lv: スキルレベル(1〜10)
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_cards (
            user_id INTEGER,
            card_id INTEGER,
            count INTEGER DEFAULT 1,
            level INTEGER DEFAULT 1,
            max_level INTEGER DEFAULT 20,
            skill_lv INTEGER DEFAULT 1,
            weapon_id INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, card_id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS effect_media (
            key TEXT PRIMARY KEY,
            url TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS raid_boss (
            id INTEGER PRIMARY KEY,
            name TEXT,
            max_hp INTEGER,
            current_hp INTEGER,
            image_url TEXT DEFAULT '',
            active INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS promo_codes (
            code TEXT PRIMARY KEY,
            gems INTEGER DEFAULT 0,
            funds INTEGER DEFAULT 0,
            mat_parts INTEGER DEFAULT 0,
            mat_alloy INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS used_codes (
            user_id INTEGER,
            code TEXT,
            PRIMARY KEY (user_id, code)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS tourney (
            id INTEGER PRIMARY KEY,
            title TEXT,
            status TEXT DEFAULT 'closed',
            bracket_text TEXT DEFAULT ''
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS tourney_entries (
            user_id INTEGER PRIMARY KEY,
            user_name TEXT
        )
    """)

    c.execute("SELECT COUNT(*) FROM cards")
    if c.fetchone() == 0:
        initial_cards = [
            # --- C（コモン：緑） ---
            ("C", "レオン", "量産型装甲車・歩兵分隊長", 140, 160, 110, 120, 700,
             "斉射号令", "味方歩兵の射撃精度と攻撃力を上昇させる",
             "フルバースト突撃", "敵前衛に物理弾幕を浴びせる",
             "【前線適応】基地防衛戦時、自身の防御力+10%", ""),
            ("C", "ミア", "戦術レーダー観測オペレーター", 100, 130, 160, 150, 750,
             "広域索敵スキャン", "敵部隊の隠密状態を解除し命中率を上昇",
             "精密座標ロックオン", "味方全体のクリティカル率を強化",
             "【早期警戒】先制行動確率+15%", ""),
            ("C", "ガッツ", "前線工兵・装甲整備長", 130, 180, 100, 130, 800,
             "緊急フィールド修理", "損傷した味方車両の耐久値を即座に回復",
             "鉄壁バリケード構築", "1ターンの間、味方全体への被ダメージを軽減",
             "【補給効率】軍需工場の資金生産量+5%", ""),

            # --- UC（アンコモン：銅） ---
            ("UC", "クロエ", "偵察ドローン＆軽装甲指揮官", 300, 260, 380, 310, 2400,
             "スウォームドローン", "無数の小型ドローンで敵単体に3連続ダメージ",
             "上空制圧・爆撃誘導", "敵全体に爆撃ダメージ＋防御ダウン",
             "【高速機動】部隊の行動速度+12%", ""),
            ("UC", "バルカン", "重火器・自走ロケット砲手", 450, 280, 190, 260, 2600,
             "焼夷ロケット弾幕", "敵前列に炎上効果付きの砲撃を行う",
             "飽和火力殲滅砲撃", "敵陣全体に重砲撃を叩き込む",
             "【重火器習熟】重装甲ユニットへのダメージ+15%", ""),
            ("UC", "ハヤテ", "低空強襲ヘリパイロット", 390, 250, 420, 290, 2800,
             "ハイスピード・ストレイフ", "高速旋回しながら敵後衛を機関砲で掃射",
             "ヘルファイア連装斉射", "誘導ミサイル8発で単体目標を粉砕する",
             "【低空回避】敵の対空攻撃を15%の確率で回避", ""),

            # --- R（レア：銀・主力エース枠） ---
            ("R", "アイゼン", "第7機甲師団・主力戦車エース", 1100, 1150, 700, 950, 12000,
             "徹甲弾ゼロ距離砲撃", "敵の装甲を50%貫通する主砲撃",
             "鋼鉄の電撃戦（ブリッツ）", "機甲部隊の攻撃力を上げ敵陣を突破",
             "【複合装甲】受ける物理ダメージを常に15%カット", ""),
            ("R", "セラフィナ", "音速ジェット戦闘機エース", 1250, 820, 1400, 1020, 13500,
             "マッハ・ドッグファイト", "超音速機動で敵航空戦力を確実に撃墜",
             "アフターバーナー強襲", "敵全体に空対地ミサイル雨を降らせる",
             "【制空権掌握】戦闘開始時、味方全体の速度+20%", ""),
            ("R", "カゲロウ", "光学迷彩・超長距離スナイパー", 1380, 740, 1220, 920, 15000,
             "サイレント・ヘッドショット", "ステルス状態から必ずクリティカルとなる一撃",
             "零距離・対物ライフル貫通", "敵指揮官単体に致命的貫通ダメージ",
             "【光学迷彩】3ターンの間、敵の単体攻撃対象にならない", ""),

            # --- SR（スーパーレア：金・主力将軍枠） ---
            ("SR", "提督・ジン", "イージス艦隊・海上防衛司令", 2800, 3100, 2100, 3200, 42000,
             "イージス迎撃システム", "敵のミサイル・砲撃を無効化し反撃する",
             "トマホーク巡航ミサイル斉射", "敵全軍に広域爆撃＋行動遅延",
             "【艦隊司令の威光】味方全体の防御力+25%", ""),
            ("SR", "ノヴァ", "ステルス戦略爆撃機エース", 3500, 2300, 3400, 2900, 46000,
             "ナイトホーク奇襲", "レーダーに映らず敵拠点へ精密爆撃",
             "デイジーカッター絨毯爆撃", "戦場全体を焼き尽くす超大型爆撃",
             "【完全ステルス】初回スキル発動時、ダメージ1.5倍", ""),
            ("SR", "ベルグ将軍", "鉄壁の重装甲師団長", 3100, 3600, 2000, 3500, 50000,
             "不落の要塞陣形", "味方全体の受けるダメージを軽減し士気回復",
             "重装機甲・全軍突撃", "防御力を攻撃力に加算し全体攻撃",
             "【百戦錬磨の統率】部隊総戦力がさらに+10%上昇", ""),

            # --- SSR（スーパースペシャル：濃い虹・稀） ---
            ("SSR", "アストレア", "超巨大空中空母・艦長", 7800, 7200, 6900, 8200, 160000,
             "無人迎撃機スクランブル", "空中空母から50機の自律戦闘機を発進させ制圧",
             "天空からの裁き・荷電粒子砲", "雲上から超高出力レーザーを照射",
             "【空中要塞】全ステータス+20%・状態異常完全無効", ""),
            ("SSR", "ヴァルキリー・改", "七色強化外骨格・突撃機兵", 9100, 6600, 9500, 7400, 185000,
             "プリズム・ブレード連舞", "虹色の高周波ブレードで敵陣を7連撃で切り裂く",
             "オーバードライブ・閃光突貫", "限界出力で敵単体に防御無視ダメージ",
             "【反応装甲】HP50%以下で攻撃力と速度が1.6倍に覚醒", ""),
            ("SSR", "軍師・シオン", "最高戦略参謀・天才軍師", 7200, 7600, 8600, 9900, 210000,
             "絶対戦術予測", "敵の次の行動を完全に封じ、味方の火力を強化",
             "チェックメイト・完全包囲網", "敵全軍に戦術爆撃＋全バフ解除",
             "【天才の頭脳】全施設の資源生産効率+25%", ""),

            # --- UR（ウルトラレア：ピンク・極稀 0.01%） ---
            ("UR", "司令官・カイン", "大陸間戦略核ミサイル統括", 22000, 17000, 18500, 23000, 600000,
             "戦術核弾頭・先行着弾", "敵前線を蒸発させる熱核エネルギー攻撃",
             "ICBM・終末の流星群", "12発の多弾頭核ミサイルで敵全軍に壊滅ダメージ",
             "【核抑止力】自身の戦力と核兵器威力が常に+30%", ""),
            ("UR", "ルミナ", "軌道レーザー衛星オペレーター", 25000, 16000, 24000, 21500, 720000,
             "サテライト・ピンポイント照射", "宇宙軌道から敵の主力を一瞬で蒸発させる",
             "ヘブンズ・ジャッジメント", "衛星ネットワーク全開で極太レーザー殲滅",
             "【軌道上の支配者】回避不能の必中攻撃＆防御力60%無視", ""),

            # --- LR（レジェンドレア：白多めの虹・超絶稀 0.003%） ---
            ("LR", "白銀元帥・アルテミス", "白虹の翼を纏う伝説の英雄", 68000, 62000, 72000, 78000, 2500000,
             "白銀の聖域展開", "味方全軍のダメージ無効バリアを張り全能力上昇",
             "セイクリッド・ノヴァ", "白き虹の極光で戦場全体を浄化する超殲滅波",
             "【伝説のカリスマ】全ユニットの戦力ボーナス+20%", ""),

            # --- MR（ミシックレア：赤と黒・極絶稀 0.001%） ---
            ("MR", "終末最高司令官・リリス", "深紅の機神を従える絶対支配者", 240000, 210000, 235000, 290000, 12000000,
             "紅蓮の覇王領域", "漆黒のダークオーラで敵の戦意を砕き全能力を半減させる",
             "終末の紅蓮審判（ラグナロク）", "巨大機神と紅き魔法陣を解放し絶対消滅撃を放つ",
             "【絶対支配者の威圧】あらゆる防御・無敵効果を貫通する神格能力", ""),
            ("MR", "ゴースト・リーパー", "スカル覆面の伝説特殊突撃兵", 280000, 190000, 310000, 250000, 14000000,
             "シャドウ・アサルト", "音もなく背後に回り込み必殺のクリティカル3連撃を叩き込む",
             "死神の無音処刑（レクイエム）", "戦場の全てを闇に沈め単体・全体へ超絶連撃",
             "【死神の加護】先制率100%・回避率50%・クリティカルダメージ3倍", ""),
        ]
        c.executemany("""
            INSERT INTO cards (
                rarity, name, role_title, atk, dfn, spd, cmd, power,
                skill_name, skill_desc, ult_name, ult_desc, passive_ability, image_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, initial_cards)
    conn.commit()
    conn.close()
def get_user(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if not row:
        is_god = (user_id == OWNER_ID)
        init_title = "創造主・絶対最高神" if is_god else "名もなき新兵"
        init_base = "創世・絶対神域要塞" if is_god else "第1前線基地"
        init_funds = 999999999 if is_god else 20000
        init_gems = 999999 if is_god else 3000
        c.execute(
            "INSERT INTO users (user_id, funds, gems, free_ten_pull, base_name, equipped_title, last_collect) VALUES (?, ?, ?, 1, ?, ?, ?)",
            (user_id, init_funds, init_gems, init_base, init_title, datetime.now(JST).isoformat())
        )
        c.execute("INSERT OR IGNORE INTO user_titles (user_id, title) VALUES (?, ?)", (user_id, init_title))
        c.execute("INSERT OR IGNORE INTO user_cards (user_id, card_id, count, level, max_level, skill_lv) VALUES (?, 1, 1, 1, 20, 1)", (user_id,))
        conn.commit()
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
    conn.close()
    return {
        "user_id": row[0],
        "funds": row[1],
        "gems": row[2],
        "free_ten_pull": row[3],
        "base_name": row[4],
        "base_hq": row[5],
        "base_factory": row[6],
        "base_nuke_lab": row[7],
        "base_defense": row[8],
        "nuke_count": row[9],
        "nuke_megaton": row[10],
        "equipped_title": row[11],
        "custom_rank": row[12],
        "bonus_power": row[13],
        "rp": row[14],
        "story_stage": row[15],
        "mat_parts": row[16],
        "mat_alloy": row[17],
        "mat_quantum": row[18],
        "mat_mythic": row[19],
        "party_1": row[20],
        "party_2": row[21],
        "party_3": row[22],
        "expedition_end": row[23],
        "last_collect": row[24],
    }

def calc_total_power(user_id: int) -> int:
    u = get_user(user_id)
    base_power = (
        u["base_hq"] * 3000
        + u["base_factory"] * 2000
        + u["base_nuke_lab"] * 5000
        + u["base_defense"] * 2500
        + u["nuke_count"] * 200000
        + u["nuke_megaton"] * 15000
        + u["bonus_power"]
    )
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT cards.power, user_cards.level, user_cards.skill_lv, user_cards.weapon_id
        FROM user_cards
        JOIN cards ON user_cards.card_id = cards.id
        WHERE user_cards.user_id = ?
    """, (user_id,))
    rows = c.fetchall()
    conn.close()
    card_power = 0
    for p, lv, slv, wid in rows:
        lv_mult = 1.0 + ((lv - 1) * 0.04)     # Lv.100で基本戦力 約4.96倍
        skill_mult = 1.0 + ((slv - 1) * 0.10) # Skill Lv.10で さらに1.9倍
        wep_mult = WEAPONS[wid][1] if wid in WEAPONS else 1.0
        card_power += int(p * lv_mult * skill_mult * wep_mult)
    return base_power + card_power

def get_party_combat_stats(user_id: int):
    u = get_user(user_id)
    party_ids = [u["party_1"], u["party_2"], u["party_3"]]
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    members = []
    total_atk, total_def, total_spd, avg_skill_mult = 0, 0, 0, 1.0
    skill_mults = []
    for cid in party_ids:
        c.execute("SELECT * FROM cards WHERE id = ?", (cid,))
        card = c.fetchone()
        if not card:
            continue
        c.execute("SELECT level, max_level, skill_lv, weapon_id FROM user_cards WHERE user_id = ? AND card_id = ?", (user_id, cid))
        uc = c.fetchone()
        lv = uc[0] if uc else 1
        max_lv = uc[1] if uc else 20
        slv = uc[2] if uc else 1
        wid = uc[3] if uc else 0
        mult = (1.0 + (lv - 1) * 0.04) * (WEAPONS[wid][1] if wid in WEAPONS else 1.0)
        atk = int(card[4] * mult)
        dfn = int(card[5] * mult)
        spd = int(card[6] * mult)
        total_atk += atk
        total_def += dfn
        total_spd += spd
        skill_mults.append(1.0 + (slv - 1) * 0.12)
        members.append({
            "id": card[0], "rarity": card[1], "name": card[2], "role": card[3],
            "atk": atk, "dfn": dfn, "spd": spd, "lv": lv, "max_lv": max_lv, "slv": slv,
            "skill_name": card[9], "ult_name": card[11], "image_url": card[14]
        })
    conn.close()
    if skill_mults:
        avg_skill_mult = sum(skill_mults) / len(skill_mults)
    if not members:
        total_atk, total_def, total_spd = 500, 500, 500
    bonus = u["bonus_power"] // 200
    max_hp = max(3000, total_def * 8 + u["base_hq"] * 1500 + bonus)
    return {
        "members": members,
        "atk": total_atk + bonus,
        "def": total_def + bonus,
        "spd": total_spd,
        "skill_mult": avg_skill_mult,
        "max_hp": max_hp,
        "nuke_count": u["nuke_count"],
        "nuke_dmg": max(15000, u["base_nuke_lab"] * 25000 + u["nuke_megaton"] * 500)
    }

def get_rank_info(user_id: int, power: int):
    u = get_user(user_id)
    if u["custom_rank"]:
        return (0, u["custom_rank"], "👑"), None
    if user_id == OWNER_ID:
        return (0, "創世の絶対最高統帥", "👑"), None
    current_rank = RANKS[0]
    next_rank = None
    for idx, r in enumerate(RANKS):
        if power >= r[0]:
            current_rank = r
            next_rank = RANKS[idx + 1] if idx + 1 < len(RANKS) else None
    return current_rank, next_rank

def get_pvp_tier(user_id: int, rp: int):
    if user_id == OWNER_ID:
        return "🌌 創世神（ランク規格外）"
    tier = f"{PVP_TIERS[0][2]} {PVP_TIERS[0][1]}"
    for r_req, name, emoji in PVP_TIERS:
        if rp >= r_req:
            tier = f"{emoji} {name}"
    return tier

def get_effect_url(key: str) -> str:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT url FROM effect_media WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row and row[0] else ""

async def sync_member_nickname(member: discord.Member, power: int):
    rank_info, _ = get_rank_info(member.id, power)
    u = get_user(member.id)
    base_name = member.name
    suffix = f" 【{rank_info[1]}・{u['equipped_title']}】"
    new_nick = f"{base_name}{suffix}"[:32]
    try:
        if member.display_name != new_nick:
            await member.edit(nick=new_nick)
    except Exception:
        pass
class TacticalBattleView(discord.ui.View):
    def __init__(self, user_id: int, enemy_name: str, enemy_hp: int, enemy_atk: int, enemy_def: int,
                 reward_gems: int, reward_funds: int, reward_rp: int, reward_mat: str,
                 is_rank: bool = False, story_clear_stage: int = 0):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.p_stats = get_party_combat_stats(user_id)
        self.p_hp = self.p_stats["max_hp"]
        self.p_max_hp = self.p_stats["max_hp"]
        self.sp = 0
        self.turn = 1
        self.enemy_name = enemy_name
        self.e_hp = enemy_hp
        self.e_max_hp = enemy_hp
        self.e_atk = enemy_atk
        self.e_def = enemy_def
        self.reward_gems = reward_gems
        self.reward_funds = reward_funds
        self.reward_rp = reward_rp
        self.reward_mat = reward_mat
        self.is_rank = is_rank
        self.story_clear_stage = story_clear_stage
        self.finished = False

    def build_embed(self, log_text: str, color: int = 0xE74C3C, img_url: str = ""):
        lead = self.p_stats["members"] if self.p_stats["members"] else None
        party_names = " / ".join([f"{m['name']}(Lv.{m['lv']}・S{m['slv']})" for m in self.p_stats["members"]]) or "初期歩兵小隊"
        embed = discord.Embed(
            title=f"⚔️ 戦術コマンドバトル｜Turn {self.turn}",
            description=f"**出撃部隊**：{party_names}\n\n{log_text}",
            color=color
        )
        embed.add_field(
            name="🛡️ 自軍ステータス",
            value=f"HP：`{max(0, self.p_hp):,}` / `{self.p_max_hp:,}`\n⚡ 奥義SP：**`{self.sp}%`** / 100%\n☢️ 核弾頭：`{self.p_stats['nuke_count']}発`",
            inline=True
        )
        embed.add_field(
            name=f"👹 敵軍：{self.enemy_name}",
            value=f"HP：`{max(0, self.e_hp):,}` / `{self.e_max_hp:,}`\n⚔️ ATK：`{self.e_atk:,}`",
            inline=True
        )
        if img_url:
            embed.set_image(url=img_url)
        elif lead and lead["image_url"]:
            embed.set_thumbnail(url=lead["image_url"])
        return embed
    async def process_turn(self, interaction: discord.Interaction, action: str):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ 他の司令官の戦闘は操作できません。", ephemeral=True)
        if self.finished:
            return await interaction.response.send_message("この戦闘はすでに決着がついています。", ephemeral=True)

        lead = self.p_stats["members"] if self.p_stats["members"] else None
        skill_n = lead["skill_name"] if lead else "一斉射撃"
        ult_n = lead["ult_name"] if lead else "総力突撃"
        ult_img = lead["image_url"] if lead else ""
        s_mult = self.p_stats["skill_mult"]

        logs = []
        guard_mult = 1.0
        show_img = ""

        if action == "skill":
            dmg = max(500, int((self.p_stats["atk"] * 1.6 * s_mult - self.e_def * 0.3) * random.uniform(0.9, 1.15)))
            self.e_hp -= dmg
            self.sp = min(100, self.sp + 40)
            logs.append(f"⚔️ **【固有スキル：{skill_n}】** 発動！敵軍に **`{dmg:,}`** のダメージ！（SP +40%）")

        elif action == "guard":
            guard_mult = 0.25
            counter = max(300, int(self.p_stats["def"] * 0.9 * s_mult))
            self.e_hp -= counter
            self.sp = min(100, self.sp + 30)
            logs.append(f"🛡️ **【鉄壁防空・迎撃陣形】** 展開！被ダメージ75%軽減＆カウンターで **`{counter:,}`** ダメージ！（SP +30%）")

        elif action == "ult":
            if self.sp < 100:
                return await interaction.response.send_message(f"❌ 奥義SPが足りません！（現在 `{self.sp}%` / 必要 `100%`）", ephemeral=True)
            self.sp = 0
            dmg = max(2500, int(self.p_stats["atk"] * 4.2 * s_mult * random.uniform(0.95, 1.2)))
            self.e_hp -= dmg
            show_img = ult_img
            logs.append(f"🔥 **【必殺奥義：{ult_n}】** 解放！！超絶火力で **`{dmg:,}`** の壊滅ダメージ！！")

        elif action == "nuke":
            if self.p_stats["nuke_count"] <= 0:
                return await interaction.response.send_message("❌ 保有している戦略核弾頭がありません！`/nuke_build` で開発してください。", ephemeral=True)
            self.p_stats["nuke_count"] -= 1
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("UPDATE users SET nuke_count = MAX(0, nuke_count - 1) WHERE user_id = ?", (self.user_id,))
            conn.commit()
            conn.close()
            dmg = self.p_stats["nuke_dmg"]
            self.e_hp -= dmg
            show_img = get_effect_url("nuke")
            logs.append(f"☢️ **【戦略核ミサイル投下】** 目標エリアに核弾頭が着弾！！**`{dmg:,}`** の核熱ダメージ！！")

        if self.e_hp <= 0:
            self.finished = True
            self.clear_items()
            buff_mult = 2 if "好景気" in WORLD_BUFF else 1
            g_gems = self.reward_gems * buff_mult
            g_funds = self.reward_funds * buff_mult
            mat_cnt = 3 if "戒厳令" in WORLD_BUFF else 1

            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute(f"""
                UPDATE users SET
                    gems = gems + ?,
                    funds = funds + ?,
                    rp = rp + ?,
                    {self.reward_mat} = {self.reward_mat} + ?,
                    story_stage = CASE WHEN ? > 0 AND story_stage = ? THEN MIN(999, story_stage + 1) ELSE story_stage END
                WHERE user_id = ?
            """, (g_gems, g_funds, self.reward_rp, mat_cnt, self.story_clear_stage, self.story_clear_stage, self.user_id))
            conn.commit()
            conn.close()

            extra = ""
            if self.is_rank:
                extra += f"\n🏅 ランクポイント：**+{self.reward_rp} RP**"
            if self.story_clear_stage > 0:
                extra += f"\n🌍 **メインストーリー Stage.{self.story_clear_stage} 制圧完了！**（グローバル順位上昇！）"

            logs.append(
                f"\n🏆 **【作戦完全勝利！！】** {self.enemy_name} を殲滅しました！\n"
                f"💎 機密ダイヤ：**+{g_gems:,} 個** / 💰 資金：**+{g_funds:,} G**\n"
                f"📦 突破素材獲得：**{MAT_NAMES[self.reward_mat]} ×{mat_cnt}**{extra}"
            )
            return await interaction.response.edit_message(embed=self.build_embed("\n".join(logs), 0x2ECC71, show_img), view=self)

        e_dmg = max(200, int((self.e_atk - self.p_stats["def"] * 0.25) * guard_mult * random.uniform(0.85, 1.15)))
        self.p_hp -= e_dmg
        logs.append(f"💥 {self.enemy_name} の反撃！自軍に **`{e_dmg:,}`** のダメージ！")

        if self.p_hp <= 0:
            self.finished = True
            self.clear_items()
            if self.is_rank and self.user_id != OWNER_ID:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("UPDATE users SET rp = MAX(0, rp - 15) WHERE user_id = ?", (self.user_id,))
                conn.commit()
                conn.close()
            logs.append("\n💀 **【部隊壊滅・作戦失敗】** `/train` でレベルを上げるか編成を見直して再挑戦せよ！")
            return await interaction.response.edit_message(embed=self.build_embed("\n".join(logs), 0x95A5A6), view=self)

        self.turn += 1
        await interaction.response.edit_message(embed=self.build_embed("\n".join(logs), 0xE74C3C, show_img), view=self)

    @discord.ui.button(label="⚔️ スキル攻撃 (+40SP)", style=discord.ButtonStyle.primary)
    async def btn_skill(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_turn(interaction, "skill")

    @discord.ui.button(label="🛡️ 鉄壁防御・反撃 (+30SP)", style=discord.ButtonStyle.secondary)
    async def btn_guard(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_turn(interaction, "guard")

    @discord.ui.button(label="🔥 必殺奥義解放 (100SP)", style=discord.ButtonStyle.danger)
    async def btn_ult(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_turn(interaction, "ult")

    @discord.ui.button(label="☢️ 戦略核投下", style=discord.ButtonStyle.danger, row=1)
    async def btn_nuke(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_turn(interaction, "nuke")
RANK_QUEUE = {}  # {guild_id: discord.Member}

class PvPTourneyBattleView(discord.ui.View):
    def __init__(self, p1: discord.Member, p2: discord.Member, is_rank_match: bool = False):
        super().__init__(timeout=300)
        self.players = [p1, p2]
        self.stats = [get_party_combat_stats(p1.id), get_party_combat_stats(p2.id)]
        self.hp = [self.stats["max_hp"], self.stats["max_hp"]]
        self.sp = [0, 0]
        self.guard = [1.0, 1.0]
        self.turn_idx = 0
        self.is_rank_match = is_rank_match
        self.finished = False

    def build_embed(self, log: str, color: int = 0xF1C40F):
        cur_p = self.players[self.turn_idx]
        mode_title = "🏅 ランクマッチ対人戦" if self.is_rank_match else "🏆 公式トーナメント対人戦"
        embed = discord.Embed(
            title=f"{mode_title}｜{self.players.display_name} vs {self.players.display_name}",
            description=f"{log}\n\n👉 **現在の行動ターン：{cur_p.mention}**",
            color=color
        )
        for i in (0, 1):
            embed.add_field(
                name=f"⚔️ {self.players[i].display_name}",
                value=f"HP：`{max(0, self.hp[i]):,}` / `{self.stats[i]['max_hp']:,}`\n⚡ SP：**`{self.sp[i]}%`** / ☢️ 核：`{self.stats[i]['nuke_count']}発`",
                inline=True
            )
        return embed

    async def act(self, interaction: discord.Interaction, mode: str):
        if self.finished:
            return await interaction.response.send_message("すでに試合は終了しています。", ephemeral=True)
        if interaction.user.id != self.players[self.turn_idx].id:
            return await interaction.response.send_message("❌ 今は相手の行動ターンです！", ephemeral=True)

        me = self.turn_idx
        opp = 1 - me
        self.guard[me] = 1.0
        s_mult = self.stats[me]["skill_mult"]

        if mode == "skill":
            dmg = max(500, int((self.stats[me]["atk"] * 1.5 * s_mult - self.stats[opp]["def"] * 0.25) * self.guard[opp]))
            self.hp[opp] -= dmg
            self.sp[me] = min(100, self.sp[me] + 40)
            msg = f"⚔️ {self.players[me].display_name} の固有スキル攻撃！**`{dmg:,}`** ダメージ！"
        elif mode == "guard":
            self.guard[me] = 0.25
            self.sp[me] = min(100, self.sp[me] + 35)
            msg = f"🛡️ {self.players[me].display_name} は鉄壁防御を展開！（次ターン被ダメ75%カット＆SP+35%）"
        elif mode == "ult":
            if self.sp[me] < 100:
                return await interaction.response.send_message("❌ SPが100%溜まっていません！", ephemeral=True)
            self.sp[me] = 0
            dmg = max(2500, int(self.stats[me]["atk"] * 4.0 * s_mult * self.guard[opp]))
            self.hp[opp] -= dmg
            msg = f"🔥 {self.players[me].display_name} の**必殺奥義**炸裂！！**`{dmg:,}`** の超絶ダメージ！！"
        elif mode == "nuke":
            if self.stats[me]["nuke_count"] <= 0:
                return await interaction.response.send_message("❌ 保有している核弾頭がありません！", ephemeral=True)
            self.stats[me]["nuke_count"] -= 1
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("UPDATE users SET nuke_count = MAX(0, nuke_count - 1) WHERE user_id = ?", (self.players[me].id,))
            conn.commit()
            conn.close()
            dmg = self.stats[me]["nuke_dmg"]
            self.hp[opp] -= dmg
            msg = f"☢️ {self.players[me].display_name} が**戦略核ミサイル**を投下！！**`{dmg:,}`** の核爆発ダメージ！！"

        if self.hp[opp] <= 0:
            self.finished = True
            self.clear_items()
            winner = self.players[me]
            loser = self.players[opp]
            if self.is_rank_match:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("UPDATE users SET rp = rp + 50, gems = gems + 1500, mat_alloy = mat_alloy + 1 WHERE user_id = ?", (winner.id,))
                if loser.id != OWNER_ID:
                    c.execute("UPDATE users SET rp = MAX(0, rp - 25) WHERE user_id = ?", (loser.id,))
                conn.commit()
                conn.close()
                result_desc = (
                    f"{msg}\n\n🏆 **勝者：{winner.mention}**（`+50 RP` / 💎 `+1,500個` / ⚙️ 超合金 `+1個`）\n"
                    f"💀 **敗者：{loser.mention}**（`-25 RP`）"
                )
            else:
                result_desc = f"{msg}\n\n🎉 **勝者：{winner.mention} がトーナメント次戦へ勝ち上がりました！！**"

            win_embed = discord.Embed(title="⚔️ 対人戦 決着！！", description=result_desc, color=0x2ECC71)
            return await interaction.response.edit_message(embed=win_embed, view=self)

        self.turn_idx = opp
        await interaction.response.edit_message(embed=self.build_embed(msg), view=self)

    @discord.ui.button(label="⚔️ スキル攻撃", style=discord.ButtonStyle.primary)
    async def p_skill(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.act(interaction, "skill")

    @discord.ui.button(label="🛡️ 鉄壁防御", style=discord.ButtonStyle.secondary)
    async def p_guard(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.act(interaction, "guard")

    @discord.ui.button(label="🔥 必殺奥義", style=discord.ButtonStyle.danger)
    async def p_ult(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.act(interaction, "ult")

    @discord.ui.button(label="☢️ 戦略核投下", style=discord.ButtonStyle.danger, row=1)
    async def p_nuke(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.act(interaction, "nuke")

class RankQueueCancelView(discord.ui.View):
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.user_id = user_id

    @discord.ui.button(label="❌ マッチング待機をキャンセル", style=discord.ButtonStyle.secondary)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ 本人のみキャンセルできます。", ephemeral=True)
        if RANK_QUEUE.get(self.guild_id) and RANK_QUEUE[self.guild_id].id == self.user_id:
            del RANK_QUEUE[self.guild_id]
        self.clear_items()
        await interaction.response.edit_message(content="🚫 ランクマッチの待機をキャンセルしました。", embed=None, view=self)

# ==========================================
# 5. 基地・ガチャ・運営神コンソール・大会募集UI
# ==========================================
class BaseUpgradeView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=180)
        self.user_id = user_id

    async def upgrade(self, interaction: discord.Interaction, col: str, label: str):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ 他の司令官の基地は操作できません。", ephemeral=True)
        u = get_user(self.user_id)
        lv = u[col]
        cost = 0 if self.user_id == OWNER_ID else lv * 5000
        if u["funds"] < cost:
            return await interaction.response.send_message(f"❌ 軍事資金不足！（必要：{cost:,} G）", ephemeral=True)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(f"UPDATE users SET funds = funds - ?, {col} = {col} + 1 WHERE user_id = ?", (cost, self.user_id))
        conn.commit()
        conn.close()
        power = calc_total_power(self.user_id)
        if isinstance(interaction.user, discord.Member):
            await sync_member_nickname(interaction.user, power)
        await interaction.response.send_message(f"🏗️ **{label}** を **Lv.{lv + 1}** に強化！（総戦力：`{power:,}`）", ephemeral=True)

    @discord.ui.button(label="🏢 司令部強化", style=discord.ButtonStyle.primary)
    async def btn_hq(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.upgrade(interaction, "base_hq", "最高司令部（HQ）")

    @discord.ui.button(label="🏭 軍需工場強化", style=discord.ButtonStyle.success)
    async def btn_factory(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.upgrade(interaction, "base_factory", "軍需工場")

    @discord.ui.button(label="🔬 核研究所強化", style=discord.ButtonStyle.danger)
    async def btn_nuke(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.upgrade(interaction, "base_nuke_lab", "戦略核研究所")

    @discord.ui.button(label="🛡️ 防空網強化", style=discord.ButtonStyle.secondary)
    async def btn_def(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.upgrade(interaction, "base_defense", "イージス防空システム")

    @discord.ui.button(label="💰 資源＆突破素材を回収", style=discord.ButtonStyle.success, row=1)
    async def btn_collect(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ 他の司令官の基地は操作できません。", ephemeral=True)
        u = get_user(self.user_id)
        now = datetime.now(JST)
        try:
            last = datetime.fromisoformat(u["last_collect"])
        except Exception:
            last = now - timedelta(hours=1)
        mins = max(1, int((now - last).total_seconds() // 60))
        earn_funds = min(1000000, mins * (u["base_factory"] * 300 + u["base_hq"] * 150))
        earn_gems = min(5000, max(200, (mins // 5) * 250))
        earn_parts = max(1, mins // 10)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE users SET funds = funds + ?, gems = gems + ?, mat_parts = mat_parts + ?, last_collect = ? WHERE user_id = ?",
                  (earn_funds, earn_gems, earn_parts, now.isoformat(), self.user_id))
        conn.commit()
        conn.close()
        await interaction.response.send_message(
            f"📦 基地から物資を回収しました！\n💰 資金：**+{earn_funds:,} G** / 💎 ダイヤ：**+{earn_gems:,} 個** / 🔩 精密パーツ：**+{earn_parts}個**",
            ephemeral=True
        )

class GachaView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=180)
        self.user_id = user_id

    async def pull_gacha(self, interaction: discord.Interaction, times: int, use_free_ten: bool = False):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ 他の司令官のガチャ画面です。", ephemeral=True)
        u = get_user(self.user_id)

        if use_free_ten:
            if u["free_ten_pull"] <= 0:
                return await interaction.response.send_message("❌ 初回無料10連はすでに使用済みです！", ephemeral=True)
            cost = 0
        else:
            # 運営もダイヤを消費する仕様（だからこそチート付与に意味がある！）
            cost = 500 * times
            if u["gems"] < cost:
                return await interaction.response.send_message(
                    f"❌ 機密ダイヤが不足しています！（必要：`{cost:,}` / 所持：`{u['gems']:,}`）\n※ `/story`（実在国進軍）や `/battle_bot`（Bot戦）でダイヤを稼げます！",
                    ephemeral=True
                )

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        if use_free_ten:
            c.execute("UPDATE users SET free_ten_pull = 0 WHERE user_id = ?", (self.user_id,))
        else:
            c.execute("UPDATE users SET gems = gems - ? WHERE user_id = ?", (cost, self.user_id))

        rarities = list(RARITY_CONFIG.keys())
        w_key = "fes" if FESTIVAL_ACTIVE else "weight"
        weights = [RARITY_CONFIG[r][w_key] for r in rarities]

        results = []
        best_card = None
        best_rank_idx = -1

        for _ in range(times):
            chosen_r = random.choices(rarities, weights=weights, k=1)
            c.execute("SELECT * FROM cards WHERE rarity = ?", (chosen_r,))
            pool = c.fetchall()
            if not pool:
                c.execute("SELECT * FROM cards")
                pool = c.fetchall()
            card = random.choice(pool)
            cid = card

            c.execute("SELECT count, max_level FROM user_cards WHERE user_id = ? AND card_id = ?", (self.user_id, cid))
            existing = c.fetchone()
            if not existing:
                c.execute(
                    "INSERT INTO user_cards (user_id, card_id, count, level, max_level, skill_lv) VALUES (?, ?, 1, 1, 20, 1)",
                    (self.user_id, cid)
                )
                note = "🆕 NEW!（上限Lv.20）"
            else:
                new_max = min(100, existing + 20)
                c.execute(
                    "UPDATE user_cards SET count = count + 1, max_level = ? WHERE user_id = ? AND card_id = ?",
                    (new_max, self.user_id, cid)
                )
                note = f"🔓 上限解放 → **Lv.{new_max}**" if new_max > existing else "✨ 上限Lv.100解放済"

            results.append((card, note))
            r_idx = rarities.index(card)
            if r_idx > best_rank_idx:
                best_rank_idx = r_idx
                best_card = card

        unlocked_msg = ""
        if best_card == "MR":
            c.execute("INSERT OR IGNORE INTO user_titles (user_id, title) VALUES (?, ?)", (self.user_id, "漆黒の覇王"))
            unlocked_msg = "\n🩸 **【極絶稀 0.001%降臨！！】特別異名【漆黒の覇王】を解放！**"
        elif best_card == "LR":
            c.execute("INSERT OR IGNORE INTO user_titles (user_id, title) VALUES (?, ?)", (self.user_id, "終末の設計者"))
            unlocked_msg = "\n✨ **【超絶稀 0.003%降臨！！】特別異名【終末の設計者】を解放！**"
        elif best_card == "UR":
            c.execute("INSERT OR IGNORE INTO user_titles (user_id, title) VALUES (?, ?)", (self.user_id, "核のボタンを押す者"))
            unlocked_msg = "\n🩷 **【極稀 0.01%降臨！！】特別異名【核のボタンを押す者】を解放！**"

        conn.commit()
        conn.close()

        power = calc_total_power(self.user_id)
        if isinstance(interaction.user, discord.Member):
            await sync_member_nickname(interaction.user, power)

        r_conf = RARITY_CONFIG[best_card]
        lines = [f"{RARITY_CONFIG[cd]['emoji']} **[{cd}] {cd}**｜{nt}" for cd, nt in results]

        embed = discord.Embed(
            title=f"🎰 機密軍事コンテナ開封結果（{times}連）" + (" 【🔥確率2倍フェス中】" if FESTIVAL_ACTIVE else ""),
            description="\n".join(lines) + unlocked_msg,
            color=r_conf["color"]
        )
        embed.add_field(
            name=f"🌟 最高排出：[{best_card}] {best_card}（{best_card}）",
            value=(
                f"⚔️ ATK:`{best_card:,}` / 🛡️ DEF:`{best_card:,}` / ⚡ SPD:`{best_card:,}`\n"
                f"🔹 **スキル【{best_card}】** / 🔥 **必殺技【{best_card}】**"
            ),
            inline=False
        )
        if best_card:
            embed.set_image(url=best_card)
        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="🎁 初回限定・無料10連", style=discord.ButtonStyle.success)
    async def pull_free(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.pull_gacha(interaction, 10, use_free_ten=True)

    @discord.ui.button(label="🎲 単発召集（500💎）", style=discord.ButtonStyle.primary)
    async def pull_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.pull_gacha(interaction, 1, use_free_ten=False)

    @discord.ui.button(label="🔥 10連召集（5,000💎）", style=discord.ButtonStyle.danger)
    async def pull_10(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.pull_gacha(interaction, 10, use_free_ten=False)
class AdminGodView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="💰 運営無限補給（資金/ダイヤ/核/全素材9999）", style=discord.ButtonStyle.success, row=0)
    async def god_supply(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message("❌ 運営専用権限です。", ephemeral=True)
        get_user(OWNER_ID)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            UPDATE users SET
                funds = funds + 100000000,
                gems = gems + 100000,
                nuke_count = nuke_count + 100,
                nuke_megaton = nuke_megaton + 50000,
                bonus_power = bonus_power + 100000000,
                mat_parts = mat_parts + 9999,
                mat_alloy = mat_alloy + 9999,
                mat_quantum = mat_quantum + 9999,
                mat_mythic = mat_mythic + 9999
            WHERE user_id = ?
        """, (OWNER_ID,))
        conn.commit()
        conn.close()
        power = calc_total_power(OWNER_ID)
        if isinstance(interaction.user, discord.Member):
            await sync_member_nickname(interaction.user, power)
        await interaction.response.send_message(f"👑 **運営神権限：無限物資＆全突破素材9999個を補充！**\n💥 総戦力：**`{power:,}`**", ephemeral=True)

    @discord.ui.button(label="🏰 基地全施設 Lv.99（MAX）", style=discord.ButtonStyle.primary, row=1)
    async def god_base_max(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message("❌ 運営専用権限です。", ephemeral=True)
        get_user(OWNER_ID)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE users SET base_hq = 99, base_factory = 99, base_nuke_lab = 99, base_defense = 99 WHERE user_id = ?", (OWNER_ID,))
        conn.commit()
        conn.close()
        await interaction.response.send_message("🏰 **マイ基地の全施設を Lv.99（限界突破MAX）へ引き上げました！**", ephemeral=True)

    @discord.ui.button(label="🩸 全MR・全20キャラ即時Lv.100＆Skill10召喚", style=discord.ButtonStyle.danger, row=1)
    async def god_summon_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message("❌ 運営専用権限です。", ephemeral=True)
        get_user(OWNER_ID)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id FROM cards")
        all_ids = [r[0] for r in c.fetchall()]
        for cid in all_ids:
            c.execute("""
                INSERT INTO user_cards (user_id, card_id, count, level, max_level, skill_lv, weapon_id)
                VALUES (?, ?, 10, 100, 100, 10, 6)
                ON CONFLICT(user_id, card_id) DO UPDATE SET count = 10, level = 100, max_level = 100, skill_lv = 10, weapon_id = 6
            """, (OWNER_ID, cid))
        c.execute("UPDATE users SET party_1 = 19, party_2 = 20, party_3 = 18 WHERE user_id = ?", (OWNER_ID,))
        conn.commit()
        conn.close()
        power = calc_total_power(OWNER_ID)
        await interaction.response.send_message(f"🩸 **MRを含む全{len(all_ids)}体を【Lv.100 MAX・Skill Lv.10・神話兵器装備】で召喚しました！**\n💥 総戦力：**`{power:,}`**", ephemeral=True)

    @discord.ui.button(label="🔥 ガチャ確率2倍フェス ON/OFF", style=discord.ButtonStyle.secondary, row=2)
    async def toggle_fes(self, interaction: discord.Interaction, button: discord.ui.Button):
        global FESTIVAL_ACTIVE
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message("❌ 運営専用権限です。", ephemeral=True)
        FESTIVAL_ACTIVE = not FESTIVAL_ACTIVE
        state = "🔥 **開催中（SSR〜MR排出率2倍！）**" if FESTIVAL_ACTIVE else "❄️ **終了（通常確率）**"
        await interaction.response.send_message(f"🎰 運営イベントスイッチ切替：{state}")

    @discord.ui.button(label="🔧 メンテナンスモード ON/OFF", style=discord.ButtonStyle.danger, row=2)
    async def toggle_maint(self, interaction: discord.Interaction, button: discord.ui.Button):
        global MAINTENANCE_MODE
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message("❌ 運営専用権限です。", ephemeral=True)
        MAINTENANCE_MODE = not MAINTENANCE_MODE
        if MAINTENANCE_MODE:
            await interaction.response.send_message("🚧 **【緊急メンテナンス開始】現在、運営以外のコマンド実行を一時停止しました。**")
        else:
            await interaction.response.send_message("✅ **【メンテナンス終了】サーバーを再開放しました！お詫び配布は `/maint_reward` で実行できます。**")

    @discord.ui.button(label="🌍 世界情勢バフ切替（好景気/戒厳令/通常）", style=discord.ButtonStyle.primary, row=3)
    async def cycle_world_buff(self, interaction: discord.Interaction, button: discord.ui.Button):
        global WORLD_BUFF
        if interaction.user.id != OWNER_ID:
            return await interaction.response.send_message("❌ 運営専用権限です。", ephemeral=True)
        modes = [
            "通常情勢（ボーナスなし）",
            "☀️ 軍需好景気（戦闘報酬ダイヤ＆資金2倍！）",
            "⛈️ 戒厳令発令（ドロップ突破素材3倍！）",
        ]
        idx = (modes.index(WORLD_BUFF) + 1) % len(modes) if WORLD_BUFF in modes else 0
        WORLD_BUFF = modes[idx]
        await interaction.response.send_message(f"🌍 **【世界情勢変動】現在の情勢：{WORLD_BUFF}**")

class TourneyJoinView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="⚔️ トーナメントにエントリーする", style=discord.ButtonStyle.success, custom_id="tourney_join_btn")
    async def join_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT title, status FROM tourney WHERE id = 1")
        row = c.fetchone()
        if not row or row[1] != "open":
            conn.close()
            return await interaction.response.send_message("❌ 現在エントリー受付中の大会はありません。", ephemeral=True)
        c.execute("INSERT OR REPLACE INTO tourney_entries (user_id, user_name) VALUES (?, ?)", (interaction.user.id, interaction.user.display_name))
        c.execute("SELECT user_name FROM tourney_entries")
        all_names = [r[0] for r in c.fetchall()]
        conn.commit()
        conn.close()
        await interaction.response.send_message(
            f"✅ **{interaction.user.display_name}** が大会にエントリーしました！（現在の参加者：**{len(all_names)}名**：{', '.join(all_names)}）"
        )
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

def check_maint(user_id: int) -> bool:
    return MAINTENANCE_MODE and user_id != OWNER_ID

@bot.tree.command(name="admin_god", description="【運営専用】創造主特権コンソールを開く")
async def cmd_admin_god(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("❌ 運営専用コマンドです。", ephemeral=True)
    embed = discord.Embed(
        title="👑 運営（創造主）専用・絶対特権コンソール",
        description=f"現在の情勢：**{WORLD_BUFF}**\nメンテナンス：**{'🚧 メンテ中' if MAINTENANCE_MODE else '✅ 稼働中'}**",
        color=0x8B0000
    )
    await interaction.response.send_message(embed=embed, view=AdminGodView(), ephemeral=True)

@bot.tree.command(name="maint_reward", description="【運営専用】全司令官にメンテお詫び（ダイヤ・資金・突破素材）を一斉配布")
@app_commands.describe(gems="ダイヤ数", funds="資金", parts="精密パーツ", alloy="超合金コア", reason="お詫び内容")
async def cmd_maint_reward(interaction: discord.Interaction, gems: int = 3000, funds: int = 50000, parts: int = 10, alloy: int = 3, reason: str = "メンテナンスご協力のお礼"):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("❌ 運営専用コマンドです。", ephemeral=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET gems = gems + ?, funds = funds + ?, mat_parts = mat_parts + ?, mat_alloy = mat_alloy + ?",
              (gems, funds, parts, alloy))
    conn.commit()
    conn.close()
    embed = discord.Embed(
        title="🎁【運営からの特別お詫び・配布物資】",
        description=f"**{reason}**\n💎 ダイヤ：**+{gems:,} 個** / 💰 資金：**+{funds:,} G**\n🔩 パーツ：**+{parts}個** / ⚙️ 超合金：**+{alloy}個**",
        color=0xF1C40F
    )
    await interaction.response.send_message(embed=embed)
@bot.tree.command(name="god_edit", description="【運営専用】自分の戦力・資金・ダイヤ・階級・異名を自由改変する")
@app_commands.describe(field="power / funds / gems / nuke / rp / story / rank / title", value="設定する値")
async def cmd_god_edit(interaction: discord.Interaction, field: str, value: str):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("❌ 運営専用コマンドです。", ephemeral=True)
    get_user(OWNER_ID)
    f = field.lower().strip()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if f == "power":
        c.execute("UPDATE users SET bonus_power = ? WHERE user_id = ?", (int(value), OWNER_ID))
    elif f == "funds":
        c.execute("UPDATE users SET funds = ? WHERE user_id = ?", (int(value), OWNER_ID))
    elif f == "gems":
        c.execute("UPDATE users SET gems = ? WHERE user_id = ?", (int(value), OWNER_ID))
    elif f == "nuke":
        c.execute("UPDATE users SET nuke_count = ? WHERE user_id = ?", (int(value), OWNER_ID))
    elif f == "rp":
        c.execute("UPDATE users SET rp = ? WHERE user_id = ?", (int(value), OWNER_ID))
    elif f == "story":
        c.execute("UPDATE users SET story_stage = ? WHERE user_id = ?", (int(value), OWNER_ID))
    elif f == "rank":
        c.execute("UPDATE users SET custom_rank = ? WHERE user_id = ?", (value, OWNER_ID))
    elif f == "title":
        c.execute("UPDATE users SET equipped_title = ? WHERE user_id = ?", (value, OWNER_ID))
    else:
        conn.close()
        return await interaction.response.send_message("❌ 無効な項目です。", ephemeral=True)
    conn.commit()
    conn.close()
    if isinstance(interaction.user, discord.Member):
        await sync_member_nickname(interaction.user, calc_total_power(OWNER_ID))
    await interaction.response.send_message(f"👑 **改変完了**：`{field}` → **`{value}`**", ephemeral=True)

@bot.tree.command(name="god_edict", description="【運営専用】他プレイヤーへ恩恵または粛清を下す")
@app_commands.describe(target="対象ユーザー", mode="reward（恩恵） または purge（粛清）", amount="変動値")
async def cmd_god_edict(interaction: discord.Interaction, target: discord.Member, mode: str, amount: int = 1000000):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("❌ 運営専用コマンドです。", ephemeral=True)
    get_user(target.id)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if mode.lower() == "reward":
        c.execute("UPDATE users SET funds = funds + ?, gems = gems + 10000, bonus_power = bonus_power + ? WHERE user_id = ?", (amount, amount, target.id))
        msg = f"👑 **【運営の恩寵】** {target.mention} に資金 `+{amount:,} G`・ダイヤ `+10,000個`・戦力 `+{amount:,}` 授与！"
        color = 0xF1C40F
    else:
        c.execute("UPDATE users SET funds = 0, nuke_count = 0, bonus_power = MAX(0, bonus_power - ?) WHERE user_id = ?", (amount, target.id))
        msg = f"⚡ **【運営の粛清】** {target.mention} は資金・核・戦力 `-{amount:,}` を没収されました！"
        color = 0xFF0000
    conn.commit()
    conn.close()
    await sync_member_nickname(target, calc_total_power(target.id))
    await interaction.response.send_message(embed=discord.Embed(title="⚖️ 最高統帥の布告", description=msg, color=color))
@bot.tree.command(name="create_code", description="【運営専用】シリアルコード（合言葉）を発行する")
@app_commands.describe(code="合言葉（例：PAYPAY10000）", gems="もらえるダイヤ数", funds="もらえる資金")
async def cmd_create_code(interaction: discord.Interaction, code: str, gems: int = 3000, funds: int = 30000):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("❌ 運営専用コマンドです。", ephemeral=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO promo_codes (code, gems, funds, mat_parts, mat_alloy) VALUES (?, ?, ?, 5, 2)",
              (code.upper().strip(), gems, funds))
    conn.commit()
    conn.close()
    await interaction.response.send_message(f"🎟️ シリアルコード **`{code.upper().strip()}`** を発行！（報酬：`{gems:,}💎` / `{funds:,}G`）", ephemeral=True)

@bot.tree.command(name="code", description="運営が発表したシリアルコードを入力して報酬を受け取る")
@app_commands.describe(code="シリアルコードを入力")
async def cmd_use_code(interaction: discord.Interaction, code: str):
    if check_maint(interaction.user.id):
        return await interaction.response.send_message("🚧 現在メンテナンス中です。", ephemeral=True)
    get_user(interaction.user.id)
    cd = code.upper().strip()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT gems, funds, mat_parts, mat_alloy FROM promo_codes WHERE code = ?", (cd,))
    row = c.fetchone()
    if not row:
        conn.close()
        return await interaction.response.send_message("❌ 無効なシリアルコードです。", ephemeral=True)
    c.execute("SELECT 1 FROM used_codes WHERE user_id = ? AND code = ?", (interaction.user.id, cd))
    if c.fetchone():
        conn.close()
        return await interaction.response.send_message("❌ 既に使用済みです。", ephemeral=True)
    c.execute("INSERT INTO used_codes (user_id, code) VALUES (?, ?)", (interaction.user.id, cd))
    c.execute("UPDATE users SET gems = gems + ?, funds = funds + ?, mat_parts = mat_parts + ?, mat_alloy = mat_alloy + ? WHERE user_id = ?",
              (row, row, row, row, interaction.user.id))
    conn.commit()
    conn.close()
    await interaction.response.send_message(f"🎁 **シリアルコード特典獲得！** ダイヤ `+{row:,}💎` / 資金 `+{row:,}G` を受け取りました！", ephemeral=True)

@bot.tree.command(name="create_base_room", description="自分と運営（創造主）だけが入れる個別プライベート基地チャンネルを作成する")
async def cmd_create_base_room(interaction: discord.Interaction):
    if check_maint(interaction.user.id):
        return await interaction.response.send_message("🚧 現在メンテナンス中です。", ephemeral=True)
    guild = interaction.guild
    if not guild:
        return
    u = get_user(interaction.user.id)
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
    }
    owner_member = guild.get_member(OWNER_ID)
    if owner_member:
        overwrites[owner_member] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
    ch_name = f"🔒｜{interaction.user.name}の極秘基地"[:32]
    ch = await guild.create_text_channel(name=ch_name, overwrites=overwrites)
    embed = discord.Embed(
        title=f"🏰 {u['base_name']} — 個別極秘司令室",
        description=f"{interaction.user.mention} 専用のプライベート軍事基地です。（他メンバー非公開・運営視察可）",
        color=0x2C3E50
    )
    await ch.send(embed=embed, view=BaseUpgradeView(interaction.user.id))
    await interaction.response.send_message(f"✅ 専用のプライベート基地チャンネル {ch.mention} を建設しました！", ephemeral=True)
@bot.tree.command(name="train", description="資金と突破素材を使ってユニットのレベルを上げる（同キャラ被りで最大Lv.100解放）")
@app_commands.describe(card_id="強化したいユニットID（/dexで確認）", levels="上げるレベル数")
async def cmd_train(interaction: discord.Interaction, card_id: int, levels: int = 1):
    if check_maint(interaction.user.id):
        return await interaction.response.send_message("🚧 現在メンテナンス中です。", ephemeral=True)
    if levels < 1:
        return await interaction.response.send_message("❌ 1以上の数値を指定してください。", ephemeral=True)
    u = get_user(interaction.user.id)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT rarity, name FROM cards WHERE id = ?", (card_id,))
    card = c.fetchone()
    c.execute("SELECT level, max_level FROM user_cards WHERE user_id = ? AND card_id = ?", (interaction.user.id, card_id))
    uc = c.fetchone()
    if not card or not uc:
        conn.close()
        return await interaction.response.send_message("❌ そのユニットを所持していません。", ephemeral=True)

    cur_lv, max_lv = uc[0], uc[1]
    if cur_lv >= max_lv:
        conn.close()
        return await interaction.response.send_message(
            f"⚠️ 現在のレベル上限 **Lv.{max_lv}** に達しています！\nガチャで同じキャラが被ると上限が **+20ずつ（最大Lv.100）** 解放されます！",
            ephemeral=True
        )
    actual_add = min(levels, max_lv - cur_lv)
    mat_col = RARITY_CONFIG[card[0]]["mat"]
    cost_funds = actual_add * 2000
    cost_mat = actual_add
    if interaction.user.id != OWNER_ID and (u["funds"] < cost_funds or u[mat_col] < cost_mat):
        conn.close()
        return await interaction.response.send_message(
            f"❌ 育成資源が不足しています！（必要：資金 `{cost_funds:,} G` ＆ {MAT_NAMES[mat_col]} `×{cost_mat}個`）",
            ephemeral=True
        )
    if interaction.user.id != OWNER_ID:
        c.execute(f"UPDATE users SET funds = funds - ?, {mat_col} = {mat_col} - ? WHERE user_id = ?", (cost_funds, cost_mat, interaction.user.id))
    c.execute("UPDATE user_cards SET level = ? WHERE user_id = ? AND card_id = ?", (cur_lv + actual_add, interaction.user.id, card_id))
    conn.commit()
    conn.close()
    power = calc_total_power(interaction.user.id)
    await interaction.response.send_message(
        f"⬆️ **レベルアップ完了！** **[{card[0]}] {card[1]}** が **Lv.{cur_lv} → Lv.{cur_lv + actual_add} / {max_lv}** に成長しました！（総戦力：`{power:,}`）"
    )

@bot.tree.command(name="skill_up", description="突破素材を使ってユニットのスキル＆必殺奥義レベルを強化する（最大Lv.10）")
@app_commands.describe(card_id="強化したいユニットID")
async def cmd_skill_up(interaction: discord.Interaction, card_id: int):
    if check_maint(interaction.user.id):
        return await interaction.response.send_message("🚧 現在メンテナンス中です。", ephemeral=True)
    u = get_user(interaction.user.id)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT rarity, name FROM cards WHERE id = ?", (card_id,))
    card = c.fetchone()
    c.execute("SELECT skill_lv FROM user_cards WHERE user_id = ? AND card_id = ?", (interaction.user.id, card_id))
    uc = c.fetchone()
    if not card or not uc:
        conn.close()
        return await interaction.response.send_message("❌ そのユニットを所持していません。", ephemeral=True)
    slv = uc[0]
    if slv >= 10:
        conn.close()
        return await interaction.response.send_message("✨ すでに **Skill Lv.10（MAX）** です！", ephemeral=True)
    mat_col = RARITY_CONFIG[card[0]]["mat"]
    req_mat = slv * 2
    if interaction.user.id != OWNER_ID and u[mat_col] < req_mat:
        conn.close()
        return await interaction.response.send_message(f"❌ 素材不足！（必要：{MAT_NAMES[mat_col]} `×{req_mat}個`）", ephemeral=True)
    if interaction.user.id != OWNER_ID:
        c.execute(f"UPDATE users SET {mat_col} = {mat_col} - ? WHERE user_id = ?", (req_mat, interaction.user.id))
    c.execute("UPDATE user_cards SET skill_lv = skill_lv + 1 WHERE user_id = ? AND card_id = ?", (interaction.user.id, card_id))
    conn.commit()
    conn.close()
    await interaction.response.send_message(f"🔥 **スキル強化成功！** **[{card[0]}] {card[1]}** のスキルが **Skill Lv.{slv + 1}** になりました！")

@bot.tree.command(name="party", description="バトルに出撃する主力3部隊（前衛・中衛・後衛）を編成する")
@app_commands.describe(slot1="前衛カードID", slot2="中衛カードID", slot3="後衛カードID")
async def cmd_party(interaction: discord.Interaction, slot1: int, slot2: int, slot3: int):
    if check_maint(interaction.user.id):
        return await interaction.response.send_message("🚧 現在メンテナンス中です。", ephemeral=True)
    get_user(interaction.user.id)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for cid in (slot1, slot2, slot3):
        c.execute("SELECT 1 FROM user_cards WHERE user_id = ? AND card_id = ?", (interaction.user.id, cid))
        if not c.fetchone() and interaction.user.id != OWNER_ID:
            conn.close()
            return await interaction.response.send_message(f"❌ カードID `{cid}` は未所持です！`/dex` で所持IDを確認してください。", ephemeral=True)
    c.execute("UPDATE users SET party_1 = ?, party_2 = ?, party_3 = ? WHERE user_id = ?", (slot1, slot2, slot3, interaction.user.id))
    conn.commit()
    conn.close()
    p = get_party_combat_stats(interaction.user.id)
    names = " / ".join([f"[{m['rarity']}] {m['name']}(Lv.{m['lv']})" for m in p["members"]])
    await interaction.response.send_message(f"⚔️ **主力3部隊を編成しました！**\n編成：{names}\n総ATK：`{p['atk']:,}` / 総DEF：`{p['def']:,}` / 総HP：`{p['max_hp']:,}`")

@bot.tree.command(name="equip", description="ユニットに専用兵器を装備して能力を大幅強化する")
@app_commands.describe(card_id="装備させるカードID", weapon_id="1:ライフル / 2:重装甲 / 3:推進機 / 4:核ポッド / 5:軌道衛星 / 6:神話魔導機装")
async def cmd_equip(interaction: discord.Interaction, card_id: int, weapon_id: int):
    if check_maint(interaction.user.id):
        return await interaction.response.send_message("🚧 現在メンテナンス中です。", ephemeral=True)
    if weapon_id not in WEAPONS:
        return await interaction.response.send_message("❌ weapon_id は 1〜6 を指定してください。", ephemeral=True)
    if weapon_id == 6 and interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("❌ 【神話兵器】は運営（創造主）専用装備です。", ephemeral=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE user_cards SET weapon_id = ? WHERE user_id = ? AND card_id = ?", (weapon_id, interaction.user.id, card_id))
    updated = c.rowcount
    conn.commit()
    conn.close()
    if updated == 0:
        return await interaction.response.send_message("❌ そのカードIDを所持していません。", ephemeral=True)
    w_name, _, w_desc = WEAPONS[weapon_id]
    await interaction.response.send_message(f"🔫 カードID:`{card_id}` に専用兵器 **【{w_name}】**（{w_desc}）を装備しました！")
@bot.tree.command(name="story", description="【メインストーリー全999ステージ】実在国の軍事力に挑み世界制覇を進める")
async def cmd_story(interaction: discord.Interaction):
    if check_maint(interaction.user.id):
        return await interaction.response.send_message("🚧 現在メンテナンス中です。", ephemeral=True)
    u = get_user(interaction.user.id)
    st = min(999, u["story_stage"])
    country_name, flag, power_mult = REAL_COUNTRIES[(st - 1) % len(REAL_COUNTRIES)]
    loop_num = (st - 1) // len(REAL_COUNTRIES) + 1

    scale = (st ** 1.35) * power_mult
    e_hp = int(3500 + scale * 420)
    e_atk = int(420 + scale * 55)
    e_def = int(220 + scale * 30)
    r_gems = min(5000, 500 + (st // 5) * 50)
    r_funds = int(12000 + st * 800)
    mat = "mat_parts" if st < 150 else ("mat_alloy" if st < 450 else ("mat_quantum" if st < 800 else "mat_mythic"))

    enemy_title = f"{flag} Stage.{st}/999：{country_name}（第{loop_num}防衛線）"
    view = TacticalBattleView(
        interaction.user.id, enemy_title, e_hp, e_atk, e_def,
        r_gems, r_funds, 0, mat, is_rank=False, story_clear_stage=st
    )
    await interaction.response.send_message(
        embed=view.build_embed(f"🌍 **メインストーリー Stage.{st} / 999 開戦！**\n敵国：**{flag} {country_name}** へ進軍を開始しました！"),
        view=view
    )

@bot.tree.command(name="battle_bot", description="【Bot戦】難易度を選んで敵部隊と戦術バトル（ダイヤ＆突破素材稼ぎ）")
@app_commands.describe(difficulty="1:初級(500💎) / 2:中級(1000💎) / 3:上級(1800💎) / 4:超級(3000💎) / 5:終末級(5000💎)")
async def cmd_battle_bot(interaction: discord.Interaction, difficulty: int = 1):
    if check_maint(interaction.user.id):
        return await interaction.response.send_message("🚧 現在メンテナンス中です。", ephemeral=True)
    stages = {
        1: ("反乱軍・偵察小隊",       4000,    450,   200,   500,  10000,  "mat_parts"),
        2: ("帝国第4機甲大隊",        18000,   1600,  800,   1000, 30000,  "mat_parts"),
        3: ("浮遊要塞・戦略航空艦隊", 75000,   5500,  2800,  1800, 80000,  "mat_alloy"),
        4: ("軌道防衛・サイバー軍団", 320000,  18000, 9000,  3000, 200000, "mat_quantum"),
        5: ("終末兵器・虚無の機械神", 1500000, 65000, 30000, 5000, 500000, "mat_mythic"),
    }
    st = stages.get(difficulty, stages)
    view = TacticalBattleView(interaction.user.id, st, st, st, st, st, st, 0, st, is_rank=False)
    await interaction.response.send_message(embed=view.build_embed(f"🚨 **Bot戦（難易度Lv.{difficulty}）開戦！** 戦術コマンドを選択せよ！"), view=view)

async def start_or_queue_rank_match(interaction: discord.Interaction):
    if check_maint(interaction.user.id):
        return await interaction.response.send_message("🚧 現在メンテナンス中です。", ephemeral=True)
    if not interaction.guild:
        return
    gid = interaction.guild.id
    get_user(interaction.user.id)
    waiting = RANK_QUEUE.get(gid)

    if waiting is None:
        RANK_QUEUE[gid] = interaction.user
        embed = discord.Embed(
            title="📡 ランクマッチ 対戦相手マッチング中…",
            description=f"**待機中プレイヤー：{interaction.user.mention}**\n他のプレイヤーが `/rank_match`（またはパネルのランク戦ボタン）を押すと即座に開戦します！",
            color=0x3498DB
        )
        return await interaction.response.send_message(embed=embed, view=RankQueueCancelView(gid, interaction.user.id))

    if waiting.id == interaction.user.id:
        return await interaction.response.send_message("⏳ すでにマッチング待機中です！他のプレイヤーの参加を待っています。", ephemeral=True)

    del RANK_QUEUE[gid]
    view = PvPTourneyBattleView(waiting, interaction.user, is_rank_match=True)
    await interaction.response.send_message(
        content=f"🚨 **ランクマッチ成立！！** {waiting.mention} 🆚 {interaction.user.mention}",
        embed=view.build_embed(f"🏅 **対人ランク戦 開戦！** 先攻は {waiting.mention} です！"),
        view=view
    )

@bot.tree.command(name="rank_match", description="【対人ランク戦】他のプレイヤーと自動マッチングしてRPを奪い合う")
async def cmd_rank_match(interaction: discord.Interaction):
    await start_or_queue_rank_match(interaction)


@bot.tree.command(name="challenge_god", description="【下剋上挑戦】序列第0位の運営（創造主）に反逆戦を挑む")
async def cmd_challenge_god(interaction: discord.Interaction):
    if check_maint(interaction.user.id):
        return await interaction.response.send_message("🚧 現在メンテナンス中です。", ephemeral=True)
    god_stats = get_party_combat_stats(OWNER_ID)
    view = TacticalBattleView(
        interaction.user.id, "👑 創世の絶対最高統帥（運営）",
        god_stats["max_hp"], god_stats["atk"], god_stats["def"],
        50000, 10000000, 500, "mat_mythic", is_rank=True
    )
    await interaction.response.send_message(embed=view.build_embed("⚡ **【緊急布告】運営（創造主）への反逆クーデター戦が開戦！！**"), view=view)
@bot.tree.command(name="tourney_open", description="【運営専用】PayPay優勝賞金トーナメント大会の参加募集を開始する")
@app_commands.describe(title="大会タイトル（例：第1回 覇王決定戦・優勝賞金PayPay 10,000円）")
async def cmd_tourney_open(interaction: discord.Interaction, title: str = "第1回 覇王決定トーナメント（優勝賞金：PayPay 10,000円）"):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("❌ 運営専用コマンドです。", ephemeral=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM tourney_entries")
    c.execute("INSERT OR REPLACE INTO tourney (id, title, status, bracket_text) VALUES (1, ?, 'open', '')", (title,))
    conn.commit()
    conn.close()
    embed = discord.Embed(
        title=f"🏆【公式大会開催】{title}",
        description="下の「⚔️ トーナメントにエントリーする」ボタンを押して参加登録せよ！\n集まり次第、運営が対戦組み合わせを発表します！",
        color=0xF1C40F
    )
    await interaction.response.send_message(embed=embed, view=TourneyJoinView())

@bot.tree.command(name="tourney_start", description="【運営専用】募集を締め切り、勝ち上がりトーナメント対戦表を自動生成する")
async def cmd_tourney_start(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("❌ 運営専用コマンドです。", ephemeral=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT title FROM tourney WHERE id = 1")
    t_row = c.fetchone()
    c.execute("SELECT user_id, user_name FROM tourney_entries")
    entries = c.fetchall()
    if len(entries) < 2:
        conn.close()
        return await interaction.response.send_message("❌ 参加者が2名以上必要です！", ephemeral=True)
    random.shuffle(entries)
    lines = []
    for i in range(0, len(entries), 2):
        if i + 1 < len(entries):
            lines.append(f"🔥 **第{(i//2)+1}試合**：<@{entries[i]}> 🆚 <@{entries[i+1]}>")
        else:
            lines.append(f"🎫 **シード枠（不戦勝）**：<@{entries[i]}>")
    bracket = "\n".join(lines)
    c.execute("UPDATE tourney SET status = 'running', bracket_text = ? WHERE id = 1", (bracket,))
    conn.commit()
    conn.close()
    embed = discord.Embed(
        title=f"⚔️ {t_row if t_row else '公式トーナメント'} — 対戦カード決定！",
        description=f"{bracket}\n\n👉 対戦相手をメンションして `/tourney_battle @相手` で試合を開始してください！",
        color=0xE74C3C
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="tourney_battle", description="【大会用】対戦相手とリアルタイム対人コマンドバトルを行う")
@app_commands.describe(opponent="対戦相手のメンバー")
async def cmd_tourney_battle(interaction: discord.Interaction, opponent: discord.Member):
    if opponent.id == interaction.user.id or opponent.bot:
        return await interaction.response.send_message("❌ 有効な対戦相手を指定してください。", ephemeral=True)
    view = PvPTourneyBattleView(interaction.user, opponent)
    await interaction.response.send_message(
        embed=view.build_embed(f"🚨 **公式トーナメント対人戦 開戦！**\n{interaction.user.mention} 🆚 {opponent.mention}"),
        view=view
    )

@bot.tree.command(name="tourney_champion", description="【運営専用】トーナメント優勝者を確定し特別王者異名を授与する")
@app_commands.describe(winner="優勝したメンバー", award_title="授与する特別異名")
async def cmd_tourney_champion(interaction: discord.Interaction, winner: discord.Member, award_title: str = "第1回覇王トーナメント王者"):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("❌ 運営専用コマンドです。", ephemeral=True)
    get_user(winner.id)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE tourney SET status = 'closed' WHERE id = 1")
    c.execute("INSERT OR IGNORE INTO user_titles (user_id, title) VALUES (?, ?)", (winner.id, award_title))
    c.execute("UPDATE users SET equipped_title = ?, gems = gems + 10000 WHERE user_id = ?", (award_title, winner.id))
    conn.commit()
    conn.close()
    await sync_member_nickname(winner, calc_total_power(winner.id))
    embed = discord.Embed(
        title="👑🎉 公式トーナメント 優勝者決定！！ 🎉👑",
        description=(
            f"激闘を制した優勝者は **{winner.mention}** です！！\n"
            f"🎖️ 限定異名 **【{award_title}】** ＆ 💎 ダイヤ `10,000個` を授与しました！\n"
            f"💰 優勝賞金（PayPay）は運営よりDMにて直接贈呈されます！"
        ),
        color=0xF1C40F
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="spawn_boss", description="【運営専用】ワールドレイドボスをチャンネルに緊急召喚する")
@app_commands.describe(boss_name="ボス名", hp="ボスの最大HP", image_url="ボスの画像またはGIFのURL（任意）")
async def cmd_spawn_boss(interaction: discord.Interaction, boss_name: str = "超巨大終末機械神・オメガ", hp: int = 50000000, image_url: str = ""):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("❌ 運営専用コマンドです。", ephemeral=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO raid_boss (id, name, max_hp, current_hp, image_url, active) VALUES (1, ?, ?, ?, ?, 1)",
              (boss_name, hp, hp, image_url.strip()))
    conn.commit()
    conn.close()
    embed = discord.Embed(
        title=f"🚨【緊急ワールドレイド警報】{boss_name} 襲来！！",
        description=f"総HP：**`{hp:,}`**\n全司令官は `/raid_attack` で総攻撃を行い討伐せよ！",
        color=0xFF0000
    )
    if image_url.strip():
        embed.set_image(url=image_url.strip())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="raid_attack", description="開催中のワールドレイドボスへ総攻撃を行う")
async def cmd_raid_attack(interaction: discord.Interaction):
    if check_maint(interaction.user.id):
        return await interaction.response.send_message("🚧 現在メンテナンス中です。", ephemeral=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, max_hp, current_hp, image_url, active FROM raid_boss WHERE id = 1")
    boss = c.fetchone()
    if not boss or boss == 0:
        conn.close()
        return await interaction.response.send_message("現在出現中のレイドボスはいません。", ephemeral=True)
    p = get_party_combat_stats(interaction.user.id)
    dmg = p["atk"] * 3 + random.randint(1000, 10000)
    new_hp = max(0, boss - dmg)
    if new_hp == 0:
        c.execute("UPDATE raid_boss SET current_hp = 0, active = 0 WHERE id = 1")
        c.execute("UPDATE users SET gems = gems + 10000, mat_mythic = mat_mythic + 2 WHERE user_id = ?", (interaction.user.id,))
        res_msg = f"🎉 **トドメの一撃！！{boss} を完全撃破！！**\n報酬：💎 ダイヤ `+10,000個` ＆ 🩸 覇王核 `+2個` 獲得！"
    else:
        c.execute("UPDATE raid_boss SET current_hp = ? WHERE id = 1", (new_hp,))
        c.execute("UPDATE users SET gems = gems + 500 WHERE user_id = ?", (interaction.user.id,))
        res_msg = f"⚔️ {interaction.user.mention} の総攻撃！**`{dmg:,}`** ダメージ！\n残りHP：**`{new_hp:,}`** / `{boss:,}`（参加報酬 +500💎）"
    conn.commit()
    conn.close()
    embed = discord.Embed(title=f"🔥 レイドボス戦：{boss}", description=res_msg, color=0xE67E22)
    if boss:
        embed.set_image(url=boss)
    await interaction.response.send_message(embed=embed)
@bot.tree.command(name="status", description="司令官の階級・序列・異名・総戦力・進行度・突破素材を表示")
async def cmd_status(interaction: discord.Interaction):
    if check_maint(interaction.user.id):
        return await interaction.response.send_message("🚧 現在メンテナンス中です。", ephemeral=True)
    u = get_user(interaction.user.id)
    power = calc_total_power(interaction.user.id)
    rank_info, _ = get_rank_info(interaction.user.id, power)
    pvp_str = get_pvp_tier(interaction.user.id, u["rp"])
    order_str = "👑 序列 第0位（運営・規格外）" if interaction.user.id == OWNER_ID else f"進行度 Stage.{u['story_stage']}/999"

    if isinstance(interaction.user, discord.Member):
        await sync_member_nickname(interaction.user, power)

    embed = discord.Embed(
        title=f"{rank_info[2]} 最高司令部 個人戦績カード",
        description=f"**司令官：{interaction.user.mention}**\n**異名：【{u['equipped_title']}】**",
        color=0x8B0000 if interaction.user.id == OWNER_ID else 0xE74C3C
    )
    embed.add_field(name="🎖️ 階級", value=f"**{rank_info[2]} {rank_info[1]}**", inline=True)
    embed.add_field(name="🌍 制覇進捗", value=f"**{order_str}**", inline=True)
    embed.add_field(name="⚔️ 総戦力", value=f"**`{power:,}`**", inline=True)
    embed.add_field(name="🏅 ランク戦階級", value=f"**{pvp_str}**（`{u['rp']:,} RP`）", inline=True)
    embed.add_field(name="☢️ 保有戦略核", value=f"**{u['nuke_count']}発**（`{u['nuke_megaton']:,} Mt`）", inline=True)
    embed.add_field(name="💰 資金 / 💎 ダイヤ", value=f"`{u['funds']:,} G` / `{u['gems']:,} 💎`", inline=True)
    embed.add_field(
        name="📦 所持突破素材",
        value=f"🔩 パーツ:`{u['mat_parts']}` / ⚙️ 超合金:`{u['mat_alloy']}` / 💠 量子:`{u['mat_quantum']}` / 🩸 覇王核:`{u['mat_mythic']}`",
        inline=False
    )
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="base", description="マイ基地の施設レベル確認・強化・資源回収")
async def cmd_base(interaction: discord.Interaction):
    if check_maint(interaction.user.id):
        return await interaction.response.send_message("🚧 現在メンテナンス中です。", ephemeral=True)
    u = get_user(interaction.user.id)
    embed = discord.Embed(
        title=f"🏰 {u['base_name']}（BASE STATUS）",
        description="各施設を強化して基礎戦力と生産力を引き上げろ！",
        color=0x2C3E50
    )
    embed.add_field(name=f"🏢 最高司令部 Lv.{u['base_hq']}", value=f"強化費：`{0 if interaction.user.id == OWNER_ID else u['base_hq']*5000:,} G`", inline=True)
    embed.add_field(name=f"🏭 軍需工場 Lv.{u['base_factory']}", value=f"強化費：`{0 if interaction.user.id == OWNER_ID else u['base_factory']*5000:,} G`", inline=True)
    embed.add_field(name=f"🔬 核研究所 Lv.{u['base_nuke_lab']}", value=f"強化費：`{0 if interaction.user.id == OWNER_ID else u['base_nuke_lab']*5000:,} G`", inline=True)
    embed.add_field(name=f"🛡️ 防空システム Lv.{u['base_defense']}", value=f"強化費：`{0 if interaction.user.id == OWNER_ID else u['base_defense']*5000:,} G`", inline=True)
    base_img = get_effect_url("base")
    if base_img:
        embed.set_image(url=base_img)
    await interaction.response.send_message(embed=embed, view=BaseUpgradeView(interaction.user.id))

@bot.tree.command(name="base_name", description="マイ基地の名前を自由に命名する")
@app_commands.describe(name="新しい基地の名前")
async def cmd_base_name(interaction: discord.Interaction, name: str):
    if check_maint(interaction.user.id):
        return await interaction.response.send_message("🚧 現在メンテナンス中です。", ephemeral=True)
    get_user(interaction.user.id)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET base_name = ? WHERE user_id = ?", (name[:30], interaction.user.id))
    conn.commit()
    conn.close()
    await interaction.response.send_message(f"🏰 マイ基地の名称を **【{name[:30]}】** に変更しました！")

@bot.tree.command(name="expedition", description="控え部隊を極秘遠征へ派遣し、突破素材とダイヤを持ち帰らせる")
async def cmd_expedition(interaction: discord.Interaction):
    if check_maint(interaction.user.id):
        return await interaction.response.send_message("🚧 現在メンテナンス中です。", ephemeral=True)
    u = get_user(interaction.user.id)
    now = datetime.now(JST)
    if u["expedition_end"]:
        end_dt = datetime.fromisoformat(u["expedition_end"])
        if now < end_dt and interaction.user.id != OWNER_ID:
            rem = int((end_dt - now).total_seconds() // 60) + 1
            return await interaction.response.send_message(f"🛰️ 控え部隊は極秘遠征中です！（帰還まであと約 **{rem}分**）", ephemeral=True)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE users SET expedition_end = '', gems = gems + 1000, mat_parts = mat_parts + 3, mat_alloy = mat_alloy + 1 WHERE user_id = ?", (interaction.user.id,))
        conn.commit()
        conn.close()
        return await interaction.response.send_message("🎖️ **極秘遠征部隊が帰還！** 💎 ダイヤ `+1,000個` / 🔩 パーツ `+3個` / ⚙️ 超合金 `+1個` 獲得！")

    next_end = (now + timedelta(minutes=30)).isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET expedition_end = ? WHERE user_id = ?", (next_end, interaction.user.id))
    conn.commit()
    conn.close()
    await interaction.response.send_message("🚀 **控え部隊を極秘遠征へ派遣しました！**（30分後に再度 `/expedition` で回収できます）")

@bot.tree.command(name="nuke_build", description="戦略核ミサイルを開発・配備する")
async def cmd_nuke_build(interaction: discord.Interaction):
    if check_maint(interaction.user.id):
        return await interaction.response.send_message("🚧 現在メンテナンス中です。", ephemeral=True)
    u = get_user(interaction.user.id)
    cost = 0 if interaction.user.id == OWNER_ID else 25000
    if u["funds"] < cost:
        return await interaction.response.send_message(f"❌ 戦略核の開発には `{cost:,} G` が必要です！", ephemeral=True)
    megaton = u["base_nuke_lab"] * 50
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET funds = funds - ?, nuke_count = nuke_count + 1, nuke_megaton = nuke_megaton + ? WHERE user_id = ?",
              (cost, megaton, interaction.user.id))
    conn.commit()
    conn.close()
    power = calc_total_power(interaction.user.id)
    embed = discord.Embed(title="☢️ 戦略核ミサイル 配備完了！", description=f"核弾頭（**{megaton} Mt**）を配備！総戦力：**`{power:,}`**", color=0xC0392B)
    nuke_img = get_effect_url("nuke")
    if nuke_img:
        embed.set_image(url=nuke_img)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="gacha", description="全8レアリティ（C〜MR）軍事・将軍＆超兵器ガチャを開く（単発500💎）")
async def cmd_gacha(interaction: discord.Interaction):
    if check_maint(interaction.user.id):
        return await interaction.response.send_message("🚧 現在メンテナンス中です。", ephemeral=True)
    u = get_user(interaction.user.id)
    free_txt = "🎁 **初回限定・無料10連チケット：残り1回！**\n" if u["free_ten_pull"] > 0 else ""
    embed = discord.Embed(
        title="🎰 最高機密 軍事・将軍＆超兵器ガチャ" + (" 【🔥確率2倍フェス開催中】" if FESTIVAL_ACTIVE else ""),
        description=(
            f"{free_txt}"
            "🟢 **C** (40%) / 🟤 **UC** (28%) / ⚪ **R【主力】** (20%) / 🟡 **SR【主力】** (10.5%)\n"
            "🌈 **SSR【稀】** (1.486%) / 🩷 **UR【極稀】** (0.01%) / ✨ **LR【超絶稀】** (0.003%) / 🩸 **MR【極絶稀】** (0.001%)\n\n"
            f"💎 所持機密ダイヤ：**`{u['gems']:,} 個`**（単発 500💎 / 10連 5,000💎）"
        ),
        color=0x8B0000
    )
    await interaction.response.send_message(embed=embed, view=GachaView(interaction.user.id))
@bot.tree.command(name="title", description="異名（称号）を変更・装備する")
@app_commands.describe(title_name="装備したい異名を入力")
async def cmd_title(interaction: discord.Interaction, title_name: str):
    if check_maint(interaction.user.id):
        return await interaction.response.send_message("🚧 現在メンテナンス中です。", ephemeral=True)
    get_user(interaction.user.id)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO user_titles (user_id, title) VALUES (?, ?)", (interaction.user.id, title_name))
    c.execute("UPDATE users SET equipped_title = ? WHERE user_id = ?", (title_name, interaction.user.id))
    conn.commit()
    conn.close()
    if isinstance(interaction.user, discord.Member):
        await sync_member_nickname(interaction.user, calc_total_power(interaction.user.id))
    await interaction.response.send_message(f"🎖️ 異名を **【{title_name}】** に変更しました！")

@bot.tree.command(name="ranking", description="ランクマ順位表 ＆ グローバル世界制覇ランキングボードを表示")
@app_commands.describe(board="rank（ランクマランキング） または global（グローバルストーリー進行度ランキング）")
async def cmd_ranking(interaction: discord.Interaction, board: str = "rank"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    mode = board.lower().strip()
    if mode == "global":
        c.execute("SELECT user_id, story_stage FROM users WHERE user_id != ? ORDER BY story_stage DESC LIMIT 15", (OWNER_ID,))
        rows = c.fetchall()
        conn.close()
        lines = [f"👑 **序列 第0位（創造主・規格外）**｜<@{OWNER_ID}> — **全999ステージ統括**"]
        for i, (uid, st) in enumerate(rows, start=1):
            lines.append(f"**第{i}位**｜<@{uid}> — **Stage.{st} / 999** 制覇")
        embed = discord.Embed(title="🌍 グローバルランキングボード（メインストーリー制覇順位）", description="\n".join(lines), color=0x3498DB)
    else:
        c.execute("SELECT user_id, rp FROM users WHERE user_id != ? ORDER BY rp DESC LIMIT 15", (OWNER_ID,))
        rows = c.fetchall()
        conn.close()
        lines = [f"👑 **序列 第0位（創世神・規格外）**｜<@{OWNER_ID}> — **測定不能 RP**"]
        for i, (uid, rp) in enumerate(rows, start=1):
            tier = get_pvp_tier(uid, rp)
            lines.append(f"**第{i}位**｜<@{uid}> — **{tier}**（`{rp:,} RP`）")
        embed = discord.Embed(title="🏅 ランクマランキングボード（PvP階級順位表）", description="\n".join(lines), color=0xF1C40F)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="dex", description="ユニット・兵器図鑑（Lv.100上限・スキル・必殺技・画像/GIF表示）")
@app_commands.describe(card_id="詳細を見たいユニットID（省略すると一覧表示）")
async def cmd_dex(interaction: discord.Interaction, card_id: int = 0):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if card_id > 0:
        c.execute("SELECT * FROM cards WHERE id = ?", (card_id,))
        card = c.fetchone()
        c.execute("SELECT level, max_level, skill_lv FROM user_cards WHERE user_id = ? AND card_id = ?", (interaction.user.id, card_id))
        uc = c.fetchone()
        conn.close()
        if not card:
            return await interaction.response.send_message("❌ 指定されたIDは見つかりませんでした。", ephemeral=True)
        rc = RARITY_CONFIG[card]
        lv_txt = f"Lv.{uc} / 上限Lv.{uc}（Skill Lv.{uc}）" if uc else "未所持（初期上限 Lv.20）"
        embed = discord.Embed(
            title=f"{rc['emoji']} [{card}] {card} — {card}",
            description=f"💥 基本戦力：**`+{card:,}`**｜📈 育成状態：**{lv_txt}**",
            color=rc["color"]
        )
        embed.add_field(
            name="📊 基本ステータス",
            value=f"⚔️ ATK：`{card:,}` / 🛡️ DEF：`{card:,}` / ⚡ SPD：`{card:,}` / 👑 統率：`{card:,}`",
            inline=False
        )
        embed.add_field(name=f"🔹 固有スキル【{card}】", value=card, inline=False)
        embed.add_field(name=f"🔥 必殺奥義【{card}】", value=card, inline=False)
        embed.add_field(name="✨ 特殊能力（パッシブ）", value=card, inline=False)
        if card:
            embed.set_image(url=card)
        return await interaction.response.send_message(embed=embed)

    c.execute("""
        SELECT cards.id, cards.rarity, cards.name, cards.role_title,
               COALESCE(user_cards.level, 0), COALESCE(user_cards.max_level, 20), COALESCE(user_cards.skill_lv, 1)
        FROM cards
        LEFT JOIN user_cards ON cards.id = user_cards.card_id AND user_cards.user_id = ?
        ORDER BY cards.id ASC
    """, (interaction.user.id,))
    rows = c.fetchall()
    conn.close()
    lines = []
    for r in rows:
        rc = RARITY_CONFIG[r]
        owned = f"Lv.{r}/{r} (S{r})" if r > 0 else "未所持"
        lines.append(f"`ID:{r:02d}` {rc['emoji']} **[{r}] {r}**（{r}）｜{owned}")
    embed = discord.Embed(
        title="📖 最高機密 兵器・将軍図鑑（`/dex card_id:番号` で画像・スキル表示）",
        description="\n".join(lines[:25]),
        color=0x34495E
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="set_card_image", description="【運営専用】図鑑・ガチャのカードに画像またはGIFのURLを設定する")
@app_commands.describe(card_id="設定したいカードのID（/dexで確認）", image_url="Discordに貼った画像またはGIFのリンク")
async def cmd_set_card_image(interaction: discord.Interaction, card_id: int, image_url: str):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("❌ 運営専用コマンドです。", ephemeral=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE cards SET image_url = ? WHERE id = ?", (image_url.strip(), card_id))
    updated = c.rowcount
    conn.commit()
    conn.close()
    if updated == 0:
        return await interaction.response.send_message("❌ そのカードIDは存在しません。", ephemeral=True)
    embed = discord.Embed(title=f"✅ カードID:{card_id} に画像・GIFを設定しました！", color=0x2ECC71)
    embed.set_image(url=image_url.strip())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="set_effect_image", description="【運営専用】基地(/base)や核投下の演出GIF・画像を設定する")
@app_commands.describe(target="base または nuke", image_url="Discordに貼った画像またはGIFのリンク")
async def cmd_set_effect_image(interaction: discord.Interaction, target: str, image_url: str):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("❌ 運営専用コマンドです。", ephemeral=True)
    key = target.lower().strip()
    if key not in ("base", "nuke"):
        return await interaction.response.send_message("❌ target には `base` または `nuke` を入力してください。", ephemeral=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO effect_media (key, url) VALUES (?, ?)", (key, image_url.strip()))
    conn.commit()
    conn.close()
    embed = discord.Embed(title=f"✅ `{key}` の演出メディアを設定しました！", color=0x2ECC71)
    embed.set_image(url=image_url.strip())
    await interaction.response.send_message(embed=embed)

# ==========================================
# 7. 起動処理＆ヘルスチェックサーバー
# ==========================================
class PermanentHubView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎰 ガチャを開く", style=discord.ButtonStyle.danger, custom_id="hub_gacha", row=0)
    async def hub_gacha(self, interaction: discord.Interaction, button: discord.ui.Button):
        u = get_user(interaction.user.id)
        free_txt = "🎁 **初回限定・無料10連チケット：残り1回！**\n" if u["free_ten_pull"] > 0 else ""
        embed = discord.Embed(
            title="🎰 最高機密 軍事・将軍＆超兵器ガチャ",
            description=f"{free_txt}💎 所持ダイヤ：**`{u['gems']:,} 個`**（単発 500💎 / 10連 5,000💎）",
            color=0x8B0000
        )
        await interaction.response.send_message(embed=embed, view=GachaView(interaction.user.id), ephemeral=True)

    @discord.ui.button(label="🌍 実在国ストーリー(999)", style=discord.ButtonStyle.primary, custom_id="hub_story", row=0)
    async def hub_story(self, interaction: discord.Interaction, button: discord.ui.Button):
        u = get_user(interaction.user.id)
        st = min(999, u["story_stage"])
        c_name, flag, p_mult = REAL_COUNTRIES[(st - 1) % len(REAL_COUNTRIES)]
        scale = (st ** 1.35) * p_mult
        view = TacticalBattleView(
            interaction.user.id, f"{flag} Stage.{st}/999：{c_name}",
            int(3500 + scale * 420), int(420 + scale * 55), int(220 + scale * 30),
            min(5000, 500 + (st // 5) * 50), int(12000 + st * 800), 0,
            "mat_parts" if st < 150 else ("mat_alloy" if st < 450 else "mat_quantum"),
            is_rank=False, story_clear_stage=st
        )
        await interaction.response.send_message(embed=view.build_embed(f"🌍 **Stage.{st} / 999 開戦！**"), view=view, ephemeral=True)

    @discord.ui.button(label="🤖 Bot戦(ダイヤ稼ぎ)", style=discord.ButtonStyle.success, custom_id="hub_bot", row=0)
    async def hub_bot(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = TacticalBattleView(interaction.user.id, "帝国第4機甲大隊", 18000, 1600, 800, 1000, 30000, 0, "mat_parts")
        await interaction.response.send_message(embed=view.build_embed("🚨 **Bot戦（中級）開戦！**"), view=view, ephemeral=
    @discord.ui.button(label="🏅 ランク戦出撃", style=discord.ButtonStyle.danger, custom_id="hub_rank", row=1)
    async def hub_rank(self, interaction: discord.Interaction, button: discord.ui.Button):
        await start_or_queue_rank_match(interaction)
        
    @discord.ui.button(label="📊 戦績ステータス", style=discord.ButtonStyle.secondary, custom_id="hub_status", row=1)
    async def hub_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        u = get_user(interaction.user.id)
        power = calc_total_power(interaction.user.id)
        rank_info, _ = get_rank_info(interaction.user.id, power)
        await interaction.response.send_message(
            f"🎖️ 階級：**{rank_info}**｜異名：**【{u['equipped_title']}】**\n⚔️ 総戦力：**`{power:,}`**｜💎 ダイヤ：**`{u['gems']:,}`**｜🌍 進行：**Stage.{u['story_stage']}/999**",
            ephemeral=True
        )

    @discord.ui.button(label="🔒 個別極秘基地を作る", style=discord.ButtonStyle.primary, custom_id="hub_room", row=1)
    async def hub_room(self, interaction: discord.Interaction, button: discord.ui.Button):
        await cmd_create_base_room.callback(interaction)

@bot.tree.command(name="setup_panel", description="【運営専用】このチャンネルに常設の総合司令部ボタンパネルを設置する")
@app_commands.describe(title="パネルのタイトル", description="案内文")
async def cmd_setup_panel(interaction: discord.Interaction, title: str = "🎖️ 最高司令部・総合作戦ターミナル", description: str = "下のボタンからいつでもガチャ・実在国進軍ストーリー・Bot戦・ランク戦・個別基地建設へアクセスできます！"):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("❌ 運営専用コマンドです。", ephemeral=True)
    embed = discord.Embed(title=title, description=description, color=0x8B0000)
    await interaction.channel.send(embed=embed, view=PermanentHubView())
    await interaction.response.send_message("✅ 常設パネルを設置しました！", ephemeral=True)
@bot.event
async def on_ready():
    init_db()
    bot.add_view(TourneyJoinView())
    bot.add_view(PermanentHubView())
    synced = await bot.tree.sync()
    print(f"Commander Bot logged in as {bot.user} | Synced {len(synced)} commands", flush=True)

async def handle_health(reader, writer):
    await reader.read(1024)
    response = "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 24\r\n\r\nCommander Bot is alive!"
    writer.write(response.encode())
    await writer.drain()
    writer.close()

async def main():
    if not TOKEN:
        print("ERROR: DISCORD_TOKEN is empty!", flush=True)
        return
    port = int(os.environ.get("PORT", 10000))
    server = await asyncio.start_server(handle_health, "0.0.0.0", port)
    async with server:
        async with bot:
            await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
