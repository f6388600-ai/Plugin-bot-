import os
import asyncio
import time
import datetime

from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties

from motor.motor_asyncio import AsyncIOMotorClient

from fastapi import FastAPI
import uvicorn
import threading

# =========================
# CONFIG
# =========================

TOKEN = "8523644793:AAGqHoxIdblgyCKvucU-5exjaaSweSaFvEc"
ADMIN_ID = 7793812954
MONGO_URL = "mongodb+srv://botuser:<db_password>@cluster0.xdoda3m.mongodb.net/?appName=Cluster0"

BASE_DIR = "storage"
PLUGIN_DIR = "plugins"

os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(PLUGIN_DIR, exist_ok=True)

# =========================
# BOT + DB
# =========================

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

client = AsyncIOMotorClient(MONGO_URL)
db = client["saas"]

users = db["users"]
files_db = db["files"]
system_db = db["system"]

# =========================
# UPTIME PERSISTENT SYSTEM (IMPORTANT)
# =========================

async def init_uptime():
    doc = await system_db.find_one({"key": "uptime"})

    if not doc:
        await system_db.insert_one({
            "key": "uptime",
            "start": time.time()
        })

async def get_uptime():
    doc = await system_db.find_one({"key": "uptime"})
    return time.time() - doc["start"]

# =========================
# FASTAPI (RENDER KEEP ALIVE)
# =========================

app = FastAPI()

@app.get("/")
def home():
    return {"status": "alive"}

@app.get("/ping")
def ping():
    return {"pong": True}

def run_web():
    uvicorn.run(app, host="0.0.0.0", port=10000)

# =========================
# USER INIT
# =========================

async def init_user(user):
    await users.update_one(
        {"id": user.id},
        {"$setOnInsert": {
            "id": user.id,
            "username": user.username,
            "role": "admin" if user.id == ADMIN_ID else "user",
            "created": str(datetime.date.today())
        }},
        upsert=True
    )

# =========================
# STORAGE
# =========================

def user_path(uid):
    path = f"{BASE_DIR}/{uid}"
    os.makedirs(path, exist_ok=True)
    return path

# =========================
# START
# =========================

@dp.message(Command("start"))
async def start(m: types.Message):

    await init_user(m.from_user)

    await m.answer(
        "💀 SYSTEM ONLINE\n"
        "━━━━━━━━━━━━━━\n"
        "⚡ Persistent Uptime Enabled\n"
        "⚙ MongoDB Active\n"
        "📦 SaaS System Running"
    )

# =========================
# HELP
# =========================

@dp.message(Command("help"))
async def help_cmd(m: types.Message):

    await m.answer(
        "📦 COMMANDS:\n\n"
        "/files\n"
        "/read <file>\n"
        "/delete <file>\n"
        "/rename <old> <new>\n"
        "/uptime"
    )

# =========================
# FILE UPLOAD
# =========================

@dp.message(F.document)
async def upload(m: types.Message):

    await init_user(m.from_user)

    uid = str(m.from_user.id)
    path = user_path(uid)

    file = m.document
    save_path = f"{path}/{file.file_name}"

    tg = await bot.get_file(file.file_id)
    await bot.download_file(tg.file_path, save_path)

    await files_db.insert_one({
        "uid": m.from_user.id,
        "file": file.file_name,
        "path": save_path,
        "time": time.time()
    })

    await m.answer(f"📂 Uploaded: {file.file_name}")

# =========================
# FILE LIST
# =========================

@dp.message(Command("files"))
async def list_files(m: types.Message):

    path = user_path(str(m.from_user.id))
    files = os.listdir(path)

    if not files:
        return await m.answer("📂 Empty")

    await m.answer("\n".join(files))

# =========================
# READ FILE
# =========================

@dp.message(Command("read"))
async def read_file(m: types.Message):

    args = m.text.split()
    if len(args) < 2:
        return await m.answer("Usage: /read file.py")

    path = user_path(str(m.from_user.id))
    file_path = f"{path}/{args[1]}"

    if not os.path.exists(file_path):
        return await m.answer("❌ Not found")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    await m.answer(content[:3000])

# =========================
# DELETE
# =========================

@dp.message(Command("delete"))
async def delete_file(m: types.Message):

    args = m.text.split()
    if len(args) < 2:
        return await m.answer("Usage: /delete file.py")

    path = user_path(str(m.from_user.id))
    file_path = f"{path}/{args[1]}"

    if os.path.exists(file_path):
        os.remove(file_path)
        return await m.answer("🗑 Deleted")

    await m.answer("❌ Not found")

# =========================
# RENAME
# =========================

@dp.message(Command("rename"))
async def rename_file(m: types.Message):

    args = m.text.split()
    if len(args) < 3:
        return await m.answer("Usage: /rename old new")

    path = user_path(str(m.from_user.id))

    old = f"{path}/{args[1]}"
    new = f"{path}/{args[2]}"

    if os.path.exists(old):
        os.rename(old, new)
        return await m.answer("✏️ Renamed")

    await m.answer("❌ Not found")

# =========================
# UPTIME COMMAND (REAL PERSISTENT)
# =========================

@dp.message(Command("uptime"))
async def uptime_cmd(m: types.Message):

    up = await get_uptime()
    uptime = str(datetime.timedelta(seconds=int(up)))

    await m.answer(f"⏱ Uptime: {uptime}")

# =========================
# AUTO RECONNECT BOT LOOP
# =========================

async def run_bot():
    while True:
        try:
            print("💀 BOT STARTED")
            await dp.start_polling(bot)
        except Exception as e:
            print("RESTARTING BOT:", e)
            await asyncio.sleep(3)

# =========================
# MAIN
# =========================

async def main():

    await init_uptime()

    # web server thread (keep alive)
    threading.Thread(target=run_web, daemon=True).start()

    # bot run loop
    await run_bot()

if __name__ == "__main__":
    asyncio.run(main())
