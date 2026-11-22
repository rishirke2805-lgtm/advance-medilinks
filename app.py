# Initialize database automatically on startup (required for Gunicorn/Render)

import csv
import io
import re
from config import Config
from database import get_db, init_db

app = Flask(__name__)
app.config.from_object(Config)
init_db()

from datetime import datetime
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    Response,
)
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from config import Config
from database import get_db, init_db

# -----------------------------------------------------------------------------
# 1. Initialize Application First
# -----------------------------------------------------------------------------
app = Flask(__name__)
app.config.from_object(Config)

# -----------------------------------------------------------------------------
# 2. Public Form Routes
# -----------------------------------------------------------------------------
@app.route("/")
def register_form():
    """Render public event registration form."""
    return render_template("register.html")

@app.route("/register", methods=["POST"])
def submit_registration():
    """Process attendee form submission and persist to SQLite."""
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    city = request.form.get("city", "").strip()
    notes = request.form.get("notes", "").strip()

    # Server-side validation
    if not all([full_name, email, phone, city]):
        flash("Please complete all required fields (Name, Email, Phone, City).", "danger")
        return redirect(url_for("register_form"))

    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        flash("Please provide a valid email address.", "danger")
        return redirect(url_for("register_form"))

    with get_db() as conn:
        cursor = conn.cursor()
        # Inspect columns to support both fresh databases and existing databases
        cursor.execute("PRAGMA table_info(registrations);")
        existing_cols = [col["name"] for col in cursor.fetchall()]

        if "ticket_type" in existing_cols:
            cursor.execute("""
                INSERT INTO registrations (full_name, email, phone, city, ticket_type, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (full_name, email, phone, city, "Standard", notes))
        else:
            cursor.execute("""
                INSERT INTO registrations (full_name, email, phone, city, notes)
                VALUES (?, ?, ?, ?, ?)
            """, (full_name, email, phone, city, notes))
        reg_id = cursor.lastrowid

    return redirect(url_for("registration_success", reg_id=reg_id))

@app.route("/success")
def registration_success():
    """Display registration confirmation screen."""
    reg_id = request.args.get("reg_id")
    if not reg_id:
        return redirect(url_for("register_form"))

    with get_db() as conn:
        reg = conn.execute("SELECT * FROM registrations WHERE id = ?", (reg_id,)).fetchone()

    if not reg:
        flash("Registration record not found.", "warning")
        return redirect(url_for("register_form"))

    return render_template("success.html", reg=reg)

# -----------------------------------------------------------------------------
# 3. Admin & Data Management Routes
# -----------------------------------------------------------------------------
@app.route("/admin")
def admin_dashboard():
    """Admin overview with live search and aggregate metrics."""
    query = request.args.get("q", "").strip()
    conn = get_db()

    total_count = conn.execute("SELECT COUNT(*) AS total FROM registrations").fetchone()["total"]
    
    # Calculate unique cities count
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(registrations);")
    cols = [c["name"] for c in cursor.fetchall()]
    
    if "city" in cols:
        city_count = conn.execute(
            "SELECT COUNT(DISTINCT city) AS total_cities FROM registrations WHERE city != ''"
        ).fetchone()["total_cities"]
    else:
        city_count = 0

    if query:
        pattern = f"%{query}%"
        if "city" in cols:
            rows = conn.execute("""
                SELECT * FROM registrations
                WHERE full_name LIKE ? OR email LIKE ? OR phone LIKE ? OR city LIKE ? OR notes LIKE ?
                ORDER BY created_at DESC
            """, (pattern, pattern, pattern, pattern, pattern)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM registrations
                WHERE full_name LIKE ? OR email LIKE ? OR phone LIKE ? OR notes LIKE ?
                ORDER BY created_at DESC
            """, (pattern, pattern, pattern, pattern)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM registrations ORDER BY created_at DESC").fetchall()

    conn.close()
    return render_template(
        "admin.html",
        rows=rows,
        total_count=total_count,
        city_count=city_count,
        query=query
    )

@app.route("/admin/export")
def export_csv():
    """Stream registrations to a downloadable CSV file."""
    query = request.args.get("q", "").strip()
    conn = get_db()

    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(registrations);")
    cols = [c["name"] for c in cursor.fetchall()]

    if query:
        pattern = f"%{query}%"
        if "city" in cols:
            rows = conn.execute("""
                SELECT * FROM registrations
                WHERE full_name LIKE ? OR email LIKE ? OR phone LIKE ? OR city LIKE ? OR notes LIKE ?
                ORDER BY created_at DESC
            """, (pattern, pattern, pattern, pattern, pattern)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM registrations
                WHERE full_name LIKE ? OR email LIKE ? OR phone LIKE ? OR notes LIKE ?
                ORDER BY created_at DESC
            """, (pattern, pattern, pattern, pattern)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM registrations ORDER BY created_at DESC").fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Reference ID", "Registration Date", "Full Name", "Email Address", "Phone", "City", "Notes"])

    for r in rows:
        city_val = r["city"] if "city" in r.keys() else ""
        writer.writerow([
            f"#REG-{r['id']:04d}",
            r["created_at"],
            r["full_name"],
            r["email"],
            r["phone"],
            city_val,
            r["notes"]
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=event_registrations.csv"}
    )

@app.route("/admin/export-excel")
def export_excel():
    """Convert the entire SQLite database into a styled multi-sheet Excel (.xlsx) workbook."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [row["name"] for row in cursor.fetchall()]

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4F46E5", end_color="4F46E5", fill_type="solid")
    data_font = Font(name="Segoe UI", size=10)
    thin_border = Border(
        left=Side(style="thin", color="E2E8F0"),
        right=Side(style="thin", color="E2E8F0"),
        top=Side(style="thin", color="E2E8F0"),
        bottom=Side(style="thin", color="E2E8F0"),
    )

    for table_name in tables:
        ws = wb.create_sheet(title=table_name.capitalize())
        ws.views.sheetView[0].showGridLines = True

        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = [col["name"] for col in cursor.fetchall()]

        for col_idx, col_name in enumerate(columns, start=1):
            cell = ws.cell(row=1, column=col_idx, value=col_name.replace("_", " ").title())
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = thin_border
        ws.row_dimensions[1].height = 26

        cursor.execute(f"SELECT * FROM {table_name} ORDER BY id ASC;")
        rows = cursor.fetchall()
        for row_idx, row in enumerate(rows, start=2):
            for col_idx, col_name in enumerate(columns, start=1):
                val = row[col_name]
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.font = data_font
                cell.border = thin_border
                if col_name == "id":
                    cell.alignment = Alignment(horizontal="center")
                elif col_name in ("created_at", "email", "phone"):
                    cell.alignment = Alignment(horizontal="left")
            ws.row_dimensions[row_idx].height = 20

        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val_str = str(cell.value or "")
                if len(val_str) > max_len:
                    max_len = len(val_str)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    conn.close()

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"database_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return Response(
        output.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

@app.route("/admin/delete/<int:reg_id>", methods=["POST"])
def delete_registration(reg_id):
    """Delete an individual registration record."""
    with get_db() as conn:
        conn.execute("DELETE FROM registrations WHERE id = ?", (reg_id,))
    flash(f"Registration #REG-{reg_id:04d} removed successfully.", "warning")
    return redirect(url_for("admin_dashboard"))

# -----------------------------------------------------------------------------
# 4. Entry Point
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    init_db()
    print("=" * 60)
    print(" Server Running")
    print(" Public Form:     http://127.0.0.1:5000/")
    print(" Admin Console:   http://127.0.0.1:5000/admin")
    print("=" * 60)
    app.run(debug=True, host="127.0.0.1", port=5000)
