<script setup lang="ts">
/** Scheda "Identità e footer": titolo/sottotitolo, testo del footer, link del footer (max 4, ordinabili). */
import { computed, ref, watch } from 'vue'

import { api } from '@/api/http'
import CampoForm from '@/components/CampoForm.vue'
import IconaBs from '@/components/IconaBs.vue'
import ImpostazioniEditorHtml from '@/components/impostazioni/ImpostazioniEditorHtml.vue'
import type { FooterLink, Impostazioni } from '@/components/impostazioni/tipi'
import { conferma } from '@/composables/conferma'
import { dataOra, sposta } from '@/composables/impostazioni-editor'
import { useSalvataggio } from '@/composables/impostazioni-salvataggio'
import { useSitoStore } from '@/stores/sito'

const MAX_LINK = 4

const props = defineProps<{ dati: Impostazioni }>()
const emit = defineEmits<{ aggiornate: [Impostazioni] }>()
const sito = useSitoStore()

// --- Identità ------------------------------------------------------------------------------
const titolo = ref(props.dati.identita.titolo)
const sottotitolo = ref(props.dati.identita.sottotitolo)
const identita = useSalvataggio()
async function salvaIdentita(): Promise<void> {
  const r = await identita.esegui(
    () => api.patch<Impostazioni>('/impostazioni/identita', { titolo: titolo.value, sottotitolo: sottotitolo.value }),
    'Identità salvata.',
  )
  if (r) {
    emit('aggiornate', r)
    void sito.carica()
  }
}

// --- Testo del footer ----------------------------------------------------------------------
const footerTesto = ref(props.dati.footer.footer_testo)
const footer = useSalvataggio()
async function salvaFooter(): Promise<void> {
  const r = await footer.esegui(
    () => api.patch<Impostazioni>('/impostazioni/footer', { footer_testo: footerTesto.value }),
    'Testo del footer salvato.',
  )
  if (r) {
    emit('aggiornate', r)
    void sito.carica()
  }
}

// --- Link del footer -----------------------------------------------------------------------
interface RigaLink {
  id: number | null
  tipo: string
  url: string
  etichetta: string
  modificata: boolean
}
const tipiLink = computed(() => props.dati.scelte.footer_link_tipo ?? [])
const righe = ref<RigaLink[]>([])
function daLink(l: FooterLink): RigaLink {
  return { id: l.id, tipo: l.tipo, url: l.url, etichetta: l.etichetta, modificata: false }
}
watch(
  () => props.dati.footer.links,
  (links) => (righe.value = links.map(daLink)),
  { immediate: true },
)
const erroriLink = ref<Record<number, Record<string, string[]>>>({})
const link = useSalvataggio()

function aggiungi(): void {
  if (righe.value.length >= MAX_LINK) return
  righe.value.push({ id: null, tipo: tipiLink.value[0]?.valore ?? '', url: '', etichetta: '', modificata: true })
}

async function ricarica(): Promise<void> {
  const links = await api.get<FooterLink[]>('/impostazioni/footer/link')
  emit('aggiornate', { ...props.dati, footer: { ...props.dati.footer, links } })
  void sito.carica()
}

async function salvaLink(i: number): Promise<void> {
  const r = righe.value[i]
  if (!r) return
  const corpo = { tipo: r.tipo, url: r.url.trim(), etichetta: r.etichetta.trim() }
  const ok = await link.esegui(
    () => (r.id ? api.patch(`/impostazioni/footer/link/${r.id}`, corpo) : api.post('/impostazioni/footer/link', corpo)),
    'Link salvato.',
  )
  erroriLink.value = { ...erroriLink.value, [i]: link.errori.value }
  if (ok) await ricarica()
}

async function eliminaLink(i: number): Promise<void> {
  const r = righe.value[i]
  if (!r) return
  if (!r.id) {
    righe.value.splice(i, 1)
    return
  }
  if (!(await conferma(`Eliminare il link «${r.etichetta || r.url}» dal footer?`, { testoConferma: 'Elimina', pericolosa: true }))) return
  if (await link.esegui(() => api.delete(`/impostazioni/footer/link/${r.id}`).then(() => true), 'Link eliminato.')) await ricarica()
}

async function muovi(i: number, delta: number): Promise<void> {
  const nuove = sposta(righe.value, i, delta)
  const ids = nuove.map((r) => r.id).filter((id): id is number => id !== null)
  righe.value = nuove
  if (ids.length !== nuove.length) return // c'è un link nuovo non salvato: l'ordine si salva dopo
  if (await link.esegui(() => api.post('/impostazioni/footer/link/ordina', { ids }))) await ricarica()
}
</script>

<template>
  <section class="card mb-6" aria-labelledby="titolo-identita">
    <div class="card-body">
      <h2 id="titolo-identita" class="h5 mb-4"><IconaBs nome="card-heading" class="me-2" />Identità</h2>
      <form novalidate @submit.prevent="salvaIdentita">
        <div class="row">
          <div class="md:col-5">
            <CampoForm v-model="titolo" etichetta="Titolo" :errori="identita.errori.value.titolo" obbligatorio />
          </div>
          <div class="md:col-7">
            <CampoForm v-model="sottotitolo" etichetta="Sottotitolo" :errori="identita.errori.value.sottotitolo" />
          </div>
        </div>
        <div class="d-flex justify-content-end">
          <button type="submit" class="btn btn-solid theme-primary" :disabled="identita.inCorso.value">
            <IconaBs nome="check-lg" class="me-1" />Salva identità
          </button>
        </div>
      </form>
    </div>
  </section>

  <section class="card mb-6" aria-labelledby="titolo-footer">
    <div class="card-body">
      <h2 id="titolo-footer" class="h5 mb-4"><IconaBs nome="layout-text-window-reverse" class="me-2" />Footer</h2>
      <form novalidate @submit.prevent="salvaFooter">
        <ImpostazioniEditorHtml
          v-model="footerTesto"
          etichetta="Testo del footer"
          :segnaposti="['titolo', 'sottotitolo', 'versione', 'commit']"
          :errori="footer.errori.value.footer_testo"
          altezza="8rem"
        />
        <p class="form-text mb-4">
          Le variabili vengono sostituite al momento della visualizzazione (es. versione
          <code>{{ sito.versioneServer || '—' }}</code>).
        </p>
        <div class="d-flex justify-content-end">
          <button type="submit" class="btn btn-solid theme-primary" :disabled="footer.inCorso.value">
            <IconaBs nome="check-lg" class="me-1" />Salva testo del footer
          </button>
        </div>
      </form>

      <hr class="my-6" />
      <div class="d-flex flex-wrap align-items-center gap-3 mb-4">
        <h3 class="h6 mb-0">Link del footer</h3>
        <span class="small fg-2">{{ righe.length }} di {{ MAX_LINK }}</span>
        <button
          type="button"
          class="btn btn-outline btn-sm theme-primary ms-auto"
          :disabled="righe.length >= MAX_LINK"
          @click="aggiungi"
        >
          <IconaBs nome="plus-lg" class="me-1" />Aggiungi link
        </button>
      </div>
      <p v-if="!righe.length" class="fg-2 small">Nessun link nel footer.</p>
      <ol class="list-unstyled mb-0">
        <li v-for="(r, i) in righe" :key="r.id ?? `nuovo-${i}`" class="border rounded p-4 mb-3">
          <div class="row align-items-end">
            <div class="md:col-3 mb-3">
              <label :for="`link-tipo-${i}`" class="form-label">Tipo</label>
              <select :id="`link-tipo-${i}`" v-model="r.tipo" class="form-control" @change="r.modificata = true">
                <option v-for="t in tipiLink" :key="t.valore" :value="t.valore">{{ t.etichetta }}</option>
              </select>
            </div>
            <div class="md:col-3 mb-3">
              <label :for="`link-etichetta-${i}`" class="form-label">Etichetta</label>
              <input :id="`link-etichetta-${i}`" v-model="r.etichetta" class="form-control" :class="{ 'is-invalid': erroriLink[i]?.etichetta }" @input="r.modificata = true" />
            </div>
            <div class="md:col-6 mb-3">
              <label :for="`link-url-${i}`" class="form-label">Indirizzo</label>
              <input :id="`link-url-${i}`" v-model="r.url" type="url" class="form-control" :class="{ 'is-invalid': erroriLink[i]?.url }" placeholder="https://…" @input="r.modificata = true" />
            </div>
          </div>
          <div v-for="(msgs, campo) in erroriLink[i] ?? {}" :key="campo" class="invalid-feedback d-block mb-2">
            {{ msgs.join(' ') }}
          </div>
          <div class="d-flex flex-wrap gap-2">
            <button type="button" class="btn btn-outline btn-sm theme-secondary" :disabled="i === 0 || link.inCorso.value" :aria-label="`Sposta su: ${r.etichetta || 'link'}`" title="Sposta su" @click="muovi(i, -1)">
              <IconaBs nome="arrow-up" />
            </button>
            <button type="button" class="btn btn-outline btn-sm theme-secondary" :disabled="i === righe.length - 1 || link.inCorso.value" :aria-label="`Sposta giù: ${r.etichetta || 'link'}`" title="Sposta giù" @click="muovi(i, 1)">
              <IconaBs nome="arrow-down" />
            </button>
            <button type="button" class="btn btn-outline btn-sm theme-danger ms-auto" :disabled="link.inCorso.value" @click="eliminaLink(i)">
              <IconaBs nome="trash" class="me-1" />{{ r.id ? 'Elimina' : 'Annulla' }}
            </button>
            <button type="button" class="btn btn-solid btn-sm theme-primary" :disabled="!r.modificata || link.inCorso.value" @click="salvaLink(i)">
              <IconaBs nome="check-lg" class="me-1" />{{ r.id ? 'Salva' : 'Aggiungi' }}
            </button>
          </div>
        </li>
      </ol>
      <p class="small fg-2 mt-4 mb-0">Aggiornato il {{ dataOra(dati.aggiornato_at) }}.</p>
    </div>
  </section>
</template>
