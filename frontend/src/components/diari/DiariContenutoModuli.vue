<script setup lang="ts">
/**
 * Contenuto dei moduli 1–6 nel dettaglio del diario (sola lettura): riepilogo di ciò che è
 * compilato, con il link "Compila"/"Visualizza" alla pagina del modulo. La relazione finale
 * arriva dall'API solo a chi può vederla (mai al Capo Squadriglia).
 */
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import IconaBs from '@/components/IconaBs.vue'
import DiariAllegatiModulo from '@/components/diari/DiariAllegatiModulo.vue'
import {
  COLORE_ESITO_SPECIALITA,
  ETICHETTE_ESITO_SPECIALITA,
  ETICHETTE_RUOLO_SQ,
  ETICHETTE_SENTIERO,
  formattaData,
  type DiarioDettaglio,
} from '@/components/diari/diari'

const props = defineProps<{ diario: DiarioDettaglio }>()
defineEmits<{ aggiorna: [] }>()

const d = computed(() => props.diario)
const puoModificare = computed(() => Boolean(d.value.permessi?.puo_modificare_moduli))
const puoRelazione = computed(() => Boolean(d.value.permessi?.puo_modificare_relazione))
const vedeRelazione = computed(() => d.value.stato_moduli?.relazione_finale != null)
const impresa = (n: number) => d.value.imprese.find((i) => i.numero === n) ?? null
const imprese = computed(() => [1, 2].map((n) => ({ numero: n, dati: impresa(n) })))
const prima = (n: number) => (n === 1 ? '1ª Impresa' : '2ª Impresa')
const siNo = (v: boolean | null | undefined) =>
  v === true ? 'Sì' : v === false ? 'No' : 'Non indicato'
const statiPrimaRelazione = new Set(['non_iniziato', 'in_compilazione'])
</script>

<template>
  <div class="d-grid gap-5">
    <!-- Modulo 1 -->
    <section class="card" aria-labelledby="mod-1">
      <div class="card-header d-flex flex-row flex-wrap align-items-center gap-3">
        <h2 id="mod-1" class="h6 mb-0">
          <span class="fg-2">Modulo 1</span> · Anagrafica squadriglia
        </h2>
        <RouterLink
          v-if="puoModificare"
          :to="`/diari/${d.id}/anagrafica`"
          class="btn btn-outline btn-sm theme-primary ms-auto"
          >Compila</RouterLink
        >
      </div>
      <div v-if="d.anagrafica" class="card-body small">
        <dl class="row g-3 mb-0">
          <div class="col-12 md:col-4">
            <dt>Capo Reparto</dt>
            <dd class="mb-0">{{ d.anagrafica.crp_cognome }} {{ d.anagrafica.crp_nome }}</dd>
          </div>
          <div class="col-12 md:col-4">
            <dt>Email Capo Reparto</dt>
            <dd class="mb-0 text-break">{{ d.anagrafica.crp_email || '—' }}</dd>
          </div>
          <div class="col-12 md:col-4">
            <dt>Cellulare Capo Reparto</dt>
            <dd class="mb-0">{{ d.anagrafica.crp_cell || '—' }}</dd>
          </div>
          <template v-if="d.anagrafica.csq_nome || d.anagrafica.csq_cognome">
            <div class="col-12 md:col-4">
              <dt>Capo Squadriglia</dt>
              <dd class="mb-0">{{ d.anagrafica.csq_cognome }} {{ d.anagrafica.csq_nome }}</dd>
            </div>
            <div class="col-12 md:col-4">
              <dt>Email Capo Squadriglia</dt>
              <dd class="mb-0 text-break">{{ d.anagrafica.csq_email || '—' }}</dd>
            </div>
            <div class="col-12 md:col-4">
              <dt>Cellulare Capo Squadriglia</dt>
              <dd class="mb-0">{{ d.anagrafica.csq_cell || '—' }}</dd>
            </div>
          </template>
          <div class="col-12 md:col-4">
            <dt>Specialità</dt>
            <dd class="mb-0">{{ d.anagrafica.specialita || '—' }}</dd>
          </div>
          <div class="col-12 md:col-4">
            <dt>Tipo</dt>
            <dd class="mb-0">{{ d.tipo_display }}</dd>
          </div>
          <div class="col-12 md:col-4">
            <dt>Partecipa all'evento Guidoncini Verdi</dt>
            <dd class="mb-0">{{ d.anagrafica.partecipa_evento ? 'Sì' : 'No' }}</dd>
          </div>
        </dl>
        <div
          v-if="
            d.anagrafica.desc_prima_impresa ||
            d.anagrafica.desc_seconda_impresa ||
            d.anagrafica.tecniche
          "
          class="mt-5 pt-5 border-top"
        >
          <p class="text-uppercase fw-semibold fg-2 small mb-2">Precompilazione da import</p>
          <p v-if="d.anagrafica.desc_prima_impresa" class="mb-2">
            <strong>1ª impresa:</strong> {{ d.anagrafica.desc_prima_impresa }}
          </p>
          <p v-if="d.anagrafica.desc_seconda_impresa" class="mb-2">
            <strong>2ª impresa:</strong> {{ d.anagrafica.desc_seconda_impresa }}
          </p>
          <p v-if="d.anagrafica.tecniche" class="mb-0">
            <strong>Tecniche:</strong> {{ d.anagrafica.tecniche }}
          </p>
        </div>
      </div>
      <div v-else class="card-body fg-2 fst-italic">Non ancora compilato.</div>
    </section>

    <!-- Modulo 2 -->
    <section class="card" aria-labelledby="mod-2">
      <div class="card-header d-flex flex-row flex-wrap align-items-center gap-3">
        <h2 id="mod-2" class="h6 mb-0">
          <span class="fg-2">Modulo 2</span> · Presentazione squadriglia
        </h2>
        <RouterLink
          v-if="puoModificare"
          :to="`/diari/${d.id}/presentazione`"
          class="btn btn-outline btn-sm theme-primary ms-auto"
          >Compila</RouterLink
        >
      </div>
      <div v-if="d.presentazione" class="card-body small">
        <p class="mb-3 plancia-diari-testo">{{ d.presentazione.cosa_sappiamo_fare }}</p>
        <p class="fw-semibold mb-2">Membri ({{ d.presentazione.membri.length }})</p>
        <ul class="list-unstyled d-flex flex-wrap gap-2 mb-0">
          <li
            v-for="m in d.presentazione.membri"
            :key="m.id"
            class="badge theme-secondary fw-normal"
          >
            {{ m.nome }} — {{ ETICHETTE_RUOLO_SQ[m.ruolo] ?? m.ruolo }} —
            {{ ETICHETTE_SENTIERO[m.sentiero] ?? m.sentiero }}
          </li>
        </ul>
      </div>
      <div v-else class="card-body fg-2 fst-italic">Non ancora compilato.</div>
    </section>

    <!-- Moduli 3 e 4 -->
    <section
      v-for="imp in imprese"
      :key="imp.numero"
      class="card"
      :aria-labelledby="`mod-${imp.numero + 2}`"
    >
      <div class="card-header d-flex flex-row flex-wrap align-items-center gap-3">
        <h2 :id="`mod-${imp.numero + 2}`" class="h6 mb-0">
          <span class="fg-2">Modulo {{ imp.numero + 2 }}</span> · {{ prima(imp.numero) }}
          <span
            v-if="imp.numero === 2 && !d.stato_moduli?.impresa_2_obbligatoria"
            class="badge theme-secondary ms-1"
            >facoltativa</span
          >
        </h2>
        <RouterLink
          v-if="puoModificare"
          :to="`/diari/${d.id}/imprese/${imp.numero}`"
          class="btn btn-outline btn-sm theme-primary ms-auto"
          >Compila</RouterLink
        >
      </div>
      <div v-if="imp.dati" class="card-body small">
        <h3 class="h6 mb-1">{{ imp.dati.titolo || '(senza titolo)' }}</h3>
        <p v-if="imp.dati.data_inizio" class="fg-2 mb-3">
          {{ formattaData(imp.dati.data_inizio)
          }}<template v-if="imp.dati.data_fine"> – {{ formattaData(imp.dati.data_fine) }}</template>
        </p>
        <div class="row g-5">
          <div v-if="imp.dati.perche" class="col-12 md:col-4">
            <p class="text-uppercase fw-semibold fg-2 mb-1">Perché</p>
            <p class="mb-0 plancia-diari-testo">{{ imp.dati.perche }}</p>
          </div>
          <div v-if="imp.dati.come" class="col-12 md:col-4">
            <p class="text-uppercase fw-semibold fg-2 mb-1">Come</p>
            <p class="mb-0 plancia-diari-testo">{{ imp.dati.come }}</p>
          </div>
          <div v-if="imp.dati.cosa" class="col-12 md:col-4">
            <p class="text-uppercase fw-semibold fg-2 mb-1">Cosa abbiamo fatto</p>
            <p class="mb-0 plancia-diari-testo">{{ imp.dati.cosa }}</p>
          </div>
          <div v-if="imp.dati.posti_azione.length" class="col-12 md:col-6">
            <p class="text-uppercase fw-semibold fg-2 mb-1">Posti d'azione</p>
            <ul class="list-unstyled mb-0">
              <li v-for="p in imp.dati.posti_azione" :key="p.id">
                <IconaBs nome="geo-alt" class="fg-primary me-1" /><template v-if="p.chi"
                  ><strong>{{ p.chi }}</strong> — </template
                >{{ p.cosa }}
              </li>
            </ul>
          </div>
          <div
            v-if="imp.dati.specialita.length || imp.dati.brevetti.length"
            class="col-12 md:col-6"
          >
            <p class="text-uppercase fw-semibold fg-2 mb-1">Specialità e brevetti</p>
            <ul class="list-unstyled mb-0">
              <li
                v-for="e in [...imp.dati.specialita, ...imp.dati.brevetti]"
                :key="`${e.tipo}-${e.id}`"
                class="mb-1"
              >
                <span
                  class="badge me-1"
                  :class="`theme-${COLORE_ESITO_SPECIALITA[e.stato] ?? 'secondary'}`"
                  >{{ ETICHETTE_ESITO_SPECIALITA[e.stato] ?? e.stato }}</span
                >
                <IconaBs
                  v-if="e.tipo === 'brevetto'"
                  nome="award"
                  class="fg-warning me-1"
                  etichetta="Brevetto"
                />
                <template v-if="e.chi"
                  ><strong>{{ e.chi }}</strong> — </template
                >{{ e.nome }}
              </li>
            </ul>
          </div>
          <div v-if="imp.dati.link_esterno" class="col-12">
            <a :href="imp.dati.link_esterno" target="_blank" rel="noopener"
              ><IconaBs nome="link-45deg" class="me-1" />Link esterno</a
            >
          </div>
        </div>
        <DiariAllegatiModulo
          :diario="d"
          :modulo="`impresa_${imp.numero}`"
          @eliminato="$emit('aggiorna')"
        />
      </div>
      <div v-else class="card-body fg-2 fst-italic">Non ancora compilato.</div>
    </section>

    <!-- Modulo 5 -->
    <section class="card" aria-labelledby="mod-5">
      <div class="card-header d-flex flex-row flex-wrap align-items-center gap-3">
        <h2 id="mod-5" class="h6 mb-0">
          <span class="fg-2">Modulo 5</span> · Missione
          <span v-if="!d.stato_moduli?.missione_obbligatoria" class="badge theme-secondary ms-1"
            >facoltativa</span
          >
        </h2>
        <RouterLink
          v-if="puoModificare"
          :to="`/diari/${d.id}/missione`"
          class="btn btn-outline btn-sm theme-primary ms-auto"
          >Compila</RouterLink
        >
      </div>
      <div v-if="d.missione" class="card-body small">
        <h3 class="h6 mb-1">{{ d.missione.titolo || '(senza titolo)' }}</h3>
        <p v-if="d.missione.data" class="fg-2 mb-3">{{ formattaData(d.missione.data) }}</p>
        <template v-if="d.missione.descrizione_svolgimento">
          <p class="text-uppercase fw-semibold fg-2 mb-1">Svolgimento</p>
          <p class="mb-3 plancia-diari-testo">{{ d.missione.descrizione_svolgimento }}</p>
        </template>
        <DiariAllegatiModulo :diario="d" modulo="missione" @eliminato="$emit('aggiorna')" />
      </div>
      <div v-else class="card-body fg-2 fst-italic">Non ancora compilato.</div>
    </section>

    <!-- Modulo 6: solo a chi l'API la mostra -->
    <section v-if="vedeRelazione" class="card" aria-labelledby="mod-6">
      <div class="card-header d-flex flex-row flex-wrap align-items-center gap-3">
        <h2 id="mod-6" class="h6 mb-0">
          <span class="fg-2">Modulo 6</span> · Relazione finale del Capo Reparto
        </h2>
        <RouterLink
          v-if="puoRelazione"
          :to="`/diari/${d.id}/relazione-finale`"
          class="btn btn-outline btn-sm theme-primary ms-auto"
          >Compila</RouterLink
        >
        <RouterLink
          v-else-if="d.relazione_finale"
          :to="`/diari/${d.id}/relazione-finale`"
          class="btn btn-outline btn-sm theme-secondary ms-auto"
          >Visualizza</RouterLink
        >
      </div>
      <div v-if="d.relazione_finale" class="card-body small">
        <div class="row g-5">
          <div class="col-12 md:col-6">
            <p class="text-uppercase fw-semibold fg-2 mb-1">Specialità conquistata?</p>
            <p class="mb-0">{{ siNo(d.relazione_finale.specialita_conquistata) }}</p>
          </div>
          <div v-if="d.relazione_finale.sintesi_impresa_1" class="col-12 md:col-6">
            <p class="text-uppercase fw-semibold fg-2 mb-1">Sintesi 1ª impresa</p>
            <p class="mb-0 plancia-diari-testo">{{ d.relazione_finale.sintesi_impresa_1 }}</p>
          </div>
          <div v-if="d.relazione_finale.sintesi_impresa_2" class="col-12 md:col-6">
            <p class="text-uppercase fw-semibold fg-2 mb-1">Sintesi 2ª impresa</p>
            <p class="mb-0 plancia-diari-testo">{{ d.relazione_finale.sintesi_impresa_2 }}</p>
          </div>
          <div v-if="d.relazione_finale.sintesi_missione" class="col-12 md:col-6">
            <p class="text-uppercase fw-semibold fg-2 mb-1">Sintesi missione</p>
            <p class="mb-0 plancia-diari-testo">{{ d.relazione_finale.sintesi_missione }}</p>
          </div>
          <div v-if="d.relazione_finale.considerazioni" class="col-12">
            <p class="text-uppercase fw-semibold fg-2 mb-1">Considerazioni finali</p>
            <p class="mb-0 plancia-diari-testo">{{ d.relazione_finale.considerazioni }}</p>
          </div>
        </div>
      </div>
      <div v-else-if="statiPrimaRelazione.has(d.stato)" class="card-body fg-2 fst-italic">
        Disponibile dopo che il Capo Squadriglia ha inviato la propria parte.
      </div>
      <div v-else class="card-body fg-2 fst-italic">Non ancora compilato.</div>
    </section>
  </div>
</template>

<style scoped>
.plancia-diari-testo {
  white-space: pre-line;
}
dt {
  font-weight: 600;
}
</style>
