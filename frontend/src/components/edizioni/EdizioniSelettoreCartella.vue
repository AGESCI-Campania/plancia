<script setup lang="ts">
/**
 * Scelta di una cartella Google Drive dell'account collegato: ricerca per nome (prime 20),
 * navigazione nelle sottocartelle, creazione di una nuova cartella nella posizione corrente.
 */
import { computed, ref, useId, watch } from 'vue'

import { api, ErroreApi } from '@/api/http'
import type { Cartella } from '@/api/tipi-edizioni'
import FinestraDialogo from '@/components/FinestraDialogo.vue'
import IconaBs from '@/components/IconaBs.vue'

const props = defineProps<{ account: string; titolo: string }>()
const aperta = defineModel<boolean>('aperta', { default: false })
const emit = defineEmits<{ scelta: [cartella: Cartella] }>()

const id = useId()
const ricerca = ref('')
const cartelle = ref<Cartella[]>([])
const percorso = ref<Cartella[]>([])
const inCorso = ref(false)
const errore = ref('')
const nuovoNome = ref('')
const creazione = ref(false)

const corrente = computed(() => percorso.value.at(-1) ?? null)

async function carica(): Promise<void> {
  inCorso.value = true
  errore.value = ''
  try {
    cartelle.value = await api.get<Cartella[]>('/drive/cartelle', {
      account: props.account,
      q: ricerca.value.trim(),
      parent_id: corrente.value?.id,
    })
  } catch (e) {
    cartelle.value = []
    errore.value = e instanceof ErroreApi ? e.message : 'Cartelle non caricate.'
  } finally {
    inCorso.value = false
  }
}

watch(aperta, (v) => {
  if (!v) return
  ricerca.value = nuovoNome.value = errore.value = ''
  percorso.value = []
  void carica()
})

function entra(c: Cartella): void {
  percorso.value = [...percorso.value, c]
  ricerca.value = ''
  void carica()
}

function torna(indice: number): void {
  percorso.value = percorso.value.slice(0, indice)
  ricerca.value = ''
  void carica()
}

function scegli(c: Cartella): void {
  emit('scelta', c)
  aperta.value = false
}

async function crea(): Promise<void> {
  const nome = nuovoNome.value.trim()
  if (!nome) {
    errore.value = 'Inserisci un nome per la nuova cartella.'
    return
  }
  creazione.value = true
  errore.value = ''
  try {
    const c = await api.post<Cartella>('/drive/cartelle', {
      account: props.account,
      nome,
      parent_id: corrente.value?.id ?? null,
    })
    scegli(c)
  } catch (e) {
    errore.value = e instanceof ErroreApi ? (e.errori.nome?.[0] ?? e.message) : 'Cartella non creata.'
  } finally {
    creazione.value = false
  }
}
</script>

<template>
  <FinestraDialogo v-model:aperta="aperta" :titolo="titolo">
    <nav aria-label="Posizione nella cartella" class="mb-3 small">
      <ol class="breadcrumb mb-0">
        <li class="breadcrumb-item">
          <button v-if="percorso.length" type="button" class="btn btn-text btn-sm p-0" @click="torna(0)">Il mio Drive</button>
          <span v-else aria-current="location">Il mio Drive</span>
        </li>
        <li v-for="(c, i) in percorso" :key="c.id" class="breadcrumb-item">
          <button v-if="i < percorso.length - 1" type="button" class="btn btn-text btn-sm p-0" @click="torna(i + 1)">{{ c.nome }}</button>
          <span v-else aria-current="location">{{ c.nome }}</span>
        </li>
      </ol>
    </nav>

    <form class="d-flex gap-2 mb-3" role="search" @submit.prevent="carica">
      <label :for="`${id}-cerca`" class="visually-hidden">Cerca per nome</label>
      <input :id="`${id}-cerca`" v-model="ricerca" type="search" class="form-control" placeholder="Cerca per nome…" autocomplete="off" />
      <button type="submit" class="btn btn-outline theme-secondary">Cerca</button>
    </form>

    <button v-if="corrente" type="button" class="btn btn-solid btn-sm theme-primary mb-3" @click="scegli(corrente)">
      <IconaBs nome="check-lg" class="me-1" />Scegli «{{ corrente.nome }}»
    </button>

    <div class="plancia-elenco-cartelle mb-4" :aria-busy="inCorso">
      <p v-if="inCorso" class="fg-2 small p-2 mb-0" role="status">Caricamento…</p>
      <p v-else-if="!cartelle.length && !errore" class="fg-2 small p-2 mb-0">
        Nessuna cartella trovata.
      </p>
      <ul v-else class="list-group">
        <li v-for="c in cartelle" :key="c.id" class="list-group-item d-flex align-items-center gap-2">
          <IconaBs nome="folder2" class="fg-2" />
          <span class="flex-grow-1 text-truncate" :title="c.id">{{ c.nome }}</span>
          <button type="button" class="btn btn-text btn-sm theme-secondary" :aria-label="`Apri la cartella ${c.nome}`" @click="entra(c)">
            <IconaBs nome="chevron-right" /><span class="d-none sm:d-inline ms-1">Apri</span>
          </button>
          <button type="button" class="btn btn-outline btn-sm theme-primary" :aria-label="`Scegli la cartella ${c.nome}`" @click="scegli(c)">
            Scegli
          </button>
        </li>
      </ul>
    </div>

    <form class="d-flex gap-2 align-items-center" @submit.prevent="crea">
      <label :for="`${id}-nuova`" class="visually-hidden">Nome della nuova cartella</label>
      <input :id="`${id}-nuova`" v-model="nuovoNome" type="text" class="form-control" placeholder="Nome nuova cartella…" />
      <button type="submit" class="btn btn-outline theme-success text-nowrap" :disabled="creazione">
        <IconaBs nome="folder-plus" class="me-1" />Crea<span class="d-none sm:d-inline">&nbsp;qui</span>
      </button>
    </form>
    <p v-if="errore" class="fg-danger small mt-2 mb-0" role="alert">{{ errore }}</p>
  </FinestraDialogo>
</template>

<style scoped>
.plancia-elenco-cartelle {
  max-height: 20rem;
  overflow-y: auto;
}
</style>
