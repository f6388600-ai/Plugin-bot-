import os
import time
import asyncio
import importlib.util
from fastapi import FastAPI
import uvicorn
import threading

from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.client.default import DefaultBotProperties

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
db = client["master_bot"]
files_col = db["files"]
users_col = db["users"]

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
# USER SAVE
# ======================

async def save_user(user):
    await users_col.update_one(
        {"id": user.id},
        {"$setOnInsert": {
            "id": user.id,
            "username": user.username
        }},
        upsert=True
    )

# ======================
# START
# ======================

@dp.message(Command("start"))
async def start(m: types.Message):

    await save_user(m.from_user)

    if m.from_user.id == ADMIN_ID:
        return await m.answer(
            "💀 ADMIN PANEL\n"
            "━━━━━━━━━━━━━━\n"
            "/panel - control\n"
            "/files - list files"
        )

    await m.answer("⚡ Bot Active")

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

    await m.answer("💀 MASTER PANEL", reply_markup=kb)

# ======================
# FILE LIST
# ======================

@dp.callback_query(F.data == "files")
async def files(c: types.CallbackQuery):

    files = os.listdir(BASE_DIR)

    if not files:
        return await c.message.edit_text("📂 Empty")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f, callback_data=f"file:{f}")]
        for f in files
    ])

    await c.message.edit_text("📂 FILES", reply_markup=kb)

# ======================
# FILE MENU
# ======================

@dp.callback_query(F.data.startswith("file:"))
async def file_menu(c: types.CallbackQuery):

    name = c.data.split(":")[1]

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Download", callback_data=f"dl:{name}")],
        [InlineKeyboardButton(text="🗑 Delete", callback_data=f"del:{name}")],
        [InlineKeyboardButton(text="👁 View", callback_data=f"view:{name}")]
    ])

    await c.message.edit_text(f"📄 {name}", reply_markup=kb)

# ======================
# DOWNLOAD
# ======================

@dp.callback_query(F.data.startswith("dl:"))
async def download(c: types.CallbackQuery):

    name = c.data.split(":")[1]
    path = f"{BASE_DIR}/{name}"

    if os.path.exists(path):
        await c.message.answer_document(FSInputFile(path))

# ======================
# DELETE
# ======================

@dp.callback_query(F.data.startswith("del:"))
async def delete(c: types.CallbackQuery):

    name = c.data.split(":")[1]
    path = f"{BASE_DIR}/{name}"

    if os.path.exists(path):
        os.remove(path)
        await c.message.edit_text("🗑 Deleted")

# ======================
# VIEW
# ======================

@dp.callback_query(F.data.startswith("view:"))
async def view(c: types.CallbackQuery):

    name = c.data.split(":")[1]
    path = f"{BASE_DIR}/{name}"

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = f.read()

        await c.message.answer(data[:3500])

# ======================
# UPLOAD (FILES + PLUGINS + DB)
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
            await msg.edit_text(f"🔌 Plugin Loaded: {name}")
        else:
            await msg.edit_text(f"📂 Uploaded: {name}")

    except Exception as e:
        await msg.edit_text(f"❌ Error: {e}")

# ======================
# RELOAD PLUGINS
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
