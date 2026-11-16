<script setup lang="ts">
// Modulo 2 — Presentazione della squadriglia: cosa sappiamo fare e membri.
import { computed } from 'vue'

import type { components } from '@/api/schema'
import CampoModulo from '@/components/moduli/CampoModulo.vue'
import PaginaModulo from '@/components/moduli/PaginaModulo.vue'
import RigheRipetute from '@/components/moduli/RigheRipetute.vue'
import { nuovaRiga } from '@/composables/moduloDiario'
import { usePaginaModulo } from '@/composables/paginaModulo'

type Membro = Omit<components['schemas']['MembroSqSchema'], 'id'> & { id: number | null; _k?: string }
type Presentazione = { cosa_sappiamo_fare: string; membri: Membro[] }

const props = defineProps<{ id: string }>()
const pagina = usePaginaModulo<Presentazione>(props.id, 'presentazione', {
  // Una riga aggiunta e lasciata senza nome non si invia
  righeVuote: { membri: (r) => !String(r.nome ?? '').trim() },
})
const { diario, opzioni, modulo, solaLettura } = pagina
const { dati } = modulo
// Alias non nullo per il template (usato solo dentro `v-if="dati"`)
const d = computed(() => dati.value as Presentazione)
const nuovoMembro = (): Membro => nuovaRiga({ id: null, nome: '', ruolo: '', sentiero: 'non_specificato' })
</script>

<template>
  <PaginaModulo
    :diario-id="id"
    chiave="presentazione"
    :diario="diario"
    :errore-diario="pagina.errore.value"
    :in-corso-diario="pagina.inCorso.value"
    :modulo="modulo"
    :sola-lettura="solaLettura"
    :avviso-sola-lettura="pagina.avvisoSolaLettura.value"
    @ricarica-diario="pagina.ricaricaDiario()"
  >
    <template v-if="dati">
      <div class="mb-6">
        <CampoModulo
          v-model="d.cosa_sappiamo_fare"
          tipo="textarea"
          :righe="5"
          :maxlength="10000"
          etichetta="Cosa sappiamo fare"
          segnaposto="Descrivete le competenze e le attività che la vostra squadriglia sa fare meglio..."
          :errori="modulo.erroriDi('cosa_sappiamo_fare')"
          :sola-lettura="solaLettura"
        />
      </div>

      <fieldset class="mb-4">
        <legend class="h5 border-bottom pb-2 mb-2">Membri della squadriglia</legend>
        <p class="fg-2 small mb-4">Inserite il nome completo di ogni membro, il ruolo e la tappa del sentiero.</p>
        <RigheRipetute
          v-model="d.membri"
          :nuova="nuovoMembro"
          nome-riga="membro"
          etichetta-aggiungi="Aggiungi membro"
          messaggio-vuoto="Nessun membro inserito."
          :sola-lettura="solaLettura"
        >
          <template #default="{ riga }">
            <div class="col-12 md:col-6">
              <CampoModulo
                v-model="riga.nome"
                etichetta="Nome e cognome"
                segnaposto="Nome e cognome"
                :maxlength="120"
                :errori="modulo.erroriRiga('membri', riga).nome"
                :sola-lettura="solaLettura"
              />
            </div>
            <div class="col-12 sm:col-6 md:col-3">
              <CampoModulo
                v-model="riga.ruolo"
                tipo="select"
                etichetta="Ruolo in squadriglia"
                vuota="—"
                :opzioni="opzioni?.ruoli_squadriglia ?? []"
                :errori="modulo.erroriRiga('membri', riga).ruolo"
                :sola-lettura="solaLettura"
              />
            </div>
            <div class="col-12 sm:col-6 md:col-3">
              <CampoModulo
                v-model="riga.sentiero"
                tipo="select"
                etichetta="Tappa sentiero"
                :opzioni="opzioni?.sentieri ?? []"
                :errori="modulo.erroriRiga('membri', riga).sentiero"
                :sola-lettura="solaLettura"
              />
            </div>
          </template>
        </RigheRipetute>
      </fieldset>
    </template>
  </PaginaModulo>
</template>
