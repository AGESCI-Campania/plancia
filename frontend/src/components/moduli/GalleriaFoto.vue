<script setup lang="ts">
/**
 * Foto di un modulo (1ª/2ª impresa, missione): miniature, anteprima a tutto schermo con
 * "Scarica", caricamento multiplo da fotocamera o galleria con anteprima, avanzamento ed
 * errore per file, eliminazione con conferma. Le azioni seguono i permessi del backend.
 */
import { computed, onBeforeUnmount, onMounted, ref, useId } from 'vue'

import FinestraDialogo from '@/components/FinestraDialogo.vue'
import IconaBs from '@/components/IconaBs.vue'
import type { Allegato } from '@/composables/diarioCompilazione'
import { scaricaESalva } from '@/composables/file'
import { formattaDimensione, useGalleriaFoto, type InviaFoto } from '@/composables/fotoDiario'
import type { VoceCoda } from '@/offline/db'
import { fotoInCoda, inviaFotoOffline, scartaVoce } from '@/offline/coda'
import { useAvvisiStore } from '@/stores/avvisi'

const props = withDefaults(
  defineProps<{
    diarioId: number | string
    modulo: string
    titolo?: string
    puoCaricare: boolean
    puoEliminare: boolean
    maxPx?: number
    maxMb?: number
    tipi?: string[]
    /** Livello del titolo (h2 nella pagina Foto, h3 dentro un modulo). */
    livello?: 2 | 3
    invia?: InviaFoto
  }>(),
  { titolo: 'Foto', maxPx: 1024, maxMb: 20, tipi: () => [], livello: 3, invia: undefined },
)
const emit = defineEmits<{ modificata: [] }>()

const avvisi = useAvvisiStore()
const g = useGalleriaFoto(props.diarioId, props.modulo, {
  // Offline le foto restano sul dispositivo e partono alla riconnessione (Fase 5)
  invia: props.invia ?? inviaFotoOffline,
  maxPx: () => props.maxPx,
  maxMb: () => props.maxMb,
  tipi: () => props.tipi,
  dopoModifica: () => emit('modificata'),
})
const { foto, invii, caricamento, errore } = g
const inCoda = computed(() => fotoInCoda(props.diarioId, props.modulo))
const anteprimeCoda = new Map<number, string>()
function anteprimaCoda(v: VoceCoda): string {
  let url = anteprimeCoda.get(v.id!)
  if (!url && v.file) {
    url = URL.createObjectURL(v.file)
    anteprimeCoda.set(v.id!, url)
  }
  return url ?? ''
}
onBeforeUnmount(() => anteprimeCoda.forEach((u) => URL.revokeObjectURL(u)))
const id = useId()
const inputFotocamera = ref<HTMLInputElement>()
const inputGalleria = ref<HTMLInputElement>()
const aperta = ref<Allegato | null>(null)
const finestraAperta = ref(false)

onMounted(() => void g.carica())

function scelte(evento: Event): void {
  const input = evento.target as HTMLInputElement
  if (input.files?.length) g.aggiungi(Array.from(input.files))
  input.value = ''
}

function apri(a: Allegato): void {
  aperta.value = a
  finestraAperta.value = true
}

async function elimina(a: Allegato): Promise<void> {
  // Una finestra alla volta: l'anteprima si chiude prima della conferma
  finestraAperta.value = false
  try {
    if (await g.elimina(a)) avvisi.mostra('Foto eliminata.')
  } catch (e) {
    avvisi.mostra(e instanceof Error ? e.message : 'Eliminazione non riuscita.', 'danger')
  }
}

async function scarica(a: Allegato): Promise<void> {
  try {
    await scaricaESalva(a.download_url)
  } catch (e) {
    avvisi.mostra(e instanceof Error ? e.message : 'Scaricamento non riuscito.', 'danger')
  }
}

const accetta = () => (props.tipi.length ? props.tipi.join(',') : 'image/*')
</script>

<template>
  <section class="galleria-foto" :aria-labelledby="`${id}-titolo`">
    <component :is="`h${livello}`" :id="`${id}-titolo`" class="h5 mb-3 d-flex align-items-center gap-2">
      <IconaBs nome="images" />{{ titolo }}
      <span v-if="foto.length" class="badge theme-secondary fw-normal">{{ foto.length }}</span>
    </component>

    <div v-if="errore" class="alert theme-danger d-flex align-items-center gap-3" role="alert">
      <span>{{ errore }}</span>
      <button type="button" class="btn btn-outline btn-sm theme-danger ms-auto" @click="g.carica()">Riprova</button>
    </div>
    <div v-else-if="caricamento && !foto.length" class="py-4" role="status">
      <span class="spinner-border spinner-border-sm me-2" aria-hidden="true" />Caricamento delle foto…
    </div>

    <ul v-if="foto.length || invii.length || inCoda.length" class="list-unstyled griglia-foto mb-4">
      <li v-for="a in foto" :key="a.id" class="foto">
        <button type="button" class="foto-miniatura" :aria-label="`Apri la foto ${a.nome}`" @click="apri(a)">
          <img :src="a.miniatura_url" :alt="a.nome" loading="lazy" width="160" height="160" />
        </button>
        <div class="foto-didascalia small">
          <span class="text-truncate" :title="a.nome">{{ a.nome }}</span>
          <button
            v-if="puoEliminare"
            type="button"
            class="btn btn-text theme-danger btn-sm btn-icon"
            :aria-label="`Elimina la foto ${a.nome}`"
            @click="elimina(a)"
          >
            <IconaBs nome="trash" />
          </button>
        </div>
      </li>
      <li v-for="v in inCoda" :key="`coda-${v.id}`" class="foto foto-in-invio" :aria-label="`${v.nome} in attesa di invio`">
        <div class="foto-miniatura">
          <img :src="anteprimaCoda(v)" :alt="v.nome" width="160" height="160" />
          <div class="foto-sovrimpressione"><IconaBs nome="cloud-upload" etichetta="In attesa di invio" /></div>
        </div>
        <div class="foto-didascalia small flex-column align-items-stretch">
          <span class="text-truncate" :title="v.nome">{{ v.nome }}</span>
          <span v-if="v.stato === 'attesa'" class="fg-2">Sul dispositivo: verrà inviata online</span>
          <template v-else>
            <span class="fg-danger" role="alert">{{ v.errore }}</span>
            <button type="button" class="btn btn-text theme-secondary btn-sm px-1" @click="scartaVoce(v)">Rimuovi</button>
          </template>
        </div>
      </li>
      <li v-for="v in invii" :key="v.id" class="foto foto-in-invio" :aria-label="`Invio di ${v.nome}`">
        <div class="foto-miniatura">
          <img :src="v.anteprima" :alt="v.nome" width="160" height="160" />
          <div v-if="v.stato !== 'errore'" class="foto-sovrimpressione">
            <span class="spinner-border spinner-border-sm" aria-hidden="true" />
          </div>
        </div>
        <div class="foto-didascalia small flex-column align-items-stretch">
          <span class="text-truncate" :title="v.nome">{{ v.nome }}</span>
          <template v-if="v.stato === 'errore'">
            <span class="fg-danger" role="alert">{{ v.errore }}</span>
            <span class="d-flex gap-1">
              <button v-if="!v.definitivo" type="button" class="btn btn-text theme-primary btn-sm px-1" @click="g.riprova(v.id)">Riprova</button>
              <button type="button" class="btn btn-text theme-secondary btn-sm px-1" @click="g.togli(v.id)">Rimuovi</button>
            </span>
          </template>
          <div
            v-else
            class="progress"
            role="progressbar"
            :aria-label="`Avanzamento di ${v.nome}`"
            :aria-valuenow="Math.round(v.avanzamento * 100)"
            aria-valuemin="0"
            aria-valuemax="100"
            style="height: 0.375rem"
          >
            <div class="progress-bar" :style="{ width: `${Math.max(v.avanzamento * 100, v.stato === 'invio' ? 5 : 0)}%` }" />
          </div>
        </div>
      </li>
    </ul>
    <p v-else-if="!caricamento && !errore" class="fg-2">Nessuna foto per questo modulo.</p>

    <div v-if="puoCaricare" class="d-flex flex-wrap align-items-center gap-2">
      <button type="button" class="btn btn-outline theme-primary" @click="inputFotocamera?.click()">
        <IconaBs nome="camera" class="me-1" />Scatta una foto
      </button>
      <button type="button" class="btn btn-outline theme-primary" @click="inputGalleria?.click()">
        <IconaBs nome="image" class="me-1" />Scegli dalla galleria
      </button>
      <span class="form-text">JPEG, PNG, WebP o HEIC, max {{ maxMb }} MB ciascuna.</span>
      <input
        ref="inputFotocamera"
        type="file"
        :accept="accetta()"
        capture="environment"
        class="visually-hidden"
        tabindex="-1"
        aria-hidden="true"
        @change="scelte"
      />
      <input
        ref="inputGalleria"
        type="file"
        :accept="accetta()"
        multiple
        class="visually-hidden"
        tabindex="-1"
        aria-label="Scegli le foto da caricare"
        :data-testid="`input-foto-${modulo}`"
        @change="scelte"
      />
    </div>

    <FinestraDialogo v-model:aperta="finestraAperta" :titolo="aperta?.nome ?? 'Foto'" @chiusa="aperta = null">
      <template v-if="aperta">
        <img :src="aperta.anteprima_url" :alt="aperta.nome" class="foto-grande" />
        <p class="fg-2 small mt-2 mb-0">{{ formattaDimensione(aperta.dimensione) }}</p>
      </template>
      <template #piede>
        <button v-if="aperta && puoEliminare" type="button" class="btn btn-outline theme-danger me-auto" @click="elimina(aperta)">
          <IconaBs nome="trash" class="me-1" />Elimina
        </button>
        <button v-if="aperta" type="button" class="btn btn-solid theme-primary" @click="scarica(aperta)">
          <IconaBs nome="download" class="me-1" />Scarica
        </button>
      </template>
    </FinestraDialogo>
  </section>
</template>

<style scoped>
.griglia-foto {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(8.5rem, 1fr));
  gap: 0.75rem;
}
.foto {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-width: 0;
}
.foto-miniatura {
  position: relative;
  display: block;
  width: 100%;
  aspect-ratio: 1;
  padding: 0;
  overflow: hidden;
  background: var(--bg-1, #f1f3f5);
  border: var(--border-width, 1px) solid var(--border-color, #dee2e6);
  border-radius: var(--radius-5, 0.5rem);
}
.foto-miniatura img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
button.foto-miniatura:focus-visible {
  outline: 3px solid var(--primary-focus-ring, #86b7fe);
  outline-offset: 2px;
}
.foto-sovrimpressione {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  background: rgb(255 255 255 / 55%);
}
.foto-didascalia {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  min-width: 0;
}
.foto-grande {
  display: block;
  max-width: 100%;
  max-height: 70vh;
  margin: 0 auto;
}
</style>
