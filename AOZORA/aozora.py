# Pycordを読み込む
import discord
import discord.ext.commands
import psutil
import configparser
import os
from discord.ext import pages
from discord.ui import Select, Button, View
from discord import default_permissions
from datetime import timedelta

# アクセストークンを設定
TOKEN = "YOUR_TOKEN"  # 自分のアクセストークンと置換してください
guild_id = ['12345678987654321'] # 自分のサーバーIDと置換してください
CATEGORY_ID = 12345678987654321 # 自分のサーバーのチケット専用カテゴリのカテゴリIDと置換してください
VCCATEGORY_ID = 12345678987654321 # 自分のサーバーのVC専用カテゴリのカテゴリIDと置換してください
MOD_ROLE_NAME = "MODERATOR" # 自分のサーバーのモデレーターロール名と置換してください
ROLE_NAME = "member" # 自分のサーバーのメンバーロール名と置換してください
version = "Beta 0.53"
build = "20250217"
intents = discord.Intents.default()
intents.guilds = True
intents.voice_states = True  # ボイスチャンネルの情報を取得するために必要
intents.members = True  # メンバー情報取得のために必要

# Botの大元となるオブジェクトを生成する
bot = discord.Bot(
    intents=discord.Intents.all(),
    activity=discord.Game("ﾊﾞｰｼﾞｮﾝ " + version),
)

# VCのリーダーを管理する辞書 {vc_id: leader_id}
vc_leaders = {}

# 処罰名の対応表
PUNISHMENT_MAP = {
    "verbal1": "口頭注意",
    "verbal2": "厳重注意",
    "ban": "BAN",
    "unban": "UNBAN",
    "kick": "KICK",
    "timeout": "TIMEOUT",
}

# データを保存するファイルのパス
DATA_FILE = "vc_leaders.ini"

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
def save_config(user_id: int, action: str, reason: str = ""):
    config = configparser.ConfigParser()
    config.read("aozora.ini")

    if "Users" not in config:
        config["Users"] = {}
    
   # 既存データを取得して新しいデータを追記
    existing_data = config["Users"].get(str(user_id), "")
    new_entry = f"{action}:{reason}" if reason else action

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

# 処罰コマンド
@bot.slash_command(description="処罰", guild_ids=guild_id)
async def aozora(ctx: discord.ApplicationContext, action: str, member: discord.Member, reason: str = None, duration: int = None):
    config = configparser.ConfigParser()
    reason = ' '.join(reason) if reason else '理由は指定されていません'
    member_id = str(member.id)

    if action.lower() == 'ban':
        save_config(member.id, 'BAN', reason)
        await send_dm(member, f"""
{member.mention} さん
いつも当サーバーをご利用くださいまして、ありがとうございます。
運営からの大切なお知らせです。
今回、当サーバーでの違反行為が複数回、または重い違反があったため、サーバーからのBANを行いさせていただくこととなりました。
サーバーへの再ログインはできませんので、ご了承ください。
また、サブアカウントや他のアカウントでの再ログインも禁止となりますので、ご注意ください。
納得がいかない場合もあるかと思いますが、ご理解のほど、よろしくお願いいたします。
違反レベル: サーバーBAN(複数回にわたる違反行為、または重い違反行為)
違反内容: {reason}
また、違反行為をしていないなどの場合、異議申し立てを行うことができます。
異議申し立ては運営までお願いします。
※返事がない場合もあります。複数回にわたってDMを送られた場合、通知オフやブロックなどの対応を取ることがあります。
当サーバーをご利用いただきまして、ありがとうございました。
バージョン{version} Build{build}""")
        await ctx.guild.ban(member, reason=reason)
        await ctx.respond(f'{member.mention} をBANしました。理由: {reason}', ephemeral=False)

    elif action.lower() == 'kick':
        save_config(member.id, 'KICK', reason)
        await send_dm(member, f"""
{member.mention} さん
いつも当サーバーをご利用くださいまして、ありがとうございます。
運営からの大切なお知らせです。
今回、当サーバーでの違反行為が複数回、または重い違反があったため、サーバーキックを行いさせていただくこととなりました。
サーバーには再度ログインできますが、今後、同様の行動があった場合、コミュニティからのBANを行うことがありますので、十分ご注意ください。
納得がいかない場合もあるかと思いますが、ご理解のほど、よろしくお願いいたします。
違反レベル: サーバーキック(複数回にわたる違反行為、または重い違反行為)
違反内容: {reason}
また、違反行為をしていないなどの場合、異議申し立てを行うことができます。
異議申し立ては運営までお願いします。
※返事がない場合もあります。複数回にわたってDMを送られた場合、通知オフやブロックなどの対応を取ることがあります。
バージョン{version} Build{build}""")
        await ctx.guild.kick(member, reason=reason)
        await ctx.respond(f'{member.mention} をKickしました。理由: {reason}', ephemeral=False)

    elif action.lower() == 'timeout':
        if duration is None:
            await ctx.respond('時間を指定してください。例: /aozora timeout ユーザー名 時間 [理由]', ephemeral=False)
            return
        try:
            duration = int(duration)
            reason = ' '.join(reason)
        except ValueError:
            await ctx.respond('時間は数字で指定してください。', ephemeral=False)
            return
        await member.timeout(discord.utils.utcnow() + timedelta(minutes=duration))
        save_config(member.id, f'TIMEOUT ({duration}分)', reason)
        await send_dm(member, f"""
{member.mention} さん
いつも当サーバーをご利用くださいまして、ありがとうございます。
運営からの大切なお知らせです。
今回、貴方の行動が当サーバーの違反行為に該当するため、タイムアウトを行いさせていただくこととなりました。
今後、同様の行動があった場合、より厳しい処置を取ることがありますので、ご注意ください。
納得がいかない場合もあるかと思いますが、ご理解のほど、よろしくお願いいたします。
違反レベル: {duration}分間のタイムアウト
違反内容: {reason}
また、心当たりがない、違反行為をしていないなどの場合、異議申し立てを行うことができます。
バージョン{version} Build{build}""")
        await ctx.respond(f'{member.mention} をタイムアウトしました ({duration}分)。理由: {reason}', ephemeral=False)

    elif action.lower() in ['verbal1', 'verbal2']:
        level = '口頭注意' if action.lower() == 'verbal1' else '厳重注意'
        save_config(member.id, f'{level}', reason)
        await send_dm(member, f"""
{member.mention} さん
いつも当サーバーをご利用くださいまして、ありがとうございます。
運営からの大切なお知らせです。
今回、貴方の行動が当サーバーの違反行為に該当するため、口頭注意/厳重注意を行いさせていただくこととなりました。
今後、同様の行動があった場合、より厳しい処置を取ることがありますので、ご注意ください。
納得がいかない場合もあるかと思いますが、ご理解のほど、よろしくお願いいたします。
違反レベル: {level}
違反内容: {reason}
また、心当たりがない、違反行為をしていないなどの場合、異議申し立てを行うことができます。
バージョン{version} Build{build} """)
        if action.lower() == 'verbal2':
            role = discord.utils.get(ctx.guild.roles, name='~⚠️𝑪𝑨𝑹𝑬𝑭𝑼𝑳⚠️~')
            if role:
                await member.add_roles(role)
        await ctx.respond(f'{member.mention} に{level}を実行しました。内容: {reason}', ephemeral=False)

    elif action.lower() == 'unban':
        await ctx.guild.unban(member, reason=reason)
        save_config(member.id, 'UNBAN', reason)
        await send_dm(member, f"""
{member.mention} さん
いつも当サーバーをご利用くださいまして、ありがとうございます。
運営からの大切なお知らせです。
先ほど、貴方のBANを解除いたしましたので、ご連絡をさせていただきました。
内容: {reason}
返信や異議申し立ては運営までお願いします。
※返事がない場合もあります。複数回にわたってDMを送られた場合、通知オフやブロックなどの対応を取ることがあります。
バージョン{version} Build{build}""")
        await ctx.respond(f'{member.mention} のBANを解除しました。理由: {reason}', ephemeral=False)
    
    elif action.lower() == 'version':
        mem = psutil.virtual_memory()
        available_gb = mem.available / (1024 ** 1)  # KBに変換
        total_gb = mem.total / (1024 ** 1)
        await ctx.respond(f"""
Aozora のﾊﾞｰｼﾞｮﾝ情報
        Aozora
            Version {version} (Build {build})
            2025 Hatsukari
            このアプリケーションはモデレーター、運営のためのツールであり、トークン、個人情報を公開してはなりません。
            Aozora が使用できる最大物理メモリ
            {total_gb:.2f} KB
               """, ephemeral=False)

    else:
        await ctx.respond('無効なアクションです。ban, kick, timeout, verbal1, verbal2, versionのいずれかを指定してください。', ephemeral=False)

# 処罰履歴を表示するコマンド
@bot.slash_command(description="処罰履歴", guild_ids=guild_id)
async def criminal(ctx: discord.ApplicationContext, user: discord.Member):

    user_data = get_user_data(user.id)
    if user_data:
        await ctx.respond(f"ユーザー {user.name} の処罰履歴:\n{user_data}", ephemeral=False)
    else:
        await ctx.respond(f"ユーザー {user.name} に処罰履歴はありません。", ephemeral=False)

@bot.slash_command(description="使い方", guild_ids=guild_id)
async def help(ctx: discord.ApplicationContext):
    await ctx.respond(f"""```python
使い方
/aozora -このツールのベースコマンドです。
    ┠ ban ユーザー名 reason(理由) -ユーザーをBANします。
    ┠ unban ユーザー名 reason(理由) -ユーザーのBANを解除します。
    ┠ kick ユーザー名 reason(理由) -ユーザーをKICKします。
    ┠ timeout ユーザー名 duration(時間) reason(理由) -ユーザーをタイムアウトします。
    ┠ verbal1 ユーザー名 reason(注意内容) -ユーザーに口頭注意をします。
    ┠ verbal2 ユーザー名 reason(注意内容) -ユーザーに厳重注意をします。危険人物ロールが付与されます。
    ┠ version -Aozoraのﾊﾞｰｼﾞｮﾝ情報を表示します。
/criminal ユーザー名 -ユーザーの処罰履歴を表示します。
/help -このヘルプを表示します。
/format ユーザー名 action(処罰) -ユーザーの処罰履歴を削除します。
    ┠ action: all -全ての処罰を削除
    ┠ action: ban, kick, timeout, verbal1, verbal2 -特定の処罰を削除
    
    なお、口頭注意、厳重注意は、ユーザーにDMで通知されます。
    以下定型文----------------------------------------------------
    いつも当サーバーをご利用くださいまして、ありがとうございます。
    運営からの大切なお知らせです。
    今回、貴方の行動が当サーバーの違反行為に該当するため、口頭注意/厳重注意を行いさせていただくこととなりました。
    今後、同様の行動があった場合、より厳しい処置を取ることがありますので、ご注意ください。
    納得がいかない場合もあるかと思いますが、ご理解のほど、よろしくお願いいたします。
    違反内容: (注意内容)
    また、心当たりがない、違反行為をしていないなどの場合、異議申し立てを行うことができます。
    -------------------------------------------------------------
    ```""", ephemeral=False)

# 処罰履歴を削除するスラッシュコマンド
@bot.slash_command(description="処罰履歴を削除する", guild_ids=guild_id)
async def format(ctx: discord.ApplicationContext, action: str, user: discord.Member):
    """
    action:
    - all: 全ての処罰を削除
    - ban, unban, kick, timeout, verbal1, verbal2: 特定の処罰を削除
    """
    user_id = user.id
    action = action.lower()

    if action == "all":
        # 全ての処罰履歴を削除
        success = delete_user_data(user_id)
        if success:
            await ctx.respond(f"ユーザー {user.name} の全ての処罰履歴を削除しました。")
        else:
            await ctx.respond(f"ユーザー {user.name} に処罰履歴はありません。")
    elif action in ["ban", "unban", "kick", "timeout", "verbal1", "verbal2"]:
        # 特定の処罰履歴を削除
        success = delete_user_data(user_id, action)
        if success:
            await ctx.respond(f"ユーザー {user.name} の「{action}」履歴を削除しました。")
        else:
            await ctx.respond(f"ユーザー {user.name} に「{action}」の履歴はありません。")
    else:
        await ctx.respond(f"無効な処罰タイプです。all, ban, unban, kick, timeout, verbal1, verbal2 のいずれかを指定してください。")

# 処罰履歴を手動で追加するコマンド
@bot.slash_command(description="処罰履歴を追加します", guild_ids=guild_id)
async def add(ctx: discord.ApplicationContext, action: str, member: discord.Member, reason: str = None, duration: int = None):
    config = configparser.ConfigParser()
    reason = ' '.join(reason) if reason else '理由は指定されていません'
    member_id = str(member.id)

    if action.lower() == 'ban':
        save_config(member.id, 'BAN', reason)
        await send_dm(member, f"""
{member.mention} さん
いつも当サーバーをご利用くださいまして、ありがとうございます。
運営からの大切なお知らせです。
今回、当サーバーでの違反行為が複数回、または重い違反があったため、サーバーからのBANを行いさせていただくこととなりました。
サーバーへの再ログインはできませんので、ご了承ください。
また、サブアカウントや他のアカウントでの再ログインも禁止となりますので、ご注意ください。
納得がいかない場合もあるかと思いますが、ご理解のほど、よろしくお願いいたします。
違反レベル: サーバーBAN(複数回にわたる違反行為、または重い違反行為)
違反内容: {reason}
また、違反行為をしていないなどの場合、異議申し立てを行うことができます。
異議申し立ては運営までお願いします。
※返事がない場合もあります。複数回にわたってDMを送られた場合、通知オフやブロックなどの対応を取ることがあります。
当サーバーをご利用いただきまして、ありがとうございました。
バージョン{version} Build{build}""")
        await ctx.respond(f'{member.mention} をBANした旨の連絡を送信し、犯歴に追加しました。理由: {reason}', ephemeral=False)

    elif action.lower() == 'kick':
        save_config(member.id, 'KICK', reason)
        await send_dm(member, f"""
{member.mention} さん
いつも当サーバーをご利用くださいまして、ありがとうございます。
運営からの大切なお知らせです。
今回、当サーバーでの違反行為が複数回、または重い違反があったため、サーバーキックを行いさせていただくこととなりました。
サーバーには再度ログインできますが、今後、同様の行動があった場合、コミュニティからのBANを行うことがありますので、十分ご注意ください。
納得がいかない場合もあるかと思いますが、ご理解のほど、よろしくお願いいたします。
違反レベル: サーバーキック(複数回にわたる違反行為、または重い違反行為)
違反内容: {reason}
また、違反行為をしていないなどの場合、異議申し立てを行うことができます。
異議申し立ては運営までお願いします。
※返事がない場合もあります。複数回にわたってDMを送られた場合、通知オフやブロックなどの対応を取ることがあります。
バージョン{version} Build{build}""")
        await ctx.respond(f'{member.mention} をKickした旨の連絡を送信し、犯歴に追加しました。理由: {reason}', ephemeral=False)

    elif action.lower() == 'timeout':
        if duration is None:
            await ctx.respond('時間を指定してください。例: /aozora timeout ユーザー名 時間 [理由]', ephemeral=False)
            return
        try:
            duration = int(duration)
            reason = ' '.join(reason)
        except ValueError:
            await ctx.respond('時間は数字で指定してください。', ephemeral=False)
            return
        save_config(member.id, f'TIMEOUT ({duration}分)', reason)
        await send_dm(member, f"""
{member.mention} さん
いつも当サーバーをご利用くださいまして、ありがとうございます。
運営からの大切なお知らせです。
今回、貴方の行動が当サーバーの違反行為に該当するため、タイムアウトを行いさせていただくこととなりました。
今後、同様の行動があった場合、より厳しい処置を取ることがありますので、ご注意ください。
納得がいかない場合もあるかと思いますが、ご理解のほど、よろしくお願いいたします。
違反レベル: {duration}分間のタイムアウト
違反内容: {reason}
また、心当たりがない、違反行為をしていないなどの場合、異議申し立てを行うことができます。
バージョン{version} Build{build}""")
        await ctx.respond(f'{member.mention} を {duration}分間タイムアウトした旨の連絡を送信し、犯歴に追加しました。理由: {reason}', ephemeral=False)

    elif action.lower() in ['verbal1', 'verbal2']:
        level = '口頭注意' if action.lower() == 'verbal1' else '厳重注意'
        save_config(member.id, f'{level}', reason)
        if action.lower() == 'verbal2':
            role = discord.utils.get(ctx.guild.roles, name='~⚠️𝑪𝑨𝑹𝑬𝑭𝑼𝑳⚠️~')
            if role:
                await member.add_roles(role)
        await ctx.respond(f'{member.mention} に{level}の犯歴を追加しました。内容: {reason}', ephemeral=False)

    elif action.lower() == 'unban':
        save_config(member.id, 'UNBAN', reason)
        await send_dm(member, f"""
{member.mention} さん
いつも当サーバーをご利用くださいまして、ありがとうございます。
運営からの大切なお知らせです。
先ほど、貴方のBANを解除いたしましたので、ご連絡をさせていただきました。
内容: {reason}
返信や異議申し立ては運営までお願いします。
※返事がない場合もあります。複数回にわたってDMを送られた場合、通知オフやブロックなどの対応を取ることがあります。
バージョン{version} Build{build}""")
        await ctx.respond(f'{member.mention} のBANを解除した旨の連絡を送信し、履歴に追加しました。理由: {reason}', ephemeral=False)

    else:
        await ctx.respond('無効なアクションです。ban, unban, kick, timeout, verbal1, verbal2, versionのいずれかを指定してください。', ephemeral=False)

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
※誤って作ってしまった、または運営からの指示がない限り消さないでください。""",
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
    mem = psutil.virtual_memory()
    available_gb = mem.available / (1024 ** 1)  # KBに変換
    total_gb = mem.total / (1024 ** 1)
    print(f"""
ようこそ
    {bot.user} のﾊﾞｰｼﾞｮﾝ情報
        {bot.user}
            Version {version} (Build {build})
            2025 Hatsukari
            このアプリケーションはモデレーター、運営のためのツールであり、トークン、個人情報を公開してはなりません。
            {bot.user} が使用できる最大物理メモリ
            {total_gb:.2f} KB""")

# Botを起動9
bot.run(TOKEN)

