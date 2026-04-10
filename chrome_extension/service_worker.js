const SERVER_UPDATE = "http://127.0.0.1:5123/update";

// 1 minute minimum for MV3 Alarms
const TICK_INTERVAL_MIN = 1;
const CONFIG_INTERVAL_MIN = 1;

let currentSite = null;
let isIdle = false;
let keywordConfig = {};
let lastTickTime = Date.now();

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
    if (currentSite && !isIdle) {
        const now = Date.now();
        const elapsedSecs = Math.max(0, Math.floor((now - lastTickTime) / 1000));
        if (elapsedSecs > 0) {
            await postUpdate(currentSite, elapsedSecs);
        }
    }
    lastTickTime = Date.now();
}

async function refreshActiveTabSite() {
    try {
        const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
        if (!tab) return;
        const newSite = await classify(tab.url);
        
        if (newSite !== currentSite) {
            // Flush accumulated time to the old site
            await flushTime();
            
            currentSite = newSite;
            lastTickTime = Date.now();
            
            if (currentSite) {
                // Instant heartbeat (0 seconds) to light up the UI yellow immediately
                await postUpdate(currentSite, 0);
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
    if (state !== "active") {
        if (!isIdle) {
            await flushTime();
            isIdle = true;
        }
    } else {
        isIdle = false;
        lastTickTime = Date.now();
        await refreshActiveTabSite();
    }
});

// Alarms Logic (Reliable Loop)
chrome.alarms.create("tick", { periodInMinutes: TICK_INTERVAL_MIN });
chrome.alarms.create("config", { periodInMinutes: CONFIG_INTERVAL_MIN });

chrome.alarms.onAlarm.addListener(async (alarm) => {
    if (alarm.name === "tick") {
        if (isIdle) return;
        // Don't wait for tab change, just flush the accumulated time
        await flushTime();
        // After flushing, re-ping if still on site
        await refreshActiveTabSite();
    } else if (alarm.name === "config") {
        await fetchConfig();
    }
});

// Init
fetchConfig();
