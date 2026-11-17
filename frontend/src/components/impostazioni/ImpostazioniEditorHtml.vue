<script setup lang="ts">
/**
 * Editor HTML (Tiptap) per template email, pagine statiche e testo del footer: barra di
 * formattazione, segnaposti del template come pulsanti, caricamento immagini, vista sorgente
 * e anteprima. L'HTML che l'editor visuale perderebbe (tabelle, stili, `{% for %}`) si
 * modifica dal sorgente, che resta intatto; l'anteprima è in un iframe isolato (sandbox).
 */
import { EditorContent, mergeAttributes, Node, useEditor } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import { computed, onBeforeUnmount, ref, useId, watch } from 'vue'

import { api } from '@/api/http'
import FinestraDialogo from '@/components/FinestraDialogo.vue'
import IconaBs from '@/components/IconaBs.vue'
import { conferma } from '@/composables/conferma'
import { inserisciInTesto, richiedeSorgente, segnaposto } from '@/composables/impostazioni-editor'
import { useAvvisiStore } from '@/stores/avvisi'

type Modo = 'visuale' | 'sorgente' | 'anteprima'

const valore = defineModel<string>({ default: '' })
withDefaults(
  defineProps<{
    etichetta: string
    /** Nomi delle variabili del template (diventano pulsanti `{{ nome }}`). */
    segnaposti?: string[]
    /** Abilita il caricamento di immagini (`POST /impostazioni/immagini-mail`). */
    immagini?: boolean
    errori?: string[]
    altezza?: string
  }>(),
  { segnaposti: () => [], immagini: false, errori: () => [], altezza: '18rem' },
)

const id = useId()
const avvisi = useAvvisiStore()
const modo = ref<Modo>(richiedeSorgente(valore.value) ? 'sorgente' : 'visuale')
const avanzato = computed(() => richiedeSorgente(valore.value))
const sorgente = ref<HTMLTextAreaElement>()
const fileImmagine = ref<HTMLInputElement>()
const caricamento = ref(false)

/** Immagini in linea (`<img src alt>`): StarterKit non le comprende. */
const Immagine = Node.create({
  name: 'image',
  inline: true,
  group: 'inline',
  draggable: true,
  addAttributes() {
    return { src: { default: null }, alt: { default: null }, title: { default: null }, width: { default: null } }
  },
  parseHTML() {
    return [{ tag: 'img[src]' }]
  },
  renderHTML({ HTMLAttributes }) {
    return ['img', mergeAttributes(HTMLAttributes)]
  },
})

const editor = useEditor({
  content: modo.value === 'visuale' ? valore.value : '',
  extensions: [
    StarterKit.configure({
      link: { openOnClick: false, protocols: ['mailto'], HTMLAttributes: { rel: 'noopener', target: null } },
    }),
    Immagine,
  ],
  editorProps: {
    attributes: { class: 'form-control impostazioni-editor-area', 'aria-labelledby': `${id}-etichetta`, role: 'textbox', 'aria-multiline': 'true' },
  },
  onUpdate: ({ editor: e }) => {
    if (modo.value === 'visuale') valore.value = e.isEmpty ? '' : e.getHTML()
  },
})

onBeforeUnmount(() => editor.value?.destroy())

// Valore cambiato dall'esterno (caricamento, "Importa predefinito"): riallinea l'editor
watch(valore, (nuovo) => {
  const e = editor.value
  if (!e || modo.value !== 'visuale') return
  if (richiedeSorgente(nuovo)) {
    modo.value = 'sorgente'
    return
  }
  if (nuovo !== (e.isEmpty ? '' : e.getHTML())) e.commands.setContent(nuovo, { emitUpdate: false })
})

async function cambiaModo(nuovo: Modo): Promise<void> {
  if (nuovo === modo.value) return
  if (nuovo === 'visuale') {
    if (
      avanzato.value &&
      !(await conferma(
        "Questo contenuto usa HTML che l'editor visuale non conserva (tabelle, stili, istruzioni di template): passando all'editor visuale verrà semplificato. Continuare?",
        { titolo: 'Passa all’editor visuale', testoConferma: 'Semplifica e continua', pericolosa: true },
      ))
    ) {
      return
    }
    editor.value?.commands.setContent(valore.value, { emitUpdate: false })
    modo.value = 'visuale'
    // allinea subito il valore a ciò che l'editor conserva davvero
    if (editor.value) valore.value = editor.value.isEmpty ? '' : editor.value.getHTML()
    return
  }
  modo.value = nuovo
}

// --- Comandi della barra -----------------------------------------------------------------
interface Pulsante {
  etichetta: string
  icona: string
  attivo?: () => boolean
  azione: () => void
}
const catena = () => editor.value!.chain().focus()
const pulsanti = computed<Pulsante[][]>(() => [
  [
    { etichetta: 'Grassetto', icona: 'type-bold', attivo: () => !!editor.value?.isActive('bold'), azione: () => catena().toggleBold().run() },
    { etichetta: 'Corsivo', icona: 'type-italic', attivo: () => !!editor.value?.isActive('italic'), azione: () => catena().toggleItalic().run() },
    { etichetta: 'Sottolineato', icona: 'type-underline', attivo: () => !!editor.value?.isActive('underline'), azione: () => catena().toggleUnderline().run() },
  ],
  [
    { etichetta: 'Titolo di sezione', icona: 'type-h2', attivo: () => !!editor.value?.isActive('heading', { level: 2 }), azione: () => catena().toggleHeading({ level: 2 }).run() },
    { etichetta: 'Titolo di paragrafo', icona: 'type-h3', attivo: () => !!editor.value?.isActive('heading', { level: 3 }), azione: () => catena().toggleHeading({ level: 3 }).run() },
    { etichetta: 'Paragrafo', icona: 'paragraph', attivo: () => !!editor.value?.isActive('paragraph'), azione: () => catena().setParagraph().run() },
  ],
  [
    { etichetta: 'Elenco puntato', icona: 'list-ul', attivo: () => !!editor.value?.isActive('bulletList'), azione: () => catena().toggleBulletList().run() },
    { etichetta: 'Elenco numerato', icona: 'list-ol', attivo: () => !!editor.value?.isActive('orderedList'), azione: () => catena().toggleOrderedList().run() },
    { etichetta: 'Citazione', icona: 'quote', attivo: () => !!editor.value?.isActive('blockquote'), azione: () => catena().toggleBlockquote().run() },
  ],
  [
    { etichetta: 'Link', icona: 'link-45deg', attivo: () => !!editor.value?.isActive('link'), azione: apriLink },
    { etichetta: 'Rimuovi link', icona: 'x-circle', azione: () => catena().unsetLink().run() },
  ],
  [
    { etichetta: 'Annulla', icona: 'arrow-counterclockwise', azione: () => catena().undo().run() },
    { etichetta: 'Ripeti', icona: 'arrow-clockwise', azione: () => catena().redo().run() },
  ],
])

// --- Link ----------------------------------------------------------------------------------
const finestraLink = ref(false)
const urlLink = ref('')
const erroreLink = ref('')
function apriLink(): void {
  urlLink.value = (editor.value?.getAttributes('link').href as string | undefined) ?? ''
  erroreLink.value = ''
  finestraLink.value = true
}
function applicaLink(): void {
  const url = urlLink.value.trim()
  if (!url) {
    catena().extendMarkRange('link').unsetLink().run()
  } else if (!/^(https?:\/\/|mailto:|\{\{)/i.test(url)) {
    erroreLink.value = 'Inserisci un indirizzo che inizia con https://, http:// o mailto:.'
    return
  } else {
    catena().extendMarkRange('link').setLink({ href: url }).run()
  }
  finestraLink.value = false
}

// --- Segnaposti e immagini -----------------------------------------------------------------
function inserisci(testo: string): void {
  if (modo.value === 'visuale' && editor.value) {
    catena().insertContent(testo).run()
    return
  }
  const area = sorgente.value
  const r = inserisciInTesto(valore.value, testo, area?.selectionStart ?? valore.value.length, area?.selectionEnd)
  valore.value = r.valore
  requestAnimationFrame(() => {
    area?.focus()
    area?.setSelectionRange(r.cursore, r.cursore)
  })
}

async function caricaImmagine(evento: Event): Promise<void> {
  const input = evento.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (file.size > 2 * 1024 * 1024) {
    avvisi.mostra("L'immagine supera i 2 MB.", 'danger')
    return
  }
  caricamento.value = true
  try {
    const dati = new FormData()
    dati.append('file', file)
    const { url } = await api.post<{ url: string }>('/impostazioni/immagini-mail', dati)
    const alt = file.name.replace(/\.[^.]+$/, '')
    if (modo.value === 'visuale' && editor.value) {
      catena().insertContent({ type: 'image', attrs: { src: url, alt } }).run()
    } else {
      inserisci(`<img src="${url}" alt="${alt.replaceAll('"', '')}">`)
    }
  } catch (e) {
    avvisi.mostra(e instanceof Error ? e.message : 'Immagine non caricata.', 'danger')
  } finally {
    caricamento.value = false
  }
}
</script>

<template>
  <div class="mb-5">
    <div class="d-flex flex-wrap align-items-center gap-3 mb-2">
      <span :id="`${id}-etichetta`" class="form-label mb-0">{{ etichetta }}</span>
      <div class="nav nav-pills ms-auto" role="group" aria-label="Modalità dell'editor">
        <button
          v-for="m in (['visuale', 'sorgente', 'anteprima'] as Modo[])"
          :key="m"
          type="button"
          class="nav-link py-1 px-3"
          :class="{ active: modo === m }"
          :aria-pressed="modo === m"
          @click="cambiaModo(m)"
        >
          {{ m === 'visuale' ? 'Visuale' : m === 'sorgente' ? 'HTML' : 'Anteprima' }}
        </button>
      </div>
    </div>

    <div v-if="avanzato && modo === 'sorgente'" class="alert theme-info small py-2" role="note">
      <IconaBs nome="info-circle" class="me-2" />Il contenuto usa HTML avanzato (tabelle, stili o
      istruzioni di template): si modifica qui, nel sorgente, per non perderne parti.
    </div>

    <div v-if="modo !== 'anteprima'" class="impostazioni-editor-barra d-flex flex-wrap gap-2 mb-2" role="toolbar" :aria-label="`Formattazione: ${etichetta}`">
      <template v-if="modo === 'visuale'">
        <div v-for="(gruppo, g) in pulsanti" :key="g" class="btn-group" role="group">
          <button
            v-for="p in gruppo"
            :key="p.etichetta"
            type="button"
            class="btn btn-outline btn-sm theme-secondary"
            :class="{ active: p.attivo?.() }"
            :aria-pressed="p.attivo ? p.attivo() : undefined"
            :title="p.etichetta"
            :aria-label="p.etichetta"
            @mousedown.prevent
            @click="p.azione"
          >
            <IconaBs :nome="p.icona" />
          </button>
        </div>
      </template>
      <template v-if="immagini">
        <input ref="fileImmagine" type="file" accept="image/jpeg,image/png,image/gif,image/webp" class="d-none" @change="caricaImmagine" />
        <button type="button" class="btn btn-outline btn-sm theme-secondary" :disabled="caricamento" @click="fileImmagine?.click()">
          <span v-if="caricamento" class="spinner-border spinner-border-sm me-1" aria-hidden="true" />
          <IconaBs v-else nome="image" class="me-1" />Immagine
        </button>
      </template>
    </div>

    <div v-if="segnaposti.length && modo !== 'anteprima'" class="mb-2">
      <span class="small fg-2 me-2">Inserisci:</span>
      <button
        v-for="s in segnaposti"
        :key="s"
        type="button"
        class="btn btn-subtle btn-sm theme-secondary font-monospace me-2 mb-1"
        :title="`Inserisci ${segnaposto(s)}`"
        @mousedown.prevent
        @click="inserisci(segnaposto(s))"
      >
        {{ segnaposto(s) }}
      </button>
    </div>

    <EditorContent v-show="modo === 'visuale'" :editor="editor" class="impostazioni-editor" :class="{ 'is-invalid': errori.length }" :style="{ '--altezza-editor': altezza }" />
    <textarea
      v-if="modo === 'sorgente'"
      :id="`${id}-sorgente`"
      ref="sorgente"
      v-model="valore"
      class="form-control font-monospace small"
      :class="{ 'is-invalid': errori.length }"
      :style="{ minHeight: altezza }"
      spellcheck="false"
      :aria-labelledby="`${id}-etichetta`"
    />
    <iframe
      v-if="modo === 'anteprima'"
      class="impostazioni-editor-anteprima form-control p-0"
      :style="{ height: altezza }"
      sandbox=""
      :srcdoc="valore"
      :title="`Anteprima: ${etichetta}`"
    />
    <div v-for="e in errori" :key="e" class="invalid-feedback d-block">{{ e }}</div>

    <FinestraDialogo v-model:aperta="finestraLink" titolo="Link">
      <form id="form-link-editor" novalidate @submit.prevent="applicaLink">
        <label :for="`${id}-url`" class="form-label">Indirizzo</label>
        <input :id="`${id}-url`" v-model="urlLink" type="url" class="form-control" :class="{ 'is-invalid': erroreLink }" placeholder="https://…" />
        <div v-if="erroreLink" class="invalid-feedback d-block">{{ erroreLink }}</div>
        <div class="form-text">Lascia vuoto per togliere il link.</div>
      </form>
      <template #piede>
        <button type="button" class="btn btn-text theme-secondary" @click="finestraLink = false">Annulla</button>
        <button type="submit" form="form-link-editor" class="btn btn-solid theme-primary">Applica</button>
      </template>
    </FinestraDialogo>
  </div>
</template>

<style scoped>
.impostazioni-editor :deep(.impostazioni-editor-area) {
  min-height: var(--altezza-editor, 18rem);
  max-height: 70vh;
  overflow-y: auto;
}
.impostazioni-editor :deep(.impostazioni-editor-area img) {
  max-width: 100%;
  height: auto;
}
.impostazioni-editor :deep(.ProseMirror-selectednode) {
  outline: 2px solid var(--bs-primary-base, currentColor);
}
.impostazioni-editor.is-invalid :deep(.impostazioni-editor-area) {
  border-color: var(--bs-danger-base, #dc3545);
}
.impostazioni-editor-anteprima {
  width: 100%;
  background: #fff;
}
</style>
