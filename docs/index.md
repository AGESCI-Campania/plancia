# Plancia — Documentazione

**Piattaforma Guidoncini Verdi · AGESCI Campania**

Plancia è la piattaforma web per la gestione del concorso [Guidoncini Verdi](https://www.agesci.it)
della Branca E/G di AGESCI Campania. Permette alle squadriglie di compilare il Diario di Bordo,
ai Capi Reparto di integrarlo con la Relazione finale, alla Pattuglia GV di valutarlo e alla
Segreteria di amministrare l'intera edizione.

---

## Manuale d'uso

La documentazione operativa è organizzata per ruolo:

| Ruolo | Cosa fa su Plancia |
|---|---|
| [Capo Squadriglia](manuale/csq.md) | Compila i sei moduli del Diario di Bordo |
| [Capo Reparto](manuale/crp.md) | Distribuisce i link ai Capi Squadriglia, compila la Relazione finale |
| [Pattuglia Guidoncini Verdi](manuale/pgv.md) | Valuta i diari assegnati |
| [Incaricato EG](manuale/incaricato.md) | Supervisiona le valutazioni e pubblica gli esiti |
| [Segreteria](manuale/segreteria.md) | Gestisce utenti, edizioni, import e inviti |
| [Amministratore](manuale/admin.md) | Configura la piattaforma, OAuth, MFA e social login |

Inizia dalla [Panoramica e ruoli](manuale/index.md) per una visione d'insieme.

---

## Guide tecniche

Per chi installa e configura Plancia:

- [Configurazione provider email](guide/email_provider.md) — SMTP, Brevo, Mailgun, Postmark, ecc.
- [Google Drive OAuth](guide/google_drive_oauth.md) — caricamento automatico PDF/Excel su Drive
- [Autenticazione social](guide/social_auth.md) — Google, Microsoft, Apple login

---

## Stack e deployment

| Componente | Tecnologia |
|---|---|
| Backend | Python ≥ 3.14, Django ≥ 6.0 |
| Database | PostgreSQL ≥ 17 |
| Task asincroni | Redis + Celery |
| Frontend | Bootstrap 5, django-agesci-campania-theme |
| Auth | django-allauth, MFA, social login |
| PDF / Excel | WeasyPrint, openpyxl |
| Gestione dipendenze | uv |

Per installazione e deployment consulta il [README](https://github.com/AGESCI-Campania/plancia#readme)
del repository.

---

## Specifica di progetto

La specifica completa (ruoli, modello dati, FSM, sicurezza, deployment) è in
[Plancia\_Progettazione.md](Plancia_Progettazione.md).
