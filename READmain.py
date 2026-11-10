import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import sqlite3
import threading
from flask import Flask

# توكن البوت الخاص بك
TOKEN = "9276388966:AAGTaW3GqPDsWDHNvJKzd9d0RqaoNep_89g"
bot = telebot.TeleBot(TOKEN)

# إعداد قاعدة البيانات
conn = sqlite3.connect("rshq_bot.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, points INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS channels (channel_user TEXT PRIMARY KEY, owner_id INTEGER, points INTEGER)")
conn.commit()

# --- سيرفر Flask لإبقاء البوت يعمل 24/7 على الاستضافات المجانية ---
app = Flask(__name__)

@app.route('/')
def home():
    return "البوت يعمل بنجاح 24/7!"

def run_server():
    # الاستضافات المجانية تستخدم غالباً بورت 8080 أو 8000
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    t = threading.Thread(target=run_server)
    t.start()
# -----------------------------------------------------------------

def register_user(user_id):
    cursor.execute("SELECT points FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id, points) VALUES (?, ?)", (user_id, 20)) # هدية ترحيبية 20 نقطة
        conn.commit()

@bot.message_handler(commands=['start'])
def start_message(message):
    register_user(message.chat.id)
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("🪙 تجميع نقاط"), KeyboardButton("🚀 رشق قناتي"))
    markup.add(KeyboardButton("👤 حسابي"))
    
    bot.send_message(
        message.chat.id, 
        "أهلاً بك في بوت الرشق المجاني 🌟\n\nاجمع النقاط عبر الاشتراك بقنوات الآخرين، واستخدمها لرفع قناتك!", 
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == "👤 حسابي")
def my_account(message):
    cursor.execute("SELECT points FROM users WHERE user_id = ?", (message.chat.id,))
    points = cursor.fetchone()[0]
    bot.send_message(message.chat.id, f"👤 معرفك: `{message.chat.id}`\n🪙 رصيد نقاطك: {points}", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "🪙 تجميع نقاط")
def earn_points(message):
    cursor.execute("SELECT channel_user, points FROM channels WHERE points > 0 AND owner_id != ? ORDER BY RANDOM() LIMIT 1", (message.chat.id,))
    channel = cursor.fetchone()
    
    if channel:
        channel_user = channel[0]
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ اشترك الآن", url=f"https://t.me/{channel_user.replace('@', '')}"))
        markup.add(InlineKeyboardButton("🔄 تحقق من الانضمام", callback_data=f"check_{channel_user}"))
        bot.send_message(message.chat.id, f"اشترك في هذه القناة لتحصل على 5 نقاط:\n{channel_user}", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "لا توجد قنوات متاحة حالياً للرشق. جرب إضافة قناتك أولاً! 🚀")

@bot.callback_query_handler(func=lambda call: call.data.startswith("check_"))
def verify_subscription(call):
    channel_user = call.data.split("_")[1]
    try:
        status = bot.get_chat_member(channel_user, call.message.chat.id).status
        if status in ['member', 'administrator', 'creator']:
            cursor.execute("UPDATE users SET points = points + 5 WHERE user_id = ?", (call.message.chat.id,))
            cursor.execute("UPDATE channels SET points = points - 5 WHERE channel_user = ?", (channel_user,))
            cursor.execute("DELETE FROM channels WHERE points <= 0")
            conn.commit()
            
            bot.answer_callback_query(call.id, "تمت إضافة 5 نقاط إلى رصيدك! ✅", show_alert=True)
            bot.delete_message(call.message.chat.id, call.message.message_id)
        else:
            bot.answer_callback_query(call.id, "❌ أنت لم تشترك في القناة بعد!", show_alert=True)
    except Exception as e:
        bot.answer_callback_query(call.id, "حدث خطأ. تأكد أن البوت مشرف في القناة المطلوبة.", show_alert=True)

@bot.message_handler(func=lambda message: message.text == "🚀 رشق قناتي")
def add_channel(message):
    cursor.execute("SELECT points FROM users WHERE user_id = ?", (message.chat.id,))
    points = cursor.fetchone()[0]
    
    if points < 50:
        bot.send_message(message.chat.id, f"❌ رصيدك غير كافٍ. تحتاج إلى 50 نقطة على الأقل لإضافة قناتك.\nرصيدك الحالي: {points}")
    else:
        msg = bot.send_message(message.chat.id, "أرسل معرف قناتك (يجب أن يبدأ بـ @)\n\n⚠️ *ملاحظة هامة:* يجب أن ترفع هذا البوت كـ (مشرف) في قناتك ليتمكن من التحقق من انضمام الأعضاء.", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_add_channel)

def process_add_channel(message):
    channel_user = message.text
    if not channel_user.startswith("@"):
        bot.send_message(message.chat.id, "❌ المعرف غير صحيح. يجب أن يبدأ بـ @ (مثال: @mychannel)")
        return
        
    try:
        bot.get_chat(channel_user)
        cursor.execute("UPDATE users SET points = points - 50 WHERE user_id = ?", (message.chat.id,))
        cursor.execute("INSERT OR REPLACE INTO channels (channel_user, owner_id, points) VALUES (?, ?, ?)", (channel_user, message.chat.id, 50))
        conn.commit()
        
        bot.send_message(message.chat.id, "✅ تمت إضافة قناتك بنجاح! سيتم عرضها للأعضاء الآخرين للحصول على المشتركين.")
    except Exception as e:
        bot.send_message(message.chat.id, "❌ البوت لا يستطيع الوصول لقناتك. تأكد من رفع البوت كـ (مشرف) في القناة وأرسل المعرف بشكل صحيح.")

# تشغيل السيرفر والبوت معاً
if __name__ == "__main__":
    keep_alive() # تشغيل سيرفر الويب لضمان بقاء الاستضافة تعمل
    print("بوت الرشق يعمل الآن على الاستضافة يا عبود...")
    bot.infinity_polling(skip_pending=True)
