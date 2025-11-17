import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import sqlite3
import json

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота
BOT_TOKEN = "8359470099:AAHwFgFRzeoTs7DgD9LjoyRKOq2ooRFEtv4"

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('anon_messages.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            messages_count INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user_id INTEGER,
            to_user_id INTEGER,
            message_text TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_answered BOOLEAN DEFAULT FALSE,
            original_message_id INTEGER,
            FOREIGN KEY (to_user_id) REFERENCES users (user_id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Функция для получения или создания пользователя
def get_or_create_user(user_id, username):
    conn = sqlite3.connect('anon_messages.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        cursor.execute(
            'INSERT INTO users (user_id, username) VALUES (?, ?)',
            (user_id, username)
        )
        conn.commit()
    
    conn.close()

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_or_create_user(user.id, user.username)
    
    # Если есть аргументы (переход по ссылке)
    if context.args:
        target_user_id = context.args[0]
        
        try:
            target_user_id = int(target_user_id)
            
            # Проверяем существование пользователя
            conn = sqlite3.connect('anon_messages.db')
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (target_user_id,))
            target_user = cursor.fetchone()
            conn.close()
            
            if target_user:
                # Сохраняем ID целевого пользователя для следующего сообщения
                context.user_data['sending_to'] = target_user_id
                
                # Получаем username целевого пользователя для красивого отображения
                target_username = target_user[1] if target_user[1] else "пользователю"
                
                await update.message.reply_text(
                    f"✍️ **Отправьте анонимное сообщение для @{target_username}:**\n\n"
                    "Напишите сообщение которое будет отправлено анонимно владельцу этой ссылки.\n\n"
                    "💡 *Сообщение будет полностью анонимным*",
                    parse_mode='Markdown'
                )
                return
            else:
                await update.message.reply_text("❌ Пользователь не найден")
        
        except ValueError:
            await update.message.reply_text("❌ Неверная ссылка")
    
    # Если нет аргументов - показываем главное меню
    keyboard = [
        [InlineKeyboardButton("📱 Профиль", callback_data="profile")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        "Это бот для анонимных сообщений.\n"
        "Получи свою ссылку и делись с друзьями!",
        reply_markup=reply_markup
    )

# Обработчик кнопок
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    
    if query.data == "profile":
        # Генерируем ссылку для пользователя
        bot_username = context.bot.username
        profile_link = f"https://t.me/{bot_username}?start={user.id}"
        
        # Получаем статистику
        conn = sqlite3.connect('anon_messages.db')
        cursor = conn.cursor()
        cursor.execute('SELECT messages_count FROM users WHERE user_id = ?', (user.id,))
        result = cursor.fetchone()
        messages_count = result[0] if result else 0
        conn.close()
        
        keyboard = [
            [InlineKeyboardButton("🔗 Копировать ссылку", 
                                callback_data="copy_link")],
            [InlineKeyboardButton("📨 Мои сообщения", callback_data="my_messages")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"👤 **Твой профиль**\n\n"
            f"🆔 @{user.username or 'без username'}\n"
            f"📊 Получено сообщений: {messages_count}\n\n"
            f"**Твоя ссылка для анонимных сообщений:**\n`{profile_link}`\n\n"
            f"Поделись ссылкой чтобы получать анонимные сообщения!",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        # Сохраняем ссылку в контексте для копирования
        context.user_data['profile_link'] = profile_link
    
    elif query.data == "copy_link":
        profile_link = context.user_data.get('profile_link', '')
        if profile_link:
            await query.message.reply_text(
                f"🔗 **Ваша ссылка:**\n\n`{profile_link}`\n\n"
                "Скопируйте и поделитесь этой ссылкой!",
                parse_mode='Markdown'
            )
    
    elif query.data == "my_messages":
        await show_my_messages(query, context)
    
    elif query.data == "help":
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "❓ **Помощь**\n\n"
            "📱 **Профиль** - получи свою ссылку для анонимных сообщений\n"
            "📨 **Мои сообщения** - просмотр и ответ на полученные сообщения\n\n"
            "💡 **Как использовать:**\n"
            "1. Получи свою ссылку в разделе 'Профиль'\n"
            "2. Поделись ссылкой с друзьями\n"
            "3. Получай анонимные сообщения\n"
            "4. Отвечай на сообщения через 'Мои сообщения'\n\n"
            "🔗 **Как отправить сообщение:**\n"
            "Просто перейди по чужой ссылке и напиши сообщение!",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    elif query.data == "back_to_main":
        keyboard = [
            [InlineKeyboardButton("📱 Профиль", callback_data="profile")],
            [InlineKeyboardButton("❓ Помощь", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "👋 Главное меню\n\n"
            "Выберите действие:",
            reply_markup=reply_markup
        )

# Показать сообщения пользователя
async def show_my_messages(query, context):
    user_id = query.from_user.id
    
    conn = sqlite3.connect('anon_messages.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT m.message_id, m.message_text, m.timestamp, m.is_answered 
        FROM messages m 
        WHERE m.to_user_id = ? 
        ORDER BY m.timestamp DESC
    ''', (user_id,))
    
    messages = cursor.fetchall()
    conn.close()
    
    if not messages:
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="profile")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📭 У вас пока нет сообщений\n\n"
            "Поделитесь своей ссылкой чтобы получать анонимные сообщения!",
            reply_markup=reply_markup
        )
        return
    
    # Показываем первое сообщение с пагинацией
    await show_message_page(query, context, messages, 0)

# Показать страницу с сообщением
async def show_message_page(query, context, messages, page_index):
    message_id, message_text, timestamp, is_answered = messages[page_index]
    
    keyboard = []
    
    if not is_answered:
        keyboard.append([InlineKeyboardButton("💬 Ответить", callback_data=f"reply_{message_id}")])
    
    nav_buttons = []
    if page_index > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Пред", callback_data=f"page_{page_index-1}"))
    if page_index < len(messages) - 1:
        nav_buttons.append(InlineKeyboardButton("След ➡️", callback_data=f"page_{page_index+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="profile")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    status = "✅ Отвечено" if is_answered else "🆕 Новое"
    
    await query.edit_message_text(
        f"📨 **Сообщение {page_index + 1}/{len(messages)}**\n\n"
        f"{message_text}\n\n"
        f"🕒 {timestamp}\n"
        f"📊 {status}",
        reply_markup=reply_markup
    )
    
    # Сохраняем данные о сообщениях в контекст
    context.user_data['current_messages'] = messages
    context.user_data['current_page'] = page_index

# Обработчик пагинации
async def handle_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if data.startswith('page_'):
        page_index = int(data.split('_')[1])
        messages = context.user_data.get('current_messages', [])
        await show_message_page(query, context, messages, page_index)

# Обработчик кнопки "Ответить"
async def handle_reply_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    message_id = int(query.data.split('_')[1])
    
    # Сохраняем ID сообщения для ответа
    context.user_data['replying_to'] = message_id
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_reply")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "💬 **Отправьте ваш ответ:**\n\n"
        "Напишите сообщение которое будет отправлено анонимно автору исходного сообщения.",
        reply_markup=reply_markup
    )

# Отмена ответа
async def cancel_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if 'replying_to' in context.user_data:
        del context.user_data['replying_to']
    
    await show_my_messages(query, context)

# Обработка текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message_text = update.message.text
    
    # Если пользователь отвечает на сообщение
    if 'replying_to' in context.user_data:
        original_message_id = context.user_data['replying_to']
        
        conn = sqlite3.connect('anon_messages.db')
        cursor = conn.cursor()
        
        # Получаем информацию об оригинальном сообщении
        cursor.execute('''
            SELECT from_user_id, to_user_id, message_text 
            FROM messages 
            WHERE message_id = ?
        ''', (original_message_id,))
        
        original_msg = cursor.fetchone()
        
        if original_msg:
            from_user_id, to_user_id, original_text = original_msg
            
            # Проверяем что отвечает владелец сообщения
            if to_user_id == user.id:
                # Сохраняем ответ
                cursor.execute('''
                    INSERT INTO messages (from_user_id, to_user_id, message_text, is_answered, original_message_id)
                    VALUES (?, ?, ?, TRUE, ?)
                ''', (user.id, from_user_id, message_text, original_message_id))
                
                # Помечаем оригинальное сообщение как отвеченное
                cursor.execute('''
                    UPDATE messages SET is_answered = TRUE WHERE message_id = ?
                ''', (original_message_id,))
                
                # Обновляем счетчик сообщений у получателя
                cursor.execute('''
                    UPDATE users SET messages_count = messages_count + 1 WHERE user_id = ?
                ''', (from_user_id,))
                
                conn.commit()
                
                # Отправляем ответ пользователю
                try:
                    await context.bot.send_message(
                        chat_id=from_user_id,
                        text=f"💌 **Вам ответ на анонимное сообщение:**\n\n{message_text}"
                    )
                except Exception as e:
                    logger.error(f"Не удалось отправить ответ пользователю {from_user_id}: {e}")
                
                await update.message.reply_text("✅ Ответ отправлен!")
            else:
                await update.message.reply_text("❌ Ошибка: вы не можете ответить на это сообщение")
        else:
            await update.message.reply_text("❌ Ошибка: сообщение не найдено")
        
        # Очищаем контекст
        if 'replying_to' in context.user_data:
            del context.user_data['replying_to']
        
        conn.close()
        return
    
    # Если пользователь отправляет анонимное сообщение (после перехода по ссылке)
    elif 'sending_to' in context.user_data:
        target_user_id = context.user_data['sending_to']
        
        # Сохраняем сообщение в базу
        conn = sqlite3.connect('anon_messages.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO messages (from_user_id, to_user_id, message_text)
            VALUES (?, ?, ?)
        ''', (user.id, target_user_id, message_text))
        
        # Обновляем счетчик сообщений
        cursor.execute('''
            UPDATE users SET messages_count = messages_count + 1 WHERE user_id = ?
        ''', (target_user_id,))
        
        conn.commit()
        conn.close()
        
        # Уведомляем целевого пользователя
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"📨 **Новое анонимное сообщение:**\n\n{message_text}"
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя {target_user_id}: {e}")
        
        await update.message.reply_text("✅ Сообщение отправлено анонимно!")
        
        # Очищаем контекст
        del context.user_data['sending_to']
    
    else:
        # Обычное сообщение - показываем меню
        keyboard = [
            [InlineKeyboardButton("📱 Профиль", callback_data="profile")],
            [InlineKeyboardButton("❓ Помощь", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "👋 Выберите действие:",
            reply_markup=reply_markup
        )

# Основная функция
def main():
    # Инициализация базы данных
    init_db()
    
    # Создание приложения
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    
    # Обработчики кнопок
    application.add_handler(CallbackQueryHandler(button_handler, pattern="^(profile|help|back_to_main|my_messages|copy_link)$"))
    application.add_handler(CallbackQueryHandler(handle_pagination, pattern="^page_"))
    application.add_handler(CallbackQueryHandler(handle_reply_button, pattern="^reply_"))
    application.add_handler(CallbackQueryHandler(cancel_reply, pattern="^cancel_reply$"))
    
    # Обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запуск бота
    print("Бот запущен...")
    application.run_polling()

if __name__ == '__main__':
    main()
