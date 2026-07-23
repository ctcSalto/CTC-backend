"""
Regresion de seguridad (auditoria M6): el QueryBuilder ya no descarta en silencio
una condicion que no se puede construir. Antes, un campo inexistente hacia que la
condicion desapareciera del WHERE y la consulta devolviera MAS filas de las
pedidas — una fuga en cualquier listado filtrado por permisos o por `published`.
"""
import os
import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing")
os.environ.setdefault("TIME_ZONE", "America/Montevideo")

from database.services.filter.filters import (
    QueryBuilder, Condition, QueryBuilderError,
)
from v2.models.usuario import Usuario


class TestFiltroNoSilencioso:

    def test_campo_valido_construye(self):
        qb = QueryBuilder(Usuario)
        qb.apply_conditions([Condition(attribute="email", operator="eq", value="x@ctcsalto.edu.uy")])
        # No levanta: la condicion se aplico
        assert qb.query is not None

    def test_campo_inexistente_levanta_en_vez_de_descartar(self):
        qb = QueryBuilder(Usuario)
        with pytest.raises(QueryBuilderError):
            qb.apply_conditions([Condition(attribute="campo_que_no_existe", operator="eq", value="x")])

    def test_relacion_inexistente_levanta(self):
        qb = QueryBuilder(Usuario)
        with pytest.raises(QueryBuilderError):
            qb.apply_conditions([Condition(attribute="relacion_fantasma.campo", operator="eq", value="x")])
