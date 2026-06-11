"""
====================================================
  🤖 FOREX TRADING GROUP BOT - by Telegram Bot API
====================================================
Fitur:
  - Welcome member baru
  - Jadwal sesi market forex (WIB)
  - Kalkulator lot & risk management
  - Kirim sinyal trading (admin only)
====================================================
"""

import logging
from datetime import datetime
import pytz
import requests
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Konfigurasi ───────────────────────────────────────────────────────────────
TOKEN = "8829387199:AAHksb4qzubqEVL8dUPZVG_3eXwcdlsn75c"
TWELVE_API_KEY = "464497cc298e4dd9b925d8577568976e"

# Telegram User ID admin yang boleh kirim sinyal.
# Kosongkan [] agar semua bisa kirim sinyal (tidak disarankan untuk grup publik).
# Contoh: ADMIN_IDS = [123456789, 987654321]
ADMIN_IDS = []

WIB = pytz.timezone("Asia/Jakarta")

# ═════════════════════════════════════════════════════════════════════════════
# 1. WELCOME MEMBER BARU
# ═════════════════════════════════════════════════════════════════════════════
async def welcome_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kirim pesan sambutan saat ada member baru bergabung."""
    for member in update.message.new_chat_members:
        name = member.first_name or "Trader"
        text = (
            f"👋 Selamat datang, *{name}*\\!\n\n"
            "Kamu telah bergabung di *Grup Trading Forex* kami 🎉\n\n"
            "📌 *Panduan singkat:*\n"
            "• /sinyal – Lihat atau kirim sinyal trading\n"
            "• /sesi – Jadwal sesi market forex \\(WIB\\)\n"
            "• /kalkulator – Kalkulator lot & risk management\n"
            "• /help – Menu bantuan\n\n"
            "Selamat trading & semoga profit\\! 💰📈"
        )
        await update.message.reply_text(text, parse_mode="MarkdownV2")


# ═════════════════════════════════════════════════════════════════════════════
# 2. JADWAL SESI TRADING
# ═════════════════════════════════════════════════════════════════════════════
SESI_FOREX = [
    {
        "flag": "🇦🇺", "nama": "Sydney",
        "jam": "05:00 – 14:00 WIB",
        "start": 5, "end": 14,
        "tip": "Volatilitas rendah, cocok untuk pair AUD/USD",
    },
    {
        "flag": "🇯🇵", "nama": "Tokyo",
        "jam": "06:00 – 15:00 WIB",
        "start": 6, "end": 15,
        "tip": "Aktif untuk JPY, AUD, NZD",
    },
    {
        "flag": "🇬🇧", "nama": "London",
        "jam": "14:00 – 23:00 WIB",
        "start": 14, "end": 23,
        "tip": "Sesi paling aktif & volatil di dunia",
    },
    {
        "flag": "🇺🇸", "nama": "New York",
        "jam": "19:00 – 04:00 WIB",
        "start": 19, "end": 28,   # 28 = 04:00 hari berikutnya
        "tip": "Overlap London–NY (19-23 WIB) = volume tertinggi",
    },
]


def _is_session_active(start: int, end: int, hour: int) -> bool:
    """Cek apakah sesi sedang aktif berdasarkan jam WIB."""
    if end > 24:
        return hour >= start or hour < (end - 24)
    return start <= hour < end


async def sesi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tampilkan jadwal sesi forex dan statusnya saat ini."""
    now = datetime.now(WIB)
    hour = now.hour

    lines = ["🕐 *Jadwal Sesi Forex \\(WIB\\)*\n"]
    for s in SESI_FOREX:
        aktif = _is_session_active(s["start"], s["end"], hour)
        status = "🟢 *BUKA*" if aktif else "🔴 Tutup"
        lines.append(
            f"{s['flag']} *{s['nama']}*  {status}\n"
            f"   ⏰ {s['jam']}\n"
            f"   💡 _{s['tip']}_\n"
        )

    lines.append(f"\n🗓 _{now.strftime('%H:%M WIB, %d %b %Y')}_")
    await update.message.reply_text("\n".join(lines))


# ═════════════════════════════════════════════════════════════════════════════
# 3. KALKULATOR LOT & RISK MANAGEMENT
# ═════════════════════════════════════════════════════════════════════════════
KALKULATOR_USAGE = (
    "📊 *Kalkulator Lot & Risk*\n\n"
    "Format perintah:\n"
    "`/kalkulator <balance> <risk%> <stoploss_pip>`\n\n"
    "Contoh:\n"
    "`/kalkulator 1000 2 50`\n"
    "_\\(Balance \\$1000, risk 2%, SL 50 pip\\)_\n\n"
    "📌 Pip value menggunakan \\$10/lot \\(pair mayor standar\\)"
)


async def kalkulator_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hitung ukuran lot berdasarkan balance, risk %, dan stop loss pip."""
    args = context.args
    if len(args) != 3:
        await update.message.reply_text(KALKULATOR_USAGE, parse_mode="MarkdownV2")
        return

    try:
        balance  = float(args[0])
        risk_pct = float(args[1])
        sl_pip   = float(args[2])

        if any(v <= 0 for v in [balance, risk_pct, sl_pip]):
            raise ValueError("Nilai harus lebih dari 0")

        risk_usd        = balance * (risk_pct / 100)
        pip_value_lot   = 10.0        # USD per pip, 1 standard lot (pair mayor)
        lot_standard    = risk_usd / (sl_pip * pip_value_lot)
        lot_mini        = lot_standard * 10
        lot_micro       = lot_standard * 100
        reward_1r       = risk_usd    # target R:R 1:1
        reward_2r       = risk_usd * 2

        # Escape karakter khusus MarkdownV2
        def e(v): return str(v).replace(".", "\\.").replace("-", "\\-").replace("+", "\\+").replace("$", "\\$")

        result = (
            f"📊 *Hasil Kalkulator Lot*\n"
            f"{'─' * 28}\n"
            f"💰 Balance      : \\${e(f'{balance:,.2f}')}\n"
            f"⚠️  Risk          : {e(risk_pct)}% = \\${e(f'{risk_usd:,.2f}')}\n"
            f"🎯 Stop Loss    : {e(int(sl_pip))} pip\n"
            f"{'─' * 28}\n"
            f"📦 *Ukuran Lot*\n"
            f"   Standard  : *{e(f'{lot_standard:.2f}')} lot*\n"
            f"   Mini        : {e(f'{lot_mini:.1f}')} lot\n"
            f"   Micro      : {e(f'{lot_micro:.0f}')} lot\n"
            f"{'─' * 28}\n"
            f"🎯 *Target Profit*\n"
            f"   R:R 1:1   → \\${e(f'{reward_1r:,.2f}')}\n"
            f"   R:R 1:2   → \\${e(f'{reward_2r:,.2f}')}\n\n"
            f"_\\*Berlaku untuk pair mayor \\(pip value \\$10/lot\\)_"
        )
        await update.message.reply_text(result)

    except (ValueError, ZeroDivisionError):
        await update.message.reply_text(
            "❌ Input tidak valid\\.\n\n" + KALKULATOR_USAGE,
            parse_mode="MarkdownV2",
        )


# ═════════════════════════════════════════════════════════════════════════════
# 4. KIRIM SINYAL TRADING (Admin Only)
# ═════════════════════════════════════════════════════════════════════════════
SINYAL_USAGE = (
    "📡 *Format Sinyal Trading*\n\n"
    "`/sinyal PAIR ACTION ENTRY TP SL`\n\n"
    "Contoh:\n"
    "`/sinyal EURUSD BUY 1\\.0850 1\\.0900 1\\.0800`\n\n"
    "Action yang valid: `BUY` atau `SELL`"
)


async def sinyal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kirim sinyal trading ke grup. Hanya untuk admin jika ADMIN_IDS diset."""
    user_id = update.effective_user.id

    # Cek hak akses admin
    if ADMIN_IDS and user_id not in ADMIN_IDS:
        await update.message.reply_text(
            "⛔ Hanya *admin* yang bisa mengirim sinyal\\.",
            parse_mode="MarkdownV2",
        )
        return

    args = context.args
    if len(args) != 5:
        await update.message.reply_text(SINYAL_USAGE, parse_mode="MarkdownV2")
        return

    pair, action, entry, tp, sl = args
    action = action.upper()

    if action not in ("BUY", "SELL"):
        await update.message.reply_text(
            "❌ Action harus `BUY` atau `SELL`\\.", parse_mode="MarkdownV2"
        )
        return

    emoji_action = "📈 LONG" if action == "BUY" else "📉 SHORT"
    now = datetime.now(WIB)

    # Escape untuk MarkdownV2
    def e(v): return str(v).replace(".", "\\.").replace("-", "\\-")

    sinyal = (
        f"📡 *SINYAL TRADING*\n"
        f"{'═' * 28}\n"
        f"💱 Pair        : *{e(pair.upper())}*\n"
        f"🔹 Action     : *{emoji_action}*\n"
        f"🎯 Entry       : `{e(entry)}`\n"
        f"✅ Take Profit : `{e(tp)}`\n"
        f"🛑 Stop Loss   : `{e(sl)}`\n"
        f"{'═' * 28}\n"
        f"⏰ {e(now.strftime('%H:%M WIB'))}, {e(now.strftime('%d %b %Y'))}\n\n"
        f"⚠️ _DYOR \\— sinyal bukan jaminan profit\\._\n"
        f"_Selalu gunakan risk management\\!_"
    )
    await update.message.reply_text(sinyal, parse_mode="MarkdownV2")


# ═════════════════════════════════════════════════════════════════════════════
# 5. HELP / START
# ═════════════════════════════════════════════════════════════════════════════
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tampilkan daftar perintah yang tersedia."""
    text = (
        "🤖 *Forex Trading Bot*\n\n"
        "📌 *Perintah tersedia:*\n\n"
        "• /sinyal `PAIR ACTION ENTRY TP SL`\n"
        "  _→ Kirim sinyal trading \\(admin\\)_\n\n"
        "• /sesi\n"
        "  _→ Jadwal sesi market forex \\(WIB\\)_\n\n"
        "• /kalkulator `balance risk% sl_pip`\n"
        "  _→ Hitung ukuran lot & target profit_\n\n"
        "• /help\n"
        "  _→ Tampilkan menu ini_\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 *Contoh kalkulator:*\n"
        "`/kalkulator 1000 2 50`\n\n"
        "💡 *Contoh sinyal:*\n"
        "`/sinyal EURUSD BUY 1\\.0850 1\\.0900 1\\.0800`"
    )
    await update.message.reply_text(text, parse_mode="MarkdownV2")


# ═════════════════════════════════════════════════════════════════════════════
# MAIN — Jalankan Bot
# ═════════════════════════════════════════════════════════════════════════════
def main():
    print("🚀 Bot Forex Trading sedang berjalan...")

    app = Application.builder().token(TOKEN).build()

    # Daftarkan semua handler
    app.add_handler(CommandHandler(["start", "help"], help_command))
    app.add_handler(CommandHandler("sesi",        sesi_command))
    app.add_handler(CommandHandler("kalkulator",  kalkulator_command))
    app.add_handler(CommandHandler("sinyal",      sinyal_command))
    app.add_handler(
        MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_member)
    )

    print("✅ Bot siap menerima pesan. Tekan Ctrl+C untuk berhenti.\n")
    app.run_polling(poll_interval=2)


if __name__ == "__main__":
    main()
