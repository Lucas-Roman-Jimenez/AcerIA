"""Módulo LLM del asistente de inventario (responsable: Nacho).

Uso desde el backend:

    from llm import interpretar, pregunta_tras_busqueda, responder, ErrorLLM
"""
from .aviso import aviso_ia
from .catalogo import Catalogo
from .contrato import Cantidad, Especificacion, ResultadoInterpretacion
from .interprete import CAMPOS_MINIMOS, interpretar, pregunta_tras_busqueda
from .proveedores import ClienteFalso, ErrorLLM, crear_cliente
from .respuesta import responder

__all__ = ["interpretar", "pregunta_tras_busqueda", "responder", "Especificacion", "Cantidad",
           "ResultadoInterpretacion", "Catalogo", "ClienteFalso", "ErrorLLM", "crear_cliente", "CAMPOS_MINIMOS", "aviso_ia"]
