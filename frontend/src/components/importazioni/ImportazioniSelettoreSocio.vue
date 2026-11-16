<script setup lang="ts">
/**
 * Selettore di un Socio con ricerca lato server (`GET /org/soci?q=&categoria=`), al posto di
 * Tom Select. Combobox ARIA 1.2: input con lista di opzioni, frecce per scorrere, Invio per
 * scegliere, Esc per chiudere. `v-model` è il Socio scelto (o `null`).
 */
import { computed, onBeforeUnmount, ref, useId, watch } from 'vue'

import { api, ErroreApi } from '@/api/http'
import type { SocioAutocomplete } from '@/components/importazioni/importazioni'

const props = withDefaults(
  defineProps<{
    etichetta: string
    categoria?: string
    aiuto?: string
    minimoCaratteri?: number
    errori?: string[]
  }>(),
  { categoria: '', aiuto: 'Digita almeno 2 caratteri per cercare.', minimoCaratteri: 2, errori: () => [] },
)
const scelto = defineModel<SocioAutocomplete | null>({ default: null })

const id = useId()
const testo = ref(scelto.value?.label ?? '')
const opzioni = ref<SocioAutocomplete[]>([])
const aperta = ref(false)
const attiva = ref(-1)
const inCorso = ref(false)
const erroreRicerca = ref('')

let timer: ReturnType<typeof setTimeout> | undefined
let controllo: AbortController | undefined

const mostraLista = computed(() => aperta.value && testo.value.trim().length >= props.minimoCaratteri)
const idAttiva = computed(() => (attiva.value >= 0 ? `${id}-opz-${attiva.value}` : undefined))

watch(scelto, (s) => {
  if (s) testo.value = s.label
  else if (!aperta.value) testo.value = ''
})

async function cerca(q: string): Promise<void> {
  controllo?.abort()
  controllo = new AbortController()
  inCorso.value = true
  erroreRicerca.value = ''
  try {
    opzioni.value = await api.get<SocioAutocomplete[]>(
      '/org/soci',
      { q, categoria: props.categoria },
      controllo.signal,
    )
    attiva.value = opzioni.value.length ? 0 : -1
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return
    opzioni.value = []
    erroreRicerca.value = e instanceof ErroreApi ? e.message : 'Ricerca non riuscita.'
  } finally {
    inCorso.value = false
  }
}

function digitato(): void {
  if (scelto.value && testo.value !== scelto.value.label) scelto.value = null
  aperta.value = true
  clearTimeout(timer)
  const q = testo.value.trim()
  if (q.length < props.minimoCaratteri) {
    opzioni.value = []
    attiva.value = -1
    return
  }
  timer = setTimeout(() => void cerca(q), 250)
}

function scegli(socio: SocioAutocomplete): void {
  scelto.value = socio
  testo.value = socio.label
  aperta.value = false
}

function tasto(evento: KeyboardEvent): void {
  if (evento.key === 'ArrowDown') {
    evento.preventDefault()
    aperta.value = true
    if (opzioni.value.length) attiva.value = (attiva.value + 1) % opzioni.value.length
  } else if (evento.key === 'ArrowUp') {
    evento.preventDefault()
    if (opzioni.value.length) attiva.value = (attiva.value - 1 + opzioni.value.length) % opzioni.value.length
  } else if (evento.key === 'Enter') {
    if (mostraLista.value && attiva.value >= 0 && opzioni.value[attiva.value]) {
      evento.preventDefault()
      scegli(opzioni.value[attiva.value]!)
    }
  } else if (evento.key === 'Escape') {
    if (aperta.value) {
      evento.preventDefault()
      aperta.value = false
    }
  }
}

function uscito(): void {
  // Ritardo: il click su un'opzione arriva dopo il blur dell'input
  setTimeout(() => {
    aperta.value = false
    if (!scelto.value) testo.value = testo.value.trim()
  }, 150)
}

onBeforeUnmount(() => {
  clearTimeout(timer)
  controllo?.abort()
})
</script>

<template>
  <div class="plancia-selettore-socio">
    <label :for="`${id}-input`" class="form-label small fw-semibold">{{ etichetta }}</label>
    <div class="position-relative">
      <input
        :id="`${id}-input`"
        v-model="testo"
        type="text"
        class="form-control form-control-sm"
        :class="{ 'is-invalid': errori.length }"
        role="combobox"
        autocomplete="off"
        aria-autocomplete="list"
        :aria-expanded="mostraLista"
        :aria-controls="`${id}-lista`"
        :aria-activedescendant="mostraLista ? idAttiva : undefined"
        :aria-describedby="`${id}-aiuto`"
        placeholder="Cerca per nome, cognome, codice o gruppo…"
        @input="digitato"
        @keydown="tasto"
        @focus="aperta = true"
        @blur="uscito"
      />
      <ul
        v-show="mostraLista"
        :id="`${id}-lista`"
        role="listbox"
        class="plancia-selettore-socio__lista list-group shadow"
        :aria-label="etichetta"
      >
        <li v-if="inCorso" class="list-group-item small fg-2" aria-live="polite">Ricerca in corso…</li>
        <li v-else-if="erroreRicerca" class="list-group-item small fg-danger">{{ erroreRicerca }}</li>
        <li v-else-if="!opzioni.length" class="list-group-item small fg-2">Nessun socio trovato.</li>
        <template v-else>
          <li
            v-for="(s, i) in opzioni"
            :id="`${id}-opz-${i}`"
            :key="s.id"
            role="option"
            class="list-group-item list-group-item-action small"
            :class="{ active: i === attiva }"
            :aria-selected="i === attiva"
            @mousedown.prevent="scegli(s)"
            @mouseenter="attiva = i"
          >
            {{ s.label }}
          </li>
        </template>
      </ul>
    </div>
    <div :id="`${id}-aiuto`" class="form-text">{{ aiuto }}</div>
    <div v-for="e in errori" :key="e" class="invalid-feedback d-block">{{ e }}</div>
  </div>
</template>

<style scoped>
.plancia-selettore-socio__lista {
  position: absolute;
  inset-inline: 0;
  top: calc(100% + 2px);
  z-index: 20;
  max-height: 16rem;
  overflow-y: auto;
  margin: 0;
  padding: 0;
}
.plancia-selettore-socio__lista [role='option'] {
  cursor: pointer;
}
</style>
