# apps/api/api.py
"""Istanza principale NinjaAPI per Plancia v1."""

from ninja import NinjaAPI

from apps.api.auth import plancia_auth
from apps.api.errors import registra_gestori
from apps.api.routers.aggiornamenti import router as aggiornamenti_router
from apps.api.routers.diaries import router as diari_router
from apps.api.routers.drive import router as drive_router
from apps.api.routers.editions import router as edizioni_router
from apps.api.routers.evaluations import router as evaluations_router
from apps.api.routers.helpdesk import router as helpdesk_router
from apps.api.routers.importazioni import router as importazioni_router
from apps.api.routers.impostazioni import router as impostazioni_router
from apps.api.routers.me import router as me_router
from apps.api.routers.notifiche import router as notifiche_router
from apps.api.routers.org import router as org_router
from apps.api.routers.sito import router as sito_router
from apps.api.routers.statistiche import router as statistiche_router
from apps.api.routers.system import router as system_router
from apps.api.routers.utenti import router as utenti_router

api = NinjaAPI(
    version="1.0.0",
    title="Plancia API",
    description="API REST per i Guidoncini Verdi AGESCI Campania.",
    docs_url="/docs",
    auth=plancia_auth,
)

api.add_router("/", system_router)
api.add_router("/", me_router)
api.add_router("/edizioni", edizioni_router)
api.add_router("/org", org_router)
api.add_router("/diari", diari_router)
api.add_router("/diari", evaluations_router)
api.add_router("/sito", sito_router)
api.add_router("/utenti", utenti_router)
api.add_router("/notifiche", notifiche_router)
api.add_router("/impostazioni", impostazioni_router)
api.add_router("/importazioni", importazioni_router)
api.add_router("/helpdesk", helpdesk_router)
api.add_router("/statistiche", statistiche_router)
api.add_router("/aggiornamenti", aggiornamenti_router)
api.add_router("/drive", drive_router)

registra_gestori(api)
