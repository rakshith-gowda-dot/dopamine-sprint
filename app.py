import os, sqlite3, random
from datetime import date, datetime, timedelta, timezone
from flask import Flask, g, request, session, redirect, jsonify, render_template
from werkzeug.security import generate_password_hash, check_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "sprint.db")
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")
GOALS = {"med": 1, "water": 8, "up": 2, "prob": 1}   # daily targets
MAXV = {"med": 1, "water": 8, "up": 12, "prob": 12}
XP = {"med": 100, "water": 20, "up": 75, "prob": 75}  # xp per unit
TITLES = ["Rookie", "Script Kiddie", "Packet Sniffer", "Exploit Dev", "Zero-Day Hunter", "Root Legend"]

def today():  # IST by default; override with TZ_OFFSET_MIN env var
    return (datetime.now(timezone.utc) + timedelta(minutes=int(os.environ.get("TZ_OFFSET_MIN", 330)))).date()

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB); g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close(_):
    d = g.pop("db", None)
    if d: d.close()

with sqlite3.connect(DB) as c:
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT UNIQUE, pw TEXT, start TEXT);
    CREATE TABLE IF NOT EXISTS logs(uid INTEGER, day TEXT, med INT DEFAULT 0, water INT DEFAULT 0,
      up INT DEFAULT 0, prob INT DEFAULT 0, bonus INT DEFAULT 0, PRIMARY KEY(uid, day));""")

def compute(uid):
    start = date.fromisoformat(db().execute("SELECT start FROM users WHERE id=?", (uid,)).fetchone()["start"])
    t = today(); span = (t - start).days; n = min(span, 59)
    rows = {r["day"]: r for r in db().execute("SELECT * FROM logs WHERE uid=?", (uid,))}
    bank = {"up": 0, "prob": 0}; debts = {"up": [], "prob": []}; D = []
    for i in range(n + 1):   # pass 1: buffer cover, and surplus repaying the oldest missed hours
        d = start + timedelta(i); r = rows.get(d.isoformat())
        v = {k: (r[k] if r else 0) for k in GOALS}
        day = dict(i=i, date=d.isoformat(), v=v, bonus=(r["bonus"] if r else 0), cover={}, paid={}, short={})
        for k in ("up", "prob"):
            h, goal = v[k], GOALS[k]
            use = min(max(0, goal - h), bank[k]); bank[k] -= use
            day["cover"][k] = use; day["paid"][k] = 0
            left = max(0, goal - h) - use
            if left and d < t: debts[k].append([i, left])
            sur = max(0, h - goal)
            for dbt in debts[k]:   # extra hours (even today's) repay oldest debt first
                if not sur: break
                p = min(sur, dbt[1]); dbt[1] -= p; sur -= p; D[dbt[0]]["paid"][k] += p
            if d < t: bank[k] += sur
        D.append(day)
    grid = []; xp = 0; prev = None; m = 1
    for day in D:   # pass 2: final day status after repayments
        v = day["v"]; d = date.fromisoformat(day["date"])
        ok = v["med"] >= 1 and v["water"] >= 8
        for k in ("up", "prob"):
            day["short"][k] = max(0, GOALS[k] - v[k] - day["cover"][k] - day["paid"][k])
            ok = ok and day["short"][k] == 0
        m = 2 if prev is False else 1   # comeback mode: 2x XP after a missed day
        xp += (sum(v[k] * XP[k] for k in v) + day["bonus"] + (300 if ok else 0)) * m
        prev = ok if d < t else None
        day["ok"] = ok if (d < t or ok) else None
        grid.append(day["ok"])
    seq = grid[:]
    if seq and seq[-1] is None: seq.pop()
    s = 0
    while seq and seq[-1]: s += 1; seq.pop()
    v, cover = D[-1]["v"], D[-1]["cover"]
    fr = {"med": min(1, v["med"]), "water": v["water"] / 8,
          "up": min(1, (v["up"] + cover["up"]) / 2), "prob": min(1, v["prob"] + cover["prob"])}
    return dict(day=n + 1, done=span > 59, streak=s, xp=xp, grid=grid + [None] * (60 - len(grid)),
                v=v, cover=cover, bank=bank, debt={k: sum(x[1] for x in debts[k]) for k in debts},
                days=D, fr=fr, mult=m, pct=round(sum(fr.values()) / 4 * 100), cleared=D[-1]["ok"] is True)

def state(uid):
    c = compute(uid); me = db().execute("SELECT name FROM users WHERE id=?", (uid,)).fetchone()
    c.update(name=me["name"], lvl=c["xp"] // 600 + 1, xp_pct=c["xp"] % 600 // 6)
    c["title"] = TITLES[min(c["lvl"] - 1, 5)]
    return c

@app.before_request
def drop_stale_session():  # e.g. after deleting sprint.db, the old cookie points to a missing user
    uid = session.get("uid")
    if uid and not db().execute("SELECT 1 FROM users WHERE id=?", (uid,)).fetchone():
        session.clear()

@app.route("/")
def index():
    return render_template("index.html") if session.get("uid") else redirect("/login")

@app.route("/login", methods=["GET", "POST"])
def login():
    err = None
    if request.method == "POST":
        n, p = request.form["name"].strip().lower(), request.form["pw"]
        u = db().execute("SELECT * FROM users WHERE name=?", (n,)).fetchone()
        if not n or len(p) < 4: err = "Name required, password min 4 chars."
        elif u is None and db().execute("SELECT 1 FROM users").fetchone(): err = "Solo sprint: account already created."
        elif u is None:  # first visit = create your account (only one allowed)
            cur = db().execute("INSERT INTO users(name,pw,start) VALUES(?,?,?)", (n, generate_password_hash(p), today().isoformat()))
            db().commit(); session["uid"] = cur.lastrowid; return redirect("/")
        elif check_password_hash(u["pw"], p): session["uid"] = u["id"]; return redirect("/")
        else: err = "Wrong password."
    return render_template("login.html", err=err)

@app.route("/logout")
def logout():
    session.clear(); return redirect("/login")

@app.get("/api/state")
def api_state():
    return jsonify(state(session["uid"])) if session.get("uid") else (jsonify(error=1), 401)

@app.post("/api/set")
def api_set():
    uid = session.get("uid")
    if not uid: return jsonify(error=1), 401
    j = request.get_json(force=True); k = j.get("habit")
    if k not in GOALS: return jsonify(error=1), 400
    day = today().isoformat(); c = db()
    c.execute("INSERT OR IGNORE INTO logs(uid,day) VALUES(?,?)", (uid, day))
    row = c.execute(f"SELECT {k}, bonus FROM logs WHERE uid=? AND day=?", (uid, day)).fetchone(); cur = row[0]
    new = max(0, min(MAXV[k], cur + int(j.get("delta", 1))))
    crit = random.choice([25, 50, 75, 150]) if new > cur and random.random() < 0.18 and row[1] < 100 else 0  # crits capped per day  # variable reward
    c.execute(f"UPDATE logs SET {k}=?, bonus=bonus+? WHERE uid=? AND day=?", (new, crit, uid, day)); c.commit()
    st = state(uid); st["crit"] = crit
    return jsonify(st)

if __name__ == "__main__":
    app.run(debug=True)