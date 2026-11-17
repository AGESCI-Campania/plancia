<script setup lang="ts">
/** Editor di un template email: oggetto, attivo, corpo HTML (Tiptap) con i tag del template. */
import { computed, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { api } from '@/api/http'
import CampoForm from '@/components/CampoForm.vue'
import FinestraDialogo from '@/components/FinestraDialogo.vue'
import IconaBs from '@/components/IconaBs.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import ImpostazioniEditorHtml from '@/components/impostazioni/ImpostazioniEditorHtml.vue'
import ImpostazioniInterruttore from '@/components/impostazioni/ImpostazioniInterruttore.vue'
import type { TemplateEmail } from '@/components/impostazioni/tipi'
import { conferma } from '@/composables/conferma'
import { dataOra } from '@/composables/impostazioni-editor'
import { useSalvataggio } from '@/composables/impostazioni-salvataggio'
import { useRichiesta } from '@/composables/richiesta'

const props = defineProps<{ chiave: string }>()
const router = useRouter()

const template = useRichiesta(() => api.get<TemplateEmail>(`/impostazioni/mail/${props.chiave}`))
const oggetto = ref('')
const attivo = ref(true)
const corpo = ref('')
const caricato = ref(false)

function applica(t: TemplateEmail | null): void {
  if (!t) return
  oggetto.value = t.oggetto ?? ''
  attivo.value = t.attivo ?? true
  corpo.value = t.corpo_html ?? ''
  caricato.value = true
}

watch(
  () => props.chiave,
  async () => {
    caricato.value = false
    applica(await template.esegui())
  },
  { immediate: true },
)

const t = computed(() => template.dati.value)
const salvataggio = useSalvataggio()
async function salva(): Promise<void> {
  const r = await salvataggio.esegui(
    () => api.put<TemplateEmail>(`/impostazioni/mail/${props.chiave}`, { oggetto: oggetto.value, corpo_html: corpo.value, attivo: attivo.value }),
    'Template salvato.',
  )
  if (r) {
    template.dati.value = r
    applica(r)
  }
}

const azione = useSalvataggio()
async function importa(): Promise<void> {
  const r = await azione.esegui(() => api.post<TemplateEmail>(`/impostazioni/mail/${props.chiave}/importa`), 'Template importato dal file predefinito.')
  if (r) {
    template.dati.value = r
    applica(r)
  }
}

async function elimina(): Promise<void> {
  if (!(await conferma('Eliminare il template personalizzato? Verrà usato di nuovo il file predefinito.', { testoConferma: 'Elimina', pericolosa: true }))) return
  if ((await azione.esegui(() => api.delete(`/impostazioni/mail/${props.chiave}`).then(() => true), 'Template eliminato: torna il file predefinito.')) !== null) {
    await router.push('/impostazioni/template-email')
  }
}

const finestraCopia = ref(false)
const destinazione = ref('')
async function copia(): Promise<void> {
  if (!destinazione.value) return
  const r = await azione.esegui(
    () => api.post<TemplateEmail>(`/impostazioni/mail/${props.chiave}/copia`, { target_chiave: destinazione.value }),
    `Template duplicato in «${destinazione.value}».`,
  )
  if (r) {
    finestraCopia.value = false
    await router.push(`/impostazioni/mail/${r.chiave}`)
  }
}
</script>

<template>
  <StatoCaricamento :in-corso="template.inCorso.value && !caricato" :errore="template.errore.value" @riprova="template.esegui">
    <template v-if="t">
      <div class="d-flex flex-wrap align-items-start gap-3 mb-5">
        <div class="flex-grow-1">
          <h1 class="h3 mb-1">Template email <code>{{ chiave }}</code></h1>
          <small v-if="t.esiste" class="fg-2">Aggiornato il {{ dataOra(t.aggiornato_at) }}</small>
          <small v-else class="text-warning"><IconaBs nome="plus-circle" class="me-1" />Nuovo template, non ancora salvato: finché non lo salvi si usa il file predefinito.</small>
        </div>
        <div class="d-flex flex-wrap gap-2">
          <button v-if="!t.esiste" type="button" class="btn btn-outline btn-sm theme-secondary" :disabled="azione.inCorso.value" @click="importa">
            <IconaBs nome="download" class="me-1" />Importa da file
          </button>
          <button v-if="t.esiste && t.chiavi_senza_record.length" type="button" class="btn btn-outline btn-sm theme-primary" @click="finestraCopia = true">
            <IconaBs nome="copy" class="me-1" />Crea nuovo da attuale
          </button>
          <button v-if="t.esiste" type="button" class="btn btn-outline btn-sm theme-danger" :disabled="azione.inCorso.value" @click="elimina">
            <IconaBs nome="trash" class="me-1" />Elimina (ripristina predefinito)
          </button>
          <RouterLink to="/impostazioni/template-email" class="btn btn-text btn-sm theme-secondary">
            <IconaBs nome="arrow-left" class="me-1" />Template email
          </RouterLink>
        </div>
      </div>

      <form novalidate @submit.prevent="salva">
        <section class="card mb-6">
          <div class="card-body">
            <div class="row align-items-start">
              <div class="md:col-9">
                <CampoForm v-model="oggetto" etichetta="Oggetto email" obbligatorio :errori="salvataggio.errori.value.oggetto" />
              </div>
              <div class="md:col-3 md:pt-6">
                <ImpostazioniInterruttore v-model="attivo" etichetta="Attivo" descrizione="Se disattivato si usa il file predefinito." />
              </div>
            </div>
            <ImpostazioniEditorHtml
              v-model="corpo"
              etichetta="Corpo HTML"
              :segnaposti="t.tag_disponibili"
              immagini
              :errori="salvataggio.errori.value.corpo_html"
              altezza="24rem"
            />
            <div v-for="(m, campo) in salvataggio.errori.value" :key="campo">
              <div v-if="!['oggetto', 'corpo_html'].includes(String(campo))" class="invalid-feedback d-block">{{ m.join(' ') }}</div>
            </div>
            <div class="d-flex justify-content-end gap-3">
              <RouterLink to="/impostazioni/template-email" class="btn btn-outline theme-secondary">Annulla</RouterLink>
              <button type="submit" class="btn btn-solid theme-primary" :disabled="salvataggio.inCorso.value">
                <IconaBs nome="check-lg" class="me-1" />Salva template
              </button>
            </div>
          </div>
        </section>
      </form>

      <FinestraDialogo v-model:aperta="finestraCopia" titolo="Crea nuovo da attuale">
        <form id="form-copia-template" novalidate @submit.prevent="copia">
          <p class="small fg-2">
            Scegli la chiave di destinazione: il template <code>{{ chiave }}</code> verrà duplicato
            (oggetto e corpo HTML) come punto di partenza.
          </p>
          <label for="destinazione-copia" class="form-label">Chiave di destinazione</label>
          <select id="destinazione-copia" v-model="destinazione" class="form-control" required>
            <option value="" disabled>— Seleziona —</option>
            <option v-for="k in t.chiavi_senza_record" :key="k" :value="k">{{ k }}</option>
          </select>
        </form>
        <template #piede>
          <button type="button" class="btn btn-text theme-secondary" @click="finestraCopia = false">Annulla</button>
          <button type="submit" form="form-copia-template" class="btn btn-solid theme-primary" :disabled="!destinazione || azione.inCorso.value">
            <IconaBs nome="copy" class="me-1" />Duplica e apri l'editor
          </button>
        </template>
      </FinestraDialogo>
    </template>
  </StatoCaricamento>
</template>
