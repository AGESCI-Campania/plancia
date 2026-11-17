<script setup lang="ts">
/** Scheda "Template email": tutte le chiavi, personalizzate o dal file predefinito. */
import { onMounted } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { api } from '@/api/http'
import IconaBs from '@/components/IconaBs.vue'
import StatoCaricamento from '@/components/StatoCaricamento.vue'
import type { RigaTemplate } from '@/components/impostazioni/tipi'
import { useSalvataggio } from '@/composables/impostazioni-salvataggio'
import { useRichiesta } from '@/composables/richiesta'

const router = useRouter()
const elenco = useRichiesta(() => api.get<RigaTemplate[]>('/impostazioni/mail'))
onMounted(elenco.esegui)
const importazione = useSalvataggio()

async function importa(chiave: string): Promise<void> {
  const r = await importazione.esegui(() => api.post(`/impostazioni/mail/${chiave}/importa`), `Template «${chiave}» importato dal file predefinito.`)
  if (r) await router.push(`/impostazioni/mail/${chiave}`)
}
</script>

<template>
  <section class="card mb-6" aria-labelledby="titolo-template">
    <div class="card-body">
      <div class="d-flex align-items-center gap-3 mb-4">
        <h2 id="titolo-template" class="h5 mb-0"><IconaBs nome="file-earmark-text" class="me-2" />Template email</h2>
        <span class="badge theme-secondary">{{ elenco.dati.value?.length ?? 0 }}</span>
      </div>
      <p class="small fg-2">
        Senza personalizzazione viene usato il file predefinito. I tag tra doppie graffe vengono
        sostituiti all'invio.
      </p>
      <StatoCaricamento :in-corso="elenco.inCorso.value" :errore="elenco.errore.value" @riprova="elenco.esegui">
        <ul class="list-group">
          <li v-for="t in elenco.dati.value" :key="t.chiave" class="list-group-item py-4">
            <div class="d-flex flex-wrap align-items-start gap-3">
              <div class="flex-grow-1" style="min-width: 14rem">
                <code>{{ t.chiave }}</code>
                <span v-if="!t.esiste" class="badge theme-secondary ms-2" title="Usa il file predefinito">predefinito</span>
                <span v-else-if="t.attivo" class="badge theme-success ms-2">attivo</span>
                <span v-else class="badge theme-warning ms-2">disattivato</span>
                <div class="mt-1">
                  <template v-if="t.esiste">{{ t.oggetto }}</template>
                  <em v-else class="fg-2">dal file predefinito</em>
                </div>
                <div class="small fg-2 mt-1">
                  Tag: <span class="font-monospace">{{ t.tag_disponibili.join(', ') || '—' }}</span>
                </div>
              </div>
              <div class="d-flex flex-wrap gap-2">
                <RouterLink v-if="t.esiste" :to="`/impostazioni/mail/${t.chiave}`" class="btn btn-outline btn-sm theme-primary">
                  <IconaBs nome="pencil" class="me-1" />Modifica
                </RouterLink>
                <template v-else>
                  <button type="button" class="btn btn-outline btn-sm theme-secondary" :disabled="importazione.inCorso.value" title="Importa il file predefinito e apri l'editor" @click="importa(t.chiave)">
                    <IconaBs nome="download" class="me-1" />Importa da file
                  </button>
                  <RouterLink :to="`/impostazioni/mail/${t.chiave}`" class="btn btn-outline btn-sm theme-success" title="Crea un template personalizzato da zero">
                    <IconaBs nome="plus-lg" class="me-1" />Crea nuovo
                  </RouterLink>
                </template>
              </div>
            </div>
          </li>
        </ul>
      </StatoCaricamento>
    </div>
  </section>
</template>
