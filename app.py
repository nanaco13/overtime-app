from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import sqlite3
from datetime import datetime
import os

app = FastAPI()

# テンプレートパス（Render対応）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

DB_NAME = "db.sqlite3"

# =========================
# DB初期化
# =========================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS overtime_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            date TEXT,
            hours REAL,
            reason TEXT,
            status TEXT,
            created_at TEXT,
            approved_at TEXT,
            approved_by TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# =========================
# メール送信（一旦停止）
# =========================
def send_mail(to_list, subject, html_body):
    print("メール送信スキップ")

# =========================
# フォーム表示
# =========================
@app.get("/", response_class=HTMLResponse)
def form(request: Request):
    return templates.TemplateResponse("form.html", {"request": request})

# =========================
# 申請
# =========================
@app.post("/apply")
def apply(
    name: str = Form(...),
    email: str = Form(...),
    date: str = Form(...),
    hours: float = Form(...),
    reason: str = Form(...)
):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO overtime_requests
        (name, email, date, hours, reason, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'pending', ?)
    """, (name, email, date, hours, reason, datetime.now()))

    request_id = cur.lastrowid
    conn.commit()
    conn.close()

    base_url = "https://overtime-app2.onrender.com"

    approve_link = f"{base_url}/approve?id={request_id}"
    reject_link = f"{base_url}/reject?id={request_id}"

    html_body = f"""
    残業申請があります

    名前: {name}
    日付: {date}
    時間: {hours}
    理由: {reason}

    承認: {approve_link}
    却下: {reject_link}
    """

    send_mail(["test@example.com"], "残業申請", html_body)

    return HTMLResponse("<h2>申請完了しました</h2>")

# =========================
# 承認
# =========================
@app.get("/approve")
def approve(id: int):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        UPDATE overtime_requests
        SET status='approved',
            approved_at=?,
            approved_by=?
        WHERE id=?
    """, (datetime.now(), "承認者", id))

    conn.commit()
    conn.close()

    return HTMLResponse("<h2>承認しました</h2>")

# =========================
# 却下
# =========================
@app.get("/reject")
def reject(id: int):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        UPDATE overtime_requests
        SET status='rejected',
            approved_at=?,
            approved_by=?
        WHERE id=?
    """, (datetime.now(), "承認者", id))

    conn.commit()
    conn.close()

    return HTMLResponse("<h2>却下しました</h2>")

# =========================
# 履歴
# =========================
@app.get("/history", response_class=HTMLResponse)
def history():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("SELECT * FROM overtime_requests ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()

    html = """
    <html><body>
    <h2>申請履歴</h2>
    <table border="1">
    <tr>
    <th>ID</th><th>名前</th><th>メール</th><th>日付</th><th>時間</th>
    <th>理由</th><th>状態</th><th>申請日時</th><th>承認日時</th><th>担当</th>
    </tr>
    """

    for r in rows:
        html += "<tr>" + "".join(f"<td>{x}</td>" for x in r) + "</tr>"

    html += "</table></body></html>"

    return HTMLResponse(html)