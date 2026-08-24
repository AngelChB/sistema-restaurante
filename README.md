# Sistema Restaurante

Sistema de gestión integral para restaurantes desarrollado en Django 6.0.8. Permite administrar mesas, pedidos, cocina, caja, inventario, compras, personal, reservas y reportes en una sola plataforma.

## Descripción general

El sistema cubre el flujo completo de operaciones de un restaurante:

- **Gestión de mesas**: Control de estado (libre, ocupada, reservada, fuera de servicio) y capacidad
- **Catálogo**: Categorías y productos con precios y disponibilidad
- **Pedidos**: Registro de pedidos por mesa, detalles con productos, validación de estados y sincronización automática con el estado de la mesa
- **Cocina**: Panel para visualizar y gestionar pedidos en preparación
- **Sala**: Panel para meseros con vista de mesas y pedidos activos
- **Caja**: Registro de pagos (efectivo, tarjeta, Yape, Plin) y cierre de caja diario con arqueo
- **Inventario**: Ingredientes, unidades de medida, recetas por producto, movimientos de stock (entradas, salidas, ajustes) y alertas de stock mínimo
- **Compras**: Proveedores, órdenes de compra (borrador, recibida, cancelada) y recepción que alimenta inventario
- **Personal**: Perfiles de empleado con roles (Administrador, Mesero, Cocina, Cajero) y control de permisos por rol
- **Reservas**: Clientes, reservas con validación de horarios, capacidad de mesa y conflictos
- **Reportes**: Reportes de ventas y análisis

## Tecnologías utilizadas

| Tecnología | Versión | Uso |
|------------|---------|-----|
| Python | 3.12+ | Lenguaje base |
| Django | 6.0.8 | Framework web |
| PostgreSQL | 15+ | Base de datos principal |
| psycopg | 3.3.4 | Driver PostgreSQL |
| python-decouple | 3.8 | Gestión de variables de entorno |

## Requisitos previos

- Python 3.12 o superior
- PostgreSQL 15 o superior
- pip (gestor de paquetes de Python)
- Git (para clonar el repositorio)

## Instalación paso a paso

### 1. Clonar el repositorio

```bash
git clone <URL_DEL_REPOSITORIO>
cd sistema-restaurante
```

### 2. Crear y activar el entorno virtual

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install Django==6.0.8 psycopg-binary==3.3.4 python-decouple==3.8
```

> **Nota**: No existe un archivo `requirements.txt` en el proyecto. Las dependencias se listan arriba según lo instalado en el entorno virtual del proyecto.

### 4. Configurar las variables de entorno

Copie el archivo `.env.example` a `.env` y ajuste los valores:

```bash
cp .env.example .env
```

Edite el archivo `.env` con sus credenciales reales (ver sección **Configuración del archivo .env**).

### 5. Crear la base de datos en PostgreSQL

```sql
CREATE DATABASE restaurante_db;
CREATE USER postgres WITH PASSWORD 'su_password';
GRANT ALL PRIVILEGES ON DATABASE restaurante_db TO postgres;
```

> Ajuste nombre de base de datos, usuario y contraseña según lo que configure en `.env`.

### 6. Ejecutar migraciones

```bash
python manage.py migrate
```

### 7. Crear superusuario (opcional, para acceso al admin de Django)

```bash
python manage.py createsuperuser
```

### 8. Ejecutar el servidor de desarrollo

```bash
python manage.py runserver
```

El sistema estará disponible en `http://127.0.0.1:8000/`

## Configuración del archivo .env

El proyecto utiliza `python-decouple` para leer variables de entorno desde un archivo `.env`. **Nunca suba el archivo `.env` real a control de versiones**.

Cree un archivo `.env` en la raíz del proyecto con las siguientes variables:

```env
# Clave secreta de Django (generar una nueva para producción)
SECRET_KEY=django-insecure-xxxxxxxxxxxxxxxxxxxxxxxx

# Modo debug (True para desarrollo, False para producción)
DEBUG=True

# Base de datos PostgreSQL
DB_NAME=restaurante_db
DB_USER=postgres
DB_PASSWORD=su_password_seguro
DB_HOST=localhost
DB_PORT=5432
```

| Variable | Descripción | Requerida |
|----------|-------------|-----------|
| `SECRET_KEY` | Clave secreta para firmas criptográficas de Django | Sí |
| `DEBUG` | Activa/desactiva modo debug (True/False) | No (default: False) |
| `DB_NAME` | Nombre de la base de datos PostgreSQL | Sí |
| `DB_USER` | Usuario de PostgreSQL | Sí |
| `DB_PASSWORD` | Contraseña del usuario PostgreSQL | Sí |
| `DB_HOST` | Host del servidor PostgreSQL | Sí |
| `DB_PORT` | Puerto de PostgreSQL (default: 5432) | Sí |

## Cómo ejecutar el proyecto

### Desarrollo

```bash
# Activar entorno virtual
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/macOS

# Ejecutar servidor
python manage.py runserver
```

### Producción (resumen)

1. Configure `DEBUG=False` en `.env`
2. Configure `ALLOWED_HOSTS` en `config/settings.py` con su dominio
3. Use un servidor WSGI como Gunicorn: `gunicorn config.wsgi:application`
4. Configure un proxy inverso (Nginx) frente a Gunicorn
5. Sirva archivos estáticos con `python manage.py collectstatic`
6. Use HTTPS en producción

## Módulos / Funcionalidades

### catalogo
- **Categoria**: Clasificación de productos (nombre, descripción, activo)
- **Producto**: Platos/bebidas con categoría, precio, disponibilidad

### mesas
- **Mesa**: Número único, capacidad, estado (Libre/Ocupada/Reservada/Fuera de servicio), ubicación

### pedidos
- **Pedido**: Vinculado a mesa y mesero, estados (Abierto, En preparación, Listo, Entregado, Pagado, Cancelado), observaciones, total calculado automáticamente
- **DetallePedido**: Línea de pedido con producto, cantidad, precio unitario (congelado al momento), observación

### cocina
- Panel para visualizar pedidos en preparación y cambiar estados

### sala
- Panel para meseros con vista de mesas y pedidos activos

### caja
- **Pago**: Registro de pago por pedido (métodos: Efectivo, Tarjeta, Yape, Plin), cálculo de vuelto, validación de monto vs total del pedido
- **CierreCaja**: Arqueo diario con monto inicial, ventas por método de pago, efectivo contado, diferencia, responsable

### inventario
- **UnidadMedida**: Unidades con abreviatura (kg, g, L, ml, und, etc.)
- **Ingrediente**: Stock actual, stock mínimo, costo unitario, alerta de bajo stock
- **RecetaProducto**: Relación producto-ingrediente con cantidad (para descontar stock al vender)
- **MovimientoInventario**: Trazabilidad completa (Entrada, Salida, Ajuste positivo/negativo), vinculado a pedido o compra, stock anterior/resultante, inmutable una vez creado

### compras
- **Proveedor**: Razón social, RUC, contacto, teléfono, email, dirección
- **Compra**: Estado (Borrador, Recibida, Cancelada), número de documento, fecha, observación, total calculado
- **DetalleCompra**: Ingrediente, cantidad, costo unitario

### personal
- **PerfilEmpleado**: Extiende User de Django con rol (Administrador, Mesero, Cocina, Cajero), teléfono
- **Permisos por rol**: Control de acceso a vistas mediante `personal.permisos` y context processor

### reservas
- **Cliente**: Nombres, apellidos, documento único opcional, teléfono, email, observación
- **Reserva**: Cliente, mesa, fecha/hora, cantidad de personas, duración, estado (Pendiente, Confirmada, Atendida, Cancelada, No asistió), validación de capacidad, conflictos de horario y mesa activa

### reportes
- Vistas para reportes de ventas (sin modelos propios, consulta modelos de otros módulos)

### core
- Vista principal/dashboard (sin modelos propios)

## Estructura principal de carpetas

```
sistema-restaurante/
├── config/                 # Configuración central del proyecto Django
│   ├── settings.py         # Configuración principal (BD, apps, middleware, etc.)
│   ├── urls.py             # URLs raíz
│   ├── wsgi.py             # Entrada WSGI
│   └── asgi.py             # Entrada ASGI
├── catalogo/               # Catálogo de productos y categorías
├── mesas/                  # Gestión de mesas
├── pedidos/                # Pedidos y detalles
├── cocina/                 # Panel de cocina
├── sala/                   # Panel de sala/meseros
├── caja/                   # Pagos y cierre de caja
├── inventario/             # Inventario, ingredientes, recetas, movimientos
├── compras/                # Proveedores y compras
├── personal/               # Perfiles de empleado y permisos por rol
├── reservas/               # Clientes y reservas
├── reportes/               # Reportes y análisis
├── core/                   # Vista principal / dashboard
├── templates/              # Plantillas base y por app
│   ├── registration/       # Login, logout (auth)
│   ├── catalogo/
│   ├── mesas/
│   ├── pedidos/
│   ├── cocina/
│   ├── sala/
│   ├── caja/
│   ├── inventario/
│   ├── compras/
│   ├── personal/
│   ├── reservas/
│   └── reportes/
├── static/                 # Archivos estáticos (CSS, JS, imágenes)
├── manage.py               # Script de gestión de Django
├── .env                    # Variables de entorno (NO versionar)
├── .gitignore              # Archivos ignorados por Git
└── venv/                   # Entorno virtual (NO versionar)
```

## Base de datos

- **Motor**: PostgreSQL (configurado en `config/settings.py` con `django.db.backends.postgresql`)
- **Conexión**: Variables de entorno `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
- **Migraciones**: Cada app con modelos tiene su carpeta `migrations/`
- **Zona horaria**: `America/Lima` (configurado en `TIME_ZONE`)
- **Idioma**: Español (`LANGUAGE_CODE = 'es'`)

## Usuarios, roles y permisos

El sistema extiende el usuario de Django (`AbstractUser`) mediante `personal.models.PerfilEmpleado` con 4 roles:

| Rol | Descripción | Acceso típico |
|-----|-------------|---------------|
| **Administrador** | Acceso total al sistema | Admin de Django, todos los módulos, reportes, gestión de usuarios |
| **Mesero** | Atención en sala | Mesas, pedidos, sala, reservas |
| **Cocina** | Preparación de pedidos | Cocina, pedidos (cambio de estado) |
| **Cajero** | Cobro y caja | Caja, pedidos (ver para cobrar), reportes de ventas |

El control de permisos se implementa en `personal/permisos.py` y se inyecta en templates via context processor `personal.context_processors.permisos`.

Autenticación: Usa vistas estándar de Django (`django.contrib.auth.urls`) bajo `/cuentas/`.

## Desarrollo y pruebas

### Ejecutar tests

```bash
# Todos los tests
python manage.py test

# Tests de una app específica
python manage.py test pedidos
python manage.py test personal.tests_permisos
```

Apps con tests:
- `catalogo/tests.py`
- `mesas/tests.py`
- `pedidos/tests.py`
- `cocina/tests.py`
- `sala/tests.py`
- `caja/tests.py`
- `inventario/tests.py`
- `compras/tests.py`
- `personal/tests.py` y `personal/tests_permisos.py`
- `reservas/tests.py`
- `reportes/tests.py`
- `core/tests.py`

### Comandos útiles

```bash
# Crear migraciones tras cambios en modelos
python manage.py makemigrations

# Ver migraciones pendientes
python manage.py showmigrations

# Shell interactivo
python manage.py shell

# Recolectar estáticos (producción)
python manage.py collectstatic
```

## Notas importantes para ejecutar en otra computadora

1. **Base de datos**: Debe tener PostgreSQL instalado y accesible. Cree la base de datos y usuario antes de migrar.
2. **Variables de entorno**: El archivo `.env` **no se versiona**. Cada entorno necesita su propio `.env` con credenciales válidas.
3. **SECRET_KEY**: Genere una nueva clave secreta para producción (`django-insecure-` + string aleatoria).
4. **DEBUG**: En producción **siempre** `DEBUG=False` y configure `ALLOWED_HOSTS` en `config/settings.py`.
5. **Zona horaria**: El proyecto usa `America/Lima`. Ajuste en `settings.py` si está en otra zona.
6. **Archivos estáticos**: En producción ejecute `collectstatic` y configure su servidor web (Nginx/Apache) para servirlos.
7. **Permisos de archivos**: Asegúrese de que el usuario que ejecuta la app tenga permisos de escritura en la carpeta del proyecto (para logs, media si se usa, etc.).
8. **Dependencias**: No hay `requirements.txt`. Instale manualmente: `Django==6.0.8`, `psycopg-binary==3.3.4`, `python-decouple==3.8`.
9. **Puerto por defecto**: `runserver` usa el 8000. Cambie con `python manage.py runserver 0.0.0.0:8000` para acceso en red local.

## Licencia

Uso interno / privado. No se especifica licencia en el proyecto.

---

**Desarrollado con Django 6.0.8** | Sistema de gestión para restaurantes