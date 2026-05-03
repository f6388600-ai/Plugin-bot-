import os, sys, asyncio, logging, datetime, psutil, time, importlib.util, sqlite3
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from flask import Flask
from threading import Thread

# --- ⚙️ CONFIGURATION ---
API_TOKEN = '8523644793:AAEfmABlnanvt5I7LfHTw_I_2mVHKIvnEiw'
ADMIN_ID = 7793812954
PLUGIN_DIR = "plugins"
DB_PATH = "data/master_elite.db"
START_TIME = time.time()

os.makedirs(PLUGIN_DIR, exist_ok=True)
os.makedirs("data", exist_ok=True)

# --- 🛰️ PORT BINDING & UPTIME SERVER ---
app = Flask('')
@app.route('/')
def home(): return "<h1>LR Elite Pulse: LIVE (SQL Mode) 🟢</h1>"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- 🗄️ SQLITE DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY, 
        name TEXT, 
        joined TEXT)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS plugins (
        filename TEXT PRIMARY KEY, 
        status TEXT DEFAULT 'ON')""")
    conn.commit()
    conn.close()

# --- 🛠️ DYNAMIC MODULE LOADER ---
def load_plugins():
    global plugin_router
    new_router = Router()
    count = 0
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for file in os.listdir(PLUGIN_DIR):
        if file.endswith(".py"):
            # Check if plugin is disabled in DB
            cursor.execute("SELECT status FROM plugins WHERE filename=?", (file,))
            row = cursor.fetchone()
            if row and row[0] == 'OFF': continue
            
            try:
                spec = importlib.util.spec_from_file_location(file[:-3], os.path.join(PLUGIN_DIR, file))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, "register_plugin"):
                    module.register_plugin(new_router)
                    count += 1
            except Exception: continue
    conn.close()
    return new_router, count

# --- 🤖 BOT INITIALIZATION ---
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
plugin_router = Router()

# --- 🎭 MASTER UI HANDLERS ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR IGNORE INTO users (id, name, joined) VALUES (?,?,?)", 
                 (user_id, message.from_user.full_name, str(datetime.date.today())))
    conn.commit()
    conn.close()
    
    if user_id == ADMIN_ID:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗂️ FILE MANAGER", callback_data="fm_open")],
            [InlineKeyboardButton(text="📊 SYSTEM STATS", callback_data="sys_stats")]
        ])
        await message.answer("<b>💀 MASTER CONSOLE: SQL MODE</b>\n━━━━━━━━━━━━━━━━━━━━\nStatus: <code>OPTIMAL ✅</code>", reply_markup=kb)
    else:
        await message.answer(f"<b>⚜️ LR DIGITAL NETWORK ⚜️</b>\nWelcome <code>{message.from_user.first_name}</code>")

# --- 📁 FULL FILE MANAGER LOGIC ---
@dp.callback_query(F.data == "fm_open")
async def open_fm(call: CallbackQuery):
    files = [f for f in os.listdir(PLUGIN_DIR) if f.endswith(".py")]
    kb = [[InlineKeyboardButton(text=f"📄 {f}", callback_data=f"manage_{f}")] for f in files]
    kb.append([InlineKeyboardButton(text="🔙 BACK", callback_data="back_start")])
    await call.message.edit_text("<b>📂 MODULE DIRECTORY:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("manage_"))
async def manage_file(call: CallbackQuery):
    fname = call.data.split("_")[1]
    fpath = os.path.join(PLUGIN_DIR, fname)
    size = os.path.getsize(fpath) / 1024
    
    conn = sqlite3.connect(DB_PATH)
    status = conn.execute("SELECT status FROM plugins WHERE filename=?", (fname,)).fetchone()
    status = status[0] if status else "ON"
    conn.close()

    text = (f"<b>🛠️ MODULE:</b> <code>{fname}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📏 <b>SIZE:</b> <code>{size:.2f} KB</code>\n"
            f"⚡ <b>POWER:</b> <code>{'ACTIVE ✅' if status == 'ON' else 'STOPPED 🛑'}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 DOWNLOAD", callback_data=f"get_{fname}"),
         InlineKeyboardButton(text="🗑️ DELETE", callback_data=f"del_{fname}")],
        [InlineKeyboardButton(text="📝 RENAME", callback_data=f"ren_{fname}"),
         InlineKeyboardButton(text="🛑 STOP/ON", callback_data=f"tog_{fname}")],
        [InlineKeyboardButton(text="🔙 BACK", callback_data="fm_open")]
    ])
    await call.message.edit_text(text, reply_markup=kb)

# --- ⚡ FILE ACTIONS ---
@dp.callback_query(F.data.startswith("tog_"))
async def toggle_plugin(call: CallbackQuery):
    fname = call.data.split("_")[1]
    conn = sqlite3.connect(DB_PATH)
    curr = conn.execute("SELECT status FROM plugins WHERE filename=?", (fname,)).fetchone()
    new_stat = "OFF" if not curr or curr[0] == "ON" else "ON"
    conn.execute("INSERT OR REPLACE INTO plugins (filename, status) VALUES (?,?)", (fname, new_stat))
    conn.commit()
    conn.close()
    await call.answer(f"Module set to {new_stat}")
    global plugin_router
    plugin_router, _ = load_plugins() # Reload
    await manage_file(call)

@dp.callback_query(F.data.startswith("get_"))
async def download_plugin(call: CallbackQuery):
    fname = call.data.split("_")[1]
    file = FSInputFile(os.path.join(PLUGIN_DIR, fname))
    await call.message.answer_document(file, caption=f"🚀 <b>Backup:</b> <code>{fname}</code>")

@dp.callback_query(F.data.startswith("del_"))
async def delete_plugin(call: CallbackQuery):
    fname = call.data.split("_")[1]
    os.remove(os.path.join(PLUGIN_DIR, fname))
    await call.answer("File deleted permanently.")
    await open_fm(call)

# --- 📥 UPLOAD ANIMATION ---
@dp.message(F.document, F.from_user.id == ADMIN_ID)
async def handle_upload(message: types.Message):
    if not message.document.file_name.endswith(".py"): return
    status = await message.answer("📡 <b>SCANNING...</b>")
    await asyncio.sleep(0.5)
    await status.edit_text("📥 <b>INJECTING DATA: 70%</b>")
    
    path = os.path.join(PLUGIN_DIR, message.document.file_name)
    await bot.download(message.document, destination=path)
    
    global plugin_router
    plugin_router, count = load_plugins()
    
    await status.edit_text(
        f"<b>✅ INJECTION SUCCESSFUL</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📄 <b>FILE:</b> <code>{message.document.file_name}</code>\n"
        f"🔥 <b>LIVE MODULES:</b> <code>{count}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

# --- 🚀 BOOT ---
async def main():
    init_db()
    Thread(target=run_web).start() 
    global plugin_router
    plugin_router, _ = load_plugins()
    dp.include_router(plugin_router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
