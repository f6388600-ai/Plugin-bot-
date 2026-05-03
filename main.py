import os, sys, asyncio, logging, datetime, psutil, time, importlib.util
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from motor.motor_asyncio import AsyncIOMotorClient
from flask import Flask
from threading import Thread

# --- CONFIG & SECURE LINKS ---
API_TOKEN = '8523644793:AAEer9gT4sDYvPL6LXzwGmKPuILEsTjoXho'
ADMIN_ID = 7793812954
MONGO_URL = os.environ.get("MONGO_URL", "your_mongodb_url_here") # Render Env logic
PLUGIN_DIR = "plugins"
os.makedirs(PLUGIN_DIR, exist_ok=True)

# --- WEB SERVER FOR RENDER PORT BINDING & UPTIME ---
app = Flask('')
@app.route('/')
def home(): return "<h1>LR Elite Pulse: ACTIVE 🟢</h1>"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- MONGODB CONNECTION ---
client = AsyncIOMotorClient(MONGO_URL)
db = client.lr_master_db
users_col = db.users

# --- BOT CORE ---
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
plugin_router = Router()

# --- DYNAMIC PLUGIN SYSTEM ---
def load_plugins():
    global plugin_router
    new_router = Router()
    count = 0
    for file in os.listdir(PLUGIN_DIR):
        if file.endswith(".py"):
            spec = importlib.util.spec_from_file_location(file[:-3], os.path.join(PLUGIN_DIR, file))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, "register_plugin"):
                module.register_plugin(new_router)
                count += 1
    return new_router, count

# --- UI COMPONENTS ---
def file_manager_kb():
    files = [f for f in os.listdir(PLUGIN_DIR) if f.endswith(".py")]
    kb = [[InlineKeyboardButton(text=f"📄 {f}", callback_data=f"inf_{f}")] for f in files]
    kb.append([InlineKeyboardButton(text="📤 UPLOAD NEW", callback_data="fast_up")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# --- HANDLERS ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    await users_col.update_one({"id": user_id}, {"$set": {"user": message.from_user.username}}, upsert=True)
    
    if user_id == ADMIN_ID:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📂 FILE MANAGER", callback_data="open_fm")],
            [InlineKeyboardButton(text="📊 SYSTEM STATS", callback_data="st_view")]
        ])
        await message.answer("<b>💀 MASTER CONSOLE: ONLINE</b>\nNeural link established.", reply_markup=kb)
    else:
        await message.answer(f"<b>⚜️ LR ELITE NETWORK ⚜️</b>\nAuthorized user: <code>{message.from_user.first_name}</code>")

@dp.callback_query(F.data == "open_fm")
async def open_fm(call: CallbackQuery):
    await call.message.edit_text("<b>📁 SELECT MODULE DATA:</b>", reply_markup=file_manager_kb())

@dp.callback_query(F.data.startswith("inf_"))
async def file_info(call: CallbackQuery):
    fname = call.data.split("_")[1]
    fpath = os.path.join(PLUGIN_DIR, fname)
    size = os.path.getsize(fpath) / 1024
    
    msg = (f"<b>📄 MODULE:</b> <code>{fname}</code>\n"
           f"━━━━━━━━━━━━━━━━━━━━\n"
           f"📏 <b>SIZE:</b> <code>{size:.2f} KB</code>\n"
           f"🛡️ <b>STATUS:</b> <code>ACTIVE ✅</code>\n"
           f"━━━━━━━━━━━━━━━━━━━━")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 GET", callback_data=f"get_{fname}"), 
         InlineKeyboardButton(text="🗑️ DEL", callback_data=f"del_{fname}")],
        [InlineKeyboardButton(text="🛑 STOP", callback_data=f"off_{fname}"),
         InlineKeyboardButton(text="📝 REN", callback_data=f"ren_{fname}")],
        [InlineKeyboardButton(text="🔙 BACK", callback_data="open_fm")]
    ])
    await call.message.edit_text(msg, reply_markup=kb)

@dp.message(F.document, F.from_user.id == ADMIN_ID)
async def pro_upload(message: types.Message):
    if not message.document.file_name.endswith(".py"): return
    
    status = await message.answer("📡 <b>UPLOADING TO NEURAL CORE...</b>")
    await asyncio.sleep(0.8)
    await status.edit_text("📥 <b>DATA STREAMING: 60%</b>")
    
    path = os.path.join(PLUGIN_DIR, message.document.file_name)
    await bot.download(message.document, destination=path)
    
    global plugin_router
    plugin_router, count = load_plugins()
    
    await status.edit_text(
        f"<b>✅ INJECTION SUCCESSFUL</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📄 <b>FILE:</b> <code>{message.document.file_name}</code>\n"
        f"📏 <b>SIZE:</b> <code>{message.document.file_size/1024:.1f} KB</code>\n"
        f"🔄 <b>RELOAD:</b> <code>COMPLETE ✅</code>"
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    files = [f[:-3] for f in os.listdir(PLUGIN_DIR) if f.endswith(".py")]
    if message.from_user.id == ADMIN_ID:
        await message.answer("<b>💀 ADMIN CMD:</b>\n/admin, /reload, /upload, /bc")
    else:
        text = "<b>⚜️ PUBLIC MODULES:</b>\n" + ", ".join([f"<code>/{f}</code>" for f in files])
        await message.answer(text)

# --- BOOT ENGINE ---
async def main():
    global plugin_router
    Thread(target=run_web).start() # Render Port Binding
    plugin_router, _ = load_plugins()
    dp.include_router(plugin_router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
            
