<script setup lang="ts">
/**
 * Navigazione tra i moduli del diario con la completezza calcolata dal backend
 * (`stato_moduli`: modulo salvato almeno una volta, obbligatorio o facoltativo per il tipo).
 * La relazione finale compare solo se `permessi.puo_vedere_relazione`.
 */
import { computed } from 'vue'

import IconaBs from '@/components/IconaBs.vue'
import type { DiarioDettaglio } from '@/composables/diarioCompilazione'

import { MODULI, percorsoModulo, type ChiaveModulo } from './elenco'

const props = defineProps<{ diario: DiarioDettaglio; attivo?: ChiaveModulo | 'allegati' }>()

const voci = computed(() => {
  const s = props.diario.stato_moduli
  const p = props.diario.permessi
  return MODULI.filter((m) => m.chiave !== 'relazione_finale' || p?.puo_vedere_relazione).map((m) => {
    const compilato = s ? Boolean(s[m.chiave]) : false
    const facoltativo =
      (m.chiave === 'impresa_2' && s?.impresa_2_obbligatoria === false) ||
      (m.chiave === 'missione' && s?.missione_obbligatoria === false)
    return { ...m, compilato, facoltativo, to: percorsoModulo(props.diario.id, m) }
  })
})
const fotoTotali = computed(() => props.diario.allegati?.length ?? 0)
</script>

<template>
  <nav aria-label="Moduli del diario" class="mb-6 nav-moduli">
    <ul class="nav nav-pills flex-nowrap">
      <li v-for="v in voci" :key="v.chiave" class="nav-item">
        <RouterLink
          :to="v.to"
          class="nav-link text-nowrap"
          :class="{ active: attivo === v.chiave }"
          :aria-current="attivo === v.chiave ? 'page' : undefined"
        >
          <IconaBs
            :nome="v.compilato ? 'check-circle-fill' : 'circle'"
            :class="attivo === v.chiave ? '' : v.compilato ? 'fg-success' : 'fg-3'"
            :etichetta="v.compilato ? 'compilato' : 'da compilare'"
            class="me-1"
          />
          <span class="fw-semibold me-1">{{ v.numero }}</span>{{ v.breve }}
          <small v-if="v.facoltativo" class="ms-1 fg-2">(facoltativo)</small>
        </RouterLink>
      </li>
      <li class="nav-item">
        <RouterLink
          :to="`/diari/${diario.id}/allegati`"
          class="nav-link text-nowrap"
          :class="{ active: attivo === 'allegati' }"
          :aria-current="attivo === 'allegati' ? 'page' : undefined"
        >
          <IconaBs nome="images" class="me-1" />Foto
          <span v-if="fotoTotali" class="badge theme-secondary ms-1">{{ fotoTotali }}</span>
        </RouterLink>
      </li>
    </ul>
  </nav>
</template>

<style scoped>
.nav-moduli {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: thin;
}
.nav-moduli .nav {
  width: max-content;
  min-width: 100%;
}
</style>
