Sistema de reservas para el gimnasio

Proyecto final de Lenguaje de Modelado 2026 2.
Autor Julian Vargas.

Esta aplicacion usa Flask, Python y SQLite.
El sistema permite crear una cuenta, iniciar sesion, consultar clases, reservar cupos y cancelar reservas.

Requisitos

Python 3.10 o una version posterior.
pip.

Instalacion

1. Instale las dependencias.
pip install -r requirements.txt

2. Inicie la aplicacion.
python app.py

3. Abra esta direccion.
http://127.0.0.1:5000

Credenciales de prueba

Administrador.
Correo admin@gimnasio.com
Clave admin123

Los nuevos socios pueden crear una cuenta desde la aplicacion.

Datos

La primera vez se crea el archivo gimnasio.db.
Tambien se crean tres clases de ejemplo.

Despliegue

El proyecto puede publicarse en Railway.
La configuracion esta en render.yaml y Procfile.
