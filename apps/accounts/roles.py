# apps/accounts/roles.py
"""Regole di creazione e nomina dei ruoli (docs sez. 2).

- Admin: creato solo da altri Admin (+ createsuperuser di Django).
- Segreteria: creata da Admin.
- IABR (Incaricati EG): creati da Admin o Segreteria.
- PGV/CRP/CSQ: nominati da Admin/Segreteria/IABR rispettando la categoria del Socio.

Vincoli di categoria:
- PGV, CRP, Segreteria, IABR -> il Socio collegato deve essere un CAPO.
- CSQ -> il Socio collegato deve essere un RAGAZZO.
- Admin -> nessun vincolo (puo' non avere Socio).
"""
from __future__ import annotations

from apps.accounts.models import Ruolo

# Categoria di Socio richiesta per ciascun ruolo (None = nessun vincolo).
ROLE_REQUIRES_CATEGORY: dict[str, str | None] = {
    Ruolo.ADMIN: None,
    Ruolo.SEGRETERIA: "capo",
    Ruolo.INCARICATO_EG: "capo",
    Ruolo.PGV: "capo",
    Ruolo.CRP: "capo",
    Ruolo.CSQ: "ragazzo",
}

# Chi puo' creare/nominare ciascun ruolo.
ROLE_CREATABLE_BY: dict[str, set[str]] = {
    Ruolo.ADMIN: {Ruolo.ADMIN},  # + createsuperuser (fuori dal flusso applicativo)
    Ruolo.SEGRETERIA: {Ruolo.ADMIN},
    Ruolo.INCARICATO_EG: {Ruolo.ADMIN, Ruolo.SEGRETERIA},
    Ruolo.PGV: {Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG},
    Ruolo.CRP: {Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG},
    Ruolo.CSQ: {Ruolo.ADMIN, Ruolo.SEGRETERIA, Ruolo.INCARICATO_EG},
}


def puo_nominare(attore_ruolo: str, ruolo_target: str) -> bool:
    return attore_ruolo in ROLE_CREATABLE_BY.get(ruolo_target, set())


def categoria_compatibile(ruolo_target: str, categoria_socio: str | None) -> bool:
    richiesta = ROLE_REQUIRES_CATEGORY.get(ruolo_target)
    return richiesta is None or richiesta == categoria_socio


def nomina(attore: User, utente: User, ruolo: str, edizione=None, scadenza=None) -> Nomina:
    """Assegna *ruolo* a *utente* per conto di *attore*.

    Applica puo_nominare + categoria_compatibile + esclusività CSQ, crea il record
    Nomina e (solo al primo ruolo) aggiorna utente.ruolo. Solleva PermissionError o
    ValueError in caso di violazione.

    Per passare al nuovo ruolo usa CambiaRuoloView o imposta utente.ruolo manualmente.
    """
    from apps.accounts.models import Nomina

    if not puo_nominare(attore.ruolo, ruolo):
        raise PermissionError(
            f"{attore.ruolo} non può nominare al ruolo {ruolo}."
        )

    # Esclusività CSQ nella stessa edizione (prima del check categoria per messaggio chiaro)
    if edizione is not None:
        if ruolo == Ruolo.CSQ:
            altri = Nomina.objects.filter(utente=utente, edizione=edizione, attiva=True).exclude(ruolo=Ruolo.CSQ)
            if altri.exists():
                raise ValueError("Nella stessa edizione, un CSQ non può avere altri ruoli.")
        else:
            csq = Nomina.objects.filter(utente=utente, edizione=edizione, ruolo=Ruolo.CSQ, attiva=True)
            if csq.exists():
                raise ValueError("Nella stessa edizione, un CSQ non può avere altri ruoli.")

    socio = getattr(utente, "socio", None)
    categoria = socio.categoria if socio else None
    if not categoria_compatibile(ruolo, categoria):
        richiesta = ROLE_REQUIRES_CATEGORY.get(ruolo)
        raise ValueError(
            f"Il ruolo {ruolo} richiede categoria '{richiesta}', "
            f"ma il socio ha categoria '{categoria}'."
        )

    # Primo ruolo: attiva subito; altrimenti l'utente sceglie dal selettore.
    if not utente.ruoli_attivi:
        utente.ruolo = ruolo
        utente.save(update_fields=["ruolo"])

    return Nomina.objects.create(
        utente=utente,
        socio=socio,
        ruolo=ruolo,
        nominato_da=attore,
        edizione=edizione,
        scadenza=scadenza,
    )


def nomina_staff_diretto(
    attore: User,
    email: str,
    first_name: str,
    last_name: str,
    ruolo: str,
) -> tuple[User, Nomina, bool]:
    """Crea un utente staff (Admin/Segreteria/IABR) senza Socio associato.

    Bypassa il check di categoria perché questi utenti non sono capi AGESCI
    ma puri utenti della piattaforma. Ritorna (utente, nomina, creato).
    """
    from apps.accounts.models import Nomina, User

    if not puo_nominare(attore.ruolo, ruolo):
        raise PermissionError(f"{attore.ruolo} non può creare il ruolo {ruolo}.")

    email = email.strip().lower()
    utente, creato = User.objects.get_or_create(
        email=email,
        defaults={
            "username": email,
            "first_name": first_name.strip(),
            "last_name": last_name.strip(),
            "ruolo": ruolo,
            "is_active": True,
        },
    )
    if not creato:
        if utente.ruoli_attivi:
            raise ValueError(f"L'utente {email} ha già ruoli attivi.")
    else:
        utente.set_unusable_password()
        utente.save(update_fields=["password"])

    n = Nomina.objects.create(
        utente=utente,
        socio=None,
        ruolo=ruolo,
        nominato_da=attore,
    )

    if not utente.ruoli_attivi or utente.ruolo != ruolo:
        utente.ruolo = ruolo
        utente.save(update_fields=["ruolo"])

    return utente, n, creato


# --- Impersonazione (docs sez. 2) -------------------------------------------
# Ranghi: Admin > Segreteria > IABR > PGV > CRP > CSQ
ROLE_RANK: dict[str, int] = {
    Ruolo.ADMIN: 100,
    Ruolo.SEGRETERIA: 80,
    Ruolo.INCARICATO_EG: 60,
    Ruolo.PGV: 40,
    Ruolo.CRP: 30,
    Ruolo.CSQ: 20,
}

# Solo questi ruoli possono impersonare.
IMPERSONATORI = {Ruolo.ADMIN, Ruolo.SEGRETERIA}


def _rango_massimo(utente) -> int:
    """Rango più alto tra tutti i ruoli attivi dell'utente."""
    try:
        ruoli = utente.ruoli_attivi
    except AttributeError:
        ruoli = []
    if not ruoli:
        ruoli = [getattr(utente, "ruolo", None)]
    return max((ROLE_RANK.get(r, 0) for r in ruoli if r), default=0)


def puo_impersonare(attore, target) -> bool:
    """True se 'attore' puo' impersonare 'target': attore in {Admin, Segreteria}
    e rango_massimo(target) <= rango(attore) (la Segreteria non impersona un Admin,
    neanche se l'Admin ha il ruolo attivo a CSQ).
    """
    if attore is None or target is None or attore.pk == target.pk:
        return False
    a = getattr(attore, "ruolo", None)
    if a not in IMPERSONATORI:
        return False
    return _rango_massimo(target) <= ROLE_RANK.get(a, 0)


def can_hijack(hijacker, hijacked) -> bool:
    """HIJACK_PERMISSION_CHECK per django-hijack."""
    return puo_impersonare(hijacker, hijacked)
