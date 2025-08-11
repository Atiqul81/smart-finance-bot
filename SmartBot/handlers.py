import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from decimal import Decimal
from datetime import datetime
from database import get_db_connection
from config import (
    ADD_EXPENSE_AMOUNT,
    ADD_EXPENSE_CATEGORY,
    ADD_EXPENSE_DESCRIPTION,
    SET_BUDGET_CATEGORY,
    SET_BUDGET_AMOUNT,
    DELETE_EXPENSE_ID,
)

# --- Utility Functions ---

def get_or_create_category_id(cur, user_id, category_name):
    cur.execute("SELECT id FROM categories WHERE user_id = %s AND name = %s", (user_id, category_name))
    category = cur.fetchone()
    if category:
        return category[0]
    else:
        cur.execute("INSERT INTO categories (user_id, name) VALUES (%s, %s) RETURNING id", (user_id, category_name))
        return cur.fetchone()[0]

def get_expense_categories(user_id):
    categories = []
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT name FROM categories WHERE user_id = %s ORDER BY name", (user_id,))
                categories = [row[0] for row in cur.fetchall()]
    except Exception:
        logging.exception(f"Error retrieving categories for user {user_id}")
    return categories

def build_category_keyboard(categories):
    keyboard = [[category] for category in categories]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

# --- Command Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO users (user_id, first_name) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET first_name = EXCLUDED.first_name", (user_id, first_name))
        
        keyboard = [['/add_expense', '/view_expenses'], ['/report', '/set_budget', '/view_budget'], ['/delete_expense']]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=False, resize_keyboard=True)
        await update.message.reply_text(
            f'Hello, {first_name}! I am your personal budget manager. Use the buttons below or type a command to get started.',
            reply_markup=reply_markup
        )
    except Exception:
        logging.exception(f"Error in start_command for user {user_id}")
        await update.message.reply_text("I'm sorry, I couldn't set up your account. Please try again later.")

async def add_expense_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Please enter the amount of your expense:")
    return ADD_EXPENSE_AMOUNT

async def add_expense_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        amount = Decimal(update.message.text.strip())
        if amount <= 0:
            await update.message.reply_text("Amount must be a positive number. Please try again.")
            return ADD_EXPENSE_AMOUNT
        context.user_data['amount'] = amount
        
        categories = get_expense_categories(update.effective_user.id)
        keyboard = build_category_keyboard(categories) if categories else None
        await update.message.reply_text('Please select a category or type a new one:', reply_markup=keyboard)
        return ADD_EXPENSE_CATEGORY
    except (ValueError, Exception):
        await update.message.reply_text("Invalid amount. Please enter a valid number.")
        return ADD_EXPENSE_AMOUNT

async def add_expense_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['category'] = update.message.text.strip()
    await update.message.reply_text("Great! Now, please enter a short description for the expense:")
    return ADD_EXPENSE_DESCRIPTION

async def add_expense_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['description'] = update.message.text.strip()
    amount = context.user_data['amount']
    category_name = context.user_data['category']
    description = context.user_data['description']
    user_id = update.effective_user.id
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                category_id = get_or_create_category_id(cur, user_id, category_name)
                cur.execute("INSERT INTO expenses (user_id, category_id, amount, description) VALUES (%s, %s, %s, %s)",
                            (user_id, category_id, amount, description))
        await update.message.reply_text(
            f'✅ Expense of {amount} in category "{category_name}" has been saved successfully!',
            reply_markup=ReplyKeyboardRemove()
        )
    except Exception:
        logging.exception(f"Error adding expense for user {user_id}")
        await update.message.reply_text("I'm sorry, an error occurred while saving your expense. Please try again later.")
    finally:
        context.user_data.clear()
    return ConversationHandler.END

async def view_expenses_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT e.id, e.amount, c.name, e.description, e.date
                    FROM expenses e LEFT JOIN categories c ON e.category_id = c.id
                    WHERE e.user_id = %s ORDER BY e.date DESC LIMIT 10
                """, (user_id,))
                expenses = cur.fetchall()
        
        if not expenses:
            await update.message.reply_text('You have no expenses recorded yet. Use /add_expense to start.')
            return
            
        message = "Your 10 latest expenses:\n\n"
        for expense in expenses:
            message += f"🆔 *ID:* {expense[0]}\n💵 *Amount:* {expense[1]:.2f}\n📂 *Category:* {expense[2] or 'N/A'}\n📝 *Description:* {expense[3] or 'N/A'}\n📅 *Date:* {expense[4].strftime('%Y-%m-%d')}\n\n"
        await update.message.reply_text(message, parse_mode='Markdown')
    except Exception:
        logging.exception(f"Error retrieving expenses for user {user_id}")
        await update.message.reply_text("I'm sorry, an error occurred while retrieving your expenses.")

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                today = datetime.now()
                start_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                
                cur.execute("SELECT SUM(amount) FROM expenses WHERE user_id = %s AND date >= %s", (user_id, start_of_month))
                total_expense = cur.fetchone()[0]

                if total_expense is None:
                    await update.message.reply_text("You have no expenses recorded this month.")
                    return

                cur.execute("""
                    SELECT c.name, SUM(e.amount) FROM expenses e JOIN categories c ON e.category_id = c.id
                    WHERE e.user_id = %s AND e.date >= %s GROUP BY c.name ORDER BY SUM(e.amount) DESC
                """, (user_id, start_of_month))
                category_expenses = cur.fetchall()

        message = f"📊 *Monthly Report for {today.strftime('%B, %Y')}*\n\nTotal Expenses: *{total_expense:.2f}*\n\n*Breakdown by Category:*\n"
        for category, amount in category_expenses:
            message += f"- {category}: {amount:.2f}\n"
        await update.message.reply_text(message, parse_mode='Markdown')
    except Exception:
        logging.exception(f"Error generating report for user {user_id}")
        await update.message.reply_text("I'm sorry, an error occurred while generating your report.")

async def set_budget_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    categories = get_expense_categories(update.effective_user.id)
    keyboard = build_category_keyboard(categories) if categories else None
    await update.message.reply_text('Please select a category for the budget or type a new one:', reply_markup=keyboard)
    return SET_BUDGET_CATEGORY

async def set_budget_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['budget_category'] = update.message.text.strip()
    await update.message.reply_text("Please enter the monthly budget amount for this category:")
    return SET_BUDGET_AMOUNT

async def set_budget_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    category_name = context.user_data['budget_category']
    amount_text = update.message.text.strip()
    
    try:
        amount = Decimal(amount_text)
        if amount <= 0:
            await update.message.reply_text("Amount must be a positive number. Please try again.")
            return SET_BUDGET_AMOUNT
            
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                category_id = get_or_create_category_id(cur, user_id, category_name)
                cur.execute("""
                    INSERT INTO budgets (user_id, category_id, amount) VALUES (%s, %s, %s)
                    ON CONFLICT (user_id, category_id) DO UPDATE SET amount = EXCLUDED.amount
                """, (user_id, category_id, amount))
        await update.message.reply_text(f'✅ Budget of {amount} for category "{category_name}" has been set successfully!', reply_markup=ReplyKeyboardRemove())
    except ValueError:
        await update.message.reply_text("Invalid amount. Please enter a valid number.")
        return SET_BUDGET_AMOUNT
    except Exception:
        logging.exception(f"Error setting budget for user {user_id}")
        await update.message.reply_text("I'm sorry, an error occurred while setting your budget.")
    finally:
        context.user_data.clear()
    return ConversationHandler.END

async def view_budget_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT c.name, b.amount FROM budgets b JOIN categories c ON b.category_id = c.id
                    WHERE b.user_id = %s ORDER BY c.name
                """, (user_id,))
                budgets = cur.fetchall()
        
        if not budgets:
            await update.message.reply_text('You have no budgets set yet. Use /set_budget to create one.')
            return
            
        message = "Your current monthly budgets:\n\n"
        for budget in budgets:
            message += f"📂 *{budget[0]}*: {budget[1]:.2f}\n"
        await update.message.reply_text(message, parse_mode='Markdown')
    except Exception:
        logging.exception(f"Error retrieving budgets for user {user_id}")
        await update.message.reply_text("I'm sorry, an error occurred while retrieving your budgets.")

async def delete_expense_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await view_expenses_command(update, context) # This might show an error if view_expenses fails, which is okay.
    await update.message.reply_text("\nAbove are your recent expenses. Please enter the ID of the expense you want to delete:")
    return DELETE_EXPENSE_ID
    
async def delete_expense_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    expense_id_text = update.message.text.strip()
    try:
        expense_id = int(expense_id_text)
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM expenses WHERE id = %s AND user_id = %s RETURNING id", (expense_id, user_id))
                deleted_row = cur.fetchone()
        
        if deleted_row:
            await update.message.reply_text(f'✅ Expense with ID {expense_id} has been deleted.')
        else:
            await update.message.reply_text('⚠️ No expense found with that ID or you do not have permission to delete it.')
    except ValueError:
        await update.message.reply_text("Invalid ID. Please enter a valid number.")
    except Exception:
        logging.exception(f"Error deleting expense {expense_id_text} for user {user_id}")
        await update.message.reply_text("An error occurred while trying to delete the expense.")
    return ConversationHandler.END

# Dummy cancel function for states without a specific one.
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    await update.message.reply_text('Operation cancelled.', reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    return ConversationHandler.END