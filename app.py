from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import pandas as pd
import os
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from collections import Counter

app = Flask(__name__)
app.secret_key = "ysfdjhfkvzvFHUILEHAOIUer38t4wat4yt73wy73EESFOEAIEF98eutnrstrsyf8974wyt4w8ynrw78YCNA8O"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['UPLOAD_FOLDER'] = 'uploads'

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))


class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    filename = db.Column(db.String(150))
    date = db.Column(db.String(50))
    score = db.Column(db.Integer)


class DiagnosticRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(50), nullable=False)

    company = db.Column(db.String(150), nullable=False)
    location = db.Column(db.String(250), nullable=False)

    building_type = db.Column(db.String(100))
    size_sqft = db.Column(db.Integer)
    goal = db.Column(db.String(150))
    notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)




@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))




@app.route("/")
def index():
    return render_template("index.html")


@app.route("/book-diagnostic", methods=["POST"])
def book_diagnostic():
    entry = DiagnosticRequest(
        first_name=request.form.get("first_name"),
        last_name=request.form.get("last_name"),
        email=request.form.get("email"),
        phone=request.form.get("phone"),
        company=request.form.get("company"),
        location=request.form.get("location"),
        building_type=request.form.get("building_type"),
        size_sqft=request.form.get("size_sqft") or None,
        goal=request.form.get("goal"),
        notes=request.form.get("notes")
    )

    db.session.add(entry)
    db.session.commit()

    flash("Your diagnostic request has been submitted! Our team will contact you within 1-2 business days.")
    return redirect(url_for("index"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if User.query.filter_by(username=request.form['username']).first():
            flash("Account already exists.", "error")
            return redirect(url_for('register'))

        user = User(
            username=request.form['username'],
            password=generate_password_hash(request.form['password'])
        )
        db.session.add(user)
        db.session.commit()
        flash("Account created successfully.")
        return redirect(url_for('login'))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(username=request.form['username']).first()
        if not user or not check_password_hash(user.password, request.form['password']):
            flash("Invalid credentials.", "error")
            return redirect(url_for('login'))

        login_user(user)
        return redirect(url_for('dashboard'))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


# CSV analyis function
def analyze_csv(file_path):
    df = pd.read_csv(file_path)
    issues = []

    for _, row in df.iterrows():
        if 'temp' in row and 'target_temp' in row:
            delta = abs(row['temp'] - row['target_temp'])
            if delta > 2:
                sev = 'High' if delta > 4 else 'Medium'
                issues.append({
                    'issue': 'Temperature deviation',
                    'time': row.get('time', 'Unknown'),
                    'evidence': f"{row['temp']}°C vs {row['target_temp']}°C",
                    'cost': 60 if sev == 'High' else 40,
                    'severity': sev,
                    'notes': 'Actual temperature deviates from setpoint',
                    'action': 'Schedule technician' if sev == 'High' else 'Check yourself'
                })

        if 'runtime' in row and row['runtime'] > 120:
            issues.append({
                'issue': 'Excessive runtime',
                'time': row.get('time', 'Unknown'),
                'evidence': f"{row['runtime']} min",
                'cost': 60,
                'severity': 'High',
                'notes': 'HVAC ran unusually long',
                'action': 'Schedule technician'
            })

        if 'occupancy' in row and row['occupancy'] == 0 and row.get('runtime', 0) > 0:
            issues.append({
                'issue': 'Unnecessary runtime',
                'time': row.get('time', 'Unknown'),
                'evidence': f"{row['runtime']} min",
                'cost': 20,
                'severity': 'Medium',
                'notes': 'HVAC running while space unoccupied',
                'action': 'Check yourself'
            })

    total_cost = sum(i['cost'] for i in issues)

    max_cost = max((i['cost'] for i in issues), default=60)
    total_possible = len(df) * max_cost
    observed_waste = (total_cost / total_possible) * 100 if total_possible else 0

    benchmark = 30
    efficiency_score = max(0, min(100, int(round(100 - (observed_waste - benchmark)))))

    occupancy_wasted = df[df.get('occupancy', pd.Series()) == 0]['runtime'].sum() if 'runtime' in df else 0

    counts = Counter(i['issue'] for i in issues)
    for i in issues:
        if counts[i['issue']] > 1:
            i['notes'] += " (Repeated issue)"

    issues.sort(key=lambda x: {'High': 0, 'Medium': 1, 'Low': 2}[x['severity']])

    return issues, efficiency_score, total_cost, occupancy_wasted


@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    issues = []
    efficiency_score = None
    total_cost = 0
    occupancy_wasted = 0

    if request.method == "POST":
        file = request.files.get('csv_file')
        if file:
            filename = f"{current_user.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
            path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file.save(path)

            issues, efficiency_score, total_cost, occupancy_wasted = analyze_csv(path)

            db.session.add(Log(
                user_id=current_user.id,
                filename=filename,
                date=datetime.now().strftime('%Y-%m-%d %H:%M'),
                score=efficiency_score
            ))
            db.session.commit()

    logs = Log.query.filter_by(user_id=current_user.id).all()

    return render_template(
        "dashboard.html",
        issues=issues,
        efficiency_score=efficiency_score,
        total_cost=total_cost,
        occupancy_wasted=occupancy_wasted,
        previous_logs=list(reversed(logs))
    )


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)