<script setup lang="ts">
/**
 * Campo "Comune" dell'evento con suggerimenti (servizio pubblico dei comuni italiani, come
 * la pagina Django). Il testo resta libero: il suggerimento serve solo a scriverlo giusto.
 */
import { onBeforeUnmount, ref, useId } from 'vue'

const valore = defineModel<string>({ default: '' })
defineProps<{ errori?: string[] }>()

interface Comune {
  nome: string
  provincia?: string | { sigla?: string; nome?: string }
}

const id = useId()
const suggerimenti = ref<{ nome: string; etichetta: string }[]>([])
const aperto = ref(false)
const attivo = ref(-1)
let attesa: ReturnType<typeof setTimeout> | undefined
let controllo: AbortController | undefined

function provincia(c: Comune): string {
  if (!c.provincia) return ''
  return typeof c.provincia === 'object' ? (c.provincia.sigla ?? c.provincia.nome ?? '') : c.provincia
}

async function cerca(q: string): Promise<void> {
  controllo?.abort()
  controllo = new AbortController()
  try {
    const url = `https://comuni-ita.nicolorebaioli.dev/comuni?q=${encodeURIComponent(q)}&pagesize=10&fields=nome,provincia`
    const r = await fetch(url, { signal: controllo.signal })
    const dati: unknown = await r.json()
    const comuni = (Array.isArray(dati) ? dati : ((dati as { data?: Comune[] }).data ?? [])) as Comune[]
    suggerimenti.value = comuni.map((c) => {
      const p = provincia(c)
      return { nome: c.nome, etichetta: p ? `${c.nome} (${p})` : c.nome }
    })
    aperto.value = suggerimenti.value.length > 0
    attivo.value = -1
  } catch {
    // servizio irraggiungibile: il campo resta a testo libero
    aperto.value = false
  }
}

function suInput(): void {
  clearTimeout(attesa)
  const q = valore.value.trim()
  if (q.length < 2) {
    aperto.value = false
    return
  }
  attesa = setTimeout(() => void cerca(q), 300)
}

function scegli(nome: string): void {
  valore.value = nome
  aperto.value = false
}

function tasto(e: KeyboardEvent): void {
  if (!aperto.value) return
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    attivo.value = (attivo.value + 1) % suggerimenti.value.length
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    attivo.value = attivo.value <= 0 ? suggerimenti.value.length - 1 : attivo.value - 1
  } else if (e.key === 'Enter' && attivo.value >= 0) {
    e.preventDefault()
    scegli(suggerimenti.value[attivo.value]!.nome)
  } else if (e.key === 'Escape') {
    aperto.value = false
  }
}

function chiudiDopo(): void {
  setTimeout(() => (aperto.value = false), 150)
}

onBeforeUnmount(() => {
  clearTimeout(attesa)
  controllo?.abort()
})
</script>

<template>
  <div class="mb-5 position-relative">
    <label :for="id" class="form-label">Comune</label>
    <input
      :id="id"
      v-model="valore"
      type="text"
      class="form-control"
      :class="{ 'is-invalid': errori?.length }"
      placeholder="Digita il nome del comune…"
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
    <ul
      v-show="aperto"
      :id="`${id}-lista`"
      role="listbox"
      class="list-group position-absolute w-100 shadow plancia-suggerimenti"
    >
      <li
        v-for="(s, i) in suggerimenti"
        :id="`${id}-${i}`"
        :key="s.etichetta"
        role="option"
        :aria-selected="i === attivo"
        class="list-group-item list-group-item-action py-2 small"
        :class="{ active: i === attivo }"
        @mousedown.prevent="scegli(s.nome)"
      >
        {{ s.etichetta }}
      </li>
    </ul>
    <div v-for="e in errori ?? []" :key="e" class="invalid-feedback d-block">{{ e }}</div>
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
