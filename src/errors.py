"""Excepciones propias. Separan fallas DETERMINISTAS (datos/contrato: no se reintentan)
de fallas TRANSITORIAS (infraestructura: se reintentan de forma acotada)."""


class DataQualityError(Exception):
    """Una regla CRITICAL falló. Repetir la tarea reproduciría el mismo fallo -> sin retry."""


class IntegrationError(Exception):
    """Invariante de integración violado (p. ej. el join multiplicó filas)."""
