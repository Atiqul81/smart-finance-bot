# main.py
import logging
import json

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import (
    BOT_TOKEN,
    ADD_EXPENSE_AMOUNT,
    ADD_EXPENSE_CATEGORY,
    ADD_EXPENSE_DESCRIPTION,
    SET_BUDGET_CATEGORY,
    SET_BUDGET_AMOUNT,
    DELETE_EXPENSE_ID,
)
from database import (
    setup_database,
    get_db_connection,
    get_or_create_category_id,
)
from handlers import (
    start_command,
    button_handler,
    open_budget_command,
    open_expense_command,
    add_expense_command,
    add_expense_amount,
    add_expense_category,
    add_expense_description,
    cancel,
    view_expenses_command,
    report_command,
    set_budget_command,
    set_budget_category,
    set_budget_amount,
    view_budget_command,
    delete_expense_command,
    delete_expense_id,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# ---------------- WebApp service message handlers ---------------- #

async def webapp_data_handler(update: Update, context):
    """Handles Telegram WebApp service messages (preferred path)."""
    try:
        # 👇 এই লাইনটা try ব্লকের ভেতরেই আছে (৪ স্পেস ইন্ডেন্ট)
        logging.info(
            "WEBAPP DATA: %s",
            getattr(getattr(update, "effective_message", None), "web_app_data", None).data
            if getattr(getattr(update, "effective_message", None), "web_app_data", None)
            else "NONE",
        )

        msg = update.effective_message
        wad = getattr(msg, "web_app_data", None) if msg else None
        if not wad:
            return

        data = json.loads(wad.data)
        user_id = update.effective_user.id

        if data.get("type") == "budget.save":
            items = data.get("items", [])
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    for it in items:
                        name = (it.get("name") or "").strip()
                        amount = float(it.get("amount") or 0)
                        if not name:
                            continue
                        cat_id = get_or_create_category_id(cur, user_id, name)
                        cur.execute(
                            """
                            INSERT INTO budgets (user_id, category_id, amount, period_month)
                            VALUES (%s, %s, %s, DATE_TRUNC('month', CURRENT_DATE))
                            ON CONFLICT (user_id, category_id, period_month)
                            DO UPDATE SET amount = EXCLUDED.amount
                            """,
                            (user_id, cat_id, amount),
                        )
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Budget saved successfully ✅",
            )

        elif data.get("type") == "expense.add":
            amt = float(data.get("amount") or 0)
            cat_name = (data.get("category") or "").strip()
            desc = (data.get("description") or "").strip()
            if amt <= 0 or not cat_name:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="Invalid amount/category.",
                )
                return

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cat_id = get_or_create_category_id(cur, user_id, cat_name)
                    cur.execute(
                        "INSERT INTO expenses (user_id, category_id, amount, description) VALUES (%s, %s, %s, %s)",
                        (user_id, cat_id, amt, desc),
                    )
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Expense saved ✅ {amt:.2f} • {cat_name}",
            )

        elif data.get("type") == "expense.view":
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
                    rows = cur.fetchall()

            if not rows:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="No expenses yet.",
                )
            else:
                lines = ["Last 10 expenses:\n"]
                for exp_id, amount, cat, desc, dt in rows:
                    lines.append(
                        f"ID {exp_id} • {float(amount):.2f} • {cat or 'N/A'} • {dt.strftime('%Y-%m-%d')}"
                    )
                    if desc:
                        lines.append(f"  - {desc}")
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="\n".join(lines),
                )

        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Unknown type: {data.get('type')}",
            )

    except Exception:
        logging.exception("Error handling web_app_data")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Error processing WebApp data.",
        )


async def webapp_fallback_handler(update: Update, context):
    """
    Safety net: some clients deliver web_app_data as a regular message.
    We catch ANY message and process if web_app_data exists.
    """
    try:
        logging.info(
            "WEBAPP DATA (fallback): %s",
            getattr(getattr(update, "effective_message", None), "web_app_data", None).data
            if getattr(getattr(update, "effective_message", None), "web_app_data", None)
            else "NONE",
        )

        msg = update.effective_message
        wad = getattr(msg, "web_app_data", None) if msg else None
        if not wad:
            return

        data = json.loads(wad.data)
        user_id = update.effective_user.id

        if data.get("type") == "budget.save":
            items = data.get("items", [])
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    for it in items:
                        name = (it.get("name") or "").strip()
                        amount = float(it.get("amount") or 0)
                        if not name:
                            continue
                        cat_id = get_or_create_category_id(cur, user_id, name)
                        cur.execute(
                            """
                            INSERT INTO budgets (user_id, category_id, amount, period_month)
                            VALUES (%s, %s, %s, DATE_TRUNC('month', CURRENT_DATE))
                            ON CONFLICT (user_id, category_id, period_month)
                            DO UPDATE SET amount = EXCLUDED.amount
                            """,
                            (user_id, cat_id, amount),
                        )
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Budget saved successfully ✅",
            )

        elif data.get("type") == "expense.add":
            amt = float(data.get("amount") or 0)
            cat_name = (data.get("category") or "").strip()
            desc = (data.get("description") or "").strip()
            if amt <= 0 or not cat_name:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="Invalid amount/category.",
                )
                return

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cat_id = get_or_create_category_id(cur, user_id, cat_name)
                    cur.execute(
                        "INSERT INTO expenses (user_id, category_id, amount, description) VALUES (%s, %s, %s, %s)",
                        (user_id, cat_id, amt, desc),
                    )
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Expense saved ✅ {amt:.2f} • {cat_name}",
            )

        elif data.get("type") == "expense.view":
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
                    rows = cur.fetchall()

            if not rows:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="No expenses yet.",
                )
            else:
                lines = ["Last 10 expenses:\n"]
                for exp_id, amount, cat, desc, dt in rows:
                    lines.append(
                        f"ID {exp_id} • {float(amount):.2f} • {cat or 'N/A'} • {dt.strftime('%Y-%m-%d')}"
                    )
                    if desc:
                        lines.append(f"  - {desc}")
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="\n".join(lines),
                )

        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Unknown type: {data.get('type')}",
            )

    except Exception:
        logging.exception("Error in webapp_fallback_handler")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Error processing WebApp data.",
        )

# --------------------------- App entrypoint --------------------------- #

def main():
    """Start the bot."""
    setup_database()
    application = Application.builder().token(BOT_TOKEN).build()

    # Conversation handlers (legacy CLI flows, optional)
    add_expense_conv_handler = ConversationHandler(
        entry_points=[CommandHandler(["add_expense", "add", "a"], add_expense_command)],
        states={
            ADD_EXPENSE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_expense_amount)],
            ADD_EXPENSE_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_expense_category)],
            ADD_EXPENSE_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_expense_description)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    )

    set_budget_conv_handler = ConversationHandler(
        entry_points=[CommandHandler(["set_budget", "set", "sb"], set_budget_command)],
        states={
            SET_BUDGET_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_budget_category)],
            SET_BUDGET_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_budget_amount)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    )

    delete_expense_conv_handler = ConversationHandler(
        entry_points=[CommandHandler(["delete_expense", "delete", "d"], delete_expense_command)],
        states={
            DELETE_EXPENSE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_expense_id)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    )

    # Core menu & callbacks
    application.add_handler(CommandHandler(["start", "s"], start_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(CommandHandler(["budget"], open_budget_command))
    application.add_handler(CommandHandler(["expense"], open_expense_command))

    # Legacy quick commands
    application.add_handler(add_expense_conv_handler)
    application.add_handler(set_budget_conv_handler)
    application.add_handler(delete_expense_conv_handler)
    application.add_handler(CommandHandler(["view_expenses", "view", "v"], view_expenses_command))
    application.add_handler(CommandHandler(["report", "r"], report_command))
    application.add_handler(CommandHandler(["view_budget", "v_budget", "vb"], view_budget_command))

    # UX: reply keyboard taps (Budget/Expense/Report) loop back to the start menu
    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex(r"^(Budget|Expense|Report)$"),
            start_command,
        )
    )

    # Receive WebApp service messages
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, webapp_data_handler))

    # Fallback catcher: safety net
    application.add_handler(MessageHandler(filters.ALL, webapp_fallback_handler))

    logging.info("Bot is polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
