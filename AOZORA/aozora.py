# Pycord (Pycord v2, SQLiteでBAN期間管理)
# Pycordを読み込む
import discord
import discord.ext.commands
import configparser
import asyncio
import sqlite3
import psutil
import os
import re
from os.path import join, dirname
from dotenv import load_dotenv
from discord.ext import pages
from discord.ui import Select, Button, View
from discord import default_permissions, option
from datetime import datetime, timedelta, timezone

load_dotenv(verbose=True)

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path, override=True)

# アクセストークンを設定
TOKEN=os.environ.get("TOKEN")
guild_id=[int(os.getenv("guild_id"))]
CATEGORY_ID=int(os.getenv("CATEGORY_ID"))
VCCATEGORY_ID=int(os.getenv("VCCATEGORY_ID"))
username=os.environ.get("username")
botname=os.environ.get("botname")
objection=os.environ.get("objection")
MOD_ROLE_NAME=os.environ.get("MOD_ROLE_NAME")
ROLE_NAME=os.environ.get("ROLE_NAME")
CAUTIONROLE=os.environ.get("CAUTIONROLE")
APPEAL=int(os.getenv("APPEAL"))
FEEDBACK=int(os.getenv("FEEDBACK"))
USERID=int(os.getenv("USERID"))
CAUTIONINFO=int(os.getenv("CAUTIONINFO"))
version = "Beta 1.0  Beta-1"
build = "20250307"
intents = discord.Intents.default()
intents.guilds = True
intents.voice_states = True  # ボイスチャンネルの情報を取得するために必要
intents.members = True  # メンバー情報取得のために必要
dt = datetime.today()

# Botの大元となるオブジェクトを生成する
bot = discord.Bot(
    intents=discord.Intents.all(),
    activity=discord.Game(f'{botname} - ﾊﾞｰｼﾞｮﾝ ' + version),
)

# VCのリーダーを管理する辞書 {vc_id: leader_id}
vc_leaders = {}

# 処罰名の対応表
PUNISHMENT_MAP = {
    "caution": "口頭注意",
    "warn": "厳重注意",
    "ban": "BAN",
    "unban": "UNBAN",
    "kick": "KICK",
    "timeout": "TIMEOUT",
}

time_units = {"m": 60, "h": 3600, "d": 86400, "mo": 2592000, "y": 31536000}

# データを保存するファイルのパス
DATA_FILE = "vc_leaders.ini"

def parse_time(time_str):
    try:
        if not time_str:
            return None
        match = re.fullmatch(r"(\d+)([mhdymo]+)", time_str)
        if not match:
            raise ValueError("時間形式は '10m', '2h', '1d' などを使用してください。")
        value, unit = match.groups()
        return int(value) * time_units[unit]
    except Exception:
        raise ValueError("無効な時間形式です。例: '10m', '2h', '1d'")

# DBセットアップ
conn = sqlite3.connect('ban_data.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS bans(member_id INTEGER, guild_id INTEGER, member_name TEXT, unban_time TEXT)''')
conn.commit()

async def unban_task():
    while True:
        now = datetime.now(timezone.utc)
        c.execute("SELECT member_id, guild_id FROM bans WHERE unban_time <= ?", (now.isoformat(),))
        for member_id, guild_id in c.fetchall():
            guild = bot.get_guild(guild_id)
            await guild.unban(discord.Object(id=member_id))
            c.execute("DELETE FROM bans WHERE member_id=? AND guild_id=?", (member_id, guild_id))
        conn.commit()
        await asyncio.sleep(60)

# データをファイルに保存する関数
def save_vc(vc_id, user_id):
    vc_leaders[vc_id] = user_id
    config = configparser.ConfigParser()
    config.read("vc_leaders.ini")
    if 'VC_LEADERS' not in config:
        config['VC_LEADERS'] = {}
    
    userid=str(user_id)

    config['VC_LEADERS'][str(vc_id)] = userid
    with open(DATA_FILE, 'w') as f:
        config.write(f)

# データをファイルから読み込む関数
def load_vc_data():
    config = configparser.ConfigParser()
    if os.path.exists(DATA_FILE):
        config.read(DATA_FILE)
        return {int(vc_id): int(user_id) for vc_id, user_id in config['VC_LEADERS'].items()}
    return {}

def delete_save_vc(vc_id, user_id):
    vc_leaders[vc_id] = user_id
    config = configparser.ConfigParser()
    config.read("vc_leaders.ini")
    
    config.remove_option('VC_LEADERS', str(vc_id))
    with open('vc_leaders.ini', 'w') as configfile:
        config.write(configfile)

def blocked_vc(user_id, block_id):
    config = configparser.ConfigParser()
    config.read("vcblocked.ini")

    if "Users" not in config:
        config["Users"] = {}
    
   # 既存データを取得して新しいデータを追記
    existing_data = config["Users"].get(str(user_id), "")
    new_entry = f"{block_id}"

    # 既存データがあれば追記、新規の場合は新しいデータを設定
    if existing_data:
        config["Users"][str(user_id)] = f"{existing_data},{new_entry}"
    else:
        config["Users"][str(user_id)] = new_entry

    with open('vcblocked.ini', 'w') as configfile:
        config.write(configfile)

def get_block(leader_id: int):
    config = configparser.ConfigParser()
    config.read("vcblocked.ini")
    if "Users" not in config or str(leader_id) not in config["Users"]:
        return None

    return config["Users"][str(leader_id)]

def delete_block(leader_id: int, block_id: int):
    config = configparser.ConfigParser()
    config.read("vcblocked.ini")

    blockid=str(block_id)

    if "Users" not in config or str(leader_id) not in config["Users"]:
        return False
    
    data = config["Users"][str(leader_id)]
    entries = [entry.strip() for entry in data.split(",")]
    filtered_entries = [entry for entry in entries if not entry.startswith(blockid)]
    if filtered_entries:
        config["Users"][str(leader_id)] = ", ".join(filtered_entries)
    else:
        config.remove_option("Users", str(leader_id))
    
    with open('vcblocked.ini', 'w') as configfile:
        config.write(configfile)

# Configファイル操作用関数
def get_user_data(user_id: int):
    config = configparser.ConfigParser()
    config.read("aozora.ini")
    if "Users" not in config or str(user_id) not in config["Users"]:
        return None

    # 保存された値を分割して取得 (action, reason)
    value = config["Users"][str(user_id)]
    parts = value.split('|', 1)  # データを区切り文字で分割
    return parts if len(parts) > 1 else (parts[0], "")  # reasonがない場合に空文字を返す

# 設定ファイルを保存する関数
def save_config(user_id: int, action: str, reason: str = "", time: str = ""):
    config = configparser.ConfigParser()
    config.read("aozora.ini")

    if "Users" not in config:
        config["Users"] = {}
    
   # 既存データを取得して新しいデータを追記
    existing_data = config["Users"].get(str(user_id), "")
    new_entry = f"{action}:{reason}:{time}" if reason else f"{action}:{time}"

   # `reason` を明確に文字列化
    reason = str(reason).strip()

    # 既存データがあれば追記、新規の場合は新しいデータを設定
    if existing_data:
        config["Users"][str(user_id)] = f"{existing_data}, {new_entry}"
    else:
        config["Users"][str(user_id)] = new_entry
    
    # 保存
    with open('aozora.ini', 'w') as configfile:
        config.write(configfile)

# 処罰履歴を削除する関数
def delete_user_data(user_id: int, action: str = None):
    config = configparser.ConfigParser()
    config.read("aozora.ini")

    if "Users" not in config or str(user_id) not in config["Users"]:
        return False

    # 全削除の場合
    if action is None:
        config.remove_option("Users", str(user_id))
    else:
        # 特定の処罰だけ削除
        action_name = PUNISHMENT_MAP.get(action, action)
        data = config["Users"][str(user_id)]
        entries = [entry.strip() for entry in data.split(",")]
        filtered_entries = [entry for entry in entries if not entry.startswith(action_name)]
        if filtered_entries:
            config["Users"][str(user_id)] = ", ".join(filtered_entries)
        else:
            config.remove_option("Users", str(user_id))

    with open("aozora.ini", "w") as configfile:
        config.write(configfile)
    return True

# DM送信の共通関数
async def send_dm(user, message):
    try:
        await user.send(message)
    except discord.Forbidden:
        pass  # DMが送信できなかった場合は無視

@bot.slash_command(description="ユーザーをBAN (期間省略時は永久BAN)")
@option("member", discord.Member, description="BANするユーザーを指定")
@option("reason", str, required=False, description="理由")
@option("time", str, required=False, description="BAN期間 (例: 1h, 1d, 1mo, 1y, なし: 無期限)")
async def ban(ctx: discord.ApplicationContext, member: discord.Member, reason, time):
    reason = ' '.join(reason) if reason else '理由は指定されていません'
    duration = parse_time(time)
    embed_dm = discord.Embed(title="運営からの重要なお知らせ",description=f"""
{member.mention} さん
いつも当サーバーをご利用くださいまして、ありがとうございます。
運営からの大切なお知らせです。
今回、当サーバーでの違反行為が複数回、または重い違反があったため、サーバーからのBANを行いさせていただくこととなりました。
サーバーへの再参加はできませんので、ご了承ください。
また、サブアカウントや他のアカウントでの再参加も禁止となりますので、ご注意ください。
納得がいかない場合もあるかと思いますが、ご理解のほど、よろしくお願いいたします。
期間が設定されている場合、期間終了後にサーバーへの再参加が可能です。
また、違反行為をしていないなどの場合、異議申し立てを行うことができます。
異議申し立ては <@{USERID}> までお願いします。
※返事がない場合もあります。複数回にわたってDMを送られた場合、通知オフや無視機能、ブロック機能を使うなどの対応を取ることがあります。
当サーバーをご利用くださいまして、ありがとうございました。
{botname} バージョン{version} Build{build}
""",color=0xE03625)
    embed_dm.add_field(name="違反レベル",value=f"サーバーBAN(複数回にわたる違反行為、または重い違反行為)",inline=True)
    embed_dm.add_field(name="違反内容",value=f"{reason}",inline=True)
    embed_dm.add_field(name="期間",value=f"{time}",inline=True)
    await member.send(embed=embed_dm)
    await ctx.guild.ban(member, reason=reason)
    if duration:
        unban_time = datetime.now(timezone.utc) + timedelta(seconds=duration)
        c.execute("INSERT INTO bans VALUES (?, ?, ?, ?)", (member.id, ctx.guild.id, member.name, unban_time.isoformat()))
    else:
        c.execute("INSERT INTO bans VALUES (?, ?, ?, NULL)", (member.id, ctx.guild.id, member.name))
    conn.commit()
    save_config(member.id, 'BAN', reason, time)
    embed=discord.Embed(title="BANが正常に実行されました", color=0x7BAB4F)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="対象", value=member.mention, inline=False)
    embed.add_field(name="実行", value=ctx.author, inline=False)
    embed.add_field(name="期間", value=f"{'無期限' if not time else time}", inline=False)
    embed.add_field(name="理由", value=reason, inline=False)
    await ctx.respond(embed=embed)

@bot.slash_command(description="ユーザーをサーバーからキック")
@option("member", discord.Member, description="キックするユーザーを指定")
@option("reason", str, required=False, description="理由")
async def kick(ctx: discord.ApplicationContext, member: discord.Member, reason: str = None):
    reason = ' '.join(reason) if reason else '理由は指定されていません'
    embed_dm = discord.Embed(title="運営からの重要なお知らせ",description=f"""
{member.mention} さん
運営からの大切なお知らせです。
今回、当サーバーでの違反行為が複数回、または重い違反があったため、サーバーキックを行いさせていただくこととなりました。
サーバーには再度参加できますが、今後、同様の行動があった場合、コミュニティからのBANを行うことがありますので、十分ご注意ください。
納得がいかない場合もあるかと思いますが、ご理解のほど、よろしくお願いいたします。
また、違反行為をしていないなどの場合、異議申し立てを行うことができます。
異議申し立ては <@{USERID}> までお願いします。
※返事がない場合もあります。複数回にわたってDMを送られた場合、通知オフや無視機能、ブロック機能を使うなどの対応を取ることがあります。
当サーバーをご利用くださいまして、ありがとうございました。
{botname} バージョン{version} Build{build}
""",color=0xB53D27)
    embed_dm.add_field(name="違反レベル",value=f"サーバーキック(複数回にわたる違反行為、または重い違反行為)",inline=True)
    embed_dm.add_field(name="違反内容",value=f"{reason}",inline=True)
    await member.send(embed=embed_dm)
    save_config(member.id, 'KICK', reason)
    await ctx.guild.kick(member, reason=reason)
    embed=discord.Embed(title="キックが正常に実行されました", color=0x7BAB4F)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="対象", value=member.mention, inline=False)
    embed.add_field(name="実行", value=ctx.author, inline=False)
    embed.add_field(name="理由", value=reason, inline=False)
    await ctx.respond(embed=embed)

@bot.slash_command(description="ユーザーをタイムアウト")
@option("member", discord.Member, description="タイムアウトするユーザーを指定")
@option("reason", str, required=False, description="理由")
@option("time", int, description="分")
async def timeout(ctx: discord.ApplicationContext, member: discord.Member, reason: str = None, time: int = None):
    try:
        time = int(time)
        reason = ' '.join(reason)
    except ValueError:
        embed=discord.Embed(title=f"時間は数字で指定してください。", color=0xE03625)
        await ctx.respond(embed=embed)
        return
    embed_dm = discord.Embed(title="運営からのお知らせ",description=f"""
{member.mention} さん
いつも当サーバーをご利用くださいまして、ありがとうございます。
運営からの大切なお知らせです。
今回、貴方の行動が当サーバーの違反行為に該当するため、タイムアウトを行いさせていただくこととなりました。
今後、同様の行動があった場合、より厳しい処置を取ることがありますので、ご注意ください。
納得がいかない場合もあるかと思いますが、ご理解のほど、よろしくお願いいたします。
また、心当たりがない、違反行為をしていないなどの場合、異議申し立てを行うことができます。
異議申し立ては[こちら]({objection})
{botname} バージョン{version} Build{build}
""",color=0xC16543)
    embed_dm.add_field(name="違反レベル",value=f"{time}分間のタイムアウト",inline=True)
    embed_dm.add_field(name="違反内容",value=f"{reason}",inline=True)
    await member.send(embed=embed_dm)
    save_config(member.id, f'TIMEOUT ({time}分)', reason)
    await member.timeout(discord.utils.utcnow() + timedelta(minutes=time))
    embed=discord.Embed(title="タイムアウトが正常に実行されました", color=0x7BAB4F)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="対象", value=member.mention, inline=False)
    embed.add_field(name="実行", value=ctx.author, inline=False)
    embed.add_field(name="時間", value=time, inline=False)
    embed.add_field(name="理由", value=reason, inline=False)
    await ctx.respond(embed=embed)

@bot.slash_command(description="口頭注意(違反者にDMを送信します。)")
@option("member", discord.Member, description="口頭注意するユーザーを指定")
@option("reason", str, required=True, description="理由")
async def caution(ctx: discord.ApplicationContext, member: discord.Member, reason: str):
    save_config(member.id, f'口頭注意', reason)
    embed_dm = discord.Embed(title="運営からの大切なお知らせ",description=f"""
{member.mention} さん
いつも当サーバーをご利用くださいまして、ありがとうございます。
運営からの大切なお知らせです。
今回、貴方の行動が当サーバーの違反行為に該当するため、口頭注意を行いさせていただくこととなりました。
今後、同様の行動があった場合、より厳しい処置を取ることがありますので、ご注意ください。
納得がいかない場合もあるかと思いますが、ご理解のほど、よろしくお願いいたします。
また、心当たりがない、違反行為をしていないなどの場合、異議申し立てを行うことができます。
異議申し立ては[こちら]({objection})
{botname} バージョン{version} Build{build}
""",color=0x97BC94)
    embed_dm.add_field(name="違反レベル",value=f"口頭注意",inline=True)
    embed_dm.add_field(name="違反内容",value=f"{reason}",inline=True)
    await member.send(embed=embed_dm)
    embed=discord.Embed(title="口頭注意が正常に実行されました", color=0x7BAB4F)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="対象", value=member.mention, inline=False)
    embed.add_field(name="実行", value=ctx.author, inline=False)
    embed.add_field(name="理由", value=reason, inline=False)
    await ctx.respond(embed=embed)

@bot.slash_command(description="厳重注意(違反者にDMを送信し、危険人物ロールを付与します。)")
@option("member", discord.Member, description="厳重注意するユーザーを指定")
@option("reason", str, required=True, description="理由")
async def warn(ctx: discord.ApplicationContext, member: discord.Member, reason: str):
    save_config(member.id, f'厳重注意', reason)
    embed_dm = discord.Embed(title="運営からの大切なお知らせ",description=f"""
{member.mention} さん
いつも当サーバーをご利用くださいまして、ありがとうございます。
運営からの大切なお知らせです。
今回、貴方の行動が当サーバーの違反行為に該当するため、厳重注意を行いさせていただくこととなりました。
これにより、危険人物を意味する{CAUTIONROLE}ロールが付与されます。
今後、同様の行動があった場合、より厳しい処置を取ることがありますので、ご注意ください。
納得がいかない場合もあるかと思いますが、ご理解のほど、よろしくお願いいたします。
また、心当たりがない、違反行為をしていないなどの場合、異議申し立てを行うことができます。
異議申し立ては[こちら]({objection})
{botname} バージョン{version} Build{build}
""",color=0xFDBC00)
    embed_dm.add_field(name="違反レベル",value=f"厳重注意",inline=True)
    embed_dm.add_field(name="違反内容",value=f"{reason}",inline=True)
    await member.send(embed=embed_dm)
    channel = bot.get_channel(CAUTIONINFO)
    role = discord.utils.get(ctx.guild.roles, name=CAUTIONROLE)
    if role:
        await member.add_roles(role)
        user_data = get_user_data(member.id)
        embed=discord.Embed(title=f"⚠️危険人物発信情報⚠️", color=0xE03625)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="人物", value=member.mention, inline=False)
        embed.add_field(name="違反レベル", value=f"厳重注意", inline=False)
        embed.add_field(name="違反内容", value=f"{reason}", inline=False)
        embed.add_field(name="処罰履歴(現時点)", value=user_data, inline=False)
        await channel.send(embed=embed)
    embed=discord.Embed(title="厳重注意が正常に実行されました", color=0x7BAB4F)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="対象", value=member.mention, inline=False)
    embed.add_field(name="実行", value=ctx.author, inline=False)
    embed.add_field(name="理由", value=reason, inline=False)
    await ctx.respond(embed=embed)

@bot.slash_command(description="ユーザーをUNBANします。")
@option("member_id", str, description="UNBANするユーザーのID")
@option("reason", str, description="理由", required=False)
async def unban(ctx: discord.ApplicationContext, member_id: str, reason: str = None):
    try:
        save_config(int(member_id), 'UNBAN', reason)
        member_obj = discord.Object(id=int(member_id))
        await ctx.guild.unban(member_obj)
        c.execute("DELETE FROM bans WHERE member_id=? AND guild_id=?", (int(member_id), ctx.guild.id))
        conn.commit()
        embed=discord.Embed(title="UNBANが正常に実行されました", color=0x7BAB4F)
        embed.add_field(name="対象", value=member_id, inline=False)
        embed.add_field(name="実行", value=ctx.author, inline=False)
        embed.add_field(name="理由", value=reason, inline=False)
        await ctx.respond(embed=embed)
    except Exception as e:
        embed=discord.Embed(title="⚠️UNBANに失敗しました", color=0xE03625)
        embed.add_field(name="対象", value=member_id, inline=False)
        embed.add_field(name="実行", value=ctx.author, inline=False)
        embed.add_field(name="エラー", value=e, inline=False)
        await ctx.respond(embed=embed)

@bot.slash_command(description="BANされているユーザー一覧を表示")
async def banlist(ctx):
    c.execute("SELECT member_name, unban_time FROM bans WHERE guild_id=?", (ctx.guild.id,))
    bans = c.fetchall()
    if not bans:
        embed1=discord.Embed(title="現在BANされているユーザーはいません。", color=0x7BAB4F)
        await ctx.respond(embed=embed1)
    else:
        ban_info = "\n".join([f"ユーザー名: {name}, UNBAN予定: {unban_time if unban_time else '無期限'}" for name, unban_time in bans])
        embed2=discord.Embed(title="**BANリスト**", description=f"{ban_info}", color=0x7BAB4F)
        await ctx.respond(embed=embed2)

# 処罰コマンド
@bot.slash_command(description="違反者にDMを送らずに処罰をします。", guild_ids=guild_id)
async def silent(ctx: discord.ApplicationContext, action: str, member: discord.Member, reason: str = None, time: int = None, bantime: str =None):
    config = configparser.ConfigParser()
    reason = ' '.join(reason) if reason else '理由は指定されていません'
    member_id = str(member.id)

    if action.lower() == 'ban':
        duration = parse_time(bantime)
        await ctx.guild.ban(member, reason=reason)
        if duration:
            unban_time = datetime.now(timezone.utc) + timedelta(seconds=duration)
            c.execute("INSERT INTO bans VALUES (?, ?, ?, ?)", (member.id, ctx.guild.id, member.name, unban_time.isoformat()))
        else:
            c.execute("INSERT INTO bans VALUES (?, ?, ?, NULL)", (member.id, ctx.guild.id, member.name))
        conn.commit()
        save_config(member.id, 'BAN', reason, bantime)
        embed=discord.Embed(title="BANが正常に実行されました", color=0x7BAB4F)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="対象", value=member.mention, inline=False)
        embed.add_field(name="実行", value=ctx.author, inline=False)
        embed.add_field(name="期間", value=f"{'無期限' if not bantime else bantime}", inline=False)
        embed.add_field(name="理由", value=reason, inline=False)
        await ctx.respond(embed=embed)

    elif action.lower() == 'kick':
        save_config(member.id, 'KICK', reason)
        await ctx.guild.kick(member, reason=reason)
        embed=discord.Embed(title="キックが正常に実行されました", color=0x7BAB4F)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="対象", value=member.mention, inline=False)
        embed.add_field(name="実行", value=ctx.author, inline=False)
        embed.add_field(name="理由", value=reason, inline=False)
        await ctx.respond(embed=embed)

    elif action.lower() == 'timeout':
        if time is None:
            embed=discord.Embed(title=f"時間を指定してください。bantimeにしていませんか？例: /silent timeout ユーザー名 時間(分) [理由]", color=0xE03625)
            await ctx.respond(embed=embed)
            return
        try:
            time = int(time)
            reason = ' '.join(reason)
        except ValueError:
            embed=discord.Embed(title=f"時間は数字で指定してください。", color=0xE03625)
            await ctx.respond(embed=embed)
            return
        await member.timeout(discord.utils.utcnow() + timedelta(minutes=time))
        save_config(member.id, f'TIMEOUT ({time}分)', reason)
        embed=discord.Embed(title="タイムアウトが正常に実行されました", color=0x7BAB4F)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="対象", value=member.mention, inline=False)
        embed.add_field(name="実行", value=ctx.author, inline=False)
        embed.add_field(name="時間", value=f"{time}分", inline=False)
        embed.add_field(name="理由", value=reason, inline=False)
        await ctx.respond(embed=embed)

    elif action.lower() in ['caution', 'warn']:
        level = '口頭注意' if action.lower() == 'caution' else '厳重注意'
        save_config(member.id, f'{level}', reason)
        if action.lower() == 'warn':
            channel = bot.get_channel(CAUTIONINFO)
            role = discord.utils.get(ctx.guild.roles, name=CAUTIONROLE)
            if role:
                await member.add_roles(role)
                user_data = get_user_data(member.id)
                embed=discord.Embed(title=f"⚠️危険人物発信情報⚠️", color=0xE03625)
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.add_field(name="人物", value=member.mention, inline=False)
                embed.add_field(name="違反レベル", value=f"厳重注意", inline=False)
                embed.add_field(name="違反内容", value=f"{reason}", inline=False)
                embed.add_field(name="処罰履歴(現時点)", value=user_data, inline=False)
                await channel.send(embed=embed)
        embed=discord.Embed(title=f"{level}が正常に実行されました", color=0x7BAB4F)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="対象", value=member.mention, inline=False)
        embed.add_field(name="実行", value=ctx.author, inline=False)
        embed.add_field(name="理由", value=reason, inline=False)
        await ctx.respond(embed=embed)

    else:
        embed=discord.Embed(title=f"無効なアクションです。ban, kick, timeoutのいずれかを指定してください。", color=0xE03625)
        await ctx.respond(embed=embed)

# 処罰履歴を表示するコマンド
@bot.slash_command(description="処罰履歴を表示します", guild_ids=guild_id)
async def criminal(ctx: discord.ApplicationContext, user: discord.Member):

    user_data = get_user_data(user.id)
    if user_data:
        embed=discord.Embed(title=f"ユーザー {user.name} の処罰履歴", color=0xE03625)
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="対象", value=user.mention, inline=False)
        embed.add_field(name="処罰履歴", value={user_data}, inline=False)
        await ctx.respond(embed=embed)
    else:
        embed=discord.Embed(title=f"ユーザー {user.name} の処罰履歴はありません。", color=0x7BAB4F)
        await ctx.respond(embed=embed)

@bot.slash_command(description=f"{botname}のバージョン情報", guild_ids=guild_id)
async def about(ctx: discord.ApplicationContext):
    mem = psutil.virtual_memory()
    available_gb = mem.available / (1024 ** 1)  # KBに変換
    total_gb = mem.total / (1024 ** 1)
    embed=discord.Embed(title=f"{botname}のバージョン情報", color=0x7BAB4F)
    embed.add_field(name=f"{botname}", value="", inline=False)
    embed.add_field(name=f"Version", value=f"{version}", inline=False)
    embed.add_field(name=f"Build", value=f"{build}", inline=True)
    embed.add_field(name=f"Owner", value=f"{dt.year} {username}", inline=True)
    embed.add_field(name=f"Tool", value=f"""
このアプリケーションはモデレーター・運営のためのツールであり、トークン・個人情報を公開してはなりません。
このアプリケーションは以下のユーザーによって管理されています。
            : {username}
            {botname} が使用できる最大物理メモリ
            {total_gb:.0f} KB
""", inline=False)
    await ctx.respond(embed=embed)

@bot.slash_command(description="使い方", guild_ids=guild_id)
async def help(ctx: discord.ApplicationContext):
    embed=discord.Embed(title=f"{botname} ヘルプ", description=f"このアプリケーションの使用方法", color=0x7BAB4F)
    embed.add_field(name="/ban",value=f"""
ユーザーをBANします。(違反ユーザーにDMが送信されます。)
/ban member:@BANするユーザー名 reason:BANをする理由 time:時間(指定しない場合、永久BANとなります。)
時間を設定した場合、設定時間経過後、自動的にBAN解除されます。
""",inline=False)
    embed.add_field(name="/kick",value=f"""
ユーザーをキックします。(違反ユーザーにDMが送信されます。)
/kick member:@キックするユーザー名 reason:キックをする理由
""",inline=False)
    embed.add_field(name="/timeout",value=f"""
ユーザーをタイムアウトします。(違反ユーザーにDMが送信されます。)
/timeout member:@タイムアウトするユーザー名 reason:タイムアウトをする理由 time:分
""",inline=False)
    embed.add_field(name="/caution",value=f"""
ユーザーを口頭注意します。(違反ユーザーにDMが送信されます。)
/caution member:@注意するユーザー名 reason:違反内容(注意したい内容)
""",inline=False)
    embed.add_field(name="/warn",value=f"""
ユーザーを厳重注意し、危険人物ロールをつけます。(違反ユーザーにDMが送信されます。)
/warn member:@注意するユーザー名 reason:違反内容(注意したい内容)
""",inline=False)
    embed.add_field(name="/unban",value=f"""
BANしたユーザーのBANを解除します。
/unban member:ユーザーID reason:理由
""",inline=False)
    embed.add_field(name="/silent",value=f"""
注意・処罰報告のDMをせずに処罰をします。
/silent action member:@違反ユーザー reason:理由 time:時間(BAN, タイムアウト)
action 一覧:
    ┠ ban ユーザー名 **bantime(時間)** reason(理由) -ユーザーをBANします。
    ┠ kick ユーザー名 reason(理由) -ユーザーをKICKします。
    ┠ timeout ユーザー名 **time(分)** reason(理由) -ユーザーをタイムアウトします。
""",inline=False)
    embed.add_field(name="/help",value=f"このヘルプを表示します。",inline=False)
    embed.add_field(name="/criminal",value=f"""
/criminal @ユーザー名
ユーザーの処罰履歴を表示します。""",inline=False)
    embed.add_field(name="/format",value=f"""
ユーザーの処罰履歴を削除します。
/format member:@ユーザー名 action(処罰)
action 一覧:
全ての処罰を削除
ban, kick, timeout, caution, warn -特定の処罰を削除
""",inline=False)
    embed.add_field(name="時間の書き方",value=f"""
m   ･･･分
h   ･･･時間
d   ･･･日
mo  ･･･月
y   ･･･年
""",inline=False)
    embed.add_field(name="ユーザーIDの入手方法",value=f"""
/banlist
""",inline=False)
    embed.add_field(name="BOT処罰定型文",value=f"""
(member.mention) さん
いつも当サーバーをご利用くださいまして、ありがとうございます。
運営からの大切なお知らせです。
今回、貴方の行動が当サーバーの違反行為に該当するため、口頭注意を行いさせていただくこととなりました。
今後、同様の行動があった場合、より厳しい処置を取ることがありますので、ご注意ください。
納得がいかない場合もあるかと思いますが、ご理解のほど、よろしくお願いいたします。
また、心当たりがない、違反行為をしていないなどの場合、異議申し立てを行うことができます。
異議申し立ては[こちら]({objection})
{botname} バージョン{version} Build{build}
""",inline=False)
    embed.add_field(name="違反レベル",value=f"口頭注意",inline=True)
    embed.add_field(name="違反内容",value=f"ここに reason の入力内容が表示",inline=True)
    await ctx.respond(embed=embed)

# 処罰履歴を削除するスラッシュコマンド
@bot.slash_command(description="処罰履歴を削除する", guild_ids=guild_id)
async def format(ctx: discord.ApplicationContext, action: str, user: discord.Member):
    """
    action:
    - all: 全ての処罰を削除
    - ban, unban, kick, timeout, caution, warn: 特定の処罰を削除
    """
    user_id = user.id
    action = action.lower()

    if action == "all":
        # 全ての処罰履歴を削除
        success = delete_user_data(user_id)
        if success:
            await user.remove_roles(CAUTIONROLE)
            embed=discord.Embed(title=f"ユーザー {user.name} の全ての処罰履歴を削除しました。", color=0x7BAB4F)
            await ctx.respond(embed=embed)
        else:
            embed=discord.Embed(title=f"ユーザー {user.name} に処罰履歴はありません。", color=0x7BAB4F)
            await ctx.respond(embed=embed)

    elif action == "warn":
        # 厳重注意の処罰履歴を削除
        success = delete_user_data(user_id, action)
        if success:
            await user.remove_roles(CAUTIONROLE)
            embed=discord.Embed(title=f"ユーザー {user.name} の「{action}」履歴を削除しました。", color=0x7BAB4F)
            await ctx.respond(embed=embed)
        else:
            embed=discord.Embed(title=f"ユーザー {user.name} の「{action}」の履歴はありません。", color=0x7BAB4F)
            await ctx.respond(embed=embed)

    elif action in ["ban", "unban", "kick", "timeout", "caution"]:
        # 特定の処罰履歴を削除
        success = delete_user_data(user_id, action)
        if success:
            embed=discord.Embed(title=f"ユーザー {user.name} の「{action}」履歴を削除しました。", color=0x7BAB4F)
            await ctx.respond(embed=embed)
        else:
            embed=discord.Embed(title=f"ユーザー {user.name} の「{action}」の履歴はありません。", color=0x7BAB4F)
            await ctx.respond(embed=embed)
    else:
        embed=discord.Embed(title=f"無効な処罰タイプです。all, ban, unban, kick, timeout, caution, warn のいずれかを指定してください。", color=0xE03625)
        await ctx.respond(embed=embed)

# 処罰履歴を手動で追加するコマンド
@bot.slash_command(description="処罰履歴を追加します(処罰を手動でした場合)", guild_ids=guild_id)
@option("action", str, description="ban kick timeout caution warn unban", required=True)
@option("member", discord.Member, description="処罰するメンバー")
@option("reason", str, description="理由", required=False)
@option("bantime", str, description="BAN専用の時間指定(m/h/d/mo/y)", required=False)
@option("time", int, description="タイムアウト時間１(分)単位不要", required=False)
async def add(ctx: discord.ApplicationContext, action, member: discord.Member, reason, time, bantime):
    config = configparser.ConfigParser()
    reason = ' '.join(reason) if reason else '理由は指定されていません'
    member_id = str(member.id)

    if action.lower() == 'ban':
        duration = parse_time(bantime)
        if duration:
            unban_time = datetime.now(timezone.utc) + timedelta(seconds=duration)
            c.execute("INSERT INTO bans VALUES (?, ?, ?, ?)", (member.id, ctx.guild.id, member.name, unban_time.isoformat()))
        else:
            c.execute("INSERT INTO bans VALUES (?, ?, ?, NULL)", (member.id, ctx.guild.id, member.name))
        conn.commit()
        save_config(member.id, 'BAN', reason, bantime)
        embed_dm = discord.Embed(title="運営からの重要なお知らせ",description=f"""
{member.mention} さん
いつも当サーバーをご利用くださいまして、ありがとうございます。
運営からの大切なお知らせです。
今回、当サーバーでの違反行為が複数回、または重い違反があったため、サーバーからのBANを行いさせていただくこととなりました。
サーバーへの再参加はできませんので、ご了承ください。
また、サブアカウントや他のアカウントでの再参加も禁止となりますので、ご注意ください。
納得がいかない場合もあるかと思いますが、ご理解のほど、よろしくお願いいたします。
期間が設定されている場合、期間終了後にサーバーへの再参加が可能です。
また、違反行為をしていないなどの場合、異議申し立てを行うことができます。
異議申し立ては <@{USERID}> までお願いします。
※返事がない場合もあります。複数回にわたってDMを送られた場合、通知オフや無視機能、ブロック機能を使うなどの対応を取ることがあります。
当サーバーをご利用くださいまして、ありがとうございました。
{botname} バージョン{version} Build{build}
""",color=0xE03625)
        embed_dm.add_field(name="違反レベル",value=f"サーバーBAN(複数回にわたる違反行為、または重い違反行為)",inline=True)
        embed_dm.add_field(name="違反内容",value=f"{reason}",inline=True)
        await member.send(embed=embed_dm)
        embed=discord.Embed(title="BAN履歴の追加とDMの送信が正常に実行されました", color=0x7BAB4F)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="対象", value=member.mention, inline=False)
        embed.add_field(name="実行", value=ctx.author, inline=False)
        embed.add_field(name="期間", value=f"{'無期限' if not bantime else bantime}", inline=False)
        embed.add_field(name="理由", value=reason, inline=False)
        await ctx.respond(embed=embed)

    elif action.lower() == 'kick':
        save_config(member.id, 'KICK', reason)
        embed_dm = discord.Embed(title="運営からの重要なお知らせ",description=f"""
{member.mention} さん
運営からの大切なお知らせです。
今回、当サーバーでの違反行為が複数回、または重い違反があったため、サーバーキックを行いさせていただくこととなりました。
サーバーには再度参加できますが、今後、同様の行動があった場合、コミュニティからのBANを行うことがありますので、十分ご注意ください。
納得がいかない場合もあるかと思いますが、ご理解のほど、よろしくお願いいたします。
また、違反行為をしていないなどの場合、異議申し立てを行うことができます。
異議申し立ては <@{USERID}> までお願いします。
※返事がない場合もあります。複数回にわたってDMを送られた場合、通知オフや無視機能、ブロック機能を使うなどの対応を取ることがあります。
当サーバーをご利用くださいまして、ありがとうございました。
{botname} バージョン{version} Build{build}
""",color=0xB53D27)
        embed_dm.add_field(name="違反レベル",value=f"サーバーキック(複数回にわたる違反行為、または重い違反行為)",inline=True)
        embed_dm.add_field(name="違反内容",value=f"{reason}",inline=True)
        await member.send(embed=embed_dm)
        embed=discord.Embed(title="キック履歴の追加とDMの送信が正常に実行されました", color=0x7BAB4F)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="対象", value=member.mention, inline=False)
        embed.add_field(name="実行", value=ctx.author, inline=False)
        embed.add_field(name="理由", value=reason, inline=False)
        await ctx.respond(embed=embed)

    elif action.lower() == 'timeout':
        if time is None:
            embed=discord.Embed(title=f"時間を指定してください。bantimeにしていませんか？例: /silent timeout ユーザー名 時間(分) [理由]", color=0xE03625)
            await ctx.respond(embed=embed)
            return
        try:
            time = int(time)
            reason = ' '.join(reason)
        except ValueError:
            embed=discord.Embed(title=f"時間は数字で指定してください。", color=0xE03625)
            await ctx.respond(embed=embed)
            return
        save_config(member.id, f'TIMEOUT ({time}分)', reason)
        embed_dm = discord.Embed(title="運営からのお知らせ",description=f"""
{member.mention} さん
いつも当サーバーをご利用くださいまして、ありがとうございます。
運営からの大切なお知らせです。
今回、貴方の行動が当サーバーの違反行為に該当するため、タイムアウトを行いさせていただくこととなりました。
今後、同様の行動があった場合、より厳しい処置を取ることがありますので、ご注意ください。
納得がいかない場合もあるかと思いますが、ご理解のほど、よろしくお願いいたします。
また、心当たりがない、違反行為をしていないなどの場合、異議申し立てを行うことができます。
異議申し立ては[こちら]({objection})
{botname} バージョン{version} Build{build}
""",color=0xC16543)
        embed_dm.add_field(name="違反レベル",value=f"{time}分間のタイムアウト",inline=True)
        embed_dm.add_field(name="違反内容",value=f"{reason}",inline=True)
        await member.send(embed=embed_dm)
        embed=discord.Embed(title="タイムアウト履歴の追加とDMの送信が正常に実行されました", color=0x7BAB4F)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="対象", value=member.mention, inline=False)
        embed.add_field(name="実行", value=ctx.author, inline=False)
        embed.add_field(name="時間", value=time, inline=False)
        embed.add_field(name="理由", value=reason, inline=False)
        await ctx.respond(embed=embed)

    elif action.lower() == 'unban':
        save_config(member.id, 'UNBAN', reason)
        embed=discord.Embed(title="UNBAN履歴の追加が正常に実行されました", color=0x7BAB4F)
        embed.add_field(name="対象", value=member_id, inline=False)
        embed.add_field(name="実行", value=ctx.author, inline=False)
        embed.add_field(name="理由", value=reason, inline=False)
        await ctx.respond(embed=embed)

    else:
        await ctx.respond('**⚠️無効なアクションです。ban, unban, kick, timeoutのいずれかを指定してください。**', ephemeral=False)

#--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
#------------------------------------------------------------------------------プライベートスレッド機能----------------------------------------------------------------------------------

class DeleteButton(discord.ui.View):
    def __init__(self, channel: discord.TextChannel):
        super().__init__(timeout=None)
        self.channel = channel

    @discord.ui.button(label="削除", style=discord.ButtonStyle.danger, custom_id="delete_button")
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # プライベートスレッドを削除
        await self.channel.delete()

# 「お問い合わせを開始」ボタンを含むビュー
class TicketButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        

    @discord.ui.button(label="お問い合わせを開始", style=discord.ButtonStyle.success, custom_id="ticket_button")
    async def ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # プライベートスレッドを作成
        user_data = get_user_data(button.user.id)
        guild = button.guild
        category = guild.get_channel(CATEGORY_ID)
        mod_role = discord.utils.get(guild.roles, name=MOD_ROLE_NAME)
        thread_name = f"チケットー{button.user.name}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            button.user: discord.PermissionOverwrite(view_channel=True, read_messages=True, send_messages=True, attach_files=True, read_message_history=True),
            mod_role: discord.PermissionOverwrite(read_messages=True, view_channel=True, manage_channels=True, send_messages=True, attach_files=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, manage_channels=True)
        }

        thread = await guild.create_text_channel(thread_name, overwrites=overwrites, category=category)
        await button.response.send_message(f"✅ {button.user.mention} のチケットが作成されました！: {thread.mention}", ephemeral=True)
        # スレッド内にメッセージを送信
        await thread.send(f"""
{button.user.mention}
ここがお問い合わせです。このチャンネルを削除するには下の削除ボタンを押してください。
※誤って作ってしまった、または運営からの指示がない限り消さないでください。
@{MOD_ROLE_NAME} お問い合わせがあります。対応をお願いします。""",
view=DeleteButton(thread))

@bot.slash_command(description="ｵｰﾅｰ限定です", guild_ids=guild_id)  # `GUILD_ID` は実際のギルドIDに置き換え
@default_permissions(administrator=True)
async def ticket(ctx: discord.ApplicationContext):
    embed=discord.Embed(title="お問い合わせ", color=0x00B2E5)
    embed.add_field(name="下のボタンを押すと、お問い合わせが実行されます", value="""
治安維持と早期問題解決のため、ユーザーIDを記録する場合があります。
違反ユーザーを報告したユーザー情報を漏洩することはありません。""", inline=False)
    await ctx.respond(embed=embed,
                      view=TicketButtonView())

#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------異議申し立て---------------------------------------------------------------------------------------
class AppealButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)


    @discord.ui.button(label="異議申し立て", style=discord.ButtonStyle.success, custom_id="appeal_button")
    async def appeal_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 異議申し立てのModalを表示
        modal = Appeal(title="異議申し立て")
        await button.response.send_modal(modal)

class Appeal(discord.ui.Modal):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.add_item(discord.ui.InputText(
            label="異議申し立ての内容を入力してください。", style=discord.InputTextStyle.long
        ))

    async def callback(self, interaction: discord.Interaction):
        channel = bot.get_channel(APPEAL)
        input=self.children[0].value
        await channel.send(f"@here {interaction.user.mention} さんから異議申し立てがありました。")
        embed=discord.Embed(title="異議申し立て", color=0x7BAB4F)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="実行者", value=interaction.user.mention, inline=False)
        embed.add_field(name="内容", value=input, inline=False)
        await channel.send(embed=embed)
        embed=discord.Embed(title=f"異議申し立てを送信しました。", color=0x7BAB4F)
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.slash_command(description="異議申し立てを行います", guild_ids=guild_id)
@default_permissions(administrator=True)
async def appeal(ctx: discord.ApplicationContext):
    embed=discord.Embed(title="異議申し立て", color=0x00B2E5)
    embed.add_field(name="下のボタンを押すと、異議申し立てが実行されます", value="""
運営からの処罰に異議がある場合、異議申し立てを行うことができます。""", inline=False)
    await ctx.response.send_message(embed=embed, view=AppealButtonView())

#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
#--------------------------------------------------------------------------------フィードバック-------------------------------------------------------------------------------------
class FeedButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)


    @discord.ui.button(label="フィードバック", style=discord.ButtonStyle.success, custom_id="feed_button")
    async def appeal_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # フィードバックのModalを表示
        modal = Feedback(title="フィードバック")
        await button.response.send_modal(modal)

class Feedback(discord.ui.Modal):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.add_item(discord.ui.InputText(
            label="フィードバックの内容を入力してください。", style=discord.InputTextStyle.long
        ))

    async def callback(self, interaction: discord.Interaction):
        channel = bot.get_channel(FEEDBACK)
        input=self.children[0].value
        await channel.send(f"{interaction.user.mention} さんからフィードバックがありました。")
        embed=discord.Embed(title="フィードバック", color=0x7BAB4F)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="実行者", value=interaction.user.mention, inline=False)
        embed.add_field(name="内容", value=input, inline=False)
        await channel.send(embed=embed)
        embed=discord.Embed(title=f"フィードバックを送信しました。", color=0x7BAB4F)
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.slash_command(description="フィードバックを行います", guild_ids=guild_id)
@default_permissions(administrator=True)
async def feedback(ctx: discord.ApplicationContext):
    embed=discord.Embed(title="フィードバック", color=0x00B2E5)
    embed.add_field(name="下のボタンを押すことで、フィードバックを送信できます", value="""
何か改善点や要望、アドバイスがある場合は、是非フィードバックをご送信ください!
※必ずしも採用されるとは限りません。
※技術上、不可能な要望は不採用になる場合があります。""", inline=False)
    await ctx.response.send_message(embed=embed, view=FeedButtonView())

#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------座席作成------------------------------------------------------------------------------------------

class VCButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📕作成する", style=discord.ButtonStyle.success, custom_id="createvc_button")
    async def createvc_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc_leaders = load_vc_data()  # データを読み込む
        guild = button.guild
        category = guild.get_channel(VCCATEGORY_ID)
        vc_name = f"🎙️{button.user.display_name}の部屋"
        vc = await guild.create_voice_channel(vc_name, category=category)
        vc_leaders[vc.id] = button.user.id  # 作成者をリーダーに設定
        save_vc(vc.id, button.user.id)
        await button.response.send_message(f"✅ VC `{vc_name}` を作成しました！: {vc.mention}", ephemeral=True)
    
    @discord.ui.button(label="🧑‍🤝‍🧑人数変更", style=discord.ButtonStyle.success, custom_id="limitvc_button")
    async def limitvc_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = Mylimit(title="人数を変更する")
        await button.response.send_modal(modal)

    @discord.ui.button(label="✏️名前変更", style=discord.ButtonStyle.success, custom_id="renamevc_button")
    async def renamevc_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal2 = rename(title="名前を変更する")
        await button.response.send_modal(modal2)

    @discord.ui.button(label="👑リーダー変更", style=discord.ButtonStyle.success, custom_id="leadervc_button")
    async def leadervc_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal3 = leader(title="リーダーを変更する")
        await button.response.send_modal(modal3)

    @discord.ui.button(label="🔒ロック", style=discord.ButtonStyle.success, custom_id="lockvc_button")
    async def lockvc_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc_leaders = load_vc_data()  # データを読み込む
        vc = button.user.voice.channel if button.user.voice else None
        guild = button.guild
        user_role = discord.utils.get(guild.roles, name=ROLE_NAME)

        if not vc or vc.id not in vc_leaders:
            await button.response.send_message("⚠️ VCが見つかりません。", ephemeral=True)
            return
        if vc_leaders[vc.id] != button.user.id:
            await button.response.send_message("⚠️ あなたはこのVCのリーダーではありません！", ephemeral=True)
            return
        
        channel = button.user.voice.channel  # VCチャンネルを取得

        # VCに現在接続しているメンバーのリストを取得
        connected_members = vc.members
        allowed_users = {member: True for member in connected_members}
        # チャンネルの権限を変更（全員の接続を禁止）
        overwrite = vc.overwrites
        overwrite[user_role] = discord.PermissionOverwrite(connect=False, view_channel=True)  # @member を禁止

        # 現在VCにいるメンバーには接続を許可
        for member in allowed_users:
            overwrite[member] = discord.PermissionOverwrite(connect=True, view_channel=True)
        
        # ブロックされたユーザーを非表示にする
        leader_id = vc_leaders[vc.id]
        blocked = get_block(leader_id)
        blocked_ids = blocked.split(",") if blocked else []
        for user_id in blocked_ids:
            user = guild.get_member(int(user_id))
            if user:
                overwrite[user] = discord.PermissionOverwrite(connect=False, view_channel=False)
                await user.move_to(None)
        
        await vc.edit(overwrites=overwrite)
        await button.response.send_message(f"✅ VC `{channel.name}` をロックしました！", ephemeral=True)

    @discord.ui.button(label="🔑ロック解除", style=discord.ButtonStyle.success, custom_id="unlockvc_button")
    async def unlockvc_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc_leaders = load_vc_data()  # データを読み込む
        vc = button.user.voice.channel if button.user.voice else None
        guild = button.guild
        user_role = discord.utils.get(guild.roles, name=ROLE_NAME)
        if not vc or vc.id not in vc_leaders:
            await button.response.send_message("⚠️ VCが見つかりません。", ephemeral=True)
            return
        if vc_leaders[vc.id] != button.user.id:
            await button.response.send_message("⚠️ あなたはこのVCのリーダーではありません！", ephemeral=True)
            return
        
        channel = button.user.voice.channel  # VCチャンネルを取得


        leader_id = vc_leaders[vc.id]
        blocked = get_block(leader_id)
        blocked_ids = blocked.split(",") if blocked else []
        for user_id in blocked_ids:
            user = guild.get_member(int(user_id))

        await vc.edit(sync_permissions=True)  # 更新
        await button.response.send_message(f"✅ VC `{channel.name}` をロック解除しました！", ephemeral=True)

    @discord.ui.button(label="🗑️VCを削除", style=discord.ButtonStyle.danger, custom_id="deletevc_button")
    async def deletevc_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc_leaders = load_vc_data()  # データを読み込む
        vc = button.user.voice.channel if button.user.voice else None
        if not vc or vc.id not in vc_leaders:
            await button.response.send_message("⚠️ VCが見つかりません。", ephemeral=True)
            return
        if vc_leaders[vc.id] != button.user.id:
            await button.response.send_message("⚠️ あなたはこのVCのリーダーではありません！", ephemeral=True)
            return
        
        del vc_leaders[vc.id]
        delete_save_vc(vc.id, vc_leaders)  # データを更新
        await vc.delete()
        await button.response.send_message("✅ VCを削除しました！", ephemeral=True)
    
    @discord.ui.button(label="🚫ブロック", style=discord.ButtonStyle.danger, custom_id="blockuser_button")
    async def blockuser_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """現在のボイスチャンネルにいるユーザーを取得し、ドロップダウン+表示ボタンを作成"""
        if not button.user.voice or not button.user.voice.channel:
            await button.response.send_message("⚠️ ボイスチャンネルに接続してから実行してください。", ephemeral=True, delete_after=10)
            return

        channel = button.user.voice.channel
        members = channel.members

        if not members:
            await button.response.send_message("⚠️ ボイスチャンネルに誰もいません。", ephemeral=True, delete_after=10)
            return
        
        modal4 = Block(title="ブロック")
        await button.response.send_modal(modal4)

    @discord.ui.button(label="✅️ブロック解除", style=discord.ButtonStyle.success, custom_id="unblockuser_button")
    async def unblockuser_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal5 = Unblock(title="ブロック解除")
        await button.response.send_modal(modal5)

class Block(discord.ui.Modal):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.add_item(discord.ui.InputText(
            label="ブロックするユーザーの名前を入力してください。", style=discord.InputTextStyle.short
        ))

    async def callback(self, interaction: discord.Interaction):
        vc_leaders = load_vc_data()  # データを読み込む
        input_name=self.children[0].value
        member = discord.utils.find(lambda m: m.name == input_name or m.display_name == input_name, interaction.guild.members)
        vc = interaction.user.voice.channel if interaction.user.voice else None
        if not vc or vc.id not in vc_leaders:
            await interaction.response.send_message("⚠️ VCが見つかりません。", ephemeral=True)
            return
        if vc_leaders[vc.id] != interaction.user.id:
            await interaction.response.send_message("⚠️ あなたはこのVCのリーダーではありません！", ephemeral=True)
            return
        try:
            blocked_vc(vc_leaders[vc.id], member.id)
            await member.move_to(None)
            await interaction.response.send_message(f"✅ `{input_name}({member.id})`をブロックしました。", ephemeral=True)
        except discord.HTTPException:
            await interaction.response.send_message("""
⚠️ 名前の変更に失敗しました。
ℹ️ 使えない文字が含まれていませんか?""", ephemeral=True)

class Unblock(discord.ui.Modal):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.add_item(discord.ui.InputText(
            label="ブロック解除するユーザーの名前を入力してください。", style=discord.InputTextStyle.short
        ))

    async def callback(self, interaction: discord.Interaction):
        vc_leaders = load_vc_data()  # データを読み込む
        input_name=self.children[0].value
        member = discord.utils.find(lambda m: m.name == input_name or m.display_name == input_name, interaction.guild.members)
        vc = interaction.user.voice.channel if interaction.user.voice else None
        if not vc or vc.id not in vc_leaders:
            await interaction.response.send_message("⚠️ VCが見つかりません。", ephemeral=True)
            return
        if vc_leaders[vc.id] != interaction.user.id:
            await interaction.response.send_message("⚠️ あなたはこのVCのリーダーではありません！", ephemeral=True)
            return
        try:
            delete_block(vc_leaders[vc.id], member.id)
            await interaction.response.send_message(f"✅ `{input_name}({member.id})`をブロック解除しました。", ephemeral=True)
        except discord.HTTPException:
            await interaction.response.send_message("""
⚠️ 名前の変更に失敗しました。
ℹ️ 使えない文字が含まれていませんか?""", ephemeral=True)

class Mylimit(discord.ui.Modal):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.add_item(discord.ui.InputText(
            label="人数を入力してください。最大:99", style=discord.InputTextStyle.short
        ))

    async def callback(self, interaction: discord.Interaction):
        vc_leaders = load_vc_data()  # データを読み込む
        limit=self.children[0].value
        vc = interaction.user.voice.channel if interaction.user.voice else None
        if not vc or vc.id not in vc_leaders:
            await interaction.response.send_message("⚠️ VCが見つかりません。", ephemeral=True)
            return
        if vc_leaders[vc.id] != interaction.user.id:
            await interaction.response.send_message("⚠️ あなたはこのVCのリーダーではありません！", ephemeral=True)
            return
        try:
            await vc.edit(user_limit=limit)
            await interaction.response.send_message(f"✅ VCの人数制限を `{limit}` 人に変更しました！", ephemeral=True)
        except discord.HTTPException:
            await interaction.response.send_message("""
⚠️ 人数制限の変更に失敗しました。
ℹ️ 数字以外の文字が含まれていませんか?
ℹ️ 数字を全角で入力していませんか?""", ephemeral=True)
            
class rename(discord.ui.Modal):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.add_item(discord.ui.InputText(
            label="VCの名前を入力してください。", style=discord.InputTextStyle.short
        ))

    async def callback(self, interaction: discord.Interaction):
        vc_leaders = load_vc_data()  # データを読み込む
        rename=self.children[0].value
        vc = interaction.user.voice.channel if interaction.user.voice else None
        if not vc or vc.id not in vc_leaders:
            await interaction.response.send_message("⚠️ VCが見つかりません。", ephemeral=True)
            return
        if vc_leaders[vc.id] != interaction.user.id:
            await interaction.response.send_message("⚠️ あなたはこのVCのリーダーではありません！", ephemeral=True)
            return
        try:
            await vc.edit(name=rename)
            await interaction.response.send_message(f"✅ VCの名前を `{rename}` に変更しました！", ephemeral=True)
        except discord.HTTPException:
            await interaction.response.send_message("""
⚠️ 名前の変更に失敗しました。
ℹ️ 使えない文字が含まれていませんか?""", ephemeral=True)

class leader(discord.ui.Modal):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.add_item(discord.ui.InputText(
            label="リーダーの名前を入力してください。", style=discord.InputTextStyle.short
        ))

    async def callback(self, interaction: discord.Interaction):
        vc_leaders = load_vc_data()  # データを読み込む
        input_name=self.children[0].value
        member = discord.utils.find(lambda m: m.name == input_name or m.display_name == input_name, interaction.guild.members)
        vc = interaction.user.voice.channel if interaction.user.voice else None
        if not vc or vc.id not in vc_leaders:
            await interaction.response.send_message("⚠️ VCが見つかりません。", ephemeral=True)
            return
        if vc_leaders[vc.id] != interaction.user.id:
            await interaction.response.send_message("⚠️ あなたはこのVCのリーダーではありません！", ephemeral=True)
            return
        try:
            vc_leaders[vc.id] = member.id
            save_vc(vc.id, member.id)
            await interaction.response.send_message(f"✅ VCのリーダーを `{input_name}({member.id})` に変更しました！", ephemeral=True)
        except discord.HTTPException:
            await interaction.response.send_message("""
⚠️ 名前の変更に失敗しました。
ℹ️ 使えない文字が含まれていませんか?""", ephemeral=True)

@bot.slash_command(description="ｵｰﾅｰ限定です", guild_ids=guild_id)  # `GUILD_ID` は実際のギルドIDに置き換え
@default_permissions(administrator=True)
async def vcos(ctx: discord.ApplicationContext):
    embed=discord.Embed(title="座席作成", color=0x00B2E5)
    embed.add_field(name="下のボタンを押すと、VCが作成できます", value="""
ボタンを押した人がリーダーとなって、VCを作成できます。
人数を変更、リーダー権の譲渡、VCに入れる人数の変更、特定の人のブロック機能などが使えます。
※人数変更は半角数字で入力してください。0にすると人数制限を削除できます。""", inline=False)
    view = VCButton()
    await ctx.respond(embed=embed,
                      view=view)

@bot.event
async def on_ready():
    print(f"{bot.user} を起動しています")
    global vc_leaders
    vc_leaders = load_vc_data()  # データを読み込む
    bot.add_view(TicketButtonView())
    bot.add_view(VCButton())
    bot.add_view(DeleteButton(channel=None))  # 永続的に動作するボタンを登録
    bot.add_view(AppealButtonView())
    bot.add_view(FeedButtonView())
    mem = psutil.virtual_memory()
    available_gb = mem.available / (1024 ** 1)  # KBに変換
    total_gb = mem.total / (1024 ** 1)
    print(f"""
ようこそ
    {bot.user} のﾊﾞｰｼﾞｮﾝ情報
        {bot.user}
            Version {version} (Build {build})
            {dt.year} {username}
            このアプリケーションはモデレーター、運営のためのツールであり、トークン、個人情報を公開してはなりません。
            このアプリケーションは以下のユーザーによって管理されています。
            : {username}
            {bot.user} が使用できる最大物理メモリ
            {total_gb:.0f} KB""")

# Botを起動9
bot.loop.create_task(unban_task())
bot.run(TOKEN)

