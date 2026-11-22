(() => {
  const config = window.HEATGUARD_MAP_CONFIG;
  const map = L.map('india-heatmap', {
    center: [22.8, 80.5],
    zoom: 5,
    minZoom: 4,
    maxZoom: 12
  });

  // Use the community-hosted OSM Germany raster endpoint. CARTO raster basemaps
  // now require an API key; this project has no configured CARTO credential.
  const basemap = L.tileLayer('https://tile.openstreetmap.de/{z}/{x}/{y}.png', {
    maxZoom: 19,
    subdomains: 'abcd',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
  }).addTo(map);

  let tileErrorShown = false;
  basemap.on('tileerror', () => {
    if (!tileErrorShown) {
      tileErrorShown = true;
      const note = document.createElement('div');
      note.className = 'alert alert-warning';
      note.setAttribute('role', 'status');
      note.textContent = 'Map background tiles are temporarily unavailable. The India outline and thermal overlay remain visible.';
      document.querySelector('.map-shell').appendChild(note);
    }
  });

  // Color gradient for temperature: cool blue through warm orange and red.
  const tempGradient = {
    0.0: '#38bdf8',  // Cool cyan/blue (<= 5°C)
    0.25: '#22c55e', // Fresh green (~15°C)
    0.45: '#eab308', // Warm yellow (~23°C)
    0.65: '#f97316', // Orange (~30°C)
    0.82: '#ef4444', // Red-orange (~37°C)
    1.0: '#7f1d1d'   // Deep maroon/extreme (>= 44°C)
  };

  // Color gradient for Heat Index
  const hiGradient = {
    0.0: '#38bdf8',
    0.2: '#a3e635',
    0.4: '#facc15',
    0.65: '#fb923c',
    0.82: '#ef4444',
    1.0: '#7f1d1d'
  };

  const heat = L.heatLayer([], {
    radius: 52,
    blur: 38,
    maxZoom: 8,
    max: 1.0,
    gradient: tempGradient
  }).addTo(map);

  let indiaBoundaryLayer = null;
  let currentMode = 'temp'; // 'temp' or 'hi'
  let cachedPayload = null;
  let busy = false;
  let loaded = false;

  const statusEl = document.getElementById('heatmap-status');
  const timestampEl = document.getElementById('heatmap-timestamp');
  const errorEl = document.getElementById('heatmap-error');
  const toggleTempBtn = document.getElementById('toggle-temp');
  const toggleHiBtn = document.getElementById('toggle-hi');
  const legendTitle = document.getElementById('legend-title');
  const legendLabels = document.getElementById('legend-labels');
  const legendDesc = document.getElementById('legend-description');

  // Load India Boundary
  const boundaryPromise = fetch(config.boundaryUrl)
    .then(r => {
      if (!r.ok) throw new Error('Boundary asset response not OK');
      return r.json();
    })
    .then(geo => {
      indiaBoundaryLayer = L.geoJSON(geo, {
        style: {
          color: '#1e293b',
          weight: 1.8,
          fill: false,
          opacity: 0.85
        }
      }).addTo(map);
      map.fitBounds(indiaBoundaryLayer.getBounds(), { padding: [15, 15] });
    })
    .catch(() => {
      if (errorEl) {
        errorEl.hidden = false;
        errorEl.textContent = 'India boundary overlay could not be loaded.';
      }
    });

  function updateLayerData() {
    if (!cachedPayload || !cachedPayload.valid_points) return;

    const points = cachedPayload.valid_points;
    const heatData = [];

    if (currentMode === 'temp') {
      // Temperature range in C: scale -5°C to 45°C
      const minT = -5;
      const maxT = 45;
      points.forEach(p => {
        const val = p.temperature_c;
        const norm = Math.max(0.08, Math.min(1.0, (val - minT) / (maxT - minT)));
        heatData.push([p.latitude, p.longitude, norm]);

      });

      heat.setOptions({ gradient: tempGradient });
      heat.setLatLngs(heatData);

      if (legendTitle) legendTitle.textContent = 'Live Temperature Scale (°C)';
      if (legendLabels) {
        legendLabels.innerHTML = `
          <span>&le; 0°C</span>
          <span>15°C</span>
          <span>25°C</span>
          <span>32°C</span>
          <span>38°C</span>
          <span>&ge; 45°C</span>
        `;
      }
      if (legendDesc) {
        legendDesc.textContent = 'Model-based 2 m air-temperature estimates from Open-Meteo. The smooth surface is interpolated between sample locations.';
      }
    } else {
      // Heat Index mode
      points.forEach(p => {
        heatData.push([p.latitude, p.longitude, p.intensity]);

      });

      heat.setOptions({ gradient: hiGradient });
      heat.setLatLngs(heatData);

      if (legendTitle) legendTitle.textContent = 'Heat Index (Human Thermal Stress)';
      if (legendLabels) {
        legendLabels.innerHTML = `
          <span>Normal (&lt;80°F)</span>
          <span>Caution (80–90°F)</span>
          <span>Extreme Caution</span>
          <span>Danger</span>
          <span>Extreme Danger</span>
        `;
      }
      if (legendDesc) {
        legendDesc.textContent = 'Estimated Heat Index calculated from model-based air temperature and humidity using the NOAA/NWS method.';
      }
    }
  }

  async function refresh(manual = false) {
    if (busy || (document.hidden && !manual)) return;
    busy = true;
    if (statusEl) statusEl.textContent = 'Fetching the latest model-based weather estimates across India…';
    try {
      const response = await fetch(config.dataUrl, {
        headers: { 'Accept': 'application/json' }
      });
      const data = await response.json();
      if (!response.ok || !data.success || !data.valid_points?.length) {
        throw new Error(data.error || 'Weather telemetry temporarily unavailable.');
      }
      cachedPayload = data;
      loaded = true;
      if (errorEl) errorEl.hidden = true;

      updateLayerData();

      if (statusEl) {
        statusEl.textContent = `${data.valid_point_count} model-based sample points · Source: Open-Meteo · Provider time: ${data.provider_valid_time || 'unavailable'}`;
      }
      if (timestampEl) {
        timestampEl.textContent = `Updated: ${new Date(data.retrieved_at).toLocaleTimeString()}`;
      }
    } catch (e) {
      if (errorEl) {
        errorEl.hidden = false;
        errorEl.textContent = loaded
          ? `Live update failed. Displaying cached data from ${timestampEl ? timestampEl.textContent : 'earlier'}.`
          : 'Weather estimates are temporarily unavailable. Please try again shortly.';
      }
      if (statusEl) {
        statusEl.textContent = loaded ? 'Showing cached estimates' : 'Weather estimates unavailable';
      }
    } finally {
      busy = false;
    }
  }

  if (toggleTempBtn) {
    toggleTempBtn.addEventListener('click', () => {
      if (currentMode === 'temp') return;
      currentMode = 'temp';
      toggleTempBtn.classList.add('active');
      toggleTempBtn.setAttribute('aria-pressed', 'true');
      toggleHiBtn.classList.remove('active');
      toggleHiBtn.setAttribute('aria-pressed', 'false');
      updateLayerData();
    });
  }

  if (toggleHiBtn) {
    toggleHiBtn.addEventListener('click', () => {
      if (currentMode === 'hi') return;
      currentMode = 'hi';
      toggleHiBtn.classList.add('active');
      toggleHiBtn.setAttribute('aria-pressed', 'true');
      toggleTempBtn.classList.remove('active');
      toggleTempBtn.setAttribute('aria-pressed', 'false');
      updateLayerData();
    });
  }

  document.getElementById('heatmap-refresh')?.addEventListener('click', () => refresh(true));
  document.getElementById('heatmap-reset')?.addEventListener('click', () => {
    if (indiaBoundaryLayer) {
      map.fitBounds(indiaBoundaryLayer.getBounds(), { padding: [15, 15] });
    } else {
      map.setView([22.8, 80.5], 5);
    }
  });

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && (!loaded || Date.now() - (window._lastHeatmapFetch || 0) > 300000)) {
      refresh();
    }
  });

  boundaryPromise.finally(() => refresh());
  setInterval(() => {
    if (!document.hidden) refresh();
  }, 600000); // 10 minutes
})();
