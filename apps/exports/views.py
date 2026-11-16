# apps/exports/views.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View


class TaskProgressoView(LoginRequiredMixin, View):
    """Restituisce il progresso di un task Celery tramite il result backend (Redis).

    Usato dal polling JS nella pagina cache-pdf per aggiornare la progress bar
    della generazione massiva PDF. Accessibile a qualunque utente autenticato:
    il task_id funge da token opaco. Logica in `apps.siteconfig.services.progresso_task`
    (condivisa con l'API `GET /api/v1/impostazioni/task/{task_id}`).
    """

    def get(self, request, task_id: str):
        from apps.siteconfig.services import progresso_task

        return JsonResponse(progresso_task(task_id))
