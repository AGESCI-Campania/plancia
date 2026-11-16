<script setup lang="ts">
// Moduli 3 e 4 — 1ª e 2ª impresa: racconto, posti d'azione, specialità e brevetti, foto.
import { computed } from 'vue'

import type { components } from '@/api/schema'
import { nuovaRiga } from '@/composables/moduloDiario'
import { usePaginaModulo } from '@/composables/paginaModulo'

import CampoModulo from './CampoModulo.vue'
import GalleriaFoto from './GalleriaFoto.vue'
import PaginaModulo from './PaginaModulo.vue'
import RigheRipetute from './RigheRipetute.vue'

type Schemi = components['schemas']
type Posto = Omit<Schemi['PostoAzioneSchema'], 'id'> & { id: number | null; _k?: string }
type Esito = Omit<Schemi['EsitoSpecialitaSchema'], 'id' | 'tipo'> & { id: number | null; tipo?: string; _k?: string }
type Impresa = Omit<Schemi['ImpresaSchema'], 'posti_azione' | 'specialita' | 'brevetti'> & {
  posti_azione: Posto[]
  specialita: Esito[]
  brevetti: Esito[]
}

const props = defineProps<{ id: string; numero: 1 | 2 }>()
const chiave = props.numero === 1 ? 'impresa_1' : 'impresa_2'
const pagina = usePaginaModulo<Impresa>(props.id, chiave, {
  righeVuote: {
    posti_azione: (r) => !String(r.chi ?? '').trim() && !String(r.cosa ?? '').trim(),
    // Specialità e brevetti si inviano quando è scelto il nome
    specialita: (r) => !r.nome,
    brevetti: (r) => !r.nome,
  },
})
const { diario, opzioni, modulo, solaLettura } = pagina
const { dati } = modulo
// Alias non nullo per il template (usato solo dentro `v-if="dati"`)
const d = computed(() => dati.value as Impresa)

const facoltativa = computed(() => props.numero === 2 && diario.value?.stato_moduli?.impresa_2_obbligatoria === false)
const scelte = (valori: string[] | undefined) => (valori ?? []).map((v) => ({ valore: v, etichetta: v }))
const specialita = computed(() => scelte(opzioni.value?.specialita_individuali))
const brevetti = computed(() => scelte(opzioni.value?.brevetti))
const nuovoPosto = (): Posto => nuovaRiga({ id: null, chi: '', cosa: '' })
const nuovoEsito = (): Esito => nuovaRiga({ id: null, chi: '', nome: '', stato: 'in_cammino' })

const ESITI = [
  {
    lista: 'specialita',
    titolo: 'Specialità individuali',
    spiegazione: 'Specialità individuali conquistate, non conquistate o in cammino durante questa impresa.',
    etichetta: 'Specialità',
    vuota: '— Scegli specialità —',
    aggiungi: 'Aggiungi specialità',
    nomeRiga: 'specialità',
  },
  {
    lista: 'brevetti',
    titolo: 'Brevetti di competenza',
    spiegazione: 'Brevetti di competenza conquistati, non conquistati o in cammino durante questa impresa.',
    etichetta: 'Brevetto',
    vuota: '— Scegli brevetto —',
    aggiungi: 'Aggiungi brevetto',
    nomeRiga: 'brevetto',
  },
] as const
</script>

<template>
  <PaginaModulo
    :diario-id="id"
    :chiave="chiave"
    :diario="diario"
    :errore-diario="pagina.errore.value"
    :in-corso-diario="pagina.inCorso.value"
    :modulo="modulo"
    :sola-lettura="solaLettura"
    :avviso-sola-lettura="pagina.avvisoSolaLettura.value"
    @ricarica-diario="pagina.ricaricaDiario()"
  >
    <div v-if="facoltativa" class="alert theme-info" role="note">
      Per i diari di rinnovo la 2ª impresa è facoltativa: compilala solo se l'avete svolta.
    </div>
    <template v-if="dati">
      <div class="row g-4 mb-6">
        <div class="col-12">
          <CampoModulo
            v-model="d.titolo"
            etichetta="Titolo"
            segnaposto="Titolo dell'impresa"
            :maxlength="200"
            :errori="modulo.erroriDi('titolo')"
            :sola-lettura="solaLettura"
          />
        </div>
        <div class="col-12 sm:col-6">
          <CampoModulo v-model="d.data_inizio" tipo="date" etichetta="Data inizio" :errori="modulo.erroriDi('data_inizio')" :sola-lettura="solaLettura" />
        </div>
        <div class="col-12 sm:col-6">
          <CampoModulo v-model="d.data_fine" tipo="date" etichetta="Data fine" :errori="modulo.erroriDi('data_fine')" :sola-lettura="solaLettura" />
        </div>
        <div class="col-12">
          <CampoModulo
            v-model="d.perche"
            tipo="textarea"
            :maxlength="10000"
            etichetta="Perché"
            aiuto="Descriveteci perché avete deciso di fare questa impresa: cosa vi piaceva, cosa vi ha spinto a farla, ecc."
            :errori="modulo.erroriDi('perche')"
            :sola-lettura="solaLettura"
          />
        </div>
        <div class="col-12">
          <CampoModulo
            v-model="d.come"
            tipo="textarea"
            :maxlength="10000"
            etichetta="Come"
            aiuto="Come avete progettato il vostro lavoro, come avete acquisito le competenze necessarie e quali sono, come vi siete divisi i posti d'azione in squadriglia, ecc."
            :errori="modulo.erroriDi('come')"
            :sola-lettura="solaLettura"
          />
        </div>
        <div class="col-12">
          <CampoModulo
            v-model="d.cosa"
            tipo="textarea"
            :maxlength="10000"
            etichetta="Cosa"
            aiuto="Quello che avete fatto per realizzare l'impresa, dove l'avete realizzata e tutte le informazioni utili per poterci far comprendere il vostro lavoro."
            :errori="modulo.erroriDi('cosa')"
            :sola-lettura="solaLettura"
          />
        </div>
        <div class="col-12">
          <CampoModulo
            v-model="d.link_esterno"
            tipo="url"
            etichetta="Link esterno (video/materiale)"
            segnaposto="https://youtube.com/..."
            :maxlength="200"
            aiuto="Se avete realizzato un video o avete del materiale da condividere, inserite qui il link a YouTube / OneDrive / Google Drive / ecc. per poterlo visionare."
            :errori="modulo.erroriDi('link_esterno')"
            :sola-lettura="solaLettura"
          />
        </div>
      </div>

      <fieldset class="mb-6">
        <legend class="h5 border-bottom pb-2 mb-2">Posti d'azione</legend>
        <p class="fg-2 small mb-4">Per ogni posto d'azione indicate chi lo ha svolto e cosa ha fatto.</p>
        <RigheRipetute
          v-model="d.posti_azione"
          :nuova="nuovoPosto"
          nome-riga="posto d'azione"
          etichetta-aggiungi="Aggiungi posto d'azione"
          messaggio-vuoto="Nessun posto d'azione inserito."
          :sola-lettura="solaLettura"
        >
          <template #default="{ riga }">
            <div class="col-12 md:col-5">
              <CampoModulo
                v-model="riga.chi"
                etichetta="Chi"
                segnaposto="Nome (es. Mario Rossi)"
                :maxlength="200"
                :errori="modulo.erroriRiga('posti_azione', riga).chi"
                :sola-lettura="solaLettura"
              />
            </div>
            <div class="col-12 md:col-7">
              <CampoModulo
                v-model="riga.cosa"
                etichetta="Cosa"
                segnaposto="Posto d'azione (es. Fotografia)"
                :maxlength="300"
                :errori="modulo.erroriRiga('posti_azione', riga).cosa"
                :sola-lettura="solaLettura"
              />
            </div>
          </template>
        </RigheRipetute>
      </fieldset>

      <fieldset v-for="e in ESITI" :key="e.lista" class="mb-6">
        <legend class="h5 border-bottom pb-2 mb-2">{{ e.titolo }}</legend>
        <p class="fg-2 small mb-4">{{ e.spiegazione }}</p>
        <RigheRipetute
          v-model="d[e.lista]"
          :nuova="nuovoEsito"
          :nome-riga="e.nomeRiga"
          :etichetta-aggiungi="e.aggiungi"
          :messaggio-vuoto="`Nessun${e.lista === 'brevetti' ? ' brevetto' : 'a specialità'} inserit${e.lista === 'brevetti' ? 'o' : 'a'}.`"
          :sola-lettura="solaLettura"
        >
          <template #default="{ riga }">
            <div class="col-12 md:col-4">
              <CampoModulo
                v-model="riga.chi"
                etichetta="Chi"
                segnaposto="Nome del membro"
                :maxlength="120"
                :errori="modulo.erroriRiga(e.lista, riga).chi"
                :sola-lettura="solaLettura"
              />
            </div>
            <div class="col-12 sm:col-7 md:col-5">
              <CampoModulo
                v-model="riga.nome"
                tipo="select"
                :etichetta="e.etichetta"
                :vuota="e.vuota"
                :opzioni="e.lista === 'brevetti' ? brevetti : specialita"
                :errori="modulo.erroriRiga(e.lista, riga).nome"
                :sola-lettura="solaLettura"
              />
            </div>
            <div class="col-12 sm:col-5 md:col-3">
              <CampoModulo
                v-model="riga.stato"
                tipo="select"
                etichetta="Stato"
                :opzioni="opzioni?.stati_specialita ?? []"
                :errori="modulo.erroriRiga(e.lista, riga).stato"
                :sola-lettura="solaLettura"
              />
            </div>
          </template>
        </RigheRipetute>
      </fieldset>

      <GalleriaFoto
        v-if="diario"
        class="mb-4"
        :diario-id="id"
        :modulo="chiave"
        :titolo="`Foto della ${numero}ª impresa`"
        :puo-caricare="Boolean(diario.permessi?.puo_caricare_allegati)"
        :puo-eliminare="Boolean(diario.permessi?.puo_eliminare_allegati)"
        :max-px="opzioni?.allegati_max_px"
        :max-mb="opzioni?.allegati_max_mb"
        :tipi="opzioni?.allegati_tipi"
        @modificata="pagina.aggiorna()"
      />
    </template>
  </PaginaModulo>
</template>
