import asyncio
import logging
import os
import threading
import json
from datetime import datetime
from typing import Any, Coroutine

import uvicorn
from binance.spot import Spot
from binance.error import ClientError
from fastapi import FastAPI
from pydantic import TypeAdapter
from starlette.responses import JSONResponse
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes

from dto.totalDTO import totalDTO, totalDTOList

# Your keys
BINANCE_API_KEY = os.environ["binance_api_key"]
BINANCE_API_SECRET = os.environ["binance_api_secret"]
TELEGRAM_BOT_TOKEN = os.environ["telegram_bot_token"]

binance_client = Spot(api_key=BINANCE_API_KEY, api_secret=BINANCE_API_SECRET)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["/wallet"],
        ["/total"],
        ["/open_order"],
        ["/show_last_trades"],
        ["/trades"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    print(update.effective_user.id)
    await update.message.reply_text(
        "👋 Welcome! Choose a command below:",
        reply_markup=reply_markup
    )


async def show_all_trades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Show all trades for all symbols or a specific symbol
    Usage: /trades or /trades BTCUSDT or /trades BTC
    """
    try:
        # Get symbol from command arguments
        symbol_filter = None
        if context.args:
            symbol_input = context.args[0].upper()
            # Add USDT if not present
            if not any(symbol_input.endswith(suffix) for suffix in ['USDT', 'USDC', 'BTC', 'ETH', 'BNB']):
                symbol_filter = symbol_input + 'USDT'
            else:
                symbol_filter = symbol_input

        if symbol_filter:
            trades_data = get_trades_for_symbol(binance_client, symbol_filter)
            if trades_data['trades']:
                await send_trades_message(update, trades_data, symbol_filter)
            else:
                await update.message.reply_text(f"No trades found for {symbol_filter}")
        else:
            await show_all_symbols_trades(update, binance_client)

    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {e}")


def get_trades_for_symbol(client, symbol):
    """Get all trades for a specific symbol across different quote currencies"""
    try:
        all_trades = []

        # Try different quote currencies
        base_symbol = symbol.replace('USDT', '').replace('USDC', '').replace(
            'BNB', '')
        trading_pairs = [f"{base_symbol}USDT", f"{base_symbol}USDC", f"{base_symbol}BTC", f"{base_symbol}ETH"]

        for pair in trading_pairs:
            try:
                trades = client.my_trades(symbol=pair)
                if trades:
                    for trade in trades:
                        trade['pair'] = pair
                    all_trades.extend(trades)
            except Exception:
                continue

        # Sort by time (newest first)
        all_trades.sort(key=lambda x: x['time'], reverse=True)

        # Calculate summary statistics
        buy_trades = [t for t in all_trades if t['isBuyer']]
        sell_trades = [t for t in all_trades if not t['isBuyer']]

        total_bought = sum(float(t['qty']) for t in buy_trades)
        total_sold = sum(float(t['qty']) for t in sell_trades)

        buy_value = sum(float(t['qty']) * float(t['price']) for t in buy_trades)
        sell_value = sum(float(t['qty']) * float(t['price']) for t in sell_trades)

        avg_buy_price = buy_value / total_bought if total_bought > 0 else 0
        avg_sell_price = sell_value / total_sold if total_sold > 0 else 0

        return {
            'trades': all_trades,
            'total_trades': len(all_trades),
            'buy_trades': len(buy_trades),
            'sell_trades': len(sell_trades),
            'total_bought': total_bought,
            'total_sold': total_sold,
            'avg_buy_price': avg_buy_price,
            'avg_sell_price': avg_sell_price,
            'net_position': total_bought - total_sold
        }

    except Exception as e:
        return {'trades': [], 'error': str(e)}


async def send_trades_message(update, trades_data, symbol):
    """Send formatted trades message"""
    trades = trades_data['trades']

    if not trades:
        await update.message.reply_text(f"No trades found for {symbol}")
        return

    # Header with summary
    msg = f"📊 **{symbol} Trade History**\n\n"
    msg += f"📈 Total Trades: {trades_data['total_trades']}\n"
    msg += f"🛒 Buys: {trades_data['buy_trades']} | 💰 Sells: {trades_data['sell_trades']}\n"
    msg += f"📦 Total Bought: {trades_data['total_bought']:.6f}\n"
    msg += f"📤 Total Sold: {trades_data['total_sold']:.6f}\n"
    msg += f"📊 Net Position: {trades_data['net_position']:.6f}\n"

    if trades_data['avg_buy_price'] > 0:
        msg += f"🛒 Avg Buy Price: ${trades_data['avg_buy_price']:.4f}\n"
    if trades_data['avg_sell_price'] > 0:
        msg += f"💰 Avg Sell Price: ${trades_data['avg_sell_price']:.4f}\n"

    msg += "\n" + "=" * 30 + "\n\n"

    # Show recent trades (limit to avoid message length issues)
    recent_trades = trades[:20]  # Last 20 trades

    for i, trade in enumerate(recent_trades, 1):
        trade_time = datetime.fromtimestamp(trade['time'] / 1000)
        side = "🛒 BUY" if trade['isBuyer'] else "💰 SELL"

        # Calculate trade value
        trade_value = float(trade['qty']) * float(trade['price'])

        msg += (
            f"{i:2d}. {side}\n"
            f"    📅 {trade_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"    📦 Qty: {float(trade['qty']):.6f}\n"
            f"    💵 Price: ${float(trade['price']):.4f}\n"
            f"    💰 Value: ${trade_value:.2f}\n"
            f"    🔄 Pair: {trade['pair']}\n"
            f"    🏷️ ID: {trade['id']}\n\n"
        )

    if len(trades) > 20:
        msg += f"... and {len(trades) - 20} more trades\n"
        msg += "Use /tradesall {symbol} for complete history\n"

    # Split message if too long
    if len(msg) > 4000:
        # Send summary first
        summary_msg = f"📊 **{symbol} Trade Summary**\n\n"
        summary_msg += f"📈 Total Trades: {trades_data['total_trades']}\n"
        summary_msg += f"🛒 Buys: {trades_data['buy_trades']} | 💰 Sells: {trades_data['sell_trades']}\n"
        summary_msg += f"📦 Total Bought: {trades_data['total_bought']:.6f}\n"
        summary_msg += f"📤 Total Sold: {trades_data['total_sold']:.6f}\n"
        summary_msg += f"📊 Net Position: {trades_data['net_position']:.6f}\n"

        if trades_data['avg_buy_price'] > 0:
            summary_msg += f"🛒 Avg Buy Price: ${trades_data['avg_buy_price']:.4f}\n"
        if trades_data['avg_sell_price'] > 0:
            summary_msg += f"💰 Avg Sell Price: ${trades_data['avg_sell_price']:.4f}\n"

        await update.message.reply_text(summary_msg)

        # Send recent trades
        trades_msg = f"🕒 Recent Trades for {symbol}:\n\n"
        for i, trade in enumerate(recent_trades[:10], 1):
            trade_time = datetime.fromtimestamp(trade['time'] / 1000)
            side = "🛒 BUY" if trade['isBuyer'] else "💰 SELL"
            trade_value = float(trade['qty']) * float(trade['price'])

            trades_msg += (
                f"{i}. {side} | {trade_time.strftime('%m-%d %H:%M')} | "
                f"{float(trade['qty']):.4f} @ ${float(trade['price']):.4f}\n"
            )

        await update.message.reply_text(trades_msg)
    else:
        await update.message.reply_text(msg)


async def show_all_symbols_trades(update, client):
    """Show trades summary for all symbols with trades"""
    try:
        # Get account info to find symbols with balances
        account_info = binance_client.account()
        balances = account_info['balances']
        symbols_with_balance = [b['asset'] for b in balances if float(b['free']) + float(b['locked']) > 0]

        # Also check for symbols that might have been traded but no longer held
        exchange_info = binance_client.exchange_info()
        all_symbols = [s['symbol'] for s in exchange_info['symbols'] if s['symbol'].endswith('USDT')]

        trades_summary = {}
        symbols_to_check = set()

        # Add symbols with balance
        for asset in symbols_with_balance:
            if asset not in ['USDT', 'USDC']:
                symbols_to_check.add(f"{asset}USDT")

        # Limit to prevent too many API calls
        symbols_to_check = list(symbols_to_check)[:10]

        msg = "📊 **All Trading Activity Summary**\n\n"

        total_symbols_with_trades = 0

        for symbol in symbols_to_check:
            try:
                trades_data = get_trades_for_symbol(binance_client, symbol)
                if trades_data['trades']:
                    total_symbols_with_trades += 1

                    base_asset = symbol.replace('USDT', '')
                    msg += f"**{base_asset}:**\n"
                    msg += f"  📈 Trades: {trades_data['total_trades']} ({trades_data['buy_trades']}B/{trades_data['sell_trades']}S)\n"
                    msg += f"  📊 Net: {trades_data['net_position']:+.4f}\n"

                    if trades_data['avg_buy_price'] > 0:
                        msg += f"  🛒 Avg Buy: ${trades_data['avg_buy_price']:.4f}\n"
                    if trades_data['avg_sell_price'] > 0:
                        msg += f"  💰 Avg Sell: ${trades_data['avg_sell_price']:.4f}\n"

                    msg += "\n"

                    # Prevent message from getting too long
                    if len(msg) > 3500:
                        msg += f"... and more symbols\n"
                        break

            except Exception as e:
                continue

        if total_symbols_with_trades == 0:
            msg += "No trading activity found.\n"
        else:
            msg += f"\n📊 Total symbols with trades: {total_symbols_with_trades}\n"
            msg += "\n💡 Use `/trades SYMBOL` for detailed history"

        await update.message.reply_text(msg)

    except Exception as e:
        await update.message.reply_text(f"⚠️ Error getting trade summary: {e}")


async def trades_pnl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Show P&L analysis for a specific symbol
    Usage: /pnl BTCUSDT or /pnl BTC
    """
    try:
        if not context.args:
            await update.message.reply_text("Please specify a symbol. Example: `/pnl BTC` or `/pnl BTCUSDT`")
            return

        symbol_input = context.args[0].upper()
        if not any(symbol_input.endswith(suffix) for suffix in ['USDT', 'USDC', 'BTC', 'ETH', 'BNB']):
            symbol = symbol_input + 'USDT'
        else:
            symbol = symbol_input

        client = Spot(api_key=BINANCE_API_KEY, api_secret=BINANCE_API_SECRET)
        trades_data = get_trades_for_symbol(client, symbol)

        if not trades_data['trades']:
            await update.message.reply_text(f"No trades found for {symbol}")
            return

        # Calculate P&L
        buy_trades = [t for t in trades_data['trades'] if t['isBuyer']]
        sell_trades = [t for t in trades_data['trades'] if not t['isBuyer']]

        total_buy_cost = sum(float(t['qty']) * float(t['price']) for t in buy_trades)
        total_sell_revenue = sum(float(t['qty']) * float(t['price']) for t in sell_trades)

        realized_pnl = total_sell_revenue - (trades_data['total_sold'] * trades_data['avg_buy_price'])

        msg = f"📊 **{symbol} P&L Analysis**\n\n"
        msg += f"💰 Total Buy Cost: ${total_buy_cost:.2f}\n"
        msg += f"💵 Total Sell Revenue: ${total_sell_revenue:.2f}\n"
        msg += f"📈 Realized P&L: ${realized_pnl:+.2f}\n"

        if realized_pnl != 0:
            pnl_percentage = (realized_pnl / total_buy_cost) * 100 if total_buy_cost > 0 else 0
            pnl_emoji = "📈" if realized_pnl > 0 else "📉"
            msg += f"{pnl_emoji} P&L Percentage: {pnl_percentage:+.2f}%\n"

        # Current position value if any remaining
        if trades_data['net_position'] > 0:
            try:
                current_ticker = client.ticker_price(symbol=symbol)
                current_price = float(current_ticker['price'])
                current_value = trades_data['net_position'] * current_price
                remaining_cost_basis = trades_data['net_position'] * trades_data['avg_buy_price']
                unrealized_pnl = current_value - remaining_cost_basis

                msg += f"\n🏦 **Current Position:**\n"
                msg += f"📦 Quantity: {trades_data['net_position']:.6f}\n"
                msg += f"💰 Current Value: ${current_value:.2f}\n"
                msg += f"📊 Unrealized P&L: ${unrealized_pnl:+.2f}\n"

                total_pnl = realized_pnl + unrealized_pnl
                msg += f"\n🎯 **Total P&L: ${total_pnl:+.2f}**"

            except Exception:
                msg += f"\n📦 Remaining Position: {trades_data['net_position']:.6f}"

        await update.message.reply_text(msg)

    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {e}")

async def get_traded_symbols():
    exchange_info = binance_client.exchange_info()
    symbols = [s["symbol"] for s in exchange_info["symbols"] if s["quoteAsset"] == "USDT"]

    traded_symbols = []
    for symbol in symbols:
        try:
            trades = binance_client.my_trades(symbol=symbol)
            if trades:
                traded_symbols.append(symbol)
        except ClientError as e:
            if "Invalid symbol" in str(e.error_message):
                continue
            raise e
    return traded_symbols

async def show_orders(update: Update, side: str, limit: int = None):
    try:
        account_info = binance_client.account()
        symbols = await get_traded_symbols()

        trades = []
        for symbol in symbols:
            try:
                symbol_trades = binance_client.my_trades(symbol=symbol)
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
                continue

        if not trades:
            await update.message.reply_text(f"No {side.lower()} orders found.")
            return

        trades = sorted(trades, key=lambda x: x["time"], reverse=True)
        if limit:
            trades = trades[:limit]

        msg_lines = [f"*All {side} orders:*"]
        for t in trades:
            date_str = datetime.utcfromtimestamp(t["time"] / 1000).strftime('%Y-%m-%d %H:%M:%S UTC')
            msg_lines.append(f"- {t['symbol']}: {t['qty']} @ {t['price']} on {date_str}")

        MAX_LENGTH = 4000
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

async def wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        account_info = binance_client.account()
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
                current_price = 1.0
            else:
                try:
                    trades = binance_client.my_trades(symbol=symbol + "USDT")
                    trades += binance_client.my_trades(symbol=symbol + "USDC")
                except Exception:
                    trades = []

                if not trades:
                    avg_price = 0
                else:
                    # Only use BUY trades
                    buy_trades = [t for t in trades if t['isBuyer']]

                    if not buy_trades:
                        avg_price = 0
                    else:
                        total_qty_bought = sum(float(t['qty']) for t in buy_trades)
                        total_cost_bought = sum(float(t['qty']) * float(t['price']) for t in buy_trades)
                        avg_price = total_cost_bought / total_qty_bought if total_qty_bought > 0 else 0

                try:
                    ticker = binance_client.ticker_price(symbol=symbol + "USDT")
                    current_price = float(ticker['price'])
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

async def total(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        totals = await total_web_server()
        total_value = sum (t.value_usd for t in totals.items)
        # Build response with percentages
        response = f"💵 **Portfolio Summary**\n"
        response += f"Total Value: ${total_value:.2f}\n\n"
        for total in totals.items:
            if total_value > 0:
                percentage = (total.value_usd / total_value) * 100
                response += f"{total.symbol}: ${total.value_usd:.2f} ({percentage:.1f}%)\n"
            else:
                response += f"{total['symbol']}: ${total['value_usd']:.2f} (0.0%)\n"

        await update.message.reply_text(response)

    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {e}")

async def total_web_server() -> totalDTOList | None:
    try:
        account_info = binance_client.account()
        balances = account_info['balances']
        non_zero = [b for b in balances if float(b['free']) + float(b['locked']) > 0]

        if not non_zero:
            return None

        total_value = 0.0
        asset_values = []

        # Calculate value for each asset
        for asset in non_zero:
            symbol = asset['asset']
            total_qty = float(asset['free']) + float(asset['locked'])

            if symbol in ["BUSD", "USDT"]:
                value_usd = total_qty
            else:
                try:
                    ticker = binance_client.ticker_price(symbol=symbol + "USDT")
                    current_price = float(ticker['price'])
                except Exception:
                    current_price = 0
                value_usd = total_qty * current_price

            total_value += value_usd
            asset_values.append({
                'symbol': symbol,
                'quantity': total_qty,
                'value_usd': value_usd
            })
        # Sort assets by value (highest first)
        asset_values.sort(key=lambda x: x['value_usd'], reverse=True)

        totals = totalDTOList()
        for asset in asset_values:
            if total_value > 0:
                percentage = (asset['value_usd'] / total_value) * 100
                totals.append(totalDTO(symbol=asset['symbol'],value_usd= asset['value_usd'], percentage=percentage))
        return totals

    except Exception as e:
        #await update.message.reply_text(f"⚠️ Error: {e}")
        logging.ERROR("fdasf")

async def open_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        open_orders = binance_client.get_open_orders()

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

SELECTED_SYMBOLS = ["ETHUSDT", "AVAXUSDT", "USDCUSDT", "ZROUSDT", "EURUSDT"]

async def show_last_trades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        all_trades = []

        for symbol in SELECTED_SYMBOLS:
            try:
                trades = binance_client.my_trades(symbol=symbol)
                for trade in trades:
                    all_trades.append({
                        "symbol": symbol,
                        "side": "BUY" if trade["isBuyer"] else "SELL",
                        "qty": trade["qty"],
                        "price": trade["price"],
                        "time": trade["time"],
                    })
            except ClientError as e:
                if "Invalid symbol" in str(e.error_message):
                    continue
                else:
                    raise e

        if not all_trades:
            await update.message.reply_text("You have no ETH, AVAX, USDC, ZRO, EUR trades.")
            return

        latest_trades = sorted(all_trades, key=lambda t: t["time"], reverse=True)[:50]

        msg_lines = ["*Last 50 orders (ETH, AVAX, USDC, ZRO, EUR):*"]
        for t in latest_trades:
            date_str = datetime.utcfromtimestamp(t["time"] / 1000).strftime('%Y-%m-%d %H:%M:%S UTC')
            msg_lines.append(f"- {t['side']} {t['qty']} {t['symbol']} @ {t['price']} on {date_str}")

        await update.message.reply_text("\n".join(msg_lines), parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

# Your existing bot logic + new API endpoints
web_server = FastAPI()

@web_server.get("/portfolio/total")
async def get_portfolio_total():
    # Use your existing calculation logic
    portfolio_data = await total_web_server()  # Your existing function
    return portfolio_data

def main() -> None:
    # API in background thread
    api_thread = threading.Thread(target=lambda: uvicorn.run(web_server, port=8000))
    api_thread.start()
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("wallet", wallet))
    app.add_handler(CommandHandler("total", total))
    app.add_handler(CommandHandler("open_order", open_order))
    app.add_handler(CommandHandler("show_last_trades", show_last_trades))
    app.add_handler(CommandHandler("trades", show_all_trades))

    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
