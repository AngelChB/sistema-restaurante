from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from inventario.models import Ingrediente, MovimientoInventario

from .models import Compra


def recibir_compra(compra_id, usuario):
    with transaction.atomic():
        compra = Compra.objects.select_for_update().get(pk=compra_id)
        if compra.estado != Compra.Estado.BORRADOR:
            raise ValidationError(
                'Solo se puede recibir una compra en borrador.'
            )

        detalles = list(
            compra.detalles.select_related(
                'ingrediente__unidad_medida'
            ).order_by('id')
        )
        if not detalles:
            raise ValidationError('La compra no tiene ingredientes.')

        ingrediente_ids = [detalle.ingrediente_id for detalle in detalles]
        ingredientes = list(
            Ingrediente.objects.filter(
                pk__in=ingrediente_ids
            ).select_for_update().select_related('unidad_medida')
        )
        ingredientes_por_id = {ingrediente.pk: ingrediente for ingrediente in ingredientes}

        ingredientes_inactivos = [
            ingrediente
            for ingrediente in ingredientes
            if not ingrediente.activo
        ]
        if ingredientes_inactivos:
            nombres = ', '.join(
                sorted(i.nombre for i in ingredientes_inactivos)
            )
            raise ValidationError(
                f'Los siguientes ingredientes están inactivos: {nombres}.'
            )

        if MovimientoInventario.objects.filter(compra=compra).exists():
            raise ValidationError(
                'Esta compra ya ha ingresado sus ingredientes al inventario.'
            )

        for detalle in detalles:
            ingrediente = ingredientes_por_id[detalle.ingrediente_id]
            movimiento = MovimientoInventario(
                compra=compra,
                ingrediente=ingrediente,
                tipo=MovimientoInventario.Tipo.ENTRADA,
                cantidad=detalle.cantidad,
                usuario=usuario,
                motivo=f'Ingreso por compra #{compra.id}',
                referencia=f'COMPRA-{compra.id}',
            )
            movimiento.save()
            ingrediente.costo_unitario = detalle.costo_unitario
            ingrediente.save(
                update_fields=['costo_unitario', 'fecha_actualizacion']
            )

        compra.estado = Compra.Estado.RECIBIDA
        compra.fecha_recepcion = timezone.now()
        compra.save(_desde_recepcion=True)

        return compra
