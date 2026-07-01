/* ===================================
   Bridge — Capa de compatibilidad pywebview
   =================================== */

/**
 * Espera a que pywebview esté listo y expone window.api como proxy global.
 * Todos los demás scripts usan `api.function()` en vez de `eel.function()()`.
 */

// Promise global que se resuelve cuando pywebview inyecta su API
const pywebviewReady = new Promise((resolve) => {
    if (window.pywebview && window.pywebview.api) {
        resolve(window.pywebview.api);
    } else {
        window.addEventListener('pywebviewready', () => {
            resolve(window.pywebview.api);
        });
    }
});

// Proxy 'api' que encola llamadas hasta que pywebview esté listo
const api = new Proxy({}, {
    get(target, prop) {
        return async function (...args) {
            const realApi = await pywebviewReady;
            if (typeof realApi[prop] === 'function') {
                return await realApi[prop](...args);
            }
            console.warn(`api.${prop} no existe en pywebview.api`);
            return undefined;
        };
    }
});
