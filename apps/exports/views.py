# apps/exports/views.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View


class TaskProgressoView(LoginRequiredMixin, View):
    """Restituisce il progresso di un task Celery tramite il result backend (Redis).

    Usato dal polling JS nella pagina cache-pdf per aggiornare la progress bar
    della generazione massiva PDF. Accessibile a qualunque utente autenticato:
    il task_id funge da token opaco.
    """

    def get(self, request, task_id: str):
        from celery.result import AsyncResult

        result = AsyncResult(task_id)
        state = result.state

        if state == "PROGRESS":
            meta = result.info or {}
            return JsonResponse({
                "stato": "PROGRESS",
                "progresso": meta.get("progresso", 0),
                "completati": meta.get("completati", 0),
                "totale": meta.get("totale", 0),
            })
        if state == "SUCCESS":
            return JsonResponse({"stato": "SUCCESS", "progresso": 100})
        if state == "FAILURE":
            return JsonResponse({"stato": "FAILURE", "progresso": 0})
        # PENDING / STARTED / RETRY
        return JsonResponse({"stato": state, "progresso": 0})
