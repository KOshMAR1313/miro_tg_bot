import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, CallbackQueryHandler, filters
import requests

# ========== НАСТРОЙКИ ==========
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
MIRO_ACCESS_TOKEN = os.environ.get("MIRO_ACCESS_TOKEN")
MIRO_HEADERS = {"Authorization": f"Bearer {MIRO_ACCESS_TOKEN}", "Content-Type": "application/json"}

MIRO_BOARDS = {
    "Личное": "<YOUR_PERSONAL_BOARD_ID>",
    "Работа": "<YOUR_WORK_BOARD_ID>"
}

# ========== ЛОГИ ==========
logging.basicConfig(level=logging.INFO)

# ========== ОБРАБОТКА /start ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отправьте задачу, чтобы начать.")

# ========== ОБРАБОТКА СООБЩЕНИЯ ==========
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['task_text'] = update.message.text

    keyboard = [
        [InlineKeyboardButton("Личное", callback_data="board_Личное"),
         InlineKeyboardButton("Работа", callback_data="board_Работа")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Выберите доску:", reply_markup=reply_markup)

# ========== ОБРАБОТКА КНОПОК ==========
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("board_"):
        board_name = data.split("_")[1]
        context.user_data['board_name'] = board_name

        board_id = MIRO_BOARDS[board_name]

        # Получение Kanban структуры
        url = f"https://api.miro.com/v2/boards/{board_id}/items"
        response = requests.get(url, headers=MIRO_HEADERS)
        data = response.json()

        kanban_id = None
        for item in data.get("data", []):
            if item["type"] == "kanban":
                kanban_id = item["id"]
                break

        if kanban_id is None:
            await query.edit_message_text("Kanban не найден на доске.")
            return

        # Получение колонок Kanban
        url = f"https://api.miro.com/v2/boards/{board_id}/items/{kanban_id}"
        response = requests.get(url, headers=MIRO_HEADERS)
        kanban_data = response.json()

        columns = kanban_data.get("columns", [])

        keyboard = []
        for col in columns:
            col_title = col["title"]
            col_id = col["id"]
            keyboard.append([InlineKeyboardButton(col_title, callback_data=f"column_{col_id}")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Выберите колонку:", reply_markup=reply_markup)

    elif data.startswith("column_"):
        column_id = data.split("_")[1]
        board_name = context.user_data.get('board_name')
        board_id = MIRO_BOARDS[board_name]
        task_text = context.user_data.get('task_text')

        # Создание карточки
        url = "https://api.miro.com/v2/cards"
        payload = {
            "data": {
                "title": task_text,
                "description": "Добавлено через Telegram Bot"
            },
            "parent": {
                "id": column_id,
                "type": "kanban-column"
            }
        }

        response = requests.post(url, json=payload, headers=MIRO_HEADERS)

        if response.status_code == 201:
            await query.edit_message_text("Задача успешно добавлена в Miro!")
        else:
            await query.edit_message_text(f"Ошибка при добавлении задачи: {response.text}")

# ========== ОСНОВНОЙ ЗАПУСК ==========
async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_handler(CallbackQueryHandler(button))

    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
