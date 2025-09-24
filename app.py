
import os, secrets, re, csv, io, datetime
from collections import Counter

from flask import Flask, render_template, request, redirect, url_for, flash, session, abort, send_file
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "changeme")

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set. Provide a Postgres connection string.")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()

class Response(Base):
    __tablename__ = "responses"
    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    name = Column(String(80), nullable=False)
    role = Column(String(30), nullable=False)
    store_type = Column(String(30), nullable=False)

    satisfaction = Column(Integer, nullable=False)
    frequency = Column(String(20), nullable=False)

    brand_perception = Column(String(20), nullable=False)
    primary_diaper_brand = Column(String(60), nullable=True)

    open_feedback = Column(Text, nullable=True)

def init_db():
    Base.metadata.create_all(engine)

STEPS = [1,2,3,4]
TOTAL_STEPS = len(STEPS)

def ensure_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(16)
    return session["csrf_token"]

def validate_csrf():
    token_form = request.form.get("_csrf", "")
    if not token_form or token_form != session.get("csrf_token"):
        abort(400, description="Invalid CSRF token.")

def require_step(step_no):
    allowed = session.get("allowed_step", 1)
    if step_no != allowed:
        return redirect(url_for(f"step{allowed}"))
    return None

def progress_pct(step_no):
    return int((step_no-1) / TOTAL_STEPS * 100)

def require_admin():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))
    return None

@app.route("/")
def home():
    session.setdefault("allowed_step", 1)
    ensure_csrf_token()
    return redirect(url_for("step1"))

@app.route("/back/<int:from_step>")
def back(from_step):
    prev_step = max(1, from_step - 1)
    session["allowed_step"] = prev_step
    return redirect(url_for(f"step{prev_step}"))

@app.route("/step1", methods=["GET","POST"])
def step1():
    guard = require_step(1)
    if guard: return guard
    csrf = ensure_csrf_token()

    if request.method == "POST":
        validate_csrf()
        name = request.form.get("name","").strip()
        role = request.form.get("role","").strip()
        store_type = request.form.get("store_type","").strip()

        errors = []
        if not (2 <= len(name) <= 60) or not re.match(r"^[\w\s\-\.'À-ỹ]+$", name):
            errors.append("Tên 2–60 ký tự, không chứa ký tự lạ.")
        if role not in {"Owner","Manager","Staff"}:
            errors.append("Vai trò không hợp lệ.")
        if store_type not in {"Grocery","Pharmacy","Baby Store","Other"}:
            errors.append("Loại cửa hàng không hợp lệ.")

        if errors:
            for e in errors: flash(e, "error")
            return render_template("step1.html", csrf=csrf, step=1, total=TOTAL_STEPS, progress=progress_pct(1))

        session.update({"name": name, "role": role, "store_type": store_type})
        session["allowed_step"] = 2
        return redirect(url_for("step2"))

    return render_template("step1.html", csrf=csrf, step=1, total=TOTAL_STEPS, progress=progress_pct(1))

@app.route("/step2", methods=["GET","POST"])
def step2():
    guard = require_step(2)
    if guard: return guard
    csrf = ensure_csrf_token()

    if request.method == "POST":
        validate_csrf()
        satisfaction = request.form.get("satisfaction","").strip()
        frequency = request.form.get("frequency","").strip()

        errors = []
        try:
            s = int(satisfaction)
            if s < 1 or s > 5: errors.append("Mức độ hài lòng phải từ 1 đến 5.")
        except: errors.append("Mức độ hài lòng phải là số hợp lệ.")
        if frequency not in {"Weekly","Monthly","Less often"}:
            errors.append("Tần suất đặt hàng không hợp lệ.")

        if errors:
            for e in errors: flash(e, "error")
            return render_template("step2.html", csrf=csrf, step=2, total=TOTAL_STEPS, progress=progress_pct(2), store_type=session.get("store_type",""))

        session.update({"satisfaction": int(satisfaction), "frequency": frequency})
        session["allowed_step"] = 3
        return redirect(url_for("step3"))

    return render_template("step2.html", csrf=csrf, step=2, total=TOTAL_STEPS, progress=progress_pct(2), store_type=session.get("store_type",""))

@app.route("/step3", methods=["GET","POST"])
def step3():
    guard = require_step(3)
    if guard: return guard
    csrf = ensure_csrf_token()

    if request.method == "POST":
        validate_csrf()
        brand_perception = request.form.get("brand_perception","").strip()
        primary_diaper_brand = request.form.get("primary_diaper_brand","").strip()

        errors = []
        if brand_perception not in {"Agree","Neutral","Disagree"}:
            errors.append("Cảm nhận thương hiệu không hợp lệ.")
        if session.get("store_type") == "Baby Store":
            if not (1 <= len(primary_diaper_brand) <= 40):
                errors.append("Vui lòng nhập thương hiệu tã chính (tối đa 40 ký tự).")

        if errors:
            for e in errors: flash(e, "error")
            return render_template("step3.html", csrf=csrf, step=3, total=TOTAL_STEPS, progress=progress_pct(3), is_baby_store=session.get("store_type")=="Baby Store")

        session.update({"brand_perception": brand_perception, "primary_diaper_brand": primary_diaper_brand})
        session["allowed_step"] = 4
        return redirect(url_for("step4"))

    return render_template("step3.html", csrf=csrf, step=3, total=TOTAL_STEPS, progress=progress_pct(3), is_baby_store=session.get("store_type")=="Baby Store")

@app.route("/step4", methods=["GET","POST"])
def step4():
    guard = require_step(4)
    if guard: return guard
    csrf = ensure_csrf_token()

    if request.method == "POST":
        validate_csrf()
        open_feedback = request.form.get("open_feedback","").strip()
        if len(open_feedback) > 500:
            flash("Ý kiến thêm tối đa 500 ký tự.", "error")
            return render_template("step4.html", csrf=csrf, step=4, total=TOTAL_STEPS, progress=progress_pct(4))

        from sqlalchemy.orm import scoped_session
        db = scoped_session(SessionLocal)
        try:
            r = Response(
                name=session.get("name"),
                role=session.get("role"),
                store_type=session.get("store_type"),
                satisfaction=session.get("satisfaction"),
                frequency=session.get("frequency"),
                brand_perception=session.get("brand_perception"),
                primary_diaper_brand=session.get("primary_diaper_brand"),
                open_feedback=open_feedback or None
            )
            db.add(r)
            db.commit()
        finally:
            db.remove()

        session.clear()
        return redirect(url_for("thanks"))

    return render_template("step4.html", csrf=csrf, step=4, total=TOTAL_STEPS, progress=progress_pct(4))

@app.route("/thanks")
def thanks():
    return render_template("thanks.html")

# Admin
def is_admin():
    return session.get("is_admin", False)

@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    csrf = ensure_csrf_token()
    if request.method == "POST":
        validate_csrf()
        u = request.form.get("username","")
        p = request.form.get("password","")
        if u == ADMIN_USER and p == ADMIN_PASS:
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Sai tài khoản hoặc mật khẩu.", "error")
    return render_template("admin_login.html", csrf=csrf)

@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))

@app.route("/admin")
def admin_dashboard():
    if not is_admin():
        return redirect(url_for("admin_login"))

    db = SessionLocal()
    try:
        total = db.query(Response).count()
        sats = [r.satisfaction for r in db.query(Response.satisfaction).all() if r.satisfaction is not None]
        avg_sat = round(sum(sats)/len(sats), 2) if sats else 0
        from collections import Counter
        freq_counts = Counter([r.frequency for r in db.query(Response.frequency).all() if r.frequency])
        brand_counts = Counter([r.brand_perception for r in db.query(Response.brand_perception).all() if r.brand_perception])
        recent = db.query(Response).order_by(Response.id.desc()).limit(10).all()
    finally:
        db.close()

    return render_template("admin_dashboard.html", total=total, avg_sat=avg_sat, freq_counts=freq_counts, brand_counts=brand_counts, recent=recent)

@app.route("/admin/export")
def admin_export():
    if not is_admin():
        return redirect(url_for("admin_login"))

    db = SessionLocal()
    import csv, io
    try:
        rows = db.query(Response).order_by(Response.id.asc()).all()
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["timestamp_iso","name","role","store_type","satisfaction","frequency","brand_perception","primary_diaper_brand","open_feedback"])
        for r in rows:
            w.writerow([r.created_at.isoformat(), r.name, r.role, r.store_type, r.satisfaction, r.frequency, r.brand_perception, r.primary_diaper_brand or "", r.open_feedback or ""])
        out.seek(0)
    finally:
        db.close()

    return send_file(io.BytesIO(out.getvalue().encode("utf-8")), mimetype="text/csv", as_attachment=True, download_name="responses.csv")

if __name__ == "__main__":
    try:
        init_db()
    except OperationalError as e:
        print("DB init failed, check DATABASE_URL:", e)
        raise

    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)
