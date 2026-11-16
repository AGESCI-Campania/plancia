<script setup lang="ts">
/**
 * Layout delle pagine autenticate: header con stato offline, sidebar (fissa da lg, drawer
 * sotto lg), breadcrumb dalla rotta, banner di impersonazione e manutenzione, footer.
 */
import { computed, ref, watch } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'

import { api } from '@/api/http'
import IconaBs from '@/components/IconaBs.vue'
import { useOnline } from '@/composables/online'
import { vociMenu } from '@/layouts/menu'
import PiePagina from '@/components/PiePagina.vue'
import { inAttesa } from '@/offline/coda'
import { useSessioneStore } from '@/stores/sessione'
import { useSitoStore } from '@/stores/sito'
import emblema from '@/assets/EMBLEMA_CAMPANIA_WHITE.svg'

const sessione = useSessioneStore()
const sito = useSitoStore()
const route = useRoute()
const router = useRouter()
const online = useOnline()

const sidebar = ref<HTMLDialogElement>()
const compressa = ref(leggiPreferenza())
const sezioni = computed(() => (sessione.me ? vociMenu(sessione.me) : []))
const breadcrumb = computed(
  () => (route.meta.breadcrumb as { label: string; to?: string }[] | undefined) ?? [],
)
const iniziale = computed(() => (sessione.me?.nome_completo ?? '?').charAt(0).toUpperCase())

function leggiPreferenza(): boolean {
  try {
    return localStorage.getItem('plancia:sidebar-compressa') === '1'
  } catch {
    return false
  }
}
watch(compressa, (valore) => {
  try {
    localStorage.setItem('plancia:sidebar-compressa', valore ? '1' : '0')
  } catch {
    // preferenza non salvata: non è un problema
  }
})

function apriMenu(): void {
  sidebar.value?.showModal()
}
function chiudiMenu(): void {
  if (sidebar.value?.open && window.matchMedia('(max-width: 1023.98px)').matches) sidebar.value.close()
}
watch(() => route.fullPath, chiudiMenu)

function attiva(to: string): boolean {
  return to === '/' ? route.path === '/' : route.path.startsWith(to)
}

async function cambiaRuolo(ruolo: string): Promise<void> {
  await sessione.cambiaRuolo(ruolo)
  await router.push('/')
}

async function esci(): Promise<void> {
  await sessione.esci()
  await router.push({ name: 'accesso' })
}

async function terminaImpersonazione(): Promise<void> {
  await api.post('/me/impersonazione/termina')
  window.location.assign('/')
}
</script>

<template>
  <header>
    <div
      v-if="sessione.me?.impersonato_da"
      class="alert theme-warning rounded-0 mb-0 py-2 d-flex align-items-center gap-3"
      role="status"
    >
      <IconaBs nome="incognito" />
      <span>Stai operando come <strong>{{ sessione.me.nome_completo }}</strong>
        (impersonazione avviata da {{ sessione.me.impersonato_da.nome_completo }}).</span>
      <button type="button" class="btn btn-solid btn-sm theme-warning ms-auto" @click="terminaImpersonazione">
        Torna al tuo account
      </button>
    </div>
    <div
      v-if="sito.sito?.manutenzione?.attiva"
      class="alert theme-danger rounded-0 mb-0 py-2"
      role="status"
    >
      <IconaBs nome="cone-striped" class="me-2" />{{
        sito.sito.manutenzione.messaggio || 'Plancia è in manutenzione.'
      }}
    </div>

    <div class="ag-header-top px-5 py-3 d-flex flex-wrap align-items-center">
      <RouterLink to="/" class="ag-header-brand my-3 lg:my-0">
        <img :src="emblema" alt="" />
        <span class="d-none sm:d-inline">{{ sito.sito?.titolo ?? 'Plancia' }}</span>
      </RouterLink>
      <div class="ms-auto d-flex align-items-center gap-3">
        <span v-if="!online" class="badge theme-danger" role="status">
          <IconaBs nome="wifi-off" class="me-1" />Offline
        </span>
        <span v-if="inAttesa > 0" class="badge theme-warning" role="status">
          <IconaBs nome="cloud-upload" class="me-1" />{{ inAttesa }} in attesa
        </span>
        <button
          type="button"
          class="ag-header-toggler lg:d-none"
          aria-controls="agSidebar"
          aria-label="Apri menu"
          @click="apriMenu"
        >
          <IconaBs nome="list" />
        </button>
      </div>
    </div>
    <div v-if="breadcrumb.length" class="ag-header-bottom">
      <nav aria-label="Percorso" class="breadcrumb-agesci">
        <ol class="breadcrumb mb-0 py-3 px-5">
          <template v-for="(voce, i) in breadcrumb" :key="i">
            <li v-if="voce.to" class="breadcrumb-item">
              <RouterLink class="breadcrumb-link" :to="voce.to">{{ voce.label }}</RouterLink>
            </li>
            <li v-else class="breadcrumb-item" aria-current="page">
              <span class="breadcrumb-link active">{{ voce.label }}</span>
            </li>
            <li v-if="i < breadcrumb.length - 1" class="breadcrumb-divider" aria-hidden="true" />
          </template>
        </ol>
      </nav>
    </div>
  </header>

  <div class="d-flex flex-grow-1 overflow-hidden">
    <dialog
      id="agSidebar"
      ref="sidebar"
      class="ag-sidebar ag-sidebar--dark lg:drawer drawer-start"
      :class="{ 'ag-sidebar--collapsed': compressa }"
      aria-label="Menu laterale"
    >
      <button
        type="button"
        class="ag-sidebar__toggle d-none lg:d-flex"
        :aria-expanded="!compressa"
        aria-controls="agSidebar"
        :aria-label="compressa ? 'Espandi menu laterale' : 'Comprimi menu laterale'"
        @click="compressa = !compressa"
      >
        <IconaBs nome="layout-sidebar" />
        <span class="ag-sidebar__toggle-label ms-3">Menu</span>
      </button>
      <button type="button" class="ag-sidebar__close lg:d-none" aria-label="Chiudi menu laterale" @click="sidebar?.close()">
        <IconaBs nome="x-lg" />
      </button>

      <ul class="ag-sidebar__nav">
        <template v-for="(sezione, s) in sezioni" :key="s">
          <li v-if="sezione.titolo" class="ag-sidebar__section-title">{{ sezione.titolo }}</li>
          <li v-for="voce in sezione.voci" :key="voce.to">
            <a v-if="voce.esterno" :href="voce.to" target="_blank" rel="noopener" class="ag-sidebar__nav-link">
              <IconaBs :nome="voce.icona" /><span class="ag-sidebar__label">{{ voce.etichetta }}</span>
            </a>
            <RouterLink
              v-else
              :to="voce.to"
              class="ag-sidebar__nav-link"
              :class="{ active: attiva(voce.to) }"
              :title="compressa ? voce.etichetta : undefined"
            >
              <IconaBs :nome="voce.icona" /><span class="ag-sidebar__label">{{ voce.etichetta }}</span>
            </RouterLink>
          </li>
        </template>
      </ul>

      <div v-if="sessione.me" class="ag-sidebar__user">
        <a
          href="#"
          class="ag-sidebar__user-toggle"
          role="button"
          data-bs-toggle="menu"
          data-bs-placement="top-start"
          data-bs-strategy="fixed"
          aria-expanded="false"
          @click.prevent
        >
          <span class="ag-sidebar__user-avatar" :class="`avatar-${sessione.me.ruolo.chiave}`" aria-hidden="true">
            {{ iniziale }}
          </span>
          <span class="ag-sidebar__label">
            {{ sessione.me.nome_completo }}<br />
            <small class="opacity-75">{{ sessione.me.ruolo.etichetta }}</small>
          </span>
        </a>
        <div class="menu shadow" data-bs-theme="dark">
          <span class="menu-text">
            <strong>{{ sessione.me.nome_completo }}</strong><br />
            <small class="fg-2">{{ sessione.me.email }}</small>
          </span>
          <template v-if="sessione.me.ruoli_attivi.length > 1">
            <hr class="menu-divider" />
            <span class="menu-header">Opera come</span>
            <button
              v-for="r in sessione.me.ruoli_attivi"
              :key="r.chiave"
              type="button"
              class="menu-item"
              :class="{ active: r.chiave === sessione.me.ruolo.chiave }"
              @click="cambiaRuolo(r.chiave)"
            >
              {{ r.etichetta }}
            </button>
          </template>
          <hr class="menu-divider" />
          <RouterLink class="menu-item" to="/profilo"><IconaBs nome="person" class="me-2" />Profilo</RouterLink>
          <RouterLink class="menu-item" to="/profilo/sicurezza">
            <IconaBs nome="shield-check" class="me-2" />Password e sicurezza
          </RouterLink>
          <hr class="menu-divider" />
          <button type="button" class="menu-item text-danger" @click="esci">
            <IconaBs nome="box-arrow-right" class="me-2" />Esci
          </button>
        </div>
      </div>
    </dialog>

    <div class="ag-scroll-area flex-grow-1">
      <main class="container py-7">
        <RouterView />
      </main>
      <PiePagina />
    </div>
  </div>
</template>
