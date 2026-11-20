"""
Sistema de reservas para el gimnasio.
Aplicacion creada con Flask y SQLite.
"""

import sqlite3
import hashlib
import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, g

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "clave-secreta-gimnasio-local")

DATABASE = "gimnasio.db"


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DATABASE)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS socio (
            id_socio      INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre        TEXT    NOT NULL,
            correo        TEXT    NOT NULL UNIQUE,
            telefono      TEXT,
            contrasena_hash TEXT NOT NULL,
            fecha_registro  TEXT
        );

        CREATE TABLE IF NOT EXISTS clase (
            id_clase    INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre      TEXT NOT NULL,
            instructor  TEXT NOT NULL,
            fecha       TEXT NOT NULL,
            hora_inicio TEXT NOT NULL,
            hora_fin    TEXT NOT NULL,
            cupo_maximo INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reserva (
            id_reserva     INTEGER PRIMARY KEY AUTOINCREMENT,
            id_socio       INTEGER NOT NULL REFERENCES socio(id_socio),
            id_clase       INTEGER NOT NULL REFERENCES clase(id_clase),
            estado         TEXT NOT NULL DEFAULT 'CONFIRMADA',
            fecha_creacion TEXT,
            UNIQUE (id_socio, id_clase)
        );

        /* El administrador usa la clave admin123. */
        INSERT OR IGNORE INTO socio (nombre, correo, contrasena_hash, fecha_registro)
        VALUES ('Administrador', 'admin@gimnasio.com',
                '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9',
                '2026-01-01');

        /* Clases de ejemplo. */
        INSERT OR IGNORE INTO clase (id_clase, nombre, instructor, fecha, hora_inicio, hora_fin, cupo_maximo)
        VALUES
            (1, 'Yoga', 'Maria Lopez', date('now', '+1 day'), '08:00', '09:00', 10),
            (2, 'Spinning', 'Carlos Ruiz', date('now', '+1 day'), '10:00', '11:00', 8),
            (3, 'Zumba', 'Ana Torres', date('now', '+2 days'), '17:00', '18:00', 15);
    """)
    db.commit()
    db.close()


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


@app.route("/")
def index():
    if "socio_id" not in session:
        return redirect(url_for("login"))
    return redirect(url_for("clases"))


@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        nombre   = request.form["nombre"].strip()
        correo   = request.form["correo"].strip().lower()
        telefono = request.form["telefono"].strip()
        password = request.form["password"]

        if not nombre or not correo or not password:
            flash("Nombre, correo y contraseña son obligatorios.", "error")
            return render_template("registro.html")

        db = get_db()
        try:
            db.execute(
                "INSERT INTO socio (nombre, correo, telefono, contrasena_hash, fecha_registro) VALUES (?, ?, ?, ?, date('now'))",
                (nombre, correo, telefono, hash_password(password))
            )
            db.commit()
            flash("Cuenta creada. Inicia sesión.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Ese correo ya está registrado.", "error")
    return render_template("registro.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        correo   = request.form["correo"].strip().lower()
        password = request.form["password"]
        db = get_db()
        socio = db.execute(
            "SELECT * FROM socio WHERE correo = ? AND contrasena_hash = ?",
            (correo, hash_password(password))
        ).fetchone()
        if socio:
            session["socio_id"]     = socio["id_socio"]
            session["socio_nombre"] = socio["nombre"]
            session["es_admin"]     = (correo == "admin@gimnasio.com")
            return redirect(url_for("clases"))
        flash("Correo o contraseña incorrectos.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/clases")
def clases():
    if "socio_id" not in session:
        return redirect(url_for("login"))
    db = get_db()
    clases_rows = db.execute("""
        SELECT c.*,
               c.cupo_maximo - COUNT(r.id_reserva) AS cupos_disponibles,
               EXISTS(
                   SELECT 1 FROM reserva r2
                   WHERE r2.id_clase = c.id_clase
                     AND r2.id_socio = ?
                     AND r2.estado   = 'CONFIRMADA'
               ) AS ya_reservo
        FROM clase c
        LEFT JOIN reserva r ON r.id_clase = c.id_clase AND r.estado = 'CONFIRMADA'
        WHERE c.fecha >= date('now')
        GROUP BY c.id_clase
        ORDER BY c.fecha, c.hora_inicio
    """, (session["socio_id"],)).fetchall()
    return render_template("clases.html", clases=clases_rows)


@app.route("/reservar/<int:id_clase>", methods=["POST"])
def reservar(id_clase):
    if "socio_id" not in session:
        return redirect(url_for("login"))
    db = get_db()

    # Comprobar cupos.
    clase = db.execute("""
        SELECT c.*, c.cupo_maximo - COUNT(r.id_reserva) AS cupos_disponibles
        FROM clase c
        LEFT JOIN reserva r ON r.id_clase = c.id_clase AND r.estado = 'CONFIRMADA'
        WHERE c.id_clase = ?
        GROUP BY c.id_clase
    """, (id_clase,)).fetchone()

    if not clase:
        flash("Clase no encontrada.", "error")
        return redirect(url_for("clases"))

    if clase["cupos_disponibles"] <= 0:
        flash(f"La clase '{clase['nombre']}' está llena.", "error")
        return redirect(url_for("clases"))

    try:
        db.execute(
            "INSERT INTO reserva (id_socio, id_clase, estado, fecha_creacion) VALUES (?, ?, 'CONFIRMADA', datetime('now'))",
            (session["socio_id"], id_clase)
        )
        db.commit()
        flash(f"Reserva confirmada para '{clase['nombre']}'.", "success")
    except sqlite3.IntegrityError:
        flash(f"Ya tienes una reserva en '{clase['nombre']}'.", "error")

    return redirect(url_for("clases"))


@app.route("/mis-reservas")
def mis_reservas():
    if "socio_id" not in session:
        return redirect(url_for("login"))
    db = get_db()
    reservas = db.execute("""
        SELECT r.id_reserva, r.estado, r.fecha_creacion,
               c.nombre AS clase_nombre, c.instructor,
               c.fecha, c.hora_inicio, c.hora_fin
        FROM reserva r
        JOIN clase c ON c.id_clase = r.id_clase
        WHERE r.id_socio = ?
        ORDER BY c.fecha DESC
    """, (session["socio_id"],)).fetchall()
    return render_template("mis_reservas.html", reservas=reservas)


@app.route("/cancelar/<int:id_reserva>", methods=["POST"])
def cancelar(id_reserva):
    if "socio_id" not in session:
        return redirect(url_for("login"))
    db = get_db()
    reserva = db.execute(
        "SELECT * FROM reserva WHERE id_reserva = ? AND id_socio = ?",
        (id_reserva, session["socio_id"])
    ).fetchone()
    if not reserva:
        flash("Reserva no encontrada.", "error")
        return redirect(url_for("mis_reservas"))
    db.execute(
        "UPDATE reserva SET estado = 'CANCELADA' WHERE id_reserva = ?",
        (id_reserva,)
    )
    db.commit()
    flash("Reserva cancelada.", "success")
    return redirect(url_for("mis_reservas"))


@app.route("/admin/crear-clase", methods=["GET", "POST"])
def crear_clase():
    if not session.get("es_admin"):
        return redirect(url_for("clases"))
    if request.method == "POST":
        db = get_db()
        db.execute(
            "INSERT INTO clase (nombre, instructor, fecha, hora_inicio, hora_fin, cupo_maximo) VALUES (?,?,?,?,?,?)",
            (
                request.form["nombre"].strip(),
                request.form["instructor"].strip(),
                request.form["fecha"],
                request.form["hora_inicio"],
                request.form["hora_fin"],
                int(request.form["cupo_maximo"]),
            )
        )
        db.commit()
        flash("Clase creada.", "success")
        return redirect(url_for("clases"))
    return render_template("crear_clase.html")


@app.route("/admin/reportes")
def reportes():
    if not session.get("es_admin"):
        return redirect(url_for("clases"))
    db = get_db()
    reporte = db.execute("""
        SELECT c.nombre, c.instructor, c.fecha, c.hora_inicio,
               c.cupo_maximo,
               COUNT(CASE WHEN r.estado = 'CONFIRMADA' THEN 1 END) AS confirmadas,
               COUNT(CASE WHEN r.estado = 'ASISTIDA'   THEN 1 END) AS asistidas,
               COUNT(CASE WHEN r.estado = 'CANCELADA'  THEN 1 END) AS canceladas
        FROM clase c
        LEFT JOIN reserva r ON r.id_clase = c.id_clase
        GROUP BY c.id_clase
        ORDER BY confirmadas DESC
    """).fetchall()
    return render_template("reportes.html", reporte=reporte)


init_db()

init_db()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
    )
