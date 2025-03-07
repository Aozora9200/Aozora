# Pycord (Pycord v2, SQLiteでBAN期間管理)
# Pycordを読み込む
import configparser
import asyncio
import sqlite3
import psutil
import os
import re
from os.path import join, dirname
from dotenv import load_dotenv
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
version = "Beta 1.0  Beta-1"
build = "20250228"
dt = datetime.today()
bot = "envtest"

print(f"{bot} を起動しています")
mem = psutil.virtual_memory()
available_gb = mem.available / (1024 ** 1)  # KBに変換
total_gb = mem.total / (1024 ** 1)
print(f"""
ようこそ
    {bot} のﾊﾞｰｼﾞｮﾝ情報
        {bot}
            Version {version} (Build {build})
            {dt.year} {username}
            このアプリケーションはモデレーター、運営のためのツールであり、トークン、個人情報を公開してはなりません。
            このアプリケーションは以下のユーザーによって管理されています。
            : {username}
            {bot} が使用できる最大物理メモリ
            {total_gb:.0f} KB""")
print(f"""
------ENVTEST: {bot} 読込結果------
    BOTNAME: {botname}
    TOKEN: {TOKEN}
    GUILD_ID: {guild_id}
    CATEGORY_ID: {CATEGORY_ID}
    VCCATEGORY_ID: {VCCATEGORY_ID}
    OBJECTION: {objection}
    MOD_ROLE_NAME: {MOD_ROLE_NAME}
    ROLE_NAME: {ROLE_NAME}
    USERNAME: {username}
---------------------------------
""")
    
