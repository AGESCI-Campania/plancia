<script setup lang="ts">
/** Miniature delle foto di un modulo nel dettaglio del diario, con eliminazione se consentita. */
import { computed } from 'vue'

import { api, ErroreApi } from '@/api/http'
import IconaBs from '@/components/IconaBs.vue'
import { conferma } from '@/composables/conferma'
import type { DiarioDettaglio } from '@/components/diari/diari'
import { useAvvisiStore } from '@/stores/avvisi'

const props = defineProps<{ diario: DiarioDettaglio; modulo: string }>()
const emit = defineEmits<{ eliminato: [] }>()
const avvisi = useAvvisiStore()

const allegati = computed(() => props.diario.allegati.filter((a) => a.modulo === props.modulo))
const puoEliminare = computed(() => Boolean(props.diario.permessi?.puo_eliminare_allegati))

async function elimina(id: number, nome: string): Promise<void> {
  const ok = await conferma(`Eliminare la foto «${nome}»?`, {
    titolo: 'Elimina foto',
    testoConferma: 'Elimina',
    pericolosa: true,
  })
  if (!ok) return
  try {
    await api.delete(`/diari/${props.diario.id}/allegati/${id}`)
    avvisi.mostra('Foto eliminata.')
    emit('eliminato')
  } catch (e) {
    avvisi.mostra(e instanceof ErroreApi ? e.message : 'Eliminazione non riuscita.', 'danger')
  }
}
</script>

<template>
  <div v-if="allegati.length" class="mt-5 pt-5 border-top">
    <p class="small fg-2 mb-3">
      <IconaBs nome="paperclip" class="me-1" /><strong
        >{{ allegati.length }} {{ allegati.length === 1 ? 'allegato' : 'allegati' }}</strong
      >
    </p>
    <ul class="list-unstyled d-flex flex-wrap gap-3 mb-0">
      <li v-for="a in allegati" :key="a.id" class="position-relative plancia-diari-miniatura">
        <a
          v-if="a.mime.startsWith('image/')"
          :href="a.anteprima_url"
          target="_blank"
          rel="noopener"
          :title="a.nome"
        >
          <img
            :src="a.miniatura_url"
            loading="lazy"
            :alt="a.nome"
            class="rounded-4 border"
            width="90"
            height="90"
          />
        </a>
        <a
          v-else
          :href="a.download_url"
          class="d-flex flex-column align-items-center justify-content-center text-center small rounded-4 border bg-1 h-100 p-2"
          :title="a.nome"
        >
          <IconaBs nome="file-earmark" class="fs-xl mb-1" />{{ a.nome.slice(0, 22) }}
        </a>
        <button
          v-if="puoEliminare"
          type="button"
          class="btn btn-solid btn-xs theme-danger position-absolute top-0 end-0 m-1 p-1 lh-1"
          :aria-label="`Elimina la foto ${a.nome}`"
          @click="elimina(a.id, a.nome)"
        >
          <IconaBs nome="x-lg" />
        </button>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.plancia-diari-miniatura {
  width: 90px;
  height: 90px;
}
.plancia-diari-miniatura img {
  object-fit: cover;
}
</style>
