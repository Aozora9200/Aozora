# Pycordを読み込む
import discord
import discord.ext.commands
import asyncio
import configparser
from discord.ext import pages
from discord import default_permissions

# アクセストークンを設定
TOKEN = "YOUR_TOKEN"  # 自分のアクセストークンと置換してください
guild_id = ['1234567890987654321'] # 自分のサーバーIDと置換してください
version = "Beta 0.37"
build = "20250217"

# Botの大元となるオブジェクトを生成する
bot = discord.Bot(
    intents=discord.Intents.all(),
    activity=discord.Game("ｾｯﾄｱｯﾌﾟ - ﾊﾞｰｼﾞｮﾝ " + version),
)

PUNISHMENT_MAP = {
    "~📺昭和📺~": "昭和",
    "~🖥平成🖥~": "平成",
    "~📱令和📱~": "令和",
    "~🌠𝑴𝑬𝑴𝑩𝑬𝑹🌠~": "メンバー",
}

# Configファイル操作用関数
def get_user_drive(user_id: int):
    config = configparser.ConfigParser()
    config.read("config.ini")

    if "Users" not in config or str(user_id) not in config["Users"]:
        return None

    return config["Users"][str(user_id)]

def save_user_to_config(user_id: int, drive: str):
    config = configparser.ConfigParser()
    config.read("config.ini")

    if "Users" not in config:
        config["Users"] = {}

    # ユーザーIDをキーにしてドライブを記録
    drive_name = PUNISHMENT_MAP.get(drive, drive)
    config["Users"][str(user_id)] = drive_name

    # 設定をファイルに保存
    with open("config.ini", "w") as configfile:
        config.write(configfile)

# ドロップダウンメニューの定義
class DriveSelection(discord.ui.Select):
    def __init__(self, user: discord.User, thread: discord.TextChannel):
        self.thread = thread
        self.user = user
        options = [
            discord.SelectOption(label="~📺昭和📺~", description="~📺昭和📺~を選択"),
            discord.SelectOption(label="~🖥平成🖥~", description="~🖥平成🖥~を選択"),
            discord.SelectOption(label="~📱令和📱~", description="~📱令和📱~を選択"),
        ]
        super().__init__(placeholder="好きな世代を選択してください", options=options, custom_id="drive_selection")

    async def callback(self, interaction: discord.Interaction):
        selected_drive = self.values[0]
        role = discord.utils.get(interaction.guild.roles, name=selected_drive)
        role2 = discord.utils.get(interaction.guild.roles, name="~🌠𝑴𝑬𝑴𝑩𝑬𝑹🌠~")

        if not role:
            role = await interaction.guild.create_role(name=selected_drive)
            role2 = discord.utils.get(interaction.guild.roles, name="~🌠𝑴𝑬𝑴𝑩𝑬𝑹🌠~")

        # ロール付与処理にエラーハンドリングを追加
        try:
            await self.user.add_roles(role)
        except discord.Forbidden:
            # 権限が不足している場合
            await interaction.response.send_message(
                f"⚠️ ﾛｰﾙ '{selected_drive}' を付与する権限がありません。管理者に確認してください。",
                ephemeral=True
            )
            return
        except Exception as e:
            # その他のエラー
            await interaction.response.send_message(
                f"⚠️ ﾛｰﾙ '{selected_drive}' の付与中にｴﾗｰが発生しました: {str(e)}",
                ephemeral=True
            )
            return

        # ロールを付与
        await interaction.response.edit_message(content="ｲﾝｽﾄｰﾙ中...", view=None, embed=None)
        await self.user.add_roles(role, role2)
        # ConfigファイルにユーザーIDとドライブを記録
        save_user_to_config(self.user.id, selected_drive)
        await asyncio.sleep(3)

        # 「ｾｯﾄｱｯﾌﾟ終了」と完了ボタンを表示
        await interaction.followup.send(
            content="ｾｯﾄｱｯﾌﾟは終了しました。5秒後に自動終了します...",
            view=CompleteButton(interaction.channel)
        )
        await asyncio.sleep(5)
        try:
            await self.thread.delete()
        except discord.NotFound:
            pass  # 既に削除済みの場合

# セットアッププロパティビュー
class SetupPropertyView(discord.ui.View):
    def __init__(self, user: discord.User, thread: discord.TextChannel):
        super().__init__(timeout=60)  # 60秒で自動削除
        self.user = user
        self.thread = thread

        # ドライブ切り替え用のドロップダウンを追加
        self.add_item(DriveSwitch(user, thread))

    @discord.ui.button(label="ﾊﾞｰｼﾞｮﾝ情報", style=discord.ButtonStyle.primary, custom_id="version_info")
    async def version_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        # バージョン情報を表示
        await button.response.send_message(f"""
Aozora -Setup のﾊﾞｰｼﾞｮﾝ情報
        Aozora -Setup
            Version {version} (Build {build})
            2025 Hatsukari
            このアプリケーションはモデレーター、運営のためのツールであり、コード、個人情報を公開してはなりません。
            Aozora -Setup が使用できる最大物理メモリ
            -- KB
               """, ephemeral=True)

    async def on_timeout(self):
        # タイムアウト時にスレッドを削除
        try:
            await self.thread.delete()
        except discord.NotFound:
            pass  # 既に削除済みの場合


# ドライブ切り替え用セレクトメニュー
class DriveSwitch(discord.ui.Select):
    def __init__(self, user: discord.User, thread: discord.TextChannel):
        self.user = user
        self.thread = thread
        options = [
            discord.SelectOption(label="~📺昭和📺~", description="~📺昭和📺~を選択"),
            discord.SelectOption(label="~🖥平成🖥~", description="~🖥平成🖥~を選択"),
            discord.SelectOption(label="~📱令和📱~", description="~📱令和📱~を選択"),
        ]
        super().__init__(placeholder="切り替えたいﾛｰﾙを選択してください", options=options, custom_id="drive_switch")

    async def callback(self, interaction: discord.Interaction):
        selected_drive = self.values[0]
        role = discord.utils.get(interaction.guild.roles, name=selected_drive)
        role2 = discord.utils.get(interaction.guild.roles, name="~🌠𝑴𝑬𝑴𝑩𝑬𝑹🌠~")

        if not role:
            role = await interaction.guild.create_role(name=selected_drive)

        try:
            # ユーザーの既存ロールを削除し、新しいロールを付与
            await interaction.response.edit_message(content="ﾌｧｲﾙを移動中...", view=None, embed=None)
            for r in self.user.roles:
                if r.name in ["~📺昭和📺~", "~🖥平成🖥~", "~📱令和📱~", "~🌠𝑴𝑬𝑴𝑩𝑬𝑹🌠~"]:
                    await self.user.remove_roles(r)
            await asyncio.sleep(3)
            await self.user.add_roles(role, role2)
            save_user_to_config(self.user.id, selected_drive)
            await asyncio.sleep(2)

            await interaction.followup.send(f"ﾄﾞﾗｲﾌﾞが `{selected_drive}` に切り替えられました。")
            await asyncio.sleep(5)
            await self.thread.delete()
        except discord.Forbidden:
            await interaction.followup.send("⚠️ ﾄﾞﾗｲﾌﾞの切り替えに必要な権限がありません。ﾌｨｰﾄﾞﾊﾞｯｸをご送信ください。")
        except Exception as e:
            await interaction.followup.send(f"⚠️ ﾄﾞﾗｲﾌﾞの切り替え中にｴﾗｰが発生しました。ﾌｨｰﾄﾞﾊﾞｯｸをご送信ください。: {str(e)}")

# 完了ボタンの定義
class CompleteButton(discord.ui.View):
    def __init__(self, channel: discord.TextChannel):
        super().__init__(timeout=None)
        self.channel = channel

    @discord.ui.button(label="完了", style=discord.ButtonStyle.danger, custom_id="complete_button")
    async def complete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # プライベートスレッドを削除
        await self.channel.delete()

# ページネーションビュー
class Paginator(discord.ui.View):
    def __init__(self, pages: list, user: discord.User, thread: discord.TextChannel):
        super().__init__(timeout=300)
        self.pages = pages
        self.current_page = 0
        self.user = user  # ユーザーを保存
        self.thread = thread

        # 初期状態で「前へ」ボタンを無効化
        self.previous_button.disabled = True
        if len(self.pages) == 1:
            self.next_button.disabled = True

    @discord.ui.button(label="< 戻る(B)", style=discord.ButtonStyle.primary, custom_id="previous_button")
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        if self.current_page == 0:
            self.previous_button.disabled = True
        self.next_button.disabled = False
        await button.response.edit_message(embed=self.pages[self.current_page], view=self)

    @discord.ui.button(label="次へ(N) >", style=discord.ButtonStyle.primary, custom_id="next_button")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        if self.current_page == len(self.pages) - 1:
            self.next_button.disabled = True
        # Page 3 にドロップダウンを追加
            view = discord.ui.View(timeout=None)
            view.add_item(DriveSelection(self.user, self.thread))
            await button.response.edit_message(embed=self.pages[self.current_page], view=view)
        else:
            self.previous_button.disabled = False
            await button.response.edit_message(embed=self.pages[self.current_page], view=self)

    async def on_timeout(self):
        # タイムアウト時にスレッドを削除
        try:
            await self.thread.delete()
        except discord.NotFound:
            pass  # 既に削除済みの場合

# 「ｾｯﾄｱｯﾌﾟを開始」ボタンを含むビュー
class SetupButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        

    @discord.ui.button(label="ｾｯﾄｱｯﾌﾟを開始", style=discord.ButtonStyle.success, custom_id="setup_button")
    async def setup_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # プライベートスレッドを作成
        user_drive = get_user_drive(button.user.id)
        guild = button.guild
        thread_name = f"ｾｯﾄｱｯﾌﾟ-{button.user.name}"
        thread = await guild.create_text_channel(thread_name, overwrites={
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            button.user: discord.PermissionOverwrite(read_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True)
        })

        # セットアップ済みユーザーの場合
        if user_drive:
            embed = discord.Embed(
                title="ｾｯﾄｱｯﾌﾟのﾌﾟﾛﾊﾟﾃｨ",
                description=f"現在の設定: `{user_drive}`\nﾛｰﾙを切り替えるか、ﾊﾞｰｼﾞｮﾝ情報を確認できます。",
                color=discord.Color.blue(),
            )
            view = SetupPropertyView(button.user, thread)
            await button.response.send_message(f"✅ {button.user.mention} ﾌﾟﾛﾊﾟﾃｨはここから: {thread.mention}", ephemeral=True)
            await thread.send(f"{button.user.mention}, ここでﾌﾟﾛﾊﾟﾃｨを表示しています。1分経過後、このﾁｬﾝﾈﾙは自動的に削除されます。", embed=embed, view=view)
        else:
        # 新規セットアップユーザーの場合

        # スレッド内にセットアップ開始メッセージを送信
            await button.response.send_message(f"✅ {button.user.mention} 認証はここから: {thread.mention}", ephemeral=True)
            await thread.send(f"{button.user.mention}, ここでｾｯﾄｱｯﾌﾟを開始します。5分経過後、このﾁｬﾝﾈﾙは自動的に削除されます。")

        # setupコマンドを実行
            await setup_in_thread(thread, button.user)

@bot.event
async def on_ready():
    print(f"Bot is ready! Logged in as {bot.user}")
    # 再起動時にボタンとドロップダウンを登録
    bot.add_view(SetupButtonView())
    bot.add_view(CompleteButton(channel=None))  # 永続的に動作するボタンを登録


# setupコマンドを実行する関数
async def setup_in_thread(thread: discord.TextChannel, user: discord.User, versions=version):

    message2 = await thread.send("お待ちください...")

    # ページとなるEmbedを作成
    pages = [
        discord.Embed(title="**利用規約**", description="""
以下利用規約
""", color=discord.Color.dark_gray()),
        discord.Embed(title="**ｻｰﾊﾞｰﾙｰﾙ**", description="""
**ルール**
```python
以下ルール
```
同意される方は次へを押してください""", color=discord.Color.dark_gray()),
        discord.Embed(title="好きな世代の選択", description="""
好きな世代を選択してください。
※どちらを選んでも変わりません。""", color=discord.Color.dark_gray()),
    ]

    # ページネーションビューを作成して送信
    view = Paginator(pages, user, thread)
    await message2.edit(f"ｾｯﾄｱｯﾌﾟ" + versions, embed=pages[0], view=view)



# setupコマンドを実装
@bot.slash_command(description="ｾｯﾄｱｯﾌﾟを開始します", guild_ids=guild_id)  # `GUILD_ID` は実際のギルドIDに置き換え
@default_permissions(administrator=True) # 管理者権限が必要。これを消せば誰でも使える
async def setup(ctx: discord.ApplicationContext):
    message1 = await ctx.respond("お待ちください...")

    # ページとなるEmbedを作成
    pages = [
        discord.Embed(title="Page 1", description="This is the first page", color=discord.Color.blue()),
        discord.Embed(title="Page 2", description="This is the second page", color=discord.Color.green()),
        discord.Embed(title="Page 3", description="This is the third page", color=discord.Color.red()),
    ]

    # ページネーションビューを作成して送信
    view = Paginator(pages)
    await message1.edit(content="ｾｯﾄｱｯﾌﾟ", embed=pages[0], view=view)


@bot.slash_command(description="ｵｰﾅｰ限定です", guild_ids=guild_id)  # `GUILD_ID` は実際のギルドIDに置き換え
@default_permissions(administrator=True)
async def win(ctx: discord.ApplicationContext):
    await ctx.respond(
        """
ｾｯﾄｱｯﾌﾟ
```python
認証する際は「ｾｯﾄｱｯﾌﾟを開始」を押してください。
ﾌﾟﾗｲﾍﾞｰﾄﾁｬﾝﾈﾙが作成され、ｾｯﾄｱｯﾌﾟが開始されます。
治安維持のため、ﾕｰｻﾞｰIDを記録する場合があります。
IPｱﾄﾞﾚｽや個人情報を入手することはありません。
すでにｾｯﾄｱｯﾌﾟ済みの方は、「ｾｯﾄｱｯﾌﾟを開始」を押すとﾌﾟﾛﾊﾟﾃｨが表示されます。
```
        """,
        view=SetupButtonView()  # 「ｾｯﾄｱｯﾌﾟを開始」ボタンを表示
    )

# Botを起動9
bot.run(TOKEN)

