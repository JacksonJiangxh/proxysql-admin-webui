"""Wizard mode API endpoints."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from app.middleware import get_current_user, require_role
from app.services.wizard_engine import WIZARD_REGISTRY
from app.services.proxysql import proxysql_service
from app.utils.db_helpers import get_proxysql_credentials

router = APIRouter()


# ── Helper: serialize a field definition for the frontend ──────
def _serialize_field(f) -> dict:
    data = {
        "name": f.name,
        "label": f.label,
        "type": f.type,
        "required": f.required,
        "default": f.default,
        "options": f.options,
        "help": f.help_text,
        "placeholder": f.placeholder,
        "validation": f.validation,
        "min": f.min,
        "max": f.max,
    }
    if f.lookup:
        data["lookup"] = {
            "table": f.lookup.get("table", ""),
            "label_template": f.lookup.get("label_template", ""),
            "linked_fields": f.lookup.get("linked_fields", {}),
            "allow_manual": f.lookup.get("allow_manual", True),
        }
    return data


class WizardExecuteRequest(BaseModel):
    wizard_id: str
    server_id: str
    fields: dict
    options: dict = {"auto_apply": False, "auto_save": False, "dry_run": False}


class WizardPreviewRequest(BaseModel):
    wizard_id: str
    server_id: str
    fields: dict


class LookupOptionsRequest(BaseModel):
    server_id: str
    wizard_id: str
    field_name: str


@router.get("/definitions")
async def get_wizard_definitions(user=Depends(get_current_user)):
    """Get all wizard definitions for dynamic form rendering."""
    wizards = []
    for wizard_id, wizard in WIZARD_REGISTRY.items():
        definition = wizard.definition
        fields_list = [_serialize_field(f) for f in definition.fields]

        wizards.append({
            "id": definition.id,
            "category": definition.category,
            "name": definition.name,
            "description": definition.description,
            "guide": definition.guide,
            "icon": definition.icon,
            "fields": fields_list,
            "auto_apply_module": definition.auto_apply_module,
            "related_tables": definition.related_tables,
            "status": definition.status,
        })

    return {"wizards": wizards}


@router.get("/definitions/{wizard_id}")
async def get_wizard_definition(wizard_id: str, user=Depends(get_current_user)):
    """Get a single wizard definition."""
    wizard = WIZARD_REGISTRY.get(wizard_id)
    if not wizard:
        raise HTTPException(status_code=404, detail=f"Wizard '{wizard_id}' not found")

    definition = wizard.definition
    fields_list = [_serialize_field(f) for f in definition.fields]

    return {
        "id": definition.id,
        "category": definition.category,
        "name": definition.name,
        "description": definition.description,
        "guide": definition.guide,
        "icon": definition.icon,
        "fields": fields_list,
        "auto_apply_module": definition.auto_apply_module,
        "related_tables": definition.related_tables,
        "status": definition.status,
    }


@router.post("/lookup-options")
async def get_lookup_options(data: LookupOptionsRequest, user=Depends(get_current_user)):
    """Fetch dynamic dropdown options for a lookup-type wizard field.

    The backend reads the lookup definition from the wizard field, builds
    and executes the appropriate SELECT query on the target ProxySQL instance,
    and returns the rows so the frontend can populate the dropdown.
    """
    wizard = WIZARD_REGISTRY.get(data.wizard_id)
    if not wizard:
        raise HTTPException(status_code=404, detail=f"Wizard '{data.wizard_id}' not found")

    # Find the lookup field
    target_field = None
    for f in wizard.definition.fields:
        if f.name == data.field_name:
            target_field = f
            break
    if not target_field:
        raise HTTPException(status_code=404, detail=f"Field '{data.field_name}' not found in wizard '{data.wizard_id}'")
    if target_field.type != "lookup":
        raise HTTPException(status_code=400, detail=f"Field '{data.field_name}' is not a lookup field")
    if not target_field.lookup:
        raise HTTPException(status_code=400, detail=f"Field '{data.field_name}' has no lookup config")

    host, port, admin_user, password = await get_proxysql_credentials(data.server_id)
    sql = target_field.get_lookup_sql()

    try:
        rows = await proxysql_service.execute_query(host, port, admin_user, password, sql)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to query lookup data: {e}")

    # Build options list for the frontend
    linked = target_field.lookup.get("linked_fields", {})
    label_tpl = target_field.lookup.get("label_template", "")
    options = []
    for row in rows:
        label = label_tpl.format(**row) if label_tpl else " | ".join(str(v) for v in row.values())
        option = {"label": label, "value": label, "fields": {}}
        for col_key, field_name in linked.items():
            if col_key in row:
                option["fields"][field_name] = row[col_key]
        options.append(option)

    return {"options": options, "field_name": data.field_name}


@router.post("/preview")
async def preview_wizard(data: WizardPreviewRequest, user=Depends(get_current_user)):
    """Preview the SQL that a wizard would generate."""
    wizard = WIZARD_REGISTRY.get(data.wizard_id)
    if not wizard:
        raise HTTPException(status_code=404, detail=f"Wizard '{data.wizard_id}' not found")

    if wizard.definition.status != "implemented":
        raise HTTPException(
            status_code=501,
            detail=f"Wizard '{data.wizard_id}' is planned but not yet implemented"
        )

    return wizard.preview_sql(data.fields)


@router.post("/execute")
async def execute_wizard(
    data: WizardExecuteRequest,
    user=Depends(require_role("admin", "operator")),
):
    """Execute a wizard operation."""
    wizard = WIZARD_REGISTRY.get(data.wizard_id)
    if not wizard:
        raise HTTPException(status_code=404, detail=f"Wizard '{data.wizard_id}' not found")

    if wizard.definition.status != "implemented":
        raise HTTPException(
            status_code=501,
            detail=f"Wizard '{data.wizard_id}' is planned but not yet implemented"
        )

    host, port, admin_user, password = await get_proxysql_credentials(data.server_id)

    options = data.options or {}
    result = await wizard.execute(
        host, port, admin_user, password,
        data.fields,
        auto_apply=options.get("auto_apply", False),
        auto_save=options.get("auto_save", False),
    )

    # Store in wizard history
    from app.database import get_db
    import json
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO wizard_history
               (user_id, server_id, wizard_id, wizard_name, category,
                submitted_fields, executed_sql, auto_apply, auto_save, success, error_message)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user["id"], data.server_id, data.wizard_id, wizard.definition.name,
             wizard.definition.category,
             json.dumps(data.fields),
             json.dumps(result.get("executed_sql", [])),
             1 if options.get("auto_apply") else 0,
             1 if options.get("auto_save") else 0,
             1 if result.get("ok") else 0,
             result.get("errors", [None])[0] if result.get("errors") else None)
        )
        await db.commit()
    finally:
        await db.close()

    return result


@router.get("/history/{server_id}")
async def get_wizard_history(
    server_id: str,
    limit: int = 20,
    user=Depends(get_current_user),
):
    """Get wizard execution history."""
    from app.database import get_db
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT id, wizard_id, wizard_name, category, success, auto_apply, auto_save, created_at
               FROM wizard_history
               WHERE user_id = ? AND server_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (user["id"], server_id, limit)
        )
        rows = await cursor.fetchall()
        return {"history": [dict(r) for r in rows]}
    finally:
        await db.close()
