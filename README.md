# GastoClaro

Aplicación web para registrar gastos personales con Flask, Python y SQLite.

**Autor:** ITeMH

## Capturas

### 1. Acceso al sistema

El ingreso está protegido con las credenciales definidas para la actividad.

![Pantalla de acceso](capturas/01_LOGUIN.png)

### 2. Panel principal

Muestra el total registrado, los gastos del mes, la cantidad de movimientos y el formulario para registrar nuevos gastos.

![Panel principal de gastos](capturas/02_BACKEND_INICIO.png)

### 3. Reporte de gastos

Permite consultar los movimientos, filtrar por un rango de fechas y revisar el total del periodo.

![Reporte de gastos](capturas/03_BACKEND_REPORTES.png)

### 4. Configuración

Permite personalizar el nombre, los logos y los textos de pie de página del sistema.

![Configuración del sistema](capturas/04_BACKEND_CONFIGURACION.png)

### 5. Exportación a Excel

El reporte puede descargarse como un archivo `.xlsx` compatible con Microsoft Excel.

![Reporte exportado a Excel](capturas/05_BACKEND_EXPORTACION.png)

## Funcionamiento

1. Ingresa con el usuario **admin** y la contraseña **123**.
2. En el panel, registra la **fecha**, **descripción** y **monto** de cada gasto.
3. Consulta el total acumulado, el total del mes y los últimos movimientos.
4. Edita o elimina gastos directamente desde la tabla del panel. La tabla muestra 10 registros por defecto, permite elegir 10, 25, 50 o 100 y cuenta con paginación.
5. Abre **Reporte** para ver todos los gastos, filtrar por fechas y descargar un archivo Excel `.xlsx`.
6. Usa **Salir** para cerrar la sesión.
7. En **Configurar**, cambia el nombre del sitio o reemplaza cualquiera de los dos logos con imágenes PNG, JPG o WebP de hasta 2 MB cada una. Los logos aparecen juntos en el acceso de escritorio; en móvil se ocultan para mantener el formulario compacto.

Los datos se guardan en `gastos.db`, que se crea automáticamente al iniciar la aplicación. El archivo está excluido de Git para no publicar tus gastos.

Los logos iniciales son `rsy.png` y `uprit.png` de la carpeta `static/logo/`. Los cambios hechos en **Configurar** se guardan en SQLite.

## Ejecución local

Necesitas Python 3.10 o superior.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Abre `http://127.0.0.1:5000` en el navegador.

Para un despliegue público, configura `SECRET_KEY` con un valor secreto y cambia `ADMIN_PASSWORD` mediante variables de entorno. Las credenciales predeterminadas son solo para la demostración de la actividad.

## Estructura

- `app.py`: rutas, autenticación, validación y SQLite.
- `templates/`: páginas HTML.
- `static/`: estilos, JavaScript, fuente Inter y logos iniciales.
- `capturas/`: imágenes de la aplicación para este README.
