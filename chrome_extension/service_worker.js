const SERVER_UPDATE = "http://127.0.0.1:5123/update";

// 1 minute minimum for MV3 Alarms
const TICK_INTERVAL_MIN = 1;
const CONFIG_INTERVAL_MIN = 1;
const TRACKER_STATE_KEY = "task_overlay_tracker_state_v1";

let keywordConfig = {};
const runtimeState = {
    currentSite: null,
    isIdle: false,
    lastTickTime: Date.now()
};

let stateLoaded = false;
let stateLoadPromise = null;

async function ensureStateLoaded() {
    if (stateLoaded) return;
    if (stateLoadPromise) return stateLoadPromise;

    stateLoadPromise = (async () => {
        try {
            const data = await chrome.storage.local.get(TRACKER_STATE_KEY);
            const saved = data?.[TRACKER_STATE_KEY];
            if (saved && typeof saved === "object") {
                runtimeState.currentSite = typeof saved.currentSite === "string" ? saved.currentSite : null;
                runtimeState.isIdle = Boolean(saved.isIdle);
                if (typeof saved.lastTickTime === "number" && Number.isFinite(saved.lastTickTime)) {
                    runtimeState.lastTickTime = saved.lastTickTime;
                }
            }
        } catch (e) {
            console.log("Failed to load tracker state", e);
        } finally {
            stateLoaded = true;
            stateLoadPromise = null;
        }
    })();

    return stateLoadPromise;
}

async function persistState() {
    try {
        await chrome.storage.local.set({ [TRACKER_STATE_KEY]: runtimeState });
    } catch (e) {
        console.log("Failed to persist tracker state", e);
    }
}

async function ensureAlarms() {
    const tickAlarm = await chrome.alarms.get("tick");
    if (!tickAlarm) {
        chrome.alarms.create("tick", { periodInMinutes: TICK_INTERVAL_MIN });
    }

    const configAlarm = await chrome.alarms.get("config");
    if (!configAlarm) {
        chrome.alarms.create("config", { periodInMinutes: CONFIG_INTERVAL_MIN });
    }
}

let configPromise = null;
async function fetchConfig() {
    if (configPromise) return configPromise;
    configPromise = (async () => {
        try {
            const res = await fetch("http://127.0.0.1:5123/config");
            keywordConfig = await res.json();
        } catch (e) {
            console.log("Failed to fetch config", e);
        }
    })();
    await configPromise;
    configPromise = null;
}

async function classify(url) {
    if (Object.keys(keywordConfig).length === 0) {
        await fetchConfig();
    }
    if (!url) return null;
    for (const kw in keywordConfig) {
        if (url.includes(kw)) return kw;
    }
    return null;
}

async function postUpdate(site, seconds) {
    try {
        await fetch(SERVER_UPDATE, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ site: site, active_seconds: seconds })
        });
    } catch (e) { }
}

async function flushTime() {
    await ensureStateLoaded();
    if (runtimeState.currentSite && !runtimeState.isIdle) {
        const now = Date.now();
        const elapsedSecs = Math.max(0, Math.floor((now - runtimeState.lastTickTime) / 1000));
        if (elapsedSecs > 0) {
            await postUpdate(runtimeState.currentSite, elapsedSecs);
        }
    }
    runtimeState.lastTickTime = Date.now();
    await persistState();
}

async function refreshActiveTabSite() {
    await ensureStateLoaded();
    try {
        const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
        if (!tab) return;
        const newSite = await classify(tab.url);
        
        if (newSite !== runtimeState.currentSite) {
            // Flush accumulated time to the old site
            await flushTime();
            
            runtimeState.currentSite = newSite;
            runtimeState.lastTickTime = Date.now();
            await persistState();
            
            if (runtimeState.currentSite) {
                // Instant heartbeat (0 seconds) to light up the UI yellow immediately
                await postUpdate(runtimeState.currentSite, 0);
            }
        }
    } catch(e) {}
}

// Event Listeners (Wake up SW)
chrome.tabs.onActivated.addListener(refreshActiveTabSite);
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (changeInfo.url) refreshActiveTabSite();
});
chrome.windows.onFocusChanged.addListener(refreshActiveTabSite);

chrome.idle.setDetectionInterval(60);
chrome.idle.onStateChanged.addListener(async (state) => {
    await ensureStateLoaded();
    if (state !== "active") {
        if (!runtimeState.isIdle) {
            await flushTime();
            runtimeState.isIdle = true;
            await persistState();
        }
    } else {
        runtimeState.isIdle = false;
        runtimeState.lastTickTime = Date.now();
        await persistState();
        await refreshActiveTabSite();
    }
});

// Alarms Logic (Reliable Loop)
chrome.runtime.onInstalled.addListener(() => {
    ensureAlarms().catch(() => {});
});

chrome.runtime.onStartup.addListener(() => {
    ensureAlarms().catch(() => {});
});

chrome.alarms.onAlarm.addListener(async (alarm) => {
    await ensureStateLoaded();
    if (alarm.name === "tick") {
        if (runtimeState.isIdle) return;
        // Don't wait for tab change, just flush the accumulated time
        await flushTime();
        // After flushing, re-ping if still on site
        await refreshActiveTabSite();
    } else if (alarm.name === "config") {
        await fetchConfig();
    }
});

// Init
ensureAlarms().catch(() => {});
fetchConfig();
refreshActiveTabSite();
