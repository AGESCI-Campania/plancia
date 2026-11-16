<script setup lang="ts">
/**
 * Ricerca di un membro della Pattuglia GV (`GET /org/soci?categoria=capo&ruolo=pgv`) con
 * suggerimenti navigabili da tastiera; `v-model` è l'utente scelto (`user_pk`) o `null`.
 */
import { onBeforeUnmount, ref, useId } from 'vue'

import { api } from '@/api/http'
import type { SocioAutocomplete } from '@/api/tipi-edizioni'

const scelto = defineModel<SocioAutocomplete | null>({ default: null })

const id = useId()
const testo = ref('')
const risultati = ref<SocioAutocomplete[]>([])
const aperto = ref(false)
const attivo = ref(-1)
const messaggio = ref('')
let attesa: ReturnType<typeof setTimeout> | undefined

async function cerca(q: string): Promise<void> {
  messaggio.value = 'Ricerca in corso…'
  try {
    const soci = await api.get<SocioAutocomplete[]>('/org/soci', { q, categoria: 'capo', ruolo: 'pgv' })
    risultati.value = soci.filter((s) => s.user_pk)
    messaggio.value = risultati.value.length ? '' : 'Nessun membro trovato.'
  } catch (e) {
    risultati.value = []
    messaggio.value = e instanceof Error ? e.message : 'Ricerca non riuscita.'
  }
  aperto.value = true
  attivo.value = -1
}

function suInput(): void {
  scelto.value = null
  clearTimeout(attesa)
  const q = testo.value.trim()
  if (q.length < 2) {
    aperto.value = false
    return
  }
  attesa = setTimeout(() => void cerca(q), 300)
}

function scegli(s: SocioAutocomplete): void {
  scelto.value = s
  testo.value = s.label
  aperto.value = false
}

function tasto(e: KeyboardEvent): void {
  if (!aperto.value || !risultati.value.length) return
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    attivo.value = (attivo.value + 1) % risultati.value.length
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    attivo.value = attivo.value <= 0 ? risultati.value.length - 1 : attivo.value - 1
  } else if (e.key === 'Enter' && attivo.value >= 0) {
    e.preventDefault()
    scegli(risultati.value[attivo.value]!)
  } else if (e.key === 'Escape') {
    aperto.value = false
  }
}

function chiudiDopo(): void {
  setTimeout(() => (aperto.value = false), 150)
}

/** Svuota il campo (dopo un'assegnazione riuscita). */
function azzera(): void {
  testo.value = ''
  scelto.value = null
  risultati.value = []
}
defineExpose({ azzera })

onBeforeUnmount(() => clearTimeout(attesa))
</script>

<template>
  <div class="position-relative">
    <label :for="id" class="visually-hidden">Membro della Pattuglia GV</label>
    <input
      :id="id"
      v-model="testo"
      type="text"
      class="form-control"
      placeholder="Cerca membro Pattuglia GV per nome, cognome o gruppo…"
      autocomplete="off"
      role="combobox"
      aria-autocomplete="list"
      :aria-expanded="aperto"
      :aria-controls="`${id}-lista`"
      :aria-activedescendant="attivo >= 0 ? `${id}-${attivo}` : undefined"
      @input="suInput"
      @keydown="tasto"
      @blur="chiudiDopo"
    />
    <ul v-show="aperto" :id="`${id}-lista`" role="listbox" class="list-group position-absolute w-100 shadow plancia-suggerimenti">
      <li v-if="messaggio" class="list-group-item small fg-2" role="option" aria-disabled="true" aria-selected="false">{{ messaggio }}</li>
      <li
        v-for="(s, i) in risultati"
        :id="`${id}-${i}`"
        :key="s.id"
        role="option"
        :aria-selected="i === attivo"
        class="list-group-item list-group-item-action py-2 small"
        :class="{ active: i === attivo }"
        @mousedown.prevent="scegli(s)"
      >
        {{ s.label }}
      </li>
    </ul>
  </div>
</template>

<style scoped>
.plancia-suggerimenti {
  z-index: 20;
  top: 100%;
  max-height: 14rem;
  overflow-y: auto;
  cursor: pointer;
}
</style>
