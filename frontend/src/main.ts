import 'bootstrap/dist/css/bootstrap.css'
import '@/theme/plancia.scss'
// Bootstrap 6 è solo ESM: importarlo attiva la data API (menu, tooltip…) sui nodi creati da Vue.
import 'bootstrap'

import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from '@/App.vue'
import { router } from '@/router'
import { useSitoStore } from '@/stores/sito'

const app = createApp(App)
app.use(createPinia())
app.use(router)
// Titolo, footer, manutenzione e versione del server: anche prima del login.
void useSitoStore().carica()
app.mount('#app')
