import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import psycopg2
from decimal import Decimal
from datetime import datetime, timedelta
from database import get_db_connection
from config import (
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

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command."""
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("INSERT INTO users (user_id, first_name) VALUES (%s, %s) ON CONFLICT (user_id) DO NOTHING", (user_id, first_name))
        conn.commit()
        
        await update.message.reply_text(f'Hello, {first_name}! I am your personal budget manager. Use me to track your expenses.')
    
    except (Exception, psycopg2.DatabaseError) as error:
        logging.error(f"Error in start_command: {error}")
        await update.message.reply_text("I'm sorry, I couldn't set up your account. Please try again later.")
    finally:
        if conn:
            cur.close()
            conn.close()

async def add_expense_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation to add a new expense."""
    await update.message.reply_text('Please enter the amount of your expense:')
    return ADD_EXPENSE_AMOUNT

async def add_expense_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the expense amount and asks for the category."""
    try:
        amount = Decimal(update.message.text)
        if amount <= 0:
            await update.message.reply_text("Amount must be a positive number. Please try again.")
            return ADD_EXPENSE_AMOUNT
        context.user_data['amount'] = amount
        await update.message.reply_text('Please enter the category of your expense (e.g., Food, Transport):')
        return ADD_EXPENSE_CATEGORY
    except (ValueError, Exception):
        await update.message.reply_text("Invalid amount. Please enter a valid number.")
        return ADD_EXPENSE_AMOUNT

async def add_expense_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the category and asks for a description."""
    context.user_data['category'] = update.message.text
    await update.message.reply_text('Please enter a short description for the expense:')
    return ADD_EXPENSE_DESCRIPTION

async def add_expense_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the description and saves the expense to the database."""
    context.user_data['description'] = update.message.text
    
    amount = context.user_data['amount']
    category_name = context.user_data['category']
    description = context.user_data['description']
    user_id = update.effective_user.id
    
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if user exists
        cur.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
        user_exists = cur.fetchone()
        if not user_exists:
            first_name = update.effective_user.first_name
            cur.execute("INSERT INTO users (user_id, first_name) VALUES (%s, %s)", (user_id, first_name))
            conn.commit()

        # Find or create category
        cur.execute("SELECT id FROM categories WHERE user_id = %s AND name = %s", (user_id, category_name))
        category = cur.fetchone()
        category_id = None
        if not category:
            cur.execute("INSERT INTO categories (user_id, name) VALUES (%s, %s) RETURNING id", (user_id, category_name))
            category_id = cur.fetchone()[0]
        else:
            category_id = category[0]

        # Insert expense
        cur.execute("INSERT INTO expenses (user_id, category_id, amount, description) VALUES (%s, %s, %s, %s)",
                    (user_id, category_id, amount, description))
        conn.commit()
        
        await update.message.reply_text(f'Expense of {amount} in category "{category_name}" has been saved.')
        
    except (Exception, psycopg2.DatabaseError) as error:
        logging.error(f"Error adding expense: {error}")
        await update.message.reply_text("I'm sorry, an error occurred while saving your expense. Please try again later.")
    finally:
        if conn:
            cur.close()
            conn.close()

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    await update.message.reply_text('Operation cancelled.')
    return ConversationHandler.END

async def view_expenses_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /view_expenses command to show all expenses."""
    user_id = update.effective_user.id
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT e.id, e.amount, c.name, e.description, e.created_at
            FROM expenses e
            JOIN categories c ON e.category_id = c.id
            WHERE e.user_id = %s
            ORDER BY e.created_at DESC
        """, (user_id,))
        expenses = cur.fetchall()
        
        if not expenses:
            await update.message.reply_text("You have not recorded any expenses yet.")
            return

        message = "Your expenses:\n\n"
        for expense in expenses:
            exp_id, amount, category, description, created_at = expense
            message += f"ID: {exp_id}\nAmount: {amount}\nCategory: {category}\nDescription: {description}\nDate: {created_at.strftime('%Y-%m-%d')}\n\n"
        
        await update.message.reply_text(message)

    except (Exception, psycopg2.DatabaseError) as error:
        logging.error(f"Error in view_expenses_command: {error}")
        await update.message.reply_text("I'm sorry, an error occurred while retrieving your expenses.")
    finally:
        if conn:
            cur.close()
            conn.close()

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /report command to show weekly and monthly expense summaries."""
    user_id = update.effective_user.id
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        message = "Expense Report:\n\n"

        # Weekly Report
        cur.execute("""
            SELECT SUM(amount) FROM expenses WHERE user_id = %s AND created_at >= %s
        """, (user_id, week_ago))
        weekly_total = cur.fetchone()[0] or Decimal(0)

        message += f"**This Week:** {weekly_total:.2f}\n"

        # Monthly Report
        cur.execute("""
            SELECT SUM(amount) FROM expenses WHERE user_id = %s AND created_at >= %s
        """, (user_id, month_ago))
        monthly_total = cur.fetchone()[0] or Decimal(0)
        
        message += f"**This Month:** {monthly_total:.2f}\n\n"

        # Category-wise Report (This Month)
        cur.execute("""
            SELECT c.name, SUM(e.amount)
            FROM expenses e
            JOIN categories c ON e.category_id = c.id
            WHERE e.user_id = %s AND e.created_at >= %s
            GROUP BY c.name
            ORDER BY SUM(e.amount) DESC
        """, (user_id, month_ago))
        monthly_categories = cur.fetchall()

        if monthly_categories:
            message += "**This Month by Category:**\n"
            for category_name, total_amount in monthly_categories:
                message += f"  - {category_name}: {total_amount:.2f}\n"

        await update.message.reply_text(message)

    except (Exception, psycopg2.DatabaseError) as error:
        logging.error(f"Error in report_command: {error}")
        await update.message.reply_text("I'm sorry, an error occurred while generating the report.")
    finally:
        if conn:
            cur.close()
            conn.close()

async def set_budget_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation to set a budget."""
    await update.message.reply_text('Please enter the category you want to set a budget for:')
    return SET_BUDGET_CATEGORY

async def set_budget_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the budget category and asks for the amount."""
    context.user_data['budget_category'] = update.message.text
    await update.message.reply_text(f'Please enter the monthly budget amount for "{update.message.text}":')
    return SET_BUDGET_AMOUNT

async def set_budget_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the budget amount and saves it to the database."""
    try:
        amount = Decimal(update.message.text)
        if amount <= 0:
            await update.message.reply_text("Budget amount must be a positive number. Please try again.")
            return SET_BUDGET_AMOUNT
        
        category_name = context.user_data['budget_category']
        user_id = update.effective_user.id
        
        conn = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Check if category already exists for the user
            cur.execute("SELECT id FROM categories WHERE user_id = %s AND name = %s", (user_id, category_name))
            category = cur.fetchone()
            
            if category:
                # If category exists, update the budget
                cur.execute("UPDATE categories SET budget = %s WHERE id = %s", (amount, category[0]))
            else:
                # If not, insert a new category with the budget
                cur.execute("INSERT INTO categories (user_id, name, budget) VALUES (%s, %s, %s)", (user_id, category_name, amount))
            
            conn.commit()
            
            await update.message.reply_text(f'Monthly budget of {amount} has been set for category "{category_name}".')
        
        except (Exception, psycopg2.DatabaseError) as error:
            logging.error(f"Error setting budget: {error}")
            await update.message.reply_text("I'm sorry, an error occurred while setting your budget.")
        finally:
            if conn:
                cur.close()
                conn.close()
        
    except (ValueError, Exception):
        await update.message.reply_text("Invalid amount. Please enter a valid number.")
        return SET_BUDGET_AMOUNT
    
    return ConversationHandler.END

async def view_budget_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /view_budget command to show budgets and spending."""
    user_id = update.effective_user.id
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT c.name, c.budget, SUM(e.amount) as total_spent
            FROM categories c
            LEFT JOIN expenses e ON c.id = e.category_id AND e.created_at >= date_trunc('month', NOW())
            WHERE c.user_id = %s
            GROUP BY c.id
            ORDER BY c.name
        """, (user_id,))
        budgets = cur.fetchall()
        
        if not budgets:
            await update.message.reply_text("You have not set any budgets yet.")
            return

        message = "Your Monthly Budgets & Spending:\n\n"
        for category_name, budget_amount, total_spent in budgets:
            total_spent = total_spent or Decimal(0)
            remaining = budget_amount - total_spent
            
            message += f"**Category:** {category_name}\n"
            message += f"  - Budget: {budget_amount:.2f}\n"
            message += f"  - Spent: {total_spent:.2f}\n"
            message += f"  - Remaining: {remaining:.2f}\n\n"
            
        await update.message.reply_text(message)

    except (Exception, psycopg2.DatabaseError) as error:
        logging.error(f"Error in view_budget_command: {error}")
        await update.message.reply_text("I'm sorry, an error occurred while retrieving your budgets.")
    finally:
        if conn:
            cur.close()
            conn.close()

async def delete_expense_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation to delete an expense."""
    await update.message.reply_text('To delete an expense, please provide the Expense ID:')
    return DELETE_EXPENSE_ID

async def delete_expense_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Deletes the expense from the database."""
    user_id = update.effective_user.id
    try:
        expense_id = int(update.message.text)
        
        conn = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Delete the expense, but only if it belongs to the current user
            cur.execute("DELETE FROM expenses WHERE id = %s AND user_id = %s", (expense_id, user_id))
            
            if cur.rowcount > 0:
                conn.commit()
                await update.message.reply_text(f'Expense with ID {expense_id} has been deleted.')
            else:
                await update.message.reply_text(f'No expense found with ID {expense_id} for your account.')
                
        except (Exception, psycopg2.DatabaseError) as error:
            logging.error(f"Error deleting expense: {error}")
            await update.message.reply_text("I'm sorry, an error occurred while deleting your expense.")
        finally:
            if conn:
                cur.close()
                conn.close()
    
    except ValueError:
        await update.message.reply_text("Invalid ID. Please enter a valid number.")
        return DELETE_EXPENSE_ID
    
    return ConversationHandler.END
