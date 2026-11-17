<script setup lang="ts">
// Modulo 1 — Anagrafica: squadriglia, Capo Reparto, Capo Squadriglia, specialità, note da import.
import { computed, useId } from 'vue'

import type { components } from '@/api/schema'
import CampoModulo from '@/components/moduli/CampoModulo.vue'
import PaginaModulo from '@/components/moduli/PaginaModulo.vue'
import { usePaginaModulo } from '@/composables/paginaModulo'
import { useSessioneStore } from '@/stores/sessione'

type Anagrafica = components['schemas']['AnagraficaSchema']

const props = defineProps<{ id: string }>()
const pagina = usePaginaModulo<Anagrafica>(props.id, 'anagrafica')
const { diario, opzioni, modulo, solaLettura } = pagina
const { dati } = modulo
// Alias non nullo per il template (usato solo dentro `v-if="dati"`)
const d = computed(() => dati.value as Anagrafica)
const sessione = useSessioneStore()
// Le email dei referenti le cambia solo lo staff (il backend ignora le altre modifiche)
const staff = computed(() => Boolean(sessione.me?.is_staff_plancia || sessione.me?.is_superuser))
const specialita = computed(() => (opzioni.value?.specialita_squadriglia ?? []).map((s) => ({ valore: s, etichetta: s })))
const idEvento = useId()
const REFERENTI = [
  { titolo: 'Capo Reparto', cognome: 'crp_cognome', nome: 'crp_nome', cell: 'crp_cell', email: 'crp_email' },
  { titolo: 'Capo Squadriglia', cognome: 'csq_cognome', nome: 'csq_nome', cell: 'csq_cell', email: 'csq_email' },
] as const
</script>

<template>
  <PaginaModulo
    :diario-id="id"
    chiave="anagrafica"
    :diario="diario"
    :errore-diario="pagina.errore.value"
    :in-corso-diario="pagina.inCorso.value"
    :copia-locale="pagina.copiaLocale.value"
    :modulo="modulo"
    :sola-lettura="solaLettura"
    :avviso-sola-lettura="pagina.avvisoSolaLettura.value"
    descrizione="I dati di contatto sono visibili solo ai Capi Reparto e allo staff."
    @ricarica-diario="pagina.ricaricaDiario()"
  >
    <template v-if="dati">
      <fieldset class="mb-6">
        <legend class="h5 border-bottom pb-2 mb-4">Squadriglia</legend>
        <div class="row g-4">
          <div class="col-12 md:col-6">
            <CampoModulo
              v-model="d.squadriglia_nome"
              etichetta="Nome squadriglia"
              segnaposto="es. Pantere"
              :maxlength="120"
              aiuto="Modifica il nome della squadriglia. Rinominerà anche le cartelle su Google Drive."
              :errori="modulo.erroriDi('squadriglia_nome')"
              :sola-lettura="solaLettura"
            />
          </div>
          <div class="col-12 md:col-6">
            <CampoModulo
              v-model="d.tipo_diario"
              tipo="select"
              etichetta="Tipo partecipazione"
              :opzioni="opzioni?.tipi_diario ?? []"
              aiuto="Nuovo: la squadriglia partecipa per la prima volta. Rinnovo: ha già conquistato la specialità."
              :errori="modulo.erroriDi('tipo_diario')"
              :sola-lettura="solaLettura"
            />
          </div>
        </div>
      </fieldset>

      <fieldset v-for="r in REFERENTI" :key="r.titolo" class="mb-6">
        <legend class="h5 border-bottom pb-2 mb-4">{{ r.titolo }}</legend>
        <div class="row g-4">
          <div class="col-12 md:col-4">
            <CampoModulo
              v-model="d[r.cognome]"
              etichetta="Cognome"
              segnaposto="Cognome"
              :maxlength="120"
              autocomplete="off"
              :errori="modulo.erroriDi(r.cognome)"
              :sola-lettura="solaLettura"
            />
          </div>
          <div class="col-12 md:col-4">
            <CampoModulo
              v-model="d[r.nome]"
              etichetta="Nome"
              segnaposto="Nome"
              :maxlength="120"
              :errori="modulo.erroriDi(r.nome)"
              :sola-lettura="solaLettura"
            />
          </div>
          <div class="col-12 md:col-4">
            <CampoModulo
              v-model="d[r.cell]"
              tipo="tel"
              etichetta="Cellulare"
              segnaposto="3xx xxxxxxx"
              :maxlength="30"
              :errori="modulo.erroriDi(r.cell)"
              :sola-lettura="solaLettura"
            />
          </div>
          <div class="col-12 md:col-6">
            <CampoModulo
              v-model="d[r.email]"
              tipo="email"
              etichetta="Email"
              segnaposto="email@esempio.it"
              :maxlength="254"
              :badge="staff ? '' : 'solo staff'"
              :errori="modulo.erroriDi(r.email)"
              :sola-lettura="solaLettura || !staff"
            />
          </div>
        </div>
      </fieldset>

      <fieldset class="mb-6">
        <legend class="h5 border-bottom pb-2 mb-4">Specialità e partecipazione</legend>
        <div class="row g-4 align-items-end">
          <div class="col-12 md:col-6">
            <CampoModulo
              v-model="d.specialita"
              tipo="select"
              etichetta="Specialità di squadriglia"
              vuota="— Scegli —"
              :opzioni="specialita"
              :errori="modulo.erroriDi('specialita')"
              :sola-lettura="solaLettura"
            />
          </div>
          <div class="col-12 md:col-6">
            <div class="form-field">
              <input :id="idEvento" v-model="d.partecipa_evento" type="checkbox" class="check" :disabled="solaLettura" />
              <label :for="idEvento">Partecipa all'evento Guidoncini Verdi</label>
            </div>
            <div v-for="e in modulo.erroriDi('partecipa_evento')" :key="e" class="invalid-feedback">{{ e }}</div>
          </div>
        </div>
      </fieldset>

      <fieldset class="mb-4">
        <legend class="h5 border-bottom pb-2 mb-2">
          Note da import (precompilazione)
          <span class="badge theme-secondary fw-normal small ms-1">sola lettura</span>
        </legend>
        <p class="fg-2 small mb-4">Dati precompilati dall'import Jotform. Non modificabili.</p>
        <div class="row g-4">
          <div class="col-12">
            <CampoModulo v-model="d.desc_prima_impresa" tipo="textarea" :righe="3" etichetta="Descrizione 1ª impresa (da import)" sola-lettura />
          </div>
          <div class="col-12">
            <CampoModulo v-model="d.desc_seconda_impresa" tipo="textarea" :righe="3" etichetta="Descrizione 2ª impresa (da import)" sola-lettura />
          </div>
          <div class="col-12">
            <CampoModulo v-model="d.tecniche" tipo="textarea" :righe="3" etichetta="Tecniche da acquisire (da import)" sola-lettura />
          </div>
        </div>
      </fieldset>
    </template>
  </PaginaModulo>
</template>
