import os
import time
import asyncio
import importlib.util
import threading

from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.client.default import DefaultBotProperties

from fastapi import FastAPI
import uvicorn

from motor.motor_asyncio import AsyncIOMotorClient

# ======================
# CONFIG
# ======================

TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
MONGO_URL = os.environ.get("MONGO_URL")
PORT = int(os.environ.get("PORT", 10000))

BASE_DIR = "files"
PLUGIN_DIR = "plugins"

os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(PLUGIN_DIR, exist_ok=True)

# ======================
# BOT + DB
# ======================

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

client = AsyncIOMotorClient(MONGO_URL)
db = client["file_bot"]

files_col = db["files"]

START_TIME = time.time()

# ======================
# WEB (ANTI SLEEP)
# ======================

app = FastAPI()

@app.get("/")
def home():
    return {"status": "alive"}

@app.get("/ping")
def ping():
    return {"pong": True}

def run_web():
    uvicorn.run(app, host="0.0.0.0", port=PORT)

# ======================
# PLUGIN SYSTEM
# ======================

plugin_router = Router()

def load_plugins():
    global plugin_router

    router = Router()

    for file in os.listdir(PLUGIN_DIR):
        if file.endswith(".py"):
            path = f"{PLUGIN_DIR}/{file}"

            try:
                spec = importlib.util.spec_from_file_location(file, path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                if hasattr(module, "register_plugin"):
                    module.register_plugin(router)

            except Exception as e:
                print("PLUGIN ERROR:", e)

    plugin_router = router
    return router

# ======================
# START
# ======================

@dp.message(Command("start"))
async def start(m: types.Message):

    if m.from_user.id == ADMIN_ID:
        return await m.answer(
            "💀 ADMIN PANEL\n"
            "━━━━━━━━━━━━━━\n"
            "/panel - open panel\n"
            "/files - file list"
        )

    await m.answer("⚡ Bot Running")

# ======================
# PANEL
# ======================

@dp.message(Command("panel"))
async def panel(m: types.Message):

    if m.from_user.id != ADMIN_ID:
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Files", callback_data="files")],
        [InlineKeyboardButton(text="🔌 Reload Plugins", callback_data="reload")],
        [InlineKeyboardButton(text="⏱ Uptime", callback_data="uptime")]
    ])

    await m.answer("💀 CONTROL PANEL", reply_markup=kb)

# ======================
# FILE LIST (DB FIXED)
# ======================

@dp.message(Command("files"))
async def files(m: types.Message):

    if m.from_user.id != ADMIN_ID:
        return

    data = await files_col.find({}).to_list(length=50)

    if not data:
        return await m.answer("📂 No files")

    text = "📁 FILES:\n\n"

    for f in data:
        text += f"📄 {f['name']}\n"

    await m.answer(text)

# ======================
# FILE VIEW
# ======================

@dp.message(Command("view"))
async def view(m: types.Message):

    if m.from_user.id != ADMIN_ID:
        return

    args = m.text.split()
    if len(args) < 2:
        return await m.answer("Usage: /view file.txt")

    path = f"{BASE_DIR}/{args[1]}"

    if not os.path.exists(path):
        return await m.answer("❌ Not found")

    with open(path, "r", encoding="utf-8") as f:
        data = f.read()

    await m.answer(data[:3500])

# ======================
# DELETE
# ======================

@dp.message(Command("delete"))
async def delete(m: types.Message):

    if m.from_user.id != ADMIN_ID:
        return

    args = m.text.split()
    if len(args) < 2:
        return await m.answer("Usage: /delete file.txt")

    path = f"{BASE_DIR}/{args[1]}"

    if os.path.exists(path):
        os.remove(path)
        await files_col.delete_one({"name": args[1]})
        return await m.answer("🗑 Deleted")

    await m.answer("❌ Not found")

# ======================
# RENAME
# ======================

@dp.message(Command("rename"))
async def rename(m: types.Message):

    if m.from_user.id != ADMIN_ID:
        return

    args = m.text.split()

    if len(args) < 3:
        return await m.answer("Usage: /rename old new")

    old = f"{BASE_DIR}/{args[1]}"
    new = f"{BASE_DIR}/{args[2]}"

    if os.path.exists(old):
        os.rename(old, new)

        await files_col.update_one(
            {"name": args[1]},
            {"$set": {"name": args[2]}}
        )

        return await m.answer("✏️ Renamed")

    await m.answer("❌ Not found")

# ======================
# UPLOAD (FINAL FIXED)
# ======================

@dp.message(F.document)
async def upload(m: types.Message):

    if m.from_user.id != ADMIN_ID:
        return

    file = m.document
    name = file.file_name

    msg = await m.answer("⏳ Uploading...")

    try:
        path = f"{PLUGIN_DIR}/{name}" if name.endswith(".py") else f"{BASE_DIR}/{name}"

        tg = await bot.get_file(file.file_id)
        await bot.download_file(tg.file_path, path)

        await files_col.insert_one({
            "name": name,
            "path": path,
            "time": time.time()
        })

        if name.endswith(".py"):
            load_plugins()
            return await msg.edit_text(f"🔌 Plugin Loaded: {name}")

        await msg.edit_text(f"📂 Uploaded: {name}")

    except Exception as e:
        await msg.edit_text(f"❌ Error: {e}")

# ======================
# RELOAD
# ======================

@dp.callback_query(F.data == "reload")
async def reload(c: types.CallbackQuery):

    load_plugins()
    await c.message.edit_text("🔄 Plugins Reloaded")

# ======================
# UPTIME
# ======================

@dp.callback_query(F.data == "uptime")
async def uptime(c: types.CallbackQuery):

    up = int(time.time() - START_TIME)
    await c.message.edit_text(f"⏱ Uptime: {up}s")

# ======================
# BOT LOOP SAFE
# ======================

async def run_bot():
    while True:
        try:
            await dp.start_polling(bot)
        except Exception as e:
            print("RESTART:", e)
            await asyncio.sleep(3)

# ======================
# MAIN
# ======================

async def main():

    load_plugins()

    threading.Thread(target=run_web, daemon=True).start()

    await run_bot()

if __name__ == "__main__":
    asyncio.run(main())
