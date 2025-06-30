from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from database.database import get_engine

def get_database_schema(engine, include_indexes=True, include_constraints=True, include_views=False):
    """
    Obtiene un esquema completo de la base de datos incluyendo tablas, columnas,
    claves primarias, claves foráneas, índices, restricciones y opcionalmente vistas.
    
    Args:
        engine: Motor de SQLAlchemy
        include_indexes: Si incluir información de índices
        include_constraints: Si incluir restricciones (checks, unique, etc.)
        include_views: Si incluir vistas en el esquema
    
    Returns:
        str: Esquema formateado de la base de datos
    """
    try:
        inspector = inspect(engine)
        schema = "=== DATABASE SCHEMA ===\n\n"
        
        # Obtener información de tablas
        table_names = inspector.get_table_names()
        schema += f"Total tables: {len(table_names)}\n\n"
        
        for table_name in table_names:
            schema += f"TABLE: {table_name}\n"
            schema += "=" * (len(table_name) + 7) + "\n"
            
            # Información de columnas
            columns = inspector.get_columns(table_name)
            schema += "Columns:\n"
            for column in columns:
                col_info = _format_column_info(column)
                schema += f"  - {col_info}\n"
            
            # Claves primarias
            pk_constraint = inspector.get_pk_constraint(table_name)
            if pk_constraint and pk_constraint['constrained_columns']:
                pk_cols = ', '.join(pk_constraint['constrained_columns'])
                schema += f"\nPrimary Key: {pk_cols}\n"
            
            # Claves foráneas
            foreign_keys = inspector.get_foreign_keys(table_name)
            if foreign_keys:
                schema += "\nForeign Keys:\n"
                for fk in foreign_keys:
                    local_cols = ', '.join(fk['constrained_columns'])
                    ref_table = fk['referred_table']
                    ref_cols = ', '.join(fk['referred_columns'])
                    fk_name = fk.get('name', 'unnamed')
                    schema += f"  - {local_cols} -> {ref_table}.{ref_cols} (constraint: {fk_name})\n"
            
            # Índices
            if include_indexes:
                indexes = inspector.get_indexes(table_name)
                if indexes:
                    schema += "\nIndexes:\n"
                    for idx in indexes:
                        idx_name = idx['name']
                        idx_cols = ', '.join(idx['column_names'])
                        unique_str = " (UNIQUE)" if idx.get('unique', False) else ""
                        schema += f"  - {idx_name}: {idx_cols}{unique_str}\n"
            
            # Restricciones adicionales
            if include_constraints:
                # Restricciones UNIQUE
                unique_constraints = inspector.get_unique_constraints(table_name)
                if unique_constraints:
                    schema += "\nUnique Constraints:\n"
                    for uc in unique_constraints:
                        uc_name = uc.get('name', 'unnamed')
                        uc_cols = ', '.join(uc['column_names'])
                        schema += f"  - {uc_name}: {uc_cols}\n"
                
                # Restricciones CHECK (si están disponibles)
                try:
                    check_constraints = inspector.get_check_constraints(table_name)
                    if check_constraints:
                        schema += "\nCheck Constraints:\n"
                        for cc in check_constraints:
                            cc_name = cc.get('name', 'unnamed')
                            cc_sql = cc.get('sqltext', 'N/A')
                            schema += f"  - {cc_name}: {cc_sql}\n"
                except (NotImplementedError, AttributeError):
                    # Algunos dialectos no soportan get_check_constraints
                    pass
            
            schema += "\n" + "-" * 50 + "\n\n"
        
        # Vistas (opcional)
        if include_views:
            try:
                view_names = inspector.get_view_names()
                if view_names:
                    schema += f"VIEWS ({len(view_names)} total):\n"
                    schema += "=" * 20 + "\n"
                    for view_name in view_names:
                        schema += f"VIEW: {view_name}\n"
                        try:
                            view_columns = inspector.get_columns(view_name)
                            for column in view_columns:
                                col_info = _format_column_info(column, is_view=True)
                                schema += f"  - {col_info}\n"
                        except Exception:
                            schema += "  - (Column information not available)\n"
                        schema += "\n"
            except (NotImplementedError, AttributeError):
                # Algunos dialectos no soportan vistas
                pass
        
        print(f"Retrieved complete database schema for {len(table_names)} tables.")
        return schema
        
    except SQLAlchemyError as e:
        error_msg = f"Error retrieving database schema: {str(e)}"
        print(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(error_msg)
        return error_msg


def _format_column_info(column, is_view=False):
    """
    Formatea la información de una columna de manera legible.
    
    Args:
        column: Diccionario con información de la columna
        is_view: Si la columna pertenece a una vista
    
    Returns:
        str: Información formateada de la columna
    """
    col_name = column["name"]
    col_type = str(column["type"])
    
    info_parts = [f"{col_name}: {col_type}"]
    
    # Nullable
    if not column.get("nullable", True):
        info_parts.append("NOT NULL")
    
    # Default value
    if column.get("default") is not None:
        default_val = column["default"]
        if hasattr(default_val, 'arg'):
            default_str = str(default_val.arg)
        else:
            default_str = str(default_val)
        info_parts.append(f"DEFAULT {default_str}")
    
    # Autoincrement
    if column.get("autoincrement", False):
        info_parts.append("AUTOINCREMENT")
    
    # Comment
    if column.get("comment"):
        info_parts.append(f"COMMENT '{column['comment']}'")
    
    return " | ".join(info_parts)


def get_table_relationships(engine):
    """
    Obtiene un resumen de las relaciones entre tablas.
    
    Args:
        engine: Motor de SQLAlchemy
    
    Returns:
        str: Resumen de relaciones formateado
    """
    try:
        inspector = inspect(engine)
        relationships = "=== TABLE RELATIONSHIPS ===\n\n"
        
        for table_name in inspector.get_table_names():
            foreign_keys = inspector.get_foreign_keys(table_name)
            if foreign_keys:
                relationships += f"{table_name}:\n"
                for fk in foreign_keys:
                    local_cols = ', '.join(fk['constrained_columns'])
                    ref_table = fk['referred_table']
                    ref_cols = ', '.join(fk['referred_columns'])
                    relationships += f"  └─ {local_cols} references {ref_table}({ref_cols})\n"
                relationships += "\n"
        
        return relationships
        
    except Exception as e:
        return f"Error retrieving relationships: {str(e)}"


# Ejemplo de uso
def example_usage():
    """
    Ejemplo de cómo usar las funciones mejoradas.
    """
    engine = get_engine()    
    # Esquema completo
    full_schema = get_database_schema(engine, 
                                  include_indexes=True, 
                                  include_constraints=True
    )
    print(full_schema)
    
    # Solo relaciones
    print("\n\n--------------------------------------------------\n\n")
    relationships = get_table_relationships(engine)
    print(relationships)

if __name__ == "__main__":
    example_usage()
