# handlers.py
import os
import json
import base64
import logging
import time
from decimal import Decimal
from datetime import datetime

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    WebAppInfo,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import ContextTypes, ConversationHandler

from database import (
    get_db_connection,
    ensure_default_categories,
    get_or_create_category_id,
    current_period,
)

from config import (
    ADD_EXPENSE_AMOUNT,
    ADD_EXPENSE_CATEGORY,
    ADD_EXPENSE_DESCRIPTION,
    SET_BUDGET_CATEGORY,
    SET_BUDGET_AMOUNT,
    DELETE_EXPENSE_ID,
)

# -------------------------------------------------------------------
# WebApp base (HTTPS). Override via env: WEBAPP_BASE=https://your.site
# -------------------------------------------------------------------
WEBAPP_BASE = os.getenv("WEBAPP_BASE", "https://meek-alfajores-d54dfe.netlify.app")


# -------------------------- internal helpers -------------------------- #
def _encode_payload(payload_dict: dict) -> str:
    raw = json.dumps(payload_dict).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8")


def _per_user_budget_items(user_id: int):
    """
    Return list of {name, setBudget, used} for the current month.
    """
    items = []
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.name, b.amount,
                       COALESCE((
                           SELECT SUM(e.amount)
                           FROM expenses e
                           WHERE e.user_id = b.user_id
                             AND e.category_id = b.category_id
                             AND e.date >= b.period_month
                             AND e.date < (b.period_month + INTERVAL '1 month')
                       ), 0) AS used
                FROM budgets b
                JOIN categories c ON b.category_id = c.id
                WHERE b.user_id = %s
                  AND b.period_month = DATE_TRUNC('month', CURRENT_DATE)
                ORDER BY c.name
                """,
                (user_id,),
            )
            for name, amount, used in cur.fetchall():
                items.append(
                    {
                        "name": name,
                        "setBudget": float(amount),
                        "used": float(used or 0.0),
                    }
                )
    return items


def _reply_kb(budget_url: str, expense_url: str, version: int) -> ReplyKeyboardMarkup:
    """
    One row with 3 WebApp buttons (Budget, Expense, Report).
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="💰 Budget", web_app=WebAppInfo(url=budget_url)),
                KeyboardButton(text="💸 Expense", web_app=WebAppInfo(url=expense_url)),
                KeyboardButton(
                    text="📊 Report",
                    web_app=WebAppInfo(url=f"{WEBAPP_BASE}/report.html?v={version}"),
                ),
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


# (legacy helpers for CLI flows)
def get_expense_categories(user_id: int):
    categories = []
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT name FROM categories WHERE user_id = %s ORDER BY name",
                    (user_id,),
                )
                categories = [r[0] for r in cur.fetchall()]
    except Exception:
        logging.exception("Error retrieving categories for user %s", user_id)
    return categories


def build_category_keyboard(categories):
    if not categories:
        return None
    return ReplyKeyboardMarkup(
        [[c] for c in categories], resize_keyboard=True, one_time_keyboard=True
    )


# ----------------------------- Start / Menu ----------------------------- #
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Welcome + show WebApp buttons. Uses separate pages:
    - index.html  -> Budget
    - expense.html -> Expense
    """
    user = update.effective_user
    user_id = user.id
    first_name = user.first_name or "there"

    try:
        # Ensure user row
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (user_id, first_name)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET first_name = EXCLUDED.first_name
                    """,
                    (user_id, first_name),
                )

        # Seed default categories once
        ensure_default_categories(user_id)

        # Build items for this user/month
        items = _per_user_budget_items(user_id)

        # Two payloads with ui hints (optional on client)
        p_budget = {"type": "budget.init", "ui": "budget", "items": items}
        p_expense = {"type": "budget.init", "ui": "expense", "items": items}
        b64_budget = _encode_payload(p_budget)
        b64_expense = _encode_payload(p_expense)

        version = int(time.time())

        # Multi-page URLs (no SPA routing/404 issues)
        budget_url = f"{WEBAPP_BASE}/index.html?v={version}&payload={b64_budget}"
        expense_url = f"{WEBAPP_BASE}/expense.html?v={version}&payload={b64_expense}"

        # Intro text
        await update.message.reply_text(
            text=(
                f"Welcome, {first_name}!\n\n"
                "Use the bottom buttons to open the Web App:\n"
                "• Budget → edit amounts → Save\n"
                "• Expense → quick add or view last 10\n"
                "• Report  → (coming next)\n"
            )
        )

        # Show the reply keyboard (one row, three buttons)
        await update.message.reply_text(
            "Quick menu ready below.", reply_markup=_reply_kb(budget_url, expense_url, version)
        )

    except Exception:
        logging.exception("Error in start_command for user %s", user_id)
        await update.message.reply_text(
            "Sorry, an error occurred while setting up your account. Please try again."
        )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Kept only for compatibility if you later add inline callback buttons.
    """
    try:
        if update.callback_query:
            await update.callback_query.answer()
    except Exception:
        logging.exception("button_handler error")


# --------- Slash openers (/budget, /expense) → inline web_app buttons --------- #
def _build_webapp_urls_for_user(user_id: int):
    items = _per_user_budget_items(user_id)
    p_budget = {"type": "budget.init", "ui": "budget", "items": items}
    p_expense = {"type": "budget.init", "ui": "expense", "items": items}
    b64_budget = _encode_payload(p_budget)
    b64_expense = _encode_payload(p_expense)
    version = int(time.time())
    budget_url = f"{WEBAPP_BASE}/index.html?v={version}&payload={b64_budget}"
    expense_url = f"{WEBAPP_BASE}/expense.html?v={version}&payload={b64_expense}"
    return budget_url, expense_url


async def open_budget_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        budget_url, _ = _build_webapp_urls_for_user(user_id)
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Open Budget WebApp", web_app=WebAppInfo(url=budget_url))]]
        )
        await update.message.reply_text("Tap to open Budget:", reply_markup=kb)
    except Exception:
        logging.exception("open_budget_command error")
        await update.message.reply_text("Sorry, couldn't open Budget.")


async def open_expense_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        _, expense_url = _build_webapp_urls_for_user(user_id)
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Open Expense WebApp", web_app=WebAppInfo(url=expense_url))]]
        )
        await update.message.reply_text("Tap to open Expense:", reply_markup=kb)
    except Exception:
        logging.exception("open_expense_command error")
        await update.message.reply_text("Sorry, couldn't open Expense.")


# ---------------------- Legacy CLI flows (optional) ---------------------- #
async def add_expense_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Please enter the amount:")
    return ADD_EXPENSE_AMOUNT


async def add_expense_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        amount = Decimal(update.message.text.strip())
        if amount <= 0:
            await update.message.reply_text("Amount must be a positive number. Try again.")
            return ADD_EXPENSE_AMOUNT

        context.user_data["amount"] = amount
        categories = get_expense_categories(update.effective_user.id)
        keyboard = build_category_keyboard(categories)
        await update.message.reply_text(
            "Select a category or type a new one:", reply_markup=keyboard
        )
        return ADD_EXPENSE_CATEGORY
    except Exception:
        await update.message.reply_text("Invalid amount. Enter a valid number.")
        return ADD_EXPENSE_AMOUNT


async def add_expense_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["category"] = update.message.text.strip()
    await update.message.reply_text("Now enter a short description:")
    return ADD_EXPENSE_DESCRIPTION


async def add_expense_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["description"] = update.message.text.strip()
    amount = context.user_data["amount"]
    category_name = context.user_data["category"]
    description = context.user_data["description"]
    user_id = update.effective_user.id

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                category_id = get_or_create_category_id(cur, user_id, category_name)
                cur.execute(
                    "INSERT INTO expenses (user_id, category_id, amount, description) VALUES (%s, %s, %s, %s)",
                    (user_id, category_id, amount, description),
                )
        await update.message.reply_text(
            f"Saved ✅ Amount: {amount} | Category: {category_name}",
            reply_markup=ReplyKeyboardRemove(),
        )
    except Exception:
        logging.exception("Error adding expense for user %s", user_id)
        await update.message.reply_text("Sorry, an error occurred while saving your expense.")
    finally:
        context.user_data.clear()
    return ConversationHandler.END


async def view_expenses_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT e.id, e.amount, c.name, e.description, e.date
                    FROM expenses e
                    LEFT JOIN categories c ON e.category_id = c.id
                    WHERE e.user_id = %s
                    ORDER BY e.date DESC
                    LIMIT 10
                    """,
                    (user_id,),
                )
                expenses = cur.fetchall()
        if not expenses:
            await update.message.reply_text('No expenses yet. Use the "💸 Expense" button to add.')
            return

        message = "Your latest 10 expenses:\n\n"
        for exp_id, amount, cat, desc, dt in expenses:
            date_str = dt.strftime("%Y-%m-%d")
            message += (
                f"ID: {exp_id}\n"
                f"Amount: {amount:.2f}\n"
                f"Category: {cat or 'N/A'}\n"
                f"Description: {desc or 'N/A'}\n"
                f"Date: {date_str}\n\n"
            )
        await update.message.reply_text(message)
    except Exception:
        logging.exception("Error retrieving expenses for user %s", user_id)
        await update.message.reply_text("Sorry, error while retrieving your expenses.")


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                today = datetime.now()
                start_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                cur.execute(
                    "SELECT COALESCE(SUM(amount),0) FROM expenses WHERE user_id = %s AND date >= %s",
                    (user_id, start_of_month),
                )
                total_expense = cur.fetchone()[0] or 0

                cur.execute(
                    """
                    SELECT c.name, COALESCE(SUM(e.amount),0)
                    FROM expenses e
                    JOIN categories c ON e.category_id = c.id
                    WHERE e.user_id = %s AND e.date >= %s
                    GROUP BY c.name
                    ORDER BY 2 DESC
                    """,
                    (user_id, start_of_month),
                )
                by_cat = cur.fetchall()

        message = f"This Month ({today.strftime('%B, %Y')})\n\nTotal: {float(total_expense):.2f}\n\nBy Category:\n"
        for cat, amt in by_cat:
            message += f"- {cat}: {float(amt):.2f}\n"
        await update.message.reply_text(message)
    except Exception:
        logging.exception("Error generating report for user %s", user_id)
        await update.message.reply_text("Sorry, error while generating report.")


async def set_budget_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    ensure_default_categories(user_id)
    categories = get_expense_categories(user_id)
    keyboard = build_category_keyboard(categories)
    await update.message.reply_text(
        "Select a category for the budget or type a new one:", reply_markup=keyboard
    )
    return SET_BUDGET_CATEGORY


async def set_budget_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["budget_category"] = update.message.text.strip()
    await update.message.reply_text("Enter the monthly budget amount:")
    return SET_BUDGET_AMOUNT


async def set_budget_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    category_name = context.user_data["budget_category"]
    amount_text = update.message.text.strip()
    try:
        amount = Decimal(amount_text)
        if amount <= 0:
            await update.message.reply_text("Amount must be positive. Try again.")
            return SET_BUDGET_AMOUNT

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                category_id = get_or_create_category_id(cur, user_id, category_name)
                cur.execute(
                    """
                    INSERT INTO budgets (user_id, category_id, amount, period_month)
                    VALUES (%s, %s, %s, DATE_TRUNC('month', CURRENT_DATE))
                    ON CONFLICT (user_id, category_id, period_month)
                    DO UPDATE SET amount = EXCLUDED.amount
                    """,
                    (user_id, category_id, amount),
                )
        await update.message.reply_text(
            f"Budget saved ✅ {category_name}: {amount}",
            reply_markup=ReplyKeyboardRemove(),
        )
    except Exception:
        logging.exception("Error setting budget for user %s", user_id)
        await update.message.reply_text("Sorry, error while setting your budget.")
    finally:
        context.user_data.clear()
    return ConversationHandler.END


async def view_budget_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    period = current_period()
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.name, b.amount,
                           COALESCE((
                               SELECT SUM(e.amount)
                               FROM expenses e
                               WHERE e.user_id = b.user_id
                                 AND e.category_id = b.category_id
                                 AND e.date >= b.period_month
                                 AND e.date < (b.period_month + INTERVAL '1 month')
                           ), 0) AS used
                    FROM budgets b
                    JOIN categories c ON b.category_id = c.id
                    WHERE b.user_id = %s AND b.period_month = %s
                    ORDER BY c.name
                    """,
                    (user_id, period),
                )
                rows = cur.fetchall()
        if not rows:
            await update.message.reply_text(
                'No budgets set for this month. Use the "💰 Budget" button to add.'
            )
            return
        message = "Current month budgets (quick view):\n\n"
        for name, amount, used in rows:
            in_hand = (float(amount) - float(used))
            message += (
                f"{name} — Set: {float(amount):.2f}, Used: {float(used):.2f}, In Hand: {in_hand:.2f}\n"
            )
        await update.message.reply_text(message)
    except Exception:
        logging.exception("Error retrieving budgets for user %s", user_id)
        await update.message.reply_text("Sorry, error while retrieving budgets.")


async def delete_expense_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Send the ID of the expense you want to delete.")
    return DELETE_EXPENSE_ID


async def delete_expense_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    try:
        expense_id = int(update.message.text.strip())
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM expenses WHERE id = %s AND user_id = %s RETURNING id",
                    (expense_id, user_id),
                )
                deleted_row = cur.fetchone()
        if deleted_row:
            await update.message.reply_text(f"Deleted ✅ Expense ID {expense_id}")
        else:
            await update.message.reply_text("No expense found with that ID.")
    except Exception:
        logging.exception("Error deleting expense for user %s", user_id)
        await update.message.reply_text("Error while deleting the expense.")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Operation cancelled.", reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    return ConversationHandler.END
