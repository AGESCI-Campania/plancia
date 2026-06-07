# apps/diaries/tests/test_cambio_referenti.py
"""Test per le view CambiaCsqView, CambiaCrpView, CambiaCrpRepartoView (docs sez. 4)."""

from apps.diaries.models import Diario, StatoDiario

# ---------------------------------------------------------------------------
# Test CambiaCsqView
# ---------------------------------------------------------------------------

class TestCambiaCsqPermessi:
    """Solo CRP (del diario, in IN_COMPILAZIONE) e staff possono cambiare il CSQ."""

    def test_crp_del_diario_accede_in_compilazione(self, diario, user_crp, client):
        client.force_login(user_crp)
        resp = client.get(f"/diari/{diario.pk}/cambia-csq/")
        assert resp.status_code == 200

    def test_crp_del_diario_non_accede_in_relazione_finale(self, diario, user_crp, client):
        diario.stato = StatoDiario.RELAZIONE_FINALE
        diario.save()
        client.force_login(user_crp)
        resp = client.get(f"/diari/{diario.pk}/cambia-csq/")
        assert resp.status_code == 403

    def test_crp_non_referente_non_accede(self, diario, db, zona, gruppo, client):
        from apps.accounts.models import Ruolo, User
        from apps.org.models import Socio

        altro_socio = Socio.objects.create(
            codice_socio="811001", nome="Altro", cognome="CRP",
            email="altroCRP@test.it", categoria="capo", zona=zona, gruppo=gruppo,
        )
        altro_crp = User.objects.create_user(
            username="altro_crp", email="altroCRP@test.it",
            password="x", ruolo=Ruolo.CRP,
        )
        altro_crp.socio = altro_socio
        altro_crp.save()
        client.force_login(altro_crp)
        resp = client.get(f"/diari/{diario.pk}/cambia-csq/")
        assert resp.status_code == 403

    def test_csq_non_puo_cambiare_csq(self, diario, user_csq, client):
        client.force_login(user_csq)
        resp = client.get(f"/diari/{diario.pk}/cambia-csq/")
        assert resp.status_code == 403

    def test_admin_accede_in_compilazione(self, diario, user_admin, client):
        client.force_login(user_admin)
        resp = client.get(f"/diari/{diario.pk}/cambia-csq/")
        assert resp.status_code == 200

    def test_admin_accede_in_relazione_finale(self, diario, user_admin, client):
        diario.stato = StatoDiario.RELAZIONE_FINALE
        diario.save()
        client.force_login(user_admin)
        resp = client.get(f"/diari/{diario.pk}/cambia-csq/")
        assert resp.status_code == 200

    def test_admin_non_accede_dopo_invio(self, diario, user_admin, client):
        diario.stato = StatoDiario.INVIATO
        diario.save()
        client.force_login(user_admin)
        resp = client.get(f"/diari/{diario.pk}/cambia-csq/")
        assert resp.status_code == 403

    def test_non_autenticato_redirect_login(self, diario, client):
        resp = client.get(f"/diari/{diario.pk}/cambia-csq/")
        assert resp.status_code == 302
        assert "/accounts/login/" in resp["Location"]


class TestCambiaCsqPost:
    """Il POST aggiorna diario.csq se i dati sono validi."""

    def test_crp_cambia_csq_valido(self, diario, user_crp, socio_csq_alt, client):
        client.force_login(user_crp)
        resp = client.post(
            f"/diari/{diario.pk}/cambia-csq/",
            {"socio_pk": socio_csq_alt.pk},
        )
        assert resp.status_code == 302
        diario.refresh_from_db()
        assert diario.csq == socio_csq_alt

    def test_admin_cambia_csq_in_relazione_finale(self, diario, user_admin, socio_csq_alt, client):
        diario.stato = StatoDiario.RELAZIONE_FINALE
        diario.save()
        client.force_login(user_admin)
        resp = client.post(
            f"/diari/{diario.pk}/cambia-csq/",
            {"socio_pk": socio_csq_alt.pk},
        )
        assert resp.status_code == 302
        diario.refresh_from_db()
        assert diario.csq == socio_csq_alt

    def test_socio_capo_rifiutato_come_csq(self, diario, user_crp, socio_crp_alt, client):
        """Un Socio capo non può essere nominato Capo Squadriglia."""
        client.force_login(user_crp)
        resp = client.post(
            f"/diari/{diario.pk}/cambia-csq/",
            {"socio_pk": socio_crp_alt.pk},
        )
        assert resp.status_code == 200  # rende il form con errore
        diario.refresh_from_db()
        assert diario.csq != socio_crp_alt

    def test_socio_pk_mancante_non_aggiorna(self, diario, user_crp, socio_csq, client):
        client.force_login(user_crp)
        resp = client.post(f"/diari/{diario.pk}/cambia-csq/", {})
        assert resp.status_code == 200
        diario.refresh_from_db()
        assert diario.csq == socio_csq

    def test_context_puo_cambiare_csq_crp(self, diario, user_crp, client):
        client.force_login(user_crp)
        resp = client.get(f"/diari/{diario.pk}/")
        assert resp.context["puo_cambiare_csq"] is True
        assert resp.context["puo_cambiare_crp"] is False

    def test_context_puo_cambiare_csq_admin(self, diario, user_admin, client):
        client.force_login(user_admin)
        resp = client.get(f"/diari/{diario.pk}/")
        assert resp.context["puo_cambiare_csq"] is True
        assert resp.context["puo_cambiare_crp"] is True

    def test_context_cambia_csq_non_visibile_dopo_invio(self, diario, user_crp, client):
        diario.stato = StatoDiario.INVIATO
        diario.save()
        client.force_login(user_crp)
        # Il CRP non accede al diario inviato via la view
        resp = client.get(f"/diari/{diario.pk}/")
        assert resp.status_code == 200
        assert resp.context["puo_cambiare_csq"] is False


# ---------------------------------------------------------------------------
# Test CambiaCrpView
# ---------------------------------------------------------------------------

class TestCambiaCrpPermessi:
    """Solo admin/segreteria/iabr possono cambiare il CRP prima dell'invio."""

    def test_admin_accede_in_compilazione(self, diario, user_admin, client):
        client.force_login(user_admin)
        resp = client.get(f"/diari/{diario.pk}/cambia-crp/")
        assert resp.status_code == 200

    def test_admin_accede_in_relazione_finale(self, diario, user_admin, client):
        diario.stato = StatoDiario.RELAZIONE_FINALE
        diario.save()
        client.force_login(user_admin)
        resp = client.get(f"/diari/{diario.pk}/cambia-crp/")
        assert resp.status_code == 200

    def test_admin_non_accede_dopo_invio(self, diario, user_admin, client):
        diario.stato = StatoDiario.INVIATO
        diario.save()
        client.force_login(user_admin)
        resp = client.get(f"/diari/{diario.pk}/cambia-crp/")
        assert resp.status_code == 403

    def test_crp_non_puo_cambiare_crp(self, diario, user_crp, client):
        client.force_login(user_crp)
        resp = client.get(f"/diari/{diario.pk}/cambia-crp/")
        assert resp.status_code == 403

    def test_csq_non_puo_cambiare_crp(self, diario, user_csq, client):
        client.force_login(user_csq)
        resp = client.get(f"/diari/{diario.pk}/cambia-crp/")
        assert resp.status_code == 403


class TestCambiaCrpPost:
    """Il POST aggiorna diario.crp se i dati sono validi."""

    def test_admin_cambia_crp_valido(self, diario, user_admin, socio_crp_alt, client):
        client.force_login(user_admin)
        resp = client.post(
            f"/diari/{diario.pk}/cambia-crp/",
            {"socio_pk": socio_crp_alt.pk},
        )
        assert resp.status_code == 302
        diario.refresh_from_db()
        assert diario.crp == socio_crp_alt

    def test_socio_ragazzo_rifiutato_come_crp(self, diario, user_admin, socio_csq_alt, client):
        """Un Socio ragazzo non può essere nominato Capo Reparto."""
        client.force_login(user_admin)
        resp = client.post(
            f"/diari/{diario.pk}/cambia-crp/",
            {"socio_pk": socio_csq_alt.pk},
        )
        assert resp.status_code == 200
        diario.refresh_from_db()
        assert diario.crp != socio_csq_alt

    def test_socio_pk_mancante_non_aggiorna(self, diario, user_admin, socio_crp, client):
        client.force_login(user_admin)
        resp = client.post(f"/diari/{diario.pk}/cambia-crp/", {})
        assert resp.status_code == 200
        diario.refresh_from_db()
        assert diario.crp == socio_crp


# ---------------------------------------------------------------------------
# Test CambiaCrpRepartoView
# ---------------------------------------------------------------------------

class TestCambiaCrpReparto:
    """La view bulk aggiorna tutti i diari non inviati del reparto."""

    def test_admin_accede_alla_pagina(self, diario, user_admin, client):
        reparto_pk = diario.squadriglia.reparto_id
        client.force_login(user_admin)
        resp = client.get(f"/diari/reparto/{reparto_pk}/cambia-crp/")
        assert resp.status_code == 200
        assert diario in list(resp.context["diari"])

    def test_crp_non_accede(self, diario, user_crp, client):
        reparto_pk = diario.squadriglia.reparto_id
        client.force_login(user_crp)
        resp = client.get(f"/diari/reparto/{reparto_pk}/cambia-crp/")
        assert resp.status_code == 403

    def test_bulk_aggiorna_diari_non_inviati(self, diario, user_admin, socio_crp_alt, client):
        reparto_pk = diario.squadriglia.reparto_id
        client.force_login(user_admin)
        resp = client.post(
            f"/diari/reparto/{reparto_pk}/cambia-crp/",
            {"socio_pk": socio_crp_alt.pk},
        )
        assert resp.status_code == 302
        diario.refresh_from_db()
        assert diario.crp == socio_crp_alt

    def test_bulk_non_tocca_diari_inviati(
        self, db, edizione, squadriglia, socio_csq, socio_crp, socio_crp_alt, user_admin, client
    ):
        """I diari già inviati non vengono modificati dal bulk change."""
        diario_inviato = Diario.objects.create(
            edizione=edizione,
            squadriglia=squadriglia,
            csq=socio_csq,
            crp=socio_crp,
            stato=StatoDiario.INVIATO,
        )
        reparto_pk = squadriglia.reparto_id
        client.force_login(user_admin)
        client.post(
            f"/diari/reparto/{reparto_pk}/cambia-crp/",
            {"socio_pk": socio_crp_alt.pk},
        )
        diario_inviato.refresh_from_db()
        assert diario_inviato.crp == socio_crp  # non modificato

    def test_bulk_aggiorna_piu_diari_dello_stesso_reparto(
        self, db, edizione, reparto, socio_csq, socio_csq_alt, socio_crp, socio_crp_alt,
        user_admin, client
    ):
        """Tutti i diari non inviati del reparto vengono aggiornati."""
        from apps.org.models import Squadriglia

        sq2 = Squadriglia.objects.create(nome="Leoni", reparto=reparto)
        d1 = Diario.objects.create(
            edizione=edizione, squadriglia=sq2, csq=socio_csq,
            crp=socio_crp, stato=StatoDiario.IN_COMPILAZIONE,
        )
        d2 = Diario.objects.create(
            edizione=edizione,
            squadriglia=Squadriglia.objects.create(nome="Lupi", reparto=reparto),
            csq=socio_csq_alt, crp=socio_crp, stato=StatoDiario.RELAZIONE_FINALE,
        )
        client.force_login(user_admin)
        client.post(
            f"/diari/reparto/{reparto.pk}/cambia-crp/",
            {"socio_pk": socio_crp_alt.pk},
        )
        d1.refresh_from_db()
        d2.refresh_from_db()
        assert d1.crp == socio_crp_alt
        assert d2.crp == socio_crp_alt

    def test_pagina_vuota_se_nessun_diario_modificabile(
        self, db, reparto, user_admin, client
    ):
        """Pagina accessibile anche se non ci sono diari modificabili."""
        resp = client.get(f"/diari/reparto/{reparto.pk}/cambia-crp/")
        client.force_login(user_admin)
        resp = client.get(f"/diari/reparto/{reparto.pk}/cambia-crp/")
        assert resp.status_code == 200
        assert list(resp.context["diari"]) == []
