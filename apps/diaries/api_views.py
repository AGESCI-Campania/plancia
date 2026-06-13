# apps/diaries/api_views.py
import json
from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View

from apps.accounts.models import Ruolo
from apps.diaries.models import (
    Anagrafica,
    BREVETTI_COMPETENZA,
    Diario,
    EsitoSpecialita,
    Impresa,
    MembroSq,
    Missione,
    PostoAzione,
    Presentazione,
    RuoloSq,
    SentieroCammino,
    SPECIALITA_INDIVIDUALI,
    SPECIALITA_SQUADRIGLIA,
    StatoDiario,
    StatoSpecialita,
    TipoDiario,
    TipoEsito,
)

# ---------------------------------------------------------------------------
# Helpers di validazione
# ---------------------------------------------------------------------------

def _str_field(data: dict, key: str, max_length: int = 255) -> str:
    val = data.get(key, "")
    if not isinstance(val, str):
        raise ValidationError({key: ["stringa richiesta"]})
    if len(val) > max_length:
        raise ValidationError({key: [f"lunghezza massima {max_length} caratteri"]})
    return val


def _bool_field(data: dict, key: str) -> bool:
    val = data.get(key)
    if not isinstance(val, bool):
        raise ValidationError({key: ["booleano richiesto"]})
    return val


def _email_field(data: dict, key: str) -> str:
    val = _str_field(data, key, 254)
    if val:
        try:
            validate_email(val)
        except ValidationError:
            raise ValidationError({key: ["indirizzo email non valido"]})
    return val


def _choice_field(data: dict, key: str, choices: list[str]) -> str:
    val = _str_field(data, key, 120)
    if val not in choices:
        raise ValidationError({key: ["valore non valido"]})
    return val


def _date_field(data: dict, key: str) -> date | None:
    val = data.get(key)
    if val is None or val == "":
        return None
    if not isinstance(val, str):
        raise ValidationError({key: ["stringa ISO 8601 richiesta"]})
    try:
        return date.fromisoformat(val)
    except ValueError:
        raise ValidationError({key: ["formato data non valido (YYYY-MM-DD)"]})


def _opt_int_field(data: dict, key: str) -> int | None:
    val = data.get(key)
    if val is None:
        return None
    if not isinstance(val, int) or val < 1:
        raise ValidationError({key: ["intero positivo richiesto"]})
    return val


# ---------------------------------------------------------------------------
# Serializzatori
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Helpers nested (create / update / delete by id)
# ---------------------------------------------------------------------------

def _validate_nested(items: list, validate_fn) -> tuple[list[dict], dict]:
    """Valida una lista di oggetti nested; raccoglie tutti gli errori prima di fallire."""
    cleaned, errors = [], {}
    for i, item in enumerate(items):
        try:
            cleaned.append(validate_fn(item))
        except ValidationError as exc:
            errors[str(i)] = exc.message_dict
    return cleaned, errors


def _sync_nested(qs, cleaned_items: list[dict], model_class, apply_fn, **create_kwargs) -> None:
    """Sincronizza oggetti nested: update per id, create per id=None, delete se assenti."""
    existing_ids = set(qs.values_list("pk", flat=True))
    client_ids: set[int] = set()

    for item in cleaned_items:
        item_id = item.get("id")
        fields = {k: v for k, v in item.items() if k != "id"}

        if item_id is not None:
            client_ids.add(item_id)
            try:
                obj = qs.get(pk=item_id)
            except model_class.DoesNotExist:
                obj = model_class(**create_kwargs)
        else:
            obj = model_class(**create_kwargs)

        apply_fn(obj, fields)
        obj.save()

    to_delete = existing_ids - client_ids
    if to_delete:
        qs.filter(pk__in=to_delete).delete()


# ---------------------------------------------------------------------------
# Serializzatori
# ---------------------------------------------------------------------------

def _anagrafica_data(anagrafica: Anagrafica, diario: Diario) -> dict:
    return {
        "squadriglia_nome": diario.squadriglia.nome,
        "tipo_diario": diario.tipo,
        "crp_nome": anagrafica.crp_nome,
        "crp_cognome": anagrafica.crp_cognome,
        "crp_email": anagrafica.crp_email,
        "crp_cell": anagrafica.crp_cell,
        "csq_nome": anagrafica.csq_nome,
        "csq_cognome": anagrafica.csq_cognome,
        "csq_email": anagrafica.csq_email,
        "csq_cell": anagrafica.csq_cell,
        "specialita": anagrafica.specialita,
        "partecipa_evento": anagrafica.partecipa_evento,
        "desc_prima_impresa": anagrafica.desc_prima_impresa,
        "desc_seconda_impresa": anagrafica.desc_seconda_impresa,
        "tecniche": anagrafica.tecniche,
    }


def _presentazione_data(pres: Presentazione) -> dict:
    return {
        "cosa_sappiamo_fare": pres.cosa_sappiamo_fare,
        "membri": [
            {"id": m.pk, "nome": m.nome, "ruolo": m.ruolo, "sentiero": m.sentiero}
            for m in pres.membri.all()
        ],
    }


def _impresa_data(impresa: Impresa) -> dict:
    return {
        "titolo": impresa.titolo,
        "data_inizio": impresa.data_inizio.isoformat() if impresa.data_inizio else None,
        "data_fine": impresa.data_fine.isoformat() if impresa.data_fine else None,
        "perche": impresa.perche,
        "come": impresa.come,
        "cosa": impresa.cosa,
        "link_esterno": impresa.link_esterno,
        "posti_azione": [
            {"id": p.pk, "chi": p.chi, "cosa": p.cosa}
            for p in impresa.posti_azione.all()
        ],
        "specialita": [
            {"id": e.pk, "chi": e.chi, "nome": e.nome, "stato": e.stato}
            for e in impresa.esiti_specialita.filter(tipo=TipoEsito.SPECIALITA)
        ],
        "brevetti": [
            {"id": e.pk, "chi": e.chi, "nome": e.nome, "stato": e.stato}
            for e in impresa.esiti_specialita.filter(tipo=TipoEsito.BREVETTO)
        ],
    }


def _missione_data(missione: Missione) -> dict:
    return {
        "titolo": missione.titolo,
        "data": missione.data.isoformat() if missione.data else None,
        "descrizione_svolgimento": missione.descrizione_svolgimento,
    }


# ---------------------------------------------------------------------------
# Mixin base
# ---------------------------------------------------------------------------

class DiarioApiMixin(View):
    """Mixin comune a tutte le API JSON del Diario.

    Gestisce auth, accesso al diario e conversione delle eccezioni in JSON.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "unauthenticated"}, status=401)
        try:
            return super().dispatch(request, *args, **kwargs)
        except PermissionDenied:
            return JsonResponse({"error": "forbidden"}, status=403)
        except Http404:
            return JsonResponse({"error": "not_found"}, status=404)

    def _get_diario(self, pk: int) -> Diario:
        diario = get_object_or_404(
            Diario.objects.select_related("edizione", "squadriglia", "csq", "crp"),
            pk=pk,
        )
        user = self.request.user
        if user.is_superuser or user.is_staff_plancia:
            return diario
        if user.ruolo == Ruolo.CSQ and user.socio and diario.csq == user.socio:
            return diario
        if user.ruolo == Ruolo.CRP and user.socio and diario.crp == user.socio:
            return diario
        if user.ruolo == Ruolo.PGV:
            return diario
        raise PermissionDenied

    def _puo_editare(self, diario: Diario) -> bool:
        user = self.request.user
        if user.is_superuser or user.is_staff_plancia:
            return True
        return (
            diario.stato in (StatoDiario.NON_INIZIATO, StatoDiario.IN_COMPILAZIONE)
            and user.ruolo == Ruolo.CSQ
        )

    def _inizia_se_necessario(self, diario: Diario) -> None:
        if diario.stato == StatoDiario.NON_INIZIATO:
            diario.inizia()

    @staticmethod
    def _parse_body(request) -> tuple[dict, None] | tuple[None, JsonResponse]:
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None, JsonResponse({"error": "invalid_json"}, status=400)
        if not isinstance(body, dict):
            return None, JsonResponse({"error": "invalid_json"}, status=400)
        return body, None

    @staticmethod
    def _check_version(body: dict) -> tuple[int, None] | tuple[None, JsonResponse]:
        version = body.get("version")
        if not isinstance(version, int) or version < 0:
            return None, JsonResponse({"error": "version_required"}, status=400)
        return version, None


# ---------------------------------------------------------------------------
# GET /api/diari/<pk>/
# ---------------------------------------------------------------------------

class DiarioStatusApiView(DiarioApiMixin):

    def get(self, request, pk):
        diario = self._get_diario(pk)
        return JsonResponse({
            "stato": diario.stato,
            "tipo": diario.tipo,
            "puo_editare": self._puo_editare(diario),
            "moduli_csq_completi": diario.moduli_csq_completi,
            "has_anagrafica": hasattr(diario, "anagrafica"),
            "has_presentazione": hasattr(diario, "presentazione"),
            "imprese": list(diario.imprese.values_list("numero", flat=True)),
            "has_missione": hasattr(diario, "missione"),
        })


# ---------------------------------------------------------------------------
# GET / PUT /api/diari/<pk>/modulo/anagrafica/
# ---------------------------------------------------------------------------

_SPECIALITA_CHOICES = [""] + SPECIALITA_SQUADRIGLIA
_TIPO_DIARIO_CHOICES = [c[0] for c in TipoDiario.choices]


class AnagraficaApiView(DiarioApiMixin):

    def get(self, request, pk):
        diario = self._get_diario(pk)
        try:
            anagrafica = diario.anagrafica
        except Anagrafica.DoesNotExist:
            anagrafica = Anagrafica()  # non salvata — solo per i default
        return JsonResponse({
            "version": anagrafica.version,
            "data": _anagrafica_data(anagrafica, diario),
        })

    def put(self, request, pk):
        diario = self._get_diario(pk)
        if not self._puo_editare(diario):
            raise PermissionDenied

        body, err = self._parse_body(request)
        if err:
            return err

        client_version, err = self._check_version(body)
        if err:
            return err

        data = body.get("data")
        if not isinstance(data, dict):
            return JsonResponse({"error": "data_required"}, status=400)

        try:
            cleaned = self._validate(data)
        except ValidationError as exc:
            return JsonResponse({"error": "validation", "errors": exc.message_dict}, status=400)

        with transaction.atomic():
            try:
                anagrafica = Anagrafica.objects.select_for_update().get(diario=diario)
                if anagrafica.version != client_version:
                    return JsonResponse(
                        {"error": "conflict", "server_version": anagrafica.version},
                        status=409,
                    )
            except Anagrafica.DoesNotExist:
                if client_version != 0:
                    return JsonResponse({"error": "conflict", "server_version": 0}, status=409)
                anagrafica = Anagrafica(diario=diario)

            self._inizia_se_necessario(diario)
            self._apply(anagrafica, diario, cleaned)
            anagrafica.version = client_version + 1
            anagrafica.save()

        diario.refresh_from_db()
        diario.squadriglia.refresh_from_db()
        return JsonResponse({
            "version": anagrafica.version,
            "data": _anagrafica_data(anagrafica, diario),
        })

    def _validate(self, data: dict) -> dict:
        is_staff = self.request.user.is_staff_plancia or self.request.user.is_superuser
        errors: dict[str, list] = {}
        out: dict = {}

        def collect(key: str, fn, *args):
            try:
                out[key] = fn(data, key, *args)
            except ValidationError as e:
                errors.update(e.message_dict)

        collect("squadriglia_nome", _str_field, 120)
        collect("tipo_diario", _choice_field, _TIPO_DIARIO_CHOICES)
        collect("crp_nome", _str_field, 120)
        collect("crp_cognome", _str_field, 120)
        collect("crp_cell", _str_field, 30)
        collect("csq_nome", _str_field, 120)
        collect("csq_cognome", _str_field, 120)
        collect("csq_cell", _str_field, 30)
        collect("specialita", _choice_field, _SPECIALITA_CHOICES)
        collect("crp_email", _email_field)
        collect("csq_email", _email_field)
        collect("partecipa_evento", _bool_field)

        if errors:
            raise ValidationError(errors)

        out["_is_staff"] = is_staff
        return out

    @staticmethod
    def _apply(anagrafica: Anagrafica, diario: Diario, cleaned: dict) -> None:
        is_staff = cleaned.pop("_is_staff")

        anagrafica.crp_nome = cleaned["crp_nome"]
        anagrafica.crp_cognome = cleaned["crp_cognome"]
        anagrafica.crp_cell = cleaned["crp_cell"]
        anagrafica.csq_nome = cleaned["csq_nome"]
        anagrafica.csq_cognome = cleaned["csq_cognome"]
        anagrafica.csq_cell = cleaned["csq_cell"]
        anagrafica.specialita = cleaned["specialita"]
        anagrafica.partecipa_evento = cleaned["partecipa_evento"]

        if is_staff:
            anagrafica.crp_email = cleaned["crp_email"]
            anagrafica.csq_email = cleaned["csq_email"]

        if cleaned["tipo_diario"] != diario.tipo:
            diario.tipo = cleaned["tipo_diario"]
            diario.save(update_fields=["tipo"])

        nuovo_nome = cleaned["squadriglia_nome"].strip()
        if nuovo_nome and nuovo_nome != diario.squadriglia.nome:
            diario.squadriglia.nome = nuovo_nome
            diario.squadriglia.save(update_fields=["nome"])


# ---------------------------------------------------------------------------
# GET / PUT /api/diari/<pk>/modulo/presentazione/
# ---------------------------------------------------------------------------

_RUOLO_SQ_CHOICES = [""] + [c[0] for c in RuoloSq.choices]
_SENTIERO_CHOICES = [c[0] for c in SentieroCammino.choices]


def _validate_membro(item: dict) -> dict:
    errors: dict[str, list] = {}
    out: dict = {}

    def collect(key, fn, *args):
        try:
            out[key] = fn(item, key, *args)
        except ValidationError as e:
            errors.update(e.message_dict)

    try:
        out["id"] = _opt_int_field(item, "id")
    except ValidationError as e:
        errors.update(e.message_dict)

    collect("nome", _str_field, 120)
    collect("ruolo", _choice_field, _RUOLO_SQ_CHOICES)
    collect("sentiero", _choice_field, _SENTIERO_CHOICES)

    if errors:
        raise ValidationError(errors)
    return out


def _apply_membro(obj: MembroSq, fields: dict) -> None:
    obj.nome = fields["nome"]
    obj.ruolo = fields["ruolo"]
    obj.sentiero = fields["sentiero"]


class PresentazioneApiView(DiarioApiMixin):

    def get(self, request, pk):
        diario = self._get_diario(pk)
        try:
            pres = diario.presentazione
        except Presentazione.DoesNotExist:
            return JsonResponse({"version": 0, "data": {"cosa_sappiamo_fare": "", "membri": []}})
        return JsonResponse({
            "version": pres.version,
            "data": _presentazione_data(pres),
        })

    def put(self, request, pk):
        diario = self._get_diario(pk)
        if not self._puo_editare(diario):
            raise PermissionDenied

        body, err = self._parse_body(request)
        if err:
            return err
        client_version, err = self._check_version(body)
        if err:
            return err

        data = body.get("data")
        if not isinstance(data, dict):
            return JsonResponse({"error": "data_required"}, status=400)

        errors: dict[str, list] = {}
        try:
            cosa_sappiamo_fare = _str_field(data, "cosa_sappiamo_fare", 10000)
        except ValidationError as e:
            errors.update(e.message_dict)
            cosa_sappiamo_fare = ""

        raw_membri = data.get("membri", [])
        if not isinstance(raw_membri, list):
            return JsonResponse({"error": "membri_must_be_list"}, status=400)
        cleaned_membri, nested_errors = _validate_nested(raw_membri, _validate_membro)
        if nested_errors:
            errors["membri"] = nested_errors

        if errors:
            return JsonResponse({"error": "validation", "errors": errors}, status=400)

        with transaction.atomic():
            try:
                pres = Presentazione.objects.select_for_update().get(diario=diario)
                if pres.version != client_version:
                    return JsonResponse(
                        {"error": "conflict", "server_version": pres.version}, status=409
                    )
            except Presentazione.DoesNotExist:
                if client_version != 0:
                    return JsonResponse({"error": "conflict", "server_version": 0}, status=409)
                pres = Presentazione(diario=diario)
                pres.save()  # serve il pk per i membri

            self._inizia_se_necessario(diario)
            pres.cosa_sappiamo_fare = cosa_sappiamo_fare
            pres.version = client_version + 1
            pres.save()

            _sync_nested(
                qs=pres.membri.all(),
                cleaned_items=cleaned_membri,
                model_class=MembroSq,
                apply_fn=_apply_membro,
                presentazione=pres,
            )

        pres.refresh_from_db()
        return JsonResponse({
            "version": pres.version,
            "data": _presentazione_data(pres),
        })


# ---------------------------------------------------------------------------
# GET / PUT /api/diari/<pk>/modulo/impresa/<numero>/
# ---------------------------------------------------------------------------

_SPECIALITA_IND_CHOICES = [""] + SPECIALITA_INDIVIDUALI
_BREVETTI_CHOICES = [""] + BREVETTI_COMPETENZA
_STATO_SPECIALITA_CHOICES = [c[0] for c in StatoSpecialita.choices]


def _validate_posto_azione(item: dict) -> dict:
    errors: dict[str, list] = {}
    out: dict = {}

    def collect(key, fn, *args):
        try:
            out[key] = fn(item, key, *args)
        except ValidationError as e:
            errors.update(e.message_dict)

    try:
        out["id"] = _opt_int_field(item, "id")
    except ValidationError as e:
        errors.update(e.message_dict)

    collect("chi", _str_field, 200)
    collect("cosa", _str_field, 300)

    if errors:
        raise ValidationError(errors)
    return out


def _validate_esito(choices: list[str]):
    def _validate(item: dict) -> dict:
        errors: dict[str, list] = {}
        out: dict = {}

        def collect(key, fn, *args):
            try:
                out[key] = fn(item, key, *args)
            except ValidationError as e:
                errors.update(e.message_dict)

        try:
            out["id"] = _opt_int_field(item, "id")
        except ValidationError as e:
            errors.update(e.message_dict)

        collect("chi", _str_field, 120)
        collect("nome", _choice_field, choices)
        collect("stato", _choice_field, _STATO_SPECIALITA_CHOICES)

        if errors:
            raise ValidationError(errors)
        return out

    return _validate


def _apply_posto_azione(obj: PostoAzione, fields: dict) -> None:
    obj.chi = fields["chi"]
    obj.cosa = fields["cosa"]


def _apply_esito(tipo: str):
    def _apply(obj: EsitoSpecialita, fields: dict) -> None:
        obj.tipo = tipo
        obj.chi = fields["chi"]
        obj.nome = fields["nome"]
        obj.stato = fields["stato"]
    return _apply


class ImpresaApiView(DiarioApiMixin):

    def get(self, request, pk, numero):
        diario = self._get_diario(pk)
        try:
            impresa = diario.imprese.get(numero=numero)
        except Impresa.DoesNotExist:
            return JsonResponse({"version": 0, "data": {
                "titolo": "", "data_inizio": None, "data_fine": None,
                "perche": "", "come": "", "cosa": "", "link_esterno": "",
                "posti_azione": [], "specialita": [], "brevetti": [],
            }})
        return JsonResponse({
            "version": impresa.version,
            "data": _impresa_data(impresa),
        })

    def put(self, request, pk, numero):
        if numero not in (1, 2):
            return JsonResponse({"error": "numero_non_valido"}, status=400)

        diario = self._get_diario(pk)
        if not self._puo_editare(diario):
            raise PermissionDenied

        body, err = self._parse_body(request)
        if err:
            return err
        client_version, err = self._check_version(body)
        if err:
            return err

        data = body.get("data")
        if not isinstance(data, dict):
            return JsonResponse({"error": "data_required"}, status=400)

        errors: dict[str, list] = {}

        def collect_top(key, fn, *args):
            try:
                return fn(data, key, *args)
            except ValidationError as e:
                errors.update(e.message_dict)
                return None

        titolo = collect_top("titolo", _str_field, 200) or ""
        data_inizio = collect_top("data_inizio", _date_field)
        data_fine = collect_top("data_fine", _date_field)
        perche = collect_top("perche", _str_field, 10000) or ""
        come = collect_top("come", _str_field, 10000) or ""
        cosa = collect_top("cosa", _str_field, 10000) or ""
        link_esterno = collect_top("link_esterno", _str_field, 200) or ""

        for key in ("posti_azione", "specialita", "brevetti"):
            if not isinstance(data.get(key, []), list):
                return JsonResponse({"error": f"{key}_must_be_list"}, status=400)

        cleaned_posti, errs = _validate_nested(data.get("posti_azione", []), _validate_posto_azione)
        if errs:
            errors["posti_azione"] = errs

        cleaned_specialita, errs = _validate_nested(
            data.get("specialita", []), _validate_esito(_SPECIALITA_IND_CHOICES)
        )
        if errs:
            errors["specialita"] = errs

        cleaned_brevetti, errs = _validate_nested(
            data.get("brevetti", []), _validate_esito(_BREVETTI_CHOICES)
        )
        if errs:
            errors["brevetti"] = errs

        if errors:
            return JsonResponse({"error": "validation", "errors": errors}, status=400)

        with transaction.atomic():
            try:
                impresa = Impresa.objects.select_for_update().get(diario=diario, numero=numero)
                if impresa.version != client_version:
                    return JsonResponse(
                        {"error": "conflict", "server_version": impresa.version}, status=409
                    )
            except Impresa.DoesNotExist:
                if client_version != 0:
                    return JsonResponse({"error": "conflict", "server_version": 0}, status=409)
                impresa = Impresa(diario=diario, numero=numero)
                impresa.save()  # serve il pk per i nested

            self._inizia_se_necessario(diario)
            impresa.titolo = titolo
            impresa.data_inizio = data_inizio
            impresa.data_fine = data_fine
            impresa.perche = perche
            impresa.come = come
            impresa.cosa = cosa
            impresa.link_esterno = link_esterno
            impresa.version = client_version + 1
            impresa.save()

            _sync_nested(
                qs=impresa.posti_azione.all(),
                cleaned_items=cleaned_posti,
                model_class=PostoAzione,
                apply_fn=_apply_posto_azione,
                impresa=impresa,
            )
            _sync_nested(
                qs=impresa.esiti_specialita.filter(tipo=TipoEsito.SPECIALITA),
                cleaned_items=cleaned_specialita,
                model_class=EsitoSpecialita,
                apply_fn=_apply_esito(TipoEsito.SPECIALITA),
                impresa=impresa,
            )
            _sync_nested(
                qs=impresa.esiti_specialita.filter(tipo=TipoEsito.BREVETTO),
                cleaned_items=cleaned_brevetti,
                model_class=EsitoSpecialita,
                apply_fn=_apply_esito(TipoEsito.BREVETTO),
                impresa=impresa,
            )

        impresa.refresh_from_db()
        return JsonResponse({
            "version": impresa.version,
            "data": _impresa_data(impresa),
        })


# ---------------------------------------------------------------------------
# GET / PUT /api/diari/<pk>/modulo/missione/
# ---------------------------------------------------------------------------

class MissioneApiView(DiarioApiMixin):

    def get(self, request, pk):
        diario = self._get_diario(pk)
        try:
            missione = diario.missione
        except Missione.DoesNotExist:
            missione = Missione()
        return JsonResponse({
            "version": missione.version,
            "data": _missione_data(missione),
        })

    def put(self, request, pk):
        diario = self._get_diario(pk)
        if not self._puo_editare(diario):
            raise PermissionDenied

        body, err = self._parse_body(request)
        if err:
            return err
        client_version, err = self._check_version(body)
        if err:
            return err

        data = body.get("data")
        if not isinstance(data, dict):
            return JsonResponse({"error": "data_required"}, status=400)

        errors: dict[str, list] = {}

        def collect(key, fn, *args):
            try:
                return fn(data, key, *args)
            except ValidationError as e:
                errors.update(e.message_dict)
                return None

        titolo = collect("titolo", _str_field, 200) or ""
        data_missione = collect("data", _date_field)
        descrizione = collect("descrizione_svolgimento", _str_field, 10000) or ""

        if errors:
            return JsonResponse({"error": "validation", "errors": errors}, status=400)

        with transaction.atomic():
            try:
                missione = Missione.objects.select_for_update().get(diario=diario)
                if missione.version != client_version:
                    return JsonResponse(
                        {"error": "conflict", "server_version": missione.version}, status=409
                    )
            except Missione.DoesNotExist:
                if client_version != 0:
                    return JsonResponse({"error": "conflict", "server_version": 0}, status=409)
                missione = Missione(diario=diario)

            self._inizia_se_necessario(diario)
            missione.titolo = titolo
            missione.data = data_missione
            missione.descrizione_svolgimento = descrizione
            missione.version = client_version + 1
            missione.save()

        return JsonResponse({
            "version": missione.version,
            "data": _missione_data(missione),
        })
