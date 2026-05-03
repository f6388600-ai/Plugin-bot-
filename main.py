import os, sys, asyncio, logging, datetime, psutil, time, importlib.util
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from motor.motor_asyncio import AsyncIOMotorClient
from flask import Flask
from threading import Thread

# --- ⚙️ CONFIGURATION ---
API_TOKEN = '8523644793:AAGqHoxIdblgyCKvucU-5exjaaSweSaFvEc'
ADMIN_ID = 7793812954
MONGO_URL = "mongodb+srv://botuser:<db_password>@cluster0.xdoda3m.mongodb.net/?appName=Cluster0" # 👈 Paste your MongoDB URI here
PLUGIN_DIR = "plugins"
START_TIME = time.time()

# Ensure plugin directory exists
os.makedirs(PLUGIN_DIR, exist_ok=True)

# --- 🛰️ PORT BINDING & UPTIME SERVER ---
app = Flask('')
@app.route('/')
def home(): return "LR Elite Engine is Pulse-Active! 🟢"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- 🗄️ MONGODB SETUP ---
client = AsyncIOMotorClient(MONGO_URL)
db = client.lr_master_db
users_col = db.users

# --- 🤖 BOT INITIALIZATION ---
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
                    module_name = file[:-3]
                    spec = importlib.util.spec_from_file_location(module_name, os.path.join(PLUGIN_DIR, file))
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    if hasattr(module, "register_plugin"):
                        module.register_plugin(new_router)
                        count += 1
                except Exception as e:
                    logging.error(f"Plugin {file} Error: {e}")
    return new_router, count

# --- 📂 FILE MANAGER UI ---
def get_manager_kb():
    files = [f for f in os.listdir(PLUGIN_DIR) if f.endswith(".py")]
    kb = []
    for f in files:
        kb.append([InlineKeyboardButton(text=f"📁 {f}", callback_data=f"manage_{f}")])
    kb.append([InlineKeyboardButton(text="🔄 REFRESH ENGINE", callback_data="reload_all")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# --- 🎭 MASTER HANDLERS ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    # Sync User to DB
    await users_col.update_one({"id": user_id}, {"$set": {"name": message.from_user.full_name, "last_seen": str(datetime.datetime.now())}}, upsert=True)
    
    if user_id == ADMIN_ID:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗂️ FILE MANAGER", callback_data="open_fm")],
            [InlineKeyboardButton(text="📊 NEURAL STATS", callback_data="view_stats")]
        ])
        await message.answer(
            "<b>💀 MASTER ELITE CONSOLE ONLINE</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Welcome, Master. Neural connection is encrypted.\n"
            "All systems are <code>OPTIMAL ✅</code>", 
            reply_markup=kb
        )
    else:
        await message.answer(
            f"<b>⚜️ LR DIGITAL NETWORK ⚜️</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Greetings, <code>{message.from_user.first_name}</code>.\n"
            f"Authorized access: <code>GRANTED ✅</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Type /help to see public modules."
        )

# --- 📁 FILE MANAGER LOGIC ---
@dp.callback_query(F.data == "open_fm")
async def open_fm(call: CallbackQuery):
    await call.message.edit_text("<b>📂 SELECT A MODULE TO MANAGE:</b>", reply_markup=get_manager_kb())

@dp.callback_query(F.data.startswith("manage_"))
async def manage_file(call: CallbackQuery):
    fname = call.data.split("_")[1]
    fpath = os.path.join(PLUGIN_DIR, fname)
    size = os.path.getsize(fpath) / 1024
    
    text = (f"<b>🛠️ MODULE SETTINGS:</b> <code>{fname}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📏 <b>SIZE:</b> <code>{size:.2f} KB</code>\n"
            f"🛰️ <b>STATUS:</b> <code>ACTIVE 🟢</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑️ DELETE", callback_data=f"del_{fname}"),
         InlineKeyboardButton(text="📥 GET FILE", callback_data=f"get_{fname}")],
        [InlineKeyboardButton(text="📝 RENAME", callback_data=f"ren_{fname}"),
         InlineKeyboardButton(text="🛑 STOP", callback_data=f"stop_{fname}")],
        [InlineKeyboardButton(text="🔙 BACK", callback_data="open_fm")]
    ])
    await call.message.edit_text(text, reply_markup=kb)

# --- 📥 UPLOAD & INJECT SYSTEM ---
@dp.message(F.document, F.from_user.id == ADMIN_ID)
async def handle_upload(message: types.Message):
    if not message.document.file_name.endswith(".py"):
        return await message.answer("⚠️ <b>Master, only .py files are accepted for injection.</b>")
    
    status_msg = await message.answer("📡 <b>INITIALIZING NEURAL INJECTION...</b>")
    await asyncio.sleep(1)
    await status_msg.edit_text("📥 <b>DOWNLOADING DATA STREAM... 45%</b>")
    
    path = os.path.join(PLUGIN_DIR, message.document.file_name)
    file = await bot.get_file(message.document.file_id)
    await bot.download_file(file.file_path, path)
    
    await status_msg.edit_text("⚙️ <b>RE-SYNCING ENGINE CORE... 90%</b>")
    
    # Reload logic
    global plugin_router
    plugin_router, count = load_plugins()
    
    await status_msg.edit_text(
        f"<b>✅ INJECTION SUCCESSFUL</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📄 <b>FILE:</b> <code>{message.document.file_name}</code>\n"
        f"📏 <b>SIZE:</b> <code>{message.document.file_size/1024:.1f} KB</code>\n"
        f"🔥 <b>MODULES LOADED:</b> <code>{count}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Status: <code>LIVE & ACTIVE ✅</code>"
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    is_admin = message.from_user.id == ADMIN_ID
    files = [f[:-3] for f in os.listdir(PLUGIN_DIR) if f.endswith(".py")]
    
    if is_admin:
        help_text = (
            "<b>💀 ADMIN COMMAND CENTER</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "• <code>/start</code> - Main Dashboard\n"
            "• <code>/admin</code> - Sys Stats\n"
            "• <code>/bc</code> - Broadcast\n"
            "• <code>Upload .py</code> - Auto Inject\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )
    else:
        help_text = (
            "<b>⚜️ PUBLIC MODULES</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n" +
            ("\n".join([f"🔹 <code>/{f}</code>" for f in files]) if files else "<i>No modules active.</i>") +
            "\n━━━━━━━━━━━━━━━━━━━━"
        )
    await message.answer(help_text)

# --- 🚀 ENGINE BOOTUP ---
async def main():
    global plugin_router
    # Start Web Server for UptimeRobot
    Thread(target=run_web).start()
    
    # Load Plugins
    plugin_router, count = load_plugins()
    dp.include_router(plugin_router)
    
    print(f"💎 MASTER ELITE ENGINE LIVE | PLUGINS: {count}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try: asyncio.run(main())
    except (KeyboardInterrupt, SystemExit): pass
