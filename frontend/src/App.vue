<script setup lang="ts">
import { RouterView } from 'vue-router'

import AggiornamentoApp from '@/components/AggiornamentoApp.vue'
import AvvisiToast from '@/components/AvvisiToast.vue'
import ConfermaDialogo from '@/components/ConfermaDialogo.vue'
import RiautenticazioneDialogo from '@/components/RiautenticazioneDialogo.vue'
</script>

<template>
  <RouterView />
  <AggiornamentoApp />
  <RiautenticazioneDialogo />
  <ConfermaDialogo />
  <AvvisiToast />
</template>
