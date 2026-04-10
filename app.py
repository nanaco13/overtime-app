from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import sqlite3
from datetime import datetime
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import FastAPI, Form, Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets



app = FastAPI()

security = HTTPBasic()
BASIC_USER     = "kanri"
BASIC_PASSWORD = "pass1234"

def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    ok_user = secrets.compare_digest(credentials.username, BASIC_USER)
    ok_pass = secrets.compare_digest(credentials.password, BASIC_PASSWORD)
    if not (ok_user and ok_pass):
        raise HTTPException(status_code=401, detail="認証失敗",
                            headers={"WWW-Authenticate": "Basic"})

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME  = os.path.join(BASE_DIR, "db.sqlite3")

# =========================
# メール設定
# =========================
SMTP_HOST = "fortis.sakura.ne.jp"
SMTP_PORT = 587
FROM_ADDR = "nanako.oomura@fortis-frp.com"
PASSWORD  = "Fortis12051205" 

# 社長・専務
APPROVERS = ["nanako.oomura@fortis-frp.com"]

# 申請者名 → メールアドレス
APPLICANTS = {
    "大村菜々子": "nanako.oomura@○○○.com",
    "山田太郎":   "taro.yamada@○○○.com",
    "佐藤花子":   "hanako.sato@○○○.com",
    "鈴木一郎":   "ichiro.suzuki@○○○.com",
}

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
# メール送信
# =========================
def send_mail(to_list, subject, body):
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"]    = FROM_ADDR
    msg["To"]      = ", ".join(to_list)
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(FROM_ADDR, PASSWORD)
        server.sendmail(FROM_ADDR, to_list, msg.as_string())

# =========================
# フォーム表示
# =========================
@app.get("/", response_class=HTMLResponse)
def form(credentials: HTTPBasicCredentials = Depends(authenticate)):
    html_path = os.path.join(BASE_DIR, "templates", "form.html")
    with open(html_path, encoding="utf-8") as f:
        return HTMLResponse(f.read())

# =========================
# 申請
# =========================
@app.post("/apply")
def apply(
    name: str = Form(...),
    date: str = Form(...),
    hours: float = Form(...),
    reason: str = Form(...)
):
    email = APPLICANTS.get(name, "")

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
    reject_link  = f"{base_url}/reject?id={request_id}"

    body = f"""残業申請があります

名前: {name}
日付: {date}
時間: {hours}時間
理由: {reason}

承認: {approve_link}
却下: {reject_link}
"""
    send_mail(APPROVERS, f"【残業申請】{name}", body)

    return HTMLResponse("<h2>申請完了しました。承認者にメールを送信しました。</h2>")

# =========================
# 承認
# =========================
@app.get("/approve")
def approve(id: int):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT name, email, date, hours, reason FROM overtime_requests WHERE id=?", (id,))
    row = cur.fetchone()
    cur.execute("""
        UPDATE overtime_requests
        SET status='approved', approved_at=?, approved_by=?
        WHERE id=?
    """, (datetime.now(), "承認者", id))
    conn.commit()
    conn.close()

    if row:
        name, email, date, hours, reason = row
        body = f"""残業申請が承認されました

名前: {name}
日付: {date}
時間: {hours}時間
理由: {reason}
"""
        send_mail([email] + APPROVERS, f"【承認】残業申請　{name}", body)

    return HTMLResponse("<h2>承認しました。申請者と承認者全員にメールを送信しました。</h2>")

# =========================
# 却下
# =========================
@app.get("/reject")
def reject(id: int):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT name, email, date, hours, reason FROM overtime_requests WHERE id=?", (id,))
    row = cur.fetchone()
    cur.execute("""
        UPDATE overtime_requests
        SET status='rejected', approved_at=?, approved_by=?
        WHERE id=?
    """, (datetime.now(), "承認者", id))
    conn.commit()
    conn.close()

    if row:
        name, email, date, hours, reason = row
        body = f"""残業申請が却下されました

名前: {name}
日付: {date}
時間: {hours}時間
理由: {reason}
"""
        send_mail([email] + APPROVERS, f"【却下】残業申請　{name}", body)

    return HTMLResponse("<h2>却下しました。申請者と承認者全員にメールを送信しました。</h2>")

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