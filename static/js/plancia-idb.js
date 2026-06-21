/* PlanciaIdb — coda offline per i moduli del diario (IndexedDB).
 *
 * API pubblica (window.PlanciaIdb):
 *   enqueue(diario_pk, modulo, url, payload) → Promise<void>   (upsert: stesso modulo sovrascrive)
 *   getAll()                                 → Promise<Item[]>
 *   remove(id)                               → Promise<void>
 *   count()                                  → Promise<number>
 *
 * Lancia l'evento DOM custom `plancia:pending-count` (detail = n) dopo ogni modifica.
 */

(function (global) {
  'use strict';

  var DB_NAME    = 'plancia-offline';
  var DB_VERSION = 1;
  var STORE      = 'pending-syncs';

  function open() {
    return new Promise(function (resolve, reject) {
      var req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = function (e) {
        var db = e.target.result;
        if (!db.objectStoreNames.contains(STORE)) {
          var store = db.createObjectStore(STORE, { keyPath: 'id', autoIncrement: true });
          // Indice per trovare rapidamente l'elemento dello stesso modulo (per upsert)
          store.createIndex('by_modulo', ['diario_pk', 'modulo'], { unique: false });
        }
      };
      req.onsuccess = function (e) { resolve(e.target.result); };
      req.onerror   = function (e) { reject(e.target.error); };
    });
  }

  function _dispatch(n) {
    document.dispatchEvent(new CustomEvent('plancia:pending-count', { detail: n }));
  }

  function count() {
    return open().then(function (db) {
      return new Promise(function (resolve, reject) {
        var req = db.transaction(STORE, 'readonly').objectStore(STORE).count();
        req.onsuccess = function (e) { resolve(e.target.result); };
        req.onerror   = function (e) { reject(e.target.error); };
      });
    });
  }

  function _notifyCount() {
    count().then(_dispatch).catch(function () { _dispatch(0); });
  }

  /**
   * Inserisce o aggiorna l'elemento in coda.
   * Se esiste già un elemento con lo stesso (diario_pk, modulo), viene sovrascritto
   * con i nuovi dati: l'ultima modifica offline vince su quelle precedenti non sincronizzate.
   */
  function enqueue(diario_pk, modulo, url, payload) {
    return open().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx    = db.transaction(STORE, 'readwrite');
        var store = tx.objectStore(STORE);
        var now   = Date.now();

        store.index('by_modulo').getAll([diario_pk, modulo]).onsuccess = function (e) {
          var existing = e.target.result;
          if (existing.length > 0) {
            var entry        = existing[0];
            entry.payload    = payload;
            entry.url        = url;
            entry.updated_at = now;
            store.put(entry);
          } else {
            store.add({
              diario_pk:  diario_pk,
              modulo:     modulo,
              url:        url,
              payload:    payload,
              created_at: now,
              updated_at: now,
            });
          }
        };

        tx.oncomplete = function () { _notifyCount(); resolve(); };
        tx.onerror    = function (e) { reject(e.target.error); };
      });
    });
  }

  function getAll() {
    return open().then(function (db) {
      return new Promise(function (resolve, reject) {
        var req = db.transaction(STORE, 'readonly').objectStore(STORE).getAll();
        req.onsuccess = function (e) { resolve(e.target.result); };
        req.onerror   = function (e) { reject(e.target.error); };
      });
    });
  }

  function remove(id) {
    return open().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction(STORE, 'readwrite');
        tx.objectStore(STORE).delete(id);
        tx.oncomplete = function () { _notifyCount(); resolve(); };
        tx.onerror    = function (e) { reject(e.target.error); };
      });
    });
  }

  global.PlanciaIdb = { enqueue: enqueue, getAll: getAll, remove: remove, count: count };

})(window);
