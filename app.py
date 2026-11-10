import io
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from functools import wraps
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from PIL import Image, UnidentifiedImageError

from flask import Flask, Response, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("DATABASE_PATH", BASE_DIR / "gastos.db"))

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "clave-local-cambiar-en-produccion")
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
app.config["MAX_CONTENT_LENGTH"] = 3 * 1024 * 1024
ADMIN_PASSWORD_HASH = generate_password_hash(os.environ.get("ADMIN_PASSWORD", "123"))


@contextmanager
def db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db() as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS gastos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            descripcion TEXT NOT NULL,
            monto_centavos INTEGER NOT NULL CHECK (monto_centavos > 0),
            creado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        connection.execute("""CREATE TABLE IF NOT EXISTS configuracion (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            nombre TEXT NOT NULL,
            logo BLOB,
            logo_mime TEXT,
            logo_version INTEGER NOT NULL DEFAULT 0
        )""")
        columnas = {fila["name"] for fila in connection.execute("PRAGMA table_info(configuracion)")}
        if "logo_secundario" not in columnas:
            connection.execute("ALTER TABLE configuracion ADD COLUMN logo_secundario BLOB")
            connection.execute("ALTER TABLE configuracion ADD COLUMN logo_secundario_mime TEXT")
            connection.execute("ALTER TABLE configuracion ADD COLUMN logo_secundario_version INTEGER NOT NULL DEFAULT 0")
        if "pie_panel" not in columnas:
            connection.execute("ALTER TABLE configuracion ADD COLUMN pie_panel TEXT NOT NULL DEFAULT 'Derechos reservados ITeMH © Universidad Privada de Trujillo'")
            connection.execute("ALTER TABLE configuracion ADD COLUMN pie_login TEXT NOT NULL DEFAULT 'Derechos reservados ITeMH © 2026'")
            connection.execute("ALTER TABLE configuracion ADD COLUMN marca_login TEXT NOT NULL DEFAULT 'UPRIT'")
        connection.execute("INSERT OR IGNORE INTO configuracion (id, nombre) VALUES (1, 'GastoClaro')")


def configuracion_actual():
    with db() as connection:
        return connection.execute("""SELECT nombre, logo_version, logo IS NOT NULL AS tiene_logo,
            logo_secundario_version, logo_secundario IS NOT NULL AS tiene_logo_secundario,
            pie_panel, pie_login, marca_login
            FROM configuracion WHERE id = 1""").fetchone()


@app.context_processor
def branding():
    config = configuracion_actual()
    return {"nombre_sitio": config["nombre"],
            "pie_panel": config["pie_panel"],
            "pie_login": config["pie_login"],
            "marca_login": config["marca_login"],
            "logo_url": url_for("logo_actual", tipo="principal", v=config["logo_version"]) if config["tiene_logo"] else url_for("static", filename="logo/rsy.png"),
            "logo_secundario_url": url_for("logo_actual", tipo="secundario", v=config["logo_secundario_version"]) if config["tiene_logo_secundario"] else url_for("static", filename="logo/uprit.png")}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("usuario"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.template_filter("dinero")
def dinero(centavos):
    return f"S/ {centavos / 100:,.2f}"


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("usuario"):
        return redirect(url_for("inicio"))
    if request.method == "POST":
        if request.form.get("usuario", "").strip() == "admin" and check_password_hash(ADMIN_PASSWORD_HASH, request.form.get("clave", "")):
            session.clear()
            session["usuario"] = "admin"
            return redirect(url_for("inicio"))
        flash("Usuario o contraseña incorrectos.", "error")
    return render_template("login.html")


@app.post("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.get("/logo")
def logo_actual():
    tipo = request.args.get("tipo", "principal")
    if tipo not in {"principal", "secundario"}:
        return "Tipo de logo no válido", 404
    campo = "logo" if tipo == "principal" else "logo_secundario"
    mime = "logo_mime" if tipo == "principal" else "logo_secundario_mime"
    with db() as connection:
        config = connection.execute(f"SELECT {campo}, {mime} FROM configuracion WHERE id = 1").fetchone()
    if not config[campo]:
        return redirect(url_for("static", filename="logo/rsy.png" if tipo == "principal" else "logo/uprit.png"))
    return Response(config[campo], mimetype=config[mime], headers={"Cache-Control": "no-store"})


def validar_logo(archivo):
    if not archivo or not archivo.filename:
        return None
    datos = archivo.read(2 * 1024 * 1024 + 1)
    if len(datos) > 2 * 1024 * 1024:
        raise ValueError("Cada logo debe pesar menos de 2 MB.")
    try:
        imagen = Image.open(io.BytesIO(datos))
        if imagen.format not in {"PNG", "JPEG", "WEBP"} or imagen.width > 4000 or imagen.height > 4000:
            raise ValueError
        imagen.verify()
        mime = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}[imagen.format]
        return datos, mime
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValueError("Sube imágenes PNG, JPG o WebP válidas.") from None


@app.route("/configurar", methods=["GET", "POST"])
@login_required
def configurar():
    if request.method == "POST":
        token = session.get("csrf_config")
        if not token or not secrets.compare_digest(token, request.form.get("csrf_token", "")):
            flash("La sesión del formulario expiró. Intenta otra vez.", "error")
            return redirect(url_for("configurar"))
        nombre = request.form.get("nombre", "").strip()
        pie_panel = request.form.get("pie_panel", "").strip()
        pie_login = request.form.get("pie_login", "").strip()
        marca_login = request.form.get("marca_login", "").strip()
        if not 2 <= len(nombre) <= 40:
            flash("El nombre debe tener entre 2 y 40 caracteres.", "error")
            return redirect(url_for("configurar"))
        if not 5 <= len(pie_panel) <= 160 or not 5 <= len(pie_login) <= 120 or not 2 <= len(marca_login) <= 40:
            flash("Revisa los textos del pie de página.", "error")
            return redirect(url_for("configurar"))
        try:
            principal = validar_logo(request.files.get("logo"))
            secundario = validar_logo(request.files.get("logo_secundario"))
        except ValueError as error:
            flash(str(error), "error")
            return redirect(url_for("configurar"))
        with db() as connection:
            connection.execute("""UPDATE configuracion
                SET nombre = ?, pie_panel = ?, pie_login = ?, marca_login = ? WHERE id = 1""",
                (nombre, pie_panel, pie_login, marca_login))
            if request.form.get("quitar_logo") == "1":
                connection.execute("UPDATE configuracion SET logo = NULL, logo_mime = NULL, logo_version = logo_version + 1 WHERE id = 1")
            elif principal is not None:
                connection.execute("UPDATE configuracion SET logo = ?, logo_mime = ?, logo_version = logo_version + 1 WHERE id = 1", principal)
            if request.form.get("quitar_logo_secundario") == "1":
                connection.execute("UPDATE configuracion SET logo_secundario = NULL, logo_secundario_mime = NULL, logo_secundario_version = logo_secundario_version + 1 WHERE id = 1")
            elif secundario is not None:
                connection.execute("UPDATE configuracion SET logo_secundario = ?, logo_secundario_mime = ?, logo_secundario_version = logo_secundario_version + 1 WHERE id = 1", secundario)
        flash("Configuración guardada.", "success")
        return redirect(url_for("configurar"))
    session["csrf_config"] = secrets.token_urlsafe(32)
    return render_template("configurar.html", csrf_token=session["csrf_config"], config=configuracion_actual())


@app.route("/")
@login_required
def inicio():
    try:
        por_pagina = int(request.args.get("por_pagina", 10))
        pagina = max(1, int(request.args.get("pagina", 1)))
    except (TypeError, ValueError):
        por_pagina, pagina = 10, 1
    if por_pagina not in {10, 25, 50, 100}:
        por_pagina = 10
    with db() as connection:
        total_registros = connection.execute("SELECT COUNT(*) FROM gastos").fetchone()[0]
        total_paginas = max(1, (total_registros + por_pagina - 1) // por_pagina)
        pagina = min(pagina, total_paginas)
        gastos = connection.execute("SELECT * FROM gastos ORDER BY fecha DESC, id DESC LIMIT ? OFFSET ?",
                                    (por_pagina, (pagina - 1) * por_pagina)).fetchall()
        total = connection.execute("SELECT COALESCE(SUM(monto_centavos), 0) FROM gastos").fetchone()[0]
        mes = date.today().strftime("%Y-%m")
        total_mes = connection.execute("SELECT COALESCE(SUM(monto_centavos), 0) FROM gastos WHERE substr(fecha, 1, 7) = ?", (mes,)).fetchone()[0]
    if "csrf_gastos" not in session:
        session["csrf_gastos"] = secrets.token_urlsafe(32)
    inicio_registro = (pagina - 1) * por_pagina + 1 if total_registros else 0
    fin_registro = min(pagina * por_pagina, total_registros)
    return render_template("index.html", gastos=gastos, total=total, total_mes=total_mes,
                           hoy=date.today().isoformat(), pagina=pagina, por_pagina=por_pagina,
                           total_paginas=total_paginas, total_registros=total_registros,
                           inicio_registro=inicio_registro, fin_registro=fin_registro,
                           paginas_visibles=range(max(1, pagina - 2), min(total_paginas, pagina + 2) + 1),
                           csrf_gastos=session["csrf_gastos"])


def validar_csrf_gastos():
    token = session.get("csrf_gastos")
    return bool(token and secrets.compare_digest(token, request.form.get("csrf_token", "")))


def leer_gasto_formulario():
    fecha = request.form.get("fecha", "").strip()
    descripcion = request.form.get("descripcion", "").strip()
    monto = request.form.get("monto", "").strip()
    datetime.strptime(fecha, "%Y-%m-%d")
    if len(fecha) != 10:
        raise ValueError
    valor = Decimal(monto)
    if not valor.is_finite() or valor <= 0 or valor.as_tuple().exponent < -2:
        raise ValueError
    centavos = int(valor * 100)
    if centavos > 99999999999 or not 1 <= len(descripcion) <= 200:
        raise ValueError
    return fecha, descripcion, centavos


@app.post("/gastos")
@login_required
def crear_gasto():
    if not validar_csrf_gastos():
        flash("La sesión del formulario expiró. Intenta otra vez.", "error")
        return redirect(url_for("inicio"))
    try:
        fecha, descripcion, centavos = leer_gasto_formulario()
    except (ValueError, InvalidOperation):
        flash("Revisa la fecha, la descripción y el monto positivo (máximo 2 decimales).", "error")
        return redirect(url_for("inicio"))
    with db() as connection:
        connection.execute("INSERT INTO gastos (fecha, descripcion, monto_centavos) VALUES (?, ?, ?)", (fecha, descripcion, centavos))
    flash("Gasto registrado correctamente.", "success")
    return redirect(url_for("inicio"))


@app.route("/gastos/<int:gasto_id>/editar", methods=["GET", "POST"])
@login_required
def editar_gasto(gasto_id):
    with db() as connection:
        gasto = connection.execute("SELECT * FROM gastos WHERE id = ?", (gasto_id,)).fetchone()
    if gasto is None:
        flash("El gasto solicitado no existe.", "error")
        return redirect(url_for("inicio"))
    if request.method == "POST":
        if not validar_csrf_gastos():
            flash("La sesión del formulario expiró. Intenta otra vez.", "error")
            return redirect(url_for("inicio"))
        try:
            fecha, descripcion, centavos = leer_gasto_formulario()
        except (ValueError, InvalidOperation):
            flash("Revisa la fecha, la descripción y el monto positivo (máximo 2 decimales).", "error")
            return redirect(url_for("editar_gasto", gasto_id=gasto_id))
        with db() as connection:
            connection.execute("UPDATE gastos SET fecha = ?, descripcion = ?, monto_centavos = ? WHERE id = ?",
                               (fecha, descripcion, centavos, gasto_id))
        flash("Gasto actualizado correctamente.", "success")
        return redirect(url_for("inicio", pagina=request.form.get("pagina", 1),
                                por_pagina=request.form.get("por_pagina", 10)))
    if "csrf_gastos" not in session:
        session["csrf_gastos"] = secrets.token_urlsafe(32)
    return render_template("editar_gasto.html", gasto=gasto, csrf_gastos=session["csrf_gastos"],
                           pagina=request.args.get("pagina", 1), por_pagina=request.args.get("por_pagina", 10))


@app.post("/gastos/<int:gasto_id>/eliminar")
@login_required
def eliminar_gasto(gasto_id):
    if not validar_csrf_gastos():
        flash("La sesión del formulario expiró. Intenta otra vez.", "error")
        return redirect(url_for("inicio"))
    with db() as connection:
        eliminado = connection.execute("DELETE FROM gastos WHERE id = ?", (gasto_id,)).rowcount
    flash("Gasto eliminado correctamente." if eliminado else "El gasto ya no existe.",
          "success" if eliminado else "error")
    return redirect(url_for("inicio", pagina=request.form.get("pagina", 1),
                            por_pagina=request.form.get("por_pagina", 10)))


def datos_reporte():
    desde = request.args.get("desde", "").strip()
    hasta = request.args.get("hasta", "").strip()
    for value in (desde, hasta):
        if value:
            datetime.strptime(value, "%Y-%m-%d")
    if desde and hasta and desde > hasta:
        raise ValueError
    condiciones, parametros = [], []
    if desde:
        condiciones.append("fecha >= ?")
        parametros.append(desde)
    if hasta:
        condiciones.append("fecha <= ?")
        parametros.append(hasta)
    where = " WHERE " + " AND ".join(condiciones) if condiciones else ""
    with db() as connection:
        gastos = connection.execute("SELECT * FROM gastos" + where + " ORDER BY fecha DESC, id DESC", parametros).fetchall()
    return gastos, desde, hasta


@app.get("/reporte")
@login_required
def reporte():
    try:
        todos_los_gastos, desde, hasta = datos_reporte()
    except ValueError:
        flash("El rango de fechas no es válido.", "error")
        return redirect(url_for("reporte"))
    try:
        por_pagina = int(request.args.get("por_pagina", 10))
        pagina = max(1, int(request.args.get("pagina", 1)))
    except (TypeError, ValueError):
        por_pagina, pagina = 10, 1
    if por_pagina not in {10, 25, 50, 100}:
        por_pagina = 10
    total_registros = len(todos_los_gastos)
    total_paginas = max(1, (total_registros + por_pagina - 1) // por_pagina)
    pagina = min(pagina, total_paginas)
    inicio = (pagina - 1) * por_pagina
    gastos = todos_los_gastos[inicio:inicio + por_pagina]
    inicio_registro = inicio + 1 if total_registros else 0
    fin_registro = min(inicio + por_pagina, total_registros)
    return render_template("reporte.html", gastos=gastos, desde=desde, hasta=hasta,
                           total=sum(g["monto_centavos"] for g in todos_los_gastos),
                           total_registros=total_registros, pagina=pagina, por_pagina=por_pagina,
                           total_paginas=total_paginas, inicio_registro=inicio_registro,
                           fin_registro=fin_registro,
                           paginas_visibles=range(max(1, pagina - 2), min(total_paginas, pagina + 2) + 1))


@app.get("/reporte/excel")
@login_required
def exportar_excel():
    try:
        gastos, _, _ = datos_reporte()
    except ValueError:
        flash("El rango de fechas no es válido.", "error")
        return redirect(url_for("reporte"))
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Gastos"
    hoja.append(["Fecha", "Descripción", "Monto (S/)"])

    relleno_encabezado = PatternFill("solid", fgColor="BA012A")
    for celda in hoja[1]:
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = relleno_encabezado
        celda.alignment = Alignment(horizontal="center", vertical="center")

    for gasto in gastos:
        fecha_excel = datetime.strptime(gasto["fecha"], "%Y-%m-%d").date()
        hoja.append([fecha_excel, gasto["descripcion"], gasto["monto_centavos"] / 100])

    for celda in hoja["A"][1:]:
        celda.number_format = "dd/mm/yyyy"
    for celda in hoja["C"][1:]:
        celda.number_format = '"S/" #,##0.00'

    hoja.column_dimensions["A"].width = 15
    hoja.column_dimensions["B"].width = 42
    hoja.column_dimensions["C"].width = 16
    hoja.auto_filter.ref = f"A1:C{max(1, hoja.max_row)}"
    hoja.freeze_panes = "A2"

    buffer = io.BytesIO()
    libro.save(buffer)
    buffer.seek(0)
    return Response(buffer.getvalue(),
                    mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": "attachment; filename=reporte_gastos.xlsx"})


init_db()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
