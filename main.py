import os
import asyncio
import time
import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties

from motor.motor_asyncio import AsyncIOMotorClient

from fastapi import FastAPI
import uvicorn

# =========================
# ENVIRONMENT VARIABLES (RENDER SAFE)
# =========================

TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
MONGO_URL = os.environ.get("MONGO_URL")

PORT = int(os.environ.get("PORT", 10000))

# =========================
# SAFETY CHECK
# =========================

if not TOKEN or not MONGO_URL:
    raise Exception("❌ Missing ENV variables (BOT_TOKEN / MONGO_URL)")

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

BASE_DIR = "storage"
os.makedirs(BASE_DIR, exist_ok=True)

START_TIME = time.time()

# =========================
# UPTIME SYSTEM (PERSISTENT)
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
# WEB SERVER (RENDER KEEP ALIVE)
# =========================

app = FastAPI()

@app.get("/")
def home():
    return {"status": "alive"}

@app.get("/ping")
def ping():
    return {"pong": True}

# =========================
# USER INIT
# =========================

async def init_user(user: types.User):
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
# USER STORAGE
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
        "⚡ Render Safe Mode Active\n"
        "🗄 MongoDB Connected\n"
        "🚀 SaaS Ready"
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
# DELETE FILE
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
# RENAME FILE
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
# UPTIME
# =========================

@dp.message(Command("uptime"))
async def uptime_cmd(m: types.Message):
    up = await get_uptime()
    await m.answer(f"⏱ Uptime: {str(datetime.timedelta(seconds=int(up)))}")

# =========================
# BOT LOOP (RECONNECT SAFE)
# =========================

async def run_bot():
    while True:
        try:
            await dp.start_polling(bot)
        except Exception as e:
            print("RESTART BOT:", e)
            await asyncio.sleep(3)

# =========================
# MAIN
# =========================

async def main():

    await init_uptime()

    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)

    # web + bot together
    await asyncio.gather(
        server.serve(),
        run_bot()
    )

if __name__ == "__main__":
    asyncio.run(main())
