# apps/diaries/serialization.py
"""Helper di validazione e serializzazione condivisi tra api_views.py e l'API ninja.

Estratto da api_views.py per poter essere importato senza dipendere da Django views.
"""
from __future__ import annotations

from datetime import date

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from apps.diaries.models import (
    BREVETTI_COMPETENZA,
    SPECIALITA_INDIVIDUALI,
    SPECIALITA_SQUADRIGLIA,
    RuoloSq,
    SentieroCammino,
    StatoSpecialita,
    TipoDiario,
)

# Scelte valide per i campi di scelta — condivise tra api_views.py e router API
SCELTE_SPECIALITA_SQ: list[str] = [""] + list(SPECIALITA_SQUADRIGLIA)
SCELTE_TIPO_DIARIO: list[str] = [c[0] for c in TipoDiario.choices]
SCELTE_RUOLO_SQ: list[str] = [""] + [c[0] for c in RuoloSq.choices]
SCELTE_SENTIERO: list[str] = [c[0] for c in SentieroCammino.choices]
SCELTE_SPECIALITA_IND: list[str] = [""] + list(SPECIALITA_INDIVIDUALI)
SCELTE_BREVETTI: list[str] = [""] + list(BREVETTI_COMPETENZA)
SCELTE_STATO_SPECIALITA: list[str] = [c[0] for c in StatoSpecialita.choices]

# ---------------------------------------------------------------------------
# Validatori campo singolo
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
            raise ValidationError({key: ["indirizzo email non valido"]}) from None
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
        raise ValidationError({key: ["formato data non valido (YYYY-MM-DD)"]}) from None


def _opt_int_field(data: dict, key: str) -> int | None:
    val = data.get(key)
    if val is None:
        return None
    if not isinstance(val, int) or val < 1:
        raise ValidationError({key: ["intero positivo richiesto"]})
    return val


# ---------------------------------------------------------------------------
# Helper nested (create / update / delete by id)
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
# Serializzatori di lettura
# ---------------------------------------------------------------------------

def _anagrafica_data(anagrafica, diario) -> dict:
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


def _presentazione_data(pres) -> dict:
    return {
        "cosa_sappiamo_fare": pres.cosa_sappiamo_fare,
        "membri": [
            {"id": m.pk, "nome": m.nome, "ruolo": m.ruolo, "sentiero": m.sentiero}
            for m in pres.membri.all()
        ],
    }


def _impresa_data(impresa) -> dict:
    from apps.diaries.models import TipoEsito
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


def _missione_data(missione) -> dict:
    return {
        "titolo": missione.titolo,
        "data": missione.data.isoformat() if missione.data else None,
        "descrizione_svolgimento": missione.descrizione_svolgimento,
        "posti_azione": [
            {"descrizione": p.descrizione}
            for p in missione.posti_azione_missione.all()
        ],
    }


def _relazione_finale_data(rf) -> dict:
    return {
        "sintesi_impresa_1": rf.sintesi_impresa_1,
        "sintesi_impresa_2": rf.sintesi_impresa_2,
        "sintesi_missione": rf.sintesi_missione,
        "considerazioni": rf.considerazioni,
        "specialita_conquistata": rf.specialita_conquistata,
    }


def _valutazione_data(val) -> dict:
    return {
        "esito": val.esito,
        "esito_display": val.get_esito_display() if val.esito else None,
        "stato": val.stato,
        "note": val.note,
        "pubblicata": val.pubblicata,
    }


# ---------------------------------------------------------------------------
# Validatori nested per write (moduli diario)
# ---------------------------------------------------------------------------

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
    collect("ruolo", _choice_field, SCELTE_RUOLO_SQ)
    collect("sentiero", _choice_field, SCELTE_SENTIERO)

    if errors:
        raise ValidationError(errors)
    return out


def _apply_membro(obj, fields: dict) -> None:
    obj.nome = fields["nome"]
    obj.ruolo = fields["ruolo"]
    obj.sentiero = fields["sentiero"]


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


def _apply_posto_azione(obj, fields: dict) -> None:
    obj.chi = fields["chi"]
    obj.cosa = fields["cosa"]


def _validate_esito(choices: list[str]):
    """Ritorna una funzione di validazione per EsitoSpecialita con le scelte date."""
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
        collect("stato", _choice_field, SCELTE_STATO_SPECIALITA)

        if errors:
            raise ValidationError(errors)
        return out

    return _validate


def _apply_esito(tipo: str):
    """Ritorna una funzione di apply per EsitoSpecialita del tipo dato."""
    def _apply(obj, fields: dict) -> None:
        obj.tipo = tipo
        obj.chi = fields["chi"]
        obj.nome = fields["nome"]
        obj.stato = fields["stato"]
    return _apply


# ---------------------------------------------------------------------------
# Validatori di modulo completi (usati da api_views.py e router API)
# ---------------------------------------------------------------------------

def _validate_anagrafica(data: dict, is_staff: bool) -> dict:
    errors: dict[str, list] = {}
    out: dict = {}

    def collect(key: str, fn, *args):
        try:
            out[key] = fn(data, key, *args)
        except ValidationError as e:
            errors.update(e.message_dict)

    collect("squadriglia_nome", _str_field, 120)
    collect("tipo_diario", _choice_field, SCELTE_TIPO_DIARIO)
    collect("crp_nome", _str_field, 120)
    collect("crp_cognome", _str_field, 120)
    collect("crp_cell", _str_field, 30)
    collect("csq_nome", _str_field, 120)
    collect("csq_cognome", _str_field, 120)
    collect("csq_cell", _str_field, 30)
    collect("specialita", _choice_field, SCELTE_SPECIALITA_SQ)
    collect("crp_email", _email_field)
    collect("csq_email", _email_field)
    collect("partecipa_evento", _bool_field)

    if errors:
        raise ValidationError(errors)

    out["_is_staff"] = is_staff
    return out


def _apply_anagrafica(anagrafica, diario, cleaned: dict) -> None:
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


def _validate_relazione_finale(data: dict) -> dict:
    errors: dict[str, list] = {}
    out: dict = {}

    def collect(key: str, fn, *args):
        try:
            out[key] = fn(data, key, *args)
        except ValidationError as e:
            errors.update(e.message_dict)

    collect("sintesi_impresa_1", _str_field, 10000)
    collect("sintesi_impresa_2", _str_field, 10000)
    collect("sintesi_missione", _str_field, 10000)
    collect("considerazioni", _str_field, 10000)
    collect("specialita_conquistata", _bool_field)

    if errors:
        raise ValidationError(errors)
    return out


def _apply_relazione_finale(rf, cleaned: dict) -> None:
    rf.sintesi_impresa_1 = cleaned["sintesi_impresa_1"]
    rf.sintesi_impresa_2 = cleaned["sintesi_impresa_2"]
    rf.sintesi_missione = cleaned["sintesi_missione"]
    rf.considerazioni = cleaned["considerazioni"]
    rf.specialita_conquistata = cleaned["specialita_conquistata"]
