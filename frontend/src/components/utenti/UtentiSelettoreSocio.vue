<script setup lang="ts">
/**
 * Selettore di un Socio con autocompletamento (`GET /org/soci?q=&categoria=`), al posto di
 * Tom Select: combobox ARIA (frecce, Invio, Esc), ricerca dopo 2 caratteri con un breve ritardo.
 * `v-model` è il Socio scelto (o `null`).
 */
import { computed, onBeforeUnmount, ref, useId, watch } from 'vue'

import { api, ErroreApi } from '@/api/http'
import IconaBs from '@/components/IconaBs.vue'
import type { SocioAutocomplete } from '@/components/utenti/tipi'

const scelto = defineModel<SocioAutocomplete | null>({ default: null })
const props = withDefaults(
  defineProps<{
    etichetta?: string
    categoria?: 'capo' | 'ragazzo'
    /** Solo soci il cui utente ha questo ruolo attivo. */
    ruolo?: string
    errori?: string[]
    aiuto?: string
    obbligatorio?: boolean
  }>(),
  { etichetta: 'Socio', categoria: undefined, ruolo: undefined, errori: () => [], aiuto: '', obbligatorio: false },
)

const id = useId()
const testo = ref(scelto.value?.label ?? '')
const risultati = ref<SocioAutocomplete[]>([])
const aperto = ref(false)
const attivo = ref(-1)
const inCorso = ref(false)
const errore = ref('')
let timer: ReturnType<typeof setTimeout> | undefined
let controllo: AbortController | undefined

const idAttivo = computed(() => (attivo.value >= 0 ? `${id}-opz-${attivo.value}` : undefined))
const messaggio = computed(() => {
  if (errore.value) return errore.value
  if (inCorso.value) return 'Ricerca…'
  if (testo.value.trim().length < 2) return 'Scrivi almeno 2 caratteri.'
  if (!risultati.value.length) return 'Nessun socio trovato.'
  return ''
})

watch(scelto, (s) => {
  if (s && s.label !== testo.value) testo.value = s.label
  if (!s && !aperto.value) testo.value = ''
})

async function cerca(q: string): Promise<void> {
  controllo?.abort()
  controllo = new AbortController()
  inCorso.value = true
  errore.value = ''
  try {
    risultati.value = await api.get<SocioAutocomplete[]>(
      '/org/soci',
      { q, categoria: props.categoria, ruolo: props.ruolo },
      controllo.signal,
    )
    attivo.value = risultati.value.length ? 0 : -1
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return
    risultati.value = []
    errore.value = e instanceof ErroreApi ? e.message : 'Ricerca non riuscita.'
  } finally {
    inCorso.value = false
  }
}

function suInput(): void {
  if (scelto.value) scelto.value = null
  aperto.value = true
  clearTimeout(timer)
  const q = testo.value.trim()
  if (q.length < 2) {
    risultati.value = []
    attivo.value = -1
    return
  }
  timer = setTimeout(() => void cerca(q), 250)
}

function scegli(s: SocioAutocomplete): void {
  scelto.value = s
  testo.value = s.label
  aperto.value = false
}

function pulisci(): void {
  scelto.value = null
  testo.value = ''
  risultati.value = []
  aperto.value = false
}

function tasto(e: KeyboardEvent): void {
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    aperto.value = true
    if (risultati.value.length) attivo.value = (attivo.value + 1) % risultati.value.length
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    if (risultati.value.length)
      attivo.value = (attivo.value - 1 + risultati.value.length) % risultati.value.length
  } else if (e.key === 'Enter') {
    if (aperto.value && attivo.value >= 0 && risultati.value[attivo.value]) {
      e.preventDefault()
      scegli(risultati.value[attivo.value]!)
    }
  } else if (e.key === 'Escape') {
    if (aperto.value) {
      e.preventDefault()
      aperto.value = false
    }
  }
}

function suBlur(): void {
  // Il click su un'opzione arriva dopo il blur: si chiude con un minimo ritardo.
  setTimeout(() => {
    aperto.value = false
    if (!scelto.value) testo.value = ''
  }, 150)
}

onBeforeUnmount(() => {
  clearTimeout(timer)
  controllo?.abort()
})
</script>

<template>
  <div class="mb-5">
    <label :for="id" class="form-label">{{ etichetta }}</label>
    <div class="position-relative">
      <div class="d-flex gap-2">
        <input
          :id="id"
          v-model="testo"
          type="text"
          class="form-control"
          :class="{ 'is-invalid': errori.length }"
          role="combobox"
          autocomplete="off"
          aria-autocomplete="list"
          :aria-expanded="aperto"
          :aria-controls="`${id}-lista`"
          :aria-activedescendant="aperto ? idAttivo : undefined"
          :aria-describedby="aiuto ? `${id}-aiuto` : undefined"
          :required="obbligatorio"
          placeholder="Cerca per nome, cognome o codice…"
          @input="suInput"
          @keydown="tasto"
          @focus="aperto = testo.length >= 2 && !scelto"
          @blur="suBlur"
        />
        <button
          v-if="scelto"
          type="button"
          class="btn btn-subtle theme-secondary"
          aria-label="Togli il socio scelto"
          @click="pulisci"
        >
          <IconaBs nome="x-lg" />
        </button>
      </div>
      <ul
        :id="`${id}-lista`"
        class="menu w-100 mt-1"
        :class="{ show: aperto }"
        role="listbox"
        :aria-label="etichetta"
        style="--menu-max-height: 18rem; --menu-overflow-y: auto"
      >
        <li v-if="messaggio" class="menu-text fg-2" role="presentation">{{ messaggio }}</li>
        <li
          v-for="(s, i) in risultati"
          v-else
          :id="`${id}-opz-${i}`"
          :key="s.id"
          class="menu-item"
          :class="{ active: i === attivo }"
          role="option"
          :aria-selected="i === attivo"
          @mousedown.prevent="scegli(s)"
          @mouseenter="attivo = i"
        >
          <span class="menu-item-content">
            {{ s.cognome }} {{ s.nome }}
            <span class="menu-item-description">{{ s.codice_socio }} · {{ s.gruppo }} · {{ s.zona }}</span>
          </span>
        </li>
      </ul>
    </div>
    <div v-if="aiuto" :id="`${id}-aiuto`" class="form-text">{{ aiuto }}</div>
    <div v-for="e in errori" :key="e" class="invalid-feedback d-block">{{ e }}</div>
  </div>
</template>
