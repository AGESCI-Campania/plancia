/**
 * Passkey (WebAuthn) con le API JSON native del browser (Safari 18.4+, Chrome 129+):
 * allauth fornisce le opzioni nel formato `PublicKeyCredential*OptionsJSON`.
 */

type OpzioniJson = { publicKey: PublicKeyCredentialRequestOptionsJSON }
type OpzioniCreazioneJson = { publicKey: PublicKeyCredentialCreationOptionsJSON }

export const passkeySupportate = (): boolean =>
  typeof window !== 'undefined' &&
  'PublicKeyCredential' in window &&
  typeof PublicKeyCredential.parseRequestOptionsFromJSON === 'function'

export async function firmaConPasskey(opzioni: unknown): Promise<unknown> {
  const publicKey = PublicKeyCredential.parseRequestOptionsFromJSON((opzioni as OpzioniJson).publicKey)
  const credenziale = (await navigator.credentials.get({ publicKey })) as PublicKeyCredential | null
  if (!credenziale) throw new Error('Nessuna passkey selezionata.')
  return credenziale.toJSON()
}

export async function creaPasskey(opzioni: unknown): Promise<unknown> {
  const publicKey = PublicKeyCredential.parseCreationOptionsFromJSON(
    (opzioni as OpzioniCreazioneJson).publicKey,
  )
  const credenziale = (await navigator.credentials.create({ publicKey })) as PublicKeyCredential | null
  if (!credenziale) throw new Error('Creazione della passkey annullata.')
  return credenziale.toJSON()
}
