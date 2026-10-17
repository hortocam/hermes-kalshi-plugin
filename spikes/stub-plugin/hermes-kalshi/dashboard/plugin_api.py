"""S1 stub: module-level router; expect it at /api/plugins/hermes-kalshi/ping."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/ping")
def ping():
    return {"ok": True, "source": "hermes-kalshi spike"}
