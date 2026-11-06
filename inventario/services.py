from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from pedidos.models import Pedido

from .models import Ingrediente, MovimientoInventario, RecetaProducto


def iniciar_preparacion_con_descuento(pedido_id, usuario):
    with transaction.atomic():
        pedido = Pedido.objects.select_for_update().get(pk=pedido_id)
        if pedido.estado != Pedido.Estado.ABIERTO:
            raise ValidationError(
                'Solo se puede iniciar la preparación de un pedido abierto.'
            )

        detalles = list(pedido.detalles.select_related('producto').order_by('id'))
        if not detalles:
            raise ValidationError('El pedido no tiene productos.')

        productos_ids = [detalle.producto_id for detalle in detalles]
        recetas = RecetaProducto.objects.filter(
            producto_id__in=productos_ids
        ).select_related('ingrediente', 'producto')
        recetas_por_producto = {}
        for receta in recetas:
            recetas_por_producto.setdefault(receta.producto_id, []).append(receta)

        for detalle in detalles:
            if detalle.producto_id not in recetas_por_producto:
                raise ValidationError(
                    f'El producto "{detalle.producto.nombre}" no tiene una '
                    'receta configurada.'
                )

        cantidades_necesarias = {}
        ingrediente_ids = set()
        for detalle in detalles:
            for receta in recetas_por_producto[detalle.producto_id]:
                cantidad = Decimal(detalle.cantidad) * receta.cantidad
                cantidades_necesarias[receta.ingrediente_id] = (
                    cantidades_necesarias.get(receta.ingrediente_id, Decimal('0'))
                    + cantidad
                )
                ingrediente_ids.add(receta.ingrediente_id)

        ingredientes = list(
            Ingrediente.objects.filter(pk__in=ingrediente_ids)
            .select_for_update()
            .select_related('unidad_medida')
        )

        ingredientes_inactivos = [
            ingrediente for ingrediente in ingredientes if not ingrediente.activo
        ]
        if ingredientes_inactivos:
            nombres = ', '.join(sorted(i.nombre for i in ingredientes_inactivos))
            raise ValidationError(
                f'Los siguientes ingredientes están inactivos: {nombres}.'
            )

        errores_stock = []
        for ingrediente in ingredientes:
            requerida = cantidades_necesarias[ingrediente.pk]
            if ingrediente.stock_actual < requerida:
                errores_stock.append(
                    f'{ingrediente.nombre}: se requieren {requerida} '
                    f'{ingrediente.unidad_medida.abreviatura} y solo hay '
                    f'{ingrediente.stock_actual} '
                    f'{ingrediente.unidad_medida.abreviatura}'
                )
        if errores_stock:
            raise ValidationError(
                'No hay suficiente stock de los siguientes ingredientes: '
                + '; '.join(errores_stock)
            )

        if MovimientoInventario.objects.filter(pedido=pedido).exists():
            raise ValidationError('Este pedido ya ha descontado ingredientes.')

        for ingrediente in ingredientes:
            movimiento = MovimientoInventario(
                pedido=pedido,
                ingrediente=ingrediente,
                tipo=MovimientoInventario.Tipo.SALIDA,
                cantidad=cantidades_necesarias[ingrediente.pk],
                usuario=usuario,
                motivo=f'Consumo por preparación del pedido #{pedido.id}',
                referencia=f'PEDIDO-{pedido.id}',
            )
            movimiento.save()

        pedido.estado = Pedido.Estado.EN_PREPARACION
        pedido.save()

        return pedido
