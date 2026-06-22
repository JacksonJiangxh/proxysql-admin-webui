"""Code emitter for generating Pydantic models and FastAPI routes."""
from typing import TextIO
from codegen.parser import TableDef


def emit_models(tables: list[TableDef], out: TextIO):
    """Generate Pydantic models for all tables."""
    out.write('"""Auto-generated Pydantic models for ProxySQL tables."""\n')
    out.write('from pydantic import BaseModel, Field\n')
    out.write('from typing import Optional\n')
    out.write('from enum import Enum\n\n')

    # Generate enums for columns with CHECK IN values
    for table in tables:
        for col in table.columns:
            if col.check_values:
                enum_name = f"{table.model_class_name}{col.name.capitalize()}"
                out.write(f"\nclass {enum_name}(str, Enum):\n")
                for val in col.check_values:
                    out.write(f'    {val} = "{val}"\n')
                out.write("\n")

    # Generate models
    for table in tables:
        class_name = table.model_class_name

        # Base model (read)
        out.write(f"\n\nclass {class_name}Base(BaseModel):\n")
        if not table.columns:
            out.write("    pass\n")
            continue

        for col in table.columns:
            py_type = col.python_type
            # Use enum type if available
            if col.check_values:
                py_type = f"{class_name}{col.name.capitalize()}"

            if col.nullable:
                py_type = f"Optional[{py_type}]"

            default_part = ""
            if col.default is not None:
                if isinstance(col.default, str):
                    default_part = f' = "{col.default}"'
                else:
                    default_part = f" = {col.default}"

            comment = ""
            if col.check_expression:
                comment = f'  # CHECK: {col.check_expression}'

            out.write(f"    {col.name}: {py_type}{default_part}{comment}\n")

        if table.is_readonly:
            # Readonly model is just the base
            out.write(f"\n\nclass {class_name}({class_name}Base):\n")
            out.write("    pass\n")
        else:
            # Create model (all fields required)
            out.write(f"\n\nclass {class_name}Create({class_name}Base):\n")
            out.write("    pass\n")

            # Update model (all fields optional except PKs)
            out.write(f"\n\nclass {class_name}Update(BaseModel):\n")
            if not table.columns:
                out.write("    pass\n")
                continue

            pk_names = set(table.all_pk_columns)
            for col in table.columns:
                if col.name in pk_names:
                    continue  # Skip PKs in update model
                py_type = col.python_type
                if col.check_values:
                    py_type = f"{class_name}{col.name.capitalize()}"
                out.write(f"    {col.name}: Optional[{py_type}] = None\n")


def emit_crud_router(tables: list[TableDef], out: TextIO):
    """Generate FastAPI CRUD router."""
    out.write('"""Auto-generated CRUD routes for ProxySQL tables."""\n')
    out.write('from fastapi import APIRouter, Depends, HTTPException\n')
    out.write('from app.services.proxysql import proxysql_service\n')
    out.write('from app.generated.models import *\n')
    out.write('from app.middleware import get_current_user\n\n')
    out.write('router = APIRouter()\n\n')

    for table in tables:
        table_name = table.table_name
        class_name = table.model_class_name
        pk_cols = table.all_pk_columns

        # GET list
        out.write(f'\n@router.get("/{table_name}", response_model=list[{class_name}Base])\n')
        out.write(f'async def list_{table_name}(user=Depends(get_current_user)):\n')
        out.write(f'    """List all rows in {table_name}."""\n')
        out.write(f'    return []\n')  # Placeholder

        # POST (only for writable tables)
        if not table.is_readonly and pk_cols:
            out.write(f'\n@router.post("/{table_name}", response_model={class_name}Create)\n')
            out.write(f'async def create_{table_name}(data: {class_name}Create, user=Depends(get_current_user)):\n')
            out.write(f'    """Create a new row in {table_name}."""\n')
            out.write(f'    return data\n')


def emit_metadata(tables: list[TableDef], out: TextIO):
    """Generate table metadata dictionary."""
    out.write('"""Auto-generated table metadata."""\n\n')
    out.write('TABLE_METADATA = {\n')

    for table in tables:
        columns_info = []
        for col in table.columns:
            info = {
                "name": col.name,
                "type": col.raw_type,
                "nullable": col.nullable,
            }
            if col.default is not None:
                info["default"] = col.default
            if col.check_values:
                info["check_values"] = col.check_values
            columns_info.append(info)

        out.write(f'    "{table.table_name}": {{\n')
        out.write(f'        "macro_name": "{table.macro_name}",\n')
        out.write(f'        "is_readonly": {table.is_readonly},\n')
        out.write(f'        "is_view": {table.is_view},\n')
        out.write(f'        "primary_keys": {table.all_pk_columns},\n')
        out.write(f'        "model_class": "{table.model_class_name}",\n')
        out.write(f'        "columns": {repr(columns_info)},\n')
        out.write(f'    }},\n')

    out.write('}\n')
