import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { nextTick } from 'vue'

import ImpostazioniEditorHtml from '@/components/impostazioni/ImpostazioniEditorHtml.vue'

beforeEach(() => setActivePinia(createPinia()))

function monta(html: string) {
  const aggiornamenti: string[] = []
  const wrapper = mount(ImpostazioniEditorHtml, {
    props: {
      modelValue: html,
      etichetta: 'Corpo',
      segnaposti: ['nome', 'link_attivazione'],
      'onUpdate:modelValue': (v: string) => {
        aggiornamenti.push(v)
        void wrapper.setProps({ modelValue: v })
      },
    },
    attachTo: document.body,
  })
  return { wrapper, aggiornamenti }
}

describe('ImpostazioniEditorHtml', () => {
  it("con HTML avanzato parte dal sorgente e non lo modifica", async () => {
    const html = '<table style="width:100%"><tr><td>{% for x in y %}{{ x }}{% endfor %}</td></tr></table>'
    const { wrapper, aggiornamenti } = monta(html)
    await flushPromises()
    const area = wrapper.get('textarea')
    expect((area.element as HTMLTextAreaElement).value).toBe(html)
    expect(wrapper.text()).toContain('HTML avanzato')
    expect(aggiornamenti).toEqual([])
    wrapper.unmount()
  })

  it('i pulsanti dei segnaposti inseriscono il tag nel sorgente al cursore', async () => {
    const { wrapper, aggiornamenti } = monta('<div>Ciao !</div>')
    await flushPromises()
    const area = wrapper.get('textarea').element as HTMLTextAreaElement
    area.setSelectionRange(10, 10)
    const pulsante = wrapper.findAll('button').find((b) => b.text() === '{{ nome }}')
    await pulsante!.trigger('click')
    expect(aggiornamenti.at(-1)).toBe('<div>Ciao {{ nome }}!</div>')
    wrapper.unmount()
  })

  it("con HTML semplice usa l'editor visuale e l'anteprima è isolata", async () => {
    const { wrapper } = monta('<p>Ciao <strong>{{ nome }}</strong></p>')
    await flushPromises()
    expect(wrapper.find('textarea').exists()).toBe(false)
    expect(wrapper.find('[role="toolbar"] button[aria-label="Grassetto"]').exists()).toBe(true)
    const anteprima = wrapper.findAll('button').find((b) => b.text() === 'Anteprima')
    await anteprima!.trigger('click')
    await nextTick()
    const iframe = wrapper.get('iframe')
    expect(iframe.attributes('sandbox')).toBe('')
    expect(iframe.attributes('srcdoc')).toContain('{{ nome }}')
    wrapper.unmount()
  })
})
