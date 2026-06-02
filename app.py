"""
MindVault - Personal note-taking & journal app
Flask + SQLAlchemy + SQLite
Run:  pip install -r requirements.txt && python app.py
"""
import os
import uuid
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, jsonify, send_from_directory, abort
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# ---------- Config ----------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
DRAWINGS_DIR = os.path.join(BASE_DIR, "static", "drawings")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(DRAWINGS_DIR, exist_ok=True)

ALLOWED_EXT = {"pdf", "doc", "docx", "ppt", "pptx", "txt", "png", "jpg", "jpeg", "gif", "webp"}
MAX_CONTENT_MB = 25

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("MINDVAULT_SECRET", "change-me-in-prod")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'database.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_MB * 1024 * 1024

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"


# ---------- Models ----------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    journals = db.relationship("Journal", backref="user", cascade="all, delete-orphan", lazy=True)
    drawings = db.relationship("Drawing", backref="user", cascade="all, delete-orphan", lazy=True)
    documents = db.relationship("Document", backref="user", cascade="all, delete-orphan", lazy=True)
    categories = db.relationship("Category", backref="user", cascade="all, delete-orphan", lazy=True)

    def set_password(self, pw): self.password_hash = generate_password_hash(pw)
    def check_password(self, pw): return check_password_hash(self.password_hash, pw)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Journal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, default="Untitled")
    content = db.Column(db.Text, default="")          # HTML from rich editor
    tags = db.Column(db.String(255), default="")
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Drawing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), default="Untitled Sketch")
    filename = db.Column(db.String(255), nullable=False)   # PNG in static/drawings
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class DocumentFolder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("document_folder.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    children = db.relationship(
        "DocumentFolder",
        backref=db.backref("parent", remote_side=[id]),
        cascade="all, delete-orphan",
        single_parent=True,
    )
    documents = db.relationship("Document", backref="folder",
                                cascade="all, delete-orphan", lazy=True)


class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_name = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(20))
    size_bytes = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    folder_id = db.Column(db.Integer, db.ForeignKey("document_folder.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(uid): return User.query.get(int(uid))


# ---------- Helpers ----------
def allowed_file(name):
    return "." in name and name.rsplit(".", 1)[1].lower() in ALLOWED_EXT


# ---------- Auth ----------
@app.route("/")
def root():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not username or not email or len(password) < 6:
            flash("Fill all fields. Password ≥ 6 chars.", "error")
            return redirect(url_for("register"))
        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("Username or email already in use.", "error")
            return redirect(url_for("register"))
        u = User(username=username, email=email)
        u.set_password(password)
        db.session.add(u); db.session.commit()
        login_user(u)
        return redirect(url_for("dashboard"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        ident = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        u = User.query.filter((User.username == ident) | (User.email == ident.lower())).first()
        if u and u.check_password(password):
            login_user(u)
            return redirect(url_for("dashboard"))
        flash("Invalid credentials.", "error")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ---------- Dashboard ----------
@app.route("/dashboard")
@login_required
def dashboard():
    recent_journals = Journal.query.filter_by(user_id=current_user.id)\
        .order_by(Journal.updated_at.desc()).limit(5).all()
    recent_docs = Document.query.filter_by(user_id=current_user.id)\
        .order_by(Document.created_at.desc()).limit(5).all()
    recent_drawings = Drawing.query.filter_by(user_id=current_user.id)\
        .order_by(Drawing.created_at.desc()).limit(4).all()
    stats = {
        "journals": Journal.query.filter_by(user_id=current_user.id).count(),
        "drawings": Drawing.query.filter_by(user_id=current_user.id).count(),
        "documents": Document.query.filter_by(user_id=current_user.id).count(),
    }
    return render_template("dashboard.html", recent_journals=recent_journals,
                           recent_docs=recent_docs, recent_drawings=recent_drawings, stats=stats)


# ---------- Journals ----------
@app.route("/journals")
@login_required
def journals():
    q = request.args.get("q", "").strip()
    query = Journal.query.filter_by(user_id=current_user.id)
    if q:
        like = f"%{q}%"
        query = query.filter((Journal.title.ilike(like)) | (Journal.content.ilike(like)) | (Journal.tags.ilike(like)))
    items = query.order_by(Journal.updated_at.desc()).all()
    cats = Category.query.filter_by(user_id=current_user.id).all()
    return render_template("journals.html", journals=items, categories=cats, q=q)


@app.route("/journal/new")
@login_required
def journal_new():
    j = Journal(user_id=current_user.id, title="Untitled", content="")
    db.session.add(j); db.session.commit()
    return redirect(url_for("journal_edit", jid=j.id))


@app.route("/journal/<int:jid>", methods=["GET"])
@login_required
def journal_edit(jid):
    j = Journal.query.get_or_404(jid)
    if j.user_id != current_user.id: abort(403)
    cats = Category.query.filter_by(user_id=current_user.id).all()
    return render_template("journal_edit.html", j=j, categories=cats)


@app.route("/api/journal/<int:jid>", methods=["POST"])
@login_required
def api_journal_save(jid):
    j = Journal.query.get_or_404(jid)
    if j.user_id != current_user.id: abort(403)
    data = request.get_json(force=True)
    j.title = (data.get("title") or "Untitled").strip()[:200]
    j.content = data.get("content", "")
    j.tags = (data.get("tags") or "")[:255]
    cid = data.get("category_id")
    j.category_id = int(cid) if cid else None
    db.session.commit()
    return jsonify({"ok": True, "updated_at": j.updated_at.strftime("%Y-%m-%d %H:%M")})


@app.route("/journal/<int:jid>/delete", methods=["POST"])
@login_required
def journal_delete(jid):
    j = Journal.query.get_or_404(jid)
    if j.user_id != current_user.id: abort(403)
    db.session.delete(j); db.session.commit()
    return redirect(url_for("journals"))


# ---------- Categories ----------
@app.route("/category/new", methods=["POST"])
@login_required
def category_new():
    name = request.form.get("name", "").strip()
    if name:
        db.session.add(Category(name=name[:80], user_id=current_user.id))
        db.session.commit()
    return redirect(request.referrer or url_for("journals"))


# ---------- Drawings ----------
@app.route("/drawings")
@login_required
def drawings():
    items = Drawing.query.filter_by(user_id=current_user.id).order_by(Drawing.created_at.desc()).all()
    return render_template("drawings.html", drawings=items)


@app.route("/drawing/new")
@login_required
def drawing_new():
    return render_template("drawing_edit.html", drawing=None)


@app.route("/drawing/<int:did>")
@login_required
def drawing_edit(did):
    d = Drawing.query.get_or_404(did)
    if d.user_id != current_user.id: abort(403)
    return render_template("drawing_edit.html", drawing=d)


@app.route("/api/drawing/save", methods=["POST"])
@login_required
def api_drawing_save():
    data = request.get_json(force=True)
    image_b64 = data.get("image", "")
    title = (data.get("title") or "Untitled Sketch")[:200]
    did = data.get("id")
    if not image_b64.startswith("data:image/png;base64,"):
        return jsonify({"ok": False, "error": "invalid image"}), 400
    import base64
    raw = base64.b64decode(image_b64.split(",", 1)[1])
    if did:
        d = Drawing.query.get_or_404(int(did))
        if d.user_id != current_user.id: abort(403)
        d.title = title
        path = os.path.join(DRAWINGS_DIR, d.filename)
    else:
        fn = f"{current_user.id}_{uuid.uuid4().hex}.png"
        d = Drawing(title=title, filename=fn, user_id=current_user.id)
        db.session.add(d)
        path = os.path.join(DRAWINGS_DIR, fn)
    with open(path, "wb") as f: f.write(raw)
    db.session.commit()
    return jsonify({"ok": True, "id": d.id, "filename": d.filename})


@app.route("/drawing/<int:did>/delete", methods=["POST"])
@login_required
def drawing_delete(did):
    d = Drawing.query.get_or_404(did)
    if d.user_id != current_user.id: abort(403)
    try: os.remove(os.path.join(DRAWINGS_DIR, d.filename))
    except OSError: pass
    db.session.delete(d); db.session.commit()
    return redirect(url_for("drawings"))


# ---------- Documents ----------
def _get_folder_or_none(fid):
    """Return user-owned folder or None for root. 404 if not owned."""
    if not fid:
        return None
    folder = DocumentFolder.query.get_or_404(int(fid))
    if folder.user_id != current_user.id:
        abort(403)
    return folder


def _folder_breadcrumbs(folder):
    crumbs = []
    cur = folder
    while cur is not None:
        crumbs.append(cur)
        cur = cur.parent
    return list(reversed(crumbs))


@app.route("/documents")
@login_required
def documents():
    fid = request.args.get("folder", type=int)
    folder = _get_folder_or_none(fid)
    folders = DocumentFolder.query.filter_by(
        user_id=current_user.id, parent_id=(folder.id if folder else None)
    ).order_by(DocumentFolder.name.asc()).all()
    items = Document.query.filter_by(
        user_id=current_user.id, folder_id=(folder.id if folder else None)
    ).order_by(Document.created_at.desc()).all()
    return render_template(
        "documents.html",
        documents=items, folders=folders, current_folder=folder,
        breadcrumbs=_folder_breadcrumbs(folder),
    )


@app.route("/documents/folder/new", methods=["POST"])
@login_required
def documents_folder_new():
    name = request.form.get("name", "").strip()
    parent_id = request.form.get("parent_id", type=int)
    parent = _get_folder_or_none(parent_id)
    if name:
        db.session.add(DocumentFolder(
            name=name[:120], user_id=current_user.id,
            parent_id=(parent.id if parent else None),
        ))
        db.session.commit()
    return redirect(url_for("documents", folder=(parent.id if parent else None)))


@app.route("/documents/folder/<int:folder_id>/delete", methods=["POST"])
@login_required
def documents_folder_delete(folder_id):
    folder = DocumentFolder.query.get_or_404(folder_id)
    if folder.user_id != current_user.id: abort(403)
    parent_id = folder.parent_id
    # remove physical files under this folder & descendants
    def collect_files(f):
        for d in f.documents: yield d
        for c in f.children:
            yield from collect_files(c)
    for d in collect_files(folder):
        try: os.remove(os.path.join(UPLOAD_DIR, d.stored_name))
        except OSError: pass
    db.session.delete(folder); db.session.commit()
    return redirect(url_for("documents", folder=parent_id))


@app.route("/documents/upload", methods=["POST"])
@login_required
def documents_upload():
    fid = request.form.get("folder_id", type=int)
    folder = _get_folder_or_none(fid)
    files = request.files.getlist("files")
    saved = 0
    for f in files:
        if not f or not f.filename: continue
        if not allowed_file(f.filename):
            flash(f"Skipped {f.filename}: type not allowed.", "error"); continue
        safe = secure_filename(f.filename)
        ext = safe.rsplit(".", 1)[1].lower()
        stored = f"{current_user.id}_{uuid.uuid4().hex}.{ext}"
        path = os.path.join(UPLOAD_DIR, stored)
        f.save(path)
        d = Document(original_name=safe, stored_name=stored, file_type=ext,
                     size_bytes=os.path.getsize(path), user_id=current_user.id,
                     folder_id=(folder.id if folder else None))
        db.session.add(d); saved += 1
    db.session.commit()
    if saved: flash(f"Uploaded {saved} file(s).", "success")
    return redirect(url_for("documents", folder=(folder.id if folder else None)))


@app.route("/documents/<int:doc_id>/move", methods=["POST"])
@login_required
def documents_move(doc_id):
    d = Document.query.get_or_404(doc_id)
    if d.user_id != current_user.id: abort(403)
    target = request.form.get("folder_id", type=int)
    folder = _get_folder_or_none(target)
    d.folder_id = folder.id if folder else None
    db.session.commit()
    return redirect(url_for("documents", folder=d.folder_id))


@app.route("/documents/<int:doc_id>/download")
@login_required
def documents_download(doc_id):
    d = Document.query.get_or_404(doc_id)
    if d.user_id != current_user.id: abort(403)
    return send_from_directory(UPLOAD_DIR, d.stored_name,
                               as_attachment=False, download_name=d.original_name)


@app.route("/documents/<int:doc_id>/delete", methods=["POST"])
@login_required
def documents_delete(doc_id):
    d = Document.query.get_or_404(doc_id)
    if d.user_id != current_user.id: abort(403)
    fid = d.folder_id
    try: os.remove(os.path.join(UPLOAD_DIR, d.stored_name))
    except OSError: pass
    db.session.delete(d); db.session.commit()
    return redirect(url_for("documents", folder=fid))



# ---------- Init ----------
with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
