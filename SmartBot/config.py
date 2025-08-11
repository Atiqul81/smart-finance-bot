import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

# State constants for ConversationHandler
ADD_EXPENSE_AMOUNT, ADD_EXPENSE_CATEGORY, ADD_EXPENSE_DESCRIPTION = range(3)
SET_BUDGET_CATEGORY, SET_BUDGET_AMOUNT = range(2)
DELETE_EXPENSE_ID = range(1)