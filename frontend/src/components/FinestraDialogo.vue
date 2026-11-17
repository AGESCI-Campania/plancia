<script setup lang="ts">
/**
 * Finestra modale Bootstrap 6 sul <dialog> nativo (focus, Esc e backdrop gestiti dal browser).
 * `v-model:aperta` la apre e la chiude; `chiusa` segnala la chiusura da Esc o dal pulsante.
 */
import { onMounted, ref, useId, watch } from 'vue'

const props = withDefaults(defineProps<{ titolo: string; chiudibile?: boolean }>(), {
  chiudibile: true,
})
const aperta = defineModel<boolean>('aperta', { default: false })
const emit = defineEmits<{ chiusa: [] }>()
const dialogo = ref<HTMLDialogElement>()
const idTitolo = useId()

function sincronizza(valore: boolean): void {
  const d = dialogo.value
  if (!d) return
  if (valore && !d.open) d.showModal()
  if (!valore && d.open) d.close()
}

onMounted(() => sincronizza(aperta.value))
watch(aperta, sincronizza)

function annulla(evento: Event): void {
  if (!props.chiudibile) evento.preventDefault()
}

function chiudi(): void {
  aperta.value = false
  emit('chiusa')
}
</script>

<template>
  <dialog ref="dialogo" class="dialog" :aria-labelledby="idTitolo" @cancel="annulla" @close="chiudi">
    <div class="dialog-header">
      <h2 :id="idTitolo" class="dialog-title h5">{{ titolo }}</h2>
      <button v-if="chiudibile" type="button" class="btn-close" aria-label="Chiudi" @click="chiudi" />
    </div>
    <!-- Contenuto solo a finestra aperta: i campi chiusi non restano nel DOM (etichette duplicate) -->
    <div v-if="aperta" class="dialog-body">
      <slot />
    </div>
    <div v-if="aperta && $slots.piede" class="dialog-footer">
      <slot name="piede" />
    </div>
  </dialog>
</template>
