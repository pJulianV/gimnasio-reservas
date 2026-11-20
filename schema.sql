/* Tablas principales del sistema. */
CREATE TABLE IF NOT EXISTS usuario (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre    TEXT NOT NULL,
    correo        TEXT NOT NULL UNIQUE,
    clave         TEXT NOT NULL,
    rol       TEXT NOT NULL DEFAULT 'usuario' CHECK (rol IN ('usuario', 'administrador'))
);

CREATE TABLE IF NOT EXISTS clase (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre        TEXT NOT NULL,
    fecha_hora    TEXT NOT NULL,
    cupo_maximo   INTEGER NOT NULL CHECK (cupo_maximo > 0)
);

CREATE TABLE IF NOT EXISTS reserva (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuario(id),
    clase_id   INTEGER NOT NULL REFERENCES clase(id),
    estado     TEXT NOT NULL DEFAULT 'pendiente'
               CHECK (estado IN ('pendiente', 'confirmada', 'cancelada', 'asistida')),
    UNIQUE (usuario_id, clase_id)
);
