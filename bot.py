import sqlite3
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import matplotlib.pyplot as plt
import io
import os

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# Инициализация базы данных
def init_db():
    # Создаем папку для данных, если ее нет
    if not os.path.exists('data'):
        os.makedirs('data')

    conn = sqlite3.connect('data/study_assistant.db')
    cursor = conn.cursor()

    # Таблица расписания
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        task TEXT,
        date TEXT,
        time TEXT,
        completed INTEGER DEFAULT 0
    )
    ''')

    # Таблица учебных материалов
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS study_materials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        subject TEXT,
        topic TEXT,
        hours_spent REAL,
        date TEXT
    )
    ''')

    # Таблица целей
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        goal TEXT,
        deadline TEXT,
        progress INTEGER DEFAULT 0,
        completed INTEGER DEFAULT 0
    )
    ''')

    conn.commit()
    conn.close()
    print("База данных инициализирована")


# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.first_name

    keyboard = [
        [InlineKeyboardButton("📅 Расписание", callback_data='schedule')],
        [InlineKeyboardButton("📚 Учеба", callback_data='study')],
        [InlineKeyboardButton("🎯 Цели", callback_data='goals')],
        [InlineKeyboardButton("📊 Аналитика", callback_data='analytics')],
        [InlineKeyboardButton("➕ Добавить задачу", callback_data='add_task')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"Привет, {username}! 👋\n\n"
        "Я твой персональный помощник для:\n"
        "1. 📅 Планирования расписания\n"
        "2. 📚 Контроля обучения\n"
        "3. 🎯 Отслеживания целей\n"
        "4. 📊 Аналитики прогресса\n\n"
        "Выбери нужный раздел:",
        reply_markup=reply_markup
    )


# Обработчик кнопок
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'schedule':
        await show_schedule(query, context)
    elif query.data == 'study':
        await show_study(query, context)
    elif query.data == 'goals':
        await show_goals(query, context)
    elif query.data == 'analytics':
        await show_analytics(query, context)
    elif query.data == 'add_task':
        await add_task_prompt(query, context)
    elif query.data == 'add_study':
        await add_study_prompt(query, context)
    elif query.data == 'add_goal':
        await add_goal_prompt(query, context)
    elif query.data == 'back':
        await start_from_query(query, context)
    elif query.data.startswith('complete_'):
        task_id = int(query.data.split('_')[1])
        await complete_task(query, context, task_id)
    elif query.data.startswith('delete_'):
        task_id = int(query.data.split('_')[1])
        await delete_task(query, context, task_id)


# Показать расписание
async def show_schedule(query, context):
    user_id = query.from_user.id
    conn = sqlite3.connect('data/study_assistant.db')
    cursor = conn.cursor()

    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('''
    SELECT id, task, time, completed 
    FROM schedule 
    WHERE user_id = ? AND date = ?
    ORDER BY time
    ''', (user_id, today))

    tasks = cursor.fetchall()
    conn.close()

    if not tasks:
        text = "📅 На сегодня задач нет!\nДобавьте новую задачу через меню."
    else:
        text = "📅 **Задачи на сегодня:**\n\n"
        for task in tasks:
            status = "✅" if task[3] else "⏳"
            text += f"{status} **{task[2]}** - {task[1]}\n"
            keyboard = [
                [InlineKeyboardButton(f"Выполнить ({task[2]})", callback_data=f'complete_{task[0]}')],
                [InlineKeyboardButton(f"Удалить", callback_data=f'delete_{task[0]}')]
            ]

    keyboard = [
        [InlineKeyboardButton("➕ Добавить задачу", callback_data='add_task')],
        [InlineKeyboardButton("Назад в меню", callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode='Markdown')


# Показать учебные материалы
async def show_study(query, context):
    user_id = query.from_user.id
    conn = sqlite3.connect('data/study_assistant.db')
    cursor = conn.cursor()

    cursor.execute('''
    SELECT subject, SUM(hours_spent) 
    FROM study_materials 
    WHERE user_id = ? 
    GROUP BY subject
    ''', (user_id,))

    subjects = cursor.fetchall()
    conn.close()

    if not subjects:
        text = "📚 Учебные данные отсутствуют."
    else:
        text = "📚 **Статистика по предметам:**\n\n"
        total_hours = 0
        for subject in subjects:
            text += f"**{subject[0]}**: {subject[1]:.1f} часов\n"
            total_hours += subject[1]
        text += f"\n**Всего часов:** {total_hours:.1f}"

    keyboard = [
        [InlineKeyboardButton("➕ Добавить время изучения", callback_data='add_study')],
        [InlineKeyboardButton("Назад в меню", callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode='Markdown')


# Показать цели
async def show_goals(query, context):
    user_id = query.from_user.id
    conn = sqlite3.connect('data/study_assistant.db')
    cursor = conn.cursor()

    cursor.execute('''
    SELECT id, goal, deadline, progress, completed 
    FROM goals 
    WHERE user_id = ? 
    ORDER BY deadline
    ''', (user_id,))

    goals = cursor.fetchall()
    conn.close()

    if not goals:
        text = "🎯 Цели не установлены."
    else:
        text = "🎯 **Ваши цели:**\n\n"
        for goal in goals:
            status = "✅" if goal[4] else "⏳"
            text += f"{status} **{goal[1]}**\n"
            text += f"   📅 Дедлайн: {goal[2]}\n"
            text += f"   📊 Прогресс: {goal[3]}%\n\n"

    keyboard = [
        [InlineKeyboardButton("➕ Добавить цель", callback_data='add_goal')],
        [InlineKeyboardButton("Назад в меню", callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode='Markdown')


# Показать аналитику
async def show_analytics(query, context):
    user_id = query.from_user.id
    conn = sqlite3.connect('data/study_assistant.db')
    cursor = conn.cursor()

    # Статистика по задачам
    cursor.execute('''
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) as completed
    FROM schedule 
    WHERE user_id = ? AND date >= date('now', '-7 days')
    ''', (user_id,))

    tasks_stats = cursor.fetchone()

    # Статистика по учебе
    cursor.execute('''
    SELECT SUM(hours_spent) 
    FROM study_materials 
    WHERE user_id = ? AND date >= date('now', '-7 days')
    ''', (user_id,))

    study_hours = cursor.fetchone()[0] or 0

    # Статистика по целям
    cursor.execute('''
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) as completed
    FROM goals 
    WHERE user_id = ?
    ''', (user_id,))

    goals_stats = cursor.fetchone()

    conn.close()

    # Генерация графика
    fig, ax = plt.subplots(figsize=(10, 6))

    categories = ['Задачи', 'Цели', 'Учеба (часы)']
    values = [
        tasks_stats[1] if tasks_stats and tasks_stats[1] else 0,
        goals_stats[1] if goals_stats and goals_stats[1] else 0,
        study_hours
    ]

    colors = ['#3498db', '#2ecc71', '#e74c3c']
    bars = ax.bar(categories, values, color=colors)
    ax.set_ylabel('Количество')
    ax.set_title('Ваша продуктивность за неделю', fontsize=14, fontweight='bold')

    # Добавление значений на столбцы
    for bar, value in zip(bars, values):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2., height + 0.1,
                f'{value}', ha='center', va='bottom', fontweight='bold')

    # Сохранение графика в буфер
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png', dpi=100)
    buf.seek(0)
    plt.close()

    text = (
        "📊 **Аналитика вашей продуктивности:**\n\n"
        f"✅ **Выполнено задач за неделю:** {tasks_stats[1] if tasks_stats and tasks_stats[1] else 0}/{tasks_stats[0] if tasks_stats else 0}\n"
        f"🎯 **Достигнуто целей:** {goals_stats[1] if goals_stats and goals_stats[1] else 0}/{goals_stats[0] if goals_stats else 0}\n"
        f"📚 **Часов обучения за неделю:** {study_hours:.1f}\n\n"
        "📈 **График вашей активности:**"
    )

    keyboard = [[InlineKeyboardButton("Назад в меню", callback_data='back')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем график
    await query.message.reply_photo(
        photo=buf,
        caption=text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    # Редактируем предыдущее сообщение
    await query.edit_message_text("📊 График аналитики отправлен выше ⬆️")


# Запрос на добавление задачи
async def add_task_prompt(query, context):
    await query.edit_message_text(
        text="📝 **Добавление задачи**\n\n"
             "Введите задачу в формате:\n"
             "`Задача;Дата(ГГГГ-ММ-ДД);Время(ЧЧ:ММ)`\n\n"
             "**Пример:**\n"
             "`Сделать домашку по математике;2024-01-20;18:00`\n\n"
             "Или напишите 'отмена' для отмены.",
        parse_mode='Markdown'
    )
    context.user_data['awaiting_task'] = True


# Запрос на добавление учебного времени
async def add_study_prompt(query, context):
    await query.edit_message_text(
        text="📚 **Добавление времени изучения**\n\n"
             "Введите данные в формате:\n"
             "`Предмет;Тема;Количество часов`\n\n"
             "**Пример:**\n"
             "`Математика;Интегралы;2.5`\n\n"
             "Или напишите 'отмена' для отмены.",
        parse_mode='Markdown'
    )
    context.user_data['awaiting_study'] = True


# Запрос на добавление цели
async def add_goal_prompt(query, context):
    await query.edit_message_text(
        text="🎯 **Добавление цели**\n\n"
             "Введите цель в формате:\n"
             "`Цель;Дедлайн(ГГГГ-ММ-ДД)`\n\n"
             "**Пример:**\n"
             "`Выучить Python;2024-02-28`\n\n"
             "Или напишите 'отмена' для отмены.",
        parse_mode='Markdown'
    )
    context.user_data['awaiting_goal'] = True


# Завершить задачу
async def complete_task(query, context, task_id):
    user_id = query.from_user.id
    conn = sqlite3.connect('data/study_assistant.db')
    cursor = conn.cursor()

    cursor.execute('''
    UPDATE schedule 
    SET completed = 1 
    WHERE id = ? AND user_id = ?
    ''', (task_id, user_id))

    conn.commit()
    conn.close()

    await query.answer("✅ Задача отмечена как выполненная!")
    await show_schedule(query, context)


# Удалить задачу
async def delete_task(query, context, task_id):
    user_id = query.from_user.id
    conn = sqlite3.connect('data/study_assistant.db')
    cursor = conn.cursor()

    cursor.execute('''
    DELETE FROM schedule 
    WHERE id = ? AND user_id = ?
    ''', (task_id, user_id))

    conn.commit()
    conn.close()

    await query.answer("🗑️ Задача удалена!")
    await show_schedule(query, context)


# Начать с query (для кнопки Назад)
async def start_from_query(query, context):
    username = query.from_user.first_name

    keyboard = [
        [InlineKeyboardButton("📅 Расписание", callback_data='schedule')],
        [InlineKeyboardButton("📚 Учеба", callback_data='study')],
        [InlineKeyboardButton("🎯 Цели", callback_data='goals')],
        [InlineKeyboardButton("📊 Аналитика", callback_data='analytics')],
        [InlineKeyboardButton("➕ Добавить задачу", callback_data='add_task')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"Привет, {username}! 👋\n\n"
        "Я твой персональный помощник для:\n"
        "1. 📅 Планирования расписания\n"
        "2. 📚 Контроля обучения\n"
        "3. 🎯 Отслеживания целей\n"
        "4. 📊 Аналитики прогресса\n\n"
        "Выбери нужный раздел:",
        reply_markup=reply_markup
    )


# Обработка текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Проверка на отмену
    if text.lower() in ['отмена', 'cancel', 'отменить']:
        if 'awaiting_task' in context.user_data:
            del context.user_data['awaiting_task']
        if 'awaiting_study' in context.user_data:
            del context.user_data['awaiting_study']
        if 'awaiting_goal' in context.user_data:
            del context.user_data['awaiting_goal']

        await update.message.reply_text("❌ Операция отменена.")
        return

    # Обработка добавления задачи
    if 'awaiting_task' in context.user_data:
        try:
            parts = text.split(';')
            if len(parts) != 3:
                raise ValueError("Неверное количество частей")

            task, date, time = parts[0].strip(), parts[1].strip(), parts[2].strip()

            # Простая валидация даты
            datetime.strptime(date, '%Y-%m-%d')
            datetime.strptime(time, '%H:%M')

            conn = sqlite3.connect('data/study_assistant.db')
            cursor = conn.cursor()

            cursor.execute('''
            INSERT INTO schedule (user_id, task, date, time, completed)
            VALUES (?, ?, ?, ?, 0)
            ''', (user_id, task, date, time))

            conn.commit()
            conn.close()

            await update.message.reply_text(
                f"✅ **Задача добавлена!**\n\n"
                f"📝 **Задача:** {task}\n"
                f"📅 **Дата:** {date}\n"
                f"⏰ **Время:** {time}",
                parse_mode='Markdown'
            )

            del context.user_data['awaiting_task']

        except ValueError as e:
            await update.message.reply_text(
                "❌ **Неверный формат!**\n\n"
                "Правильный формат:\n"
                "`Задача;Дата(ГГГГ-ММ-ДД);Время(ЧЧ:ММ)`\n\n"
                "**Пример:**\n"
                "`Сделать домашку по математике;2024-01-20;18:00`",
                parse_mode='Markdown'
            )
        except Exception as e:
            await update.message.reply_text(
                f"❌ **Ошибка:** {str(e)}\n\n"
                "Попробуйте еще раз или напишите 'отмена'."
            )

    # Обработка добавления времени изучения
    elif 'awaiting_study' in context.user_data:
        try:
            parts = text.split(';')
            if len(parts) != 3:
                raise ValueError("Неверное количество частей")

            subject, topic, hours = parts[0].strip(), parts[1].strip(), parts[2].strip()

            # Проверка что hours - число
            hours_float = float(hours)

            conn = sqlite3.connect('data/study_assistant.db')
            cursor = conn.cursor()

            cursor.execute('''
            INSERT INTO study_materials (user_id, subject, topic, hours_spent, date)
            VALUES (?, ?, ?, ?, ?)
            ''', (user_id, subject, topic, hours_float, datetime.now().strftime('%Y-%m-%d')))

            conn.commit()
            conn.close()

            await update.message.reply_text(
                f"✅ **Время изучения добавлено!**\n\n"
                f"📚 **Предмет:** {subject}\n"
                f"📖 **Тема:** {topic}\n"
                f"⏱️ **Часов:** {hours_float}",
                parse_mode='Markdown'
            )

            del context.user_data['awaiting_study']

        except ValueError as e:
            await update.message.reply_text(
                "❌ **Неверный формат!**\n\n"
                "Правильный формат:\n"
                "`Предмет;Тема;Количество часов`\n\n"
                "**Пример:**\n"
                "`Математика;Интегралы;2.5`",
                parse_mode='Markdown'
            )
        except Exception as e:
            await update.message.reply_text(
                f"❌ **Ошибка:** {str(e)}\n\n"
                "Попробуйте еще раз или напишите 'отмена'."
            )

    # Обработка добавления цели
    elif 'awaiting_goal' in context.user_data:
        try:
            parts = text.split(';')
            if len(parts) != 2:
                raise ValueError("Неверное количество частей")

            goal, deadline = parts[0].strip(), parts[1].strip()

            # Простая валидация даты
            datetime.strptime(deadline, '%Y-%m-%d')

            conn = sqlite3.connect('data/study_assistant.db')
            cursor = conn.cursor()

            cursor.execute('''
            INSERT INTO goals (user_id, goal, deadline, progress, completed)
            VALUES (?, ?, ?, 0, 0)
            ''', (user_id, goal, deadline))

            conn.commit()
            conn.close()

            await update.message.reply_text(
                f"✅ **Цель добавлена!**\n\n"
                f"🎯 **Цель:** {goal}\n"
                f"📅 **Дедлайн:** {deadline}\n"
                f"📊 **Прогресс:** 0%",
                parse_mode='Markdown'
            )

            del context.user_data['awaiting_goal']

        except ValueError as e:
            await update.message.reply_text(
                "❌ **Неверный формат!**\n\n"
                "Правильный формат:\n"
                "`Цель;Дедлайн(ГГГГ-ММ-ДД)`\n\n"
                "**Пример:**\n"
                "`Выучить Python;2024-02-28`",
                parse_mode='Markdown'
            )
        except Exception as e:
            await update.message.reply_text(
                f"❌ **Ошибка:** {str(e)}\n\n"
                "Попробуйте еще раз или напишите 'отмена'."
            )


# Команда помощи
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📋 **Доступные команды:**\n\n"
        "/start - Главное меню\n"
        "/help - Эта справка\n\n"
        "**Как добавить задачу:**\n"
        "1. Нажмите '➕ Добавить задачу'\n"
        "2. Введите: `Задача;Дата;Время`\n"
        "3. Пример: `Урок математики;2024-01-20;14:00`\n\n"
        "**Как добавить время учебы:**\n"
        "1. В разделе '📚 Учеба' нажмите '➕ Добавить время изучения'\n"
        "2. Введите: `Предмет;Тема;Часы`\n"
        "3. Пример: `Физика;Оптика;1.5`\n\n"
        "**Как добавить цель:**\n"
        "1. В разделе '🎯 Цели' нажмите '➕ Добавить цель'\n"
        "2. Введите: `Цель;Дедлайн`\n"
        "3. Пример: `Прочитать книгу;2024-02-15`"
    )

    await update.message.reply_text(help_text, parse_mode='Markdown')


# Основная функция
def main():
    # Инициализация базы данных
    init_db()

    # Токен вашего бота (ЗАМЕНИТЕ НА СВОЙ!)
    TOKEN = "8303843329:AAGWSFZZgZgNnH65a6xztDdD3qg8tElo1IU"

    if TOKEN == "ВАШ_ТОКЕН_ТЕЛЕГРАМ_БОТА":
        print("⚠️ ВНИМАНИЕ: Замените 'ВАШ_ТОКЕН_ТЕЛЕГРАМ_БОТА' на реальный токен!")
        print("Получите токен у @BotFather в Telegram")
        return

    # Создание приложения
    application = Application.builder().token(TOKEN).build()

    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    # Обработчики кнопок
    application.add_handler(CallbackQueryHandler(button_handler))

    # Обработчики сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запуск бота
    print("=" * 50)
    print("🤖 Бот запускается...")
    print(f"📁 База данных: data/study_assistant.db")
    print("=" * 50)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()