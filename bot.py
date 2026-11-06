import os
import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("market-analyzer")
KYIV = ZoneInfo("Europe/Kyiv")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Yahoo Finance symbols for ordinary (non-OTC) market data.
PAIRS = {
    "EUR/JPY": "EURJPY=X",
    "GBP/JPY": "GBPJPY=X",
    "EUR/CAD": "EURCAD=X",
    "AUD/CAD": "AUDCAD=X",
    "AUD/CHF": "AUDCHF=X",
    "AUD/JPY": "AUDJPY=X",
    "AUD/USD": "AUDUSD=X",
    "CAD/CHF": "CADCHF=X",
    "CAD/JPY": "CADJPY=X",
    "CHF/JPY": "CHFJPY=X",
    "EUR/CHF": "EURCHF=X",
    "EUR/USD": "EURUSD=X",
    "GBP/AUD": "GBPAUD=X",
    "GBP/CAD": "GBPCAD=X",
    "GBP/CHF": "GBPCHF=X",
    "GBP/USD": "GBPUSD=X",
    "USD/CAD": "CAD=X",
    "USD/CHF": "CHF=X",
    "USD/JPY": "JPY=X",
    "EUR/AUD": "EURAUD=X",
    "EUR/GBP": "EURGBP=X",
}
DURATIONS = {"1 хв": 60, "3 хв": 180, "5 хв": 300}

def keyboard(context):
    pair = context.user_data.get("pair", "EUR/JPY")
    duration = context.user_data.get("duration", "1 хв")
    rows = []
    names = list(PAIRS)
    for i in range(0, len(names), 3):
        rows.append([
            InlineKeyboardButton(
                ("• " if p == pair else "") + p,
                callback_data=f"pair|{p}"
            ) for p in names[i:i+3]
        ])
    rows.append([
        InlineKeyboardButton(
            ("• " if d == duration else "") + d,
            callback_data=f"duration|{d}"
        ) for d in DURATIONS
    ])
    rows.append([InlineKeyboardButton("📊 Новий навчальний аналіз", callback_data="analyze")])
    return InlineKeyboardMarkup(rows)

def now_kyiv():
    return datetime.now(KYIV)

def download_prices(pair, period="1d", interval="1m"):
    ticker = PAIRS[pair]
    data = yf.download(
        ticker, period=period, interval=interval,
        progress=False, auto_adjust=True, threads=False
    )
    if data is None or data.empty:
        raise RuntimeError("Постачальник зараз не повернув котирування для цієї пари.")
    close = data["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    close = close.dropna()
    if len(close) < 30:
        raise RuntimeError("Поки недостатньо даних для розрахунку індикаторів.")
    return close

def make_snapshot(pair):
    close = download_prices(pair)
    ema_fast = close.ewm(span=12, adjust=False).mean()
    ema_slow = close.ewm(span=26, adjust=False).mean()
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, float("nan"))
    rsi = 100 - 100 / (1 + rs)
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=9, adjust=False).mean()

    last_price = float(close.iloc[-1])
    rsi_value = float(rsi.iloc[-1])
    ema_up = float(ema_fast.iloc[-1]) > float(ema_slow.iloc[-1])
    macd_up = float(macd.iloc[-1]) > float(macd_signal.iloc[-1])
    rsi_up = rsi_value >= 50

    up_votes = sum((ema_up, macd_up, rsi_up))
    down_votes = 3 - up_votes
    if up_votes >= 2:
        direction = "UP ↑"
        direction_key = "UP"
    elif down_votes >= 2:
        direction = "DOWN ↓"
        direction_key = "DOWN"
    else:
        direction = "Немає узгодженого напрямку"
        direction_key = "FLAT"

    agreement = max(up_votes, down_votes) / 3 * 100
    return {
        "price": last_price,
        "rsi": rsi_value,
        "ema_up": ema_up,
        "macd_up": macd_up,
        "direction": direction,
        "direction_key": direction_key,
        "agreement": agreement,
    }

def fmt_price(value):
    return f"{value:.6f}" if abs(value) < 100 else f"{value:.3f}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.setdefault("pair", "EUR/JPY")
    context.user_data.setdefault("duration", "1 хв")
    await update.message.reply_text(
        "Привіт! Це навчальний аналізатор звичайних валютних пар (не OTC).\n\n"
        "Обери пару й тривалість спостереження, потім натисни «Новий навчальний аналіз».\n"
        "Відсоток означає лише узгодженість 3 індикаторів, а не ймовірність виграшу.\n"
        "Дані надходять від Yahoo Finance, можуть запізнюватися або бути недоступними. "
        "Це не підключення до Pocket Option і не команда для реальної угоди.",
        reply_markup=keyboard(context),
    )

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("pair|"):
        context.user_data["pair"] = data.split("|", 1)[1]
        await query.edit_message_text(
            f"Обрана пара: {context.user_data['pair']}\n"
            f"Тривалість: {context.user_data.get('duration', '1 хв')}\n"
            "Коли будеш готовий, натисни кнопку нижче.",
            reply_markup=keyboard(context),
        )
        return

    if data.startswith("duration|"):
        context.user_data["duration"] = data.split("|", 1)[1]
        await query.edit_message_text(
            f"Пара: {context.user_data.get('pair', 'EUR/JPY')}\n"
            f"Тривалість спостереження: {context.user_data['duration']}",
            reply_markup=keyboard(context),
        )
        return

    if data == "analyze":
        if context.user_data.get("running"):
            await query.answer("Поточне спостереження ще триває.", show_alert=True)
            return
        pair = context.user_data.get("pair", "EUR/JPY")
        duration_name = context.user_data.get("duration", "1 хв")
        seconds = DURATIONS[duration_name]
        await query.edit_message_text("Отримую доступні котирування й обчислюю індикатори…")
        try:
            snap = await asyncio.to_thread(make_snapshot, pair)
        except Exception as exc:
            log.exception("Quote/analysis error")
            await query.message.reply_text(
                f"Не вдалося отримати дані для {pair}.\n"
                f"Спробуй пізніше. Деталі: {str(exc)[:180]}",
                reply_markup=keyboard(context),
            )
            return

        if snap["direction_key"] == "FLAT":
            await query.message.reply_text(
                f"Навчальний аналіз {pair}\n"
                "Індикатори не мають узгодженого напрямку.\n"
                f"RSI: {snap['rsi']:.1f}\n"
                f"Остання доступна ціна: {fmt_price(snap['price'])}\n\n"
                "Новий таймер не запущено, бо напрямок нечіткий.",
                reply_markup=keyboard(context),
            )
            return

        start_time = now_kyiv()
        end_time = start_time.timestamp() + seconds
        end_dt = datetime.fromtimestamp(end_time, KYIV)
        context.user_data["running"] = True
        message = await query.message.reply_text(
            f"Навчальне спостереження: {pair}\n"
            f"Напрямок індикаторів: {snap['direction']}\n"
            f"Узгодженість індикаторів: {snap['agreement']:.0f}% (це НЕ шанс виграшу)\n"
            f"RSI(14): {snap['rsi']:.1f}\n"
            f"Стартова ціна: {fmt_price(snap['price'])}\n\n"
            f"Початок спостереження: {start_time:%H:%M:%S} Київ\n"
            f"Кінець спостереження: {end_dt:%H:%M:%S} Київ\n"
            f"Залишилося: {seconds} сек.\n\n"
            "Це лише навчальна перевірка руху ціни, не сигнал для ставки."
        )
        try:
            for remaining in range(seconds - 1, -1, -1):
                await asyncio.sleep(1)
                if remaining % 5 == 0 or remaining <= 5:
                    await message.edit_text(
                        f"Навчальне спостереження: {pair}\n"
                        f"Напрямок індикаторів: {snap['direction']}\n"
                        f"Узгодженість індикаторів: {snap['agreement']:.0f}% (не шанс виграшу)\n"
                        f"Початок: {start_time:%H:%M:%S} Київ\n"
                        f"Завершення: {end_dt:%H:%M:%S} Київ\n"
                        f"До завершення: {remaining} сек."
                    )
            end_close = await asyncio.to_thread(download_prices, pair)
            final_price = float(end_close.iloc[-1])
            change_up = final_price > snap["price"]
            change_down = final_price < snap["price"]
            matched = (
                (snap["direction_key"] == "UP" and change_up) or
                (snap["direction_key"] == "DOWN" and change_down)
            )
            if final_price == snap["price"]:
                result = "Результат невизначений: доступна ціна не змінилася."
            elif matched:
                result = "Прогнозований напрямок збігся з рухом ціни: +1 навчальний бал."
                context.user_data["wins"] = context.user_data.get("wins", 0) + 1
            else:
                result = "Прогнозований напрямок не збігся з рухом ціни: −1 навчальний бал."
                context.user_data["losses"] = context.user_data.get("losses", 0) + 1

            wins = context.user_data.get("wins", 0)
            losses = context.user_data.get("losses", 0)
            total = wins + losses
            accuracy = (wins / total * 100) if total else 0
            await message.edit_text(
                f"Спостереження завершено: {pair}\n"
                f"Початкова ціна: {fmt_price(snap['price'])}\n"
                f"Кінцева доступна ціна: {fmt_price(final_price)}\n"
                f"Напрямок моделі: {snap['direction']}\n\n"
                f"{result}\n\n"
                f"Навчальна статистика цього чату:\n"
                f"Збігів: {wins} | Незбігів: {losses}\n"
                f"Історична частка збігів: {accuracy:.1f}%\n\n"
                "Важливо: перевірка використовує останні доступні котирування, "
                "які можуть бути затриманими. Відсоток індикаторів не є "
                "ймовірністю успіху або гарантією."
            )
        except Exception:
            log.exception("Timer/check error")
            await message.reply_text(
                "Не вдалося завершити перевірку через помилку отримання даних. "
                "Результат не зараховано."
            )
        finally:
            context.user_data["running"] = False
            await message.reply_text("Можеш вибрати іншу пару або запустити новий аналіз.",
                                     reply_markup=keyboard(context))

def main():
    if not TOKEN:
        raise RuntimeError("Додай TELEGRAM_BOT_TOKEN у змінні середовища Render.")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(on_button))
    app.run_polling()

if __name__ == "__main__":
    main()
