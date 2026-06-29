# apps/api/api.py
"""Istanza principale NinjaAPI per Plancia v1."""
from ninja import NinjaAPI

from apps.api.auth import plancia_auth
from apps.api.routers.diaries import router as diari_router
from apps.api.routers.editions import router as edizioni_router
from apps.api.routers.evaluations import router as evaluations_router
from apps.api.routers.me import router as me_router
from apps.api.routers.org import router as org_router

api = NinjaAPI(
    version="1.0.0",
    title="Plancia API",
    description="API REST per i Guidoncini Verdi AGESCI Campania.",
    docs_url="/docs",
    auth=plancia_auth,
)

api.add_router("/", me_router)
api.add_router("/edizioni", edizioni_router)
api.add_router("/org", org_router)
api.add_router("/diari", diari_router)
api.add_router("/diari", evaluations_router)
