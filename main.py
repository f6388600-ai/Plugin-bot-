import os, sys, asyncio, logging, datetime, psutil, time, importlib.util
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from motor.motor_asyncio import AsyncIOMotorClient
from flask import Flask
from threading import Thread

# --- ⚙️ CONFIGURATION ---
API_TOKEN = '8523644793:AAEfmABlnanvt5I7LfHTw_I_2mVHKIvnEiw'
ADMIN_ID = 7793812954
MONGO_URL = os.environ.get("MONGO_URL") # Environment variable for security
PLUGIN_DIR = "plugins"
START_TIME = time.time()

os.makedirs(PLUGIN_DIR, exist_ok=True)

# --- 🛰️ PORT BINDING & UPTIME SERVER ---
# Helps maintain 24/7 activity on Render
app = Flask('')
@app.route('/')
def home(): return "<h1>LR Elite Pulse: LIVE 🟢</h1>"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- 🗄️ MONGODB SETUP ---
# Secure persistence for user and system data
client = AsyncIOMotorClient(MONGO_URL)
db = client.lr_master_db
users_col = db.users

# --- 🤖 BOT INITIALIZATION ---
# Aiogram 3.7.0+ compatible setup
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
plugin_router = Router()

# --- 🛠️ DYNAMIC MODULE LOADER ---
def load_plugins():
    global plugin_router
    new_router = Router()
    count = 0
    if os.path.exists(PLUGIN_DIR):
        for file in os.listdir(PLUGIN_DIR):
            if file.endswith(".py"):
                try:
                    spec = importlib.util.spec_from_file_location(file[:-3], os.path.join(PLUGIN_DIR, file))
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    if hasattr(module, "register_plugin"):
                        module.register_plugin(new_router)
                        count += 1
                except Exception: continue
    return new_router, count

# --- 🎭 MASTER UI HANDLERS ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    # Log user in MongoDB
    await users_col.update_one(
        {"id": user_id}, 
        {"$set": {"name": message.from_user.full_name, "last_seen": str(datetime.datetime.now())}}, 
        upsert=True
    )
    
    if user_id == ADMIN_ID:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗂️ FILE MANAGER", callback_data="fm_open")],
            [InlineKeyboardButton(text="📊 SYSTEM STATS", callback_data="sys_stats")]
        ])
        await message.answer(
            "<b>💀 MASTER ELITE CONSOLE</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Neural link status: <code>OPTIMAL ✅</code>\n"
            "System: <code>Pulse-Active 🟢</code>", 
            reply_markup=kb
        )
    else:
        # Welcome message based on user preferences
        await message.answer(
            f"<b>⚜️ LR DIGITAL NETWORK ⚜️</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Greetings, <code>{message.from_user.first_name}</code>.\n"
            f"Unauthorized attempts are logged. Welcome.\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Type /help to see public modules."
        )

# --- 📁 DYNAMIC FILE MANAGER ---
@dp.callback_query(F.data == "fm_open")
async def open_fm(call: CallbackQuery):
    files = [f for f in os.listdir(PLUGIN_DIR) if f.endswith(".py")]
    kb = [[InlineKeyboardButton(text=f"📄 {f}", callback_data=f"manage_{f}")] for f in files]
    kb.append([InlineKeyboardButton(text="🔄 REFRESH CORE", callback_data="core_reload")])
    await call.message.edit_text("<b>📂 ACTIVE MODULE DIRECTORY:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("manage_"))
async def manage_file(call: CallbackQuery):
    fname = call.data.split("_")[1]
    fpath = os.path.join(PLUGIN_DIR, fname)
    size = os.path.getsize(fpath) / 1024
    
    text = (f"<b>🛠️ MODULE:</b> <code>{fname}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📏 <b>SIZE:</b> <code>{size:.2f} KB</code>\n"
            f"🛰️ <b>STATUS:</b> <code>LIVE ✅</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑️ DELETE", callback_data=f"del_{fname}"),
         InlineKeyboardButton(text="📥 DOWNLOAD", callback_data=f"get_{fname}")],
        [InlineKeyboardButton(text="🔙 BACK", callback_data="fm_open")]
    ])
    await call.message.edit_text(text, reply_markup=kb)

# --- 📥 AUTO-INJECTION (WITH ANIMATION) ---
@dp.message(F.document, F.from_user.id == ADMIN_ID)
async def handle_upload(message: types.Message):
    if not message.document.file_name.endswith(".py"): return
    
    # Professional uploading animation
    status = await message.answer("📡 <b>INITIALIZING NEURAL INJECTION...</b>")
    await asyncio.sleep(0.5)
    await status.edit_text("📥 <b>STREAMING DATA... 55%</b>")
    
    path = os.path.join(PLUGIN_DIR, message.document.file_name)
    await bot.download(message.document, destination=path)
    
    await status.edit_text("⚙️ <b>SYNCING WITH CORE... 95%</b>")
    
    # Reload engine logic without restart
    global plugin_router
    plugin_router, count = load_plugins()
    
    await status.edit_text(
        f"<b>✅ INJECTION SUCCESSFUL</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📄 <b>FILE:</b> <code>{message.document.file_name}</code>\n"
        f"📏 <b>SIZE:</b> <code>{message.document.file_size/1024:.1f} KB</code>\n"
        f"🔥 <b>TOTAL MODULES:</b> <code>{count}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    files = [f[:-3] for f in os.listdir(PLUGIN_DIR) if f.endswith(".py")]
    if message.from_user.id == ADMIN_ID:
        help_text = "<b>💀 ADMIN ACCESS:</b>\n/start, /reload, /bc, /admin\n<i>Upload .py to inject.</i>"
    else:
        help_text = "<b>⚜️ PUBLIC MODULES:</b>\n" + ", ".join([f"<code>/{f}</code>" for f in files])
    await message.answer(help_text)

# --- 🚀 ENGINE BOOT ---
async def main():
    global plugin_router
    # Port binding for UptimeRobot compatibility
    Thread(target=run_web).start() 
    plugin_router, _ = load_plugins()
    dp.include_router(plugin_router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
