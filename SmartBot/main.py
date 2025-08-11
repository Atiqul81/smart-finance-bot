import logging
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters
)
from database import setup_database
from handlers import (
    start_command,
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
from config import (
    BOT_TOKEN,
    ADD_EXPENSE_AMOUNT,
    ADD_EXPENSE_CATEGORY,
    ADD_EXPENSE_DESCRIPTION,
    SET_BUDGET_CATEGORY,
    SET_BUDGET_AMOUNT,
    DELETE_EXPENSE_ID,
)

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def main():
    """Starts the bot."""
    # Setup database
    setup_database()
    
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add conversation handler for adding expenses
    add_expense_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('add_expense', add_expense_command)],
        states={
            ADD_EXPENSE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_expense_amount)],
            ADD_EXPENSE_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_expense_category)],
            ADD_EXPENSE_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_expense_description)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # Add conversation handler for setting budgets
    set_budget_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('set_budget', set_budget_command)],
        states={
            SET_BUDGET_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_budget_category)],
            SET_BUDGET_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_budget_amount)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    # Add conversation handler for deleting expenses
    delete_expense_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('delete_expense', delete_expense_command)],
        states={
            DELETE_EXPENSE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_expense_id)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(add_expense_conv_handler)
    application.add_handler(CommandHandler("view_expenses", view_expenses_command))
    application.add_handler(CommandHandler("report", report_command))
    application.add_handler(set_budget_conv_handler)
    application.add_handler(CommandHandler("view_budget", view_budget_command))
    application.add_handler(delete_expense_conv_handler)

    # Run the bot until the user presses Ctrl-C
    logging.info("Bot is polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()