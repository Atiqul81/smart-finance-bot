-- Period-based budgets (one per user/category per month)
ALTER TABLE budgets
  ADD COLUMN IF NOT EXISTS period_month DATE NOT NULL DEFAULT DATE_TRUNC('month', CURRENT_DATE);

-- Ensure uniqueness per month
CREATE UNIQUE INDEX IF NOT EXISTS budgets_user_cat_month
  ON budgets(user_id, category_id, period_month);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS expenses_user_date_idx
  ON expenses(user_id, date);

CREATE INDEX IF NOT EXISTS expenses_category_idx
  ON expenses(category_id);