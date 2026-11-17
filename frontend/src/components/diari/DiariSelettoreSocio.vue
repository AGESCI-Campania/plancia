<script setup lang="ts">
/**
 * Selettore di un Socio con ricerca (`GET /org/soci?q=&categoria=`), al posto di Tom Select:
 * combobox ARIA con elenco di suggerimenti, frecce/Invio/Esc da tastiera, almeno 2 caratteri.
 */
import { computed, onBeforeUnmount, ref, useId, watch } from 'vue'

import { api, ErroreApi } from '@/api/http'
import IconaBs from '@/components/IconaBs.vue'
import type { Socio } from '@/components/diari/diari'

const props = withDefaults(
  defineProps<{
    etichetta: string
    categoria?: 'capo' | 'ragazzo' | ''
    aiuto?: string
    errori?: string[]
    /** Soci da non proporre (es. il referente attuale). */
    escludi?: number[]
  }>(),
  { categoria: '', aiuto: '', errori: () => [], escludi: () => [] },
)
const socio = defineModel<Socio | null>({ default: null })

const id = useId()
const testo = ref('')
const risultati = ref<Socio[]>([])
const aperto = ref(false)
const attivo = ref(-1)
const inCorso = ref(false)
const erroreRicerca = ref('')
let timer: ReturnType<typeof setTimeout> | undefined
let controllore: AbortController | undefined

const visibili = computed(() => risultati.value.filter((s) => !props.escludi.includes(s.id)))
const idAttivo = computed(() => (attivo.value >= 0 ? `${id}-opz-${attivo.value}` : undefined))
const descrittori = computed(
  () =>
    [props.aiuto ? `${id}-aiuto` : '', props.errori.length ? `${id}-errori` : '']
      .filter(Boolean)
      .join(' ') || undefined,
)

async function cerca(q: string): Promise<void> {
  controllore?.abort()
  controllore = new AbortController()
  inCorso.value = true
  erroreRicerca.value = ''
  try {
    risultati.value = await api.get<Socio[]>(
      '/org/soci',
      { q, categoria: props.categoria || undefined },
      controllore.signal,
    )
    attivo.value = visibili.value.length ? 0 : -1
    aperto.value = true
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return
    erroreRicerca.value = e instanceof ErroreApi ? e.message : 'Ricerca non riuscita.'
    risultati.value = []
    aperto.value = true
  } finally {
    inCorso.value = false
  }
}

watch(testo, (valore) => {
  clearTimeout(timer)
  if (socio.value && valore !== socio.value.label) socio.value = null
  const q = valore.trim()
  if (q.length < 2) {
    risultati.value = []
    aperto.value = false
    return
  }
  if (socio.value) return
  timer = setTimeout(() => void cerca(q), 250)
})

onBeforeUnmount(() => {
  clearTimeout(timer)
  controllore?.abort()
})

function scegli(s: Socio): void {
  socio.value = s
  testo.value = s.label
  aperto.value = false
}

function svuota(): void {
  socio.value = null
  testo.value = ''
}

function tasto(evento: KeyboardEvent): void {
  const n = visibili.value.length
  if (evento.key === 'ArrowDown') {
    evento.preventDefault()
    if (!aperto.value && n) aperto.value = true
    else if (n) attivo.value = (attivo.value + 1) % n
  } else if (evento.key === 'ArrowUp') {
    evento.preventDefault()
    if (n) attivo.value = (attivo.value - 1 + n) % n
  } else if (evento.key === 'Enter') {
    if (aperto.value && attivo.value >= 0 && visibili.value[attivo.value]) {
      evento.preventDefault()
      scegli(visibili.value[attivo.value]!)
    }
  } else if (evento.key === 'Escape') {
    if (aperto.value) {
      // Chiude solo i suggerimenti, non la finestra che contiene il campo
      evento.preventDefault()
      evento.stopPropagation()
      aperto.value = false
    }
  }
}

function chiudiDopo(): void {
  // Lascia arrivare il clic sul suggerimento prima di chiudere l'elenco
  setTimeout(() => (aperto.value = false), 150)
}
</script>

<template>
  <div class="mb-5 position-relative">
    <label :for="id" class="form-label">{{ etichetta }}</label>
    <div class="d-flex gap-3 align-items-center">
      <input
        :id="id"
        v-model="testo"
        type="search"
        class="form-control"
        :class="{ 'is-invalid': errori.length }"
        role="combobox"
        autocomplete="off"
        aria-autocomplete="list"
        :aria-expanded="aperto"
        :aria-controls="`${id}-elenco`"
        :aria-activedescendant="idAttivo"
        :aria-describedby="descrittori"
        placeholder="Cerca per nome, cognome, codice o gruppo…"
        @keydown="tasto"
        @blur="chiudiDopo"
        @focus="aperto = visibili.length > 0 && !socio"
      />
      <span v-if="inCorso" class="spinner-border spinner-sm" role="status">
        <span class="visually-hidden">Ricerca in corso…</span>
      </span>
      <button
        v-if="socio"
        type="button"
        class="btn btn-text btn-sm theme-secondary"
        @click="svuota"
      >
        <IconaBs nome="x-lg" etichetta="Annulla la scelta" />
      </button>
    </div>
    <ul
      v-show="aperto"
      :id="`${id}-elenco`"
      class="list-group shadow position-absolute w-100 plancia-diari-suggerimenti"
      role="listbox"
      :aria-label="`Suggerimenti per ${etichetta}`"
    >
      <li
        v-for="(s, i) in visibili"
        :id="`${id}-opz-${i}`"
        :key="s.id"
        class="list-group-item list-group-item-action"
        :class="{ active: i === attivo }"
        role="option"
        :aria-selected="i === attivo"
        @mousedown.prevent="scegli(s)"
      >
        {{ s.label }}
      </li>
      <li v-if="!visibili.length" class="list-group-item fg-2" role="presentation">
        {{ erroreRicerca || 'Nessun risultato.' }}
      </li>
    </ul>
    <div v-if="aiuto" :id="`${id}-aiuto`" class="form-text">{{ aiuto }}</div>
    <div v-if="errori.length" :id="`${id}-errori`" class="invalid-feedback d-block">
      <div v-for="e in errori" :key="e">{{ e }}</div>
    </div>
  </div>
</template>

<style scoped>
.plancia-diari-suggerimenti {
  z-index: 20;
  max-height: 16rem;
  overflow-y: auto;
  margin-top: 0.25rem;
}
.plancia-diari-suggerimenti [role='option'] {
  cursor: pointer;
}
</style>
