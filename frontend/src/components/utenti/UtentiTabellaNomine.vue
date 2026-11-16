<script setup lang="ts">
/**
 * Storico delle nomine: ruolo, stato (attiva, scaduta, revocata, da Sestante), chi ha
 * nominato, edizione, scadenza, data. `revocabile` decide dove mostrare "Revoca".
 */
import IconaBs from '@/components/IconaBs.vue'
import { data } from '@/components/utenti/formato'
import type { Nomina } from '@/components/utenti/tipi'

withDefaults(defineProps<{ nomine: Nomina[]; revocabile?: (n: Nomina) => boolean }>(), {
  revocabile: () => false,
})
defineEmits<{ revoca: [n: Nomina] }>()

function stato(n: Nomina): { testo: string; colore: string } {
  if (!n.attiva) return { testo: 'Revocata', colore: 'secondary' }
  if (n.scaduta) return { testo: 'Scaduta', colore: 'warning' }
  return { testo: 'Attiva', colore: 'success' }
}
</script>

<template>
  <p v-if="!nomine.length" class="fg-2 mb-0">Nessuna nomina registrata.</p>
  <div v-else class="table-responsive">
    <table class="table table-sm md:table-stacked mb-0">
      <thead>
        <tr>
          <th scope="col">Ruolo</th>
          <th scope="col">Stato</th>
          <th scope="col">Nominato da</th>
          <th scope="col">Edizione</th>
          <th scope="col">Scadenza</th>
          <th scope="col">Data</th>
          <th scope="col"><span class="visually-hidden">Azioni</span></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="n in nomine" :key="n.id">
          <td data-cell="Ruolo">{{ n.ruolo.etichetta }}</td>
          <td data-cell="Stato">
            <span class="badge" :class="`theme-${stato(n).colore}`">{{ stato(n).testo }}</span>
            <span v-if="n.da_sso" class="badge theme-info ms-1" title="Ruolo assegnato da Sestante">
              <IconaBs nome="shield-check" class="me-1" />Sestante
            </span>
          </td>
          <td data-cell="Nominato da">{{ n.nominato_da?.nome_completo ?? '—' }}</td>
          <td data-cell="Edizione">{{ n.edizione ?? '—' }}</td>
          <td data-cell="Scadenza">{{ data(n.scadenza) }}</td>
          <td data-cell="Data">{{ data(n.creato_at) }}</td>
          <td class="text-end">
            <button
              v-if="revocabile(n)"
              type="button"
              class="btn btn-text btn-sm theme-danger"
              @click="$emit('revoca', n)"
            >
              Revoca<span class="visually-hidden"> la nomina {{ n.ruolo.etichetta }}</span>
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
