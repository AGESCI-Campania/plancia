<script setup lang="ts">
/** Ultimi accessi (LoginEvent): data, esito, IP ed eventualmente provider. */
import { coloreEsitoAccesso, dataOra } from '@/components/utenti/formato'
import type { LoginEvent } from '@/components/utenti/tipi'

withDefaults(defineProps<{ accessi: LoginEvent[]; conProvider?: boolean }>(), { conProvider: false })
</script>

<template>
  <p v-if="!accessi.length" class="fg-2 mb-0">Nessun evento registrato.</p>
  <div v-else class="table-responsive">
    <table class="table table-sm md:table-stacked mb-0">
      <thead>
        <tr>
          <th scope="col">Data</th>
          <th scope="col">Esito</th>
          <th scope="col">IP</th>
          <th v-if="conProvider" scope="col">Provider</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="ev in accessi" :key="ev.id">
          <td data-cell="Data">{{ dataOra(ev.creato_at) }}</td>
          <td data-cell="Esito">
            <span class="badge" :class="`theme-${coloreEsitoAccesso(ev.esito)}`">{{ ev.esito_display }}</span>
          </td>
          <td data-cell="IP"><code>{{ ev.ip || '—' }}</code></td>
          <td v-if="conProvider" data-cell="Provider">{{ ev.provider || 'email' }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
