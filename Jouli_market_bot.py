"""JOULI MARKET • DIGITAL MARKET — multilingual Telegram store bot.

Install: pip install pyTelegramBotAPI python-dotenv requests qrcode[pil]
Create .env with BOT_TOKEN and ADMIN_IDS, then run: python "Jouli_market_bot.py"
"""

from __future__ import annotations

import html
import hashlib
import io
import json
import logging
import math
import os
import re
import secrets
import sqlite3
import threading
import time
import base64
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_UP
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import parse_qs, quote, urlencode, urlparse

import qrcode
import requests
import telebot
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
from telebot import types
from telebot.apihelper import ApiTelegramException


load_dotenv()

SHOP_NAME = "Jouli Market"
BOT_DISPLAY_NAME = "Jouli Market"
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
bot_username_value = "@Sugarwymarket_bot"
BOT_USERNAME = (
    bot_username_value
    if bot_username_value.startswith("@")
    else f"@{bot_username_value}"
)
ADMIN_IDS = {
    int(value.strip())
    for value in os.getenv("ADMIN_IDS", "").split(",")
    if value.strip().isdigit()
}
admin_usernames_value = "@destroystoreadmin"
ADMIN_USERNAMES = {
    f"@{username}"
    for username in re.findall(r"@([A-Za-z0-9_]{5,32})", admin_usernames_value)
}
if not ADMIN_USERNAMES and re.fullmatch(
    r"[A-Za-z0-9_]{5,32}", admin_usernames_value.strip("\"'")
):
    ADMIN_USERNAMES = {f"@{admin_usernames_value.strip(chr(34) + chr(39))}"}
ADMIN_USERNAMES = {
    username
    for username in ADMIN_USERNAMES
    if username.casefold() != "@glavama"
}
owner_value = "@destroystoreadmin"
OWNER_USERNAME = owner_value if owner_value.startswith("@") else f"@{owner_value}"
support_value = "@destroystoretp"
SUPPORT_USERNAME = (
    support_value if support_value.startswith("@") else f"@{support_value}"
)
lead_monitor_value = os.getenv("LEAD_MONITOR_CHAT", "@FunPayPlace").strip()
lead_monitor_name = re.sub(
    r"^(?:https?://)?t\.me/", "", lead_monitor_value, flags=re.IGNORECASE
).split("/", 1)[0].lstrip("@").strip()
LEAD_MONITOR_CHAT = f"@{lead_monitor_name}"
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", "data/nexorashopp.db"))
PAYMENTS_LOG_PATH = Path(os.getenv("PAYMENTS_LOG_PATH", "payments.txt"))
TON_WALLET = os.getenv(
    "TON_WALLET_ADDRESS",
    "UQDEvKC6YHjTxgq8nsJyK33LRPcqHUEtgebTIM1oPGyPzKs2",
).strip()
TRC20_WALLET = os.getenv(
    "TRC20_WALLET_ADDRESS", "TTaXvZ3g9qnLnEGKd9NBP6CNrH5tk35eB6"
).strip()
ERC20_WALLET = os.getenv(
    "ERC20_WALLET_ADDRESS", "0x532689544E299bF588fd17C5805f1eA8bF5A4AF1"
).strip()
SOL_WALLET = os.getenv(
    "SOL_WALLET_ADDRESS", "EEBe7mg1e69BDxvuazFjHASK12Pjsu1EZNZFAMjbnTYT"
).strip()
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "").strip()
ORDER_AUTO_CLOSE_MINUTES = max(
    1, int(os.getenv("ORDER_AUTO_CLOSE_MINUTES", "60"))
)
PAYMENT_TTL_MINUTES = max(
    ORDER_AUTO_CLOSE_MINUTES, int(os.getenv("PAYMENT_TTL_MINUTES", "60"))
)
railway_public_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
webapp_value = os.getenv("WEBAPP_URL", "").strip()
if not webapp_value and railway_public_domain:
    webapp_value = (
        railway_public_domain
        if railway_public_domain.startswith(("http://", "https://"))
        else f"https://{railway_public_domain}"
    )
WEBAPP_URL = webapp_value.rstrip("/")
WEBAPP_PORT = max(1, min(65_535, int(os.getenv("PORT", "8080"))))
RUB_PER_USD = Decimal(os.getenv("RUB_PER_USD", "80"))
FX_API_URL = os.getenv(
    "FX_API_URL", "https://open.er-api.com/v6/latest/USD"
).strip()
FX_RATE_CACHE_SECONDS = max(
    300, int(os.getenv("FX_RATE_CACHE_SECONDS", "3600"))
)
TELEGRAM_STAR_RUB = Decimal(os.getenv("TELEGRAM_STAR_RUB", "1.3"))
TON_USD_FALLBACK = Decimal(os.getenv("TON_USD_FALLBACK", "3"))
SOL_USD_FALLBACK = Decimal(os.getenv("SOL_USD_FALLBACK", "150"))
GIVEAWAY_INTERVAL_HOURS = 48
GIVEAWAY_DISCOUNT_PERCENT = 15
REFERRAL_DISCOUNT_PERCENT = 5
WHOLESALE_DISCOUNT_PERCENT = 15
WHOLESALE_MIN_USD_CENTS = 3_000
MAX_TOTAL_DISCOUNT_PERCENT = 50
PROMO_CODES = {
    "NEXORAV2": 15,
    "NEXORA26": 25,
}
PRICE_MARKUP_PERCENT = Decimal(os.getenv("PRICE_MARKUP_PERCENT", "0"))
CATALOG_PRICE_INCREASE_PERCENT = Decimal("10")
PRICE_INCREASE_EXEMPT_CODES = {"stars", "pubg_uc", "steam"}
CATALOG_PRICE_DECREASE_PERCENT = Decimal("4")
MIN_TOPUP_RUB_KOPECKS = 50_000
MIN_ORDER_USD_CENTS = 1_000
MAX_TOPUP_CENTS = 1_000_000
NANO_TON = Decimal(1_000_000_000)
AUTO_VERIFY_ENABLED = os.getenv("AUTO_VERIFY_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
AUTO_VERIFY_INTERVAL_SECONDS = max(
    15, int(os.getenv("AUTO_VERIFY_INTERVAL_SECONDS", "30"))
)
AUTO_VERIFY_CONFIRMATIONS = max(1, int(os.getenv("AUTO_VERIFY_CONFIRMATIONS", "3")))
TONAPI_BASE_URL = os.getenv("TONAPI_BASE_URL", "https://tonapi.io").rstrip("/")
TONAPI_API_KEY = os.getenv("TONAPI_API_KEY", "").strip()
TRONGRID_BASE_URL = os.getenv("TRONGRID_BASE_URL", "https://api.trongrid.io").rstrip(
    "/"
)
TRONGRID_API_KEY = os.getenv("TRONGRID_API_KEY", "").strip()
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "").strip()
ETHERSCAN_API_URL = os.getenv(
    "ETHERSCAN_API_URL", "https://api.etherscan.io/v2/api"
).strip()
SOL_RPC_URL = os.getenv(
    "SOL_RPC_URL", "https://api.mainnet-beta.solana.com"
).strip()
TRON_USDT_CONTRACT = os.getenv(
    "TRON_USDT_CONTRACT", "TXLAQ63Xg1NAzckPwKHvzw7CSEmLMEqcdj"
).strip()
ETH_USDT_CONTRACT = os.getenv(
    "ETH_USDT_CONTRACT", "0xdAC17F958D2ee523a2206206994597C13D831ec7"
).strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing from environment variables")
if not 1 <= len(BOT_DISPLAY_NAME) <= 64:
    raise RuntimeError("BOT_DISPLAY_NAME must contain 1 to 64 characters")
if not ADMIN_IDS:
    raise RuntimeError("ADMIN_IDS is missing from environment variables")
if not re.fullmatch(r"@[A-Za-z0-9_]{5,32}", BOT_USERNAME):
    raise RuntimeError("Invalid BOT_USERNAME")
if not re.fullmatch(r"@[A-Za-z0-9_]{5,32}", LEAD_MONITOR_CHAT):
    raise RuntimeError("Invalid LEAD_MONITOR_CHAT")
if WEBAPP_URL and not WEBAPP_URL.startswith("https://"):
    raise RuntimeError("WEBAPP_URL must use HTTPS")
if not Decimal("0") <= PRICE_MARKUP_PERCENT <= Decimal("100"):
    raise RuntimeError("PRICE_MARKUP_PERCENT must be between 0 and 100")
if not re.fullmatch(r"@[A-Za-z0-9_]{5,32}", SUPPORT_USERNAME):
    raise RuntimeError("Invalid SUPPORT_USERNAME")
if not re.fullmatch(r"@[A-Za-z0-9_]{5,32}", OWNER_USERNAME):
    raise RuntimeError("Invalid OWNER_USERNAME")
if not re.fullmatch(r"[A-Za-z0-9_-]{48}", TON_WALLET):
    raise RuntimeError("Invalid TON_WALLET_ADDRESS")
if not re.fullmatch(r"T[1-9A-HJ-NP-Za-km-z]{33}", TRC20_WALLET):
    raise RuntimeError("Invalid TRC20_WALLET_ADDRESS")
if not re.fullmatch(r"0x[a-fA-F0-9]{40}", ERC20_WALLET):
    raise RuntimeError("Invalid ERC20_WALLET_ADDRESS")
if not re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}", SOL_WALLET):
    raise RuntimeError("Invalid SOL_WALLET_ADDRESS")
if not re.fullmatch(r"T[1-9A-HJ-NP-Za-km-z]{33}", TRON_USDT_CONTRACT):
    raise RuntimeError("Invalid TRON_USDT_CONTRACT")
if not re.fullmatch(r"0x[a-fA-F0-9]{40}", ETH_USDT_CONTRACT):
    raise RuntimeError("Invalid ETH_USDT_CONTRACT")
if not all(
    value.startswith("https://")
    for value in (TONAPI_BASE_URL, TRONGRID_BASE_URL, ETHERSCAN_API_URL, SOL_RPC_URL)
):
    raise RuntimeError("Blockchain API URLs must use HTTPS")
if (
    RUB_PER_USD <= 0
    or TELEGRAM_STAR_RUB <= 0
    or TON_USD_FALLBACK <= 0
    or SOL_USD_FALLBACK <= 0
):
    raise RuntimeError("Currency rates must be positive")
if not FX_API_URL.startswith("https://"):
    raise RuntimeError("FX_API_URL must use HTTPS")


Path("logs").mkdir(exist_ok=True)
log_handler = RotatingFileHandler(
    "logs/nexorashopp.log", maxBytes=3_000_000, backupCount=5, encoding="utf-8"
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[log_handler, logging.StreamHandler()],
)
LOGGER = logging.getLogger("nexorashopp")
PAYMENT_LOG_LOCK = threading.Lock()
FX_RATE_LOCK = threading.Lock()
FX_RATE_CACHE: tuple[float, dict[str, Decimal]] | None = None

CURRENCY_OPTIONS = (
    ("usd", "🇺🇸 USD · $"),
    ("rub", "🇷🇺 RUB · ₽"),
)
CURRENCIES = {code for code, _label in CURRENCY_OPTIONS}


def currency_rates(force: bool = False) -> dict[str, Decimal]:
    """Return current USD conversion rates with safe environment fallbacks."""
    global FX_RATE_CACHE
    now = time.monotonic()
    with FX_RATE_LOCK:
        if (
            not force
            and FX_RATE_CACHE
            and now - FX_RATE_CACHE[0] < FX_RATE_CACHE_SECONDS
        ):
            return dict(FX_RATE_CACHE[1])

    fallback = {
        "usd": Decimal("1"),
        "rub": RUB_PER_USD,
    }
    rates = fallback
    try:
        response = requests.get(FX_API_URL, timeout=8)
        response.raise_for_status()
        payload = response.json()
        raw_rates = payload.get("rates") or {}
        fresh = {
            "usd": Decimal("1"),
            "rub": Decimal(str(raw_rates["RUB"])),
        }
        if all(value.is_finite() and value > 0 for value in fresh.values()):
            rates = fresh
        else:
            raise ValueError("Non-positive exchange rate")
    except (requests.RequestException, KeyError, TypeError, ValueError, InvalidOperation):
        LOGGER.warning("FX API unavailable; using configured fallback rates")

    with FX_RATE_LOCK:
        FX_RATE_CACHE = (time.monotonic(), rates)
    return dict(rates)


def minimum_topup_cents() -> int:
    """Return the USD-cent equivalent of the 500 RUB minimum top-up."""
    rub_rate = currency_rates()["rub"]
    return int(
        (Decimal(MIN_TOPUP_RUB_KOPECKS) / rub_rate).quantize(
            Decimal("1"), rounding=ROUND_UP
        )
    )


def normalize_promo_code(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())

LANGUAGE_OPTIONS = (
    ("ru", "🇷🇺 Русский"),
    ("uk", "🇺🇦 Українська"),
    ("en", "🇬🇧 English"),
)
LANGUAGES = {code for code, _label in LANGUAGE_OPTIONS}
REMOVED_LANGUAGE_CODES = ("fa", "es", "pt", "de", "fr", "tr", "ar", "hi", "id", "zh", "ja")

TEXTS: dict[str, dict[str, str]] = {
    "ru": {
        "language_title": "<b>Выберите язык интерфейса</b> 🌍",
        "language_saved": "✅ Язык изменён на русский.",
        "subscribe_title": (
            "<b>🟢 Доступ к JOULI MARKET</b>\n"
            "<blockquote>Для использования бота подпишитесь на наш официальный канал</blockquote>\n"
            "📣 Канал: <b>{channel}</b>\n\n"
            "После подписки нажмите «Проверить подписку»."
        ),
        "subscribe_open": "🟢 Подписаться на канал",
        "subscribe_check": "✅ Проверить подписку",
        "subscribe_ok": "❤️ Подписка подтверждена. Добро пожаловать в JOULI MARKET!",
        "subscribe_missing": (
            "❌ Подписка пока не найдена. Подпишитесь на канал и повторите проверку."
        ),
        "subscribe_error": (
            "⚠️ Не удалось проверить подписку. Убедитесь, что бот назначен "
            "администратором канала."
        ),
        "home_tagline": "Цифровые товары — быстро, удобно и безопасно",
        "min_order_caption": "🧾 Минимальный заказ — <b>$10</b>",
        "catalog": "🛍 Каталог",
        "orders": "📦 Мои заказы",
        "profile": "👤 Профиль",
        "topup": "💳 Пополнить баланс",
        "giveaway": "🎁 Розыгрыш 15%",
        "support": "💬 Поддержка",
        "suggestion": "💡 Предложить идею",
        "about": "🟢 О боте",
        "help": "🛡 Безопасность",
        "language": "🌍 Сменить язык",
        "admin": "⚙️ Админ-панель",
        "back": "‹ Назад",
        "home": "⌂ Главное меню",
        "catalog_title": (
            "<b>Каталог товаров</b> 🛍\n"
            "<blockquote>Минимальная сумма заказа — $10</blockquote>\n"
            "Выберите раздел:"
        ),
        "cat_stars": "⭐ Telegram Stars",
        "cat_brawl": "🎫 Brawl Pass",
        "cat_steam": "🎮 Steam",
        "cat_pubg": "🔫 PUBG UC",
        "cat_roblox": "🎮 Roblox",
        "cat_ai": "🤖 AI-подписки",
        "cat_accounts": "🔐 Цифровые аккаунты",
        "cat_premium": "💎 Telegram Premium",
        "cat_gmail": "📧 Аккаунты Gmail",
        "cat_gta": "🚘 GTA V · Steam",
        "cat_rust": "🛢 Rust · Steam",
        "roblox_choose": (
            "<b>🟢 ROBLOX CENTER</b>\n"
            "<blockquote>Выберите удобный способ получения Robux</blockquote>"
        ),
        "roblox_account": "🟢 Робуксы аккаунтом",
        "roblox_gamepass": "🎮 Robux через Game Pass",
        "roblox_gifts": "🎁 Roblox Gift Cards",
        "category_title": "<b>{title}</b>\n\nВыберите товар:",
        "orders_title": "<b>Мои заказы</b> 📦",
        "no_orders": "У вас пока нет заказов.",
        "profile_text": (
            "<b>Мой профиль</b> 👤\n\nID: <code>{user_id}</code>\n"
            "Баланс: <b>{balance}</b>\nСкидка: <b>{discount}%</b>\n"
            "Рефералы: <b>{referrals}</b>\n\nВаша ссылка:\n{referral_url}"
        ),
        "add_funds": "<b>Пополнение баланса</b> 💳\nМинимальная сумма: <b>$10</b>",
        "custom_amount": "✏️ Другая сумма",
        "custom_amount_prompt": "Введите сумму от $10 до $10 000:",
        "profile_bonus": "\n🎁 Выигранная скидка: <b>15%</b> на следующий заказ × {uses}",
        "giveaway_card": (
            "<b>Розыгрыш скидки 15%</b> 🎁\n\nКаждые 48 часов бот случайно "
            "выбирает одного пользователя. Победитель получает скидку 15% на следующий заказ.\n\n"
            "До следующего розыгрыша: <b>{countdown}</b>{bonus}"
        ),
        "giveaway_bonus": "\n\n✅ У вас уже есть выигранная скидка × {uses}.",
        "giveaway_winner": (
            "🎉 <b>Вы победили в розыгрыше!</b>\n\nВаша скидка 15% автоматически "
            "применится к следующему заказу."
        ),
        "support_card": (
            "<b>Поддержка JOULI MARKET</b> 💬\n\nПо вопросам заказов и оплаты напишите: "
            "<b>@destroystoretp</b>"
        ),
        "open_support": "✉️ Написать @destroystoretp",
        "support_prompt": "Опишите проблему одним сообщением:",
        "suggestion_prompt": (
            "<b>Предложить улучшение</b> 💡\n\nНапишите, какой товар или функцию "
            "стоит добавить в бота. От 5 до 2000 символов:"
        ),
        "suggestion_sent": "✅ Спасибо! Предложение отправлено администратору.",
        "suggestion_invalid": "Предложение должно содержать от 5 до 2000 символов.",
        "about_text": (
            "<b>🌿 Jouli Market</b>\n"
            "<blockquote>Зелёный магазин популярных цифровых товаров</blockquote>\n"
            "⭐ Telegram Stars · 🔫 PUBG UC · 🎫 Brawl Pass\n"
            "🎮 Robux · 🤖 AI-подписки\n"
            "💳 Оплата: TON, USDT, SOL или баланс.\n"
            "🌍 <b>3 языка</b> — русский, украинский и английский.\n"
            "📦 История заказов и уведомления о статусе."
        ),
        "security": (
            "<b>Безопасность</b> 🛡\n\nНикому не сообщайте пароли, seed-фразы "
            "и коды входа. Всегда проверяйте выбранную сеть и сумму перевода."
        ),
        "product_not_found": "Товар не найден",
        "quantity_prompt": "Введите целое количество от {minimum} до {maximum}:",
        "stars_prompt": "Введите количество Stars от {minimum} до {maximum}:",
        "robux_prompt": "Введите количество Robux от {minimum} до {maximum}:",
        "steam_amount_prompt": (
            "Введите сумму пополнения Steam в долларах от ${minimum} до ${maximum} "
            "(целое число):"
        ),
        "uc_prompt": "Введите количество PUBG UC от {minimum} до {maximum}:",
        "recipient_telegram": "Отправьте @username получателя в Telegram:",
        "recipient_player": "Отправьте Player ID или игровой тег получателя:",
        "recipient_roblox": "Отправьте Roblox username или ID получателя:",
        "recipient_steam": (
            "Отправьте логин Steam или ссылку на профиль. Никогда не отправляйте пароль:"
        ),
        "recipient_pubg": "Отправьте PUBG Player ID и регион получателя:",
        "recipient_email": "Отправьте email для получения товара:",
        "product_card": (
            "{emoji} <b>{title}</b>\n<blockquote>{description}</blockquote>\n\n"
            "💵 Цена: <b>{price}</b>\n📦 Минимум: <b>{minimum}</b>\n"
            "🧾 Минимальный заказ: <b>$10</b>"
        ),
        "buy_now": "✨ Оформить покупку",
        "desc_stars": "Stars напрямую на Telegram-аккаунт получателя.",
        "desc_brawl": "Brawl Pass для игрового аккаунта по Player ID.",
        "desc_steam": "Пополнение Steam Wallet в USD. Итоговая сервисная комиссия — 2%.",
        "desc_pubg": "PUBG Mobile UC по курсу 1 UC = 1 RUB.",
        "desc_roblox": "Robux и gift-карты Roblox с ручной проверкой заказа.",
        "desc_ai": "Цифровая AI-подписка с доставкой на указанный email.",
        "desc_accounts": (
            "Цифровой аккаунт с доставкой данных на email. После получения "
            "рекомендуется сразу сменить пароль и включить двухэтапную защиту."
        ),
        "desc_premium": "Telegram Premium на 1 месяц для указанного аккаунта.",
        "desc_gmail": (
            "Аккаунты Gmail с доставкой данных на email. После получения смените "
            "пароль и включите двухэтапную защиту."
        ),
        "desc_gta": "Steam-аккаунт с GTA V с доставкой данных на указанный email.",
        "desc_rust": "Steam-аккаунт с Rust с доставкой данных на указанный email.",
        "recipient_invalid": "Введите корректные данные получателя.",
        "minimum_order": "Минимальная сумма заказа — $10.",
        "order_created": "<b>Заказ #{order_id} создан</b> ✨\nВыберите способ оплаты:",
        "choose_crypto": "<b>Выберите способ оплаты</b> 💳",
        "pay_balance": "💰 Оплатить с баланса",
        "pay_card_ru": "🇷🇺 Карта РФ",
        "pay_card_ua": "🇺🇦 Карта Украины",
        "pay_card_gb": "🇬🇧 Карта Великобритании",
        "pay_cryptobot": "🤖 Чек CryptoBot",
        "pay_ton": "💎 TON",
        "pay_trc20": "🟢 USDT · TRC20",
        "pay_erc20": "🟢 USDT · ERC20",
        "pay_sol": "🟢 SOL · Solana",
        "order_unavailable": "Заказ недоступен",
        "topup_unavailable": "Пополнение недоступно",
        "insufficient": "Недостаточно средств. Требуется: {amount}",
        "balance_paid": "✅ Заказ #{order_id} оплачен с баланса.",
        "rate_error": "Не удалось получить курс валют. Попробуйте через минуту.",
        "payment_caption": (
            "<b>{title} #{item_id}</b> 💳\n\nК зачислению/стоимость: <b>{fiat}</b>\n"
            "К оплате: <b>{crypto}</b>\nСеть: <b>{network}</b>\n"
            "Кошелёк: <code>{wallet}</code>\nНомер платежа: <code>{reference}</code>\n\n"
            "⚠️ Отправляйте только в указанной сети. После перевода нажмите кнопку ниже и отправьте хеш транзакции."
        ),
        "order_payment_title": "Оплата заказа",
        "topup_payment_title": "Пополнение баланса",
        "cryptobot_prompt": (
            "<b>Оплата чеком CryptoBot</b> 🤖\n\nЗаявка: <b>#{item_id}</b>\n"
            "Сумма: <b>{amount}</b>\n\nСоздайте активный чек на указанную сумму "
            "в @CryptoBot и отправьте сюда ссылку вида "
            "<code>https://t.me/CryptoBot?start=CQ...</code>.\n\n"
            "⚠️ Заявка будет выполнена только после ручной проверки чека."
        ),
        "open_cryptobot": "🤖 Открыть CryptoBot",
        "cryptobot_invalid": "Отправьте корректную активную ссылку на чек CryptoBot.",
        "cryptobot_submitted": "✅ Чек CryptoBot отправлен на проверку.",
        "card_payment_info": (
            "<b>Оплата картой · {country}</b> 💳\n\n{item}: <b>#{item_id}</b>\n"
            "Сумма: <b>{amount}</b>\n\nДля получения реквизитов напишите "
            "в поддержку <b>@destroystoretp</b> и укажите номер заявки. "
            "Не отправляйте в боте номер карты, CVV и коды из SMS."
        ),
        "open_payment": "↗ Открыть кошелёк / сеть",
        "paid_submit": "✅ Я оплатил — отправить хеш",
        "hash_prompt": "Отправьте хеш транзакции в сети {network}:",
        "hash_invalid": "Некорректный хеш транзакции.",
        "payment_submitted": "✅ Платёж отправлен на проверку.",
        "topup_submitted": "✅ Пополнение отправлено на проверку.",
        "already_used": "Этот хеш или заявка уже использованы.",
        "support_sent": "✅ Сообщение отправлено в поддержку.",
        "support_invalid": "Сообщение должно содержать от 2 до 2000 символов.",
        "unknown": "Неизвестное действие",
        "generic_error": "Произошла ошибка. Попробуйте ещё раз.",
        "access_denied": "⛔ Доступ запрещён.",
        "referral_joined": "🎉 Новый пользователь зарегистрировался по вашей ссылке!",
        "status_awaiting_payment": "🕒 Ожидает оплаты",
        "status_payment_review": "🔎 Платёж проверяется",
        "status_paid": "✅ Оплачен",
        "status_processing": "⚙️ Выполняется",
        "status_completed": "🏁 Выполнен",
        "status_cancelled": "❌ Отменён",
        "status_update": "<b>Заказ #{order_id}</b>\n{status}",
        "topup_credited": "✅ Баланс пополнен на {amount}",
        "topup_rejected": "❌ Пополнение отклонено.",
        "auto_topup_confirmed": (
            "✅ Транзакция подтверждена автоматически. Баланс пополнен на {amount}."
        ),
        "auto_order_confirmed": (
            "✅ Транзакция подтверждена автоматически. Заказ #{order_id} оплачен."
        ),
    },
    "en": {
        "language_title": "<b>Choose your language</b> 🌍",
        "language_saved": "✅ Language changed to English.",
        "subscribe_title": (
            "<b>🟢 Access JOULI MARKET</b>\n"
            "<blockquote>Join our official channel to use the bot</blockquote>\n"
            "📣 Channel: <b>{channel}</b>\n\n"
            "After joining, tap “Check subscription”."
        ),
        "subscribe_open": "🟢 Join the channel",
        "subscribe_check": "✅ Check subscription",
        "subscribe_ok": "❤️ Subscription confirmed. Welcome to JOULI MARKET!",
        "subscribe_missing": (
            "❌ Subscription not found yet. Join the channel and check again."
        ),
        "subscribe_error": (
            "⚠️ Subscription check failed. Make sure the bot is an administrator "
            "of the channel."
        ),
        "home_tagline": "Digital goods — fast, simple and secure",
        "min_order_caption": "🧾 Minimum order — <b>$10</b>",
        "catalog": "🛍 Catalog",
        "orders": "📦 My orders",
        "profile": "👤 Profile",
        "topup": "💳 Add funds",
        "giveaway": "🎁 15% giveaway",
        "support": "💬 Support",
        "suggestion": "💡 Suggest an idea",
        "about": "🟢 About",
        "help": "🛡 Security",
        "language": "🌍 Change language",
        "admin": "⚙️ Admin panel",
        "back": "‹ Back",
        "home": "⌂ Main menu",
        "catalog_title": (
            "<b>Product catalog</b> 🛍\n"
            "<blockquote>Minimum order amount — $10</blockquote>\n"
            "Choose a section:"
        ),
        "cat_stars": "⭐ Telegram Stars",
        "cat_brawl": "🎫 Brawl Pass",
        "cat_steam": "🎮 Steam",
        "cat_pubg": "🔫 PUBG UC",
        "cat_roblox": "🎮 Roblox",
        "cat_ai": "🤖 AI subscriptions",
        "cat_accounts": "🔐 Digital accounts",
        "cat_premium": "💎 Telegram Premium",
        "cat_gmail": "📧 Gmail accounts",
        "cat_gta": "🚘 GTA V · Steam",
        "cat_rust": "🛢 Rust · Steam",
        "roblox_choose": (
            "<b>🟢 ROBLOX CENTER</b>\n"
            "<blockquote>Choose how you would like to receive Robux</blockquote>"
        ),
        "roblox_account": "🟢 Robux via account",
        "roblox_gamepass": "🎮 Robux via Game Pass",
        "roblox_gifts": "🎁 Roblox Gift Cards",
        "category_title": "<b>{title}</b>\n\nChoose a product:",
        "orders_title": "<b>My orders</b> 📦",
        "no_orders": "You have no orders yet.",
        "profile_text": (
            "<b>My profile</b> 👤\n\nID: <code>{user_id}</code>\n"
            "Balance: <b>{balance}</b>\nDiscount: <b>{discount}%</b>\n"
            "Referrals: <b>{referrals}</b>\n\nYour link:\n{referral_url}"
        ),
        "add_funds": "<b>Add funds</b> 💳\nMinimum top-up: <b>$10</b>",
        "custom_amount": "✏️ Custom amount",
        "custom_amount_prompt": "Enter an amount from $10 to $10,000:",
        "profile_bonus": "\n🎁 Giveaway discount: <b>15%</b> on the next order × {uses}",
        "giveaway_card": (
            "<b>15% discount giveaway</b> 🎁\n\nEvery 48 hours the bot randomly "
            "selects one user. The winner receives 15% off their next order.\n\n"
            "Next draw in: <b>{countdown}</b>{bonus}"
        ),
        "giveaway_bonus": "\n\n✅ You already have a winning discount × {uses}.",
        "giveaway_winner": (
            "🎉 <b>You won the giveaway!</b>\n\nYour 15% discount will be applied "
            "automatically to your next order."
        ),
        "support_card": (
            "<b>JOULI MARKET Support</b> 💬\n\nFor order and payment questions, contact "
            "<b>@destroystoretp</b>."
        ),
        "open_support": "✉️ Message @destroystoretp",
        "support_prompt": "Describe your issue in one message:",
        "suggestion_prompt": (
            "<b>Suggest an improvement</b> 💡\n\nTell us which product or feature "
            "should be added. Use 5–2,000 characters:"
        ),
        "suggestion_sent": "✅ Thank you! Your suggestion was sent to the admin.",
        "suggestion_invalid": "Suggestion must contain 5–2,000 characters.",
        "about_text": (
            "<b>🌿 Jouli Market</b>\n"
            "<blockquote>A green store for popular digital goods</blockquote>\n"
            "⭐ Telegram Stars · 🔫 PUBG UC · 🎫 Brawl Pass\n"
            "🎮 Robux · 🤖 AI subscriptions\n"
            "💳 Pay with TON, USDT, SOL, or balance.\n"
            "🌍 <b>3 languages</b> — English, Ukrainian, and Russian.\n"
            "📦 Order history and status notifications."
        ),
        "security": (
            "<b>Security</b> 🛡\n\nNever share passwords, seed phrases, or login codes. "
            "Always verify the selected network and transfer amount."
        ),
        "product_not_found": "Product not found",
        "quantity_prompt": "Enter a whole quantity from {minimum} to {maximum}:",
        "stars_prompt": "Enter the number of Stars from {minimum} to {maximum}:",
        "robux_prompt": "Enter a Robux amount from {minimum} to {maximum}:",
        "steam_amount_prompt": (
            "Enter the Steam top-up amount in USD from ${minimum} to ${maximum} "
            "(whole dollars):"
        ),
        "uc_prompt": "Enter a PUBG UC amount from {minimum} to {maximum}:",
        "recipient_telegram": "Send the recipient's Telegram @username:",
        "recipient_player": "Send the recipient's Player ID or game tag:",
        "recipient_roblox": "Send the recipient's Roblox username or ID:",
        "recipient_steam": (
            "Send the Steam login or profile link. Never send a password:"
        ),
        "recipient_pubg": "Send the recipient's PUBG Player ID and region:",
        "recipient_email": "Send the delivery email address:",
        "product_card": (
            "{emoji} <b>{title}</b>\n<blockquote>{description}</blockquote>\n\n"
            "💵 Price: <b>{price}</b>\n📦 Minimum: <b>{minimum}</b>\n"
            "🧾 Minimum order: <b>$10</b>"
        ),
        "buy_now": "✨ Buy now",
        "desc_stars": "Stars delivered directly to the recipient's Telegram account.",
        "desc_brawl": "Brawl Pass delivered using the player's ID.",
        "desc_steam": "Steam Wallet top-up in USD with a 2% service charge.",
        "desc_pubg": "PUBG Mobile UC at the rate of 1 UC = 1 RUB.",
        "desc_roblox": "Robux and Roblox gift cards with manual order verification.",
        "desc_ai": "Digital AI subscription delivered to the specified email.",
        "desc_accounts": (
            "Digital account credentials delivered by email. Change the password "
            "and enable two-factor authentication after delivery."
        ),
        "desc_premium": "One month of Telegram Premium for the specified account.",
        "desc_gmail": (
            "Gmail account credentials delivered by email. Change the password and "
            "enable two-factor authentication after delivery."
        ),
        "desc_gta": "GTA V Steam account credentials delivered to the specified email.",
        "desc_rust": "Rust Steam account credentials delivered to the specified email.",
        "recipient_invalid": "Enter valid recipient details.",
        "minimum_order": "The minimum order amount is $10.",
        "order_created": "<b>Order #{order_id} created</b> ✨\nChoose a payment method:",
        "choose_crypto": "<b>Choose a payment method</b> 💳",
        "pay_balance": "💰 Pay from balance",
        "pay_card_ru": "🇷🇺 Russian card",
        "pay_card_ua": "🇺🇦 Ukrainian card",
        "pay_card_gb": "🇬🇧 UK card",
        "pay_cryptobot": "🤖 CryptoBot check",
        "pay_ton": "💎 TON",
        "pay_trc20": "🟢 USDT · TRC20",
        "pay_erc20": "🟢 USDT · ERC20",
        "pay_sol": "🟢 SOL · Solana",
        "order_unavailable": "Order unavailable",
        "topup_unavailable": "Top-up unavailable",
        "insufficient": "Insufficient balance. Required: {amount}",
        "balance_paid": "✅ Order #{order_id} paid from balance.",
        "rate_error": "The exchange rate is temporarily unavailable. Try again in a minute.",
        "payment_caption": (
            "<b>{title} #{item_id}</b> 💳\n\nCredit/order value: <b>{fiat}</b>\n"
            "Amount due: <b>{crypto}</b>\nNetwork: <b>{network}</b>\n"
            "Wallet: <code>{wallet}</code>\nPayment reference: <code>{reference}</code>\n\n"
            "⚠️ Send only on the selected network. After the transfer, press the button below and submit the transaction hash."
        ),
        "order_payment_title": "Order payment",
        "topup_payment_title": "Balance top-up",
        "cryptobot_prompt": (
            "<b>Pay with a CryptoBot check</b> 🤖\n\nRequest: <b>#{item_id}</b>\n"
            "Amount: <b>{amount}</b>\n\nCreate an active check for this amount in "
            "@CryptoBot and send a link like "
            "<code>https://t.me/CryptoBot?start=CQ...</code>.\n\n"
            "⚠️ The request is processed only after manual verification."
        ),
        "open_cryptobot": "🤖 Open CryptoBot",
        "cryptobot_invalid": "Send a valid active CryptoBot check link.",
        "cryptobot_submitted": "✅ CryptoBot check submitted for review.",
        "card_payment_info": (
            "<b>Card payment · {country}</b> 💳\n\n{item}: <b>#{item_id}</b>\n"
            "Amount: <b>{amount}</b>\n\nContact <b>@destroystoretp</b> for payment "
            "details and include the request number. Never send card numbers, CVV, "
            "or SMS codes inside the bot."
        ),
        "open_payment": "↗ Open wallet / network",
        "paid_submit": "✅ I paid — submit hash",
        "hash_prompt": "Send the {network} transaction hash:",
        "hash_invalid": "Invalid transaction hash.",
        "payment_submitted": "✅ Payment submitted for review.",
        "topup_submitted": "✅ Top-up submitted for review.",
        "already_used": "This hash or request has already been used.",
        "support_sent": "✅ Your message was sent to support.",
        "support_invalid": "Message must contain 2–2,000 characters.",
        "unknown": "Unknown action",
        "generic_error": "Something went wrong. Please try again.",
        "access_denied": "⛔ Access denied.",
        "referral_joined": "🎉 A new user joined through your referral link!",
        "status_awaiting_payment": "🕒 Awaiting payment",
        "status_payment_review": "🔎 Payment under review",
        "status_paid": "✅ Paid",
        "status_processing": "⚙️ Processing",
        "status_completed": "🏁 Completed",
        "status_cancelled": "❌ Cancelled",
        "status_update": "<b>Order #{order_id}</b>\n{status}",
        "topup_credited": "✅ Balance credited: {amount}",
        "topup_rejected": "❌ Top-up rejected.",
        "auto_topup_confirmed": (
            "✅ Transaction verified automatically. Balance credited: {amount}."
        ),
        "auto_order_confirmed": (
            "✅ Transaction verified automatically. Order #{order_id} is paid."
        ),
    },
    "fa": {
        "language_title": "<b>زبان رابط را انتخاب کنید</b> 🌍",
        "language_saved": "✅ زبان به فارسی تغییر کرد.",
        "subscribe_title": (
            "<b>🟢 ورود به JOULI MARKET</b>\n"
            "<blockquote>برای استفاده از ربات در کانال رسمی ما عضو شوید</blockquote>\n"
            "📣 کانال: <b>{channel}</b>\n\n"
            "پس از عضویت، «بررسی عضویت» را بزنید."
        ),
        "subscribe_open": "🟢 عضویت در کانال",
        "subscribe_check": "✅ بررسی عضویت",
        "subscribe_ok": "❤️ عضویت تأیید شد. به JOULI MARKET خوش آمدید!",
        "subscribe_missing": "❌ عضویت پیدا نشد. عضو شوید و دوباره بررسی کنید.",
        "subscribe_error": (
            "⚠️ بررسی عضویت انجام نشد. مطمئن شوید ربات مدیر کانال است."
        ),
        "home_tagline": "کالاهای دیجیتال — سریع، ساده و امن",
        "min_order_caption": "🧾 حداقل سفارش — <b>$10</b>",
        "catalog": "🛍 فروشگاه",
        "orders": "📦 سفارش‌های من",
        "profile": "👤 پروفایل",
        "topup": "💳 افزایش موجودی",
        "giveaway": "🎁 قرعه‌کشی ۱۵٪",
        "support": "💬 پشتیبانی",
        "suggestion": "💡 پیشنهاد ایده",
        "about": "🟢 درباره ربات",
        "help": "🛡 امنیت",
        "language": "🌍 تغییر زبان",
        "admin": "⚙️ پنل مدیریت",
        "back": "‹ بازگشت",
        "home": "⌂ منوی اصلی",
        "catalog_title": (
            "<b>فروشگاه محصولات</b> 🛍\n"
            "<blockquote>حداقل مبلغ سفارش $10 است</blockquote>\n"
            "یک بخش را انتخاب کنید:"
        ),
        "cat_stars": "⭐ ستاره‌های تلگرام",
        "cat_brawl": "🎫 براول پس",
        "cat_steam": "🎮 Steam",
        "cat_pubg": "🔫 PUBG UC",
        "cat_roblox": "🎮 روبلاکس",
        "cat_ai": "🤖 اشتراک‌های هوش مصنوعی",
        "cat_accounts": "🔐 حساب‌های دیجیتال",
        "cat_premium": "💎 پریمیوم تلگرام",
        "cat_gmail": "📧 حساب‌های Gmail",
        "cat_gta": "🚘 GTA V · Steam",
        "cat_rust": "🛢 Rust · Steam",
        "roblox_choose": (
            "<b>🟢 ROBLOX CENTER</b>\n"
            "<blockquote>روش دریافت Robux را انتخاب کنید</blockquote>"
        ),
        "roblox_account": "🟢 Robux از طریق حساب",
        "roblox_gamepass": "🎮 Robux از طریق Game Pass",
        "roblox_gifts": "🎁 کارت هدیه Roblox",
        "category_title": "<b>{title}</b>\n\nیک محصول را انتخاب کنید:",
        "orders_title": "<b>سفارش‌های من</b> 📦",
        "no_orders": "هنوز سفارشی ندارید.",
        "profile_text": (
            "<b>پروفایل من</b> 👤\n\nشناسه: <code>{user_id}</code>\n"
            "موجودی: <b>{balance}</b>\nتخفیف: <b>{discount}%</b>\n"
            "معرفی‌ها: <b>{referrals}</b>\n\nلینک شما:\n{referral_url}"
        ),
        "add_funds": "<b>افزایش موجودی</b> 💳\nحداقل واریز: <b>$10</b>",
        "custom_amount": "✏️ مبلغ دلخواه",
        "custom_amount_prompt": "مبلغی بین $10 تا $10,000 وارد کنید:",
        "profile_bonus": "\n🎁 تخفیف برنده‌شده: <b>۱۵٪</b> برای سفارش بعدی × {uses}",
        "giveaway_card": (
            "<b>قرعه‌کشی تخفیف ۱۵٪</b> 🎁\n\nهر ۴۸ ساعت ربات یک کاربر را "
            "به‌صورت تصادفی انتخاب می‌کند. برنده برای سفارش بعدی ۱۵٪ تخفیف می‌گیرد.\n\n"
            "زمان تا قرعه‌کشی بعدی: <b>{countdown}</b>{bonus}"
        ),
        "giveaway_bonus": "\n\n✅ شما یک تخفیف برنده‌شده دارید × {uses}.",
        "giveaway_winner": (
            "🎉 <b>شما برنده قرعه‌کشی شدید!</b>\n\nتخفیف ۱۵٪ به‌طور خودکار "
            "برای سفارش بعدی اعمال می‌شود."
        ),
        "support_card": (
            "<b>پشتیبانی JOULI MARKET</b> 💬\n\nبرای سفارش و پرداخت به "
            "<b>@destroystoretp</b> پیام دهید."
        ),
        "open_support": "✉️ پیام به @destroystoretp",
        "support_prompt": "مشکل خود را در یک پیام توضیح دهید:",
        "suggestion_prompt": (
            "<b>پیشنهاد بهبود</b> 💡\n\nمحصول یا قابلیت پیشنهادی خود را در "
            "۵ تا ۲۰۰۰ نویسه بنویسید:"
        ),
        "suggestion_sent": "✅ سپاس! پیشنهاد شما برای مدیر ارسال شد.",
        "suggestion_invalid": "پیشنهاد باید بین ۵ تا ۲۰۰۰ نویسه باشد.",
        "about_text": (
            "<b>🟢 JOULI MARKET • DIGITAL MARKET</b>\n"
            "<blockquote>فروشگاه مدرن کالاهای دیجیتال در تلگرام</blockquote>\n"
            "🛍 <b>فروشگاه گسترده</b> — Stars، Premium، بازی، Robux، AI و حساب‌ها.\n"
            "💳 <b>پرداخت متنوع</b> — Telegram Stars، TON، USDT، SOL، CryptoBot، موجودی و کارت.\n"
            "🟢 <b>خرید NFT</b> — ارزیابی دستی هر درخواست.\n"
            "🌍 <b>۱۳ زبان</b> برای خریداران بین‌المللی.\n"
            "📦 <b>پیگیری سفارش</b> با تاریخچه، وضعیت و اعلان مراحل.\n"
            "🛡 <b>امنیت</b> — ربات CVV، کد پیامک یا عبارت بازیابی درخواست نمی‌کند.\n"
            "👑 <b>مدیر</b> — {owner}.\n"
            "👑 <b>مدیر دوم</b> — {second_admin}.\n"
            "🛠 <b>پشتیبانی فنی</b> — {support}."
        ),
        "security": (
            "<b>امنیت</b> 🛡\n\nرمز عبور، عبارت بازیابی یا کد ورود را با کسی به اشتراک نگذارید. "
            "همیشه شبکه و مبلغ انتقال را بررسی کنید."
        ),
        "product_not_found": "محصول پیدا نشد",
        "quantity_prompt": "یک تعداد صحیح بین {minimum} تا {maximum} وارد کنید:",
        "stars_prompt": "تعداد Stars را بین {minimum} تا {maximum} وارد کنید:",
        "robux_prompt": "مقدار Robux را بین {minimum} تا {maximum} وارد کنید:",
        "steam_amount_prompt": (
            "مبلغ شارژ Steam را به دلار از ${minimum} تا ${maximum} وارد کنید "
            "(عدد صحیح):"
        ),
        "uc_prompt": "مقدار PUBG UC را از {minimum} تا {maximum} وارد کنید:",
        "recipient_telegram": "نام کاربری تلگرام گیرنده را با @ ارسال کنید:",
        "recipient_player": "شناسه بازیکن یا تگ بازی گیرنده را ارسال کنید:",
        "recipient_roblox": "نام کاربری یا شناسه Roblox گیرنده را ارسال کنید:",
        "recipient_steam": (
            "نام کاربری Steam یا لینک پروفایل را بفرستید. هرگز رمز عبور نفرستید:"
        ),
        "recipient_pubg": "شناسه بازیکن PUBG و منطقه گیرنده را ارسال کنید:",
        "recipient_email": "ایمیل تحویل محصول را ارسال کنید:",
        "product_card": (
            "{emoji} <b>{title}</b>\n<blockquote>{description}</blockquote>\n\n"
            "💵 قیمت: <b>{price}</b>\n📦 حداقل: <b>{minimum}</b>\n"
            "🧾 حداقل سفارش: <b>$10</b>"
        ),
        "buy_now": "✨ خرید",
        "desc_stars": "Stars مستقیماً به حساب تلگرام گیرنده ارسال می‌شود.",
        "desc_brawl": "Brawl Pass با شناسه بازیکن تحویل می‌شود.",
        "desc_steam": "شارژ Steam Wallet به دلار با کارمزد ۲٪.",
        "desc_pubg": "PUBG Mobile UC با نرخ ۱ UC برابر ۱ RUB.",
        "desc_roblox": "Robux و کارت هدیه Roblox با بررسی دستی سفارش.",
        "desc_ai": "اشتراک دیجیتال هوش مصنوعی به ایمیل مشخص‌شده تحویل می‌شود.",
        "desc_accounts": (
            "اطلاعات حساب دیجیتال به ایمیل تحویل می‌شود. پس از دریافت، رمز عبور "
            "را تغییر دهید و احراز هویت دومرحله‌ای را فعال کنید."
        ),
        "desc_premium": "یک ماه Telegram Premium برای حساب مشخص‌شده.",
        "desc_gmail": (
            "اطلاعات حساب Gmail به ایمیل تحویل می‌شود. پس از دریافت، رمز عبور را "
            "تغییر دهید و احراز هویت دومرحله‌ای را فعال کنید."
        ),
        "desc_gta": "اطلاعات حساب Steam دارای GTA V به ایمیل مشخص‌شده تحویل می‌شود.",
        "desc_rust": "اطلاعات حساب Steam دارای Rust به ایمیل مشخص‌شده تحویل می‌شود.",
        "recipient_invalid": "اطلاعات معتبر گیرنده را وارد کنید.",
        "minimum_order": "حداقل مبلغ سفارش $10 است.",
        "order_created": "<b>سفارش #{order_id} ایجاد شد</b> ✨\nروش پرداخت را انتخاب کنید:",
        "choose_crypto": "<b>روش پرداخت را انتخاب کنید</b> 💳",
        "pay_balance": "💰 پرداخت از موجودی",
        "pay_card_ru": "🇷🇺 کارت روسیه",
        "pay_card_ua": "🇺🇦 کارت اوکراین",
        "pay_card_gb": "🇬🇧 کارت بریتانیا",
        "pay_cryptobot": "🤖 چک CryptoBot",
        "pay_ton": "💎 TON",
        "pay_trc20": "🟢 USDT · TRC20",
        "pay_erc20": "🟢 USDT · ERC20",
        "pay_sol": "🟢 SOL · Solana",
        "order_unavailable": "سفارش در دسترس نیست",
        "topup_unavailable": "واریز در دسترس نیست",
        "insufficient": "موجودی کافی نیست. مبلغ لازم: {amount}",
        "balance_paid": "✅ سفارش #{order_id} از موجودی پرداخت شد.",
        "rate_error": "نرخ ارز موقتاً در دسترس نیست. یک دقیقه دیگر تلاش کنید.",
        "payment_caption": (
            "<b>{title} #{item_id}</b> 💳\n\nارزش سفارش/واریز: <b>{fiat}</b>\n"
            "مبلغ پرداخت: <b>{crypto}</b>\nشبکه: <b>{network}</b>\n"
            "کیف پول: <code>{wallet}</code>\nشناسه پرداخت: <code>{reference}</code>\n\n"
            "⚠️ فقط در شبکه انتخاب‌شده ارسال کنید. سپس دکمه زیر را بزنید و هش تراکنش را بفرستید."
        ),
        "order_payment_title": "پرداخت سفارش",
        "topup_payment_title": "افزایش موجودی",
        "cryptobot_prompt": (
            "<b>پرداخت با چک CryptoBot</b> 🤖\n\nدرخواست: <b>#{item_id}</b>\n"
            "مبلغ: <b>{amount}</b>\n\nیک چک فعال با این مبلغ در @CryptoBot بسازید "
            "و لینک <code>https://t.me/CryptoBot?start=CQ...</code> را ارسال کنید.\n\n"
            "⚠️ درخواست پس از بررسی دستی انجام می‌شود."
        ),
        "open_cryptobot": "🤖 باز کردن CryptoBot",
        "cryptobot_invalid": "یک لینک معتبر و فعال چک CryptoBot ارسال کنید.",
        "cryptobot_submitted": "✅ چک CryptoBot برای بررسی ارسال شد.",
        "card_payment_info": (
            "<b>پرداخت با کارت · {country}</b> 💳\n\n{item}: <b>#{item_id}</b>\n"
            "مبلغ: <b>{amount}</b>\n\nبرای دریافت اطلاعات پرداخت با "
            "<b>@destroystoretp</b> تماس بگیرید و شماره درخواست را بنویسید. "
            "شماره کارت، CVV یا کد پیامک را در ربات ارسال نکنید."
        ),
        "open_payment": "↗ باز کردن کیف پول / شبکه",
        "paid_submit": "✅ پرداخت کردم — ارسال هش",
        "hash_prompt": "هش تراکنش شبکه {network} را ارسال کنید:",
        "hash_invalid": "هش تراکنش معتبر نیست.",
        "payment_submitted": "✅ پرداخت برای بررسی ارسال شد.",
        "topup_submitted": "✅ واریز برای بررسی ارسال شد.",
        "already_used": "این هش یا درخواست قبلاً استفاده شده است.",
        "support_sent": "✅ پیام شما برای پشتیبانی ارسال شد.",
        "support_invalid": "پیام باید بین ۲ تا ۲۰۰۰ نویسه باشد.",
        "unknown": "عملیات ناشناخته",
        "generic_error": "خطایی رخ داد. دوباره تلاش کنید.",
        "access_denied": "⛔ دسترسی مجاز نیست.",
        "referral_joined": "🎉 یک کاربر جدید با لینک معرفی شما عضو شد!",
        "status_awaiting_payment": "🕒 در انتظار پرداخت",
        "status_payment_review": "🔎 پرداخت در حال بررسی",
        "status_paid": "✅ پرداخت‌شده",
        "status_processing": "⚙️ در حال انجام",
        "status_completed": "🏁 تکمیل‌شده",
        "status_cancelled": "❌ لغوشده",
        "status_update": "<b>سفارش #{order_id}</b>\n{status}",
        "topup_credited": "✅ موجودی به مقدار {amount} افزایش یافت",
        "topup_rejected": "❌ واریز رد شد.",
        "auto_topup_confirmed": (
            "✅ تراکنش خودکار تأیید شد. موجودی به مقدار {amount} افزایش یافت."
        ),
        "auto_order_confirmed": (
            "✅ تراکنش خودکار تأیید شد. سفارش #{order_id} پرداخت شد."
        ),
    },
}

EXTRA_TEXTS: dict[str, dict[str, str]] = {
    "es": {
        "language_saved": "✅ Idioma cambiado a español.",
        "home_tagline": "Productos digitales — rápidos, cómodos y seguros",
        "min_order_caption": "🧾 Pedido mínimo — <b>$10</b>",
        "catalog": "🛍 Catálogo",
        "orders": "📦 Mis pedidos",
        "profile": "👤 Perfil",
        "topup": "💳 Añadir saldo",
        "giveaway": "🎁 Sorteo del 15%",
        "support": "💬 Soporte",
        "help": "🛡 Seguridad",
        "language": "🌍 Cambiar idioma",
        "back": "‹ Atrás",
        "home": "⌂ Menú principal",
        "catalog_title": "<b>Catálogo de productos</b> 🛍\n<blockquote>Pedido mínimo — $10</blockquote>\nElige una sección:",
        "cat_stars": "⭐ Estrellas de Telegram",
        "cat_brawl": "🎫 Brawl Pass",
        "cat_steam": "🎮 Steam",
        "cat_pubg": "🔫 PUBG UC",
        "cat_roblox": "🎮 Roblox",
        "cat_ai": "🤖 Suscripciones de IA",
        "category_title": "<b>{title}</b>\n\nElige un producto:",
        "orders_title": "<b>Mis pedidos</b> 📦",
        "no_orders": "Aún no tienes pedidos.",
        "profile_text": "<b>Mi perfil</b> 👤\n\nID: <code>{user_id}</code>\nSaldo: <b>{balance}</b>\nDescuento: <b>{discount}%</b>\nReferidos: <b>{referrals}</b>\n\nTu enlace:\n{referral_url}",
        "add_funds": "<b>Añadir saldo</b> 💳\nRecarga mínima: <b>$10</b>",
        "custom_amount": "✏️ Otra cantidad",
        "custom_amount_prompt": "Introduce una cantidad de $10 a $10,000:",
        "support_card": "<b>Soporte JOULI MARKET</b> 💬\n\nPara pedidos y pagos, escribe a <b>@destroystoretp</b>.",
        "open_support": "✉️ Escribir a @destroystoretp",
        "security": "<b>Seguridad</b> 🛡\n\nNunca compartas contraseñas, frases semilla ni códigos. Comprueba siempre la red y el importe.",
        "buy_now": "✨ Comprar ahora",
        "minimum_order": "El pedido mínimo es de $10.",
        "order_created": "<b>Pedido #{order_id} creado</b> ✨\nElige un método de pago:",
        "choose_crypto": "<b>Elige una criptomoneda</b> 💳",
        "pay_balance": "💰 Pagar con saldo",
        "payment_caption": "<b>{title} #{item_id}</b> 💳\n\nValor: <b>{fiat}</b>\nA pagar: <b>{crypto}</b>\nRed: <b>{network}</b>\nCartera: <code>{wallet}</code>\nReferencia: <code>{reference}</code>\n\n⚠️ Envía solo por la red indicada. Después pulsa el botón y envía el hash.",
        "open_payment": "↗ Abrir cartera / red",
        "paid_submit": "✅ He pagado — enviar hash",
        "hash_prompt": "Envía el hash de la transacción {network}:",
        "hash_invalid": "Hash de transacción no válido.",
        "payment_submitted": "✅ Pago enviado para revisión.",
        "topup_submitted": "✅ Recarga enviada para revisión.",
        "generic_error": "Algo salió mal. Inténtalo de nuevo.",
    },
    "pt": {
        "language_saved": "✅ Idioma alterado para português.",
        "home_tagline": "Produtos digitais — rápidos, simples e seguros",
        "min_order_caption": "🧾 Pedido mínimo — <b>$10</b>",
        "catalog": "🛍 Catálogo",
        "orders": "📦 Meus pedidos",
        "profile": "👤 Perfil",
        "topup": "💳 Adicionar saldo",
        "giveaway": "🎁 Sorteio de 15%",
        "support": "💬 Suporte",
        "help": "🛡 Segurança",
        "language": "🌍 Alterar idioma",
        "back": "‹ Voltar",
        "home": "⌂ Menu principal",
        "catalog_title": "<b>Catálogo de produtos</b> 🛍\n<blockquote>Pedido mínimo — $10</blockquote>\nEscolha uma seção:",
        "cat_stars": "⭐ Estrelas do Telegram",
        "cat_brawl": "🎫 Brawl Pass",
        "cat_steam": "🎮 Steam",
        "cat_pubg": "🔫 PUBG UC",
        "cat_roblox": "🎮 Roblox",
        "cat_ai": "🤖 Assinaturas de IA",
        "category_title": "<b>{title}</b>\n\nEscolha um produto:",
        "orders_title": "<b>Meus pedidos</b> 📦",
        "no_orders": "Você ainda não tem pedidos.",
        "profile_text": "<b>Meu perfil</b> 👤\n\nID: <code>{user_id}</code>\nSaldo: <b>{balance}</b>\nDesconto: <b>{discount}%</b>\nIndicações: <b>{referrals}</b>\n\nSeu link:\n{referral_url}",
        "add_funds": "<b>Adicionar saldo</b> 💳\nRecarga mínima: <b>$10</b>",
        "custom_amount": "✏️ Outro valor",
        "custom_amount_prompt": "Digite um valor de $10 a $10,000:",
        "support_card": "<b>Suporte JOULI MARKET</b> 💬\n\nPara pedidos e pagamentos, fale com <b>@destroystoretp</b>.",
        "open_support": "✉️ Falar com @destroystoretp",
        "security": "<b>Segurança</b> 🛡\n\nNunca compartilhe senhas, frases-semente ou códigos. Confira sempre a rede e o valor.",
        "buy_now": "✨ Comprar agora",
        "minimum_order": "O pedido mínimo é de $10.",
        "order_created": "<b>Pedido #{order_id} criado</b> ✨\nEscolha uma forma de pagamento:",
        "choose_crypto": "<b>Escolha uma criptomoeda</b> 💳",
        "pay_balance": "💰 Pagar com saldo",
        "payment_caption": "<b>{title} #{item_id}</b> 💳\n\nValor: <b>{fiat}</b>\nA pagar: <b>{crypto}</b>\nRede: <b>{network}</b>\nCarteira: <code>{wallet}</code>\nReferência: <code>{reference}</code>\n\n⚠️ Envie somente pela rede indicada. Depois toque no botão e envie o hash.",
        "open_payment": "↗ Abrir carteira / rede",
        "paid_submit": "✅ Paguei — enviar hash",
        "hash_prompt": "Envie o hash da transação {network}:",
        "hash_invalid": "Hash de transação inválido.",
        "payment_submitted": "✅ Pagamento enviado para análise.",
        "topup_submitted": "✅ Recarga enviada para análise.",
        "generic_error": "Algo deu errado. Tente novamente.",
    },
    "de": {
        "language_saved": "✅ Sprache auf Deutsch geändert.",
        "home_tagline": "Digitale Produkte — schnell, einfach und sicher",
        "min_order_caption": "🧾 Mindestbestellwert — <b>$10</b>",
        "catalog": "🛍 Katalog",
        "orders": "📦 Meine Bestellungen",
        "profile": "👤 Profil",
        "topup": "💳 Guthaben aufladen",
        "giveaway": "🎁 15%-Gewinnspiel",
        "support": "💬 Support",
        "help": "🛡 Sicherheit",
        "language": "🌍 Sprache ändern",
        "back": "‹ Zurück",
        "home": "⌂ Hauptmenü",
        "catalog_title": "<b>Produktkatalog</b> 🛍\n<blockquote>Mindestbestellwert — $10</blockquote>\nWähle einen Bereich:",
        "cat_stars": "⭐ Telegram Stars",
        "cat_brawl": "🎫 Brawl Pass",
        "cat_steam": "🎮 Steam",
        "cat_pubg": "🔫 PUBG UC",
        "cat_roblox": "🎮 Roblox",
        "cat_ai": "🤖 KI-Abonnements",
        "category_title": "<b>{title}</b>\n\nWähle ein Produkt:",
        "orders_title": "<b>Meine Bestellungen</b> 📦",
        "no_orders": "Du hast noch keine Bestellungen.",
        "profile_text": "<b>Mein Profil</b> 👤\n\nID: <code>{user_id}</code>\nGuthaben: <b>{balance}</b>\nRabatt: <b>{discount}%</b>\nEmpfehlungen: <b>{referrals}</b>\n\nDein Link:\n{referral_url}",
        "add_funds": "<b>Guthaben aufladen</b> 💳\nMindesteinzahlung: <b>$10</b>",
        "custom_amount": "✏️ Anderer Betrag",
        "custom_amount_prompt": "Gib einen Betrag von $10 bis $10,000 ein:",
        "support_card": "<b>JOULI MARKET Support</b> 💬\n\nBei Fragen zu Bestellungen und Zahlungen: <b>@destroystoretp</b>.",
        "open_support": "✉️ @destroystoretp schreiben",
        "security": "<b>Sicherheit</b> 🛡\n\nTeile niemals Passwörter, Seed-Phrasen oder Codes. Prüfe immer Netzwerk und Betrag.",
        "buy_now": "✨ Jetzt kaufen",
        "minimum_order": "Der Mindestbestellwert beträgt $10.",
        "order_created": "<b>Bestellung #{order_id} erstellt</b> ✨\nWähle eine Zahlungsmethode:",
        "choose_crypto": "<b>Kryptowährung wählen</b> 💳",
        "pay_balance": "💰 Mit Guthaben zahlen",
        "payment_caption": "<b>{title} #{item_id}</b> 💳\n\nWert: <b>{fiat}</b>\nZu zahlen: <b>{crypto}</b>\nNetzwerk: <b>{network}</b>\nWallet: <code>{wallet}</code>\nReferenz: <code>{reference}</code>\n\n⚠️ Nur über das angegebene Netzwerk senden. Danach den Transaktions-Hash übermitteln.",
        "open_payment": "↗ Wallet / Netzwerk öffnen",
        "paid_submit": "✅ Bezahlt — Hash senden",
        "hash_prompt": "Sende den {network}-Transaktions-Hash:",
        "hash_invalid": "Ungültiger Transaktions-Hash.",
        "payment_submitted": "✅ Zahlung zur Prüfung gesendet.",
        "topup_submitted": "✅ Aufladung zur Prüfung gesendet.",
        "generic_error": "Etwas ist schiefgelaufen. Versuche es erneut.",
    },
    "fr": {
        "language_saved": "✅ Langue changée en français.",
        "home_tagline": "Produits numériques — rapides, simples et sécurisés",
        "min_order_caption": "🧾 Commande minimale — <b>$10</b>",
        "catalog": "🛍 Catalogue",
        "orders": "📦 Mes commandes",
        "profile": "👤 Profil",
        "topup": "💳 Ajouter des fonds",
        "giveaway": "🎁 Tirage à 15 %",
        "support": "💬 Assistance",
        "help": "🛡 Sécurité",
        "language": "🌍 Changer de langue",
        "back": "‹ Retour",
        "home": "⌂ Menu principal",
        "catalog_title": "<b>Catalogue de produits</b> 🛍\n<blockquote>Commande minimale — $10</blockquote>\nChoisissez une catégorie :",
        "cat_stars": "⭐ Étoiles Telegram",
        "cat_brawl": "🎫 Brawl Pass",
        "cat_steam": "🎮 Steam",
        "cat_pubg": "🔫 PUBG UC",
        "cat_roblox": "🎮 Roblox",
        "cat_ai": "🤖 Abonnements IA",
        "category_title": "<b>{title}</b>\n\nChoisissez un produit :",
        "orders_title": "<b>Mes commandes</b> 📦",
        "no_orders": "Vous n’avez pas encore de commande.",
        "profile_text": "<b>Mon profil</b> 👤\n\nID : <code>{user_id}</code>\nSolde : <b>{balance}</b>\nRéduction : <b>{discount}%</b>\nParrainages : <b>{referrals}</b>\n\nVotre lien :\n{referral_url}",
        "add_funds": "<b>Ajouter des fonds</b> 💳\nRecharge minimale : <b>$10</b>",
        "custom_amount": "✏️ Autre montant",
        "custom_amount_prompt": "Saisissez un montant de $10 à $10,000 :",
        "support_card": "<b>Assistance JOULI MARKET</b> 💬\n\nPour les commandes et paiements, contactez <b>@destroystoretp</b>.",
        "open_support": "✉️ Écrire à @destroystoretp",
        "security": "<b>Sécurité</b> 🛡\n\nNe partagez jamais vos mots de passe, phrases de récupération ou codes. Vérifiez toujours le réseau et le montant.",
        "buy_now": "✨ Acheter",
        "minimum_order": "La commande minimale est de $10.",
        "order_created": "<b>Commande #{order_id} créée</b> ✨\nChoisissez un mode de paiement :",
        "choose_crypto": "<b>Choisissez une cryptomonnaie</b> 💳",
        "pay_balance": "💰 Payer avec le solde",
        "payment_caption": "<b>{title} #{item_id}</b> 💳\n\nValeur : <b>{fiat}</b>\nÀ payer : <b>{crypto}</b>\nRéseau : <b>{network}</b>\nPortefeuille : <code>{wallet}</code>\nRéférence : <code>{reference}</code>\n\n⚠️ Envoyez uniquement sur le réseau indiqué, puis transmettez le hash.",
        "open_payment": "↗ Ouvrir le portefeuille / réseau",
        "paid_submit": "✅ J’ai payé — envoyer le hash",
        "hash_prompt": "Envoyez le hash de transaction {network} :",
        "hash_invalid": "Hash de transaction invalide.",
        "payment_submitted": "✅ Paiement envoyé pour vérification.",
        "topup_submitted": "✅ Recharge envoyée pour vérification.",
        "generic_error": "Une erreur est survenue. Réessayez.",
    },
    "tr": {
        "language_saved": "✅ Dil Türkçe olarak değiştirildi.",
        "home_tagline": "Dijital ürünler — hızlı, kolay ve güvenli",
        "min_order_caption": "🧾 Minimum sipariş — <b>$10</b>",
        "catalog": "🛍 Katalog",
        "orders": "📦 Siparişlerim",
        "profile": "👤 Profil",
        "topup": "💳 Bakiye yükle",
        "giveaway": "🎁 %15 çekiliş",
        "support": "💬 Destek",
        "help": "🛡 Güvenlik",
        "language": "🌍 Dili değiştir",
        "back": "‹ Geri",
        "home": "⌂ Ana menü",
        "catalog_title": "<b>Ürün kataloğu</b> 🛍\n<blockquote>Minimum sipariş — $10</blockquote>\nBir bölüm seçin:",
        "cat_stars": "⭐ Telegram Yıldızları",
        "cat_brawl": "🎫 Brawl Pass",
        "cat_steam": "🎮 Steam",
        "cat_pubg": "🔫 PUBG UC",
        "cat_roblox": "🎮 Roblox",
        "cat_ai": "🤖 Yapay zekâ abonelikleri",
        "category_title": "<b>{title}</b>\n\nBir ürün seçin:",
        "orders_title": "<b>Siparişlerim</b> 📦",
        "no_orders": "Henüz siparişiniz yok.",
        "profile_text": "<b>Profilim</b> 👤\n\nID: <code>{user_id}</code>\nBakiye: <b>{balance}</b>\nİndirim: <b>{discount}%</b>\nReferanslar: <b>{referrals}</b>\n\nBağlantınız:\n{referral_url}",
        "add_funds": "<b>Bakiye yükle</b> 💳\nMinimum yükleme: <b>$10</b>",
        "custom_amount": "✏️ Farklı tutar",
        "custom_amount_prompt": "$10 ile $10,000 arasında bir tutar girin:",
        "support_card": "<b>JOULI MARKET Destek</b> 💬\n\nSipariş ve ödeme soruları için <b>@destroystoretp</b> ile iletişime geçin.",
        "open_support": "✉️ @destroystoretp’ya yaz",
        "security": "<b>Güvenlik</b> 🛡\n\nŞifre, kurtarma ifadesi veya kod paylaşmayın. Ağı ve tutarı her zaman kontrol edin.",
        "buy_now": "✨ Şimdi satın al",
        "minimum_order": "Minimum sipariş tutarı $10.",
        "order_created": "<b>Sipariş #{order_id} oluşturuldu</b> ✨\nÖdeme yöntemi seçin:",
        "choose_crypto": "<b>Kripto para seçin</b> 💳",
        "pay_balance": "💰 Bakiyeden öde",
        "payment_caption": "<b>{title} #{item_id}</b> 💳\n\nDeğer: <b>{fiat}</b>\nÖdenecek: <b>{crypto}</b>\nAğ: <b>{network}</b>\nCüzdan: <code>{wallet}</code>\nReferans: <code>{reference}</code>\n\n⚠️ Yalnızca belirtilen ağdan gönderin. Ardından işlem hash’ini iletin.",
        "open_payment": "↗ Cüzdanı / ağı aç",
        "paid_submit": "✅ Ödedim — hash gönder",
        "hash_prompt": "{network} işlem hash’ini gönderin:",
        "hash_invalid": "Geçersiz işlem hash’i.",
        "payment_submitted": "✅ Ödeme incelemeye gönderildi.",
        "topup_submitted": "✅ Yükleme incelemeye gönderildi.",
        "generic_error": "Bir hata oluştu. Tekrar deneyin.",
    },
    "ar": {
        "language_saved": "✅ تم تغيير اللغة إلى العربية.",
        "home_tagline": "منتجات رقمية — سريعة وسهلة وآمنة",
        "min_order_caption": "🧾 الحد الأدنى للطلب — <b>$10</b>",
        "catalog": "🛍 المتجر",
        "orders": "📦 طلباتي",
        "profile": "👤 الملف الشخصي",
        "topup": "💳 إضافة رصيد",
        "giveaway": "🎁 سحب خصم 15%",
        "support": "💬 الدعم",
        "help": "🛡 الأمان",
        "language": "🌍 تغيير اللغة",
        "back": "‹ رجوع",
        "home": "⌂ القائمة الرئيسية",
        "catalog_title": "<b>كتالوج المنتجات</b> 🛍\n<blockquote>الحد الأدنى للطلب — $10</blockquote>\nاختر قسمًا:",
        "cat_stars": "⭐ نجوم تيليجرام",
        "cat_brawl": "🎫 Brawl Pass",
        "cat_steam": "🎮 Steam",
        "cat_pubg": "🔫 PUBG UC",
        "cat_roblox": "🎮 Roblox",
        "cat_ai": "🤖 اشتراكات الذكاء الاصطناعي",
        "category_title": "<b>{title}</b>\n\nاختر منتجًا:",
        "orders_title": "<b>طلباتي</b> 📦",
        "no_orders": "لا توجد طلبات بعد.",
        "profile_text": "<b>ملفي الشخصي</b> 👤\n\nالمعرف: <code>{user_id}</code>\nالرصيد: <b>{balance}</b>\nالخصم: <b>{discount}%</b>\nالإحالات: <b>{referrals}</b>\n\nرابطك:\n{referral_url}",
        "add_funds": "<b>إضافة رصيد</b> 💳\nالحد الأدنى للشحن: <b>$10</b>",
        "custom_amount": "✏️ مبلغ آخر",
        "custom_amount_prompt": "أدخل مبلغًا من $10 إلى $10,000:",
        "support_card": "<b>دعم JOULI MARKET</b> 💬\n\nللطلبات والمدفوعات تواصل مع <b>@destroystoretp</b>.",
        "open_support": "✉️ مراسلة @destroystoretp",
        "security": "<b>الأمان</b> 🛡\n\nلا تشارك كلمات المرور أو عبارات الاسترداد أو الرموز. تحقق دائمًا من الشبكة والمبلغ.",
        "buy_now": "✨ شراء الآن",
        "minimum_order": "الحد الأدنى للطلب هو $10.",
        "order_created": "<b>تم إنشاء الطلب #{order_id}</b> ✨\nاختر طريقة الدفع:",
        "choose_crypto": "<b>اختر العملة الرقمية</b> 💳",
        "pay_balance": "💰 الدفع من الرصيد",
        "payment_caption": "<b>{title} #{item_id}</b> 💳\n\nالقيمة: <b>{fiat}</b>\nالمبلغ المطلوب: <b>{crypto}</b>\nالشبكة: <b>{network}</b>\nالمحفظة: <code>{wallet}</code>\nالمرجع: <code>{reference}</code>\n\n⚠️ أرسل عبر الشبكة المحددة فقط، ثم أرسل معرّف المعاملة.",
        "open_payment": "↗ فتح المحفظة / الشبكة",
        "paid_submit": "✅ دفعت — إرسال المعرّف",
        "hash_prompt": "أرسل معرّف معاملة {network}:",
        "hash_invalid": "معرّف المعاملة غير صالح.",
        "payment_submitted": "✅ تم إرسال الدفع للمراجعة.",
        "topup_submitted": "✅ تم إرسال الشحن للمراجعة.",
        "generic_error": "حدث خطأ. حاول مرة أخرى.",
    },
    "hi": {
        "language_saved": "✅ भाषा हिन्दी में बदल दी गई है।",
        "home_tagline": "डिजिटल उत्पाद — तेज़, आसान और सुरक्षित",
        "min_order_caption": "🧾 न्यूनतम ऑर्डर — <b>$10</b>",
        "catalog": "🛍 कैटलॉग",
        "orders": "📦 मेरे ऑर्डर",
        "profile": "👤 प्रोफ़ाइल",
        "topup": "💳 बैलेंस जोड़ें",
        "giveaway": "🎁 15% गिवअवे",
        "support": "💬 सहायता",
        "help": "🛡 सुरक्षा",
        "language": "🌍 भाषा बदलें",
        "back": "‹ वापस",
        "home": "⌂ मुख्य मेनू",
        "catalog_title": "<b>उत्पाद कैटलॉग</b> 🛍\n<blockquote>न्यूनतम ऑर्डर — $10</blockquote>\nएक श्रेणी चुनें:",
        "cat_stars": "⭐ Telegram Stars",
        "cat_brawl": "🎫 Brawl Pass",
        "cat_steam": "🎮 Steam",
        "cat_pubg": "🔫 PUBG UC",
        "cat_roblox": "🎮 Roblox",
        "cat_ai": "🤖 AI सदस्यताएँ",
        "category_title": "<b>{title}</b>\n\nएक उत्पाद चुनें:",
        "orders_title": "<b>मेरे ऑर्डर</b> 📦",
        "no_orders": "अभी कोई ऑर्डर नहीं है।",
        "profile_text": "<b>मेरी प्रोफ़ाइल</b> 👤\n\nID: <code>{user_id}</code>\nबैलेंस: <b>{balance}</b>\nछूट: <b>{discount}%</b>\nरेफ़रल: <b>{referrals}</b>\n\nआपका लिंक:\n{referral_url}",
        "add_funds": "<b>बैलेंस जोड़ें</b> 💳\nन्यूनतम टॉप-अप: <b>$10</b>",
        "custom_amount": "✏️ दूसरी राशि",
        "custom_amount_prompt": "$10 से $10,000 तक राशि दर्ज करें:",
        "support_card": "<b>JOULI MARKET सहायता</b> 💬\n\nऑर्डर और भुगतान के लिए <b>@destroystoretp</b> से संपर्क करें।",
        "open_support": "✉️ @destroystoretp को लिखें",
        "security": "<b>सुरक्षा</b> 🛡\n\nपासवर्ड, सीड वाक्यांश या कोड साझा न करें। नेटवर्क और राशि हमेशा जाँचें।",
        "buy_now": "✨ अभी खरीदें",
        "minimum_order": "न्यूनतम ऑर्डर $10 है।",
        "order_created": "<b>ऑर्डर #{order_id} बन गया</b> ✨\nभुगतान विधि चुनें:",
        "choose_crypto": "<b>क्रिप्टोकरेंसी चुनें</b> 💳",
        "pay_balance": "💰 बैलेंस से भुगतान",
        "payment_caption": "<b>{title} #{item_id}</b> 💳\n\nमूल्य: <b>{fiat}</b>\nदेय: <b>{crypto}</b>\nनेटवर्क: <b>{network}</b>\nवॉलेट: <code>{wallet}</code>\nसंदर्भ: <code>{reference}</code>\n\n⚠️ केवल बताए गए नेटवर्क पर भेजें, फिर ट्रांज़ैक्शन हैश भेजें।",
        "open_payment": "↗ वॉलेट / नेटवर्क खोलें",
        "paid_submit": "✅ भुगतान किया — हैश भेजें",
        "hash_prompt": "{network} ट्रांज़ैक्शन हैश भेजें:",
        "hash_invalid": "ट्रांज़ैक्शन हैश अमान्य है।",
        "payment_submitted": "✅ भुगतान जाँच के लिए भेजा गया।",
        "topup_submitted": "✅ टॉप-अप जाँच के लिए भेजा गया।",
        "generic_error": "कुछ गलत हुआ। फिर कोशिश करें।",
    },
    "id": {
        "language_saved": "✅ Bahasa diubah ke Indonesia.",
        "home_tagline": "Produk digital — cepat, mudah, dan aman",
        "min_order_caption": "🧾 Pesanan minimum — <b>$10</b>",
        "catalog": "🛍 Katalog",
        "orders": "📦 Pesanan saya",
        "profile": "👤 Profil",
        "topup": "💳 Isi saldo",
        "giveaway": "🎁 Undian diskon 15%",
        "support": "💬 Dukungan",
        "help": "🛡 Keamanan",
        "language": "🌍 Ganti bahasa",
        "back": "‹ Kembali",
        "home": "⌂ Menu utama",
        "catalog_title": "<b>Katalog produk</b> 🛍\n<blockquote>Pesanan minimum — $10</blockquote>\nPilih kategori:",
        "cat_stars": "⭐ Telegram Stars",
        "cat_brawl": "🎫 Brawl Pass",
        "cat_steam": "🎮 Steam",
        "cat_pubg": "🔫 PUBG UC",
        "cat_roblox": "🎮 Roblox",
        "cat_ai": "🤖 Langganan AI",
        "category_title": "<b>{title}</b>\n\nPilih produk:",
        "orders_title": "<b>Pesanan saya</b> 📦",
        "no_orders": "Belum ada pesanan.",
        "profile_text": "<b>Profil saya</b> 👤\n\nID: <code>{user_id}</code>\nSaldo: <b>{balance}</b>\nDiskon: <b>{discount}%</b>\nReferal: <b>{referrals}</b>\n\nTautan Anda:\n{referral_url}",
        "add_funds": "<b>Isi saldo</b> 💳\nTop-up minimum: <b>$10</b>",
        "custom_amount": "✏️ Jumlah lain",
        "custom_amount_prompt": "Masukkan jumlah dari $10 hingga $10,000:",
        "support_card": "<b>Dukungan JOULI MARKET</b> 💬\n\nUntuk pesanan dan pembayaran, hubungi <b>@destroystoretp</b>.",
        "open_support": "✉️ Hubungi @destroystoretp",
        "security": "<b>Keamanan</b> 🛡\n\nJangan bagikan kata sandi, seed phrase, atau kode. Selalu periksa jaringan dan jumlah.",
        "buy_now": "✨ Beli sekarang",
        "minimum_order": "Pesanan minimum adalah $10.",
        "order_created": "<b>Pesanan #{order_id} dibuat</b> ✨\nPilih metode pembayaran:",
        "choose_crypto": "<b>Pilih mata uang kripto</b> 💳",
        "pay_balance": "💰 Bayar dari saldo",
        "payment_caption": "<b>{title} #{item_id}</b> 💳\n\nNilai: <b>{fiat}</b>\nJumlah bayar: <b>{crypto}</b>\nJaringan: <b>{network}</b>\nDompet: <code>{wallet}</code>\nReferensi: <code>{reference}</code>\n\n⚠️ Kirim hanya melalui jaringan yang dipilih, lalu kirim hash transaksi.",
        "open_payment": "↗ Buka dompet / jaringan",
        "paid_submit": "✅ Sudah bayar — kirim hash",
        "hash_prompt": "Kirim hash transaksi {network}:",
        "hash_invalid": "Hash transaksi tidak valid.",
        "payment_submitted": "✅ Pembayaran dikirim untuk ditinjau.",
        "topup_submitted": "✅ Top-up dikirim untuk ditinjau.",
        "generic_error": "Terjadi kesalahan. Coba lagi.",
    },
    "zh": {
        "language_saved": "✅ 语言已切换为中文。",
        "home_tagline": "数字商品 — 快速、便捷、安全",
        "min_order_caption": "🧾 最低订单 — <b>$10</b>",
        "catalog": "🛍 商品目录",
        "orders": "📦 我的订单",
        "profile": "👤 个人资料",
        "topup": "💳 充值余额",
        "giveaway": "🎁 15% 折扣抽奖",
        "support": "💬 客服",
        "help": "🛡 安全须知",
        "language": "🌍 切换语言",
        "back": "‹ 返回",
        "home": "⌂ 主菜单",
        "catalog_title": "<b>商品目录</b> 🛍\n<blockquote>最低订单 — $10</blockquote>\n请选择分类：",
        "cat_stars": "⭐ Telegram 星星",
        "cat_brawl": "🎫 Brawl Pass",
        "cat_steam": "🎮 Steam",
        "cat_pubg": "🔫 PUBG UC",
        "cat_roblox": "🎮 Roblox",
        "cat_ai": "🤖 AI 订阅",
        "category_title": "<b>{title}</b>\n\n请选择商品：",
        "orders_title": "<b>我的订单</b> 📦",
        "no_orders": "您还没有订单。",
        "profile_text": "<b>我的资料</b> 👤\n\nID：<code>{user_id}</code>\n余额：<b>{balance}</b>\n折扣：<b>{discount}%</b>\n推荐人数：<b>{referrals}</b>\n\n您的链接：\n{referral_url}",
        "add_funds": "<b>充值余额</b> 💳\n最低充值：<b>$10</b>",
        "custom_amount": "✏️ 其他金额",
        "custom_amount_prompt": "请输入 $10 至 $10,000 的金额：",
        "support_card": "<b>JOULI MARKET 客服</b> 💬\n\n订单和付款问题请联系 <b>@destroystoretp</b>。",
        "open_support": "✉️ 联系 @destroystoretp",
        "security": "<b>安全须知</b> 🛡\n\n请勿分享密码、助记词或验证码。务必核对网络和金额。",
        "buy_now": "✨ 立即购买",
        "minimum_order": "最低订单金额为 $10。",
        "order_created": "<b>订单 #{order_id} 已创建</b> ✨\n请选择付款方式：",
        "choose_crypto": "<b>请选择加密货币</b> 💳",
        "pay_balance": "💰 使用余额支付",
        "payment_caption": "<b>{title} #{item_id}</b> 💳\n\n价值：<b>{fiat}</b>\n应付：<b>{crypto}</b>\n网络：<b>{network}</b>\n钱包：<code>{wallet}</code>\n付款编号：<code>{reference}</code>\n\n⚠️ 仅通过所选网络发送，然后提交交易哈希。",
        "open_payment": "↗ 打开钱包 / 网络",
        "paid_submit": "✅ 已付款 — 提交哈希",
        "hash_prompt": "请发送 {network} 交易哈希：",
        "hash_invalid": "交易哈希无效。",
        "payment_submitted": "✅ 付款已提交审核。",
        "topup_submitted": "✅ 充值已提交审核。",
        "generic_error": "出现错误，请重试。",
    },
    "ja": {
        "language_saved": "✅ 言語を日本語に変更しました。",
        "home_tagline": "デジタル商品 — 速く、簡単、安全に",
        "min_order_caption": "🧾 最低注文額 — <b>$10</b>",
        "catalog": "🛍 カタログ",
        "orders": "📦 注文履歴",
        "profile": "👤 プロフィール",
        "topup": "💳 残高を追加",
        "giveaway": "🎁 15%割引抽選",
        "support": "💬 サポート",
        "help": "🛡 セキュリティ",
        "language": "🌍 言語を変更",
        "back": "‹ 戻る",
        "home": "⌂ メインメニュー",
        "catalog_title": "<b>商品カタログ</b> 🛍\n<blockquote>最低注文額 — $10</blockquote>\nカテゴリーを選択してください：",
        "cat_stars": "⭐ Telegram Stars",
        "cat_brawl": "🎫 Brawl Pass",
        "cat_steam": "🎮 Steam",
        "cat_pubg": "🔫 PUBG UC",
        "cat_roblox": "🎮 Roblox",
        "cat_ai": "🤖 AIサブスクリプション",
        "category_title": "<b>{title}</b>\n\n商品を選択してください：",
        "orders_title": "<b>注文履歴</b> 📦",
        "no_orders": "まだ注文はありません。",
        "profile_text": "<b>プロフィール</b> 👤\n\nID：<code>{user_id}</code>\n残高：<b>{balance}</b>\n割引：<b>{discount}%</b>\n紹介数：<b>{referrals}</b>\n\n紹介リンク：\n{referral_url}",
        "add_funds": "<b>残高を追加</b> 💳\n最低入金額：<b>$10</b>",
        "custom_amount": "✏️ その他の金額",
        "custom_amount_prompt": "$10から$10,000の金額を入力してください：",
        "support_card": "<b>JOULI MARKETサポート</b> 💬\n\n注文・支払いについては <b>@destroystoretp</b> までご連絡ください。",
        "open_support": "✉️ @destroystoretp に連絡",
        "security": "<b>セキュリティ</b> 🛡\n\nパスワード、シードフレーズ、コードを共有しないでください。ネットワークと金額を必ず確認してください。",
        "buy_now": "✨ 今すぐ購入",
        "minimum_order": "最低注文額は$10です。",
        "order_created": "<b>注文 #{order_id} を作成しました</b> ✨\n支払い方法を選択してください：",
        "choose_crypto": "<b>暗号資産を選択してください</b> 💳",
        "pay_balance": "💰 残高で支払う",
        "payment_caption": "<b>{title} #{item_id}</b> 💳\n\n価値：<b>{fiat}</b>\n支払額：<b>{crypto}</b>\nネットワーク：<b>{network}</b>\nウォレット：<code>{wallet}</code>\n参照番号：<code>{reference}</code>\n\n⚠️ 指定ネットワークのみで送金し、取引ハッシュを送信してください。",
        "open_payment": "↗ ウォレット / ネットワークを開く",
        "paid_submit": "✅ 支払い済み — ハッシュを送信",
        "hash_prompt": "{network} の取引ハッシュを送信してください：",
        "hash_invalid": "取引ハッシュが無効です。",
        "payment_submitted": "✅ 支払いを確認のため送信しました。",
        "topup_submitted": "✅ 入金を確認のため送信しました。",
        "generic_error": "エラーが発生しました。もう一度お試しください。",
    },
}

for language_code, translations in EXTRA_TEXTS.items():
    TEXTS[language_code] = {**TEXTS["en"], **translations}

FEATURE_TEXT_KEYS = (
    "cat_accounts",
    "suggestion",
    "suggestion_prompt",
    "suggestion_sent",
    "suggestion_invalid",
    "choose_crypto",
    "pay_card_ru",
    "pay_card_ua",
    "desc_accounts",
)
FEATURE_TEXTS = {
    "es": (
        "🔐 Cuentas digitales",
        "💡 Proponer una idea",
        "<b>Proponer una mejora</b> 💡\n\nEscribe qué producto o función deberíamos añadir (5–2.000 caracteres):",
        "✅ ¡Gracias! Tu propuesta fue enviada al administrador.",
        "La propuesta debe contener entre 5 y 2.000 caracteres.",
        "<b>Elige un método de pago</b> 💳",
        "🇷🇺 Tarjeta rusa",
        "🇺🇦 Tarjeta ucraniana",
        "Cuenta digital entregada por email. Cambia la contraseña y activa la autenticación en dos pasos.",
    ),
    "pt": (
        "🔐 Contas digitais",
        "💡 Sugerir uma ideia",
        "<b>Sugerir uma melhoria</b> 💡\n\nDiga qual produto ou função devemos adicionar (5–2.000 caracteres):",
        "✅ Obrigado! Sua sugestão foi enviada ao administrador.",
        "A sugestão deve conter de 5 a 2.000 caracteres.",
        "<b>Escolha uma forma de pagamento</b> 💳",
        "🇷🇺 Cartão russo",
        "🇺🇦 Cartão ucraniano",
        "Conta digital entregue por email. Altere a senha e ative a autenticação em duas etapas.",
    ),
    "de": (
        "🔐 Digitale Konten",
        "💡 Idee vorschlagen",
        "<b>Verbesserung vorschlagen</b> 💡\n\nWelches Produkt oder welche Funktion sollen wir hinzufügen? (5–2.000 Zeichen):",
        "✅ Danke! Dein Vorschlag wurde an den Administrator gesendet.",
        "Der Vorschlag muss 5–2.000 Zeichen enthalten.",
        "<b>Zahlungsmethode wählen</b> 💳",
        "🇷🇺 Russische Karte",
        "🇺🇦 Ukrainische Karte",
        "Digitales Konto per E-Mail. Ändere das Passwort und aktiviere die Zwei-Faktor-Authentifizierung.",
    ),
    "fr": (
        "🔐 Comptes numériques",
        "💡 Proposer une idée",
        "<b>Proposer une amélioration</b> 💡\n\nQuel produit ou quelle fonction devons-nous ajouter ? (5–2 000 caractères) :",
        "✅ Merci ! Votre proposition a été envoyée à l’administrateur.",
        "La proposition doit contenir entre 5 et 2 000 caractères.",
        "<b>Choisissez un mode de paiement</b> 💳",
        "🇷🇺 Carte russe",
        "🇺🇦 Carte ukrainienne",
        "Compte numérique livré par e-mail. Modifiez le mot de passe et activez l’authentification à deux facteurs.",
    ),
    "tr": (
        "🔐 Dijital hesaplar",
        "💡 Fikir öner",
        "<b>İyileştirme öner</b> 💡\n\nEklenmesini istediğiniz ürün veya özelliği yazın (5–2.000 karakter):",
        "✅ Teşekkürler! Öneriniz yöneticiye gönderildi.",
        "Öneri 5–2.000 karakter olmalıdır.",
        "<b>Ödeme yöntemi seçin</b> 💳",
        "🇷🇺 Rusya kartı",
        "🇺🇦 Ukrayna kartı",
        "Dijital hesap e-posta ile teslim edilir. Parolayı değiştirin ve iki aşamalı doğrulamayı açın.",
    ),
    "ar": (
        "🔐 حسابات رقمية",
        "💡 اقترح فكرة",
        "<b>اقترح تحسينًا</b> 💡\n\nاكتب المنتج أو الميزة التي تريد إضافتها (من 5 إلى 2000 حرف):",
        "✅ شكرًا! تم إرسال اقتراحك إلى المسؤول.",
        "يجب أن يحتوي الاقتراح على 5 إلى 2000 حرف.",
        "<b>اختر طريقة الدفع</b> 💳",
        "🇷🇺 بطاقة روسية",
        "🇺🇦 بطاقة أوكرانية",
        "يتم تسليم الحساب الرقمي عبر البريد الإلكتروني. غيّر كلمة المرور وفعّل المصادقة الثنائية.",
    ),
    "hi": (
        "🔐 डिजिटल खाते",
        "💡 सुझाव दें",
        "<b>सुधार सुझाएँ</b> 💡\n\nबताएँ कि कौन-सा उत्पाद या सुविधा जोड़नी चाहिए (5–2,000 अक्षर):",
        "✅ धन्यवाद! आपका सुझाव एडमिन को भेज दिया गया है।",
        "सुझाव में 5–2,000 अक्षर होने चाहिए।",
        "<b>भुगतान विधि चुनें</b> 💳",
        "🇷🇺 रूसी कार्ड",
        "🇺🇦 यूक्रेनी कार्ड",
        "डिजिटल खाता ईमेल से दिया जाता है। पासवर्ड बदलें और दो-चरणीय सुरक्षा चालू करें।",
    ),
    "id": (
        "🔐 Akun digital",
        "💡 Sarankan ide",
        "<b>Sarankan peningkatan</b> 💡\n\nTulis produk atau fitur yang perlu ditambahkan (5–2.000 karakter):",
        "✅ Terima kasih! Saran Anda dikirim ke admin.",
        "Saran harus berisi 5–2.000 karakter.",
        "<b>Pilih metode pembayaran</b> 💳",
        "🇷🇺 Kartu Rusia",
        "🇺🇦 Kartu Ukraina",
        "Akun digital dikirim melalui email. Ubah kata sandi dan aktifkan autentikasi dua langkah.",
    ),
    "zh": (
        "🔐 数字账号",
        "💡 提交建议",
        "<b>提交改进建议</b> 💡\n\n请说明希望添加的商品或功能（5–2,000个字符）：",
        "✅ 谢谢！您的建议已发送给管理员。",
        "建议内容必须为5–2,000个字符。",
        "<b>请选择付款方式</b> 💳",
        "🇷🇺 俄罗斯银行卡",
        "🇺🇦 乌克兰银行卡",
        "数字账号将通过邮箱交付。收到后请更改密码并启用双重验证。",
    ),
    "ja": (
        "🔐 デジタルアカウント",
        "💡 アイデアを提案",
        "<b>改善案を送る</b> 💡\n\n追加してほしい商品や機能を入力してください（5～2,000文字）：",
        "✅ ありがとうございます。提案を管理者に送信しました。",
        "提案は5～2,000文字で入力してください。",
        "<b>支払い方法を選択してください</b> 💳",
        "🇷🇺 ロシアのカード",
        "🇺🇦 ウクライナのカード",
        "デジタルアカウントはメールで納品されます。パスワードを変更し、二段階認証を有効にしてください。",
    ),
}
for language_code, values in FEATURE_TEXTS.items():
    TEXTS[language_code].update(dict(zip(FEATURE_TEXT_KEYS, values, strict=True)))

NEW_FEATURE_TEXTS = {
    "en": {
        "nft_buyback": "🟢 NFT buyback",
        "nft_buyback_card": (
            "<b>🟢 JOULI MARKET NFT BUYBACK</b>\n"
            "<blockquote>Send your collectible NFT for a manual valuation</blockquote>\n"
            "We buy Telegram collectible gifts/usernames and other supported NFTs. "
            "The administrator checks every request before making an offer."
        ),
        "nft_buyback_prompt": (
            "Send one message containing the NFT link, collection/network, your "
            "expected price and a short comment (10–2,000 characters). Never send "
            "a seed phrase, password or login code."
        ),
        "nft_buyback_invalid": "The NFT request must contain 10–2,000 characters.",
        "nft_buyback_sent": (
            "✅ NFT request #{request_id} was sent to the administrator. "
            "You will be contacted after manual review."
        ),
        "pay_stars": "🟢 Pay with Telegram Stars",
        "stars_invoice_title": "JOULI MARKET payment",
        "stars_invoice_desc": (
            "{kind} #{item_id} · {fiat}. Rate: 1 Star = {rate} RUB."
        ),
        "stars_invoice_sent": (
            "🟢 Telegram invoice created: <b>{stars} ⭐</b> at the rate "
            "1 ⭐ = {rate} RUB."
        ),
        "stars_paid_order": "✅ Order #{item_id} was paid with {stars} Telegram Stars.",
        "stars_paid_topup": (
            "✅ {stars} Telegram Stars were accepted. Your balance was credited by {amount}."
        ),
        "topup_stars_hint": (
            "Choose an amount, then press <b>Pay with Telegram Stars</b>. "
            "After a successful payment, the balance is credited automatically."
        ),
        "topup_stars_direct": "⭐ Top up with Telegram Stars",
        "topup_stars_amount_prompt": (
            "Enter an amount from $12.50 to $10,000. A Telegram Stars invoice "
            "will be created immediately."
        ),
        "referral_bonus_line": (
            "🟢 Referral bonus: <b>+{bonus}%</b>. Current discount: "
            "<b>{discount}%</b>."
        ),
        "profile_referral_bonus": (
            "\nReferral discount: <b>{discount}%</b> (maximum {maximum}%)"
        ),
        "wholesale_notice": (
            "📦 Wholesale discount: <b>{discount}%</b> on orders from "
            "<b>{minimum}</b> before discounts."
        ),
        "order_auto_close_notice": (
            "⏳ An unpaid order is automatically cancelled after {minutes} minutes."
        ),
        "order_auto_cancelled": (
            "⌛ Order #{order_id} was automatically cancelled because it was not "
            "paid within {minutes} minutes."
        ),
        "admin_balance_received": (
            "✅ An administrator credited {amount} to your balance. "
            "New balance: {balance}."
        ),
        "stars_payment_error": (
            "This Stars invoice is no longer available. Create a new payment invoice."
        ),
    },
    "ru": {
        "nft_buyback": "🟢 Скупка NFT",
        "nft_buyback_card": (
            "<b>🟢 JOULI MARKET · СКУПКА NFT</b>\n"
            "<blockquote>Отправьте коллекционный NFT на ручную оценку</blockquote>\n"
            "Принимаем заявки на Telegram-подарки, коллекционные username и другие "
            "поддерживаемые NFT. Администратор проверяет каждую заявку и предлагает цену."
        ),
        "nft_buyback_prompt": (
            "Одним сообщением отправьте ссылку на NFT, коллекцию/сеть, желаемую цену "
            "и короткий комментарий (10–2000 символов). Никогда не отправляйте "
            "seed-фразу, пароль или код входа."
        ),
        "nft_buyback_invalid": "Заявка на NFT должна содержать от 10 до 2000 символов.",
        "nft_buyback_sent": (
            "✅ Заявка на скупку NFT #{request_id} отправлена администратору. "
            "После ручной оценки с вами свяжутся."
        ),
        "pay_stars": "🟢 Оплатить Telegram Stars",
        "stars_invoice_title": "Оплата JOULI MARKET",
        "stars_invoice_desc": (
            "{kind} #{item_id} · {fiat}. Курс: 1 звезда = {rate} ₽."
        ),
        "stars_invoice_sent": (
            "🟢 Счёт Telegram создан: <b>{stars} ⭐</b> по курсу "
            "1 ⭐ = {rate} ₽."
        ),
        "stars_paid_order": "✅ Заказ #{item_id} оплачен: {stars} Telegram Stars.",
        "stars_paid_topup": (
            "✅ Получено {stars} Telegram Stars. Баланс пополнен на {amount}."
        ),
        "topup_stars_hint": (
            "Выберите сумму, затем нажмите <b>Оплатить Telegram Stars</b>. "
            "После успешной оплаты баланс пополнится автоматически."
        ),
        "topup_stars_direct": "⭐ Пополнить Telegram Stars",
        "topup_stars_amount_prompt": (
            "Введите сумму от $12.50 до $10 000. Бот сразу создаст счёт "
            "Telegram Stars."
        ),
        "referral_bonus_line": (
            "🟢 Реферальный бонус: <b>+{bonus}%</b>. Текущая скидка: "
            "<b>{discount}%</b>."
        ),
        "profile_referral_bonus": (
            "\nРеферальная скидка: <b>{discount}%</b> (максимум {maximum}%)"
        ),
        "wholesale_notice": (
            "📦 Оптовая скидка: <b>{discount}%</b> при сумме заказа от "
            "<b>{minimum}</b> до применения скидок."
        ),
        "order_auto_close_notice": (
            "⏳ Неоплаченный заказ автоматически отменится через {minutes} минут."
        ),
        "order_auto_cancelled": (
            "⌛ Заказ #{order_id} автоматически отменён: оплата не поступила "
            "в течение {minutes} минут."
        ),
        "admin_balance_received": (
            "✅ Администратор пополнил ваш баланс на {amount}. "
            "Новый баланс: {balance}."
        ),
        "stars_payment_error": (
            "Этот счёт Stars уже недоступен. Создайте новый счёт для оплаты."
        ),
    },
    "fa": {
        "nft_buyback": "🟢 خرید NFT",
        "nft_buyback_card": (
            "<b>🟢 خرید NFT در JOULI MARKET</b>\n"
            "<blockquote>NFT خود را برای ارزیابی دستی ارسال کنید</blockquote>"
        ),
        "nft_buyback_prompt": (
            "لینک NFT، مجموعه/شبکه، قیمت پیشنهادی و توضیح کوتاه را در یک پیام "
            "ارسال کنید (۱۰ تا ۲۰۰۰ نویسه)."
        ),
        "nft_buyback_invalid": "درخواست NFT باید ۱۰ تا ۲۰۰۰ نویسه باشد.",
        "nft_buyback_sent": "✅ درخواست NFT شماره {request_id} برای مدیر ارسال شد.",
        "pay_stars": "🟢 پرداخت با Telegram Stars",
        "stars_invoice_title": "پرداخت JOULI MARKET",
        "stars_invoice_desc": "{kind} #{item_id} · {fiat}. نرخ: هر ستاره {rate} روبل.",
        "stars_invoice_sent": "🟢 صورت‌حساب <b>{stars} ⭐</b> ایجاد شد.",
        "stars_paid_order": "✅ سفارش #{item_id} با {stars} ستاره پرداخت شد.",
        "stars_paid_topup": "✅ موجودی با {amount} افزایش یافت.",
        "topup_stars_hint": (
            "مبلغ را انتخاب کنید و سپس پرداخت با Telegram Stars را بزنید. "
            "پس از پرداخت موفق، موجودی به‌صورت خودکار افزایش می‌یابد."
        ),
        "topup_stars_direct": "⭐ افزایش موجودی با Telegram Stars",
        "topup_stars_amount_prompt": (
            "مبلغی از $12.50 تا $10,000 وارد کنید تا صورت‌حساب Stars ساخته شود."
        ),
        "referral_bonus_line": (
            "🟢 پاداش معرفی: <b>+{bonus}%</b>. تخفیف فعلی: <b>{discount}%</b>."
        ),
        "profile_referral_bonus": (
            "\nتخفیف معرفی: <b>{discount}%</b> (حداکثر {maximum}٪)"
        ),
        "wholesale_notice": (
            "📦 تخفیف عمده: <b>{discount}%</b> برای سفارش‌های حداقل "
            "<b>{minimum}</b> پیش از تخفیف."
        ),
        "order_auto_close_notice": (
            "⏳ سفارش پرداخت‌نشده پس از {minutes} دقیقه لغو می‌شود."
        ),
        "order_auto_cancelled": (
            "⌛ سفارش شماره {order_id} پس از {minutes} دقیقه به‌صورت خودکار لغو شد."
        ),
        "admin_balance_received": (
            "✅ مدیر {amount} به موجودی شما افزود. موجودی جدید: {balance}."
        ),
        "stars_payment_error": "این صورت‌حساب دیگر در دسترس نیست.",
    },
}
TEXTS["uk"] = dict(TEXTS["ru"])
for language_code in LANGUAGES:
    source = NEW_FEATURE_TEXTS.get(
        language_code,
        NEW_FEATURE_TEXTS["ru"] if language_code == "uk" else NEW_FEATURE_TEXTS["en"],
    )
    for key, value in source.items():
        TEXTS[language_code][key] = value

CURRENCY_AND_CATALOG_TEXTS = {
    "en": {
        "currency_title": (
            "<b>Choose your currency</b> 💱\n"
            "<blockquote>Prices will be converted using the current USD exchange rate.</blockquote>"
        ),
        "currency_saved": "✅ Display currency changed to {currency}.",
        "currency": "💱 Change currency",
        "promo": "🎟 Enter promo code",
        "promo_prompt": (
            "<b>Promo code</b> 🎟\n"
            "<blockquote>Enter your promo code. It will apply to your next order.</blockquote>"
        ),
        "promo_activated": "✅ Promo code {code} activated: {discount}% off your next order.",
        "promo_invalid": "❌ This promo code does not exist.",
        "promo_used": "❌ You have already used promo code {code}.",
        "promo_active": "⚠️ Promo code {code} ({discount}%) is already active.",
        "promo_profile": "\nPromo code: <b>{code}</b> · <b>{discount}%</b> on the next order.",
        "cat_robux": "🎮 Robux",
        "cat_robux_account": "👤 Robux via account",
        "cat_robux_gamepass": "🎟 Robux GamePass",
        "cat_robux_group": "👥 Robux via group",
        "cat_exitlag": "⚡ ExitLag accounts",
        "cat_roblox_gifts": "🎁 Roblox Gift Cards",
        "desc_robux_account_old": "Robux delivery through a Roblox account. Orders from $12.50.",
        "desc_robux_gamepass_old": "Robux delivery through a Game Pass. Orders from $12.50.",
        "desc_robux_account_new": (
            "Robux delivery through a Roblox account. Minimum order: 45,000 Robux."
        ),
        "desc_robux_gamepass_new": (
            "Robux delivery through a Game Pass. Minimum order: 45,000 Robux."
        ),
        "desc_robux_group": "Robux delivery through a Roblox group.",
        "desc_exitlag": "Ready ExitLag account. Warranty depends on the selected option.",
        "desc_premium": (
            "Telegram Premium for the selected subscription period and account."
        ),
        "admin_discount_received": (
            "✅ An administrator set your personal discount to {discount}%. "
            "Your current total discount is {total}%."
        ),
    },
    "ru": {
        "currency_title": (
            "<b>Выберите валюту</b> 💱\n"
            "<blockquote>Цены будут пересчитываться по актуальному курсу доллара.</blockquote>"
        ),
        "currency_saved": "✅ Валюта отображения изменена на {currency}.",
        "currency": "💱 Сменить валюту",
        "promo": "🎟 Ввести промокод",
        "promo_prompt": (
            "<b>Промокод</b> 🎟\n"
            "<blockquote>Введите промокод. Скидка применится к следующему заказу.</blockquote>"
        ),
        "promo_activated": "✅ Промокод {code} активирован: скидка {discount}% на следующий заказ.",
        "promo_invalid": "❌ Такого промокода не существует.",
        "promo_used": "❌ Вы уже использовали промокод {code}.",
        "promo_active": "⚠️ У вас уже активен промокод {code} со скидкой {discount}%.",
        "promo_profile": "\nПромокод: <b>{code}</b> · <b>{discount}%</b> на следующий заказ.",
        "cat_robux": "🎮 Robux",
        "cat_robux_account": "👤 Robux аккаунтом",
        "cat_robux_gamepass": "🎟 Robux GamePass",
        "cat_robux_group": "👥 Robux группой",
        "cat_exitlag": "⚡ Аккаунты ExitLag",
        "cat_roblox_gifts": "🎁 Подарочные карты Roblox",
        "desc_robux_account_old": "Robux с доставкой через аккаунт Roblox. Заказы от $12,50.",
        "desc_robux_gamepass_old": "Robux GamePass. Заказы от $12,50.",
        "desc_robux_account_new": (
            "Robux через аккаунт Roblox. Минимальный заказ — 45 000 Robux."
        ),
        "desc_robux_gamepass_new": (
            "Robux GamePass. Минимальный заказ — 45 000 Robux."
        ),
        "desc_robux_group": "Robux с получением через группу Roblox.",
        "desc_exitlag": "Готовый аккаунт ExitLag. Гарантия зависит от выбранного варианта.",
        "desc_premium": (
            "Telegram Premium на выбранный период для указанного аккаунта."
        ),
        "admin_discount_received": (
            "✅ Администратор установил вам персональную скидку {discount}%. "
            "Текущая общая скидка: {total}%."
        ),
    },
    "fa": {
        "currency_title": (
            "<b>ارز را انتخاب کنید</b> 💱\n"
            "<blockquote>قیمت‌ها با نرخ فعلی دلار تبدیل می‌شوند.</blockquote>"
        ),
        "currency_saved": "✅ ارز نمایش به {currency} تغییر کرد.",
        "currency": "💱 تغییر ارز",
        "promo": "🎟 وارد کردن کد تخفیف",
        "promo_prompt": "<b>کد تخفیف</b> 🎟\n<blockquote>کد را وارد کنید؛ تخفیف برای سفارش بعدی اعمال می‌شود.</blockquote>",
        "promo_activated": "✅ کد {code} فعال شد: {discount}٪ تخفیف برای سفارش بعدی.",
        "promo_invalid": "❌ این کد تخفیف وجود ندارد.",
        "promo_used": "❌ کد {code} قبلاً استفاده شده است.",
        "promo_active": "⚠️ کد {code} با تخفیف {discount}٪ هم‌اکنون فعال است.",
        "promo_profile": "\nکد تخفیف: <b>{code}</b> · <b>{discount}٪</b> برای سفارش بعدی.",
        "cat_robux": "🎮 Robux",
        "cat_robux_account": "👤 Robux از طریق حساب",
        "cat_robux_gamepass": "🎟 Robux GamePass",
        "cat_robux_group": "👥 Robux از طریق گروه",
        "cat_exitlag": "⚡ حساب‌های ExitLag",
        "cat_roblox_gifts": "🎁 کارت هدیه Roblox",
        "desc_robux_account_old": "تحویل Robux از طریق حساب Roblox؛ سفارش از $12.50.",
        "desc_robux_gamepass_old": "تحویل Robux از طریق Game Pass؛ سفارش از $12.50.",
        "desc_robux_account_new": "تحویل Robux از طریق حساب Roblox؛ حداقل ۴۵٬۰۰۰ Robux.",
        "desc_robux_gamepass_new": "تحویل Robux از طریق Game Pass؛ حداقل ۴۵٬۰۰۰ Robux.",
        "desc_robux_group": "تحویل Robux از طریق گروه Roblox.",
        "desc_exitlag": "حساب آماده ExitLag؛ ضمانت به گزینه انتخابی بستگی دارد.",
        "desc_premium": "Telegram Premium برای دوره و حساب انتخاب‌شده.",
        "admin_discount_received": (
            "✅ مدیر تخفیف شخصی شما را روی {discount}٪ تنظیم کرد. "
            "تخفیف کل فعلی: {total}٪."
        ),
    },
}
for language_code in LANGUAGES:
    TEXTS[language_code].update(
        CURRENCY_AND_CATALOG_TEXTS.get(
            language_code, CURRENCY_AND_CATALOG_TEXTS["en"]
        )
    )

TEXTS["uk"].update(
    {
        "language_title": "<b>Оберіть мову інтерфейсу</b> 🌐",
        "language_saved": "✅ Мову змінено на українську.",
        "subscribe_title": (
            "<b>🔒 Доступ до JOULI MARKET</b>\n"
            "<blockquote>Підпишіться на офіційний канал, щоб відкрити магазин</blockquote>\n"
            "📣 Канал: <b>{channel}</b>\n\n"
            "Після підписки натисніть «Перевірити підписку»."
        ),
        "subscribe_open": "➕ Підписатися на канал",
        "subscribe_check": "✅ Перевірити підписку",
        "subscribe_ok": "✅ Підписку підтверджено. Магазин відкрито!",
        "subscribe_missing": "❌ Підписку не знайдено. Підпишіться та перевірте ще раз.",
        "subscribe_error": "⚠️ Не вдалося перевірити підписку. Бот має бути адміністратором каналу.",
        "home_tagline": "Цифрові товари без зайвих кроків",
        "min_order_caption": "Мінімальне замовлення — <b>$10</b>",
        "catalog": "Каталог",
        "orders": "Мої замовлення",
        "profile": "Профіль",
        "topup": "Поповнити баланс",
        "giveaway": "Розіграш 15%",
        "support": "Підтримка",
        "suggestion": "Запропонувати ідею",
        "about": "Про магазин",
        "help": "Безпека",
        "language": "Змінити мову",
        "admin": "Адмін-панель",
        "back": "‹ Назад",
        "home": "Головне меню",
        "catalog_title": (
            "<b>Оберіть напрямок</b>\n"
            "<blockquote>Мінімальна сума замовлення — $10</blockquote>"
        ),
        "cat_stars": "⭐ Telegram Stars",
        "cat_brawl": "🎫 Brawl Pass",
        "cat_steam": "🎮 Поповнення Steam",
        "cat_pubg": "🔫 PUBG UC",
        "cat_roblox": "🎮 Roblox",
        "cat_ai": "🤖 AI-підписки",
        "cat_accounts": "🔐 Цифрові акаунти",
        "cat_premium": "💎 Telegram Premium",
        "cat_gmail": "📧 Акаунти Gmail",
        "cat_gta": "🚘 GTA V · Steam",
        "cat_rust": "🛢 Rust · Steam",
        "roblox_choose": "<b>Оберіть спосіб отримання Robux</b>",
        "roblox_account": "👤 Robux через акаунт",
        "roblox_gamepass": "🎟 Robux GamePass",
        "roblox_gifts": "🎁 Подарункові картки Roblox",
        "category_title": "<b>{title}</b>\nОберіть товар:",
        "orders_title": "<b>Ваші останні замовлення</b>",
        "no_orders": "У вас ще немає замовлень.",
        "add_funds": "<b>Поповнення балансу</b>\nОберіть суму від $12.50 або введіть власну.",
        "custom_amount": "Інша сума",
        "custom_amount_prompt": "Введіть суму від $12.50 до $10,000:",
        "profile_bonus": "Доступна знижка: <b>{discount}%</b>",
        "profile_text": (
            "<b>Мій профіль</b>\n\nID: <code>{user_id}</code>\n"
            "Баланс: <b>{balance}</b>\nЗнижка: <b>{discount}%</b>\n"
            "Реферали: <b>{referrals}</b>\n\nВаше посилання:\n{referral_url}"
        ),
        "giveaway_card": (
            "<b>Розіграш знижки 15%</b>\n\nКожні 48 годин бот випадково "
            "обирає переможця. До наступного розіграшу: <b>{countdown}</b>{bonus}"
        ),
        "support_card": "<b>Підтримка JOULI MARKET</b>\n\nНапишіть <b>@destroystoretp</b> щодо замовлень та оплати.",
        "open_support": "Написати @destroystoretp",
        "support_prompt": "Опишіть питання одним повідомленням (5–2000 символів):",
        "suggestion_prompt": "Напишіть, який товар або функцію варто додати (5–2000 символів):",
        "suggestion_sent": "✅ Пропозицію надіслано адміністратору.",
        "suggestion_invalid": "Повідомлення має містити від 5 до 2000 символів.",
        "security": "<b>Безпека</b>\n\nНе передавайте паролі, seed-фрази та коди входу. Завжди перевіряйте мережу й суму.",
        "about_text": (
            "<b>🌿 Jouli Market</b>\n"
            "<blockquote>Зелений магазин популярних цифрових товарів</blockquote>\n"
            "⭐ Telegram Stars · 🔫 PUBG UC · 🎫 Brawl Pass\n"
            "🎮 Robux · 🤖 AI-підписки\n"
            "💳 Оплата: TON, USDT, SOL або баланс.\n"
            "🌍 Українська, російська та англійська."
        ),
        "product_not_found": "Товар не знайдено.",
        "quantity_prompt": "Введіть кількість від {minimum} до {maximum}:",
        "stars_prompt": "Введіть кількість Stars від {minimum} до {maximum}:",
        "robux_prompt": "Введіть кількість Robux від {minimum} до {maximum}:",
        "steam_amount_prompt": "Введіть суму поповнення Steam від {minimum} до {maximum} USD:",
        "uc_prompt": "Введіть кількість UC від {minimum} до {maximum}:",
        "recipient_telegram": "Введіть Telegram username отримувача:",
        "recipient_player": "Введіть ID гравця:",
        "recipient_roblox": "Введіть нік Roblox та потрібні дані для доставки:",
        "recipient_steam": "Введіть логін Steam:",
        "recipient_pubg": "Введіть Player ID PUBG:",
        "recipient_email": "Введіть email для отримання:",
        "buy_now": "Оформити замовлення",
        "product_card": (
            "{emoji} <b>{title}</b>\n<blockquote>{description}</blockquote>\n\n"
            "Ціна: <b>{price}</b>\nМінімум: <b>{minimum}</b>\n"
            "Мінімальне замовлення: <b>$10</b>"
        ),
        "minimum_order": "Мінімальна сума замовлення — $10.",
        "order_created": "<b>Замовлення #{order_id} створено</b>\nОберіть спосіб оплати:",
        "choose_crypto": "<b>Оберіть спосіб оплати</b>",
        "pay_balance": "Сплатити з балансу",
        "order_unavailable": "Замовлення недоступне для оплати.",
        "topup_unavailable": "Поповнення недоступне.",
        "insufficient": "Недостатньо коштів. Потрібно: {amount}",
        "balance_paid": "✅ Замовлення сплачено з балансу.",
        "rate_error": "Не вдалося отримати курс. Спробуйте пізніше.",
        "payment_caption": (
            "<b>{title} #{item_id}</b>\n\nСума: <b>{fiat}</b>\n"
            "До сплати: <b>{crypto}</b>\nМережа: <b>{network}</b>\n"
            "Гаманець: <code>{wallet}</code>\nНомер: <code>{reference}</code>\n\n"
            "⚠️ Надсилайте кошти тільки у вказаній мережі."
        ),
        "paid_submit": "Я сплатив — надіслати хеш",
        "hash_prompt": "Надішліть хеш транзакції {network}:",
        "hash_invalid": "Неправильний формат хешу.",
        "payment_submitted": "✅ Платіж надіслано на перевірку.",
        "topup_submitted": "✅ Поповнення надіслано на перевірку.",
        "unknown": "Невідома дія.",
        "generic_error": "Сталася помилка. Спробуйте ще раз.",
        "access_denied": "Доступ заборонено.",
        "currency_title": (
            "<b>Оберіть валюту цін</b>\n"
            "<blockquote>Доступні тільки долар США та російський рубль</blockquote>"
        ),
        "currency_saved": "✅ Валюту змінено на {currency}.",
        "currency": "Змінити валюту",
        "promo": "Ввести промокод",
        "promo_prompt": "<b>Промокод</b>\nВведіть код для знижки на наступне замовлення.",
        "promo_activated": "✅ Промокод {code} активовано: знижка {discount}%.",
        "promo_invalid": "❌ Такого промокоду немає.",
        "promo_used": "❌ Ви вже використали промокод {code}.",
        "promo_active": "⚠️ Промокод {code} ({discount}%) уже активний.",
        "cat_robux": "🎮 Robux",
        "cat_robux_account": "👤 Robux через акаунт",
        "cat_robux_gamepass": "🎟 Robux GamePass",
        "cat_robux_group": "👥 Robux через групу",
        "cat_exitlag": "⚡ Акаунти ExitLag",
        "cat_roblox_gifts": "🎁 Подарункові картки Roblox",
        "admin_discount_received": "✅ Адміністратор надав вам знижку {discount}%.",
        "pay_stars": "Сплатити Telegram Stars",
        "stars_invoice_title": "Оплата JOULI MARKET",
        "stars_invoice_desc": "{kind} #{item_id} · {fiat}. Курс: 1 Star = {rate} RUB.",
        "stars_invoice_sent": "Рахунок створено: <b>{stars} ⭐</b>. Курс 1 ⭐ = {rate} RUB.",
        "stars_paid_order": "✅ Замовлення #{item_id} сплачено: {stars} Stars.",
        "stars_paid_topup": "✅ Отримано {stars} Stars. Баланс поповнено на {amount}.",
        "topup_stars_hint": "Оберіть суму та натисніть <b>Сплатити Telegram Stars</b>.",
        "topup_stars_direct": "Поповнити через Telegram Stars",
        "topup_stars_amount_prompt": "Введіть суму від $12.50 до $10,000.",
        "wholesale_notice": "Оптова знижка <b>{discount}%</b> для замовлень від <b>{minimum}</b>.",
        "order_auto_close_notice": "Неоплачене замовлення скасовується через {minutes} хвилин.",
        "order_auto_cancelled": "Замовлення #{order_id} автоматично скасовано через {minutes} хвилин без оплати.",
    }
)

ORDER_LABELS = {
    "ru": ("Количество", "Получатель", "Итого"),
    "uk": ("Кількість", "Отримувач", "Разом"),
    "en": ("Quantity", "Recipient", "Total"),
    "fa": ("تعداد", "گیرنده", "مجموع"),
    "es": ("Cantidad", "Destinatario", "Total"),
    "pt": ("Quantidade", "Destinatário", "Total"),
    "de": ("Menge", "Empfänger", "Gesamt"),
    "fr": ("Quantité", "Destinataire", "Total"),
    "tr": ("Miktar", "Alıcı", "Toplam"),
    "ar": ("الكمية", "المستلم", "الإجمالي"),
    "hi": ("मात्रा", "प्राप्तकर्ता", "कुल"),
    "id": ("Jumlah", "Penerima", "Total"),
    "zh": ("数量", "接收者", "总计"),
    "ja": ("数量", "受取人", "合計"),
}

DISCOUNT_LABELS = {
    "ru": ("Скидка", "опт"),
    "uk": ("Знижка", "опт"),
    "en": ("Discount", "wholesale"),
    "fa": ("تخفیف", "عمده"),
}


def text(lang: str, key: str, **values: Any) -> str:
    selected = lang if lang in LANGUAGES else "en"
    template = TEXTS.get(selected, {}).get(key, TEXTS["en"][key])
    display_currency = str(values.pop("_currency", "usd")).lower()
    if display_currency not in CURRENCIES:
        display_currency = "usd"
    rendered = template.format(**values).replace("@destroystoretp", SUPPORT_USERNAME)
    if key in {
        "min_order_caption",
        "catalog_title",
        "product_card",
        "minimum_order",
    }:
        rendered = rendered.replace(
            "$10", format_usd_cents(MIN_ORDER_USD_CENTS, display_currency)
        )
    if key in {
        "add_funds",
        "custom_amount_prompt",
        "topup_stars_amount_prompt",
    }:
        rendered = rendered.replace(
            "$12.50", format_usd_cents(minimum_topup_cents(), display_currency), 1
        )
        rendered = rendered.replace(
            "$10,000", format_usd_cents(MAX_TOPUP_CENTS, display_currency), 1
        )
        rendered = rendered.replace(
            "$10 000", format_usd_cents(MAX_TOPUP_CENTS, display_currency), 1
        )
        rendered = rendered.replace(
            "$10", format_usd_cents(minimum_topup_cents(), display_currency), 1
        )
    return rendered


@dataclass(frozen=True, slots=True)
class Product:
    code: str
    titles: dict[str, str]
    emoji: str
    category: str
    currency: str
    unit_minor: int
    divisor: int = 1
    minimum: int = 1
    maximum: int = 1
    custom_quantity: bool = False
    recipient_kind: str = "player"
    bulk_unit_minor: int | None = None
    bulk_threshold_minor: int = 0

    def title(self, lang: str) -> str:
        if lang == "uk":
            return self.titles.get("uk", self.titles.get("ru", self.titles["en"]))
        return self.titles.get(lang, self.titles["en"])

    def selling_unit_minor(self, quantity: int | None = None) -> Decimal:
        unit_minor = self.unit_minor
        if self.bulk_unit_minor is not None and quantity is not None:
            bulk_total = Decimal(self.bulk_unit_minor) * quantity / self.divisor
            if bulk_total >= self.bulk_threshold_minor:
                unit_minor = self.bulk_unit_minor
        increase = (
            Decimal("0")
            if self.code in PRICE_INCREASE_EXEMPT_CODES
            else CATALOG_PRICE_INCREASE_PERCENT
        )
        current_price = Decimal(unit_minor) * (
            Decimal("1")
            + (PRICE_MARKUP_PERCENT + increase) / Decimal("100")
        )
        return current_price * (
            Decimal("1") - CATALOG_PRICE_DECREASE_PERCENT / Decimal("100")
        )

    def total_minor(self, quantity: int) -> int:
        return int(
            (self.selling_unit_minor(quantity) * quantity / self.divisor).quantize(
                Decimal("1"), rounding=ROUND_UP
            )
        )


def titles(en: str, ru: str | None = None, fa: str | None = None) -> dict[str, str]:
    return {"en": en, "ru": ru or en, "fa": fa or en}


def gift_titles(amount: str) -> dict[str, str]:
    return {
        "en": f"Roblox Gift Card {amount} R$ (RU)",
        "ru": f"Гифт-карта Roblox {amount} R$ (РФ)",
        "fa": f"کارت هدیه Roblox {amount} R$ (روسیه)",
    }


def rub_kopecks_to_usd_cents(kopecks: int) -> int:
    return int(
        (Decimal(kopecks) / RUB_PER_USD).quantize(Decimal("1"), rounding=ROUND_UP)
    )


def star_rate_text() -> str:
    return f"{TELEGRAM_STAR_RUB:f}".rstrip("0").rstrip(".")


def stars_for_minor(minor: int, currency: str) -> int:
    if minor <= 0 or currency not in {"usd", "rub"}:
        raise ValueError("Invalid Stars invoice amount")
    rubles = (
        Decimal(minor) / 100
        if currency == "rub"
        else Decimal(minor) / 100 * RUB_PER_USD
    )
    return int((rubles / TELEGRAM_STAR_RUB).to_integral_value(rounding=ROUND_UP))


PRODUCTS: dict[str, Product] = {
    "stars": Product(
        "stars",
        titles("Telegram Stars"),
        "⭐",
        "stars",
        "usd",
        rub_kopecks_to_usd_cents(100_000),
        divisor=1_000,
        minimum=1_000,
        maximum=1_000_000,
        custom_quantity=True,
        recipient_kind="telegram",
    ),
    "telegram_premium_1m": Product(
        "telegram_premium_1m",
        titles(
            "Telegram Premium · 1 month",
            "Telegram Premium · 1 месяц",
            "Telegram Premium · یک ماه",
        ),
        "💎",
        "premium",
        "usd",
        250,
        recipient_kind="telegram",
    ),
    "telegram_premium_3m": Product(
        "telegram_premium_3m",
        titles(
            "Telegram Premium · 3 months",
            "Telegram Premium · 3 месяца",
            "Telegram Premium · ۳ ماه",
        ),
        "💎",
        "premium",
        "usd",
        750,
        recipient_kind="telegram",
    ),
    "telegram_premium_6m": Product(
        "telegram_premium_6m",
        titles(
            "Telegram Premium · 6 months",
            "Telegram Premium · 6 месяцев",
            "Telegram Premium · ۶ ماه",
        ),
        "💎",
        "premium",
        "usd",
        1_250,
        recipient_kind="telegram",
    ),
    "telegram_premium_12m": Product(
        "telegram_premium_12m",
        titles(
            "Telegram Premium · 12 months",
            "Telegram Premium · 12 месяцев",
            "Telegram Premium · ۱۲ ماه",
        ),
        "💎",
        "premium",
        "usd",
        2_000,
        recipient_kind="telegram",
    ),
    "bp": Product(
        "bp",
        titles("Brawl Pass"),
        "🎫",
        "brawl",
        "usd",
        rub_kopecks_to_usd_cents(25_000),
        maximum=100,
        custom_quantity=True,
    ),
    "bp_plus": Product(
        "bp_plus",
        titles("Brawl Pass Plus"),
        "💎",
        "brawl",
        "usd",
        rub_kopecks_to_usd_cents(30_000),
        maximum=100,
        custom_quantity=True,
    ),
    "steam": Product(
        "steam",
        titles(
            "Steam Wallet top-up",
            "Пополнение Steam",
            "افزایش موجودی Steam",
        ),
        "🎮",
        "steam",
        "usd",
        102,
        minimum=10,
        maximum=10_000,
        custom_quantity=True,
        recipient_kind="steam",
    ),
    "pubg_uc": Product(
        "pubg_uc",
        titles("PUBG Mobile UC"),
        "🔫",
        "pubg",
        "usd",
        rub_kopecks_to_usd_cents(100_000),
        divisor=1_000,
        minimum=1,
        maximum=1_000_000,
        custom_quantity=True,
        recipient_kind="pubg",
    ),
    "robux": Product(
        "robux",
        titles(
            "Robux via account · from $12.50",
            "Робуксы аккаунтом · от $12,50",
            "Robux حساب · از $12.50",
        ),
        "👤",
        "robux_account",
        "usd",
        400,
        divisor=1_000,
        minimum=1_000,
        maximum=1_000_000,
        custom_quantity=True,
        recipient_kind="roblox",
    ),
    "robux_gamepass": Product(
        "robux_gamepass",
        titles(
            "Robux via Game Pass · from $12.50",
            "Robux GamePass · от $12,50",
            "Robux از طریق Game Pass · از $12.50",
        ),
        "🎟",
        "robux_gamepass",
        "usd",
        420,
        divisor=1_000,
        minimum=1_000,
        maximum=1_000_000,
        custom_quantity=True,
        recipient_kind="roblox",
    ),
    "robux_account_45k": Product(
        "robux_account_45k",
        titles(
            "Robux via account · from 45,000 Robux",
            "Робуксы аккаунтом · от 45 000 Robux",
            "Robux حساب · از ۴۵٬۰۰۰ Robux",
        ),
        "👤",
        "robux_account",
        "usd",
        360,
        divisor=1_000,
        minimum=45_000,
        maximum=1_000_000,
        custom_quantity=True,
        recipient_kind="roblox",
    ),
    "robux_gamepass_45k": Product(
        "robux_gamepass_45k",
        titles(
            "Robux GamePass · from 45,000 Robux",
            "Robux GamePass · от 45 000 Robux",
            "Robux GamePass · از ۴۵٬۰۰۰ Robux",
        ),
        "🎟",
        "robux_gamepass",
        "usd",
        370,
        divisor=1_000,
        minimum=45_000,
        maximum=1_000_000,
        custom_quantity=True,
        recipient_kind="roblox",
    ),
    "robux_group": Product(
        "robux_group",
        titles(
            "Robux via group",
            "Robux группой",
            "Robux از طریق گروه",
        ),
        "👥",
        "robux_group",
        "usd",
        390,
        divisor=1_000,
        minimum=1_000,
        maximum=1_000_000,
        custom_quantity=True,
        recipient_kind="roblox",
    ),
    "robux_group_45k": Product(
        "robux_group_45k",
        titles(
            "Robux via group · from 45,000 Robux",
            "Robux группой · от 45 000 Robux",
            "Robux از طریق گروه · از ۴۵٬۰۰۰ Robux",
        ),
        "👥",
        "robux_group",
        "usd",
        380,
        divisor=1_000,
        minimum=45_000,
        maximum=1_000_000,
        custom_quantity=True,
        recipient_kind="roblox",
    ),
    "gift_100": Product(
        "gift_100",
        gift_titles("100"),
        "🎁",
        "roblox_gifts",
        "usd",
        104,
        maximum=100,
        custom_quantity=True,
        recipient_kind="email",
    ),
    "gift_200": Product(
        "gift_200",
        gift_titles("200"),
        "🎁",
        "roblox_gifts",
        "usd",
        208,
        maximum=100,
        custom_quantity=True,
        recipient_kind="email",
    ),
    "gift_300": Product(
        "gift_300",
        gift_titles("300"),
        "🎁",
        "roblox_gifts",
        "usd",
        313,
        maximum=100,
        custom_quantity=True,
        recipient_kind="email",
    ),
    "gift_400": Product(
        "gift_400",
        gift_titles("400"),
        "🎁",
        "roblox_gifts",
        "usd",
        417,
        maximum=100,
        custom_quantity=True,
        recipient_kind="email",
    ),
    "gift_500": Product(
        "gift_500",
        gift_titles("500"),
        "🎁",
        "roblox_gifts",
        "usd",
        469,
        maximum=100,
        custom_quantity=True,
        recipient_kind="email",
    ),
    "gift_600": Product(
        "gift_600",
        gift_titles("600"),
        "🎁",
        "roblox_gifts",
        "usd",
        560,
        maximum=100,
        custom_quantity=True,
        recipient_kind="email",
    ),
    "gift_800": Product(
        "gift_800",
        gift_titles("800"),
        "🎁",
        "roblox_gifts",
        "usd",
        690,
        maximum=100,
        custom_quantity=True,
        recipient_kind="email",
    ),
    "gift_1000": Product(
        "gift_1000",
        gift_titles("1,000"),
        "🎁",
        "roblox_gifts",
        "usd",
        820,
        maximum=100,
        custom_quantity=True,
        recipient_kind="email",
    ),
    "gift_2000": Product(
        "gift_2000",
        gift_titles("2,000"),
        "🎁",
        "roblox_gifts",
        "usd",
        1_641,
        maximum=100,
        custom_quantity=True,
        recipient_kind="email",
    ),
    "gift_5000": Product(
        "gift_5000",
        gift_titles("5,000"),
        "🎁",
        "roblox_gifts",
        "usd",
        3_906,
        maximum=100,
        custom_quantity=True,
        recipient_kind="email",
    ),
    "gift_10000": Product(
        "gift_10000",
        gift_titles("10,000"),
        "🎁",
        "roblox_gifts",
        "usd",
        7_813,
        maximum=100,
        custom_quantity=True,
        recipient_kind="email",
    ),
    "gemini": Product(
        "gemini",
        titles("Gemini 18m"),
        "🟢",
        "ai",
        "usd",
        44,
        maximum=100,
        custom_quantity=True,
        recipient_kind="email",
    ),
    "google_ai_plus_1m": Product(
        "google_ai_plus_1m",
        titles(
            "Google AI Plus • 1 month",
            "Google AI Plus • 1 месяц",
            "Google AI Plus • ۱ ماه",
        ),
        "♊",
        "ai",
        "usd",
        500,
        maximum=1_000,
        custom_quantity=True,
        recipient_kind="email",
    ),
    "google_ai_pro_1m": Product(
        "google_ai_pro_1m",
        titles(
            "Google AI Pro • 1 month",
            "Google AI Pro • 1 месяц",
            "Google AI Pro • ۱ ماه",
        ),
        "♊",
        "ai",
        "usd",
        1_000,
        maximum=1_000,
        custom_quantity=True,
        recipient_kind="email",
    ),
    "chatgpt_plus_1m": Product(
        "chatgpt_plus_1m",
        titles(
            "ChatGPT Plus • 1 month",
            "ChatGPT Plus • 1 месяц",
            "ChatGPT Plus • ۱ ماه",
        ),
        "🟢",
        "ai",
        "usd",
        1_000,
        maximum=1_000,
        custom_quantity=True,
        recipient_kind="email",
    ),
    "gpt": Product(
        "gpt",
        titles("ChatGPT NW", "ChatGPT NW", "ChatGPT NW"),
        "🟢",
        "ai",
        "usd",
        121,
        maximum=100,
        custom_quantity=True,
        recipient_kind="email",
        bulk_unit_minor=100,
        bulk_threshold_minor=5_000,
    ),
    "gpt_fw": Product(
        "gpt_fw",
        titles("ChatGPT FW", "ChatGPT FW", "ChatGPT FW"),
        "🟢",
        "ai",
        "usd",
        161,
        maximum=100,
        custom_quantity=True,
        recipient_kind="email",
        bulk_unit_minor=143,
        bulk_threshold_minor=5_000,
    ),
    "claude": Product(
        "claude",
        titles("Claude 1M"),
        "🟢",
        "ai",
        "usd",
        900,
        maximum=100,
        custom_quantity=True,
        recipient_kind="email",
    ),
    "claude_pro_1m": Product(
        "claude_pro_1m",
        titles(
            "Claude Pro • 1 month",
            "Claude Pro • 1 месяц",
            "Claude Pro • ۱ ماه",
        ),
        "🟢",
        "ai",
        "usd",
        1_000,
        maximum=1_000,
        custom_quantity=True,
        recipient_kind="email",
    ),
    "team_claude": Product(
        "team_claude",
        titles("TEAM CLAUDE"),
        "👥",
        "ai",
        "usd",
        2_300,
        maximum=100,
        custom_quantity=True,
        recipient_kind="email",
    ),
    "claude_max_5x": Product(
        "claude_max_5x",
        titles("Claude MAX 5x"),
        "⚡",
        "ai",
        "usd",
        4_900,
        maximum=100,
        custom_quantity=True,
        recipient_kind="email",
    ),
    "claude_max_20x": Product(
        "claude_max_20x",
        titles("Claude MAX 20x"),
        "🚀",
        "ai",
        "usd",
        7_900,
        maximum=100,
        custom_quantity=True,
        recipient_kind="email",
    ),
    "x_grok": Product(
        "x_grok",
        titles(
            "X Premium + Grok • 3 months",
            "X Premium + Grok • 3 месяца",
            "X Premium + Grok • ۳ ماه",
        ),
        "𝕏",
        "ai",
        "usd",
        350,
        maximum=100,
        custom_quantity=True,
        recipient_kind="email",
    ),
    "grok_1m": Product(
        "grok_1m",
        titles("Grok • 1 month", "Grok • 1 месяц", "Grok • ۱ ماه"),
        "🟢",
        "ai",
        "usd",
        100,
        maximum=10_000,
        custom_quantity=True,
        recipient_kind="email",
    ),
    "grok_1w": Product(
        "grok_1w",
        titles("Grok • 1 week", "Grok • 1 неделя", "Grok • ۱ هفته"),
        "🟢",
        "ai",
        "usd",
        40,
        maximum=10_000,
        custom_quantity=True,
        recipient_kind="email",
    ),
    "grok_5d": Product(
        "grok_5d",
        titles("Grok • 5 days", "Grok • 5 дней", "Grok • ۵ روز"),
        "🟢",
        "ai",
        "usd",
        30,
        maximum=10_000,
        custom_quantity=True,
        recipient_kind="email",
    ),
    "gmail_account": Product(
        "gmail_account",
        titles("Gmail account", "Аккаунт Gmail", "حساب Gmail"),
        "📧",
        "gmail",
        "usd",
        33,
        maximum=10_000,
        custom_quantity=True,
        recipient_kind="email",
    ),
    "exitlag_warranty_30d": Product(
        "exitlag_warranty_30d",
        titles(
            "ExitLag account · 30-day warranty",
            "Аккаунт ExitLag · гарантия 30 дней",
            "حساب ExitLag · ضمانت ۳۰ روزه",
        ),
        "⚡",
        "exitlag",
        "usd",
        253,
        maximum=10_000,
        custom_quantity=True,
        recipient_kind="email",
    ),
    "exitlag_no_warranty": Product(
        "exitlag_no_warranty",
        titles(
            "ExitLag account · no warranty",
            "Аккаунт ExitLag · без гарантии",
            "حساب ExitLag · بدون ضمانت",
        ),
        "⚡",
        "exitlag",
        "usd",
        121,
        maximum=10_000,
        custom_quantity=True,
        recipient_kind="email",
    ),
    "gta_steam_account": Product(
        "gta_steam_account",
        titles(
            "GTA V Steam account",
            "Аккаунт GTA V · Steam",
            "حساب GTA V در Steam",
        ),
        "🚘",
        "gta",
        "usd",
        600,
        maximum=1_000,
        custom_quantity=True,
        recipient_kind="email",
    ),
    "rust_steam_account": Product(
        "rust_steam_account",
        titles(
            "Rust Steam account",
            "Аккаунт Rust · Steam",
            "حساب Rust در Steam",
        ),
        "🛢",
        "rust",
        "usd",
        600,
        maximum=1_000,
        custom_quantity=True,
        recipient_kind="email",
    ),
}

CATEGORIES = {
    "stars": ["stars"],
    "brawl": ["bp", "bp_plus"],
    "pubg": ["pubg_uc"],
    "robux_account": [
        "robux",
        "robux_account_45k",
    ],
    "robux_gamepass": [
        "robux_gamepass",
        "robux_gamepass_45k",
    ],
    "robux_group": [
        "robux_group",
        "robux_group_45k",
    ],
    "ai": [
        "gemini",
        "google_ai_plus_1m",
        "google_ai_pro_1m",
        "gpt",
        "gpt_fw",
        "chatgpt_plus_1m",
        "claude",
        "claude_pro_1m",
        "team_claude",
        "claude_max_5x",
        "claude_max_20x",
        "x_grok",
        "grok_1m",
        "grok_1w",
        "grok_5d",
    ],
}

ACTIVE_PRODUCT_CODES = frozenset(
    product_code
    for product_codes in CATEGORIES.values()
    for product_code in product_codes
)

AI_SUBCATEGORIES = {
    "gemini": ["gemini", "google_ai_plus_1m", "google_ai_pro_1m"],
    "chatgpt": ["gpt", "gpt_fw", "chatgpt_plus_1m"],
    "claude": [
        "claude",
        "claude_pro_1m",
        "team_claude",
        "claude_max_5x",
        "claude_max_20x",
    ],
    "grok": ["x_grok", "grok_1m", "grok_1w", "grok_5d"],
}

AI_SUBCATEGORY_LABELS = {
    "gemini": "♊ Gemini",
    "chatgpt": "🟢 ChatGPT",
    "claude": "🟢 Claude",
    "grok": "𝕏 Grok",
}

ROBLOX_SUBCATEGORIES = {
    "account": ["robux", "robux_account_45k"],
    "gamepass": ["robux_gamepass", "robux_gamepass_45k"],
}


@dataclass(frozen=True, slots=True)
class PaymentMethod:
    code: str
    network: str
    asset: str
    wallet: str
    explorer_url: str


PAYMENT_METHODS = {
    "ton": PaymentMethod(
        "ton", "TON", "TON", TON_WALLET, "https://app.tonkeeper.com/transfer/"
    ),
    "trc20": PaymentMethod(
        "trc20",
        "TRON (TRC20)",
        "USDT",
        TRC20_WALLET,
        f"https://tronscan.org/#/address/{TRC20_WALLET}",
    ),
    "erc20": PaymentMethod(
        "erc20",
        "Ethereum (ERC20)",
        "USDT",
        ERC20_WALLET,
        f"https://etherscan.io/address/{ERC20_WALLET}",
    ),
    "sol": PaymentMethod(
        "sol",
        "Solana",
        "SOL",
        SOL_WALLET,
        f"https://solscan.io/account/{SOL_WALLET}",
    ),
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def dollars(cents: int) -> str:
    return f"${Decimal(cents) / 100:,.2f}"


def rubles(kopecks: int) -> str:
    value = Decimal(kopecks) / 100
    return f"{value:,.2f} RUB".replace(".00", "")


def format_usd_cents(cents: int | Decimal, currency: str = "usd") -> str:
    selected = currency if currency in CURRENCIES else "usd"
    rate = Decimal("1") if selected == "usd" else currency_rates()[selected]
    amount = (Decimal(cents) / 100 * rate).quantize(
        Decimal("0.01"), rounding=ROUND_UP
    )
    if selected == "usd":
        return f"${amount:,.2f}"
    rendered = f"{amount:,.2f}".replace(",", " ").replace(".", ",")
    return f"{rendered} ₽"


def usd_cents_from_display_amount(amount: Decimal, currency: str) -> int:
    selected = currency if currency in CURRENCIES else "usd"
    rate = Decimal("1") if selected == "usd" else currency_rates()[selected]
    return int(
        (amount / rate * 100).quantize(Decimal("1"), rounding=ROUND_UP)
    )


def source_minor_to_usd_cents(minor: int | Decimal, currency: str) -> int:
    if currency == "usd":
        return int(Decimal(minor).quantize(Decimal("1"), rounding=ROUND_UP))
    if currency == "rub":
        return rub_kopecks_to_usd_cents(int(minor))
    raise ValueError("Unsupported source currency")


def display_minor(minor: int, source_currency: str, display_currency: str) -> str:
    return format_usd_cents(
        source_minor_to_usd_cents(minor, source_currency), display_currency
    )


def format_price(minor: int, currency: str) -> str:
    return dollars(minor) if currency == "usd" else rubles(minor)


def format_unit_price(minor: Decimal, currency: str) -> str:
    value = minor / Decimal("100")
    precision = 2 if value == value.quantize(Decimal("0.01")) else 3
    rendered = f"{value:,.{precision}f}"
    if currency == "usd":
        return f"${rendered}"
    return f"{rendered} RUB".replace(".00", "")


def product_price(product: Product, display_currency: str = "usd") -> str:
    unit_usd_cents = source_minor_to_usd_cents(
        product.selling_unit_minor(), product.currency
    )
    unit_price = format_usd_cents(unit_usd_cents, display_currency)
    if product.bulk_unit_minor is not None:
        bulk_usd_cents = source_minor_to_usd_cents(
            Decimal(product.bulk_unit_minor)
            * (
                Decimal("1")
                + (
                    PRICE_MARKUP_PERCENT
                    + (
                        Decimal("0")
                        if product.code in PRICE_INCREASE_EXEMPT_CODES
                        else CATALOG_PRICE_INCREASE_PERCENT
                    )
                )
                / Decimal("100")
            )
            * (
                Decimal("1")
                - CATALOG_PRICE_DECREASE_PERCENT / Decimal("100")
            ),
            product.currency,
        )
        bulk_price = format_usd_cents(bulk_usd_cents, display_currency)
        threshold = display_minor(
            product.bulk_threshold_minor, product.currency, display_currency
        )
        return f"{unit_price} · ≥{threshold}: {bulk_price} / item"
    if product.code == "stars":
        return f"{unit_price} / 1,000 Stars"
    if product.code.startswith("robux"):
        return f"{unit_price} / {product.divisor:,} R$"
    if product.code == "steam":
        if display_currency == "usd":
            fee = product.selling_unit_minor() - Decimal("100")
            return f"Steam Wallet + {fee.normalize()}%"
        return f"{unit_price} / $1 Steam"
    if product.code == "pubg_uc":
        return f"{unit_price} / 1,000 UC"
    return unit_price


def minimum_quantity(product: Product) -> int:
    if product.category == "premium":
        return product.minimum
    if product.currency == "usd":
        minimum_minor = MIN_ORDER_USD_CENTS
    elif product.currency == "rub":
        minimum_minor = int(
            (Decimal(MIN_ORDER_USD_CENTS) * RUB_PER_USD).quantize(
                Decimal("1"), rounding=ROUND_UP
            )
        )
    else:
        return product.minimum
    required = int(
        (
            Decimal(minimum_minor) * product.divisor / product.selling_unit_minor()
        ).to_integral_value(rounding=ROUND_UP)
    )
    return max(product.minimum, required)


MINIAPP_CATEGORY_NAMES = {
    "stars": "Telegram Stars",
    "brawl": "Brawl Stars",
    "pubg": "PUBG",
    "robux_account": "Robux аккаунтом",
    "robux_gamepass": "Robux GamePass",
    "robux_group": "Robux группой",
    "ai": "AI-подписки",
}


def product_total_usd_cents(product: Product, quantity: int) -> int:
    total = product.total_minor(quantity)
    if product.currency == "usd":
        return total
    if product.currency == "rub":
        return rub_kopecks_to_usd_cents(total)
    raise ValueError("Unsupported product currency")


def miniapp_catalog_payload() -> dict[str, Any]:
    return {
        "shop": SHOP_NAME,
        "minimum_order_usd_cents": MIN_ORDER_USD_CENTS,
        "auto_close_minutes": ORDER_AUTO_CLOSE_MINUTES,
        "categories": MINIAPP_CATEGORY_NAMES,
        "products": [
            {
                "code": product.code,
                "title": product.titles.get("ru", product.titles["en"]),
                "title_en": product.titles["en"],
                "emoji": product.emoji,
                "category": product.category,
                "price_label": product_price(product),
                "minimum": minimum_quantity(product),
                "maximum": product.maximum,
                "divisor": product.divisor,
            }
            for code, product in PRODUCTS.items()
            if code in ACTIVE_PRODUCT_CODES
        ],
    }


def miniapp_html() -> str:
    template = r'''<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
  <meta name="theme-color" content="#06130d">
  <title>Jouli Market</title>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <style>
    :root{--bg:#06130d;--panel:#0d2117;--panel2:#123323;--green:#39e68a;--mint:#b9ffd8;--text:#f2fff7;--muted:#8db9a0;--line:#24583c}
    *{box-sizing:border-box}body{margin:0;color:var(--text);font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif;min-height:100vh;background:radial-gradient(circle at 10% 0,#17653d 0,transparent 32%),radial-gradient(circle at 100% 35%,#0c482d 0,transparent 28%),var(--bg)}
    body:before{content:'';position:fixed;inset:0;pointer-events:none;opacity:.22;background-image:radial-gradient(#70ffa9 1px,transparent 1px);background-size:22px 22px}.app{position:relative;max-width:860px;margin:auto;padding:16px 14px 110px}
    .hero{position:relative;overflow:hidden;padding:25px;border:1px solid #3d9b69;border-radius:32px;background:linear-gradient(145deg,#173c29e8,#091a12f4);box-shadow:0 24px 80px #0008,inset 0 1px #caffdc35}.hero:after{content:'';position:absolute;width:250px;height:250px;border-radius:50%;right:-95px;top:-120px;background:#39e68a22;box-shadow:0 0 80px #39e68a66}
    .brand{display:flex;align-items:center;gap:15px}.logo{width:58px;height:58px;border-radius:19px;background:linear-gradient(145deg,#66f6a6,#16a75e);color:#052515;display:grid;place-items:center;font:900 30px Georgia,serif;box-shadow:0 10px 30px #28d77655}.brand h1{font:800 25px Georgia,serif;margin:0;color:#fff;letter-spacing:.3px}.brand p{margin:5px 0 0;color:var(--green);font-size:12px;font-weight:800;letter-spacing:2px}
    .badges{display:flex;gap:8px;flex-wrap:wrap;margin-top:19px}.badge{padding:8px 11px;border-radius:999px;background:#153624;border:1px solid #367a54;color:#caffdc;font-size:11px;font-weight:700}
    .promobox{display:grid;grid-template-columns:1fr auto;gap:8px;margin:14px 0 3px}.promobox input{min-width:0}.promoaction{border:0;border-radius:16px;padding:0 17px;background:linear-gradient(135deg,#47ed92,#20ba69);color:#032414;font-weight:900;box-shadow:0 8px 25px #25d87844}
    .tools{position:sticky;top:0;z-index:4;padding:12px 0 8px;background:linear-gradient(#06130df5 78%,transparent)}input{width:100%;border:1px solid var(--line);background:#0c2116e8;color:#effff5;border-radius:17px;padding:13px 14px;outline:none;font:600 14px Inter,system-ui,sans-serif}input:focus{border-color:var(--green);box-shadow:0 0 0 3px #39e68a1f}.categorybar{display:flex;gap:7px;overflow-x:auto;padding:9px 0 4px;scrollbar-width:none}.categorybar::-webkit-scrollbar{display:none}.catbtn{flex:0 0 auto;border:1px solid #285c40;border-radius:999px;background:#0c2116;color:#a9d7bd;padding:9px 13px;font-weight:750;white-space:nowrap}.catbtn.active{color:#042616;background:var(--green);border-color:var(--green);box-shadow:0 6px 20px #39e68a3d}
    .grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:11px}.card{background:linear-gradient(150deg,#143624e8,#0b2015f5);border:1px solid #285d40;border-radius:25px;padding:15px;box-shadow:0 14px 38px #0007;display:flex;flex-direction:column;min-height:230px}.cardtop{display:flex;align-items:center;justify-content:space-between}.icon{width:48px;height:48px;border-radius:16px;display:grid;place-items:center;background:#1b4c32;border:1px solid #3b8059;font-size:25px}.route{font-size:10px;color:#8effb9;border:1px solid #34774f;border-radius:999px;padding:6px 9px;background:#102d1e}.title{font-weight:800;margin:11px 0 5px;line-height:1.2}.price{font-size:13px;color:var(--green);min-height:34px}.qtyrow{display:grid;grid-template-columns:38px 76px 38px 1fr;align-items:center;gap:6px;margin-top:auto}.qtyrow input{padding:9px 3px;width:76px;text-align:center;border-radius:12px}.step{height:38px;border:1px solid #387754;border-radius:12px;background:#173a27;color:#a9ffca;font-size:20px}.sum{font-weight:850;color:#d8ffe7;text-align:right;font-size:13px}.buy{border:0;border-radius:16px;padding:12px;margin-top:11px;color:#052515;font-weight:900;background:linear-gradient(135deg,#56f2a0,#24c875);box-shadow:0 9px 24px #2bdd7f35;cursor:pointer}.buy:active,.step:active,.catbtn:active{transform:scale(.97)}
    .empty{text-align:center;color:var(--muted);padding:45px 10px}.foot{position:fixed;bottom:0;left:0;right:0;padding:12px 16px 18px;background:linear-gradient(transparent,#06130d 28%);pointer-events:none}.foot div{max-width:700px;margin:auto;background:#0d281b;border:1px solid #2e6848;border-radius:18px;padding:10px;text-align:center;color:#91c5a7;font-size:11px;box-shadow:0 12px 34px #000b}
    @media(max-width:560px){.grid{grid-template-columns:1fr}.card{min-height:210px}}
  </style>
</head>
<body>
<main class="app">
  <section class="hero">
    <div class="brand"><div class="logo">J</div><div><h1>Jouli Market</h1><p>DIGITAL GARDEN</p></div></div>
    <div class="badges"><span class="badge" id="count">Загрузка…</span><span class="badge">ЗАКАЗ ОТ $10</span><span class="badge">ОПТ −15%</span><span class="badge">БРОНЬ 60 МИН</span></div>
  </section>
  <section class="promobox"><input id="promo" placeholder="ВВЕДИТЕ ПРОМОКОД"><button class="promoaction" id="promoactivate">АКТИВИРОВАТЬ</button></section>
  <section class="tools"><input id="search" placeholder="Найти товар в Jouli Market"><div class="categorybar" id="categories"></div></section>
  <section class="grid" id="grid"></section>
</main>
<div class="foot"><div>Заказ оформляется в @__BOT_USERNAME__ · неоплаченный заказ отменяется через 60 минут</div></div>
<script>
  const tg=window.Telegram?.WebApp; if(tg){tg.ready();tg.expand();tg.setHeaderColor('#0d2117');tg.setBackgroundColor('#06130d')}
  let catalog={products:[],categories:{}}; let selectedCat='all'; const quotes=new Map();
  const esc=s=>String(s).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const money=c=>'$'+(Number(c)/100).toFixed(2);
  async function quote(code,quantity){const key=code+':'+quantity;if(quotes.has(key))return quotes.get(key);const r=await fetch('/api/quote?code='+encodeURIComponent(code)+'&quantity='+quantity);const q=await r.json();if(!r.ok)throw new Error(q.error||'quote');quotes.set(key,q);return q}
  function options(){const bar=document.querySelector('#categories');const entries=[['all','Все'],...Object.entries(catalog.categories)];bar.innerHTML=entries.map(([code,name])=>`<button class="catbtn${code===selectedCat?' active':''}" data-cat="${esc(code)}">${esc(name)}</button>`).join('');bar.querySelectorAll('[data-cat]').forEach(btn=>btn.addEventListener('click',()=>{selectedCat=btn.dataset.cat;options();render()}))}
  function render(){const term=document.querySelector('#search').value.trim().toLowerCase();const list=catalog.products.filter(p=>(selectedCat==='all'||p.category===selectedCat)&&(!term||(p.title+' '+p.title_en+' '+p.code).toLowerCase().includes(term)));const grid=document.querySelector('#grid');if(!list.length){grid.innerHTML='<div class="empty">Товары не найдены</div>';return}grid.innerHTML=list.map(p=>`<article class="card"><div class="cardtop"><div class="icon">${esc(p.emoji)}</div><span class="route">${esc(catalog.categories[p.category]||'Товар')}</span></div><div class="title">${esc(p.title)}</div><div class="price">${esc(p.price_label)}</div><div class="qtyrow"><button class="step" data-step="-1" data-code="${esc(p.code)}">−</button><input class="qty" data-code="${esc(p.code)}" type="number" min="${p.minimum}" max="${p.maximum}" value="${p.minimum}"><button class="step" data-step="1" data-code="${esc(p.code)}">+</button><span class="sum" id="sum-${esc(p.code)}">…</span></div><button class="buy" data-buy="${esc(p.code)}">Купить</button></article>`).join('');grid.querySelectorAll('.qty').forEach(input=>{input.addEventListener('change',()=>refresh(input.dataset.code));refresh(input.dataset.code)});grid.querySelectorAll('[data-step]').forEach(btn=>btn.addEventListener('click',()=>stepQty(btn.dataset.code,Number(btn.dataset.step))));grid.querySelectorAll('[data-buy]').forEach(btn=>btn.addEventListener('click',()=>buy(btn.dataset.buy)))}
  function stepQty(code,direction){const p=catalog.products.find(x=>x.code===code);const input=document.querySelector(`.qty[data-code="${code}"]`);const increment=Math.max(1,p.divisor||1);input.value=Math.max(p.minimum,Math.min(p.maximum,(Number(input.value)||p.minimum)+direction*increment));refresh(code)}
  async function refresh(code){const p=catalog.products.find(x=>x.code===code);const input=document.querySelector(`.qty[data-code="${code}"]`);let qty=Math.trunc(Number(input.value)||p.minimum);qty=Math.max(p.minimum,Math.min(p.maximum,qty));input.value=qty;try{const q=await quote(code,qty);document.querySelector('#sum-'+code).textContent=money(q.total_usd_cents)}catch{document.querySelector('#sum-'+code).textContent='—'}}
  async function buy(code){const p=catalog.products.find(x=>x.code===code);const input=document.querySelector(`.qty[data-code="${code}"]`);const qty=Math.trunc(Number(input.value)||0);if(qty<p.minimum||qty>p.maximum){tg?.showAlert('Проверьте количество');return}const q=await quote(code,qty);if(p.category!=='premium'&&q.total_usd_cents<catalog.minimum_order_usd_cents){tg?.showAlert('Минимальный заказ — '+money(catalog.minimum_order_usd_cents));return}const url='https://t.me/__BOT_USERNAME__?start=buy_'+code+'_'+qty;if(tg){tg.openTelegramLink(url)}else{location.href=url}}
  function activatePromo(){const code=document.querySelector('#promo').value.toUpperCase().replace(/[^A-Z0-9]/g,'');if(!code){tg?.showAlert('Введите промокод');return}const url='https://t.me/__BOT_USERNAME__?start=promo_'+code;if(tg){tg.openTelegramLink(url)}else{location.href=url}}
  fetch('/api/catalog').then(r=>r.json()).then(data=>{catalog=data;document.querySelector('#count').textContent=data.products.length+' товаров';options();render()}).catch(()=>document.querySelector('#grid').innerHTML='<div class="empty">Не удалось загрузить каталог</div>');
  document.querySelector('#search').addEventListener('input',render);
  document.querySelector('#promoactivate').addEventListener('click',activatePromo);
</script>
</body></html>'''
    return template.replace("__BOT_USERNAME__", BOT_USERNAME.lstrip("@"))


class MiniAppHandler(BaseHTTPRequestHandler):
    server_version = "JouliMarket/1.0"

    def send_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status: int, payload: Any) -> None:
        self.send_bytes(
            status,
            json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            self.send_bytes(
                200, miniapp_html().encode("utf-8"), "text/html; charset=utf-8"
            )
            return
        if parsed.path == "/healthz":
            self.send_json(200, {"status": "ok"})
            return
        if parsed.path == "/api/catalog":
            self.send_json(200, miniapp_catalog_payload())
            return
        if parsed.path == "/api/quote":
            query = parse_qs(parsed.query)
            code = str(query.get("code", [""])[0])
            product = PRODUCTS.get(code) if code in ACTIVE_PRODUCT_CODES else None
            try:
                quantity = int(query.get("quantity", ["0"])[0])
            except (TypeError, ValueError):
                quantity = 0
            if (
                not product
                or quantity < minimum_quantity(product)
                or quantity > product.maximum
            ):
                self.send_json(400, {"error": "invalid product or quantity"})
                return
            self.send_json(
                200,
                {
                    "code": code,
                    "quantity": quantity,
                    "total_usd_cents": product_total_usd_cents(product, quantity),
                },
            )
            return
        self.send_json(404, {"error": "not found"})

    def log_message(self, format: str, *args: Any) -> None:
        LOGGER.debug("Mini App: " + format, *args)


def miniapp_server_worker() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", WEBAPP_PORT), MiniAppHandler)
    LOGGER.info("Mini App server listening on port %s", WEBAPP_PORT)
    server.serve_forever()


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.lock = threading.RLock()
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=20)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 20000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def add_column(
        db: sqlite3.Connection, table: str, column: str, definition: str
    ) -> None:
        columns = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def initialize(self) -> None:
        with self.lock, self.connect() as db:
            db.execute("PRAGMA journal_mode = WAL")
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT NOT NULL DEFAULT '',
                    balance_usd_cents INTEGER NOT NULL DEFAULT 0,
                    discount_percent INTEGER NOT NULL DEFAULT 0,
                    referral_discount_percent INTEGER NOT NULL DEFAULT 0,
                    giveaway_discount_uses INTEGER NOT NULL DEFAULT 0,
                    promo_code TEXT,
                    promo_discount_percent INTEGER NOT NULL DEFAULT 0,
                    referrer_id INTEGER,
                    language TEXT,
                    currency TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(user_id),
                    product_code TEXT NOT NULL,
                    product_title TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    total_kopecks INTEGER NOT NULL,
                    discount_percent INTEGER NOT NULL DEFAULT 0,
                    wholesale_discount_percent INTEGER NOT NULL DEFAULT 0,
                    promo_code TEXT,
                    promo_discount_percent INTEGER NOT NULL DEFAULT 0,
                    price_currency TEXT NOT NULL DEFAULT 'rub',
                    recipient TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'awaiting_payment',
                    ton_amount_nano INTEGER,
                    payment_method TEXT,
                    payment_amount_text TEXT,
                    payment_comment TEXT UNIQUE,
                    tx_hash TEXT UNIQUE,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS topups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(user_id),
                    amount_usd_cents INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'awaiting_payment',
                    ton_amount_nano INTEGER,
                    payment_method TEXT,
                    payment_amount_text TEXT,
                    payment_comment TEXT UNIQUE,
                    tx_hash TEXT UNIQUE,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS states (
                    user_id INTEGER PRIMARY KEY REFERENCES users(user_id),
                    state TEXT NOT NULL,
                    data_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS giveaways (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    winner_user_id INTEGER REFERENCES users(user_id),
                    discount_percent INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS promo_redemptions (
                    user_id INTEGER NOT NULL REFERENCES users(user_id),
                    promo_code TEXT NOT NULL,
                    discount_percent INTEGER NOT NULL,
                    activated_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, promo_code)
                );
                CREATE TABLE IF NOT EXISTS giveaway_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    next_run_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS suggestions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(user_id),
                    body TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'new',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS nft_buyback_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(user_id),
                    details TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'new',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS star_payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(user_id),
                    kind TEXT NOT NULL CHECK (kind IN ('order', 'topup')),
                    item_id INTEGER NOT NULL,
                    usd_cents INTEGER NOT NULL,
                    stars INTEGER NOT NULL,
                    payload TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT 'pending',
                    telegram_charge_id TEXT UNIQUE,
                    provider_charge_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS monitored_leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    user_id INTEGER,
                    username TEXT,
                    intent TEXT NOT NULL,
                    product_codes TEXT NOT NULL,
                    body TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(chat_id, message_id)
                );
                CREATE TABLE IF NOT EXISTS balance_adjustments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_user_id INTEGER NOT NULL,
                    target_user_id INTEGER NOT NULL REFERENCES users(user_id),
                    amount_usd_cents INTEGER NOT NULL CHECK(amount_usd_cents > 0),
                    balance_after_usd_cents INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id, id DESC);
                CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status, id DESC);
                CREATE INDEX IF NOT EXISTS idx_topups_status ON topups(status, id DESC);
                CREATE INDEX IF NOT EXISTS idx_suggestions_status
                    ON suggestions(status, id DESC);
                CREATE INDEX IF NOT EXISTS idx_nft_buyback_status
                    ON nft_buyback_requests(status, id DESC);
                CREATE INDEX IF NOT EXISTS idx_star_payments_payload
                    ON star_payments(payload, status);
                CREATE INDEX IF NOT EXISTS idx_monitored_leads_created
                    ON monitored_leads(id DESC);
                CREATE INDEX IF NOT EXISTS idx_balance_adjustments_target
                    ON balance_adjustments(target_user_id, id DESC);
                CREATE INDEX IF NOT EXISTS idx_promo_redemptions_code
                    ON promo_redemptions(promo_code);
                """
            )
            self.add_column(db, "users", "language", "TEXT")
            self.add_column(db, "users", "currency", "TEXT")
            self.add_column(
                db,
                "users",
                "giveaway_discount_uses",
                "INTEGER NOT NULL DEFAULT 0",
            )
            self.add_column(
                db,
                "users",
                "referral_discount_percent",
                "INTEGER NOT NULL DEFAULT 0",
            )
            self.add_column(db, "users", "promo_code", "TEXT")
            self.add_column(
                db,
                "users",
                "promo_discount_percent",
                "INTEGER NOT NULL DEFAULT 0",
            )
            self.add_column(
                db, "orders", "price_currency", "TEXT NOT NULL DEFAULT 'rub'"
            )
            self.add_column(
                db,
                "orders",
                "discount_percent",
                "INTEGER NOT NULL DEFAULT 0",
            )
            self.add_column(
                db,
                "orders",
                "wholesale_discount_percent",
                "INTEGER NOT NULL DEFAULT 0",
            )
            self.add_column(db, "orders", "promo_code", "TEXT")
            self.add_column(
                db,
                "orders",
                "promo_discount_percent",
                "INTEGER NOT NULL DEFAULT 0",
            )
            self.add_column(db, "orders", "payment_method", "TEXT")
            self.add_column(db, "orders", "payment_amount_text", "TEXT")
            self.add_column(db, "topups", "payment_method", "TEXT")
            self.add_column(db, "topups", "payment_amount_text", "TEXT")
            first_draw = datetime.now(timezone.utc) + timedelta(
                hours=GIVEAWAY_INTERVAL_HOURS
            )
            db.execute(
                "INSERT OR IGNORE INTO giveaway_state (id, next_run_at) VALUES (1, ?)",
                (first_draw.isoformat(timespec="seconds"),),
            )
            db.execute(
                "UPDATE topups SET status = 'rejected', updated_at = ? "
                "WHERE status = 'awaiting_payment' AND amount_usd_cents < ?",
                (now_iso(), minimum_topup_cents()),
            )
            db.execute(
                "UPDATE users SET referral_discount_percent = MIN(?, "
                "(SELECT COUNT(*) * ? FROM users AS referred "
                "WHERE referred.referrer_id = users.user_id))",
                (MAX_TOTAL_DISCOUNT_PERCENT, REFERRAL_DISCOUNT_PERCENT),
            )

    def ensure_user(self, user: types.User, referrer_id: int | None = None) -> bool:
        now = now_iso()
        with self.lock, self.connect() as db:
            row = db.execute(
                "SELECT 1 FROM users WHERE user_id = ?", (user.id,)
            ).fetchone()
            if row:
                db.execute(
                    "UPDATE users SET username = ?, first_name = ?, updated_at = ? WHERE user_id = ?",
                    (user.username, user.first_name or "", now, user.id),
                )
                return False
            valid_referrer = None
            if referrer_id and referrer_id != user.id:
                exists = db.execute(
                    "SELECT 1 FROM users WHERE user_id = ?", (referrer_id,)
                ).fetchone()
                valid_referrer = referrer_id if exists else None
            db.execute(
                """INSERT INTO users
                   (user_id, username, first_name, referrer_id, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    user.id,
                    user.username,
                    user.first_name or "",
                    valid_referrer,
                    now,
                    now,
                ),
            )
            if valid_referrer:
                db.execute(
                    "UPDATE users SET referral_discount_percent = "
                    "MIN(?, referral_discount_percent + ?), updated_at = ? "
                    "WHERE user_id = ?",
                    (
                        MAX_TOTAL_DISCOUNT_PERCENT,
                        REFERRAL_DISCOUNT_PERCENT,
                        now,
                        valid_referrer,
                    ),
                )
            return True

    def user(self, user_id: int) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
        return dict(row) if row else None

    def language(self, user_id: int) -> str | None:
        user = self.user(user_id)
        value = str(user.get("language") or "") if user else ""
        return value if value in LANGUAGES else None

    def set_language(self, user_id: int, language: str) -> None:
        if language not in LANGUAGES:
            raise ValueError("Unsupported language")
        with self.lock, self.connect() as db:
            db.execute(
                "UPDATE users SET language = ?, updated_at = ? WHERE user_id = ?",
                (language, now_iso(), user_id),
            )

    def currency(self, user_id: int) -> str | None:
        user = self.user(user_id)
        value = str(user.get("currency") or "") if user else ""
        return value if value in CURRENCIES else None

    def set_currency(self, user_id: int, currency: str) -> None:
        if currency not in CURRENCIES:
            raise ValueError("Unsupported currency")
        with self.lock, self.connect() as db:
            db.execute(
                "UPDATE users SET currency = ?, updated_at = ? WHERE user_id = ?",
                (currency, now_iso(), user_id),
            )

    def referrals(self, user_id: int) -> int:
        with self.connect() as db:
            return int(
                db.execute(
                    "SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,)
                ).fetchone()[0]
            )

    def user_ids_for_usernames(self, usernames: set[str]) -> set[int]:
        normalized = {
            username.lstrip("@").casefold() for username in usernames if username
        }
        if not normalized:
            return set()
        placeholders = ",".join("?" for _ in normalized)
        with self.connect() as db:
            rows = db.execute(
                f"SELECT user_id FROM users WHERE lower(username) IN ({placeholders})",
                tuple(sorted(normalized)),
            ).fetchall()
        return {int(row["user_id"]) for row in rows}

    @staticmethod
    def effective_discount(user: dict[str, Any] | None) -> int:
        if not user:
            return 0
        manual = max(0, int(user.get("discount_percent") or 0))
        referral = max(0, int(user.get("referral_discount_percent") or 0))
        promo = max(0, int(user.get("promo_discount_percent") or 0))
        return max(
            min(MAX_TOTAL_DISCOUNT_PERCENT, manual + referral),
            min(MAX_TOTAL_DISCOUNT_PERCENT, promo),
        )

    def activate_promo(
        self, user_id: int, raw_code: str
    ) -> tuple[str, int, str]:
        code = normalize_promo_code(raw_code)
        percent = PROMO_CODES.get(code)
        if percent is None:
            return "invalid", 0, code
        now = now_iso()
        with self.lock, self.connect() as db:
            user = db.execute(
                "SELECT promo_code FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            if not user:
                return "invalid", 0, code
            active_code = str(user["promo_code"] or "")
            if active_code:
                active_percent = PROMO_CODES.get(active_code, 0)
                return "active", active_percent, active_code
            used = db.execute(
                "SELECT 1 FROM promo_redemptions "
                "WHERE user_id = ? AND promo_code = ?",
                (user_id, code),
            ).fetchone()
            if used:
                return "used", percent, code
            db.execute(
                "INSERT INTO promo_redemptions "
                "(user_id, promo_code, discount_percent, activated_at) "
                "VALUES (?, ?, ?, ?)",
                (user_id, code, percent, now),
            )
            db.execute(
                "UPDATE users SET promo_code = ?, promo_discount_percent = ?, "
                "updated_at = ? WHERE user_id = ?",
                (code, percent, now, user_id),
            )
        return "activated", percent, code

    def add_suggestion(self, user_id: int, body: str) -> int:
        now = now_iso()
        with self.lock, self.connect() as db:
            cursor = db.execute(
                "INSERT INTO suggestions "
                "(user_id, body, status, created_at, updated_at) "
                "VALUES (?, ?, 'new', ?, ?)",
                (user_id, body, now, now),
            )
            return int(cursor.lastrowid)

    def review_suggestions(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                """SELECT s.*, u.username, u.first_name
                   FROM suggestions s JOIN users u ON u.user_id = s.user_id
                   WHERE s.status = 'new' ORDER BY s.id DESC LIMIT 20"""
            ).fetchall()
        return [dict(row) for row in rows]

    def resolve_suggestion(self, suggestion_id: int, status: str) -> bool:
        if status not in {"planned", "dismissed"}:
            raise ValueError("Invalid suggestion status")
        with self.lock, self.connect() as db:
            cursor = db.execute(
                "UPDATE suggestions SET status = ?, updated_at = ? "
                "WHERE id = ? AND status = 'new'",
                (status, now_iso(), suggestion_id),
            )
            return cursor.rowcount == 1

    def add_nft_buyback(self, user_id: int, details: str) -> int:
        now = now_iso()
        with self.lock, self.connect() as db:
            cursor = db.execute(
                "INSERT INTO nft_buyback_requests "
                "(user_id, details, status, created_at, updated_at) "
                "VALUES (?, ?, 'new', ?, ?)",
                (user_id, details, now, now),
            )
            return int(cursor.lastrowid)

    def review_nft_buybacks(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                """SELECT n.*, u.username, u.first_name
                   FROM nft_buyback_requests n
                   JOIN users u ON u.user_id = n.user_id
                   WHERE n.status = 'new' ORDER BY n.id DESC LIMIT 20"""
            ).fetchall()
        return [dict(row) for row in rows]

    def resolve_nft_buyback(
        self, request_id: int, status: str
    ) -> dict[str, Any] | None:
        if status not in {"contacted", "closed"}:
            raise ValueError("Invalid NFT request status")
        with self.lock, self.connect() as db:
            cursor = db.execute(
                "UPDATE nft_buyback_requests SET status = ?, updated_at = ? "
                "WHERE id = ? AND status = 'new'",
                (status, now_iso(), request_id),
            )
            if cursor.rowcount != 1:
                return None
            row = db.execute(
                "SELECT * FROM nft_buyback_requests WHERE id = ?", (request_id,)
            ).fetchone()
        return dict(row) if row else None

    def create_star_payment(
        self,
        kind: str,
        item_id: int,
        user_id: int,
        usd_cents: int,
        stars: int,
    ) -> str | None:
        if kind not in {"order", "topup"} or usd_cents <= 0 or stars <= 0:
            raise ValueError("Invalid Stars payment")
        table = "orders" if kind == "order" else "topups"
        payload = f"nxs:{kind[0]}:{item_id}:{secrets.token_urlsafe(12)}"
        now = now_iso()
        with self.lock, self.connect() as db:
            target = db.execute(
                f"SELECT status, user_id FROM {table} WHERE id = ?", (item_id,)
            ).fetchone()
            if (
                not target
                or int(target["user_id"]) != user_id
                or str(target["status"]) != "awaiting_payment"
            ):
                return None
            db.execute(
                "INSERT INTO star_payments "
                "(user_id, kind, item_id, usd_cents, stars, payload, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, kind, item_id, usd_cents, stars, payload, now, now),
            )
            db.execute(
                f"UPDATE {table} SET payment_method = 'telegram_stars', "
                "payment_amount_text = ?, payment_comment = ?, updated_at = ? "
                "WHERE id = ? AND status = 'awaiting_payment'",
                (f"{stars} XTR", payload, now, item_id),
            )
        return payload

    def valid_star_checkout(self, payload: str, user_id: int, stars: int) -> bool:
        with self.connect() as db:
            payment = db.execute(
                "SELECT * FROM star_payments WHERE payload = ?", (payload,)
            ).fetchone()
            if (
                not payment
                or int(payment["user_id"]) != user_id
                or int(payment["stars"]) != stars
                or str(payment["status"]) != "pending"
            ):
                return False
            table = "orders" if payment["kind"] == "order" else "topups"
            target = db.execute(
                f"SELECT status, user_id, payment_comment FROM {table} WHERE id = ?",
                (int(payment["item_id"]),),
            ).fetchone()
        return bool(
            target
            and int(target["user_id"]) == user_id
            and str(target["status"]) == "awaiting_payment"
            and str(target["payment_comment"] or "") == payload
        )

    def complete_star_payment(
        self,
        payload: str,
        user_id: int,
        stars: int,
        telegram_charge_id: str,
        provider_charge_id: str,
    ) -> dict[str, Any]:
        now = now_iso()
        with self.lock, self.connect() as db:
            payment = db.execute(
                "SELECT * FROM star_payments WHERE payload = ?", (payload,)
            ).fetchone()
            if (
                not payment
                or int(payment["user_id"]) != user_id
                or int(payment["stars"]) != stars
            ):
                return {"outcome": "refund_required"}
            if str(payment["status"]) == "paid":
                outcome = (
                    "duplicate"
                    if str(payment["telegram_charge_id"] or "") == telegram_charge_id
                    else "refund_required"
                )
                return {"outcome": outcome, **dict(payment)}
            if str(payment["status"]) != "pending":
                return {"outcome": "refund_required", **dict(payment)}
            kind = str(payment["kind"])
            table = "orders" if kind == "order" else "topups"
            target = db.execute(
                f"SELECT * FROM {table} WHERE id = ?", (int(payment["item_id"]),)
            ).fetchone()
            target_ready = bool(
                target
                and int(target["user_id"]) == user_id
                and str(target["status"]) == "awaiting_payment"
                and str(target["payment_comment"] or "") == payload
            )
            if not target_ready:
                db.execute(
                    "UPDATE star_payments SET status = 'refund_required', "
                    "telegram_charge_id = ?, provider_charge_id = ?, updated_at = ? "
                    "WHERE id = ? AND status = 'pending'",
                    (telegram_charge_id, provider_charge_id, now, int(payment["id"])),
                )
                return {"outcome": "refund_required", **dict(payment)}

            if kind == "order":
                cursor = db.execute(
                    "UPDATE orders SET status = 'paid', updated_at = ? "
                    "WHERE id = ? AND status = 'awaiting_payment' "
                    "AND payment_comment = ?",
                    (now, int(payment["item_id"]), payload),
                )
            else:
                cursor = db.execute(
                    "UPDATE topups SET status = 'credited', updated_at = ? "
                    "WHERE id = ? AND status = 'awaiting_payment' "
                    "AND payment_comment = ?",
                    (now, int(payment["item_id"]), payload),
                )
                if cursor.rowcount == 1:
                    db.execute(
                        "UPDATE users SET balance_usd_cents = balance_usd_cents + ?, "
                        "updated_at = ? WHERE user_id = ?",
                        (int(payment["usd_cents"]), now, user_id),
                    )
            if cursor.rowcount != 1:
                db.execute(
                    "UPDATE star_payments SET status = 'refund_required', "
                    "telegram_charge_id = ?, provider_charge_id = ?, updated_at = ? "
                    "WHERE id = ? AND status = 'pending'",
                    (telegram_charge_id, provider_charge_id, now, int(payment["id"])),
                )
                return {"outcome": "refund_required", **dict(payment)}
            db.execute(
                "UPDATE star_payments SET status = 'paid', telegram_charge_id = ?, "
                "provider_charge_id = ?, updated_at = ? WHERE id = ?",
                (telegram_charge_id, provider_charge_id, now, int(payment["id"])),
            )
        return {"outcome": "paid", **dict(payment)}

    def mark_star_refunded(self, telegram_charge_id: str) -> None:
        with self.lock, self.connect() as db:
            db.execute(
                "UPDATE star_payments SET status = 'refunded', updated_at = ? "
                "WHERE telegram_charge_id = ? AND status = 'refund_required'",
                (now_iso(), telegram_charge_id),
            )

    def add_monitored_lead(
        self,
        *,
        chat_id: int,
        message_id: int,
        user_id: int | None,
        username: str | None,
        intent: str,
        product_codes: list[str],
        body: str,
    ) -> int | None:
        with self.lock, self.connect() as db:
            cursor = db.execute(
                "INSERT OR IGNORE INTO monitored_leads "
                "(chat_id, message_id, user_id, username, intent, product_codes, body, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    chat_id,
                    message_id,
                    user_id,
                    username,
                    intent,
                    json.dumps(product_codes, ensure_ascii=False),
                    body,
                    now_iso(),
                ),
            )
            return int(cursor.lastrowid) if cursor.rowcount == 1 else None

    def recent_monitored_leads(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM monitored_leads ORDER BY id DESC LIMIT 20"
            ).fetchall()
        return [dict(row) for row in rows]

    def recent_users(self, limit: int = 20) -> list[dict[str, Any]]:
        safe_limit = max(1, min(50, int(limit)))
        with self.connect() as db:
            rows = db.execute(
                """SELECT u.user_id, u.username, u.first_name,
                          u.balance_usd_cents, u.discount_percent,
                          u.referral_discount_percent, u.created_at,
                          COUNT(o.id) AS orders_count
                   FROM users u
                   LEFT JOIN orders o ON o.user_id = u.user_id
                   GROUP BY u.user_id
                   ORDER BY u.updated_at DESC
                   LIMIT ?""",
                (safe_limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def admin_credit_balance(
        self, admin_user_id: int, target_user_id: int, cents: int
    ) -> dict[str, Any] | None:
        if not 1 <= cents <= MAX_TOPUP_CENTS:
            raise ValueError("Invalid admin balance adjustment")
        now = now_iso()
        with self.lock, self.connect() as db:
            cursor = db.execute(
                "UPDATE users SET balance_usd_cents = balance_usd_cents + ?, "
                "updated_at = ? WHERE user_id = ?",
                (cents, now, target_user_id),
            )
            if cursor.rowcount != 1:
                return None
            row = db.execute(
                "SELECT * FROM users WHERE user_id = ?", (target_user_id,)
            ).fetchone()
            if not row:
                return None
            db.execute(
                "INSERT INTO balance_adjustments "
                "(admin_user_id, target_user_id, amount_usd_cents, "
                "balance_after_usd_cents, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    admin_user_id,
                    target_user_id,
                    cents,
                    int(row["balance_usd_cents"]),
                    now,
                ),
            )
        return dict(row)

    def admin_stats(self) -> dict[str, int]:
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(
            timespec="seconds"
        )
        with self.connect() as db:
            stats = {
                "users": int(db.execute("SELECT COUNT(*) FROM users").fetchone()[0]),
                "users_24h": int(
                    db.execute(
                        "SELECT COUNT(*) FROM users WHERE created_at >= ?", (since,)
                    ).fetchone()[0]
                ),
                "orders": int(db.execute("SELECT COUNT(*) FROM orders").fetchone()[0]),
                "orders_24h": int(
                    db.execute(
                        "SELECT COUNT(*) FROM orders WHERE created_at >= ?", (since,)
                    ).fetchone()[0]
                ),
                "topups_review": int(
                    db.execute(
                        "SELECT COUNT(*) FROM topups WHERE status = 'payment_review' "
                        "OR (status = 'awaiting_payment' AND payment_method LIKE 'card_%')"
                    ).fetchone()[0]
                ),
                "suggestions_new": int(
                    db.execute(
                        "SELECT COUNT(*) FROM suggestions WHERE status = 'new'"
                    ).fetchone()[0]
                ),
                "nft_buybacks_new": int(
                    db.execute(
                        "SELECT COUNT(*) FROM nft_buyback_requests WHERE status = 'new'"
                    ).fetchone()[0]
                ),
                "leads": int(
                    db.execute("SELECT COUNT(*) FROM monitored_leads").fetchone()[0]
                ),
                "sales_usd_cents": int(
                    db.execute(
                        "SELECT COALESCE(SUM(total_kopecks), 0) FROM orders "
                        "WHERE status = 'completed' AND price_currency = 'usd'"
                    ).fetchone()[0]
                ),
                "user_balance_usd_cents": int(
                    db.execute(
                        "SELECT COALESCE(SUM(balance_usd_cents), 0) FROM users"
                    ).fetchone()[0]
                ),
            }
            for status in (
                "awaiting_payment",
                "payment_review",
                "paid",
                "processing",
                "completed",
                "cancelled",
            ):
                stats[status] = int(
                    db.execute(
                        "SELECT COUNT(*) FROM orders WHERE status = ?", (status,)
                    ).fetchone()[0]
                )
        return stats

    def giveaway_info(self, user_id: int) -> tuple[datetime, int]:
        with self.connect() as db:
            row = db.execute(
                "SELECT next_run_at FROM giveaway_state WHERE id = 1"
            ).fetchone()
            user = db.execute(
                "SELECT giveaway_discount_uses FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        next_run = datetime.fromisoformat(str(row["next_run_at"]))
        uses = int(user["giveaway_discount_uses"]) if user else 0
        return next_run, uses

    def run_giveaway_if_due(self) -> int | None:
        now = datetime.now(timezone.utc)
        next_run = now + timedelta(hours=GIVEAWAY_INTERVAL_HOURS)
        excluded_admins = set(ADMIN_IDS) | self.user_ids_for_usernames(
            ADMIN_USERNAMES
        )
        with self.lock, self.connect() as db:
            state = db.execute(
                "SELECT next_run_at FROM giveaway_state WHERE id = 1"
            ).fetchone()
            if state and datetime.fromisoformat(str(state["next_run_at"])) > now:
                return None
            placeholders = ",".join("?" for _ in excluded_admins)
            query = "SELECT user_id FROM users WHERE language IS NOT NULL"
            params: tuple[int, ...] = tuple(excluded_admins)
            if params:
                query += f" AND user_id NOT IN ({placeholders})"
            candidates = [
                int(row["user_id"]) for row in db.execute(query, params).fetchall()
            ]
            winner_id = secrets.choice(candidates) if candidates else None
            if winner_id is not None:
                db.execute(
                    "UPDATE users SET giveaway_discount_uses = "
                    "giveaway_discount_uses + 1, updated_at = ? WHERE user_id = ?",
                    (now_iso(), winner_id),
                )
                db.execute(
                    "INSERT INTO giveaways "
                    "(winner_user_id, discount_percent, created_at) VALUES (?, ?, ?)",
                    (winner_id, GIVEAWAY_DISCOUNT_PERCENT, now_iso()),
                )
            db.execute(
                "UPDATE giveaway_state SET next_run_at = ? WHERE id = 1",
                (next_run.isoformat(timespec="seconds"),),
            )
        return winner_id

    def state(self, user_id: int) -> tuple[str, dict[str, Any]] | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT state, data_json FROM states WHERE user_id = ?", (user_id,)
            ).fetchone()
        if not row:
            return None
        return str(row["state"]), json.loads(row["data_json"])

    def set_state(
        self, user_id: int, state: str, data: dict[str, Any] | None = None
    ) -> None:
        with self.lock, self.connect() as db:
            db.execute(
                """INSERT INTO states (user_id, state, data_json, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET state = excluded.state,
                   data_json = excluded.data_json, updated_at = excluded.updated_at""",
                (user_id, state, json.dumps(data or {}), now_iso()),
            )

    def clear_state(self, user_id: int) -> None:
        with self.lock, self.connect() as db:
            db.execute("DELETE FROM states WHERE user_id = ?", (user_id,))

    def create_order(
        self, user_id: int, product: Product, quantity: int, recipient: str
    ) -> int:
        if product.code not in ACTIVE_PRODUCT_CODES:
            raise ValueError("Product is not available in the current catalog")
        user = self.user(user_id)
        manual_discount = (
            max(0, int(user.get("discount_percent") or 0)) if user else 0
        )
        referral_discount = (
            max(0, int(user.get("referral_discount_percent") or 0))
            if user
            else 0
        )
        base_discount = min(
            MAX_TOTAL_DISCOUNT_PERCENT,
            manual_discount + referral_discount,
        )
        subtotal = product.total_minor(quantity)
        subtotal_usd_cents = (
            subtotal
            if product.currency == "usd"
            else rub_kopecks_to_usd_cents(subtotal)
            if product.currency == "rub"
            else 0
        )
        if (
            product.category != "premium"
            and subtotal_usd_cents < MIN_ORDER_USD_CENTS
        ):
            raise ValueError("Order total is below the configured minimum")
        wholesale_discount = (
            WHOLESALE_DISCOUNT_PERCENT
            if subtotal_usd_cents >= WHOLESALE_MIN_USD_CENTS
            else 0
        )
        regular_discount = min(
            MAX_TOTAL_DISCOUNT_PERCENT, base_discount + wholesale_discount
        )
        promo_discount = (
            max(0, int(user.get("promo_discount_percent") or 0)) if user else 0
        )
        promo_code = str(user.get("promo_code") or "") if user else ""
        giveaway_uses = int(user.get("giveaway_discount_uses") or 0) if user else 0
        use_giveaway = (
            giveaway_uses > 0
            and GIVEAWAY_DISCOUNT_PERCENT
            > max(regular_discount, promo_discount)
        )
        use_promo = (
            bool(promo_code)
            and promo_discount > 0
            and promo_discount
            >= max(
                regular_discount,
                GIVEAWAY_DISCOUNT_PERCENT if use_giveaway else 0,
            )
        )
        discount = max(
            regular_discount,
            GIVEAWAY_DISCOUNT_PERCENT if use_giveaway else 0,
            promo_discount if use_promo else 0,
        )
        total = (subtotal * (100 - discount) + 99) // 100
        now = now_iso()
        with self.lock, self.connect() as db:
            cursor = db.execute(
                """INSERT INTO orders
                   (user_id, product_code, product_title, quantity, total_kopecks,
                    discount_percent, wholesale_discount_percent, promo_code,
                    promo_discount_percent, price_currency, recipient,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id,
                    product.code,
                    product.titles["en"],
                    quantity,
                    total,
                    discount,
                    wholesale_discount,
                    promo_code if use_promo else None,
                    promo_discount if use_promo else 0,
                    product.currency,
                    recipient,
                    now,
                    now,
                ),
            )
            if use_giveaway:
                db.execute(
                    "UPDATE users SET giveaway_discount_uses = "
                    "MAX(giveaway_discount_uses - 1, 0), updated_at = ? "
                    "WHERE user_id = ?",
                    (now_iso(), user_id),
                )
            if use_promo:
                db.execute(
                    "UPDATE users SET promo_code = NULL, "
                    "promo_discount_percent = 0, updated_at = ? "
                    "WHERE user_id = ?",
                    (now_iso(), user_id),
                )
            return int(cursor.lastrowid)

    def order(self, order_id: int) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute(
                """SELECT o.*, u.username FROM orders o
                   JOIN users u ON u.user_id = o.user_id WHERE o.id = ?""",
                (order_id,),
            ).fetchone()
        return dict(row) if row else None

    def admin_set_discount(
        self, admin_user_id: int, target_user_id: int, percent: int
    ) -> dict[str, Any] | None:
        if not 0 <= percent <= MAX_TOTAL_DISCOUNT_PERCENT:
            raise ValueError("Invalid discount percent")
        with self.lock, self.connect() as db:
            cursor = db.execute(
                "UPDATE users SET discount_percent = ?, updated_at = ? "
                "WHERE user_id = ?",
                (percent, now_iso(), target_user_id),
            )
            if cursor.rowcount != 1:
                return None
            row = db.execute(
                "SELECT * FROM users WHERE user_id = ?", (target_user_id,)
            ).fetchone()
        if row:
            result = dict(row)
            result["discount_admin_user_id"] = admin_user_id
            return result
        return None

    def user_orders(self, user_id: int) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 8",
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def attach_order_payment(
        self, order_id: int, method: str, amount_text: str, reference: str
    ) -> None:
        with self.lock, self.connect() as db:
            db.execute(
                """UPDATE orders SET payment_method = ?, payment_amount_text = ?,
                   payment_comment = ?, updated_at = ?
                   WHERE id = ? AND status = 'awaiting_payment'""",
                (method, amount_text, reference, now_iso(), order_id),
            )

    def submit_order_hash(self, order_id: int, user_id: int, tx_hash: str) -> bool:
        with self.lock, self.connect() as db:
            if db.execute(
                "SELECT 1 FROM topups WHERE tx_hash = ?", (tx_hash,)
            ).fetchone():
                raise sqlite3.IntegrityError
            cursor = db.execute(
                """UPDATE orders SET tx_hash = ?, status = 'payment_review', updated_at = ?
                   WHERE id = ? AND user_id = ? AND status = 'awaiting_payment'""",
                (tx_hash, now_iso(), order_id, user_id),
            )
            return cursor.rowcount == 1

    def pay_from_balance(
        self, order_id: int, user_id: int, usd_cents: int
    ) -> dict[str, Any] | None:
        with self.lock, self.connect() as db:
            order = db.execute(
                "SELECT status FROM orders WHERE id = ? AND user_id = ?",
                (order_id, user_id),
            ).fetchone()
            user = db.execute(
                "SELECT balance_usd_cents FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            if not order or order["status"] != "awaiting_payment" or not user:
                return None
            if int(user["balance_usd_cents"]) < usd_cents:
                raise ValueError("Insufficient balance")
            db.execute(
                "UPDATE users SET balance_usd_cents = balance_usd_cents - ? WHERE user_id = ?",
                (usd_cents, user_id),
            )
            db.execute(
                "UPDATE orders SET status = 'paid', updated_at = ? WHERE id = ?",
                (now_iso(), order_id),
            )
        return self.order(order_id)

    def set_order_status(self, order_id: int, status: str) -> dict[str, Any] | None:
        transitions = {
            "paid": {"awaiting_payment", "payment_review"},
            "processing": {"paid"},
            "completed": {"processing"},
            "cancelled": {
                "awaiting_payment",
                "payment_review",
                "paid",
                "processing",
            },
        }
        if status not in transitions:
            raise ValueError("Invalid order status")
        with self.lock, self.connect() as db:
            allowed = tuple(transitions[status])
            placeholders = ",".join("?" for _ in allowed)
            cursor = db.execute(
                f"UPDATE orders SET status = ?, updated_at = ? WHERE id = ? "
                f"AND status IN ({placeholders})",
                (status, now_iso(), order_id, *allowed),
            )
            if cursor.rowcount != 1:
                return None
        return self.order(order_id)

    def review_orders(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT id FROM orders WHERE status IN "
                "('awaiting_payment','payment_review','paid','processing') "
                "ORDER BY id DESC LIMIT 20"
            ).fetchall()
        return [item for row in rows if (item := self.order(int(row["id"])))]

    def expire_unpaid_orders(self) -> list[dict[str, Any]]:
        cutoff = (
            datetime.now(timezone.utc)
            - timedelta(minutes=ORDER_AUTO_CLOSE_MINUTES)
        ).isoformat(timespec="seconds")
        now = now_iso()
        with self.lock, self.connect() as db:
            rows = db.execute(
                "SELECT * FROM orders WHERE status = 'awaiting_payment' "
                "AND created_at <= ? ORDER BY id",
                (cutoff,),
            ).fetchall()
            if not rows:
                return []
            order_ids = [int(row["id"]) for row in rows]
            placeholders = ",".join("?" for _ in order_ids)
            db.execute(
                f"UPDATE orders SET status = 'cancelled', updated_at = ? "
                f"WHERE id IN ({placeholders}) AND status = 'awaiting_payment'",
                (now, *order_ids),
            )
            db.execute(
                f"UPDATE star_payments SET status = 'expired', updated_at = ? "
                f"WHERE kind = 'order' AND item_id IN ({placeholders}) "
                "AND status = 'pending'",
                (now, *order_ids),
            )
        return [dict(row) for row in rows]

    def create_topup(self, user_id: int, cents: int) -> int:
        if not minimum_topup_cents() <= cents <= MAX_TOPUP_CENTS:
            raise ValueError(
                "Top-up must be between "
                f"${Decimal(minimum_topup_cents()) / 100:.2f} and $10,000"
            )
        now = now_iso()
        with self.lock, self.connect() as db:
            cursor = db.execute(
                "INSERT INTO topups "
                "(user_id, amount_usd_cents, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (user_id, cents, now, now),
            )
            return int(cursor.lastrowid)

    def topup(self, topup_id: int) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute(
                """SELECT t.*, u.username FROM topups t
                   JOIN users u ON u.user_id = t.user_id WHERE t.id = ?""",
                (topup_id,),
            ).fetchone()
        return dict(row) if row else None

    def attach_topup_payment(
        self, topup_id: int, method: str, amount_text: str, reference: str
    ) -> None:
        with self.lock, self.connect() as db:
            db.execute(
                """UPDATE topups SET payment_method = ?, payment_amount_text = ?,
                   payment_comment = ?, updated_at = ?
                   WHERE id = ? AND status = 'awaiting_payment'""",
                (method, amount_text, reference, now_iso(), topup_id),
            )

    def submit_topup_hash(self, topup_id: int, user_id: int, tx_hash: str) -> bool:
        with self.lock, self.connect() as db:
            if db.execute(
                "SELECT 1 FROM orders WHERE tx_hash = ?", (tx_hash,)
            ).fetchone():
                raise sqlite3.IntegrityError
            cursor = db.execute(
                """UPDATE topups SET tx_hash = ?, status = 'payment_review', updated_at = ?
                   WHERE id = ? AND user_id = ? AND status = 'awaiting_payment'""",
                (tx_hash, now_iso(), topup_id, user_id),
            )
            return cursor.rowcount == 1

    def review_topups(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT id FROM topups WHERE status = 'payment_review' "
                "OR (status = 'awaiting_payment' AND payment_method LIKE 'card_%') "
                "ORDER BY id DESC LIMIT 20"
            ).fetchall()
        return [item for row in rows if (item := self.topup(int(row["id"])))]

    def resolve_topup(self, topup_id: int, approve: bool) -> dict[str, Any] | None:
        with self.lock, self.connect() as db:
            topup = db.execute(
                "SELECT * FROM topups WHERE id = ?", (topup_id,)
            ).fetchone()
            is_card_request = (
                topup
                and topup["status"] == "awaiting_payment"
                and str(topup["payment_method"] or "").startswith("card_")
            )
            if not topup or (
                topup["status"] != "payment_review" and not is_card_request
            ):
                return None
            status = "credited" if approve else "cancelled"
            db.execute(
                "UPDATE topups SET status = ?, updated_at = ? WHERE id = ?",
                (status, now_iso(), topup_id),
            )
            if approve:
                db.execute(
                    "UPDATE users SET balance_usd_cents = balance_usd_cents + ? "
                    "WHERE user_id = ?",
                    (topup["amount_usd_cents"], topup["user_id"]),
                )
        return self.topup(topup_id)

    def pending_crypto_reviews(self) -> list[tuple[str, dict[str, Any]]]:
        methods = tuple(PAYMENT_METHODS)
        placeholders = ",".join("?" for _ in methods)
        with self.connect() as db:
            order_ids = db.execute(
                f"SELECT id FROM orders WHERE status = 'payment_review' "
                f"AND payment_method IN ({placeholders}) ORDER BY id LIMIT 50",
                methods,
            ).fetchall()
            topup_ids = db.execute(
                f"SELECT id FROM topups WHERE status = 'payment_review' "
                f"AND payment_method IN ({placeholders}) ORDER BY id LIMIT 50",
                methods,
            ).fetchall()
        pending: list[tuple[str, dict[str, Any]]] = []
        pending.extend(
            ("order", item)
            for row in order_ids
            if (item := self.order(int(row["id"])))
        )
        pending.extend(
            ("topup", item)
            for row in topup_ids
            if (item := self.topup(int(row["id"])))
        )
        return pending

    def auto_confirm_order(
        self, order_id: int, tx_hash: str
    ) -> dict[str, Any] | None:
        with self.lock, self.connect() as db:
            cursor = db.execute(
                "UPDATE orders SET status = 'paid', updated_at = ? "
                "WHERE id = ? AND status = 'payment_review' AND tx_hash = ?",
                (now_iso(), order_id, tx_hash),
            )
            if cursor.rowcount != 1:
                return None
        return self.order(order_id)

    def auto_confirm_topup(
        self, topup_id: int, tx_hash: str
    ) -> dict[str, Any] | None:
        with self.lock, self.connect() as db:
            topup = db.execute(
                "SELECT user_id, amount_usd_cents FROM topups "
                "WHERE id = ? AND status = 'payment_review' AND tx_hash = ?",
                (topup_id, tx_hash),
            ).fetchone()
            if not topup:
                return None
            cursor = db.execute(
                "UPDATE topups SET status = 'credited', updated_at = ? "
                "WHERE id = ? AND status = 'payment_review' AND tx_hash = ?",
                (now_iso(), topup_id, tx_hash),
            )
            if cursor.rowcount != 1:
                return None
            db.execute(
                "UPDATE users SET balance_usd_cents = balance_usd_cents + ?, "
                "updated_at = ? WHERE user_id = ?",
                (
                    int(topup["amount_usd_cents"]),
                    now_iso(),
                    int(topup["user_id"]),
                ),
            )
        return self.topup(topup_id)


@dataclass(frozen=True, slots=True)
class Invoice:
    method: PaymentMethod
    amount_text: str
    reference: str
    qr_data: str
    open_url: str


class MarketService:
    def __init__(self) -> None:
        self.rates: dict[str, Decimal] = {}
        self.updated_at = 0.0
        self.lock = threading.Lock()

    def get_rates(self) -> dict[str, Decimal]:
        with self.lock:
            if self.rates and time.monotonic() - self.updated_at < 300:
                return dict(self.rates)
            fallback = {
                "ton_usd": TON_USD_FALLBACK,
                "sol_usd": SOL_USD_FALLBACK,
            }
            try:
                headers = {
                    "Accept": "application/json",
                    "User-Agent": "JouliMarket/2.1",
                }
                if COINGECKO_API_KEY:
                    headers["x-cg-demo-api-key"] = COINGECKO_API_KEY
                response = requests.get(
                    "https://api.coingecko.com/api/v3/simple/price",
                    params={
                        "ids": "the-open-network,solana",
                        "vs_currencies": "usd",
                        "include_last_updated_at": "true",
                    },
                    headers=headers,
                    timeout=(3.05, 8),
                )
                response.raise_for_status()
                payload = response.json()
                ton = payload["the-open-network"]
                sol = payload["solana"]
                oldest = min(int(ton["last_updated_at"]), int(sol["last_updated_at"]))
                if time.time() - oldest > 1_800:
                    raise RuntimeError("Stale market rates")
                self.rates = {
                    "ton_usd": Decimal(str(ton["usd"])),
                    "sol_usd": Decimal(str(sol["usd"])),
                }
            except (
                requests.RequestException,
                KeyError,
                TypeError,
                ValueError,
                InvalidOperation,
                RuntimeError,
            ) as exc:
                self.rates = dict(self.rates or fallback)
                LOGGER.warning("Using fallback crypto rates: %s", exc)
            self.updated_at = time.monotonic()
            return dict(self.rates)

    def usd_cents(self, minor: int, currency: str) -> int:
        if currency == "usd":
            return minor
        return int(
            (Decimal(minor) / RUB_PER_USD).quantize(Decimal("1"), rounding=ROUND_UP)
        )

    def invoice(
        self, method_code: str, reference: str, minor: int, currency: str
    ) -> Invoice:
        method = PAYMENT_METHODS[method_code]
        usd_cents = self.usd_cents(minor, currency)
        usd = Decimal(usd_cents) / 100

        if method_code in {"trc20", "erc20"}:
            amount = usd.quantize(Decimal("0.01"), rounding=ROUND_UP)
            return Invoice(
                method,
                f"{amount:.2f} USDT",
                reference,
                method.wallet,
                method.explorer_url,
            )

        rates = self.get_rates()

        if method_code == "ton":
            amount = (usd / rates["ton_usd"]).quantize(
                Decimal("0.0001"), rounding=ROUND_UP
            )
            nano = int(amount * NANO_TON)
            expires = datetime.now(timezone.utc) + timedelta(
                minutes=PAYMENT_TTL_MINUTES
            )
            params = urlencode(
                {
                    "amount": str(nano),
                    "text": reference,
                    "exp": str(int(expires.timestamp())),
                }
            )
            url = f"https://app.tonkeeper.com/transfer/{method.wallet}?{params}"
            qr_data = f"ton://transfer/{method.wallet}?{params}"
            amount_text = f"{amount:.4f} TON"
            return Invoice(method, amount_text, reference, qr_data, url)

        amount = (usd / rates["sol_usd"]).quantize(Decimal("0.0001"), rounding=ROUND_UP)
        qr_data = f"solana:{method.wallet}?amount={amount}"
        return Invoice(
            method,
            f"{amount:.4f} SOL",
            reference,
            qr_data,
            method.explorer_url,
        )


@dataclass(frozen=True, slots=True)
class VerificationResult:
    status: str
    detail: str

    @property
    def confirmed(self) -> bool:
        return self.status == "confirmed"


TRANSFER_EVENT_TOPIC = (
    "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
)
BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def base58check_payload(value: str) -> bytes:
    number = 0
    for character in value:
        index = BASE58_ALPHABET.find(character)
        if index < 0:
            raise ValueError("Invalid Base58 character")
        number = number * 58 + index
    raw = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    raw = b"\0" * (len(value) - len(value.lstrip("1"))) + raw
    if len(raw) < 5:
        raise ValueError("Invalid Base58Check value")
    payload, checksum = raw[:-4], raw[-4:]
    expected = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    if checksum != expected:
        raise ValueError("Invalid Base58Check checksum")
    return payload


def tron_address_hex(value: str) -> str:
    payload = base58check_payload(value)
    if len(payload) != 21 or payload[0] != 0x41:
        raise ValueError("Invalid TRON address")
    return payload[1:].hex()


def transaction_hash_variants(value: str) -> set[str]:
    cleaned = value.strip()
    variants = {cleaned.lower(), cleaned.lower().removeprefix("0x")}
    compact = cleaned.removeprefix("0x")
    if re.fullmatch(r"[a-fA-F0-9]{64}", compact):
        raw = bytes.fromhex(compact)
        variants.add(base64.b64encode(raw).decode().rstrip("=").lower())
        variants.add(base64.urlsafe_b64encode(raw).decode().rstrip("=").lower())
    try:
        raw = base64.b64decode(cleaned + "=" * (-len(cleaned) % 4), altchars=b"-_", validate=False)
        if len(raw) == 32:
            variants.add(raw.hex())
    except (ValueError, TypeError):
        pass
    return variants


def payment_amount(value: str) -> tuple[Decimal, str] | None:
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s+(TON|USDT|SOL)", value.strip())
    if not match:
        return None
    try:
        amount = Decimal(match.group(1))
    except InvalidOperation:
        return None
    return (amount, match.group(2)) if amount > 0 else None


def chain_timestamp_is_valid(timestamp: int | float | None, created_at: str) -> bool:
    if not timestamp:
        return False
    try:
        created = datetime.fromisoformat(created_at).timestamp()
    except (TypeError, ValueError):
        return False
    return float(timestamp) >= created - 600


class PaymentVerifier:
    def verify(self, payment: dict[str, Any]) -> VerificationResult:
        method = str(payment.get("payment_method") or "")
        tx_hash = str(payment.get("tx_hash") or "").strip()
        parsed_amount = payment_amount(str(payment.get("payment_amount_text") or ""))
        if not tx_hash or not parsed_amount:
            return VerificationResult("rejected", "Missing hash or expected amount")
        try:
            if method == "ton":
                return self.verify_ton(payment, tx_hash, parsed_amount)
            if method == "trc20":
                return self.verify_trc20(payment, tx_hash, parsed_amount)
            if method == "erc20":
                return self.verify_erc20(payment, tx_hash, parsed_amount)
            if method == "sol":
                return self.verify_sol(payment, tx_hash, parsed_amount)
            return VerificationResult("unavailable", "Manual payment method")
        except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
            return VerificationResult("unavailable", str(exc))

    @staticmethod
    def _required_units(
        parsed_amount: tuple[Decimal, str], asset: str, decimals: int
    ) -> int:
        amount, actual_asset = parsed_amount
        if actual_asset != asset:
            raise ValueError(f"Expected {asset}, received {actual_asset}")
        return int(
            (amount * (Decimal(10) ** decimals)).quantize(
                Decimal("1"), rounding=ROUND_UP
            )
        )

    def verify_ton(
        self,
        payment: dict[str, Any],
        tx_hash: str,
        parsed_amount: tuple[Decimal, str],
    ) -> VerificationResult:
        required = self._required_units(parsed_amount, "TON", 9)
        headers = {"Accept": "application/json", "User-Agent": "JouliMarket/3.0"}
        if TONAPI_API_KEY:
            headers["Authorization"] = f"Bearer {TONAPI_API_KEY}"
        response = requests.get(
            f"{TONAPI_BASE_URL}/v2/blockchain/accounts/"
            f"{quote(TON_WALLET, safe='')}/transactions",
            params={"limit": 100},
            headers=headers,
            timeout=(3.05, 12),
        )
        response.raise_for_status()
        expected_hashes = transaction_hash_variants(tx_hash)
        for transaction in response.json().get("transactions", []):
            in_message = transaction.get("in_msg") or {}
            actual_hashes: set[str] = set()
            for value in (transaction.get("hash"), in_message.get("hash")):
                if value:
                    actual_hashes.update(transaction_hash_variants(str(value)))
            if not expected_hashes.intersection(actual_hashes):
                continue
            if not transaction.get("success", False):
                return VerificationResult("rejected", "TON transaction failed")
            if int(in_message.get("value") or 0) < required:
                return VerificationResult("rejected", "TON amount is too small")
            if not chain_timestamp_is_valid(
                transaction.get("utime") or in_message.get("created_at"),
                str(payment["created_at"]),
            ):
                return VerificationResult("rejected", "TON transaction is too old")
            reference = str(payment.get("payment_comment") or "")
            if reference and reference not in json.dumps(
                in_message, ensure_ascii=False, sort_keys=True
            ):
                return VerificationResult("rejected", "TON reference does not match")
            return VerificationResult("confirmed", "TON transaction confirmed")
        return VerificationResult("pending", "TON transaction not indexed yet")

    def verify_trc20(
        self,
        payment: dict[str, Any],
        tx_hash: str,
        parsed_amount: tuple[Decimal, str],
    ) -> VerificationResult:
        required = self._required_units(parsed_amount, "USDT", 6)
        headers = {"Accept": "application/json", "User-Agent": "JouliMarket/3.0"}
        if TRONGRID_API_KEY:
            headers["TRON-PRO-API-KEY"] = TRONGRID_API_KEY
        response = requests.post(
            f"{TRONGRID_BASE_URL}/walletsolidity/gettransactioninfobyid",
            json={"value": tx_hash.removeprefix("0x")},
            headers=headers,
            timeout=(3.05, 12),
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("id"):
            return VerificationResult("pending", "TRON transaction is not confirmed")
        receipt_result = str((payload.get("receipt") or {}).get("result") or "SUCCESS")
        if payload.get("result") == "FAILED" or receipt_result != "SUCCESS":
            return VerificationResult("rejected", "TRON transaction failed")
        if not chain_timestamp_is_valid(
            (
                int(payload["blockTimeStamp"]) / 1_000
                if payload.get("blockTimeStamp")
                else None
            ),
            str(payment["created_at"]),
        ):
            return VerificationResult("rejected", "TRON transaction is too old")
        wallet_hex = tron_address_hex(TRC20_WALLET)
        contract_hex = tron_address_hex(TRON_USDT_CONTRACT)
        for event in payload.get("log") or []:
            topics = event.get("topics") or []
            if (
                str(event.get("address") or "").lower() != contract_hex
                or len(topics) < 3
                or str(topics[0]).lower().removeprefix("0x") != TRANSFER_EVENT_TOPIC
                or str(topics[2]).lower().removeprefix("0x")[-40:] != wallet_hex
            ):
                continue
            amount = int(str(event.get("data") or "0").removeprefix("0x"), 16)
            if amount < required:
                return VerificationResult("rejected", "TRC20 amount is too small")
            return VerificationResult("confirmed", "TRC20 transfer confirmed")
        return VerificationResult("rejected", "TRC20 recipient or token does not match")

    def _etherscan(self, action: str, **parameters: str) -> Any:
        if not ETHERSCAN_API_KEY:
            raise ValueError("ETHERSCAN_API_KEY is not configured")
        response = requests.get(
            ETHERSCAN_API_URL,
            params={
                "chainid": "1",
                "module": "proxy",
                "action": action,
                "apikey": ETHERSCAN_API_KEY,
                **parameters,
            },
            headers={"Accept": "application/json", "User-Agent": "JouliMarket/3.0"},
            timeout=(3.05, 12),
        )
        response.raise_for_status()
        payload = response.json()
        result = payload.get("result")
        if isinstance(result, str) and result.lower().startswith(("error", "missing")):
            raise ValueError(result)
        return result

    def verify_erc20(
        self,
        payment: dict[str, Any],
        tx_hash: str,
        parsed_amount: tuple[Decimal, str],
    ) -> VerificationResult:
        required = self._required_units(parsed_amount, "USDT", 6)
        normalized_hash = tx_hash if tx_hash.startswith("0x") else f"0x{tx_hash}"
        receipt = self._etherscan(
            "eth_getTransactionReceipt", txhash=normalized_hash
        )
        if not isinstance(receipt, dict):
            return VerificationResult("pending", "Ethereum transaction not mined")
        if receipt.get("status") != "0x1":
            return VerificationResult("rejected", "Ethereum transaction failed")
        block_number = int(str(receipt["blockNumber"]), 16)
        latest = int(str(self._etherscan("eth_blockNumber")), 16)
        if latest - block_number + 1 < AUTO_VERIFY_CONFIRMATIONS:
            return VerificationResult("pending", "Waiting for Ethereum confirmations")
        block = self._etherscan(
            "eth_getBlockByNumber", tag=receipt["blockNumber"], boolean="false"
        )
        if not isinstance(block, dict) or not chain_timestamp_is_valid(
            int(str(block.get("timestamp") or "0"), 16), str(payment["created_at"])
        ):
            return VerificationResult("rejected", "Ethereum transaction is too old")
        wallet_hex = ERC20_WALLET.lower().removeprefix("0x")
        contract_hex = ETH_USDT_CONTRACT.lower().removeprefix("0x")
        for event in receipt.get("logs") or []:
            topics = event.get("topics") or []
            if (
                str(event.get("address") or "").lower().removeprefix("0x")
                != contract_hex
                or len(topics) < 3
                or str(topics[0]).lower().removeprefix("0x") != TRANSFER_EVENT_TOPIC
                or str(topics[2]).lower().removeprefix("0x")[-40:] != wallet_hex
                or event.get("removed", False)
            ):
                continue
            amount = int(str(event.get("data") or "0"), 16)
            if amount < required:
                return VerificationResult("rejected", "ERC20 amount is too small")
            return VerificationResult("confirmed", "ERC20 transfer confirmed")
        return VerificationResult("rejected", "ERC20 recipient or token does not match")

    def verify_sol(
        self,
        payment: dict[str, Any],
        tx_hash: str,
        parsed_amount: tuple[Decimal, str],
    ) -> VerificationResult:
        required = self._required_units(parsed_amount, "SOL", 9)
        response = requests.post(
            SOL_RPC_URL,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTransaction",
                "params": [
                    tx_hash,
                    {
                        "commitment": "finalized",
                        "encoding": "jsonParsed",
                        "maxSupportedTransactionVersion": 0,
                    },
                ],
            },
            headers={"Content-Type": "application/json", "User-Agent": "JouliMarket/3.0"},
            timeout=(3.05, 12),
        )
        response.raise_for_status()
        result = response.json().get("result")
        if not isinstance(result, dict):
            return VerificationResult("pending", "Solana transaction not finalized")
        meta = result.get("meta") or {}
        if meta.get("err") is not None:
            return VerificationResult("rejected", "Solana transaction failed")
        if not chain_timestamp_is_valid(
            result.get("blockTime"), str(payment["created_at"])
        ):
            return VerificationResult("rejected", "Solana transaction is too old")
        message = ((result.get("transaction") or {}).get("message") or {})
        instructions = list(message.get("instructions") or [])
        for group in meta.get("innerInstructions") or []:
            instructions.extend(group.get("instructions") or [])
        transferred = 0
        for instruction in instructions:
            parsed = instruction.get("parsed") or {}
            info = parsed.get("info") or {}
            if (
                instruction.get("program") == "system"
                and parsed.get("type") in {"transfer", "transferWithSeed"}
                and info.get("destination") == SOL_WALLET
            ):
                transferred += int(info.get("lamports") or 0)
        if transferred == 0:
            keys = [
                item.get("pubkey") if isinstance(item, dict) else item
                for item in message.get("accountKeys") or []
            ]
            if SOL_WALLET in keys:
                index = keys.index(SOL_WALLET)
                pre = meta.get("preBalances") or []
                post = meta.get("postBalances") or []
                if index < len(pre) and index < len(post):
                    transferred = max(0, int(post[index]) - int(pre[index]))
        if transferred < required:
            return VerificationResult("rejected", "SOL recipient or amount does not match")
        return VerificationResult("confirmed", "SOL transfer confirmed")


def qr_image(invoice: Invoice) -> io.BytesIO:
    image = qrcode.make(invoice.qr_data)
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    buffer.seek(0)
    buffer.name = f"{invoice.method.code}-payment.png"
    return buffer


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    names = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "arialbd.ttf" if bold else "arial.ttf",
    ]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


@lru_cache(maxsize=2)
def welcome_bytes() -> bytes:
    image = Image.new("RGB", (1200, 600), "#06170E")
    draw = ImageDraw.Draw(image, "RGBA")
    draw.ellipse((-180, -260, 460, 380), fill=(30, 190, 104, 70))
    draw.ellipse((820, 220, 1380, 780), fill=(44, 239, 132, 55))
    draw.ellipse((760, -350, 1300, 190), fill=(89, 255, 165, 35))
    for x, y, radius in ((1030, 90, 7), (1090, 165, 5), (970, 230, 4), (665, 75, 4), (720, 510, 6)):
        draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill=(115, 255, 174, 120))
    draw.rounded_rectangle((55, 48, 1145, 552), 38, fill=(12, 39, 25, 238), outline=(50, 156, 96, 230), width=3)
    draw.rounded_rectangle((87, 78, 175, 166), 26, fill=(62, 229, 135, 255))
    draw.text((116, 91), "J", font=font(49, True), fill="#052316")
    draw.text((205, 72), "Jouli Market", font=font(66, True), fill="#F2FFF7")
    draw.text((207, 151), "YOUR DIGITAL GARDEN", font=font(22, True), fill="#45E58B")
    draw.text((88, 235), "STARS  •  PUBG UC  •  BRAWL PASS", font=font(25, True), fill="#D8FFE7")
    draw.text((88, 278), "ROBUX  •  AI SUBSCRIPTIONS", font=font(25, True), fill="#D8FFE7")
    draw.rounded_rectangle((88, 345, 552, 412), 20, fill=(38, 202, 112, 245))
    draw.text((124, 364), "ONLY WHAT PEOPLE BUY", font=font(22, True), fill="#052316")
    draw.text((90, 458), "RU / UK / EN   •   USD / RUB", font=font(19, True), fill="#83D9A9")
    cards = [
        (680, "★ STARS", "$12.00 / 1K"),
        (680, "UC PUBG", "$12.00 / 1K"),
        (680, "R$ ROBUX", "FROM $3.81 / 1K"),
    ]
    for index, (x, title, price) in enumerate(cards):
        y = 230 + index * 82
        draw.rounded_rectangle((x, y, 1090, y + 65), 20, fill=(18, 57, 37, 255), outline=(43, 121, 78, 240), width=2)
        draw.text((x + 22, y + 20), title, font=font(18, True), fill="#A8FFCA")
        draw.text((900, y + 20), price, font=font(17, True), fill="#F2FFF7")
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=True)
    return buffer.getvalue()


def welcome_image() -> io.BytesIO:
    buffer = io.BytesIO(welcome_bytes())
    buffer.name = "jouli-market-welcome.png"
    return buffer


RED_VISUALS = {
    "catalog": (
        "JOULI MARKET CATALOG",
        "POPULAR DIGITAL GOODS",
        f"{len(ACTIVE_PRODUCT_CODES)} PRODUCTS",
    ),
    "stars": ("TELEGRAM STARS", "FAST DELIVERY TO TELEGRAM", "TELEGRAM"),
    "premium": ("TELEGRAM PREMIUM", "SUBSCRIPTIONS FROM 1 TO 12 MONTHS", "TELEGRAM"),
    "brawl": ("BRAWL PASS", "PASS AND PASS PLUS", "GAMING"),
    "steam": ("STEAM WALLET", "FLEXIBLE USD TOP-UPS", "GAMING"),
    "pubg": ("PUBG MOBILE UC", "GAME CURRENCY TOP-UP", "GAMING"),
    "roblox": ("ROBLOX CENTER", "CHOOSE YOUR DELIVERY METHOD", "ROBLOX"),
    "robux": ("ROBUX CENTER", "FROM $12.50 OR 45,000 ROBUX", "ROBLOX"),
    "roblox_account": ("ROBUX BY ACCOUNT", "ACCOUNT DELIVERY METHOD", "ROBLOX"),
    "robux_account": ("ROBUX BY ACCOUNT", "FROM $12.50 OR 45,000 ROBUX", "ROBLOX"),
    "roblox_gamepass": ("ROBUX GAME PASS", "DELIVERY THROUGH GAME PASS", "ROBLOX"),
    "robux_gamepass": ("ROBUX GAMEPASS", "FROM $12.50 OR 45,000 ROBUX", "ROBLOX"),
    "robux_group": ("ROBUX VIA GROUP", "$4.12 / 1K • 45K+ $4.02", "ROBLOX"),
    "roblox_gifts": ("ROBLOX GIFT CARDS", "GIFT CARDS FROM 100 TO 10K R$", "ROBLOX"),
    "ai": ("AI SUBSCRIPTIONS", "POPULAR AI SERVICES", "DIGITAL"),
    "accounts": ("DIGITAL ACCOUNTS", "SECURE DELIVERY AND SUPPORT", "ACCOUNTS"),
    "gmail": ("GMAIL ACCOUNTS", "READY DIGITAL ACCOUNTS", "ACCOUNTS"),
    "exitlag": ("EXITLAG ACCOUNTS", "WITH OR WITHOUT WARRANTY", "ACCOUNTS"),
    "gta": ("GTA V / STEAM", "STEAM ACCOUNT DELIVERY", "ACCOUNTS"),
    "rust": ("RUST / STEAM", "STEAM ACCOUNT DELIVERY", "ACCOUNTS"),
    "profile": ("YOUR JOULI MARKET PROFILE", "BALANCE / DISCOUNTS / REFERRALS", "ACCOUNT"),
    "promo": ("PROMO CODE", "DISCOUNT FOR YOUR NEXT ORDER", "BONUS"),
    "orders": ("YOUR ORDERS", "HISTORY / STATUS / DELIVERY", "ORDERS"),
    "wallet": ("JOULI MARKET WALLET", "TON / USDT / SOL TOP-UP", "PAYMENTS"),
    "payment": ("PAYMENT CENTER", "CRYPTO / BALANCE", "CHECKOUT"),
    "stars_payment": ("PAY WITH TELEGRAM STARS", "1 STAR = 1.3 RUB", "XTR PAYMENT"),
    "checkout": ("ORDER CREATED", "CHOOSE A SECURE PAYMENT METHOD", "CHECKOUT"),
    "success": ("PAYMENT CONFIRMED", "ORDER SECURED BY JOULI MARKET", "SUCCESS"),
    "support": ("JOULI MARKET SUPPORT", "HELP WITH ORDERS AND PAYMENTS", "24 / 7"),
    "suggestion": ("IDEA LAB", "SUGGEST A PRODUCT OR FEATURE", "FEEDBACK"),
    "about": ("ABOUT JOULI MARKET", "MODERN TELEGRAM MARKET", "GREEN EDITION"),
    "giveaway": ("JOULI MARKET GIVEAWAY", "15% DISCOUNT EVERY 48 HOURS", "BONUS"),
    "security": ("SECURITY CENTER", "PROTECT YOUR DATA AND FUNDS", "SAFETY"),
    "nft": ("JOULI MARKET NFT BUYBACK", "MANUAL VALUATION AND SAFE REVIEW", "NFT DESK"),
    "subscription": ("JOIN JOULI MARKET", "SUBSCRIBE TO UNLOCK THE MARKET", "ACCESS"),
    "language": ("CHOOSE YOUR LANGUAGE", "RU / UK / EN", "3 LANGUAGES"),
    "currency": ("CHOOSE YOUR CURRENCY", "USD / RUB", "LIVE FX"),
    "admin": ("ADMIN CONTROL", "ORDERS / PAYMENTS / REQUESTS", "PRIVATE"),
}

RED_VISUAL_CHIPS = {
    "wallet": ("CRYPTO TOP-UP", "TON + USDT + SOL", "GREEN WALLET"),
    "payment": ("SAFE CHECKOUT", "CRYPTO + BALANCE", "AUTO STATUS"),
    "stars_payment": ("INSTANT XTR", "AUTO CONFIRM", "1.3 RUB RATE"),
    "checkout": ("ORDER SAVED", "CHOOSE PAYMENT", "TRACK STATUS"),
    "success": ("PAYMENT VERIFIED", "BALANCE UPDATED", "SECURE"),
    "nft": ("MANUAL REVIEW", "ADMIN OFFER", "SAFE DEAL"),
    "orders": ("LIVE STATUS", "ORDER HISTORY", "FAST SUPPORT"),
    "admin": ("ORDERS", "PAYMENTS", "LEADS + NFT"),
}


def fitted_font(
    draw: ImageDraw.ImageDraw,
    value: str,
    max_width: int,
    start_size: int,
) -> ImageFont.ImageFont:
    size = start_size
    while size > 24:
        selected = font(size, True)
        if draw.textbbox((0, 0), value, font=selected)[2] <= max_width:
            return selected
        size -= 2
    return font(24, True)


@lru_cache(maxsize=96)
def red_banner_bytes(kind: str, product_code: str = "") -> bytes:
    if product_code:
        product = PRODUCTS[product_code]
        title = product.titles["en"].upper()
        subtitle = f"PRICE {product_price(product)} / MIN {product_minimum_label('en', product)}"
        badge = product.category.upper()
        color_seed = sum(product_code.encode("utf-8"))
    else:
        title, subtitle, badge = RED_VISUALS.get(kind, RED_VISUALS["catalog"])
        color_seed = sum(kind.encode("utf-8"))

    accent = (40, 190 + color_seed % 55, 105)
    image = Image.new("RGB", (1200, 600), "#06170E")
    draw = ImageDraw.Draw(image, "RGBA")

    draw.ellipse((-220, -260, 450, 410), fill=(*accent, 48))
    draw.ellipse((820, 160, 1390, 760), fill=(42, 230, 126, 42))
    draw.ellipse((760, -370, 1320, 190), fill=(110, 255, 174, 25))
    draw.rounded_rectangle((54, 48, 1146, 552), 40, fill=(12, 40, 26, 242), outline=(49, 130, 84, 230), width=3)
    draw.rounded_rectangle((82, 78, 170, 166), 25, fill=(*accent, 255))
    draw.text((114, 91), "J", font=font(50, True), fill="#052316")
    draw.text((195, 84), "Jouli Market", font=font(34, True), fill="#F1FFF6")
    draw.rounded_rectangle((890, 88, 1085, 137), 18, fill=(19, 67, 42, 240), outline=(55, 140, 91, 220), width=2)
    draw.text((923, 102), badge[:18], font=font(16, True), fill="#9BFFC2")

    title_font = fitted_font(draw, title, 950, 58)
    draw.text((84, 220), title, font=title_font, fill="#F4FFF8")
    draw.rounded_rectangle((84, 305, 1068, 312), 3, fill=(*accent, 220))
    draw.text((86, 342), subtitle[:64], font=font(23, True), fill="#9FE9BA")

    chips = (
        ("BEST PRICE", "FAST DELIVERY", "SAFE ORDER")
        if product_code
        else RED_VISUAL_CHIPS.get(
            kind,
            ("SECURE PAYMENT", "3 LANGUAGES", "FAST DELIVERY"),
        )
    )
    chip_x = 84
    for chip in chips:
        chip_font = font(15, True)
        width = draw.textbbox((0, 0), chip, font=chip_font)[2] + 44
        draw.rounded_rectangle(
            (chip_x, 438, chip_x + width, 489),
            17,
            fill=(20, 65, 42, 238),
            outline=(55, 135, 89, 220),
            width=2,
        )
        draw.text((chip_x + 22, 454), chip, font=chip_font, fill="#AEFFCC")
        chip_x += width + 16

    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=True)
    return buffer.getvalue()


def red_banner(kind: str, product_code: str = "") -> io.BytesIO:
    buffer = io.BytesIO(red_banner_bytes(kind, product_code))
    suffix = product_code or kind
    buffer.name = f"jouli-market-{suffix}.png"
    return buffer


@lru_cache(maxsize=128)
def animated_banner_bytes(kind: str, product_code: str = "") -> bytes:
    source = (
        welcome_bytes()
        if kind == "welcome" and not product_code
        else red_banner_bytes(kind, product_code)
    )
    base = Image.open(io.BytesIO(source)).convert("RGBA")
    frames: list[Image.Image] = []
    frame_count = 14

    for step in range(frame_count):
        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay, "RGBA")
        phase = step / frame_count
        pulse = int(48 + 30 * (1 + math.sin(phase * math.tau)) / 2)
        glow_x = -430 + step * 150
        draw.ellipse(
            (glow_x, -210, glow_x + 520, 790),
            fill=(40, 230, 126, 18),
        )
        draw.polygon(
            (
                (glow_x + 70, 54),
                (glow_x + 160, 54),
                (glow_x + 420, 546),
                (glow_x + 330, 546),
            ),
            fill=(95, 255, 164, 18),
        )
        scan_y = 64 + step * 35
        draw.rounded_rectangle(
            (80, scan_y, 1120, scan_y + 4),
            2,
            fill=(65, 235, 135, 42),
        )
        ring_size = 110 + (step % 7) * 16
        ring_box = (1030 - ring_size, 300 - ring_size, 1030 + ring_size, 300 + ring_size)
        draw.arc(
            ring_box,
            start=step * 24,
            end=step * 24 + 235,
            fill=(42, 224, 122, pulse),
            width=5,
        )
        progress = 120 + int(948 * ((step + 1) / frame_count))
        draw.rounded_rectangle(
            (120, 506, progress, 511),
            2,
            fill=(35, 210, 112, 150),
        )
        draw.rounded_rectangle(
            (850, 92, 1075, 150),
            22,
            outline=(105, 255, 169, pulse + 70),
            width=3,
        )
        for particle in range(18):
            x = 82 + ((particle * 97 + step * 37) % 1035)
            y = 72 + ((particle * 61 + step * 19) % 445)
            radius = 2 + (particle + step) % 3
            draw.ellipse(
                (x - radius, y - radius, x + radius, y + radius),
                fill=(160, 255, 197, 65 + (particle % 3) * 25),
            )
        frames.append(Image.alpha_composite(base, overlay).convert("RGB"))

    buffer = io.BytesIO()
    frames[0].save(
        buffer,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=85,
        loop=0,
        optimize=True,
        disposal=2,
    )
    return buffer.getvalue()


def animated_banner(kind: str, product_code: str = "") -> io.BytesIO:
    buffer = io.BytesIO(animated_banner_bytes(kind, product_code))
    suffix = product_code or kind
    buffer.name = f"jouli-market-{suffix}.gif"
    return buffer


DB = Database(DATABASE_PATH)
MARKET = MarketService()
VERIFIER = PaymentVerifier()
BOT = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=True, num_threads=8)
VERIFICATION_NOTICES: dict[tuple[str, int, str], tuple[str, str]] = {}


def admin_recipient_ids() -> set[int]:
    return set(ADMIN_IDS) | DB.user_ids_for_usernames(ADMIN_USERNAMES)


def is_admin_user(user: types.User) -> bool:
    username = f"@{user.username}" if user.username else ""
    return user.id in ADMIN_IDS or username.casefold() in {
        value.casefold() for value in ADMIN_USERNAMES
    }


def is_admin_user_id(user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True
    user = DB.user(user_id)
    username = f"@{user['username']}" if user and user.get("username") else ""
    return username.casefold() in {value.casefold() for value in ADMIN_USERNAMES}


def safe_send_photo(
    chat_id: int,
    photo: Any,
    caption: str,
    reply_markup: types.InlineKeyboardMarkup | None = None,
) -> Any:
    try:
        return BOT.send_photo(
            chat_id,
            photo,
            caption=caption,
            reply_markup=reply_markup,
        )
    except Exception as exc:
        LOGGER.warning("Photo delivery failed for chat %s: %s", chat_id, exc)
        return BOT.send_message(
            chat_id,
            caption,
            reply_markup=reply_markup,
        )


def send_visual(
    chat_id: int,
    kind: str,
    caption: str,
    reply_markup: types.InlineKeyboardMarkup | None = None,
    product_code: str = "",
) -> Any:
    try:
        return BOT.send_animation(
            chat_id,
            animated_banner(kind, product_code),
            caption=caption,
            reply_markup=reply_markup,
        )
    except Exception as exc:
        LOGGER.warning(
            "Animation delivery failed for %s in chat %s: %s",
            product_code or kind,
            chat_id,
            exc,
        )
    try:
        photo = (
            welcome_image()
            if kind == "welcome" and not product_code
            else red_banner(kind, product_code)
        )
    except Exception as exc:
        LOGGER.warning("Visual generation failed for %s: %s", kind, exc)
        return BOT.send_message(chat_id, caption, reply_markup=reply_markup)
    return safe_send_photo(chat_id, photo, caption, reply_markup)


def language_of(user_id: int) -> str:
    return DB.language(user_id) or "en"


def currency_of(user_id: int) -> str:
    return DB.currency(user_id) or "usd"


def currency_label(currency: str) -> str:
    return dict(CURRENCY_OPTIONS).get(currency, dict(CURRENCY_OPTIONS)["usd"])


def language_keyboard() -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    buttons = [
        types.InlineKeyboardButton(label, callback_data=f"lang:{code}")
        for code, label in LANGUAGE_OPTIONS
    ]
    keyboard.row(*buttons)
    return keyboard


def currency_keyboard() -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        *(
            types.InlineKeyboardButton(label, callback_data=f"cur:{code}")
            for code, label in CURRENCY_OPTIONS
        )
    )
    return keyboard


def home_keyboard(lang: str, admin: bool = False) -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup()
    if WEBAPP_URL:
        keyboard.add(
            types.InlineKeyboardButton(
                "🌿 OPEN JOULI MARKET",
                web_app=types.WebAppInfo(WEBAPP_URL),
            )
        )
    keyboard.add(
        types.InlineKeyboardButton(
            f"▰ {text(lang, 'catalog').upper()}", callback_data="nav:catalog"
        )
    )
    keyboard.row(
        types.InlineKeyboardButton(text(lang, "orders"), callback_data="nav:orders"),
        types.InlineKeyboardButton(text(lang, "profile"), callback_data="nav:profile"),
    )
    keyboard.row(
        types.InlineKeyboardButton(text(lang, "topup"), callback_data="nav:topup"),
        types.InlineKeyboardButton(
            text(lang, "giveaway"), callback_data="nav:giveaway"
        ),
    )
    keyboard.add(
        types.InlineKeyboardButton(text(lang, "promo"), callback_data="nav:promo")
    )
    keyboard.add(
        types.InlineKeyboardButton(
            text(lang, "suggestion"), callback_data="nav:suggestion"
        )
    )
    keyboard.add(
        types.InlineKeyboardButton(text(lang, "about"), callback_data="nav:about")
    )
    keyboard.add(
        types.InlineKeyboardButton(
            text(lang, "language"), callback_data="nav:language"
        )
    )
    keyboard.add(
        types.InlineKeyboardButton(
            text(lang, "currency"), callback_data="nav:currency"
        )
    )
    return keyboard


def back(lang: str, destination: str = "nav:home") -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton(text(lang, "back"), callback_data=destination)
    )


def profile_keyboard(lang: str) -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton(text(lang, "promo"), callback_data="nav:promo")
    )
    keyboard.add(
        types.InlineKeyboardButton(text(lang, "back"), callback_data="nav:home")
    )
    return keyboard


def support_keyboard(lang: str) -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton(
            text(lang, "open_support"),
            url=f"https://t.me/{SUPPORT_USERNAME.lstrip('@')}",
        )
    )
    keyboard.add(
        types.InlineKeyboardButton(text(lang, "back"), callback_data="nav:home")
    )
    return keyboard


def cryptobot_keyboard(lang: str) -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton(
            text(lang, "open_cryptobot"), url="https://t.me/CryptoBot"
        )
    )
    keyboard.add(
        types.InlineKeyboardButton(text(lang, "home"), callback_data="nav:home")
    )
    return keyboard


def countdown_text(lang: str, target: datetime) -> str:
    seconds = max(0, int((target - datetime.now(timezone.utc)).total_seconds()))
    days, remainder = divmod(seconds, 86_400)
    hours, remainder = divmod(remainder, 3_600)
    minutes = remainder // 60
    if lang == "ru":
        return f"{days} д. {hours} ч. {minutes} мин."
    if lang == "fa":
        return f"{days} روز، {hours} ساعت، {minutes} دقیقه"
    return f"{days}d {hours}h {minutes}m"


def giveaway_message(user_id: int, lang: str) -> str:
    next_run, uses = DB.giveaway_info(user_id)
    bonus = text(lang, "giveaway_bonus", uses=uses) if uses else ""
    return text(
        lang,
        "giveaway_card",
        countdown=countdown_text(lang, next_run),
        bonus=bonus,
    )


def category_keyboard(lang: str) -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton(text(lang, "cat_stars"), callback_data="cat:stars"),
        types.InlineKeyboardButton(text(lang, "cat_brawl"), callback_data="cat:brawl"),
    )
    keyboard.row(
        types.InlineKeyboardButton(text(lang, "cat_pubg"), callback_data="cat:pubg"),
        types.InlineKeyboardButton(text(lang, "cat_ai"), callback_data="cat:ai"),
    )
    keyboard.row(
        types.InlineKeyboardButton(
            text(lang, "cat_robux_account"), callback_data="cat:robux_account"
        ),
        types.InlineKeyboardButton(
            text(lang, "cat_robux_gamepass"), callback_data="cat:robux_gamepass"
        ),
    )
    keyboard.row(
        types.InlineKeyboardButton(
            text(lang, "cat_robux_group"), callback_data="cat:robux_group"
        ),
    )
    keyboard.add(
        types.InlineKeyboardButton(text(lang, "home"), callback_data="nav:home")
    )
    return keyboard


def product_list_keyboard(
    lang: str,
    product_codes: list[str],
    back_callback: str,
    display_currency: str = "usd",
) -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup()
    for code in product_codes:
        product = PRODUCTS[code]
        keyboard.add(
            types.InlineKeyboardButton(
                f"🟢 {product.emoji} {product.title(lang)} · "
                f"{product_price(product, display_currency)}",
                callback_data=f"view:{product.code}",
            )
        )
    keyboard.add(
        types.InlineKeyboardButton(text(lang, "back"), callback_data=back_callback)
    )
    return keyboard


def products_keyboard(
    lang: str, category: str, display_currency: str = "usd"
) -> types.InlineKeyboardMarkup:
    return product_list_keyboard(
        lang, CATEGORIES[category], "nav:catalog", display_currency
    )


def ai_subcategory_keyboard(lang: str) -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    for code, label in AI_SUBCATEGORY_LABELS.items():
        keyboard.add(
            types.InlineKeyboardButton(label, callback_data=f"ai:{code}")
        )
    keyboard.add(
        types.InlineKeyboardButton(text(lang, "back"), callback_data="nav:catalog")
    )
    return keyboard


def roblox_subcategory_keyboard(lang: str) -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton(
            text(lang, "roblox_account"), callback_data="rbx:account"
        )
    )
    keyboard.add(
        types.InlineKeyboardButton(
            text(lang, "roblox_gamepass"), callback_data="rbx:gamepass"
        )
    )
    keyboard.add(
        types.InlineKeyboardButton(text(lang, "back"), callback_data="nav:catalog")
    )
    return keyboard


def roblox_products_keyboard(
    lang: str, subgroup: str, display_currency: str = "usd"
) -> types.InlineKeyboardMarkup:
    return product_list_keyboard(
        lang,
        ROBLOX_SUBCATEGORIES[subgroup],
        "nav:catalog",
        display_currency,
    )


def product_description(lang: str, product: Product) -> str:
    if product.code == "stars":
        key = "desc_stars"
    elif product.code == "robux":
        key = "desc_robux_account_old"
    elif product.code == "robux_gamepass":
        key = "desc_robux_gamepass_old"
    elif product.code == "robux_account_45k":
        key = "desc_robux_account_new"
    elif product.code == "robux_gamepass_45k":
        key = "desc_robux_gamepass_new"
    elif product.code.startswith("gift_"):
        key = "desc_roblox"
    elif product.category == "brawl":
        key = "desc_brawl"
    else:
        key = f"desc_{product.category}"
    return text(lang, key)


def product_minimum_label(lang: str, product: Product) -> str:
    minimum = minimum_quantity(product)
    if product.code == "steam":
        return f"${minimum}"
    if product.code == "stars":
        return f"{minimum:,} Stars"
    if product.code.startswith("telegram_premium_"):
        unit = "подписка" if lang == "ru" else "اشتراک" if lang == "fa" else "subscription"
        return f"{minimum:,} {unit}"
    if product.code == "pubg_uc":
        return f"{minimum:,} UC"
    if product.code.startswith("robux"):
        return f"{minimum:,} R$"
    unit = "шт." if lang == "ru" else "عدد" if lang == "fa" else "item(s)"
    return f"{minimum:,} {unit}"


def product_card_text(
    lang: str, product: Product, display_currency: str = "usd"
) -> str:
    card = text(
        lang,
        "product_card",
        emoji=product.emoji,
        title=html.escape(product.title(lang)),
        description=html.escape(product_description(lang, product)),
        price=html.escape(product_price(product, display_currency)),
        minimum=html.escape(product_minimum_label(lang, product)),
        _currency=display_currency,
    )
    if product.category == "premium":
        card = card.rsplit("\n", 1)[0]
    return f"<b>🟢 {html.escape(SHOP_NAME)}</b>\n{card}"


def product_card_keyboard(lang: str, product: Product) -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton(
            text(lang, "buy_now"), callback_data=f"prd:{product.code}"
        )
    )
    back_callback = f"cat:{product.category}"
    keyboard.add(
        types.InlineKeyboardButton(
            text(lang, "back"), callback_data=back_callback
        )
    )
    return keyboard


def payment_keyboard(lang: str, order_id: int) -> types.InlineKeyboardMarkup:
    keyboard = crypto_keyboard(lang, "pay", order_id)
    keyboard.add(
        types.InlineKeyboardButton(
            text(lang, "pay_balance"), callback_data=f"pay:balance:{order_id}"
        )
    )
    keyboard.add(
        types.InlineKeyboardButton(text(lang, "home"), callback_data="nav:home")
    )
    return keyboard


def crypto_keyboard(lang: str, kind: str, item_id: int) -> types.InlineKeyboardMarkup:
    prefix = "pay:crypto" if kind == "pay" else "topup:pay"
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.row(
        types.InlineKeyboardButton(
            text(lang, "pay_ton"), callback_data=f"{prefix}:ton:{item_id}"
        ),
        types.InlineKeyboardButton(
            text(lang, "pay_trc20"), callback_data=f"{prefix}:trc20:{item_id}"
        ),
    )
    keyboard.row(
        types.InlineKeyboardButton(
            text(lang, "pay_erc20"), callback_data=f"{prefix}:erc20:{item_id}"
        ),
        types.InlineKeyboardButton(
            text(lang, "pay_sol"), callback_data=f"{prefix}:sol:{item_id}"
        ),
    )
    return keyboard


def topup_payment_keyboard(lang: str, topup_id: int) -> types.InlineKeyboardMarkup:
    keyboard = crypto_keyboard(lang, "topup", topup_id)
    keyboard.add(
        types.InlineKeyboardButton(text(lang, "home"), callback_data="nav:home")
    )
    return keyboard


def wallet_keyboard(
    lang: str, kind: str, item_id: int, url: str
) -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text(lang, "open_payment"), url=url))
    keyboard.add(
        types.InlineKeyboardButton(
            text(lang, "paid_submit"), callback_data=f"{kind}:hash:{item_id}"
        )
    )
    return keyboard


def callback_answer(
    call: types.CallbackQuery, message: str = "", alert: bool = False
) -> None:
    try:
        BOT.answer_callback_query(call.id, message, show_alert=alert)
    except ApiTelegramException as exc:
        LOGGER.debug("Callback answer failed: %s", exc)


def notify_admins(
    message: str, keyboard: types.InlineKeyboardMarkup | None = None
) -> None:
    for admin_id in admin_recipient_ids():
        try:
            BOT.send_message(admin_id, message, reply_markup=keyboard)
        except ApiTelegramException as exc:
            LOGGER.warning("Failed to notify admin %s: %s", admin_id, exc)


def payment_method_label(method_code: str) -> str:
    method = PAYMENT_METHODS.get(method_code)
    if method:
        return method.network
    if method_code == "card_ru":
        return "Карта РФ"
    if method_code == "card_ua":
        return "Карта Украины"
    if method_code == "card_gb":
        return "Карта Великобритании"
    if method_code == "cryptobot_check":
        return "CryptoBot check"
    if method_code == "telegram_stars":
        return "Telegram Stars"
    return method_code or "—"


def record_payment_event(
    *,
    kind: str,
    item_id: int,
    user_id: int,
    username: str,
    amount: str,
    method_code: str,
    tx_hash: str,
) -> bool:
    event = {
        "created_at": now_iso(),
        "event": "user_submitted_payment_hash",
        "kind": kind,
        "item_id": item_id,
        "user_id": user_id,
        "username": username,
        "amount": amount,
        "payment_method": method_code,
        "tx_hash": tx_hash,
        "verified": False,
    }
    try:
        PAYMENTS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with PAYMENT_LOG_LOCK, PAYMENTS_LOG_PATH.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")
        return True
    except OSError:
        LOGGER.exception("Failed to append payment event to %s", PAYMENTS_LOG_PATH)
        return False


def payment_submission_admin_text(
    *,
    kind: str,
    item_id: int,
    user_id: int,
    username: str,
    amount: str,
    method_code: str,
    tx_hash: str,
    saved: bool,
) -> str:
    title = "Пополнение баланса" if kind == "topup" else "Оплата заказа"
    reference_label = "CryptoBot check" if method_code == "cryptobot_check" else "TX"
    saved_text = (
        "✅ Данные сохранены в <code>payments.txt</code>"
        if saved
        else "⚠️ Не удалось записать данные в <code>payments.txt</code>"
    )
    return (
        f"🚨 <b>Пользователь нажал «Я оплатил» ({title})!</b>\n\n"
        "⚠️ <b>Платёж ещё не подтверждён — проверьте транзакцию.</b>\n\n"
        f"👤 Ник: <b>{html.escape(username)}</b>\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"🧾 Заявка: <b>#{item_id}</b>\n"
        f"💰 Сумма: <b>{html.escape(amount)}</b>\n"
        f"🌐 Метод: <b>{html.escape(payment_method_label(method_code))}</b>\n"
        f"🔗 {reference_label}: <code>{html.escape(tx_hash)}</code>\n\n"
        f"{saved_text}"
    )


def notify_order_payment_submission(order: dict[str, Any], reference: str) -> None:
    username = f"@{order['username']}" if order.get("username") else "—"
    method_code = str(order.get("payment_method") or "")
    currency = str(order.get("price_currency") or "usd")
    amount = format_price(int(order["total_kopecks"]), currency)
    saved = record_payment_event(
        kind="order",
        item_id=int(order["id"]),
        user_id=int(order["user_id"]),
        username=username,
        amount=amount,
        method_code=method_code,
        tx_hash=reference,
    )
    notify_admins(
        payment_submission_admin_text(
            kind="order",
            item_id=int(order["id"]),
            user_id=int(order["user_id"]),
            username=username,
            amount=amount,
            method_code=method_code,
            tx_hash=reference,
            saved=saved,
        )
        + "\n\n"
        + order_text(order, "en", True),
        order_admin_keyboard(int(order["id"]), "payment_review"),
    )


def notify_topup_payment_submission(topup: dict[str, Any], reference: str) -> None:
    username = f"@{topup['username']}" if topup.get("username") else "—"
    method_code = str(topup.get("payment_method") or "")
    amount = dollars(int(topup["amount_usd_cents"]))
    saved = record_payment_event(
        kind="topup",
        item_id=int(topup["id"]),
        user_id=int(topup["user_id"]),
        username=username,
        amount=amount,
        method_code=method_code,
        tx_hash=reference,
    )
    notify_admins(
        payment_submission_admin_text(
            kind="topup",
            item_id=int(topup["id"]),
            user_id=int(topup["user_id"]),
            username=username,
            amount=amount,
            method_code=method_code,
            tx_hash=reference,
            saved=saved,
        )
        + "\n\n"
        + topup_text(topup),
        topup_admin_keyboard(int(topup["id"])),
    )


def status_label(lang: str, status: str) -> str:
    key = f"status_{status}"
    return text(lang, key) if key in TEXTS["en"] else status


def order_text(
    order: dict[str, Any],
    lang: str = "en",
    admin: bool = False,
    display_currency: str | None = None,
) -> str:
    product = PRODUCTS.get(str(order["product_code"]))
    title = product.title(lang) if product else str(order["product_title"])
    currency = str(order.get("price_currency") or "rub")
    payment_method_code = str(order.get("payment_method") or "")
    quantity_label, recipient_label, total_label = ORDER_LABELS.get(
        lang, ORDER_LABELS["en"]
    )
    quantity_value = str(order["quantity"])
    if product and product.code == "steam":
        quantity_label = "Steam Wallet"
        quantity_value = dollars(int(order["quantity"]) * 100)
    elif product and product.code == "pubg_uc":
        quantity_label = "PUBG UC"
        quantity_value = f"{int(order['quantity']):,} UC"
    elif product and product.code == "stars":
        quantity_label = "Telegram Stars"
        quantity_value = f"{int(order['quantity']):,} Stars"
    elif product and product.code.startswith("telegram_premium_"):
        quantity_label = "Telegram Premium"
        period = {
            "telegram_premium_1m": "1 month",
            "telegram_premium_3m": "3 months",
            "telegram_premium_6m": "6 months",
            "telegram_premium_12m": "12 months",
        }.get(product.code, product.title(lang))
        package_count = int(order["quantity"])
        quantity_value = (
            period if package_count == 1 else f"{package_count:,} × {period}"
        )
    elif product and product.code.startswith("robux"):
        quantity_label = "Robux"
        quantity_value = f"{int(order['quantity']):,} R$"
    value = (
        f"<b>#{order['id']}</b> · {status_label(lang, str(order['status']))}\n\n"
        f"{html.escape(title)}\n"
        f"{html.escape(quantity_label)}: <b>{html.escape(quantity_value)}</b>\n"
        f"{html.escape(recipient_label)}: "
        f"<code>{html.escape(str(order['recipient']))}</code>\n"
        f"{html.escape(total_label)}: "
        f"<b>{display_minor(int(order['total_kopecks']), currency, display_currency) if display_currency else format_price(int(order['total_kopecks']), currency)}</b>"
    )
    discount_percent = int(order.get("discount_percent") or 0)
    wholesale_discount = int(order.get("wholesale_discount_percent") or 0)
    if discount_percent:
        discount_label, wholesale_label = DISCOUNT_LABELS.get(
            lang, DISCOUNT_LABELS["en"]
        )
        value += f"\n{discount_label}: <b>{discount_percent}%</b>"
        if wholesale_discount:
            value += f" ({wholesale_label}: {wholesale_discount}%)"
    if order.get("promo_code"):
        value += (
            f"\nPromo: <b>{html.escape(str(order['promo_code']))}</b>"
            f" · {int(order.get('promo_discount_percent') or 0)}%"
        )
    if order.get("payment_method"):
        method = PAYMENT_METHODS.get(payment_method_code)
        network = (
            method.network
            if method
            else text(lang, "pay_card_ru")
            if payment_method_code == "card_ru"
            else text(lang, "pay_card_ua")
            if payment_method_code == "card_ua"
            else text(lang, "pay_card_gb")
            if payment_method_code == "card_gb"
            else text(lang, "pay_cryptobot")
            if payment_method_code == "cryptobot_check"
            else text(lang, "pay_stars")
            if payment_method_code == "telegram_stars"
            else payment_method_code
        )
        value += f"\nNetwork: <b>{network}</b>"
    if order.get("payment_amount_text"):
        amount_label = (
            "Card amount"
            if payment_method_code.startswith("card_")
            else "CryptoBot amount"
            if payment_method_code == "cryptobot_check"
            else "Telegram Stars"
            if payment_method_code == "telegram_stars"
            else "Crypto"
        )
        value += (
            f"\n{amount_label}: <b>{html.escape(str(order['payment_amount_text']))}</b>"
        )
    if order.get("payment_comment"):
        value += (
            f"\nReference: <code>{html.escape(str(order['payment_comment']))}</code>"
        )
    if order.get("tx_hash"):
        value += f"\nTX: <code>{html.escape(str(order['tx_hash']))}</code>"
    if admin:
        value += f"\nCustomer: <code>{order['user_id']}</code>"
    return value


def topup_text(topup: dict[str, Any]) -> str:
    method_code = str(topup.get("payment_method") or "")
    method = PAYMENT_METHODS.get(method_code)
    network = (
        method.network
        if method
        else "Карта РФ"
        if method_code == "card_ru"
        else "Карта Украины"
        if method_code == "card_ua"
        else "Карта Великобритании"
        if method_code == "card_gb"
        else "CryptoBot check"
        if method_code == "cryptobot_check"
        else "Telegram Stars"
        if method_code == "telegram_stars"
        else "—"
    )
    return (
        f"<b>Top-up #{topup['id']}</b>\nStatus: <b>{topup['status']}</b>\n"
        f"Amount: <b>{dollars(int(topup['amount_usd_cents']))}</b>\n"
        f"Network: <b>{network}</b>\n"
        f"Payment: <b>{html.escape(str(topup.get('payment_amount_text') or '-'))}</b>\n"
        f"Reference: <code>{html.escape(str(topup.get('payment_comment') or '-'))}</code>\n"
        f"TX: <code>{html.escape(str(topup.get('tx_hash') or '-'))}</code>\n"
        f"Customer: <code>{topup['user_id']}</code>"
    )


def send_language(chat_id: int) -> None:
    send_visual(
        chat_id,
        "language",
        "<b>Оберіть мову · Выберите язык · Choose language</b>\n"
        "🇺🇦 Українська  ·  🇷🇺 Русский  ·  🇬🇧 English",
        reply_markup=language_keyboard(),
    )


def send_currency(chat_id: int) -> None:
    lang = language_of(chat_id)
    rates = currency_rates()
    send_visual(
        chat_id,
        "currency",
        text(lang, "currency_title")
        + "\n\n"
        + f"1 USD = <b>{rates['rub']:.2f} RUB</b>\n"
        + '<a href="https://www.exchangerate-api.com">Rates by ExchangeRate-API</a>',
        reply_markup=currency_keyboard(),
    )


def send_home(chat_id: int) -> None:
    lang = language_of(chat_id)
    display_currency = currency_of(chat_id)
    caption = (
        "<b>🌿 Jouli Market</b>\n"
        f"<blockquote>{text(lang, 'home_tagline')}</blockquote>\n"
        f"🟢 <b>{len(ACTIVE_PRODUCT_CODES)} товаров в каталоге</b>\n"
        "⭐ Stars  ·  🔫 UC  ·  🎫 Brawl Pass\n"
        "🎮 Robux  ·  🤖 AI-подписки\n"
        f"💱 {currency_label(display_currency)} · LIVE RATE\n\n"
        f"{text(lang, 'min_order_caption', _currency=display_currency)}\n"
        f"<b>{text(lang, 'giveaway')} / 48H</b>"
    )
    send_visual(
        chat_id,
        "welcome",
        caption,
        reply_markup=home_keyboard(lang, is_admin_user_id(chat_id)),
    )


def parse_referrer(raw: str | None) -> int | None:
    parts = (raw or "").split(maxsplit=1)
    return (
        int(parts[1][4:])
        if len(parts) == 2 and parts[1].startswith("ref_") and parts[1][4:].isdigit()
        else None
    )


def parse_start_promo(raw: str | None) -> str | None:
    parts = (raw or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].startswith("promo_"):
        return None
    code = normalize_promo_code(parts[1][6:])
    return code or None


def parse_miniapp_purchase(raw: str | None) -> tuple[Product, int] | None:
    parts = (raw or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].startswith("buy_"):
        return None
    product_code, separator, raw_quantity = parts[1][4:].rpartition("_")
    product = (
        PRODUCTS.get(product_code)
        if product_code in ACTIVE_PRODUCT_CODES
        else None
    )
    if not separator or not product or not raw_quantity.isdigit():
        return None
    quantity = int(raw_quantity)
    if not minimum_quantity(product) <= quantity <= product.maximum:
        return None
    if (
        product.category != "premium"
        and product_total_usd_cents(product, quantity) < MIN_ORDER_USD_CENTS
    ):
        return None
    return product, quantity


def quantity_prompt(lang: str, product: Product) -> str:
    key = (
        "stars_prompt"
        if product.code == "stars"
        else "robux_prompt"
        if product.code.startswith("robux")
        else "steam_amount_prompt"
        if product.code == "steam"
        else "uc_prompt"
        if product.code == "pubg_uc"
        else "quantity_prompt"
    )
    return text(
        lang,
        key,
        minimum=f"{minimum_quantity(product):,}",
        maximum=f"{product.maximum:,}",
    )


def recipient_prompt(lang: str, product: Product) -> str:
    return text(lang, f"recipient_{product.recipient_kind}")


def admin_dashboard_text() -> str:
    stats = DB.admin_stats()
    active = stats["payment_review"] + stats["paid"] + stats["processing"]
    return (
        "<b>🟢 JOULI MARKET · ADMIN CONTROL</b>\n"
        "<blockquote>Статистика магазина в реальном времени</blockquote>\n"
        f"👥 Пользователи: <b>{stats['users']:,}</b> · +{stats['users_24h']} за 24ч\n"
        f"🛒 Заказы: <b>{stats['orders']:,}</b> · +{stats['orders_24h']} за 24ч\n"
        f"🕒 Ждут оплату: <b>{stats['awaiting_payment']}</b>\n"
        f"🔎 На проверке: <b>{stats['payment_review']}</b>\n"
        f"⚙️ Активные в работе: <b>{active}</b>\n"
        f"✅ Завершено: <b>{stats['completed']}</b>\n"
        f"💳 Пополнения на проверке: <b>{stats['topups_review']}</b>\n"
        f"💡 Новые предложения: <b>{stats['suggestions_new']}</b>\n"
        f"🔎 Найдено лидов {html.escape(LEAD_MONITOR_CHAT)}: "
        f"<b>{stats['leads']}</b>\n"
        f"💰 Балансы пользователей: "
        f"<b>{dollars(stats['user_balance_usd_cents'])}</b>\n"
        f"💵 Завершённые продажи: <b>{dollars(stats['sales_usd_cents'])}</b>\n"
        f"⏳ Автоотмена без оплаты: <b>{ORDER_AUTO_CLOSE_MINUTES} минут</b>"
    )


def admin_dashboard_keyboard() -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton("👥 Пользователи / ID", callback_data="adm:users"),
        types.InlineKeyboardButton("➕ Пополнить баланс", callback_data="adm:balance"),
    )
    keyboard.add(
        types.InlineKeyboardButton(
            "🏷 Выдать скидку по ID", callback_data="adm:discount"
        )
    )
    keyboard.row(
        types.InlineKeyboardButton("📦 Активные заказы", callback_data="adm:orders"),
        types.InlineKeyboardButton("💳 Пополнения", callback_data="adm:topups"),
    )
    keyboard.add(
        types.InlineKeyboardButton("💡 Предложения", callback_data="adm:suggestions")
    )
    keyboard.row(
        types.InlineKeyboardButton(
            f"🔎 Лиды {LEAD_MONITOR_CHAT}", callback_data="adm:leads"
        ),
        types.InlineKeyboardButton("🔄 Обновить", callback_data="adm:home"),
    )
    keyboard.add(types.InlineKeyboardButton("⌂ Главное меню", callback_data="nav:home"))
    return keyboard


def send_admin_dashboard(chat_id: int) -> None:
    send_visual(
        chat_id,
        "admin",
        admin_dashboard_text(),
        reply_markup=admin_dashboard_keyboard(),
    )


@BOT.message_handler(commands=["start", "menu"])
def start(message: types.Message) -> None:
    referrer = parse_referrer(message.text)
    promo_payload = parse_start_promo(message.text)
    miniapp_purchase = parse_miniapp_purchase(message.text)
    created = DB.ensure_user(message.from_user, referrer)
    DB.clear_state(message.chat.id)
    if created and referrer:
        try:
            referrer_user = DB.user(referrer)
            if referrer_user:
                referrer_lang = language_of(referrer)
                BOT.send_message(
                    referrer,
                    text(referrer_lang, "referral_joined")
                    + "\n"
                    + text(
                        referrer_lang,
                        "referral_bonus_line",
                        bonus=REFERRAL_DISCOUNT_PERCENT,
                        discount=DB.effective_discount(referrer_user),
                    ),
                )
        except ApiTelegramException as exc:
            LOGGER.debug("Referral notification failed: %s", exc)
    if not DB.language(message.chat.id):
        send_language(message.chat.id)
        return
    if not DB.currency(message.chat.id):
        send_currency(message.chat.id)
        return
    if promo_payload:
        lang = language_of(message.chat.id)
        status, discount, code = DB.activate_promo(
            message.from_user.id, promo_payload
        )
        key = {
            "activated": "promo_activated",
            "invalid": "promo_invalid",
            "used": "promo_used",
            "active": "promo_active",
        }[status]
        BOT.send_message(
            message.chat.id,
            text(
                lang,
                key,
                code=html.escape(code),
                discount=discount,
            ),
            reply_markup=profile_keyboard(lang),
        )
        return
    if miniapp_purchase:
        product, quantity = miniapp_purchase
        DB.set_state(
            message.chat.id,
            "recipient",
            {"product": product.code, "quantity": quantity},
        )
        lang = language_of(message.chat.id)
        display_currency = currency_of(message.chat.id)
        BOT.send_message(
            message.chat.id,
            "<b>🛍 Mini App · "
            + html.escape(product.title(lang))
            + "</b>\n"
            + f"Количество: <b>{quantity:,}</b>\n"
            + f"Сумма до скидок: <b>{format_usd_cents(product_total_usd_cents(product, quantity), display_currency)}</b>\n\n"
            + recipient_prompt(lang, product),
        )
        return
    send_home(message.chat.id)


@BOT.message_handler(commands=["language"])
def language_command(message: types.Message) -> None:
    DB.ensure_user(message.from_user)
    send_language(message.chat.id)


@BOT.message_handler(commands=["currency"])
def currency_command(message: types.Message) -> None:
    DB.ensure_user(message.from_user)
    if not DB.language(message.chat.id):
        send_language(message.chat.id)
        return
    send_currency(message.chat.id)


@BOT.message_handler(commands=["about"])
def about_command(message: types.Message) -> None:
    DB.ensure_user(message.from_user)
    if not DB.language(message.chat.id):
        send_language(message.chat.id)
        return
    lang = language_of(message.chat.id)
    send_visual(
        message.chat.id,
        "about",
        text(
            lang,
            "about_text",
            owner=html.escape(OWNER_USERNAME),
            second_admin=html.escape(", ".join(sorted(ADMIN_USERNAMES)) or "—"),
            support=html.escape(SUPPORT_USERNAME),
        ),
        reply_markup=back(lang),
    )


@BOT.message_handler(commands=["admin"])
def admin(message: types.Message) -> None:
    DB.ensure_user(message.from_user)
    DB.clear_state(message.chat.id)
    lang = language_of(message.chat.id)
    if not is_admin_user(message.from_user):
        BOT.send_message(
            message.chat.id, text(lang, "access_denied")
        )
        return
    send_admin_dashboard(message.chat.id)


@BOT.callback_query_handler(func=lambda call: True)
def callbacks(call: types.CallbackQuery) -> None:
    if not call.message:
        return
    DB.ensure_user(call.from_user)
    data = call.data or ""
    lang = language_of(call.from_user.id)
    try:
        if data.startswith("lang:"):
            selected = data.split(":", 1)[1]
            DB.set_language(call.from_user.id, selected)
            DB.clear_state(call.from_user.id)
            BOT.send_message(call.from_user.id, text(selected, "language_saved"))
            send_currency(call.from_user.id)
            return

        if data.startswith("cur:"):
            selected = data.split(":", 1)[1]
            DB.set_currency(call.from_user.id, selected)
            DB.clear_state(call.from_user.id)
            lang = language_of(call.from_user.id)
            BOT.send_message(
                call.from_user.id,
                text(
                    lang,
                    "currency_saved",
                    currency=currency_label(selected),
                ),
            )
            send_home(call.from_user.id)
            return

        if not DB.language(call.from_user.id):
            send_language(call.from_user.id)
            return
        if not DB.currency(call.from_user.id):
            send_currency(call.from_user.id)
            return

        display_currency = currency_of(call.from_user.id)

        disabled_payment_prefixes = (
            "pay:card:",
            "pay:cryptobot:",
            "pay:stars:",
            "topup:card:",
            "topup:cryptobot:",
            "topup:stars:",
        )
        if data.startswith(disabled_payment_prefixes):
            DB.clear_state(call.from_user.id)
            callback_answer(call, text(lang, "unknown"), True)
            send_home(call.from_user.id)
            return

        if data.startswith(("nav:", "cat:", "rbx:", "ai:", "view:")):
            DB.clear_state(call.from_user.id)

        if data == "nav:home":
            send_home(call.from_user.id)
        elif data == "nav:language":
            send_language(call.from_user.id)
        elif data == "nav:currency":
            send_currency(call.from_user.id)
        elif data == "nav:catalog":
            send_visual(
                call.from_user.id,
                "catalog",
                "🟢 "
                + text(lang, "catalog_title", _currency=display_currency)
                + "\n\n"
                + text(
                    lang,
                    "wholesale_notice",
                    discount=WHOLESALE_DISCOUNT_PERCENT,
                    minimum=format_usd_cents(
                        WHOLESALE_MIN_USD_CENTS, display_currency
                    ),
                ),
                reply_markup=category_keyboard(lang),
            )
        elif data.startswith("cat:"):
            category = data.split(":", 1)[1]
            if category not in CATEGORIES:
                callback_answer(call, text(lang, "unknown"), True)
                return
            if category == "ai":
                send_visual(
                    call.from_user.id,
                    "ai",
                    "🟢 "
                    + text(
                        lang,
                        "category_title",
                        title=text(lang, "cat_ai"),
                    ),
                        reply_markup=ai_subcategory_keyboard(lang),
                )
            elif category == "roblox":
                send_visual(
                    call.from_user.id,
                    "roblox",
                    text(lang, "roblox_choose"),
                    reply_markup=roblox_subcategory_keyboard(lang),
                )
            else:
                title = text(lang, f"cat_{category}")
                send_visual(
                    call.from_user.id,
                    category,
                    "🟢 " + text(lang, "category_title", title=title),
                    reply_markup=products_keyboard(
                        lang, category, display_currency
                    ),
                )
        elif data.startswith("ai:"):
            subgroup = data.split(":", 1)[1]
            if subgroup not in AI_SUBCATEGORIES:
                callback_answer(call, text(lang, "unknown"), True)
                return
            send_visual(
                call.from_user.id,
                f"ai_{subgroup}",
                "🟢 "
                + text(
                    lang,
                    "category_title",
                    title=AI_SUBCATEGORY_LABELS[subgroup],
                ),
                reply_markup=product_list_keyboard(
                    lang,
                    AI_SUBCATEGORIES[subgroup],
                    "cat:ai",
                    display_currency,
                ),
            )
        elif data.startswith("rbx:"):
            subgroup = data.split(":", 1)[1]
            if subgroup not in ROBLOX_SUBCATEGORIES:
                callback_answer(call, text(lang, "unknown"), True)
                return
            title_key = {
                "account": "roblox_account",
                "gamepass": "roblox_gamepass",
                "gifts": "roblox_gifts",
            }[subgroup]
            send_visual(
                call.from_user.id,
                f"roblox_{subgroup}",
                "🟢 "
                + text(
                    lang,
                    "category_title",
                    title=text(lang, title_key),
                ),
                reply_markup=roblox_products_keyboard(
                    lang, subgroup, display_currency
                ),
            )
        elif data == "nav:orders":
            orders = DB.user_orders(call.from_user.id)
            value = (
                text(lang, "orders_title")
                + "\n\n"
                + (
                    "\n\n".join(
                        order_text(
                            item,
                            lang,
                            display_currency=display_currency,
                        )
                        for item in orders
                    )
                    if orders
                    else text(lang, "no_orders")
                )
            )
            send_visual(
                call.from_user.id,
                "orders",
                value,
                reply_markup=back(lang),
            )
        elif data == "nav:promo":
            DB.set_state(call.from_user.id, "promo_code")
            send_visual(
                call.from_user.id,
                "promo",
                text(lang, "promo_prompt"),
                reply_markup=back(lang, "nav:profile"),
            )
        elif data == "nav:profile":
            user = DB.user(call.from_user.id)
            username = BOT.get_me().username
            value = text(
                lang,
                "profile_text",
                user_id=call.from_user.id,
                balance=format_usd_cents(
                    int(user["balance_usd_cents"]), display_currency
                ),
                discount=DB.effective_discount(user),
                referrals=DB.referrals(call.from_user.id),
                referral_url=f"https://t.me/{username}?start=ref_{call.from_user.id}",
            )
            value += (
                "\n"
                + text(lang, "currency")
                + f": <b>{html.escape(currency_label(display_currency))}</b>"
            )
            giveaway_uses = int(user.get("giveaway_discount_uses") or 0)
            value += text(
                lang,
                "profile_referral_bonus",
                discount=int(user.get("referral_discount_percent") or 0),
                maximum=MAX_TOTAL_DISCOUNT_PERCENT,
            )
            if giveaway_uses:
                value += text(lang, "profile_bonus", uses=giveaway_uses)
            promo_code = str(user.get("promo_code") or "")
            promo_discount = int(user.get("promo_discount_percent") or 0)
            if promo_code and promo_discount:
                value += text(
                    lang,
                    "promo_profile",
                    code=html.escape(promo_code),
                    discount=promo_discount,
                )
            send_visual(
                call.from_user.id,
                "profile",
                value,
                reply_markup=profile_keyboard(lang),
            )
        elif data == "nav:topup":
            minimum_cents = minimum_topup_cents()
            minimum_amount = format(
                Decimal(minimum_cents) / Decimal("100"), ".2f"
            )
            keyboard = types.InlineKeyboardMarkup(row_width=2)
            keyboard.row(
                types.InlineKeyboardButton(
                    format_usd_cents(minimum_cents, display_currency),
                    callback_data=f"topup:amount:{minimum_amount}",
                ),
                types.InlineKeyboardButton(
                    format_usd_cents(2_500, display_currency),
                    callback_data="topup:amount:25",
                ),
            )
            keyboard.row(
                types.InlineKeyboardButton(
                    format_usd_cents(5_000, display_currency),
                    callback_data="topup:amount:50",
                ),
                types.InlineKeyboardButton(
                    format_usd_cents(10_000, display_currency),
                    callback_data="topup:amount:100",
                ),
            )
            keyboard.row(
                types.InlineKeyboardButton(
                    text(lang, "custom_amount"), callback_data="topup:custom"
                ),
            )
            keyboard.add(
                types.InlineKeyboardButton(text(lang, "home"), callback_data="nav:home")
            )
            send_visual(
                call.from_user.id,
                "wallet",
                text(lang, "add_funds", _currency=display_currency)
                + "\n<blockquote>TON · USDT · SOL</blockquote>",
                reply_markup=keyboard,
            )
        elif data == "nav:support":
            send_home(call.from_user.id)
        elif data == "nav:nft_buyback":
            DB.clear_state(call.from_user.id)
            send_home(call.from_user.id)
        elif data == "nav:suggestion":
            DB.set_state(call.from_user.id, "suggestion")
            send_visual(
                call.from_user.id,
                "suggestion",
                text(lang, "suggestion_prompt"),
                reply_markup=back(lang),
            )
        elif data == "nav:about":
            send_visual(
                call.from_user.id,
                "about",
                text(
                    lang,
                    "about_text",
                    owner=html.escape(OWNER_USERNAME),
                    second_admin=html.escape(
                        ", ".join(sorted(ADMIN_USERNAMES)) or "—"
                    ),
                    support=html.escape(SUPPORT_USERNAME),
                ),
                reply_markup=back(lang),
            )
        elif data == "nav:giveaway":
            send_visual(
                call.from_user.id,
                "giveaway",
                giveaway_message(call.from_user.id, lang),
                reply_markup=back(lang),
            )
        elif data == "nav:help":
            send_home(call.from_user.id)
        elif data.startswith("view:"):
            product_code = data.split(":", 1)[1]
            product = (
                PRODUCTS.get(product_code)
                if product_code in ACTIVE_PRODUCT_CODES
                else None
            )
            if not product:
                callback_answer(call, text(lang, "product_not_found"), True)
                return
            send_visual(
                call.from_user.id,
                product.category,
                product_card_text(lang, product, display_currency),
                reply_markup=product_card_keyboard(lang, product),
                product_code=product.code,
            )
        elif data.startswith("prd:"):
            product_code = data.split(":", 1)[1]
            product = (
                PRODUCTS.get(product_code)
                if product_code in ACTIVE_PRODUCT_CODES
                else None
            )
            if not product:
                callback_answer(call, text(lang, "product_not_found"), True)
                return
            if product.custom_quantity:
                DB.set_state(call.from_user.id, "quantity", {"product": product.code})
                BOT.send_message(call.from_user.id, quantity_prompt(lang, product))
            else:
                DB.set_state(
                    call.from_user.id,
                    "recipient",
                    {"product": product.code, "quantity": 1},
                )
                BOT.send_message(call.from_user.id, recipient_prompt(lang, product))
        elif data.startswith("pay:crypto:"):
            _, _, method, raw_id = data.split(":")
            send_order_invoice(call, int(raw_id), method)
        elif data.startswith("pay:card:"):
            _, _, country, raw_id = data.split(":")
            send_card_payment_support(call, "order", int(raw_id), country)
        elif data.startswith("pay:cryptobot:"):
            start_cryptobot_payment(call, "order", int(data.rsplit(":", 1)[1]))
        elif data.startswith("pay:stars:"):
            send_stars_invoice(call, "order", int(data.rsplit(":", 1)[1]))
        elif data.startswith("pay:balance:"):
            pay_balance(call, int(data.rsplit(":", 1)[1]))
        elif data.startswith("pay:hash:"):
            order_id = int(data.rsplit(":", 1)[1])
            order = DB.order(order_id)
            method = (
                PAYMENT_METHODS.get(str(order.get("payment_method"))) if order else None
            )
            DB.set_state(call.from_user.id, "order_hash", {"id": order_id})
            BOT.send_message(
                call.from_user.id,
                text(
                    lang, "hash_prompt", network=method.network if method else "crypto"
                ),
            )
        elif data.startswith("topup:amount:"):
            try:
                amount = Decimal(data.rsplit(":", 1)[1])
                if (
                    not amount.is_finite()
                    or amount != amount.quantize(Decimal("0.01"))
                ):
                    raise InvalidOperation
                cents = int(amount * 100)
                if not minimum_topup_cents() <= cents <= MAX_TOPUP_CENTS:
                    raise ValueError
                create_topup_checkout(call.from_user.id, cents)
            except (InvalidOperation, ValueError):
                callback_answer(
                    call,
                    text(
                        lang,
                        "custom_amount_prompt",
                        _currency=display_currency,
                    ),
                    True,
                )
        elif data == "topup:custom":
            DB.set_state(call.from_user.id, "topup_amount")
            BOT.send_message(
                call.from_user.id,
                text(
                    lang,
                    "custom_amount_prompt",
                    _currency=display_currency,
                ),
            )
        elif data == "topup:stars:direct":
            callback_answer(call)
            DB.set_state(call.from_user.id, "topup_stars_amount")
            BOT.send_message(
                call.from_user.id,
                text(
                    lang,
                    "topup_stars_amount_prompt",
                    _currency=display_currency,
                ),
            )
        elif data.startswith("topup:pay:"):
            _, _, method, raw_id = data.split(":")
            send_topup_invoice(call, int(raw_id), method)
        elif data.startswith("topup:card:"):
            _, _, country, raw_id = data.split(":")
            send_card_payment_support(call, "topup", int(raw_id), country)
        elif data.startswith("topup:cryptobot:"):
            start_cryptobot_payment(call, "topup", int(data.rsplit(":", 1)[1]))
        elif data.startswith("topup:stars:"):
            send_stars_invoice(call, "topup", int(data.rsplit(":", 1)[1]))
        elif data.startswith("topup:hash:"):
            topup_id = int(data.rsplit(":", 1)[1])
            topup = DB.topup(topup_id)
            method = (
                PAYMENT_METHODS.get(str(topup.get("payment_method"))) if topup else None
            )
            DB.set_state(call.from_user.id, "topup_hash", {"id": topup_id})
            BOT.send_message(
                call.from_user.id,
                text(
                    lang, "hash_prompt", network=method.network if method else "crypto"
                ),
            )
        elif data.startswith(("adm:", "ord:", "tpu:", "sug:", "nft:")):
            admin_callback(call)
        else:
            callback_answer(call, text(lang, "unknown"), True)
    except Exception:
        LOGGER.exception("Callback failed: %s", data)
        callback_answer(call, text(lang, "generic_error"), True)
    finally:
        callback_answer(call)


def invoice_caption(
    lang: str,
    title_key: str,
    item_id: int,
    fiat: str,
    invoice: Invoice,
) -> str:
    return text(
        lang,
        "payment_caption",
        title=text(lang, title_key),
        item_id=item_id,
        fiat=fiat,
        crypto=invoice.amount_text,
        network=invoice.method.network,
        wallet=invoice.method.wallet,
        reference=invoice.reference,
    )


def send_order_invoice(
    call: types.CallbackQuery, order_id: int, method_code: str
) -> None:
    lang = language_of(call.from_user.id)
    order = DB.order(order_id)
    if (
        method_code not in PAYMENT_METHODS
        or not order
        or order["user_id"] != call.from_user.id
        or order["status"] != "awaiting_payment"
    ):
        callback_answer(call, text(lang, "order_unavailable"), True)
        return
    try:
        currency = str(order.get("price_currency") or "rub")
        invoice = MARKET.invoice(
            method_code,
            f"NEX-O-{order_id}",
            int(order["total_kopecks"]),
            currency,
        )
    except (requests.RequestException, KeyError, RuntimeError, InvalidOperation):
        LOGGER.exception("Failed to prepare order invoice")
        BOT.send_message(call.from_user.id, text(lang, "rate_error"))
        return
    DB.attach_order_payment(
        order_id, method_code, invoice.amount_text, invoice.reference
    )
    safe_send_photo(
        call.from_user.id,
        qr_image(invoice),
        invoice_caption(
            lang,
            "order_payment_title",
            order_id,
            display_minor(
                int(order["total_kopecks"]),
                currency,
                currency_of(call.from_user.id),
            ),
            invoice,
        ),
        reply_markup=wallet_keyboard(lang, "pay", order_id, invoice.open_url),
    )


def pay_balance(call: types.CallbackQuery, order_id: int) -> None:
    lang = language_of(call.from_user.id)
    order = DB.order(order_id)
    if not order or order["user_id"] != call.from_user.id:
        callback_answer(call, text(lang, "order_unavailable"), True)
        return
    try:
        charge = MARKET.usd_cents(
            int(order["total_kopecks"]), str(order.get("price_currency") or "rub")
        )
    except (requests.RequestException, KeyError, RuntimeError, InvalidOperation):
        BOT.send_message(call.from_user.id, text(lang, "rate_error"))
        return
    try:
        paid = DB.pay_from_balance(order_id, call.from_user.id, charge)
    except ValueError:
        callback_answer(
            call,
            text(
                lang,
                "insufficient",
                amount=format_usd_cents(charge, currency_of(call.from_user.id)),
            ),
            True,
        )
        return
    if paid:
        send_visual(
            call.from_user.id,
            "success",
            text(lang, "balance_paid", order_id=order_id),
            reply_markup=back(lang),
        )
        notify_admins(
            "💰 <b>Order paid from balance</b>\n\n" + order_text(paid, "en", True),
            order_admin_keyboard(order_id, "paid"),
        )


def create_topup_checkout(user_id: int, cents: int) -> None:
    lang = language_of(user_id)
    topup_id = DB.create_topup(user_id, cents)
    send_visual(
        user_id,
        "payment",
        text(lang, "choose_crypto"),
        reply_markup=topup_payment_keyboard(lang, topup_id),
    )


def send_stars_invoice_to_user(user_id: int, kind: str, item_id: int) -> str | None:
    lang = language_of(user_id)
    display_currency = currency_of(user_id)
    if kind == "order":
        item = DB.order(item_id)
        unavailable_key = "order_unavailable"
        if item:
            minor = int(item["total_kopecks"])
            currency = str(item.get("price_currency") or "usd")
            fiat = display_minor(minor, currency, display_currency)
            kind_label = "Заказ" if lang == "ru" else "Order"
    elif kind == "topup":
        item = DB.topup(item_id)
        unavailable_key = "topup_unavailable"
        if item:
            minor = int(item["amount_usd_cents"])
            currency = "usd"
            fiat = format_usd_cents(minor, display_currency)
            kind_label = "Пополнение" if lang == "ru" else "Top-up"
    else:
        return text(lang, "unknown")
    if (
        not item
        or int(item["user_id"]) != user_id
        or str(item["status"]) != "awaiting_payment"
    ):
        return text(lang, unavailable_key)

    try:
        usd_cents = MARKET.usd_cents(minor, currency)
        stars = stars_for_minor(minor, currency)
        payload = DB.create_star_payment(kind, item_id, user_id, usd_cents, stars)
        if not payload:
            return text(lang, unavailable_key)
        BOT.send_invoice(
            user_id,
            title=text(lang, "stars_invoice_title"),
            description=text(
                lang,
                "stars_invoice_desc",
                kind=kind_label,
                item_id=item_id,
                fiat=fiat,
                rate=star_rate_text(),
            ),
            invoice_payload=payload,
            provider_token=None,
            currency="XTR",
            prices=[types.LabeledPrice(label=kind_label, amount=stars)],
            protect_content=True,
        )
        send_visual(
            user_id,
            "stars_payment",
            text(
                lang,
                "stars_invoice_sent",
                stars=stars,
                rate=star_rate_text(),
            ),
            reply_markup=back(lang),
        )
        return None
    except Exception:
        LOGGER.exception("Failed to create Telegram Stars invoice")
        return text(lang, "generic_error")


def send_stars_invoice(
    call: types.CallbackQuery, kind: str, item_id: int
) -> None:
    error = send_stars_invoice_to_user(call.from_user.id, kind, item_id)
    if error:
        callback_answer(call, error, True)


def start_cryptobot_payment(call: types.CallbackQuery, kind: str, item_id: int) -> None:
    lang = language_of(call.from_user.id)
    if kind == "order":
        item = DB.order(item_id)
        if (
            not item
            or item["user_id"] != call.from_user.id
            or item["status"] != "awaiting_payment"
        ):
            callback_answer(call, text(lang, "order_unavailable"), True)
            return
        currency = str(item.get("price_currency") or "usd")
        amount = format_price(int(item["total_kopecks"]), currency)
        DB.attach_order_payment(item_id, "cryptobot_check", amount, f"CB-O-{item_id}")
        state = "order_cryptobot"
    else:
        item = DB.topup(item_id)
        if (
            not item
            or item["user_id"] != call.from_user.id
            or item["status"] != "awaiting_payment"
        ):
            callback_answer(call, text(lang, "topup_unavailable"), True)
            return
        amount = dollars(int(item["amount_usd_cents"]))
        DB.attach_topup_payment(item_id, "cryptobot_check", amount, f"CB-T-{item_id}")
        state = "topup_cryptobot"
    DB.set_state(call.from_user.id, state, {"id": item_id})
    BOT.send_message(
        call.from_user.id,
        text(lang, "cryptobot_prompt", item_id=item_id, amount=amount),
        reply_markup=cryptobot_keyboard(lang),
    )


def send_card_payment_support(
    call: types.CallbackQuery, kind: str, item_id: int, country: str
) -> None:
    lang = language_of(call.from_user.id)
    if country not in {"ru", "ua", "gb"} or kind not in {"order", "topup"}:
        callback_answer(call, text(lang, "unknown"), True)
        return
    method_code = f"card_{country}"
    country_label = text(lang, f"pay_card_{country}")
    if kind == "order":
        item = DB.order(item_id)
        if (
            not item
            or item["user_id"] != call.from_user.id
            or item["status"] != "awaiting_payment"
        ):
            callback_answer(call, text(lang, "order_unavailable"), True)
            return
        currency = str(item.get("price_currency") or "usd")
        amount = display_minor(
            int(item["total_kopecks"]),
            currency,
            currency_of(call.from_user.id),
        )
        first_request = str(item.get("payment_method") or "") != method_code
        DB.attach_order_payment(
            item_id, method_code, amount, f"CARD-{country.upper()}-O-{item_id}"
        )
        if first_request:
            notify_admins(
                f"💳 <b>Запрос оплаты картой · {country.upper()}</b>\n\n"
                + order_text(DB.order(item_id) or item, "ru", True),
                order_admin_keyboard(item_id, "awaiting_payment"),
            )
        item_label = text(lang, "order_payment_title")
    else:
        item = DB.topup(item_id)
        if (
            not item
            or item["user_id"] != call.from_user.id
            or item["status"] != "awaiting_payment"
        ):
            callback_answer(call, text(lang, "topup_unavailable"), True)
            return
        amount = format_usd_cents(
            int(item["amount_usd_cents"]), currency_of(call.from_user.id)
        )
        first_request = str(item.get("payment_method") or "") != method_code
        DB.attach_topup_payment(
            item_id, method_code, amount, f"CARD-{country.upper()}-T-{item_id}"
        )
        if first_request:
            notify_admins(
                f"💳 <b>Запрос пополнения картой · {country.upper()}</b>\n\n"
                + topup_text(DB.topup(item_id) or item),
                topup_admin_keyboard(item_id),
            )
        item_label = text(lang, "topup_payment_title")
    BOT.send_message(
        call.from_user.id,
        text(
            lang,
            "card_payment_info",
            country=country_label,
            item=item_label,
            item_id=item_id,
            amount=amount,
        ),
        reply_markup=support_keyboard(lang),
    )


def send_topup_invoice(
    call: types.CallbackQuery, topup_id: int, method_code: str
) -> None:
    lang = language_of(call.from_user.id)
    topup = DB.topup(topup_id)
    if (
        method_code not in PAYMENT_METHODS
        or not topup
        or topup["user_id"] != call.from_user.id
        or topup["status"] != "awaiting_payment"
    ):
        callback_answer(call, text(lang, "topup_unavailable"), True)
        return
    try:
        invoice = MARKET.invoice(
            method_code,
            f"NEX-T-{topup_id}",
            int(topup["amount_usd_cents"]),
            "usd",
        )
    except (requests.RequestException, KeyError, RuntimeError, InvalidOperation):
        LOGGER.exception("Failed to prepare top-up invoice")
        BOT.send_message(call.from_user.id, text(lang, "rate_error"))
        return
    DB.attach_topup_payment(
        topup_id, method_code, invoice.amount_text, invoice.reference
    )
    safe_send_photo(
        call.from_user.id,
        qr_image(invoice),
        invoice_caption(
            lang,
            "topup_payment_title",
            topup_id,
            format_usd_cents(
                int(topup["amount_usd_cents"]), currency_of(call.from_user.id)
            ),
            invoice,
        ),
        reply_markup=wallet_keyboard(lang, "topup", topup_id, invoice.open_url),
    )


def order_admin_keyboard(order_id: int, status: str) -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup()
    if status in {"awaiting_payment", "payment_review"}:
        keyboard.add(
            types.InlineKeyboardButton(
                "✓ Отметить оплаченным", callback_data=f"ord:{order_id}:paid"
            )
        )
    elif status == "paid":
        keyboard.add(
            types.InlineKeyboardButton(
                "▶ Взять в работу", callback_data=f"ord:{order_id}:processing"
            )
        )
    elif status == "processing":
        keyboard.add(
            types.InlineKeyboardButton(
                "🏁 Завершить", callback_data=f"ord:{order_id}:completed"
            )
        )
    if status not in {"completed", "cancelled"}:
        keyboard.add(
            types.InlineKeyboardButton(
                "✕ Отменить", callback_data=f"ord:{order_id}:cancelled"
            )
        )
    keyboard.add(types.InlineKeyboardButton("‹ Админ-панель", callback_data="adm:home"))
    return keyboard


def topup_admin_keyboard(topup_id: int) -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton("✓ Зачислить", callback_data=f"tpu:{topup_id}:yes"),
        types.InlineKeyboardButton("✕ Отклонить", callback_data=f"tpu:{topup_id}:no"),
    )
    keyboard.add(types.InlineKeyboardButton("‹ Админ-панель", callback_data="adm:home"))
    return keyboard


def admin_callback(call: types.CallbackQuery) -> None:
    if not is_admin_user(call.from_user):
        callback_answer(call, "Access denied", True)
        return
    data = call.data or ""
    if data == "adm:home":
        send_admin_dashboard(call.from_user.id)
    elif data == "adm:users":
        users = DB.recent_users()
        if not users:
            BOT.send_message(
                call.from_user.id,
                "<b>👥 Пользователи</b>\n\nПользователей пока нет.",
                reply_markup=admin_dashboard_keyboard(),
            )
            return
        lines = [
            "<b>👥 Последние пользователи</b>",
            "<blockquote>ID можно скопировать нажатием</blockquote>",
        ]
        for user in users:
            username = f"@{user['username']}" if user.get("username") else "без username"
            name = str(user.get("first_name") or "—")
            lines.append(
                f"\n<code>{user['user_id']}</code> · "
                f"<b>{html.escape(name)}</b> · {html.escape(username)}\n"
                f"Баланс: <b>{dollars(int(user['balance_usd_cents']))}</b> · "
                f"Скидка: <b>{DB.effective_discount(user)}%</b> · "
                f"Заказов: <b>{int(user['orders_count'])}</b>"
            )
        BOT.send_message(
            call.from_user.id,
            "\n".join(lines),
            reply_markup=admin_dashboard_keyboard(),
        )
    elif data == "adm:balance":
        DB.set_state(call.from_user.id, "admin_balance_user")
        BOT.send_message(
            call.from_user.id,
            "<b>➕ Пополнение баланса</b>\n\n"
            "Отправьте цифровой Telegram ID пользователя. "
            "Он отображается в разделе «Пользователи / ID».\n\n"
            "Для отмены нажмите /admin.",
        )
    elif data == "adm:discount":
        DB.set_state(call.from_user.id, "admin_discount_user")
        BOT.send_message(
            call.from_user.id,
            "<b>🏷 Выдача персональной скидки</b>\n\n"
            "Отправьте цифровой Telegram ID пользователя. "
            "Он отображается в разделе «Пользователи / ID».\n\n"
            "Для отмены нажмите /admin.",
        )
    elif data == "adm:orders":
        orders = DB.review_orders()
        if not orders:
            BOT.send_message(
                call.from_user.id,
                "<b>📦 Активные заказы</b>\n\nОчередь пуста.",
                reply_markup=admin_dashboard_keyboard(),
            )
        for order in orders:
            BOT.send_message(
                call.from_user.id,
                order_text(order, "ru", True),
                reply_markup=order_admin_keyboard(
                    int(order["id"]), str(order["status"])
                ),
            )
    elif data == "adm:topups":
        topups = DB.review_topups()
        if not topups:
            BOT.send_message(
                call.from_user.id,
                "<b>💳 Пополнения</b>\n\nОчередь пуста.",
                reply_markup=admin_dashboard_keyboard(),
            )
        for topup in topups:
            BOT.send_message(
                call.from_user.id,
                topup_text(topup),
                reply_markup=topup_admin_keyboard(int(topup["id"])),
            )
    elif data == "adm:suggestions":
        suggestions = DB.review_suggestions()
        if not suggestions:
            BOT.send_message(
                call.from_user.id,
                "<b>💡 Предложения</b>\n\nНовых предложений нет.",
                reply_markup=admin_dashboard_keyboard(),
            )
        for suggestion in suggestions:
            username = (
                f"@{suggestion['username']}" if suggestion.get("username") else "—"
            )
            keyboard = types.InlineKeyboardMarkup()
            keyboard.row(
                types.InlineKeyboardButton(
                    "📌 В планы", callback_data=f"sug:{suggestion['id']}:planned"
                ),
                types.InlineKeyboardButton(
                    "🗑 Закрыть",
                    callback_data=f"sug:{suggestion['id']}:dismissed",
                ),
            )
            keyboard.add(
                types.InlineKeyboardButton("‹ Админ-панель", callback_data="adm:home")
            )
            BOT.send_message(
                call.from_user.id,
                f"<b>💡 Предложение #{suggestion['id']}</b>\n"
                f"Пользователь: <code>{suggestion['user_id']}</code> · "
                f"{html.escape(username)}\n\n{html.escape(str(suggestion['body']))}",
                reply_markup=keyboard,
            )
    elif data == "adm:nft":
        send_admin_dashboard(call.from_user.id)
    elif data == "adm:leads":
        leads = DB.recent_monitored_leads()
        if not leads:
            BOT.send_message(
                call.from_user.id,
                f"<b>🔎 Лиды {html.escape(LEAD_MONITOR_CHAT)}</b>\n\n"
                "Подходящих новых сообщений пока нет.",
                reply_markup=admin_dashboard_keyboard(),
            )
        for lead in leads:
            try:
                product_codes = json.loads(str(lead["product_codes"]))
            except (json.JSONDecodeError, TypeError):
                product_codes = []
            product_names = ", ".join(
                PRODUCTS[code].titles["ru"]
                for code in product_codes
                if code in PRODUCTS
            )
            username = f"@{lead['username']}" if lead.get("username") else "—"
            link = f"https://t.me/{LEAD_MONITOR_CHAT.lstrip('@')}/{lead['message_id']}"
            BOT.send_message(
                call.from_user.id,
                f"<b>🔎 Лид #{lead['id']} · {html.escape(str(lead['intent']))}</b>\n"
                f"Автор: {html.escape(username)} · "
                f"<code>{lead.get('user_id') or '—'}</code>\n"
                f"Товары: <b>{html.escape(product_names or '—')}</b>\n\n"
                f"{html.escape(str(lead['body']))}\n\n"
                f"<a href=\"{link}\">Открыть сообщение в "
                f"{html.escape(LEAD_MONITOR_CHAT)}</a>",
                reply_markup=admin_dashboard_keyboard(),
                disable_web_page_preview=True,
            )
    elif data.startswith("ord:"):
        _, raw_id, status = data.split(":")
        order = DB.set_order_status(int(raw_id), status)
        if order:
            lang = language_of(int(order["user_id"]))
            BOT.send_message(
                int(order["user_id"]),
                text(
                    lang,
                    "status_update",
                    order_id=raw_id,
                    status=status_label(lang, status),
                ),
            )
            callback_answer(call, f"Заказ #{raw_id}: {status}")
        else:
            callback_answer(call, "Статус уже изменён другим администратором", True)
    elif data.startswith("tpu:"):
        _, raw_id, decision = data.split(":")
        topup = DB.resolve_topup(int(raw_id), decision == "yes")
        if topup:
            lang = language_of(int(topup["user_id"]))
            message = (
                text(
                    lang,
                    "topup_credited",
                    amount=format_usd_cents(
                        int(topup["amount_usd_cents"]),
                        currency_of(int(topup["user_id"])),
                    ),
                )
                if decision == "yes"
                else text(lang, "topup_rejected")
            )
            BOT.send_message(int(topup["user_id"]), message)
            callback_answer(call, f"Пополнение #{raw_id} обработано")
        else:
            callback_answer(call, "Заявка уже обработана", True)
    elif data.startswith("sug:"):
        _, raw_id, status = data.split(":")
        changed = DB.resolve_suggestion(int(raw_id), status)
        callback_answer(
            call,
            "Предложение обновлено" if changed else "Уже обработано",
            not changed,
        )
    elif data.startswith("nft:"):
        _, raw_id, status = data.split(":")
        request = DB.resolve_nft_buyback(int(raw_id), status)
        if request:
            user_message = (
                f"✅ Администратор начал обработку вашей заявки NFT #{raw_id}. "
                f"Для уточнений: {OWNER_USERNAME}"
                if status == "contacted"
                else f"Заявка NFT #{raw_id} закрыта. Для уточнений: {SUPPORT_USERNAME}"
            )
            try:
                BOT.send_message(int(request["user_id"]), user_message)
            except ApiTelegramException:
                LOGGER.info("Could not notify NFT request user %s", request["user_id"])
            callback_answer(call, f"Заявка NFT #{raw_id}: {status}")
        else:
            callback_answer(call, "Заявка уже обработана", True)


def valid_hash(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_+\-/=]{32,110}", cleaned):
        return None
    compact_hex = cleaned.removeprefix("0x").removeprefix("0X")
    if re.fullmatch(r"[a-fA-F0-9]{64}", compact_hex):
        return compact_hex.lower()
    try:
        raw = base64.b64decode(
            cleaned + "=" * (-len(cleaned) % 4),
            altchars=b"-_",
            validate=False,
        )
        if len(raw) == 32:
            return raw.hex()
    except (ValueError, TypeError):
        pass
    return cleaned


def valid_cryptobot_check(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    pattern = (
        r"https://(?:t\.me|telegram\.me)/CryptoBot\?start="
        r"CQ[A-Za-z0-9_-]{8,100}"
    )
    return cleaned if re.fullmatch(pattern, cleaned, flags=re.IGNORECASE) else None


@BOT.pre_checkout_query_handler(func=lambda query: True)
def stars_pre_checkout(query: types.PreCheckoutQuery) -> None:
    valid = bool(
        query.currency == "XTR"
        and DB.valid_star_checkout(
            query.invoice_payload,
            query.from_user.id,
            int(query.total_amount),
        )
    )
    try:
        BOT.answer_pre_checkout_query(
            query.id,
            ok=valid,
            error_message=None
            if valid
            else text(language_of(query.from_user.id), "stars_payment_error"),
        )
    except Exception:
        LOGGER.exception("Failed to answer Stars pre-checkout query")


@BOT.message_handler(content_types=["successful_payment"])
def stars_successful_payment(message: types.Message) -> None:
    payment = message.successful_payment
    if not payment or payment.currency != "XTR":
        return
    lang = language_of(message.from_user.id)
    charge_id = str(payment.telegram_payment_charge_id)
    provider_charge_id = str(payment.provider_payment_charge_id or "")
    try:
        result = DB.complete_star_payment(
            str(payment.invoice_payload),
            message.from_user.id,
            int(payment.total_amount),
            charge_id,
            provider_charge_id,
        )
    except (sqlite3.IntegrityError, ValueError):
        LOGGER.exception("Could not finalize Stars payment %s", charge_id)
        result = {"outcome": "refund_required"}

    outcome = str(result.get("outcome") or "")
    if outcome == "duplicate":
        LOGGER.info("Duplicate successful_payment update ignored: %s", charge_id)
        return
    if outcome == "paid":
        kind = str(result["kind"])
        item_id = int(result["item_id"])
        stars = int(result["stars"])
        if kind == "order":
            order = DB.order(item_id)
            send_visual(
                message.chat.id,
                "success",
                text(lang, "stars_paid_order", item_id=item_id, stars=stars),
                reply_markup=back(lang),
            )
            if order:
                notify_admins(
                    f"⭐ <b>Заказ оплачен Telegram Stars</b>\n"
                    f"Курс: <b>1 ⭐ = {star_rate_text()} ₽</b>\n\n"
                    + order_text(order, "ru", True),
                    order_admin_keyboard(item_id, "paid"),
                )
        else:
            amount = format_usd_cents(
                int(result["usd_cents"]), currency_of(message.from_user.id)
            )
            send_visual(
                message.chat.id,
                "success",
                text(
                    lang,
                    "stars_paid_topup",
                    stars=stars,
                    amount=amount,
                ),
                reply_markup=back(lang),
            )
            notify_admins(
                f"⭐ <b>Баланс пополнен Telegram Stars</b>\n"
                f"Заявка: <b>#{item_id}</b> · Пользователь: "
                f"<code>{message.from_user.id}</code>\n"
                f"Получено: <b>{stars} ⭐</b> · "
                f"Зачислено: <b>{dollars(int(result['usd_cents']))}</b>"
            )
        return

    refunded = False
    try:
        refunded = bool(BOT.refund_star_payment(message.from_user.id, charge_id))
        if refunded:
            DB.mark_star_refunded(charge_id)
    except Exception:
        LOGGER.exception("Automatic Stars refund failed for %s", charge_id)
    notify_admins(
        "⚠️ <b>Платёж Stars не удалось применить</b>\n"
        f"Пользователь: <code>{message.from_user.id}</code>\n"
        f"Charge ID: <code>{html.escape(charge_id)}</code>\n"
        f"Автовозврат: <b>{'выполнен' if refunded else 'требует проверки'}</b>"
    )
    BOT.send_message(message.chat.id, text(lang, "stars_payment_error"))


@BOT.message_handler(
    func=lambda message: bool(DB.state(message.chat.id)), content_types=["text"]
)
def state_handler(message: types.Message) -> None:
    DB.ensure_user(message.from_user)
    lang = language_of(message.chat.id)
    if not DB.currency(message.chat.id):
        DB.clear_state(message.chat.id)
        send_currency(message.chat.id)
        return
    display_currency = currency_of(message.chat.id)
    state_record = DB.state(message.chat.id)
    if not state_record:
        return
    state, data = state_record
    if state == "promo_code":
        status, discount, code = DB.activate_promo(
            message.from_user.id, message.text or ""
        )
        if status == "invalid":
            BOT.send_message(
                message.chat.id,
                text(lang, "promo_invalid") + "\n\n" + text(lang, "promo_prompt"),
                reply_markup=back(lang, "nav:profile"),
            )
            return
        DB.clear_state(message.chat.id)
        key = {
            "activated": "promo_activated",
            "used": "promo_used",
            "active": "promo_active",
        }[status]
        BOT.send_message(
            message.chat.id,
            text(
                lang,
                key,
                code=html.escape(code),
                discount=discount,
            ),
            reply_markup=profile_keyboard(lang),
        )
        return
    if state in {"admin_discount_user", "admin_discount_percent"}:
        if not is_admin_user(message.from_user):
            DB.clear_state(message.chat.id)
            BOT.send_message(message.chat.id, text(lang, "access_denied"))
            return
        if state == "admin_discount_user":
            raw_user_id = (message.text or "").strip()
            if not raw_user_id.isdigit():
                BOT.send_message(
                    message.chat.id,
                    "❌ Отправьте только цифровой Telegram ID пользователя.",
                )
                return
            target = DB.user(int(raw_user_id))
            if not target:
                BOT.send_message(
                    message.chat.id,
                    "❌ Пользователь с таким ID не найден. Сначала он должен "
                    "нажать /start в боте.",
                )
                return
            DB.set_state(
                message.chat.id,
                "admin_discount_percent",
                {"target_user_id": int(raw_user_id)},
            )
            username = f"@{target['username']}" if target.get("username") else "—"
            BOT.send_message(
                message.chat.id,
                "<b>Пользователь найден</b>\n"
                f"ID: <code>{target['user_id']}</code>\n"
                f"Username: {html.escape(username)}\n"
                f"Персональная скидка: <b>{int(target.get('discount_percent') or 0)}%</b>\n"
                f"Общая скидка: <b>{DB.effective_discount(target)}%</b>\n\n"
                f"Введите новый процент от 0 до {MAX_TOTAL_DISCOUNT_PERCENT}. "
                "Значение 0 снимет персональную скидку.",
            )
            return
        raw_percent = (message.text or "").strip().removesuffix("%").strip()
        if not raw_percent.isdigit():
            BOT.send_message(
                message.chat.id,
                f"❌ Введите целое число от 0 до {MAX_TOTAL_DISCOUNT_PERCENT}.",
            )
            return
        percent = int(raw_percent)
        if not 0 <= percent <= MAX_TOTAL_DISCOUNT_PERCENT:
            BOT.send_message(
                message.chat.id,
                f"❌ Введите целое число от 0 до {MAX_TOTAL_DISCOUNT_PERCENT}.",
            )
            return
        target_user_id = int(data.get("target_user_id") or 0)
        target = DB.admin_set_discount(
            message.from_user.id, target_user_id, percent
        )
        DB.clear_state(message.chat.id)
        if not target:
            BOT.send_message(
                message.chat.id,
                "❌ Пользователь не найден. Скидка не изменена.",
                reply_markup=admin_dashboard_keyboard(),
            )
            return
        total_discount = DB.effective_discount(target)
        try:
            BOT.send_message(
                target_user_id,
                text(
                    language_of(target_user_id),
                    "admin_discount_received",
                    discount=percent,
                    total=total_discount,
                ),
            )
        except ApiTelegramException as exc:
            LOGGER.warning(
                "Failed to notify discount recipient %s: %s",
                target_user_id,
                exc,
            )
        BOT.send_message(
            message.chat.id,
            "<b>✅ Скидка обновлена</b>\n\n"
            f"ID пользователя: <code>{target_user_id}</code>\n"
            f"Персональная скидка: <b>{percent}%</b>\n"
            f"Реферальная скидка: "
            f"<b>{int(target.get('referral_discount_percent') or 0)}%</b>\n"
            f"Общая скидка: <b>{total_discount}%</b>\n"
            f"Администратор: <code>{message.from_user.id}</code>",
            reply_markup=admin_dashboard_keyboard(),
        )
        return
    if state in {"admin_balance_user", "admin_balance_amount"}:
        if not is_admin_user(message.from_user):
            DB.clear_state(message.chat.id)
            BOT.send_message(message.chat.id, text(lang, "access_denied"))
            return
        if state == "admin_balance_user":
            raw_user_id = (message.text or "").strip()
            if not raw_user_id.isdigit():
                BOT.send_message(
                    message.chat.id,
                    "❌ Отправьте только цифровой Telegram ID пользователя.",
                )
                return
            target = DB.user(int(raw_user_id))
            if not target:
                BOT.send_message(
                    message.chat.id,
                    "❌ Пользователь с таким ID не найден. Сначала он должен "
                    "нажать /start в боте.",
                )
                return
            DB.set_state(
                message.chat.id,
                "admin_balance_amount",
                {"target_user_id": int(raw_user_id)},
            )
            username = f"@{target['username']}" if target.get("username") else "—"
            BOT.send_message(
                message.chat.id,
                "<b>Пользователь найден</b>\n"
                f"ID: <code>{target['user_id']}</code>\n"
                f"Username: {html.escape(username)}\n"
                f"Текущий баланс: <b>{dollars(int(target['balance_usd_cents']))}</b>\n\n"
                "Введите сумму пополнения в долларах, например: <code>12.50</code>",
            )
            return
        try:
            amount = Decimal((message.text or "").strip().replace(",", "."))
            if not amount.is_finite() or amount != amount.quantize(Decimal("0.01")):
                raise InvalidOperation
            cents = int(amount * 100)
        except (InvalidOperation, ValueError):
            cents = 0
        if not 1 <= cents <= MAX_TOPUP_CENTS:
            BOT.send_message(
                message.chat.id,
                "❌ Введите сумму от $0.01 до $10 000, не более двух знаков "
                "после точки.",
            )
            return
        target_user_id = int(data.get("target_user_id") or 0)
        target = DB.admin_credit_balance(message.from_user.id, target_user_id, cents)
        DB.clear_state(message.chat.id)
        if not target:
            BOT.send_message(
                message.chat.id,
                "❌ Пользователь не найден. Пополнение не выполнено.",
                reply_markup=admin_dashboard_keyboard(),
            )
            return
        new_balance = int(target["balance_usd_cents"])
        try:
            BOT.send_message(
                target_user_id,
                text(
                    language_of(target_user_id),
                    "admin_balance_received",
                    amount=format_usd_cents(cents, currency_of(target_user_id)),
                    balance=format_usd_cents(
                        new_balance, currency_of(target_user_id)
                    ),
                ),
            )
        except ApiTelegramException as exc:
            LOGGER.warning("Failed to notify balance recipient %s: %s", target_user_id, exc)
        BOT.send_message(
            message.chat.id,
            "<b>✅ Баланс пополнен</b>\n\n"
            f"ID пользователя: <code>{target_user_id}</code>\n"
            f"Зачислено: <b>{dollars(cents)}</b>\n"
            f"Новый баланс: <b>{dollars(new_balance)}</b>\n"
            f"Администратор: <code>{message.from_user.id}</code>",
            reply_markup=admin_dashboard_keyboard(),
        )
        return
    if state == "quantity":
        product_code = str(data.get("product") or "")
        if product_code not in ACTIVE_PRODUCT_CODES:
            DB.clear_state(message.chat.id)
            send_home(message.chat.id)
            return
        product = PRODUCTS[product_code]
        cleaned = (message.text or "").replace(" ", "").replace(",", "")
        if (
            not cleaned.isdigit()
            or not minimum_quantity(product) <= int(cleaned) <= product.maximum
        ):
            BOT.send_message(message.chat.id, quantity_prompt(lang, product))
            return
        DB.set_state(
            message.chat.id,
            "recipient",
            {"product": product.code, "quantity": int(cleaned)},
        )
        BOT.send_message(message.chat.id, recipient_prompt(lang, product))
    elif state == "recipient":
        recipient = (message.text or "").strip()
        if not 2 <= len(recipient) <= 100:
            BOT.send_message(message.chat.id, text(lang, "recipient_invalid"))
            return
        product_code = str(data.get("product") or "")
        if product_code not in ACTIVE_PRODUCT_CODES:
            DB.clear_state(message.chat.id)
            send_home(message.chat.id)
            return
        product = PRODUCTS[product_code]
        try:
            order_id = DB.create_order(
                message.chat.id, product, int(data["quantity"]), recipient
            )
        except ValueError:
            DB.clear_state(message.chat.id)
            BOT.send_message(
                message.chat.id,
                text(
                    lang,
                    "minimum_order",
                    _currency=display_currency,
                ),
            )
            return
        DB.clear_state(message.chat.id)
        send_visual(
            message.chat.id,
            "checkout",
            text(lang, "order_created", order_id=order_id)
            + "\n\n"
            + text(
                lang,
                "order_auto_close_notice",
                minutes=ORDER_AUTO_CLOSE_MINUTES,
            ),
            reply_markup=payment_keyboard(lang, order_id),
        )
    elif state == "topup_amount":
        try:
            amount = Decimal((message.text or "").replace(",", "."))
            if not amount.is_finite() or amount != amount.quantize(Decimal("0.01")):
                raise InvalidOperation
            cents = usd_cents_from_display_amount(amount, display_currency)
        except (InvalidOperation, ValueError):
            cents = 0
        if not minimum_topup_cents() <= cents <= MAX_TOPUP_CENTS:
            BOT.send_message(
                message.chat.id,
                text(
                    lang,
                    "custom_amount_prompt",
                    _currency=display_currency,
                ),
            )
            return
        DB.clear_state(message.chat.id)
        create_topup_checkout(message.chat.id, cents)
    elif state == "topup_stars_amount":
        DB.clear_state(message.chat.id)
        send_home(message.chat.id)
    elif state == "order_hash":
        tx_hash = valid_hash(message.text)
        if not tx_hash:
            BOT.send_message(message.chat.id, text(lang, "hash_invalid"))
            return
        try:
            accepted = DB.submit_order_hash(int(data["id"]), message.chat.id, tx_hash)
        except sqlite3.IntegrityError:
            accepted = False
        DB.clear_state(message.chat.id)
        if accepted:
            order = DB.order(int(data["id"]))
            BOT.send_message(message.chat.id, text(lang, "payment_submitted"))
            if order:
                notify_order_payment_submission(order, tx_hash)
        else:
            BOT.send_message(message.chat.id, text(lang, "already_used"))
    elif state == "topup_hash":
        tx_hash = valid_hash(message.text)
        if not tx_hash:
            BOT.send_message(message.chat.id, text(lang, "hash_invalid"))
            return
        try:
            accepted = DB.submit_topup_hash(int(data["id"]), message.chat.id, tx_hash)
        except sqlite3.IntegrityError:
            accepted = False
        DB.clear_state(message.chat.id)
        if accepted:
            topup = DB.topup(int(data["id"]))
            BOT.send_message(message.chat.id, text(lang, "topup_submitted"))
            if topup:
                notify_topup_payment_submission(topup, tx_hash)
        else:
            BOT.send_message(message.chat.id, text(lang, "already_used"))
    elif state in {"order_cryptobot", "topup_cryptobot"}:
        DB.clear_state(message.chat.id)
        send_home(message.chat.id)
    elif state == "suggestion":
        body = (message.text or "").strip()
        if not 5 <= len(body) <= 2_000:
            BOT.send_message(message.chat.id, text(lang, "suggestion_invalid"))
            return
        suggestion_id = DB.add_suggestion(message.chat.id, body)
        DB.clear_state(message.chat.id)
        keyboard = types.InlineKeyboardMarkup()
        keyboard.row(
            types.InlineKeyboardButton(
                "📌 В планы", callback_data=f"sug:{suggestion_id}:planned"
            ),
            types.InlineKeyboardButton(
                "🗑 Закрыть", callback_data=f"sug:{suggestion_id}:dismissed"
            ),
        )
        username = (
            f"@{message.from_user.username}" if message.from_user.username else "—"
        )
        notify_admins(
            f"💡 <b>Новое предложение #{suggestion_id}</b>\n"
            f"Пользователь: <code>{message.chat.id}</code> · "
            f"{html.escape(username)}\n\n{html.escape(body)}",
            keyboard,
        )
        BOT.send_message(
            message.chat.id,
            text(lang, "suggestion_sent"),
            reply_markup=back(lang),
        )
    elif state == "nft_buyback":
        DB.clear_state(message.chat.id)
        send_home(message.chat.id)
    elif state == "support":
        body = (message.text or "").strip()
        if not 2 <= len(body) <= 2_000:
            BOT.send_message(message.chat.id, text(lang, "support_invalid"))
            return
        DB.clear_state(message.chat.id)
        notify_admins(
            f"💬 <b>Support message</b>\nUser: <code>{message.chat.id}</code>\n"
            f"Username: <code>{html.escape('@' + message.from_user.username if message.from_user.username else '-')}</code>\n\n"
            f"{html.escape(body)}"
        )
        BOT.send_message(message.chat.id, text(lang, "support_sent"))


LEAD_PRODUCT_ALIASES = {
    "stars": (
        "telegram stars",
        "телеграм старс",
        "телеграм звезды",
        "звезды телеграм",
        "тг звезды",
        "звезды тг",
        "старсы",
        "stars",
    ),
    "telegram_premium_1m": (
        "telegram premium",
        "телеграм премиум",
        "премиум телеграм",
        "тг премиум",
        "premium",
    ),
    "telegram_premium_3m": (
        "telegram premium 3 months",
        "telegram premium 3m",
        "телеграм премиум 3 месяца",
        "тг премиум 3 месяца",
    ),
    "telegram_premium_6m": (
        "telegram premium 6 months",
        "telegram premium 6m",
        "телеграм премиум 6 месяцев",
        "тг премиум 6 месяцев",
    ),
    "telegram_premium_12m": (
        "telegram premium 12 months",
        "telegram premium 12m",
        "telegram premium 1 year",
        "телеграм премиум 12 месяцев",
        "телеграм премиум 1 год",
        "тг премиум на год",
    ),
    "bp": ("brawl pass", "бравл пас", "бп", "пропуск бравл"),
    "bp_plus": (
        "brawl pass plus",
        "бравл пас плюс",
        "бп плюс",
        "пропуск бравл плюс",
    ),
    "steam": (
        "steam",
        "стим",
        "пополнение стим",
        "пополнение стима",
        "стим кошелек",
    ),
    "pubg_uc": (
        "pubg",
        "пабг",
        "pubg uc",
        "пабг юси",
        "юси пабг",
        "валюта пабг",
    ),
    "robux": (
        "robux",
        "робукс",
        "робуксы",
        "roblox",
        "роблокс",
        "робуксы на аккаунт",
    ),
    "robux_gamepass": (
        "robux game pass",
        "robux gamepass",
        "робуксы геймпасс",
        "робуксы гейм пасс",
        "робуксы через геймпасс",
        "робуксы через гейм пасс",
    ),
    "robux_account_45k": (
        "robux account 45k",
        "robux account from 45000",
        "робуксы аккаунтом от 45000",
        "робуксы аккаунтом 45к",
    ),
    "robux_gamepass_45k": (
        "robux gamepass 45k",
        "robux via game pass from 45000",
        "робуксы геймпассом от 45000",
        "робуксы геймпасс от 45000",
        "робуксы геймпасс 45к",
    ),
    "robux_group": (
        "robux group",
        "robux via group",
        "робуксы группой",
        "робуксы через группу",
    ),
    "robux_group_45k": (
        "robux group 45k",
        "robux via group from 45000",
        "робуксы группой от 45000",
        "робуксы через группу от 45000",
        "робуксы группой 45к",
    ),
    "exitlag_warranty_30d": (
        "exitlag warranty",
        "exitlag 30 days",
        "exitlag гарантия",
        "exitlag гарантия 30 дней",
    ),
    "exitlag_no_warranty": (
        "exitlag no warranty",
        "exitlag без гарантии",
        "аккаунт exitlag без гарантии",
    ),
    "gpt": ("chatgpt", "чатгпт", "чат гпт", "чат жпт", "gpt", "chatgpt nw"),
    "gpt_fw": ("chatgpt fw", "чатгпт фв", "чат гпт фв"),
    "chatgpt_plus_1m": (
        "chatgpt plus",
        "чатгпт плюс",
        "чат гпт плюс",
        "gpt plus",
    ),
    "claude": ("claude", "клод", "клауд", "клоуд"),
    "claude_pro_1m": (
        "claude pro",
        "клод про",
        "клауд про",
        "клоуд про",
    ),
    "team_claude": ("team claude", "командный клод", "тим клод"),
    "claude_max_5x": ("claude max 5x", "клод макс 5x", "клод макс 5"),
    "claude_max_20x": ("claude max 20x", "клод макс 20x", "клод макс 20"),
    "gemini": ("gemini", "гемини", "джемини"),
    "google_ai_plus_1m": (
        "google ai plus",
        "google ии плюс",
        "гугл аи плюс",
        "гугл ии плюс",
        "gemini plus",
        "гемини плюс",
    ),
    "google_ai_pro_1m": (
        "google ai pro",
        "google ии про",
        "гугл аи про",
        "гугл ии про",
        "gemini pro",
        "гемини про",
    ),
    "x_grok": ("x premium grok", "икс премиум грок", "grok", "грок"),
    "grok_1m": ("grok month", "grok 1m", "грок месяц", "грок на месяц"),
    "grok_1w": ("grok week", "grok 1w", "грок неделя", "грок на неделю"),
    "grok_5d": ("grok 5 days", "grok 5d", "грок 5 дней", "грок на 5 дней"),
    "gmail_account": (
        "gmail",
        "гмаил",
        "гмейл",
        "аккаунт gmail",
        "аккаунт гмейл",
        "почта гугл",
    ),
    "gta_steam_account": (
        "gta",
        "гта",
        "гта 5",
        "gta 5",
        "аккаунт гта стим",
        "гта 5 стим",
    ),
    "rust_steam_account": (
        "rust",
        "раст",
        "аккаунт раст стим",
        "раст стим",
    ),
}

for gift_amount in (100, 200, 300, 400, 500, 600, 800, 1_000, 2_000, 5_000, 10_000):
    amount = str(gift_amount)
    LEAD_PRODUCT_ALIASES[f"gift_{amount}"] = (
        f"гифт карта роблокс {amount}",
        f"гифт карту роблокс {amount}",
        f"гифт карта робукс {amount}",
        f"подарочная карта роблокс {amount}",
        f"подарочную карту роблокс {amount}",
        f"карта роблокс {amount}",
        f"карту роблокс {amount}",
        f"роблокс гифт {amount}",
    )


def normalize_lead_text(value: str) -> str:
    normalized = value.casefold().replace("ё", "е")
    normalized = re.sub(r"[#_/+\-•·.,:;!?()\[\]{}]+", " ", normalized)
    return " " + re.sub(r"\s+", " ", normalized).strip() + " "


def product_search_aliases() -> dict[str, tuple[str, ...]]:
    result: dict[str, tuple[str, ...]] = {}
    for code, product in PRODUCTS.items():
        if code not in ACTIVE_PRODUCT_CODES:
            continue
        manual_candidates = LEAD_PRODUCT_ALIASES.get(code, ())
        candidates = [code.replace("_", " "), *product.titles.values()]
        candidates.extend(manual_candidates)
        aliases: set[str] = set()
        for candidate in candidates:
            normalized = normalize_lead_text(candidate).strip()
            if len(normalized) >= 3 or (
                candidate in manual_candidates and len(normalized) >= 2
            ):
                aliases.add(normalized)
            compact = normalized.replace(" ", "")
            if len(compact) >= 4:
                aliases.add(compact)
        result[code] = tuple(sorted(aliases, key=lambda item: (-len(item), item)))
    return result


LEAD_SEARCH_ALIASES = product_search_aliases()
LEAD_DEMAND_RE = re.compile(
    r"\b(ищу|ищем|куплю|купим|покупка|покупаю|покупаем|приобрету|"
    r"приобретаю|скупаю|скупаем|закуп|закупаю|закупаем|возьму|возьмем|"
    r"нужен|нужна|нужно|нужны|"
    r"требуется|требуются|где\s+купить|кто\s+прода[её]т|"
    r"looking\s+for|want\s+to\s+buy|wtb)\b",
    re.IGNORECASE,
)
LEAD_SUPPLY_RE = re.compile(
    r"\b(продам|продадим|продаю|продаем|поставляю|поставляем|поставщик|"
    r"оптовик|оптом|есть\s+опт|"
    r"предлагаю\s+опт|в\s+наличии|selling|supplier|wholesale|wts)\b",
    re.IGNORECASE,
)


def lead_match(body: str) -> tuple[str, list[str]] | None:
    normalized = normalize_lead_text(body)
    demand = bool(LEAD_DEMAND_RE.search(normalized))
    supply = bool(LEAD_SUPPLY_RE.search(normalized))
    if not demand and not supply:
        return None
    product_codes = [
        code
        for code, aliases in LEAD_SEARCH_ALIASES.items()
        if any(f" {alias} " in normalized for alias in aliases)
    ]
    if not product_codes:
        return None
    return ("покупатель" if demand else "поставщик"), product_codes


def is_monitored_chat(message: types.Message) -> bool:
    username = str(getattr(message.chat, "username", "") or "")
    return username.casefold() == LEAD_MONITOR_CHAT.lstrip("@").casefold()


def process_monitored_message(message: types.Message) -> None:
    body = (message.text or "").strip()
    if not body or (message.from_user and message.from_user.is_bot):
        return
    matched = lead_match(body)
    if not matched:
        return
    intent, product_codes = matched
    sender = message.from_user
    username = sender.username if sender else None
    user_id = sender.id if sender else None
    lead_id = DB.add_monitored_lead(
        chat_id=message.chat.id,
        message_id=message.message_id,
        user_id=user_id,
        username=username,
        intent=intent,
        product_codes=product_codes,
        body=body[:4_000],
    )
    if lead_id is None:
        return
    product_names = ", ".join(
        PRODUCTS[code].titles["ru"] for code in product_codes if code in PRODUCTS
    )
    sender_label = f"@{username}" if username else "анонимный автор / канал"
    chat_username = str(getattr(message.chat, "username", "") or "")
    chat_handle = f"@{chat_username}" if chat_username else LEAD_MONITOR_CHAT
    link = f"https://t.me/{chat_handle.lstrip('@')}/{message.message_id}"
    keyboard = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("🔎 Открыть сообщение", url=link)
    )
    notify_admins(
        f"🟢 <b>Новый лид в {html.escape(chat_handle)}</b>\n"
        f"Тип: <b>{intent}</b>\n"
        f"Автор: <b>{html.escape(sender_label)}</b> · "
        f"<code>{user_id or '—'}</code>\n"
        f"Товары: <b>{html.escape(product_names)}</b>\n\n"
        f"{html.escape(body[:2_500])}\n\n"
        "<i>Бот только уведомляет администратора и не пишет пользователю автоматически.</i>",
        keyboard,
    )


@BOT.message_handler(func=is_monitored_chat, content_types=["text"])
def monitored_group_message(message: types.Message) -> None:
    process_monitored_message(message)


@BOT.channel_post_handler(func=is_monitored_chat, content_types=["text"])
def monitored_channel_post(message: types.Message) -> None:
    process_monitored_message(message)


def automatic_payment_worker() -> None:
    LOGGER.info("Automatic blockchain payment verification started")
    while True:
        try:
            for kind, payment in DB.pending_crypto_reviews():
                payment_id = int(payment["id"])
                tx_hash = str(payment.get("tx_hash") or "")
                marker = (kind, payment_id, tx_hash)
                result = VERIFIER.verify(payment)
                if result.confirmed:
                    confirmed = (
                        DB.auto_confirm_topup(payment_id, tx_hash)
                        if kind == "topup"
                        else DB.auto_confirm_order(payment_id, tx_hash)
                    )
                    if not confirmed:
                        continue
                    user_id = int(confirmed["user_id"])
                    lang = language_of(user_id)
                    try:
                        if kind == "topup":
                            send_visual(
                                user_id,
                                "success",
                                text(
                                    lang,
                                    "auto_topup_confirmed",
                                    amount=format_usd_cents(
                                        int(confirmed["amount_usd_cents"]),
                                        currency_of(user_id),
                                    ),
                                ),
                                reply_markup=back(lang),
                            )
                            notify_admins(
                                "🤖 <b>Пополнение подтверждено автоматически</b>\n\n"
                                + topup_text(confirmed)
                            )
                        else:
                            send_visual(
                                user_id,
                                "success",
                                text(
                                    lang,
                                    "auto_order_confirmed",
                                    order_id=payment_id,
                                ),
                                reply_markup=back(lang),
                            )
                            notify_admins(
                                "🤖 <b>Заказ оплачен автоматически</b>\n\n"
                                + order_text(confirmed, "ru", True),
                                order_admin_keyboard(payment_id, "paid"),
                            )
                    except ApiTelegramException as exc:
                        LOGGER.warning(
                            "Failed to send automatic confirmation for %s #%s: %s",
                            kind,
                            payment_id,
                            exc,
                        )
                    VERIFICATION_NOTICES.pop(marker, None)
                    continue

                notice = (result.status, result.detail)
                if VERIFICATION_NOTICES.get(marker) == notice:
                    continue
                VERIFICATION_NOTICES[marker] = notice
                if result.status == "rejected":
                    notify_admins(
                        "⚠️ <b>Автопроверка не подтвердила платёж</b>\n\n"
                        f"Тип: <b>{kind}</b> · Заявка: <b>#{payment_id}</b>\n"
                        f"Сеть: <b>{html.escape(str(payment.get('payment_method') or '—'))}</b>\n"
                        f"TX: <code>{html.escape(tx_hash)}</code>\n"
                        f"Причина: <code>{html.escape(result.detail)}</code>\n\n"
                        "Заявка оставлена для ручной проверки."
                    )
                elif result.status == "unavailable":
                    LOGGER.warning(
                        "Auto verification unavailable for %s #%s: %s",
                        kind,
                        payment_id,
                        result.detail,
                    )
            if len(VERIFICATION_NOTICES) > 1_000:
                VERIFICATION_NOTICES.clear()
        except Exception:
            LOGGER.exception("Automatic payment verification worker failed")
        time.sleep(AUTO_VERIFY_INTERVAL_SECONDS)


def order_expiration_worker() -> None:
    LOGGER.info(
        "Automatic order cancellation enabled: %s minutes",
        ORDER_AUTO_CLOSE_MINUTES,
    )
    while True:
        try:
            expired_orders = DB.expire_unpaid_orders()
            for order in expired_orders:
                user_id = int(order["user_id"])
                try:
                    BOT.send_message(
                        user_id,
                        text(
                            language_of(user_id),
                            "order_auto_cancelled",
                            order_id=int(order["id"]),
                            minutes=ORDER_AUTO_CLOSE_MINUTES,
                        ),
                        reply_markup=back(language_of(user_id)),
                    )
                except ApiTelegramException as exc:
                    LOGGER.debug(
                        "Failed to notify expired order #%s: %s", order["id"], exc
                    )
            if expired_orders:
                order_ids = ", ".join(f"#{order['id']}" for order in expired_orders)
                notify_admins(
                    "⌛ <b>Автоматически отменены неоплаченные заказы</b>\n"
                    f"Заказы: <b>{html.escape(order_ids)}</b>\n"
                    f"Лимит ожидания: <b>{ORDER_AUTO_CLOSE_MINUTES} минут</b>"
                )
        except Exception:
            LOGGER.exception("Automatic order cancellation worker failed")
        time.sleep(30)


def giveaway_worker() -> None:
    while True:
        try:
            winner_id = DB.run_giveaway_if_due()
            if winner_id is not None:
                winner_lang = language_of(winner_id)
                try:
                    BOT.send_message(
                        winner_id,
                        text(winner_lang, "giveaway_winner"),
                        reply_markup=back(winner_lang),
                    )
                except ApiTelegramException as exc:
                    LOGGER.warning("Failed to notify giveaway winner: %s", exc)
                notify_admins(
                    "🎁 <b>Giveaway completed</b>\n\n"
                    f"Winner: <code>{winner_id}</code>\n"
                    f"Prize: <b>{GIVEAWAY_DISCOUNT_PERCENT}% off the next order</b>"
                )
        except Exception:
            LOGGER.exception("Giveaway worker failed")
        time.sleep(300)


def main() -> None:
    bot_account = BOT.get_me()
    actual_username = f"@{bot_account.username or ''}"
    if actual_username.casefold() != BOT_USERNAME.casefold():
        raise RuntimeError(
            f"BOT_TOKEN belongs to {actual_username}, expected {BOT_USERNAME}"
        )
    commands = {
        "en": [
            types.BotCommand("start", "Open the store"),
            types.BotCommand("menu", "Main menu"),
            types.BotCommand("about", "About JOULI MARKET"),
            types.BotCommand("language", "Change language"),
            types.BotCommand("currency", "Change currency"),
        ],
        "ru": [
            types.BotCommand("start", "Открыть магазин"),
            types.BotCommand("menu", "Главное меню"),
            types.BotCommand("about", "О магазине JOULI MARKET"),
            types.BotCommand("language", "Сменить язык"),
            types.BotCommand("currency", "Сменить валюту"),
        ],
        "uk": [
            types.BotCommand("start", "Відкрити магазин"),
            types.BotCommand("menu", "Головне меню"),
            types.BotCommand("about", "Про JOULI MARKET"),
            types.BotCommand("language", "Змінити мову"),
            types.BotCommand("currency", "Змінити валюту"),
        ],
    }
    for language_code in REMOVED_LANGUAGE_CODES:
        try:
            BOT.delete_my_commands(language_code=language_code)
            BOT.set_my_name("", language_code=language_code)
            BOT.set_my_short_description("", language_code=language_code)
            BOT.set_my_description("", language_code=language_code)
        except Exception as exc:
            LOGGER.debug("Failed to clear %s bot localization: %s", language_code, exc)
    try:
        BOT.set_my_commands(commands["en"])
        BOT.set_my_commands(commands["ru"], language_code="ru")
        BOT.set_my_commands(commands["uk"], language_code="uk")
    except Exception as exc:
        LOGGER.warning("Failed to update bot commands; polling will continue: %s", exc)
    administrator_profiles = ", ".join(
        [OWNER_USERNAME, *sorted(ADMIN_USERNAMES)]
    )
    profile_descriptions = {
        "en": (
            "🌿 Jouli Market: Stars, PUBG UC, Brawl Pass, Robux and AI.",
            "Jouli Market is a green digital store for Telegram Stars, PUBG UC, Brawl Pass, Robux and AI subscriptions. Minimum order: $10. Payments: TON, USDT, SOL or balance.",
        ),
        "ru": (
            "🌿 Jouli Market: Stars, PUBG UC, Brawl Pass, Robux и AI.",
            "Jouli Market — зелёный цифровой магазин Telegram Stars, PUBG UC, Brawl Pass, Robux и AI-подписок. Минимальный заказ: $10. Оплата: TON, USDT, SOL или баланс.",
        ),
        "uk": (
            "🌿 Jouli Market: Stars, PUBG UC, Brawl Pass, Robux та AI.",
            "Jouli Market — зелений цифровий магазин Telegram Stars, PUBG UC, Brawl Pass, Robux та AI-підписок. Мінімальне замовлення: $10. Оплата: TON, USDT, SOL або баланс.",
        ),
    }
    try:
        BOT.set_my_name(BOT_DISPLAY_NAME)
        BOT.set_my_name(BOT_DISPLAY_NAME, language_code="ru")
        BOT.set_my_name(BOT_DISPLAY_NAME, language_code="uk")
    except Exception as exc:
        LOGGER.warning("Failed to update bot display name: %s", exc)
    try:
        for language_code, (
            short_description,
            description,
        ) in profile_descriptions.items():
            telegram_language = None if language_code == "en" else language_code
            BOT.set_my_short_description(
                short_description, language_code=telegram_language
            )
            BOT.set_my_description(description, language_code=telegram_language)
    except Exception as exc:
        LOGGER.warning(
            "Failed to update bot profile descriptions; polling will continue: %s",
            exc,
        )
    if WEBAPP_URL:
        try:
            BOT.set_chat_menu_button(
                menu_button=types.MenuButtonWebApp(
                    type="web_app",
                    text="Jouli Market",
                    web_app=types.WebAppInfo(WEBAPP_URL),
                )
            )
        except Exception as exc:
            LOGGER.warning("Failed to set Mini App menu button: %s", exc)
    for attempt in range(1, 4):
        try:
            BOT.remove_webhook()
            break
        except Exception as exc:
            LOGGER.warning("Webhook removal attempt %s failed: %s", attempt, exc)
            if attempt < 3:
                time.sleep(2)
    threading.Thread(
        target=giveaway_worker,
        name="giveaway-worker",
        daemon=True,
    ).start()
    threading.Thread(
        target=order_expiration_worker,
        name="order-expiration-worker",
        daemon=True,
    ).start()
    threading.Thread(
        target=miniapp_server_worker,
        name="miniapp-server",
        daemon=True,
    ).start()
    if AUTO_VERIFY_ENABLED:
        threading.Thread(
            target=automatic_payment_worker,
            name="payment-verifier",
            daemon=True,
        ).start()
    LOGGER.info("Starting %s", SHOP_NAME)
    BOT.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)


if __name__ == "__main__":
    main()
