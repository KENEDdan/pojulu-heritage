/* Pojulu Heritage maps (Leaflet + OpenStreetMap tiles).
 *
 *  - [data-clan-map]                 public clan map: boundary + landmark markers
 *  - textarea[data-boundary-editor]  dashboard: click the map to draw a clan boundary
 *  - input[data-point-lat]/[...lng]  dashboard: click the map to place a landmark
 *
 * Everything shown in popups is set with textContent, never innerHTML.
 */
(function () {
  'use strict';
  if (typeof L === 'undefined') return;

  var DEFAULT_CENTER = [4.35, 30.95];   // Lainya County, Central Equatoria
  var DEFAULT_ZOOM = 9;
  var BOUNDARY_STYLE = { color: '#1B5E20', weight: 3, fillColor: '#66BB6A', fillOpacity: 0.15 };

  function baseMap(el, height) {
    el.style.height = height || '420px';
    el.style.borderRadius = '8px';
    el.style.border = '1px solid #dcd6c8';
    var map = L.map(el, { scrollWheelZoom: false }).setView(DEFAULT_CENTER, DEFAULT_ZOOM);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
    return map;
  }

  function readJSON(id) {
    var node = document.getElementById(id);
    if (!node) return null;
    try { return JSON.parse(node.textContent); } catch (e) { return null; }
  }

  function parseGeoJSON(text) {
    if (!text) return null;
    try { return JSON.parse(text); } catch (e) { return null; }
  }

  function popup(title, sub) {
    var div = document.createElement('div');
    var b = document.createElement('strong');
    b.textContent = title;
    div.appendChild(b);
    if (sub) {
      div.appendChild(document.createElement('br'));
      var s = document.createElement('small');
      s.textContent = sub;
      div.appendChild(s);
    }
    return div;
  }

  // ── Public clan map ────────────────────────────────────────────────
  function whenVisible(el, fn) {
    // A map created inside a hidden tab measures 0x0 and frames itself wrongly,
    // so wait until the tab is opened.
    if (el.clientWidth > 0 || typeof ResizeObserver === 'undefined') { fn(); return; }
    var ro = new ResizeObserver(function () {
      if (el.clientWidth > 0) { ro.disconnect(); fn(); }
    });
    ro.observe(el);
  }

  function clanMap(el) {
    whenVisible(el, function () { drawClanMap(el); });
  }

  function drawClanMap(el) {
    var data = readJSON(el.getAttribute('data-clan-map'));
    if (!data) return;
    var map = baseMap(el);
    var layers = [];
    var boundary = parseGeoJSON(data.boundary);
    if (boundary) {
      try { layers.push(L.geoJSON(boundary, { style: BOUNDARY_STYLE }).addTo(map)); } catch (e) { /* ignore bad data */ }
    }
    (data.landmarks || []).forEach(function (lm) {
      var marker = L.marker([lm.lat, lm.lng]).addTo(map);
      marker.bindPopup(popup(lm.name, lm.type));
      layers.push(marker);
    });
    if (layers.length) {
      map.fitBounds(L.featureGroup(layers).getBounds().pad(0.15), { maxZoom: 14 });
    }
  }

  // ── Dashboard: boundary editor ─────────────────────────────────────
  function toolbarButton(label, onClick) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'dash-btn dash-btn-outline dash-btn-sm';
    b.textContent = label;
    b.addEventListener('click', onClick);
    return b;
  }

  function boundaryEditor(textarea) {
    var wrap = document.createElement('div');
    var help = document.createElement('p');
    help.className = 'form-text';
    help.textContent = 'Click around the edge of the clan territory to draw its boundary, point by point. ' +
      'The shape closes itself. Use "Undo last point" to fix a mistake.';
    var mapEl = document.createElement('div');
    var bar = document.createElement('div');
    bar.className = 'd-flex gap-2 my-2 flex-wrap';
    wrap.appendChild(help);
    wrap.appendChild(mapEl);
    wrap.appendChild(bar);
    textarea.parentNode.insertBefore(wrap, textarea);

    var map = baseMap(mapEl, '460px');
    var points = [];
    var shape = null;
    var readonlyLayer = null;
    var vertices = L.layerGroup().addTo(map);

    function redraw() {
      if (shape) { map.removeLayer(shape); shape = null; }
      vertices.clearLayers();
      if (points.length >= 2) {
        shape = (points.length >= 3 ? L.polygon(points, BOUNDARY_STYLE) : L.polyline(points, BOUNDARY_STYLE)).addTo(map);
      }
      points.forEach(function (p) { L.circleMarker(p, { radius: 4, color: '#1B5E20' }).addTo(vertices); });
    }

    function write() {
      if (points.length >= 3) {
        var ring = points.map(function (p) { return [+p[1].toFixed(6), +p[0].toFixed(6)]; });
        ring.push(ring[0]);
        textarea.value = JSON.stringify({ type: 'Polygon', coordinates: [ring] });
      } else {
        textarea.value = '';
      }
    }

    function load() {
      points = [];
      if (readonlyLayer) { map.removeLayer(readonlyLayer); readonlyLayer = null; }
      var g = parseGeoJSON(textarea.value);
      if (g && g.type === 'Feature') g = g.geometry;
      if (g && g.type === 'Polygon' && g.coordinates && g.coordinates.length === 1) {
        var ring = g.coordinates[0].slice(0, -1);
        points = ring.map(function (c) { return [c[1], c[0]]; });
      } else if (g) {
        // Complex shapes (several polygons, holes) are shown but not edited point by point.
        try { readonlyLayer = L.geoJSON(g, { style: BOUNDARY_STYLE }).addTo(map); } catch (e) { readonlyLayer = null; }
      }
      redraw();
      var bounds = shape ? shape.getBounds() : (readonlyLayer ? readonlyLayer.getBounds() : null);
      if (bounds && bounds.isValid()) map.fitBounds(bounds.pad(0.2));
    }

    map.on('click', function (e) {
      if (readonlyLayer) { map.removeLayer(readonlyLayer); readonlyLayer = null; }
      points.push([e.latlng.lat, e.latlng.lng]);
      redraw();
      write();
    });
    bar.appendChild(toolbarButton('Undo last point', function () { points.pop(); redraw(); write(); }));
    bar.appendChild(toolbarButton('Clear boundary', function () {
      if (readonlyLayer) { map.removeLayer(readonlyLayer); readonlyLayer = null; }
      points = []; redraw(); write();
    }));
    textarea.addEventListener('change', load);
    load();
  }

  // ── Dashboard: landmark point picker ───────────────────────────────
  function pointEditor(lat, lng) {
    var mapEl = document.createElement('div');
    var help = document.createElement('p');
    help.className = 'form-text';
    help.textContent = 'Click the map to mark where this landmark is. The latitude and longitude fill in automatically.';
    var host = lat.closest('.col-md-6') || lat.parentNode;
    var col = document.createElement('div');
    col.className = 'col-12';
    col.appendChild(help);
    col.appendChild(mapEl);
    host.parentNode.insertBefore(col, host);

    var map = baseMap(mapEl, '380px');
    var marker = null;

    function place(la, ln, pan) {
      if (marker) marker.setLatLng([la, ln]); else marker = L.marker([la, ln]).addTo(map);
      if (pan) map.setView([la, ln], Math.max(map.getZoom(), 13));
    }
    function fromInputs() {
      var la = parseFloat(lat.value), ln = parseFloat(lng.value);
      if (!isNaN(la) && !isNaN(ln)) place(la, ln, true);
    }
    map.on('click', function (e) {
      lat.value = e.latlng.lat.toFixed(6);
      lng.value = e.latlng.lng.toFixed(6);
      place(e.latlng.lat, e.latlng.lng, false);
    });
    lat.addEventListener('change', fromInputs);
    lng.addEventListener('change', fromInputs);
    fromInputs();
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-clan-map]').forEach(clanMap);
    document.querySelectorAll('textarea[data-boundary-editor]').forEach(boundaryEditor);
    var lat = document.querySelector('input[data-point-lat]');
    var lng = document.querySelector('input[data-point-lng]');
    if (lat && lng) pointEditor(lat, lng);
  });
})();
