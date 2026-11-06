# Demostración de cinco minutos

## Preparación

Abre la demo en http://127.0.0.1:8002/ e inicia sesión como `admin_demo` con la clave local `DemoRestaurante123!`. Esta demo usa una base separada y todos sus clientes y operaciones son ficticios.

## Recorrido

1. **Panel y mesas (un minuto).** Explica que el panel reúne ventas, pedidos activos e inventario. Muestra las ocho mesas y la diferencia entre una libre y una ocupada.
2. **Pedido y cocina (un minuto).** Abre el pedido de la mesa 8. Muestra sus productos y total. En Cocina pulsa “Comenzar preparación”. Explica que la operación valida stock y descuenta ingredientes una sola vez. Muestra el movimiento asociado en Inventario.
3. **Entrega (un minuto).** En Cocina marca ese pedido como listo. En Sala márcalo como entregado. Señala que ya aparece pendiente de cobro en Caja.
4. **Cobro (un minuto).** Abre ese pedido desde Caja. Para la carga inicial su total es S/ 52.00: elige efectivo, ingresa S/ 60.00 y muestra el vuelto de S/ 8.00. Comprueba que la mesa queda libre y el reporte incorpora la venta.
5. **Roles y diseño (un minuto).** Muestra las cuentas ficticias de personal y explica que cada rol tiene acceso a módulos concretos. Enseña las capturas de tablet y celular y menciona las pruebas automáticas, incluidas las de concurrencia en PostgreSQL.

## Puntos técnicos para explicar

- Django organiza las funciones en módulos; PostgreSQL conserva los registros relacionados.
- Los precios se copian al detalle del pedido para conservar el histórico.
- La preparación y la recepción de compras se ejecutan como transacciones.
- Los bloqueos evitan dos pedidos activos sobre la misma mesa o un cobro que quede fuera del cierre.
- La interfaz usa plantillas Django y JavaScript para formularios y actualización de paneles.

## Después de mostrarla

La demostración modifica únicamente `restaurante_demo`. Si repites el recorrido con el mismo pedido, ya estará pagado: crea otro pedido sobre una mesa libre. El cargador no reinicia ni borra una demo existente. Evita cerrar la caja hasta terminar de mostrar cobros.

## Texto breve para el portafolio

Sistema web de gestión para restaurantes desarrollado con Python, Django y PostgreSQL. Integra mesas, pedidos, cocina, entrega, caja e inventario, con compras, reservas, permisos por rol y reportes de ventas. Incluye validación de stock, registro de pagos, pruebas automáticas y controles para operaciones simultáneas.
