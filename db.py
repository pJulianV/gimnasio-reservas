"""Acceso a datos y reglas de reserva."""
import sqlite3
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

DB_PATH = "gimnasio.db"


class ReglaDeNegocio(Exception):
    """Error que se muestra al usuario."""
    def __init__(self, mensaje, codigo=400):
        super().__init__(mensaje)
        self.mensaje, self.codigo = mensaje, codigo


def conectar():
    con = sqlite3.connect(DB_PATH, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def iniciar_bd():
    con = conectar()
    con.executescript(open("schema.sql", encoding="utf-8").read())
    if con.execute("SELECT COUNT(*) FROM usuario").fetchone()[0] == 0:
        con.execute("INSERT INTO usuario (nombre, correo, clave, rol) VALUES (?,?,?,?)",
                    ("Administrador", "admin@gym.com", generate_password_hash("admin123"), "administrador"))
        base = datetime.now().replace(minute=0, second=0, microsecond=0)
        ejemplos = [("Yoga", 1, 8, 2), ("Spinning", 1, 18, 3), ("Funcional", 2, 7, 20), ("Pilates", 3, 17, 10)]
        for nombre, dias, hora, cupo in ejemplos:
            f = (base + timedelta(days=dias)).replace(hour=hora)
            con.execute("INSERT INTO clase (nombre, fecha_hora, cupo_maximo) VALUES (?,?,?)",
                        (nombre, f.strftime("%Y-%m-%dT%H:%M"), cupo))
    con.close()


# Usuarios
def crear_usuario(nombre, correo, clave_hash):
    con = conectar()
    try:
        con.execute("INSERT INTO usuario (nombre, correo, clave) VALUES (?,?,?)", (nombre, correo, clave_hash))
    except sqlite3.IntegrityError:
        raise ReglaDeNegocio("Ya existe una cuenta con ese correo.", 409)
    finally:
        con.close()


def buscar_usuario(correo):
    con = conectar()
    fila = con.execute("SELECT * FROM usuario WHERE correo = ?", (correo,)).fetchone()
    con.close()
    return fila


# Clases
def cupos_disponibles(con, clase_id):
    """Regla del cupo: cupo maximo menos reservas confirmadas."""
    fila = con.execute(
        "SELECT c.cupo_maximo - COUNT(r.id) AS libres FROM clase c "
        "LEFT JOIN reserva r ON r.clase_id = c.id AND r.estado = 'confirmada' "
        "WHERE c.id = ? GROUP BY c.id", (clase_id,)).fetchone()
    if fila is None:
        raise ReglaDeNegocio("La clase no existe.", 404)
    return fila["libres"]


def hay_cupo(con, clase_id):
    return cupos_disponibles(con, clase_id) > 0


def listar_clases():
    con = conectar()
    filas = con.execute("SELECT * FROM clase ORDER BY fecha_hora").fetchall()
    salida = [dict(f, cupos_disponibles=cupos_disponibles(con, f["id"])) for f in filas]
    con.close()
    return salida


def crear_clase(nombre, fecha_hora, cupo_maximo):
    con = conectar()
    con.execute("INSERT INTO clase (nombre, fecha_hora, cupo_maximo) VALUES (?,?,?)",
                (nombre, fecha_hora, cupo_maximo))
    con.close()


# Reservas
def crear_reserva(usuario_id, clase_id):
    """Secuencia: primero verifica cupo y repeticion, solo despues guarda."""
    con = conectar()
    try:
        con.execute("BEGIN IMMEDIATE")
        if not hay_cupo(con, clase_id):
            raise ReglaDeNegocio("La clase está llena. Elige otra.", 409)
        try:
            cur = con.execute("INSERT INTO reserva (usuario_id, clase_id, estado) VALUES (?,?, 'pendiente')",
                              (usuario_id, clase_id))
        except sqlite3.IntegrityError:
            raise ReglaDeNegocio("Ya tienes una reserva de esta clase.", 409)
        con.execute("UPDATE reserva SET estado = 'confirmada' WHERE id = ?", (cur.lastrowid,))
        con.execute("COMMIT")
        return cur.lastrowid
    except Exception:
        if con.in_transaction:
            con.execute("ROLLBACK")
        raise
    finally:
        con.close()


def _reserva_de(con, reserva_id):
    fila = con.execute(
        "SELECT r.*, c.fecha_hora FROM reserva r JOIN clase c ON c.id = r.clase_id WHERE r.id = ?",
        (reserva_id,)).fetchone()
    if fila is None:
        raise ReglaDeNegocio("La reserva no existe.", 404)
    return fila


def cancelar_reserva(reserva_id, usuario_id):
    """Estados: solo una reserva confirmada se cancela, y solo antes de que empiece la clase."""
    con = conectar()
    try:
        r = _reserva_de(con, reserva_id)
        if r["usuario_id"] != usuario_id:
            raise ReglaDeNegocio("Esa reserva no es tuya.", 403)
        if r["estado"] != "confirmada":
            raise ReglaDeNegocio(f"No se puede cancelar una reserva {r['estado']}.", 409)
        if datetime.fromisoformat(r["fecha_hora"]) <= datetime.now():
            raise ReglaDeNegocio("La clase ya empezó: ya no se puede cancelar.", 409)
        con.execute("UPDATE reserva SET estado = 'cancelada' WHERE id = ?", (reserva_id,))
    finally:
        con.close()


def marcar_asistida(reserva_id):
    con = conectar()
    try:
        r = _reserva_de(con, reserva_id)
        if r["estado"] != "confirmada":
            raise ReglaDeNegocio(f"No se puede marcar asistencia en una reserva {r['estado']}.", 409)
        con.execute("UPDATE reserva SET estado = 'asistida' WHERE id = ?", (reserva_id,))
    finally:
        con.close()


def reservas_de(usuario_id):
    con = conectar()
    filas = con.execute(
        "SELECT r.id, r.estado, c.nombre, c.fecha_hora FROM reserva r JOIN clase c ON c.id = r.clase_id "
        "WHERE r.usuario_id = ? ORDER BY c.fecha_hora", (usuario_id,)).fetchall()
    con.close()
    return [dict(f) for f in filas]


# Reportes
def reporte_ocupacion():
    con = conectar()
    filas = con.execute(
        "SELECT c.id AS clase_id, c.nombre, c.fecha_hora, c.cupo_maximo, "
        "SUM(r.estado = 'confirmada') AS confirmadas, SUM(r.estado = 'asistida') AS asistidas, "
        "SUM(r.estado = 'cancelada') AS canceladas "
        "FROM clase c LEFT JOIN reserva r ON r.clase_id = c.id GROUP BY c.id ORDER BY c.fecha_hora").fetchall()
    con.close()
    salida = []
    for f in filas:
        d = {k: (v or 0) if k in ("confirmadas", "asistidas", "canceladas") else v for k, v in dict(f).items()}
        d["ocupadas"] = d["confirmadas"] + d["asistidas"]
        salida.append(d)
    return salida


def reservas_de_clase(clase_id):
    con = conectar()
    filas = con.execute(
        "SELECT r.id, r.estado, u.nombre FROM reserva r JOIN usuario u ON u.id = r.usuario_id "
        "WHERE r.clase_id = ? ORDER BY u.nombre", (clase_id,)).fetchall()
    con.close()
    return [dict(f) for f in filas]
