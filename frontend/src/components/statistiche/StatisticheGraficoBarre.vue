<script setup lang="ts">
/**
 * Grafico a barre orizzontali (anche impilate) in HTML/CSS, senza librerie: si adatta alla
 * larghezza (iPhone compreso), usa i colori del tema e ha sempre la tabella dei dati come
 * alternativa accessibile (le barre sono nascoste agli screen reader).
 */
import { computed, useId } from 'vue'

import {
  descriviRiga,
  massimo,
  segmenti,
  totaleRiga,
  type RigaGrafico,
  type Serie,
} from '@/components/statistiche/grafici'

const props = withDefaults(
  defineProps<{
    titolo: string
    serie: Serie[]
    righe: RigaGrafico[]
    /** Intestazione della prima colonna della tabella dati. */
    etichettaRiga?: string
    legenda?: boolean
  }>(),
  { etichettaRiga: 'Voce', legenda: true },
)

const id = useId()
const max = computed(() => massimo(props.righe, props.serie))
const righe = computed(() =>
  props.righe.map((r) => ({
    ...r,
    totale: totaleRiga(r, props.serie),
    segmenti: segmenti(r, props.serie, max.value),
    descrizione: descriviRiga(r, props.serie),
  })),
)
const piuSerie = computed(() => props.serie.length > 1)
</script>

<template>
  <figure class="plancia-grafico mb-0" :aria-labelledby="`${id}-titolo`">
    <figcaption :id="`${id}-titolo`" class="h6 mb-3">{{ titolo }}</figcaption>

    <ul v-if="legenda && piuSerie" class="plancia-grafico__legenda list-unstyled d-flex flex-wrap gap-3 small mb-3" aria-hidden="true">
      <li v-for="s in serie" :key="s.chiave" class="d-flex align-items-center gap-1">
        <span class="plancia-grafico__campione" :style="{ background: s.colore }" />{{ s.etichetta }}
      </li>
    </ul>

    <div class="plancia-grafico__righe" aria-hidden="true">
      <div v-for="r in righe" :key="r.etichetta" class="plancia-grafico__riga" :title="r.descrizione">
        <span class="plancia-grafico__etichetta small">{{ r.etichetta }}</span>
        <span class="plancia-grafico__traccia">
          <span
            v-for="s in r.segmenti"
            :key="s.chiave"
            class="plancia-grafico__segmento"
            :style="{ width: `${s.larghezza}%`, background: s.colore }"
            :title="`${s.etichetta}: ${s.valore}`"
          />
          <span class="plancia-grafico__totale small">{{ r.totale }}</span>
        </span>
      </div>
      <p v-if="!righe.length" class="small fg-2 mb-0">Nessun dato.</p>
    </div>

    <details class="mt-3 small">
      <summary>Dati del grafico in tabella</summary>
      <div class="table-responsive mt-2">
        <table class="table table-sm mb-0">
          <caption class="visually-hidden">{{ titolo }}</caption>
          <thead>
            <tr>
              <th scope="col">{{ etichettaRiga }}</th>
              <th v-for="s in serie" :key="s.chiave" scope="col" class="text-end">{{ s.etichetta }}</th>
              <th v-if="piuSerie" scope="col" class="text-end">Totale</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in righe" :key="r.etichetta">
              <th scope="row" class="fw-normal">{{ r.etichetta }}</th>
              <td v-for="s in serie" :key="s.chiave" class="text-end">{{ r.valori[s.chiave] ?? 0 }}</td>
              <td v-if="piuSerie" class="text-end">{{ r.totale }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </details>
  </figure>
</template>

<style scoped>
.plancia-grafico__campione {
  display: inline-block;
  width: 0.85rem;
  height: 0.85rem;
  border-radius: 0.2rem;
}
.plancia-grafico__righe {
  display: grid;
  gap: 0.5rem;
}
.plancia-grafico__riga {
  display: grid;
  grid-template-columns: minmax(6rem, 11rem) 1fr;
  align-items: center;
  gap: 0.75rem;
}
/* Su schermi stretti l'etichetta va sopra la barra */
@media (max-width: 575.98px) {
  .plancia-grafico__riga {
    grid-template-columns: 1fr;
    gap: 0.15rem;
  }
}
.plancia-grafico__etichetta {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.plancia-grafico__traccia {
  display: flex;
  align-items: center;
  min-height: 1.25rem;
  /* spazio per il numero del totale in fondo */
  padding-right: 2.5rem;
  position: relative;
}
.plancia-grafico__segmento {
  height: 1.25rem;
  min-width: 3px;
  flex-shrink: 0;
}
.plancia-grafico__segmento + .plancia-grafico__segmento {
  border-left: 2px solid var(--bs-bg-body, #fff);
}
.plancia-grafico__segmento:first-child {
  border-radius: 0.25rem 0 0 0.25rem;
}
.plancia-grafico__segmento:nth-last-child(2) {
  border-radius: 0 0.25rem 0.25rem 0;
}
.plancia-grafico__segmento:first-child:nth-last-child(2) {
  border-radius: 0.25rem;
}
.plancia-grafico__totale {
  margin-left: 0.4rem;
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}
</style>
