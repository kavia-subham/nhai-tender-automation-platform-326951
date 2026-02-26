from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.api.core.db import Db, get_db
from src.api.core.security import AuthUser, require_roles
from src.api.models import AssignRoleRequest, Role

router = APIRouter(prefix="/rbac", tags=["rbac"])


@router.get(
    "/roles",
    summary="List roles",
    description="Admin endpoint to list RBAC roles.",
    operation_id="rbac_list_roles",
    response_model=list[Role],
)
def list_roles(_: AuthUser = Depends(require_roles("admin")), db: Db = Depends(get_db)) -> list[Role]:
    """List roles."""
    rows = db.fetch_all("SELECT id, name, description FROM public.roles ORDER BY name ASC")
    return [Role(id=str(r["id"]), name=r["name"], description=r.get("description")) for r in rows]


@router.post(
    "/assign",
    summary="Assign role",
    description="Admin endpoint to assign a role to a user.",
    operation_id="rbac_assign_role",
)
def assign_role(payload: AssignRoleRequest, _: AuthUser = Depends(require_roles("admin")), db: Db = Depends(get_db)):
    """Assign a role to a user by role name."""
    role = db.fetch_one("SELECT id FROM public.roles WHERE name=%(name)s", {"name": payload.role_name})
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    db.execute(
        """
        INSERT INTO public.user_roles (user_id, role_id)
        VALUES (%(uid)s, %(rid)s)
        ON CONFLICT DO NOTHING
        """,
        {"uid": payload.user_id, "rid": str(role["id"])},
    )
    return {"ok": True}
