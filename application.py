import asyncio
import os
from datetime import datetime

from binance import BinanceAPIException
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, ApplicationBuilder
from binance.client import Client

# Your keys
BINANCE_API_KEY = os.environ["binance_api_key"]
BINANCE_API_SECRET = os.environ["binance_api_secret"]
TELEGRAM_BOT_TOKEN = os.environ["telegram_bot_token"]

binance_client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["/wallet"],
        ["/total"],["/open_order"],
       # ["/order_bought"],
       # ["/order_sold"],
        ["/show_last_trades"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    print(update.effective_user.id)
    await update.message.reply_text(
        "👋 Welcome! Choose a command below:",
        reply_markup=reply_markup
    )

# Telegram bot command
#async def order(update: Update, context: ContextTypes.DEFAULT_TYPE):
#    args = context.args
#    if not args:
#        await update.message.reply_text("Usage:\n/order bought\n/order sold")
#        return
#
#    subcommand = args[0].lower()
#    if subcommand == "bought":
#        await show_orders(update, side="BUY")
#    elif subcommand == "sold":
#        await show_orders(update, side="SELL")
#    else:
#        await update.message.reply_text("Invalid subcommand. Use:\n/order bought\n/order sold")

async def get_traded_symbols():
    # Use the full symbol list from Binance exchange
    exchange_info = binance_client.get_exchange_info()
    symbols = [s["symbol"] for s in exchange_info["symbols"] if s["quoteAsset"] == "USDT"]

    traded_symbols = []
    for symbol in symbols:
        try:
            trades = binance_client.get_my_trades(symbol=symbol)
            if trades:
                traded_symbols.append(symbol)
        except BinanceAPIException as e:
            if "Invalid symbol" in str(e):
                continue  # Skip
            raise e  # Raise other errors

    return traded_symbols

async def show_orders(update: Update, side: str, limit: int = None):
    try:
        account_info = binance_client.get_account()
        symbols = await get_traded_symbols()

        trades = []
        for symbol in symbols:
            try:
                symbol_trades = binance_client.get_my_trades(symbol=symbol)
                for trade in symbol_trades:
                    is_buy = trade["isBuyer"]
                    if (side == "BUY" and is_buy) or (side == "SELL" and not is_buy):
                        trades.append({
                            "symbol": symbol,
                            "price": trade["price"],
                            "qty": trade["qty"],
                            "time": trade["time"],
                        })
            except Exception:
                continue  # skip symbols that raise errors

        if not trades:
            await update.message.reply_text(f"No {side.lower()} orders found.")
            return

        # Sort and optionally limit
        trades = sorted(trades, key=lambda x: x["time"], reverse=True)
        if limit:
            trades = trades[:limit]

        msg_lines = [f"*All {side} orders:*"]
        for t in trades:
            date_str = datetime.utcfromtimestamp(t["time"] / 1000).strftime('%Y-%m-%d %H:%M:%S UTC')
            msg_lines.append(f"- {t['symbol']}: {t['qty']} @ {t['price']} on {date_str}")

        # If too many trades, paginate manually
        MAX_LENGTH = 4000  # Telegram max message size
        message = ""
        for line in msg_lines:
            if len(message) + len(line) + 1 > MAX_LENGTH:
                await update.message.reply_text(message, parse_mode="Markdown")
                message = ""
            message += line + "\n"

        if message:
            await update.message.reply_text(message, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

# /wallet command: show asset amount, average purchase price, and USD value
async def wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)

        account_info = client.get_account()
        balances = account_info['balances']
        non_zero = [b for b in balances if float(b['free']) + float(b['locked']) > 0]

        if not non_zero:
            await update.message.reply_text("Your wallet is empty.")
            return

        msg = "💰 Your Wallet:\n\n"

        for asset in non_zero:
            symbol = asset['asset']
            total_qty = float(asset['free']) + float(asset['locked'])

            if symbol in ["BUSD", "USDT"]:
                avg_price = 1.0
                value_usd = total_qty
            else:
                try:
                    trades = client.get_my_trades(symbol=symbol + "USDT")
                except Exception:
                    trades = []

                if not trades:
                    avg_price = 0
                else:
                    total_qty_traded = sum(float(t['qty']) for t in trades)
                    total_cost = sum(float(t['qty']) * float(t['price']) for t in trades)
                    avg_price = total_cost / total_qty_traded if total_qty_traded > 0 else 0

                try:
                    ticker = client.get_symbol_ticker(symbol=symbol + "USDT")
                    current_price = float(ticker['price']) if 'price' in ticker else 0
                except Exception:
                    current_price = 0

                value_usd = total_qty * current_price

            msg += (
                f"{symbol}:\n"
                f"  Amount: {total_qty:.6f}\n"
                f"  Avg. Purchase Price: ${avg_price:.4f}\n"
                f"  Current Value: ${value_usd:.2f}\n"
                f"  Current {symbol} Value: ${current_price:.4f}\n\n"
            )

        await update.message.reply_text(msg)

    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {e}")

# /total command: return total wallet value in USD
async def total(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)

        account_info = client.get_account()
        balances = account_info['balances']
        non_zero = [b for b in balances if float(b['free']) + float(b['locked']) > 0]

        if not non_zero:
            await update.message.reply_text("Your wallet is empty.")
            return

        total_value = 0.0

        for asset in non_zero:
            symbol = asset['asset']
            total_qty = float(asset['free']) + float(asset['locked'])

            if symbol in ["BUSD", "USDT"]:
                value_usd = total_qty
            else:
                try:
                    ticker = client.get_symbol_ticker(symbol=symbol + "USDT")
                    current_price = float(ticker['price']) if 'price' in ticker else 0
                except Exception:
                    current_price = 0
                value_usd = total_qty * current_price

            total_value += value_usd

        await update.message.reply_text(f"💵 Estimated total wallet value: ${total_value:.2f}")

    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {e}")

async def open_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)
        open_orders = client.get_open_orders()

        if not open_orders:
            await update.message.reply_text("You have no open orders.")
            return

        msg = "📋 Your Open Orders:\n\n"
        for order in open_orders:
            symbol = order.get('symbol')
            side = order.get('side')
            price = order.get('price')
            orig_qty = order.get('origQty')
            status = order.get('status')
            msg += (
                f"Symbol: {symbol}\n"
                f"Side: {side}\n"
                f"Price: {price}\n"
                f"Quantity: {orig_qty}\n"
                f"Status: {status}\n"
                "--------------------\n"
            )

        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {e}")

#async def order_bought(update: Update, context: ContextTypes.DEFAULT_TYPE):
#    await show_orders(update, side="BUY", limit=None)
#
#async def order_sold(update: Update, context: ContextTypes.DEFAULT_TYPE):
#    await show_orders(update, side="SELL", limit=None)


# Symbols of interest
SELECTED_SYMBOLS = [
    "ETHUSDT", "AVAXUSDT", "USDCUSDT", "ZROUSDT", "EURUSDT"
    # USDTUSDT doesn't make sense and can be omitted
]
async def show_last_trades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        all_trades = []

        for symbol in SELECTED_SYMBOLS:
            try:
                trades = binance_client.get_my_trades(symbol=symbol)
                for trade in trades:
                    all_trades.append({
                        "symbol": symbol,
                        "side": "BUY" if trade["isBuyer"] else "SELL",
                        "qty": trade["qty"],
                        "price": trade["price"],
                        "time": trade["time"],
                    })
            except BinanceAPIException as e:
                if "Invalid symbol" in str(e):
                    continue
                else:
                    raise e

        if not all_trades:
            await update.message.reply_text("You have no ETH, AVAX, USDC, ZRO, EUR trades.")
            return

        # Sort by time (latest first) and limit to 50
        latest_trades = sorted(all_trades, key=lambda t: t["time"], reverse=True)[:50]

        msg_lines = ["*Last 50 orders (ETH, AVAX, USDC, ZRO, EUR):*"]
        for t in latest_trades:
            date_str = datetime.utcfromtimestamp(t["time"] / 1000).strftime('%Y-%m-%d %H:%M:%S UTC')
            msg_lines.append(f"- {t['side']} {t['qty']} {t['symbol']} @ {t['price']} on {date_str}")

        await update.message.reply_text("\n".join(msg_lines), parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")


# Main entry point
def main() -> None:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("wallet", wallet))
    app.add_handler(CommandHandler("total", total))
    app.add_handler(CommandHandler("open_order", open_order))
    #app.add_handler(CommandHandler("order", order))
    #app.add_handler(CommandHandler("order_bought", order_bought))
    #app.add_handler(CommandHandler("order_sold", order_sold))
    app.add_handler(CommandHandler("show_last_trades", show_last_trades))

    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

