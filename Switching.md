# Legal Invoice Platform — Branch Pull & Local Setup Guide

This guide explains the recommended workflow for switching to or pulling a new Git branch and running the Legal Invoice Platform locally.

## Project Stack

- Backend: FastAPI + Uvicorn
- Frontend: Streamlit
- Database: SQLite
- Python environment: `.venv`

## 1. Check Your Current Git State

Always check for local changes before switching branches:

```bash
git status
git branch --show-current
```

If you have important changes, commit and push them:

```bash
git add .
git commit -m "your commit message"
git push
```

If the changes are temporary:

```bash
git stash
```

View stashes:

```bash
git stash list
```

## 2. Fetch Remote Branches

```bash
git fetch origin
```

List remote branches:

```bash
git branch -r
```

Example:

```text
origin/main
origin/dev-13Aug-rajat
origin/dev-with-frontend
```

## 3. Switch to a Remote Branch

If the branch does not exist locally:

```bash
git switch -c BRANCH_NAME --track origin/BRANCH_NAME
```

Example:

```bash
git switch -c dev-with-frontend --track origin/dev-with-frontend
```

If it already exists locally:

```bash
git switch BRANCH_NAME
```

Then pull the latest code:

```bash
git pull origin BRANCH_NAME
```

Verify:

```bash
git status
git branch --show-current
```

## 4. Check Environment Variables

The backend environment file is:

```text
backend/.env
```

Check whether it exists:

```bash
ls -la backend/.env
```

If it does not exist:

```bash
cp backend/.env.example backend/.env
```

Edit it:

```bash
code backend/.env
```

Typical configuration:

```env
DATABASE_URL=sqlite:////absolute/path/to/project/backend/legal_invoice.db
JWT_SECRET=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### Important

Never commit `.env` to GitHub.

Make sure `.gitignore` contains:

```gitignore
.env
*.db
*.db.backup
```

## 5. Activate the Virtual Environment

From the project root:

```bash
source .venv/bin/activate
```

Verify:

```bash
which python
python --version
```

## 6. Install Branch Dependencies

Every branch can have a different `requirements.txt`.

After pulling a branch:

```bash
cd backend
python -m pip install -r requirements.txt
```

Optional:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Return to project root:

```bash
cd ..
```

## 7. Important: Check the SQLite Database

Git pulls source code, but it does not automatically update an existing SQLite database schema.

For example, new code may expect:

```text
budget_valid
duplicate_flag
validation_status
validation_message
```

while an older database may not contain these columns.

This can produce errors such as:

```text
sqlite3.OperationalError:
no such column: invoices.budget_valid
```

### Find all database files

```bash
find . -name "*.db" -type f -print
```

### Find the database used by the application

```bash
grep -R "DATABASE_URL\|legal_invoice.db\|sqlite" -n backend/app backend/.env 2>/dev/null
```

For the current project configuration, the application database is:

```text
backend/legal_invoice.db
```

## 8. Always Back Up the Database Before Recreating It

Before deleting or recreating the database:

```bash
cp backend/legal_invoice.db backend/legal_invoice.db.backup
```

Verify:

```bash
ls -lh backend/legal_invoice.db*
```

Do not commit the backup.

If it appears in:

```bash
git status
```

do not run `git add .` blindly.

## 9. Check Whether the Project Uses Migrations

Check for schema creation:

```bash
grep -R "create_all" -n backend/app
```

Check for migration tools:

```bash
find backend -maxdepth 3 -type f | grep -Ei "alembic|migration|migrate"
```

### Important

`Base.metadata.create_all()` creates missing tables, but it does not update the structure of an existing table.

If the project has a proper migration system such as Alembic, prefer the migration process.

If there is no migration system and the branch requires a fresh development database, recreate the database as described below.

## 10. Recreate the Development Database

Only do this when you have confirmed that the branch requires a fresh schema and you have a backup.

From the project root:

```bash
cp backend/legal_invoice.db backend/legal_invoice.db.backup
rm backend/legal_invoice.db
```

Then:

```bash
# in one terminal
cd backend
uvicorn app.main:app --reload

# then run seed.py and seed_matter_budget.py in separate terminal
cd backend
python3 -m app.database.seed
python3 -m app.database.seed_matter_budget

# in other terminal
cd frontend
streamlit run home.py
```

This creates the database schema and the development admin user.

Current development credentials:

```text
Email: admin@test.com
Password: admin123
```

Then seed the firm, matter, and budget:

```bash
python -m app.database.seed_matter_budget
```

Expected development seed data:

```text
Firm ID: 1
Matter ID: 1
Budget: 50000
```

## 11. Verify the Database Schema

Check the invoices table:

```bash
sqlite3 backend/legal_invoice.db "PRAGMA table_info(invoices);"
```

For the current `dev-with-frontend` branch, the Invoice model expects fields including:

```text
invoice_id
matter_id
firm_id
invoice_no
invoice_date
total_amount
status
confidence_score
budget_valid
duplicate_flag
validation_status
validation_message
```

If required columns are missing, stop and investigate the database/schema before starting the frontend.

## 12. Verify Seed Data

Check the admin user:

```bash
sqlite3 backend/legal_invoice.db "SELECT email, role FROM users;"
```

Check firms:

```bash
sqlite3 backend/legal_invoice.db "SELECT firm_id, name FROM firms;"
```

Check matters:

```bash
sqlite3 backend/legal_invoice.db "SELECT matter_id, firm_id, name FROM matters;"
```

Check budgets:

```bash
sqlite3 backend/legal_invoice.db "SELECT matter_id, allocated_amt, threshold_pct FROM budgets;"
```

## 13. Start the Backend

Open Terminal 1.

From the project root:

```bash
source .venv/bin/activate
cd backend
uvicorn app.main:app --reload
```

Keep this terminal open so backend errors and invoice-processing logs are visible.

Expected:

```text
Uvicorn running on http://127.0.0.1:8000
```

## 14. Start the Frontend

Open Terminal 2.

From the project root:

```bash
source .venv/bin/activate
cd frontend
streamlit run Home.py
```

If the project uses lowercase `home.py`, use:

```bash
streamlit run home.py
```

Check the actual filename with:

```bash
ls
```

## 15. Login

Current development credentials:

```text
Email: admin@test.com
Password: admin123
```

## 16. Test Invoice Upload

Go to:

```text
Invoices
    ↓
Upload Invoice
    ↓
Select PDF
    ↓
Submit
```

At the same time, monitor the Uvicorn terminal for backend logs.

## 17. Troubleshooting

### Error: `no such column`

Example:

```text
sqlite3.OperationalError:
no such column: invoices.budget_valid
```

Likely cause:

```text
New branch code
        +
Old SQLite database
        =
Schema mismatch
```

Check:

```bash
sqlite3 backend/legal_invoice.db "PRAGMA table_info(invoices);"
```

If the branch requires a new schema and there is no migration process:

```bash
cp backend/legal_invoice.db backend/legal_invoice.db.backup
rm backend/legal_invoice.db
cd backend
python -m app.database.seed
python -m app.database.seed_matter_budget
```

### Error: `ModuleNotFoundError`

Example:

```text
ModuleNotFoundError: No module named 'xyz'
```

Run:

```bash
cd backend
python -m pip install -r requirements.txt
```

### Database connection error

Check:

```bash
grep DATABASE_URL backend/.env
```

Make sure it points to the intended database.

### Authentication problems

Check:

```text
backend/.env
```

Especially:

```env
JWT_SECRET=
ALGORITHM=
ACCESS_TOKEN_EXPIRE_MINUTES=
```

## 18. Recommended Complete Workflow

For a normal new branch:

```bash
# Check current work
git status
git branch --show-current

# Fetch remote branches
git fetch origin

# Switch to the required branch
git switch -c BRANCH_NAME --track origin/BRANCH_NAME

# Pull latest code
git pull origin BRANCH_NAME

# Activate environment
source .venv/bin/activate

# Install dependencies
python -m pip install -r backend/requirements.txt

# Check environment
cat backend/.env

# Check database configuration
grep DATABASE_URL backend/.env

# Check database files
find . -name "*.db" -type f -print
```

Then determine whether the branch requires a database migration or a fresh database.

If a fresh development database is required:

```bash
cp backend/legal_invoice.db backend/legal_invoice.db.backup
rm backend/legal_invoice.db

cd backend
python3 -m app.database.seed
python3 -m app.database.seed_matter_budget
```

Then start the backend:

```bash
uvicorn app.main:app --reload
```

In another terminal:

```bash
source .venv/bin/activate
cd frontend
streamlit run Home.py
```

## 19. Quick Checklist

Before running a newly pulled branch:

- [ ] `git status` checked
- [ ] Local changes committed/stashed
- [ ] `git fetch origin`
- [ ] Correct branch selected
- [ ] `git pull` completed
- [ ] `backend/.env` exists and has required secrets
- [ ] `.venv` activated
- [ ] `requirements.txt` installed
- [ ] Correct SQLite database identified
- [ ] Database backed up before recreation
- [ ] Database schema verified
- [ ] Seed scripts executed if required
- [ ] Backend started successfully
- [ ] Frontend started successfully
- [ ] Login tested
- [ ] Invoice upload tested
- [ ] Backend logs checked

## 20. Golden Rules

1. **Git pull updates code, not your SQLite schema.**

2. **Always back up the database before recreating it.**

```bash
cp backend/legal_invoice.db backend/legal_invoice.db.backup
```

3. **Check `backend/.env` after switching branches.**

4. **Install the branch's `requirements.txt` after pulling.**

5. **Check backend logs first when invoice upload returns HTTP 500.**

6. **Do not run `git add .` blindly when you have local `.env`, `.db`, or `.db.backup` files.**

7. **Do not delete a database until you have confirmed which database the application actually uses.**

8. **If a migration system exists, prefer migrations over deleting the database.**

9. **Keep development databases/backups out of Git unless the team explicitly requires them.**

10. **Before merging changes between branches, verify model/schema differences such as `matter_id` types and invoice fields.**
