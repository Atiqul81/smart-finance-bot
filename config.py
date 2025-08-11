import os

# Telegram bot token
BOT_TOKEN = os.getenv("BOT_TOKEN", "8497175069:AAHu_4D8YHWMvmpwFLj-yuEe51Gntd8rjsI")

# PostgreSQL database connection URL
DB_URL = os.getenv("DB_URL", "postgres://postgres:Aj421981@127.0.0.1:5432/test")

# State for ConversationHandler
(
    ADD_EXPENSE_AMOUNT,
    ADD_EXPENSE_CATEGORY,
    ADD_EXPENSE_DESCRIPTION,
    SET_BUDGET_CATEGORY,
    SET_BUDGET_AMOUNT,
    DELETE_EXPENSE_ID
) = range(6)
