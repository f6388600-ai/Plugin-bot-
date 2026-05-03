import os
import asyncio
import importlib.util
import threading
import time
import requests

from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.client.default import DefaultBotProperties

from fastapi import FastAPI
import uvicorn

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
plugin_router = Router()

EDIT_MODE = {}

# ======================
# FASTAPI (ANTI SLEEP)
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
# SELF PING LOOP
# ======================

async def self_ping():
    url = os.environ.get("SELF_URL")
    if not url:
        return

    while True:
        try:
            requests.get(url + "/ping")
        except:
            pass
        await asyncio.sleep(240)

# ======================
# LOAD PLUGINS
# ======================

def load_plugins():
    global plugin_router
    new_router = Router()

    for file in os.listdir(PLUGIN_DIR):
        if file.endswith(".py"):
            path = f"{PLUGIN_DIR}/{file}"
            try:
                spec = importlib.util.spec_from_file_location(file, path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                if hasattr(module, "register_plugin"):
                    module.register_plugin(new_router)

            except Exception as e:
                print("PLUGIN ERROR:", e)

    plugin_router = new_router
    dp.include_router(plugin_router)

# ======================
# START
# ======================

@dp.message(Command("start"))
async def start(m: types.Message):
    if m.from_user.id == ADMIN_ID:
        return await m.answer("💀 ULTRA PANEL → /panel")
    await m.answer("⚡ Bot running")

# ======================
# PANEL
# ======================

@dp.message(Command("panel"))
async def panel(m: types.Message):

    if m.from_user.id != ADMIN_ID:
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Files", callback_data="files")],
        [InlineKeyboardButton(text="🔌 Plugins", callback_data="plugins")]
    ])

    await m.answer("💀 CONTROL PANEL", reply_markup=kb)

# ======================
# FILE LIST
# ======================

@dp.callback_query(F.data == "files")
async def files_menu(c: types.CallbackQuery):

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
        [InlineKeyboardButton(text="👁 View", callback_data=f"view:{name}")],
        [InlineKeyboardButton(text="✏️ Edit", callback_data=f"edit:{name}")]
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

    if not os.path.exists(path):
        return await c.answer("Not found")

    with open(path, "r", encoding="utf-8") as f:
        data = f.read()

    await c.message.answer(data[:3000])

# ======================
# EDIT SYSTEM
# ======================

@dp.callback_query(F.data.startswith("edit:"))
async def edit_start(c: types.CallbackQuery):

    name = c.data.split(":")[1]
    EDIT_MODE[c.from_user.id] = name

    await c.message.answer("✏️ Send new content for file")

@dp.message()
async def handle_edit(m: types.Message):

    if m.from_user.id not in EDIT_MODE:
        return

    name = EDIT_MODE[m.from_user.id]
    path = f"{BASE_DIR}/{name}"

    with open(path, "w", encoding="utf-8") as f:
        f.write(m.text)

    del EDIT_MODE[m.from_user.id]

    await m.answer("✅ File Updated")

# ======================
# UPLOAD
# ======================

@dp.message(F.document)
async def upload(m: types.Message):

    if m.from_user.id != ADMIN_ID:
        return

    file = m.document
    name = file.file_name

    if name.endswith(".py"):
        path = f"{PLUGIN_DIR}/{name}"
    else:
        path = f"{BASE_DIR}/{name}"

    tg = await bot.get_file(file.file_id)
    await bot.download_file(tg.file_path, path)

    if name.endswith(".py"):
        load_plugins()
        return await m.answer("🔌 Plugin Loaded")

    await m.answer("📂 File Uploaded")

# ======================
# RUN
# ======================

async def run_bot():
    while True:
        try:
            await dp.start_polling(bot)
        except:
            await asyncio.sleep(3)

async def main():
    load_plugins()
    threading.Thread(target=run_web, daemon=True).start()

    await asyncio.gather(
        run_bot(),
        self_ping()
    )

if __name__ == "__main__":
    asyncio.run(main())
