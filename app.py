
import os, secrets, re, csv, io, datetime, json
from collections import Counter

from flask import Flask, render_template, request, redirect, url_for, flash, session, abort, send_file
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, text as sql_text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError

# ---------------------- Config ----------------------
BASE_DIR = os.path.dirname(__file__)
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "changeme")

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set. Provide a Postgres connection string.")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# ---------------------- Dictionaries ----------------------
BRANDS = [
    {"code": 1, "key": "HUG", "label": "Huggies"},
    {"code": 2, "key": "PAM", "label": "Pampers"},
    {"code": 3, "key": "BOB", "label": "Bobby"},
    {"code": 4, "key": "MER", "label": "Merries"},
    {"code": 5, "key": "MOO", "label": "Moony"},
    {"code": 98, "key": "OTHER", "label": "Khác (ghi rõ)"},
    {"code": 99, "key": "NONE", "label": "Không có nhãn hiệu nào"},
]
BRAND_BASE = [b for b in BRANDS if b["code"] not in (98, 99)]

CHANNELS = [
    {"code": 1, "label": "TV/Radio"},
    {"code": 2, "label": "Facebook"},
    {"code": 3, "label": "TikTok"},
    {"code": 4, "label": "POSM tại cửa hàng"},
    {"code": 5, "label": "Nhân viên bán hàng"},
    {"code": 6, "label": "Bạn bè/Word of Mouth"},
    {"code": 98, "label": "Khác (ghi rõ)"},
]

SCALE_TEXT = {1:"Rất kém",2:"Kém",3:"Trung bình",4:"Tốt",5:"Rất tốt"}

# ---------------------- Models ----------------------
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
    extra_json = Column(Text, nullable=True)  # JSON bundle for advanced Qs

def ensure_schema():
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(sql_text("ALTER TABLE responses ADD COLUMN IF NOT EXISTS extra_json TEXT"))

# ---------------------- Helpers ----------------------
STEPS = [1,2,3,4,5,6,7]
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

def is_admin():
    return session.get("is_admin", False)

# ---------------------- Routes ----------------------
@app.route("/")
def home():
    session.clear()
    session.setdefault("allowed_step", 1)
    ensure_csrf_token()
    return redirect(url_for("step1"))

@app.route("/back/<int:from_step>")
def back(from_step):
    prev = max(1, from_step-1)
    session["allowed_step"] = prev
    return redirect(url_for(f"step{prev}"))

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
        if not (2 <= len(name) <= 60) or not re.match(r"^[\w\s\-\.'À-ỹ]+$", name): errors.append("Tên 2–60 ký tự, không chứa ký tự lạ.")
        if role not in {"Owner","Manager","Staff"}: errors.append("Vai trò không hợp lệ.")
        if store_type not in {"Grocery","Pharmacy","Baby Store","Other"}: errors.append("Loại cửa hàng không hợp lệ.")
        if errors:
            for e in errors: flash(e, "error")
            return render_template("step1.html", csrf=csrf, step=1, total=TOTAL_STEPS, progress=progress_pct(1))
        session.update({"name":name,"role":role,"store_type":store_type})
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
            s = int(satisfaction); assert 1 <= s <= 5
        except: errors.append("Mức độ hài lòng phải 1–5.")
        if frequency not in {"Weekly","Monthly","Less often"}: errors.append("Tần suất đặt hàng không hợp lệ.")
        if errors:
            for e in errors: flash(e,"error")
            return render_template("step2.html", csrf=csrf, step=2, total=TOTAL_STEPS, progress=progress_pct(2))
        session.update({"satisfaction":s,"frequency":frequency})
        session["allowed_step"] = 3
        return redirect(url_for("step3"))
    return render_template("step2.html", csrf=csrf, step=2, total=TOTAL_STEPS, progress=progress_pct(2))

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
        if brand_perception not in {"Agree","Neutral","Disagree"}: errors.append("Cảm nhận thương hiệu không hợp lệ.")
        if session.get("store_type") == "Baby Store":
            if not (1 <= len(primary_diaper_brand) <= 40): errors.append("Vui lòng nhập thương hiệu tã chính (≤40 ký tự).")
        if errors:
            for e in errors: flash(e,"error")
            return render_template("step3.html", csrf=csrf, step=3, total=TOTAL_STEPS, progress=progress_pct(3), is_baby_store=session.get("store_type")=="Baby Store")
        session.update({"brand_perception":brand_perception,"primary_diaper_brand":primary_diaper_brand})
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
        session["open_feedback"] = (request.form.get("open_feedback","").strip() or None)
        session["allowed_step"] = 5
        return redirect(url_for("step5"))
    return render_template("step4.html", csrf=csrf, step=4, total=TOTAL_STEPS, progress=progress_pct(4))

# --- Step5: MA Brand (Other + None, None is exclusive) ---
@app.route("/step5", methods=["GET","POST"])
def step5():
    guard = require_step(5)
    if guard: return guard
    csrf = ensure_csrf_token()
    if request.method == "POST":
        validate_csrf()
        selected_codes = request.form.getlist("brands")
        other_text = request.form.get("brand_other_text","").strip()
        try:
            selected_codes = [int(x) for x in selected_codes]
        except: selected_codes = []
        if 99 in selected_codes and len(selected_codes) > 1:
            flash("Chọn 'Không có nhãn hiệu nào' thì không chọn nhãn khác.", "error")
            return render_template("step5.html", csrf=csrf, step=5, total=TOTAL_STEPS, progress=progress_pct(5), brands=BRANDS)
        code_to_label = {b["code"]: b["label"] for b in BRANDS}
        session["brands_selected_codes"] = selected_codes
        session["brands_selected_texts"] = [code_to_label.get(c,str(c)) for c in selected_codes]
        session["brand_other_text"] = other_text if 98 in selected_codes else ""
        session["brand_none"] = 1 if 99 in selected_codes else 0
        session["loop_brand_codes"] = [c for c in selected_codes if c != 99]
        session["loop_idx"] = 0
        session["channels_by_brand"] = {}
        session["allowed_step"] = 6
        return redirect(url_for("step6"))
    return render_template("step5.html", csrf=csrf, step=5, total=TOTAL_STEPS, progress=progress_pct(5), brands=BRANDS)

# --- Step6: Loop channels MA per brand ---
@app.route("/step6", methods=["GET","POST"])
def step6():
    guard = require_step(6)
    if guard: return guard
    csrf = ensure_csrf_token()
    loop_codes = session.get("loop_brand_codes", [])
    idx = session.get("loop_idx", 0)
    if not loop_codes or idx >= len(loop_codes):
        session["allowed_step"] = 7
        return redirect(url_for("step7"))
    current_code = loop_codes[idx]
    brand_label = next((b["label"] for b in BRANDS if b["code"]==current_code), f"Brand {current_code}")
    if request.method == "POST":
        validate_csrf()
        chosen = request.form.getlist("channels")
        other_text = request.form.get("channel_other_text","").strip()
        try:
            chosen = [int(x) for x in chosen]
        except: chosen = []
        mp = session.get("channels_by_brand", {})
        mp[str(current_code)] = {"codes": chosen, "other": (other_text if 98 in chosen else "")}
        session["channels_by_brand"] = mp
        session["loop_idx"] = idx + 1
        if session["loop_idx"] >= len(loop_codes):
            session["allowed_step"] = 7
            return redirect(url_for("step7"))
        return redirect(url_for("step6"))
    return render_template("step6.html", csrf=csrf, step=6, total=TOTAL_STEPS, progress=progress_pct(6), brand_label=brand_label, channels=CHANNELS, idx=idx+1, total=len(loop_codes))

# --- Step7: Grid rating per brand ---
@app.route("/step7", methods=["GET","POST"])
def step7():
    guard = require_step(7)
    if guard: return guard
    csrf = ensure_csrf_token()
    selected_codes = [c for c in session.get("brands_selected_codes", []) if c != 99]
    brands = [b for b in BRANDS if b["code"] in selected_codes]
    if request.method == "POST":
        validate_csrf()
        ratings = {}
        for b in brands:
            key = f"rating_{b['code']}"
            val = request.form.get(key,"").strip()
            try:
                iv = int(val); assert 1 <= iv <= 5
                ratings[str(b["code"])] = iv
            except:
                flash(f"Vui lòng đánh giá 1–5 cho {b['label']}.", "error")
                return render_template("step7.html", csrf=csrf, step=7, total=TOTAL_STEPS, progress=progress_pct(7), brands=brands)
        # Persist
        db = SessionLocal()
        try:
            extras = {
                "brands_selected_codes": session.get("brands_selected_codes", []),
                "brands_selected_texts": session.get("brands_selected_texts", []),
                "brand_other_text": session.get("brand_other_text",""),
                "brand_none": session.get("brand_none",0),
                "channels_by_brand": session.get("channels_by_brand", {}),
                "ratings_by_brand": ratings,
            }
            resp = Response(
                name=session.get("name"),
                role=session.get("role"),
                store_type=session.get("store_type"),
                satisfaction=session.get("satisfaction"),
                frequency=session.get("frequency"),
                brand_perception=session.get("brand_perception"),
                primary_diaper_brand=session.get("primary_diaper_brand"),
                open_feedback=session.get("open_feedback"),
                extra_json=json.dumps(extras, ensure_ascii=False)
            )
            db.add(resp); db.commit()
        finally:
            db.close()
        session.clear()
        return redirect(url_for("thanks"))
    return render_template("step7.html", csrf=csrf, step=7, total=TOTAL_STEPS, progress=progress_pct(7), brands=brands)

@app.route("/thanks")
def thanks(): return render_template("thanks.html")

# --- Admin ---
@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    csrf = ensure_csrf_token()
    if request.method == "POST":
        validate_csrf()
        u = request.form.get("username",""); p = request.form.get("password","")
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
    if not is_admin(): return redirect(url_for("admin_login"))
    db = SessionLocal()
    try:
        total = db.query(Response).count()
        sats = [r.satisfaction for r in db.query(Response.satisfaction).all() if r.satisfaction is not None]
        avg_sat = round(sum(sats)/len(sats), 2) if sats else 0
        freq_counts = Counter([r.frequency for r in db.query(Response.frequency).all() if r.frequency])
        brand_counts = Counter([r.brand_perception for r in db.query(Response.brand_perception).all() if r.brand_perception])
        recent = db.query(Response).order_by(Response.id.desc()).limit(10).all()
    finally:
        db.close()
    return render_template("admin_dashboard.html", total=total, avg_sat=avg_sat, freq_counts=freq_counts, brand_counts=brand_counts, recent=recent)

# --- Export with mode=value|text ---
@app.route("/admin/export")
def admin_export():
    if not is_admin(): return redirect(url_for("admin_login"))
    mode = request.args.get("mode","value").lower().strip()
    code_to_label = {b["code"]: b["label"] for b in BRANDS}
    brand_loop_capacity = len(BRAND_BASE)
    db = SessionLocal(); rows = []
    try:
        rows = db.query(Response).order_by(Response.id.asc()).all()
    finally:
        db.close()

    out = io.StringIO(); w = csv.writer(out)
    # Header
    header = ["timestamp_iso","name","role","store_type","satisfaction","frequency","brand_perception","primary_diaper_brand","open_feedback"]
    options = list(BRANDS)
    for i,_ in enumerate(options, start=1): header.append(f"QBrands_O{i}")
    header.append("QBrands")
    for i in range(1, brand_loop_capacity+1): header.append(f"L{i}_KnownChannels")
    for i in range(1, brand_loop_capacity+1): header.append(f"LBrand{i}_KnownChannels")
    for i in range(1, brand_loop_capacity+1): header.append(f"T{i}_BrandRating")
    for i in range(1, brand_loop_capacity+1): header.append(f"TBrand{i}_BrandRating")
    w.writerow(header)

    for r in rows:
        base = [r.created_at.isoformat(), r.name, r.role, r.store_type, r.satisfaction, r.frequency, r.brand_perception, r.primary_diaper_brand or "", r.open_feedback or ""]
        extras = json.loads(r.extra_json) if r.extra_json else {}
        selected_codes = extras.get("brands_selected_codes", [])
        present = set(selected_codes)
        qbrands_oi = [1 if b["code"] in present else 0 for b in options]
        if mode == "value":
            agg = " ".join(str(c) for c in selected_codes)
        else:
            labels = []
            for c in selected_codes:
                if c == 98:
                    labels.append(extras.get("brand_other_text","").strip() or "Khác")
                else:
                    labels.append(code_to_label.get(c, str(c)))
            agg = " ".join(labels)

        loop_codes = [c for c in selected_codes if c != 99]
        channels_map = extras.get("channels_by_brand", {})
        L_vals, L_brand_vals = [], []
        for i in range(brand_loop_capacity):
            if i < len(loop_codes):
                bc = loop_codes[i]
                item = channels_map.get(str(bc), {"codes": [], "other": ""})
                codes = item.get("codes", [])
                if mode == "value":
                    L_vals.append(" ".join(str(x) for x in codes))
                    L_brand_vals.append(str(bc))
                else:
                    labs = []
                    for x in codes:
                        if x == 98:
                            labs.append(item.get("other","").strip() or "Khác")
                        else:
                            labs.append(next((c["label"] for c in CHANNELS if c["code"]==x), str(x)))
                    L_vals.append(" ".join(labs))
                    L_brand_vals.append(extras.get("brand_other_text","").strip() if bc==98 else code_to_label.get(bc,str(bc)))
            else:
                L_vals.append(""); L_brand_vals.append("")

        ratings_map = extras.get("ratings_by_brand", {})
        T_vals, T_brand_vals = [], []
        for i in range(brand_loop_capacity):
            if i < len(loop_codes):
                bc = loop_codes[i]
                val = ratings_map.get(str(bc))
                if mode == "value":
                    T_vals.append(str(val) if val is not None else "")
                    T_brand_vals.append(str(bc))
                else:
                    T_vals.append(SCALE_TEXT.get(int(val), str(val)) if val is not None else "")
                    T_brand_vals.append(extras.get("brand_other_text","").strip() if bc==98 else code_to_label.get(bc,str(bc)))
            else:
                T_vals.append(""); T_brand_vals.append("")

        row = base + qbrands_oi + [agg] + L_vals + L_brand_vals + T_vals + T_brand_vals
        w.writerow(row)

    out.seek(0)
    return send_file(io.BytesIO(out.getvalue().encode("utf-8")), mimetype="text/csv", as_attachment=True, download_name=f"responses_{mode}.csv")

# ---------------------- Boot ----------------------
if __name__ == "__main__":
    try:
        ensure_schema()
    except OperationalError as e:
        print("DB init failed, check DATABASE_URL:", e); raise
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)
