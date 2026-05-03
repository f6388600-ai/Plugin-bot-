import os
import asyncio
import time
import importlib.util
from fastapi import FastAPI
import uvicorn
import threading

from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.client.default import DefaultBotProperties

# ======================
# CONFIG
# ======================

TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
PORT = int(os.environ.get("PORT", 10000))

BASE_DIR = "files"
PLUGIN_DIR = "plugins"

os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(PLUGIN_DIR, exist_ok=True)

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

START_TIME = time.time()

# ======================
# WEB (ANTI SLEEP + UPTIME)
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

    new_router = Router()
    count = 0

    for file in os.listdir(PLUGIN_DIR):
        if file.endswith(".py"):
            path = f"{PLUGIN_DIR}/{file}"

            try:
                spec = importlib.util.spec_from_file_location(file, path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                if hasattr(module, "register_plugin"):
                    module.register_plugin(new_router)
                    count += 1

            except Exception as e:
                print("PLUGIN ERROR:", e)

    plugin_router = new_router
    dp.include_router(plugin_router)

    return count

# ======================
# START
# ======================

@dp.message(Command("start"))
async def start(m: types.Message):

    if m.from_user.id == ADMIN_ID:
        return await m.answer(
            "💀 <b>ADMIN PANEL ACTIVE</b>\n"
            "━━━━━━━━━━━━━━\n"
            "/panel - control panel\n"
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
        [InlineKeyboardButton(text="🔌 Plugins", callback_data="plugins")],
        [InlineKeyboardButton(text="⏱ Uptime", callback_data="uptime")]
    ])

    await m.answer("💀 CONTROL PANEL", reply_markup=kb)

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
# UPLOAD (FILES + PLUGINS)
# ======================

@dp.message(F.document)
async def upload(m: types.Message):

    if m.from_user.id != ADMIN_ID:
        return

    file = m.document
    name = file.file_name

    msg = await m.answer("⏳ Uploading...")

    try:
        if name.endswith(".py"):
            path = f"{PLUGIN_DIR}/{name}"
        else:
            path = f"{BASE_DIR}/{name}"

        tg = await bot.get_file(file.file_id)
        await bot.download_file(tg.file_path, path)

        if name.endswith(".py"):
            load_plugins()
            return await msg.edit_text(f"🔌 Plugin Loaded: {name}")

        await msg.edit_text(f"📂 Uploaded: {name}")

    except Exception as e:
        await msg.edit_text(f"❌ Error: {e}")

# ======================
# UPTIME
# ======================

@dp.message(Command("uptime"))
async def uptime(m: types.Message):

    up = int(time.time() - START_TIME)
    await m.answer(f"⏱ Uptime: {up}s")

# ======================
# PANEL CALLBACK
# ======================

@dp.callback_query(F.data == "uptime")
async def uptime_cb(c: types.CallbackQuery):

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
