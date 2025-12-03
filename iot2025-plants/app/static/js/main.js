///////////////////////// Automated Watering & Lighting /////////////////////////
let currentDeviceId = null;
let deviceSelectListenerAdded = false;

// Załaduj listę urządzeń z backendu i wypełnij dropdown
async function loadDevices() {
  const select = document.getElementById("deviceSelect");
  if (!select) {
    console.warn("Brak #deviceSelect w HTML");
    return;
  }

  try {
    const res = await fetch("/api/devices");
    if (!res.ok) {
      console.error("Nie udało się pobrać /api/devices:", res.status);
      return;
    }

    const devices = await res.json();

    // Zapisz aktualnie wybrany device_id przed czyszczeniem
    const currentlySelectedId = currentDeviceId;

    select.innerHTML = "";

    if (!devices.length) {
      const opt = document.createElement("option");
      opt.textContent = "Brak urządzeń";
      opt.disabled = true;
      opt.selected = true;
      select.appendChild(opt);
      currentDeviceId = null;
      return;
    }

    // Spróbuj użyć ostatnio wybranego urządzenia lub aktualnie wybranego
    const savedId = localStorage.getItem("selectedDeviceId");
    let selectedId = null;

    if (
      currentlySelectedId &&
      devices.some((d) => d.id === Number(currentlySelectedId))
    ) {
      selectedId = Number(currentlySelectedId);
    } else if (savedId && devices.some((d) => d.id === Number(savedId))) {
      selectedId = Number(savedId);
    } else {
      selectedId = devices[0].id; // pierwsze z listy
    }

    currentDeviceId = selectedId;

    devices.forEach((d) => {
      const opt = document.createElement("option");
      opt.value = d.id;
      // Użyj label jeśli istnieje, w przeciwnym razie name, w przeciwnym razie fallback
      const displayLabel = d.label || d.name || `Device ${d.id}`;
      opt.textContent = displayLabel;
      if (d.id === selectedId) opt.selected = true;
      select.appendChild(opt);
    });

    // Dodaj event listener tylko raz
    if (!deviceSelectListenerAdded) {
      select.addEventListener("change", () => {
        currentDeviceId = Number(select.value);
        localStorage.setItem("selectedDeviceId", String(currentDeviceId));
        console.log("Wybrane device_id =", currentDeviceId);

        getData();
        getChartData();
      });
      deviceSelectListenerAdded = true;
    }

    console.log("Aktualne device_id =", currentDeviceId);
  } catch (e) {
    console.error("loadDevices error:", e);
  }
}

// referencje do przełączników
const autoSwitch = document.getElementById("autoSwitch");
const manualSwitch = document.getElementById("manualSwitch");

// wysyłanie komendy do backendu (na razie device_id = 1)
async function sendAutomationCommand(kind) {
  if (!currentDeviceId) {
    alert(
      "Brak wybranego urządzenia (lista devices jest pusta albo się nie załadowała)."
    );
    return;
  }

  const deviceId = currentDeviceId;

  const thresholdInputId =
    kind === "watering" ? "wateringThreshold" : "lightingThreshold";
  const switchId = kind === "watering" ? "autoSwitch" : "manualSwitch";

  const thresholdEl = document.getElementById(thresholdInputId);
  const switchEl = document.getElementById(switchId);

  if (!thresholdEl || !switchEl) {
    console.warn("Brak elementów progów / switchy w DOM");
    return;
  }

  const threshold = Number(thresholdEl.value || 0);
  const enabled = switchEl.checked;

  const body = {
    device_id: deviceId,
    command: kind === "watering" ? "set_watering" : "set_lighting",
    payload_json: {
      threshold: threshold,
      enabled: enabled,
      type: kind,
    },
    scheduled_at: null,
  };

  try {
    const res = await fetch("/api/commands", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const txt = await res.text();
      console.error("Command error:", res.status, txt);
      alert("Nie udało się zapisać komendy (zobacz konsolę).");
    } else {
      const json = await res.json();
      console.log("Command saved:", json);
    }
  } catch (e) {
    console.error("Fetch error:", e);
    alert("Błąd połączenia z API.");
  }
}

// zapisywanie progów w localStorage + wysłanie komendy
function saveThreshold(type, value) {
  localStorage.setItem(`${type}Threshold`, value);
  console.log(`Saved ${type} threshold:`, value);
  if (type === "watering" || type === "lighting") {
    sendAutomationCommand(type);
  }
}

// przy starcie odtwórz progi z localStorage
function restoreThresholds() {
  const wateringValue = localStorage.getItem("wateringThreshold");
  const lightingValue = localStorage.getItem("lightingThreshold");
  if (wateringValue !== null) {
    const el = document.getElementById("wateringThreshold");
    if (el) el.value = wateringValue;
  }
  if (lightingValue !== null) {
    const el = document.getElementById("lightingThreshold");
    if (el) el.value = lightingValue;
  }
}

// funkcje wywoływane z HTML: onclick="auto()" / onclick="manual()"
function auto() {
  console.log("Auto watering toggled");
  if (autoSwitch && manualSwitch && autoSwitch.checked) {
    manualSwitch.checked = false;
  }
  sendAutomationCommand("watering");
}

function manual() {
  console.log("Manual lighting toggled");
  sendAutomationCommand("lighting");
}

///////////////////////// Get readings (kafelki w dashboardzie) /////////////////////////

async function getData() {
  try {
    const res = await fetch(
      `/api/graphs/latest?device_id=${currentDeviceId}&points=1`
    );
    if (!res.ok) {
      console.warn("getData status:", res.status);
      return;
    }
    const data = await res.json();

    const t = data.temperature?.values || [];
    const h = data.humidity?.values || [];
    const s = data.soil?.values || [];
    const l = data.light?.values || [];

    if (t.length) $("#tempValue").html(t[t.length - 1].toFixed(1));
    if (h.length) $("#humValue").html(h[h.length - 1].toFixed(1));
    if (s.length) $("#soilValue").html(s[s.length - 1].toFixed(1));
    if (l.length) $("#lightValue").html(l[l.length - 1].toFixed(0));
  } catch (e) {
    console.error("getData error:", e);
  }
}

/////////////////////// Get Chart data (wykresy) ///////////////////////
async function getChartData() {
  try {
    const res = await fetch(
      `/api/graphs/latest?device_id=${currentDeviceId}&points=50`
    );
    if (!res.ok) {
      console.warn("getChartData status:", res.status);
      return;
    }
    const data = await res.json();

    const tempArr = data.temperature?.values || [];
    const humArr = data.humidity?.values || [];
    const soilArr = data.soil?.values || [];
    const lightArr = data.light?.values || [];
    const timeArr = data.temperature?.labels || [];

    createGraph(tempArr, timeArr, "#tempChart");
    createGraph(humArr, timeArr, "#humChart");
    createGraph(soilArr, timeArr, "#soilChart");
    createGraph(lightArr, timeArr, "#lightChart");
  } catch (e) {
    console.error("getChartData error:", e);
  }
}

// Charts
function createGraph(data, newTime, newChart) {
  if (!data.length || !newTime.length) return;

  let chartData = {
    labels: newTime,
    series: [data],
  };

  let options = {
    axisY: {
      onlyInteger: false,
    },
    fullWidth: true,
    width: "100%",
    height: "100%",
    lineSmooth: true,
    chartPadding: {
      right: 50,
    },
  };

  new Chartist.Line(newChart, chartData, options);
}

/////////////////////// run functions ///////////////////////
$(document).ready(async function () {
  await loadDevices();
  restoreThresholds();

  // Poczekaj aż device zostanie wybrany przed pobraniem danych
  if (currentDeviceId) {
    getData();
    getChartData();
  }

  // Odśwież dane co 5 sekund
  setInterval(function () {
    if (currentDeviceId) {
      getData();
      getChartData();
    }
  }, 5000);

  // Odśwież listę urządzeń co 30 sekund (aby zobaczyć zmiany w labelach)
  setInterval(async function () {
    await loadDevices();
  }, 30000);
});
