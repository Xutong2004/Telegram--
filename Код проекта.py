import yfinance as yf
import logging
import io
import matplotlib.pyplot as plt
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)
import pandas as pd
import numpy as np

# ==================== Инициализация настроек ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== Конфигурация многоязычности ====================
LANGUAGES = {
    "en": {
        "welcome": "📈 Stock Dividend Bot\nType /help for commands",
        "no_args": "Please enter a stock symbol, e.g.: /dividend AAPL",
        "fetching": "Fetching {symbol} data...",
        "no_data": "{symbol} has no dividend data",
        "dividend_info": "🏦 Company: {name}\n💰 Price: {price}\n📈 Yield: {yield_pct}%\n\nRecent dividends:",
        "chart_btn": "View Chart",
        "error": "Data fetch failed",
        "lang_set": "Language set to English",
        "choose_lang": "Choose language:",
        "portfolio_empty": "Your portfolio is empty",
        "portfolio_header": "📊 Your Portfolio:\n",
        "lesson_menu": "Choose a lesson:",
        "risk_info": "📊 {symbol} Risk\nVolatility: {volatility:.2%}\nRisk: {risk_level}",
        "help_text": """📚 <b>Help</b>

<u>Core</u>
/start - Show welcome
/help - This guide
/language - Change language
/dividend &lt;symbol&gt; - Dividend info

<u>Portfolio</u>
/add &lt;symbol&gt; - Add stock
/portfolio - View portfolio

<u>Analysis</u>
/risk &lt;symbol&gt; - Risk analysis

<u>Education</u>
/learn - Investment lessons""",
        "help_portfolio": "📦 <b>Portfolio Help</b>\n\n/add to add stocks\n/portfolio to view",
        "help_risk": "⚠️ <b>Risk Help</b>\n\n/risk calculates stock volatility",
        "help_dividend": "💰 <b>Dividend Help</b>\n\n/dividend shows last 4 payments"
    },
    
    "ru": {
        "welcome": "📈 Бот дивидендов\nНапишите /help для команд",
        "no_args": "Введите тикер, например: /dividend AAPL",
        "fetching": "Получение данных {symbol}...",
        "no_data": "{symbol} нет данных о дивидендах",
        "dividend_info": "🏦 Компания: {name}\n💰 Цена: {price}\n📈 Доходность: {yield_pct}%\n\nПоследние дивиденды:",
        "chart_btn": "График",
        "error": "Ошибка получения данных",
        "lang_set": "Язык изменен на русский",
        "choose_lang": "Выберите язык:",
        "portfolio_empty": "Ваш портфель пуст",
        "portfolio_header": "📊 Ваш портфель:\n",
        "lesson_menu": "Выберите урок:",
        "risk_info": "📊 Риск {symbol}\nВолатильность: {volatility:.2%}\nУровень: {risk_level}",
        "help_text": """📚 <b>Помощь</b>

<u>Основное</u>
/start - Приветствие
/help - Эта справка
/language - Сменить язык
/dividend &lt;тикер&gt; - Инфо о дивидендах

<u>Портфель</u>
/add &lt;тикер&gt; - Добавить акцию
/portfolio - Показать портфель

<u>Анализ</u>
/risk &lt;тикер&gt; - Анализ риска

<u>Обучение</u>
/learn - Уроки инвестирования""",
        "help_portfolio": "📦 <b>Помощь по портфелю</b>\n\n/add добавить\n/portfolio просмотр",
        "help_risk": "⚠️ <b>Помощь по риску</b>\n\n/risk расчет волатильности",
        "help_dividend": "💰 <b>Помощь по дивидендам</b>\n\n/dividend последние 4 выплаты"
    }
}

# ==================== Сохранение данных ====================
user_data = {}  # {user_id: {'language': 'en', 'portfolio': []}}

# ==================== Конфигурация системы обучения ====================
LESSONS = {
    1: {
        "title": {
            "en": "📚 Lesson 1: Dividends Basics",
            "ru": "📚 Урок 1: Основы дивидендов"
        },
        "content": {
            "en": "Dividend: A portion of a company’s profit paid to shareholders.",
            "ru": "Дивиденды: часть прибыли компании, выплачиваемая акционерам."
        }
    },
    2: {
        "title": {
            "en": "📈 Lesson 2: Dividend Safety",
            "ru": "📈 Урок 2: Безопасность дивидендов"
        },
        "content": {
            "en": "Assess dividend safety using payout ratios.",
            "ru": "Оцените безопасность через коэффициент выплат."
        }
    }
}


# ==================== Ядровые функции ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команды /start"""
    user_id = update.effective_user.id
    lang = user_data.get(user_id, {}).get('language', 'en')
    await update.message.reply_text(LANGUAGES[lang]["welcome"])


async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установка языка"""
    user_id = update.effective_user.id
    lang = user_data.get(user_id, {}).get('language', 'en')

    buttons = [
        ["English", "Русский"]
    ]
    await update.message.reply_text(
        LANGUAGES[lang]["choose_lang"],
        reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True)
    )


async def handle_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора языка"""
    text = update.message.text
    lang_map = {"English": "en", "Русский": "ru"}

    if text in lang_map:
        user_id = update.effective_user.id
        if user_id not in user_data:
            user_data[user_id] = {}
        user_data[user_id]['language'] = lang_map[text]
        await update.message.reply_text(
            LANGUAGES[lang_map[text]]["lang_set"],
            reply_markup=ReplyKeyboardRemove()
        )


# ==================== Функции по дивидендам ====================
async def dividend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрос дивидендов"""
    user_id = update.effective_user.id
    lang = user_data.get(user_id, {}).get('language', 'en')

    if not context.args:
        await update.message.reply_text(LANGUAGES[lang]["no_args"])
        return

    symbol = context.args[0].upper()
    await update.message.reply_text(LANGUAGES[lang]["fetching"].format(symbol=symbol))

    try:
        stock = yf.Ticker(symbol)
        dividends = stock.dividends

        if dividends.empty:
            await update.message.reply_text(LANGUAGES[lang]["no_data"].format(symbol=symbol))
            return

        info = stock.info
        dividend_yield = round(info.get('dividendYield', 0) * 100, 2)

        message = LANGUAGES[lang]["dividend_info"].format(
            name=info.get('longName', symbol),
            price=info.get('currentPrice', 'N/A'),
            yield_pct=dividend_yield
        )

        for date, amount in dividends.tail(4).items():
            message += f"\n📅 {date.date()}: ${amount:.2f}"

        keyboard = [[
            InlineKeyboardButton(
                LANGUAGES[lang]["chart_btn"],
                callback_data=f"chart_{lang}_{symbol}"
            )
        ]]
        await update.message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(LANGUAGES[lang]["error"])


async def dividend_chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """График дивидендов"""
    query = update.callback_query
    await query.answer()

    _, lang, symbol = query.data.split('_')
    stock = yf.Ticker(symbol)

    plt.figure(figsize=(10, 5))
    dividends = stock.dividends
    dividends.plot(kind='bar')
    plt.title(f"{symbol} Dividends")
    plt.ylabel("Amount ($)")
    plt.xticks(rotation=45)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    plt.close()

    await query.message.reply_photo(
        photo=buf,
        caption=f"{symbol} {LANGUAGES[lang]['chart_btn']}"
    )


# ==================== Портфель ====================
async def add_to_portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавление акции"""
    user_id = update.effective_user.id
    lang = user_data.get(user_id, {}).get('language', 'en')

    if not context.args:
        await update.message.reply_text("Usage: /add <symbol>")
        return

    symbol = context.args[0].upper()

    if user_id not in user_data:
        user_data[user_id] = {'portfolio': []}
    elif 'portfolio' not in user_data[user_id]:
        user_data[user_id]['portfolio'] = []

    if symbol not in user_data[user_id]['portfolio']:
        user_data[user_id]['portfolio'].append(symbol)
        await update.message.reply_text(f"✅ {symbol} added to portfolio")
    else:
        await update.message.reply_text(f"ℹ️ {symbol} already in portfolio")


async def show_portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ портфеля"""
    user_id = update.effective_user.id
    lang = user_data.get(user_id, {}).get('language', 'en')

    if user_id not in user_data or 'portfolio' not in user_data[user_id] or not user_data[user_id]['portfolio']:
        await update.message.reply_text(LANGUAGES[lang]["portfolio_empty"])
        return

    message = LANGUAGES[lang]["portfolio_header"]
    total_value = 0

    for symbol in user_data[user_id]['portfolio']:
        try:
            stock = yf.Ticker(symbol)
            price = stock.history(period='1d')['Close'].iloc[-1]
            message += f"\n{symbol}: ${price:.2f}"
            total_value += price
        except Exception as e:
            message += f"\n{symbol}: Error"
            logger.error(f"Price fetch failed: {e}")

    message += f"\n\n💵 Total: ${total_value:.2f}"
    await update.message.reply_text(message)


# ==================== Система обучения ====================
async def start_education(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню обучения"""
    user_id = update.effective_user.id
    lang = user_data.get(user_id, {}).get('language', 'en')

    keyboard = [
        [InlineKeyboardButton(LESSONS[num]['title'][lang], callback_data=f"lesson_{num}")]
        for num in LESSONS
    ]
    await update.message.reply_text(
        LANGUAGES[lang]["lesson_menu"],
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_lesson(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать урок"""
    query = update.callback_query
    await query.answer()

    lesson_num = int(query.data.split('_')[1])
    user_id = update.effective_user.id
    lang = user_data.get(user_id, {}).get('language', 'en')

    lesson = LESSONS[lesson_num]
    await query.edit_message_text(
        f"{lesson['title'][lang]}\n\n{lesson['content'][lang]}"
    )


# ==================== Анализ рисков ====================
async def analyze_risk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Анализ рисков"""
    user_id = update.effective_user.id
    lang = user_data.get(user_id, {}).get('language', 'en')

    if not context.args:
        await update.message.reply_text("Usage: /risk <symbol>")
        return

    symbol = context.args[0].upper()

    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="1y")

        if hist.empty:
            await update.message.reply_text(f"No data for {symbol}")
            return

        returns = hist['Close'].pct_change().dropna()
        volatility = returns.std() * np.sqrt(252)

        if volatility > 0.3:
            risk_level = "High" if lang == "en" else "Высокий"
        elif volatility > 0.15:
            risk_level = "Medium" if lang == "en" else "Средний"
        else:
            risk_level = "Low" if lang == "en" else "Низкий"

        await update.message.reply_text(
            LANGUAGES[lang]["risk_info"].format(
                symbol=symbol,
                volatility=volatility,
                risk_level=risk_level
            )
        )

        plt.figure(figsize=(10, 5))
        returns.plot(kind='line', title=f"{symbol} Returns")
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()
        await update.message.reply_photo(photo=buf)

    except Exception as e:
        logger.error(f"Risk analysis failed: {e}")
        await update.message.reply_text(f"Error: {str(e)}")


# ==================== Система помощи ====================
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда помощи"""
    user_id = update.effective_user.id
    lang = user_data.get(user_id, {}).get('language', 'en')

    keyboard = [
        [InlineKeyboardButton(
            "Portfolio Help" if lang == "en" else
            "Помощь по портфелю",
            callback_data="help_portfolio")],
        [InlineKeyboardButton(
            "Risk Help" if lang == "en" else
            "Помощь по риску",
            callback_data="help_risk")],
        [InlineKeyboardButton(
            "Dividend Help" if lang == "en" else
            "Помощь по дивидендам",
            callback_data="help_dividend")]
    ]

    await update.message.reply_text(
        LANGUAGES[lang]["help_text"],
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )


async def help_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок помощи"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    lang = user_data.get(user_id, {}).get('language', 'en')

    help_type = query.data.split("_")[1]
    text = LANGUAGES[lang][f"help_{help_type}"]

    await query.edit_message_text(
        text=text,
        parse_mode="HTML"
    )


# ==================== Главная функция ====================
def main():
    """Запуск бота"""
    application = Application.builder().token("8143486168:AAF5pDrwsSoSHzacJY3HJI9fipjA56ptX0c").build()

    # Регистрация команд
    cmd_handlers = [
        CommandHandler("start", start),
        CommandHandler("help", help_command),
        CommandHandler("language", set_language),
        CommandHandler("dividend", dividend),
        CommandHandler("add", add_to_portfolio),
        CommandHandler("portfolio", show_portfolio),
        CommandHandler("learn", start_education),
        CommandHandler("risk", analyze_risk)
    ]
    for handler in cmd_handlers:
        application.add_handler(handler)

    # Регистрация коллбэков
    callback_handlers = [
        CallbackQueryHandler(handle_language, pattern="^lang_"),
        CallbackQueryHandler(dividend_chart, pattern="^chart_"),
        CallbackQueryHandler(show_lesson, pattern="^lesson_"),
        CallbackQueryHandler(help_button_handler, pattern="^help_")
    ]
    for handler in callback_handlers:
        application.add_handler(handler)

    # Регистрация обработчика текстовых сообщений
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_language
    ))

    application.run_polling()


if __name__ == '__main__':
    main()