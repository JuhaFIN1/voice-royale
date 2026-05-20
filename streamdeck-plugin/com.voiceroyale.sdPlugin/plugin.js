/**
 * Voice Royale — Elgato Stream Deck Plugin
 *
 * Connects to Voice Royale's local HTTP server (port 17842) and proxies
 * button-press events as POST /action/{name} requests.  State is polled
 * every 2 seconds and button titles are updated to reflect the current
 * recording/listening/FX state.
 *
 * Compatible with Stream Deck software 5.x and 6.x (SDK v2).
 * Entry point declared in manifest.json as "CodePath": "plugin.js".
 *
 * Elgato SDK WebSocket handshake:
 *   Stream Deck launches this script with:
 *     --port <N> --pluginUUID <uuid> --registerEvent <event> --info <json>
 *   The plugin opens a WebSocket to ws://127.0.0.1:<N> and sends the
 *   registration message, then receives/sends JSON events.
 */

'use strict';

const VOICE_ROYALE_PORT = 17842;
const BASE_URL = `http://127.0.0.1:${VOICE_ROYALE_PORT}`;
const POLL_INTERVAL_MS = 2000;

// ── CLI arg parsing ──────────────────────────────────────────────────────────
const argv = process.argv.slice(2);
function getArg(name) {
    const idx = argv.indexOf(name);
    return idx >= 0 ? argv[idx + 1] : null;
}
const sdPort      = getArg('-port')        || getArg('--port');
const pluginUUID  = getArg('-pluginUUID')  || getArg('--pluginUUID');
const registerEvent = getArg('-registerEvent') || getArg('--registerEvent');

if (!sdPort || !pluginUUID || !registerEvent) {
    console.error('[Voice Royale] Missing required CLI args: -port -pluginUUID -registerEvent');
    process.exit(1);
}

// ── Action UUID → Voice Royale action name mapping ──────────────────────────
const ACTION_MAP = {
    'com.voiceroyale.record.toggle': 'record_toggle',
    'com.voiceroyale.wake.toggle':   'wake_listen_toggle',
    'com.voiceroyale.speak':         'speak',
    'com.voiceroyale.stop':          'stop_recording',
    'com.voiceroyale.tts.toggle':    'tts_toggle',
    'com.voiceroyale.settings':      'settings',
    'com.voiceroyale.sb.page.next':  'sb_page_next',
    'com.voiceroyale.sb.page.prev':  'sb_page_prev',
    // lang / soundboard / fx resolved from payload.settings at keyDown time
};

// ── Active button contexts (for state polling updates) ───────────────────────
// Map: contextKey (actionUUID:context) → { action, context, settings }
const activeContexts = new Map();

// ── WebSocket to Stream Deck software ───────────────────────────────────────
let ws = null;
let appState = null;
let pollTimer = null;

function connect() {
    const WebSocket = (() => {
        try { return require('ws'); } catch (_) { return global.WebSocket; }
    })();

    if (!WebSocket) {
        console.error('[Voice Royale] WebSocket not available — install ws package or use Stream Deck 6.x');
        return;
    }

    ws = new WebSocket(`ws://127.0.0.1:${sdPort}`);

    ws.addEventListener('open', () => {
        ws.send(JSON.stringify({ event: registerEvent, uuid: pluginUUID }));
        console.log('[Voice Royale] Connected to Stream Deck software');
        startPolling();
    });

    ws.addEventListener('message', (evt) => {
        let msg;
        try { msg = JSON.parse(evt.data); } catch (_) { return; }
        handleSDEvent(msg);
    });

    ws.addEventListener('close', () => {
        console.log('[Voice Royale] Disconnected from Stream Deck — reconnecting in 5s');
        stopPolling();
        setTimeout(connect, 5000);
    });

    ws.addEventListener('error', (err) => {
        console.error('[Voice Royale] WebSocket error:', err.message || err);
    });
}

// ── Stream Deck event handler ─────────────────────────────────────────────────
function handleSDEvent(msg) {
    const { event, action, context, payload } = msg;

    switch (event) {
        case 'keyDown':
            handleKeyDown(action, context, payload || {});
            break;

        case 'willAppear':
            activeContexts.set(`${action}:${context}`, {
                action, context, settings: (payload && payload.settings) || {}
            });
            // Update immediately when button appears
            if (appState) updateContext(action, context, (payload && payload.settings) || {}, appState);
            break;

        case 'willDisappear':
            activeContexts.delete(`${action}:${context}`);
            break;

        case 'didReceiveSettings':
            // User changed settings in property inspector
            if (activeContexts.has(`${action}:${context}`)) {
                activeContexts.get(`${action}:${context}`).settings = (payload && payload.settings) || {};
            }
            break;

        case 'applicationDidLaunch':
        case 'applicationDidTerminate':
            // Voice Royale started/stopped — poll immediately
            pollState();
            break;
    }
}

// ── Button press handler ──────────────────────────────────────────────────────
function handleKeyDown(action, context, payload) {
    let vrAction = ACTION_MAP[action];

    if (!vrAction) {
        // Actions with user-configurable settings (lang, soundboard, fx)
        const settings = payload.settings || {};
        if (action === 'com.voiceroyale.lang') {
            vrAction = settings.lang ? `lang_${settings.lang}` : 'lang_English';
        } else if (action === 'com.voiceroyale.soundboard') {
            const page = settings.page !== undefined ? settings.page : 0;
            const slot = settings.slot !== undefined ? settings.slot : 0;
            vrAction = `soundboard_${page}_${slot}`;
        } else if (action === 'com.voiceroyale.fx') {
            vrAction = settings.preset ? `fx_${settings.preset}` : 'fx_Normal';
        } else {
            console.warn('[Voice Royale] Unknown action:', action);
            return;
        }
    }

    httpPost(`/action/${encodeURIComponent(vrAction)}`)
        .then(() => {
            // Show success tick briefly
            sendSD({ event: 'showOk', context });
            // Trigger an immediate state poll so button visuals update
            setTimeout(pollState, 300);
        })
        .catch(() => {
            // Voice Royale not running
            sendSD({ event: 'showAlert', context });
        });
}

// ── State polling ─────────────────────────────────────────────────────────────
function startPolling() {
    pollState();
    pollTimer = setInterval(pollState, POLL_INTERVAL_MS);
}

function stopPolling() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}

async function pollState() {
    try {
        const state = await httpGet('/state');
        appState = state;
        for (const [, entry] of activeContexts) {
            updateContext(entry.action, entry.context, entry.settings, state);
        }
    } catch (_) {
        // Voice Royale not running — clear state indicators
        for (const [, entry] of activeContexts) {
            sendSD({ event: 'setState', context: entry.context, payload: { state: 0 } });
        }
    }
}

// ── Per-button visual update ──────────────────────────────────────────────────
function updateContext(action, context, settings, state) {
    let isActive = false;
    let title = '';

    switch (action) {
        case 'com.voiceroyale.record.toggle':
            isActive = !!state.recording;
            title = state.recording ? 'REC...' : 'Record';
            break;
        case 'com.voiceroyale.wake.toggle':
            isActive = !!state.listening;
            title = state.listening ? 'Listening' : 'Listen';
            break;
        case 'com.voiceroyale.stop':
            isActive = !!state.recording;
            title = 'Stop';
            break;
        case 'com.voiceroyale.tts.toggle':
            title = state.tts_backend ? state.tts_backend.substring(0, 8) : 'TTS';
            break;
        case 'com.voiceroyale.lang': {
            const lang = settings.lang || 'English';
            isActive = state.language === lang;
            title = lang.substring(0, 8);
            break;
        }
        case 'com.voiceroyale.soundboard': {
            const page = settings.page !== undefined ? settings.page : 0;
            const slot = settings.slot !== undefined ? settings.slot : 0;
            const pages = state.soundboard_pages || [];
            const slotData = pages[page] && pages[page].slots[slot];
            title = slotData ? slotData.name.substring(0, 8) : `SB ${slot + 1}`;
            break;
        }
        case 'com.voiceroyale.sb.page.next': {
            const pages = state.soundboard_pages || [];
            const next = pages.length ? (state.soundboard_page + 1) % pages.length : 0;
            title = pages[next] ? pages[next].name.substring(0, 8) : '->';
            break;
        }
        case 'com.voiceroyale.sb.page.prev': {
            const pages = state.soundboard_pages || [];
            const prev = pages.length ? (state.soundboard_page + pages.length - 1) % pages.length : 0;
            title = pages[prev] ? pages[prev].name.substring(0, 8) : '<-';
            break;
        }
        case 'com.voiceroyale.fx': {
            const preset = settings.preset || 'Normal';
            isActive = state.fx_active && state.fx_preset === preset;
            title = preset.substring(0, 8);
            break;
        }
        default:
            return;
    }

    sendSD({ event: 'setState', context, payload: { state: isActive ? 1 : 0 } });
    if (title) {
        sendSD({ event: 'setTitle', context, payload: { title, target: 0 } });
    }
}

// ── Stream Deck send helper ───────────────────────────────────────────────────
function sendSD(msg) {
    if (ws && ws.readyState === (ws.OPEN !== undefined ? ws.OPEN : 1)) {
        ws.send(JSON.stringify(msg));
    }
}

// ── HTTP helpers (Node.js built-in http module) ───────────────────────────────
function httpGet(path) {
    return new Promise((resolve, reject) => {
        const http = require('http');
        http.get(`${BASE_URL}${path}`, { timeout: 1500 }, (res) => {
            let data = '';
            res.on('data', chunk => { data += chunk; });
            res.on('end', () => {
                try { resolve(JSON.parse(data)); } catch (e) { reject(e); }
            });
        }).on('error', reject).on('timeout', function() { this.destroy(); reject(new Error('timeout')); });
    });
}

function httpPost(path) {
    return new Promise((resolve, reject) => {
        const http = require('http');
        const req = http.request(
            { hostname: '127.0.0.1', port: VOICE_ROYALE_PORT, path, method: 'POST', timeout: 1500 },
            (res) => {
                let data = '';
                res.on('data', chunk => { data += chunk; });
                res.on('end', () => {
                    try { resolve(JSON.parse(data)); } catch (e) { reject(e); }
                });
            }
        );
        req.on('error', reject);
        req.on('timeout', function() { this.destroy(); reject(new Error('timeout')); });
        req.end();
    });
}

// ── Start ─────────────────────────────────────────────────────────────────────
connect();
