"use strict";

const LABELS = {
  OdwolanieKIO: "Odwołanie", Odwolujacy: "Odwołujący", Zamawiajacy: "Zamawiający",
  ZamowieniePubliczne: "Zamówienie publiczne", przelew_bankowy: "Przelew bankowy",
  mocodawca: "Mocodawca", pelnomocnicy: "Pełnomocnicy", podpisujacy: "Podpisujący",
  pelnomocnik: "Pełnomocnik", data: "Data",
  czynnosc_dzien: "Data czynności", czynnosc_powod_id: "Powód (id)", czynnosc_opis: "Zaskarżona czynność",
  miejscowosc: "Miejscowość", krs: "KRS", nip: "NIP", regon: "REGON", nazwa: "Nazwa",
  "przez-pelnomocnika": "Przez pełnomocnika", imie_nazwisko: "Imię i nazwisko", mail: "E-mail",
  prowadzacy_postepowanie: "Prowadzący postępowanie", numer_bzp: "Numer BZP",
  numer_postepowania: "Numer postępowania", numer_ted: "Numer TED", tytul: "Tytuł",
  typ: "Typ", pesel: "PESEL", data_operacji: "Data operacji", kwota: "Kwota",
  na_rachunek: "Na rachunek", z_rachunku: "Z rachunku", numer_transakcji: "Numer transakcji",
};

const DOC_TYPES = {
  odwolanie: "Odwołanie",
  pelnomocnictwo: "Pełnomocnictwo",
  przelew: "Potwierdzenie przelewu",
};

const METHODS = {
  regex: ["z tekstu", ""],
  rule: ["reguła", ""],
  item: ["z tekstu", ""],
  candidate: ["z tekstu", ""],
  enum: ["słownik", ""],
  llm: ["AI", "ai"],
  const: ["stała", ""],
  default: ["domyślna", ""],
  default_if_many: ["domyślna", ""],
  llm_pending: ["brak", ""],
};

const ICONS = {
  file: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/></svg>',
  gavel: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 13l-7.5 7.5a2.1 2.1 0 0 1-3-3L11 10"/><path d="M16 16l6-6M8 8l6-6M9 7l8 8M21 11l-8-8"/></svg>',
  user: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>',
  bldg: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18M5 21V7l7-4 7 4v14M9 21v-6h6v6"/></svg>',
  doc: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></svg>',
  dl: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4v12M7 11l5 5 5-5M5 20h14"/></svg>',
  chev: '<svg class="chev" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 6l6 6-6 6"/></svg>',
  upload: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 16V4M7 9l5-5 5 5"/><path d="M20 16v3a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-3"/></svg>',
  search: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>',
  braces: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M8 4H6a2 2 0 0 0-2 2v4a2 2 0 0 1-2 2 2 2 0 0 1 2 2v4a2 2 0 0 0 2 2h2"/><path d="M16 4h2a2 2 0 0 1 2 2v4a2 2 0 0 0 2 2 2 2 0 0 0-2 2v4a2 2 0 0 1-2 2h-2"/></svg>',
  receipt: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3z"/><path d="M9 9h6M9 13h4"/></svg>',
};

const $ = (sel, el = document) => el.querySelector(sel);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const label = (k) => LABELS[k] || k;
const rowDomId = (docId, path) => `row-${docId}-${path.replace(/[^a-zA-Z0-9_-]/g, "_")}`;

const state = {
  docs: [],
  selectedId: null,
  nextId: 1,
};

function sectionIcon(key) {
  if (/Odwolanie/i.test(key)) return ICONS.gavel;
  if (/Odwolujacy|pelnomocni|podpisujacy/i.test(key)) return ICONS.user;
  if (/Zamawiajacy|mocodawca/i.test(key)) return ICONS.bldg;
  return ICONS.doc;
}

function srcTag(t) {
  if (!t || !t.method) return "";
  const m = t.method;
  if (m.startsWith("decision")) return '<span class="tag ai">model decyzyjny</span>';
  const [txt, cls] = METHODS[m] || [m, ""];
  if (!txt || txt === "brak") return "";
  return `<span class="tag ${cls}">${esc(txt)}</span>`;
}

function collectLeafStats(obj, path, fields, out) {
  for (const [k, v] of Object.entries(obj)) {
    const p = path ? `${path}.${k}` : k;
    if (Array.isArray(v)) {
      if (!v.length) {
        out.push({ key: k, value: null, path: p, trace: fields[p] });
      } else {
        v.forEach((item, i) => {
          if (item && typeof item === "object") collectLeafStats(item, `${p}[${i}]`, fields, out);
          else out.push({ key: k, value: item, path: `${p}[${i}]`, trace: fields[`${p}[${i}]`] });
        });
      }
    } else if (v && typeof v === "object") {
      collectLeafStats(v, p, fields, out);
    } else {
      out.push({ key: k, value: v, path: p, trace: fields[p] });
    }
  }
}

function analyzeDoc(data) {
  if (!data.doctype || !data.result) return { total: 0, review: [], avgConf: null };
  const leaves = [];
  collectLeafStats(data.result, "", data.fields || {}, leaves);
  const review = [];
  let confSum = 0;
  let confCount = 0;

  for (const item of leaves) {
    const t = item.trace;
    const isNull = item.value === null || item.value === undefined || item.value === "";
    if (t && typeof t.prob === "number") {
      confSum += t.prob * 100;
      confCount++;
    } else if (!isNull && t && t.method && t.method !== "llm_pending") {
      confSum += t.method === "llm" ? 92 : 99;
      confCount++;
    }

    if (t && String(t.method || "").startsWith("decision") && (t.prob == null || t.prob < 0.85)) {
      const pct = t.prob != null ? ` · pewność ${Math.round(t.prob * 100)}%` : "";
      review.push({ ...item, why: `Ustalone przez model decyzyjny${pct}` });
    } else if (t && t.method === "llm" && t.grounded === false) {
      review.push({ ...item, why: "Nie potwierdzono dosłownie w tekście" });
    } else if (isNull && (!t || !t.status || t.status === "missing")) {
      // tylko brak w polu, które zwykle występuje; typowe braki i pola „nie dotyczy” nie wymagają sprawdzania
      review.push({ ...item, why: "Nie znaleziono w dokumencie, a pole zwykle występuje" });
    }
  }

  return {
    total: leaves.length,
    review,
    avgConf: confCount ? Math.round(confSum / confCount) : null,
  };
}

// opis pustego pola wg statusu z API (found / absent_ok / not_applicable / missing)
function nullText(t) {
  if (t?.status === "not_applicable") return "nie dotyczy";
  if (t?.status === "absent_ok") return "brak (typowe)";
  return "nie znaleziono";
}

function nullExplanation(t) {
  const note = t?.note ? esc(t.note) : "";
  if (t?.status === "not_applicable") return `Pole nie dotyczy tego dokumentu${note ? ": " + note : ""}.`;
  if (t?.status === "absent_ok") return `Brak wartości jest tu normalny${note ? ": " + note : ""}.`;
  return "Tej informacji nie znaleziono w dokumencie, choć zwykle występuje – warto sprawdzić.";
}

function buildCitation(t, isNull) {
  if (isNull && (!t || !t.quote)) {
    return `<div class="cite">${nullExplanation(t)} W pliku JSON pole ma wartość <code>null</code>.</div>`;
  }
  if (!t) return '<div class="cite">Brak śladu dla tego pola.</div>';

  const meta = [];
  if (t.page) meta.push(`<span>Strona ${t.page}</span>`);
  if (t.prob != null) {
    const pct = Math.round(t.prob * 100);
    meta.push(`<span class="conf ${pct < 80 ? "low" : ""}">Pewność <s style="--w:${pct}%"></s> ${pct}%</span>`);
  }
  if (t.method === "llm") {
    meta.push(`<span>${t.grounded ? "Odczytane przez AI i potwierdzone w tekście ✓" : "Odczytane przez AI (nie znaleziono w tekście)"}</span>`);
  } else if (String(t.method || "").startsWith("decision")) {
    meta.push("<span>Wybrane przez model z listy czynności</span>");
  }

  let body = "";
  if (t.quote) {
    body = `<q>${t.before ? "…" + esc(t.before) + " " : ""}</q><mark>${esc(t.quote)}</mark><q>${t.after ? " " + esc(t.after) + "…" : ""}</q>`;
  } else if (t.method === "enum") {
    body = `<span style="color:var(--muted)">Wartość ze słownika na podstawie pola <code>${esc(t.from)}</code>.</span>`;
  } else if (["const", "default", "default_if_many"].includes(t.method)) {
    body = '<span style="color:var(--muted)">Wartość domyślna z konfiguracji.</span>';
  } else if (isNull) {
    body = '<span style="color:var(--muted)">Tej informacji nie znaleziono w dokumencie.</span>';
  }

  let tech = "";
  if (t.question) tech += `<details><summary>Pytanie do modelu</summary>${esc(t.question)} → <b>${esc(t.answer)}</b></details>`;
  if (t.pattern) tech += `<details><summary>Wzorzec techniczny</summary><code>${esc(t.pattern)}</code></details>`;
  if (t.raw && t.method === "llm") tech += `<details><summary>Surowa odpowiedź modelu</summary>${esc(t.raw)}</details>`;

  return `<div class="cite">${meta.length ? `<div class="cite-m">${meta.join("")}</div>` : ""}${body}${tech}</div>`;
}

function renderRow(docId, key, value, path, fields, flaggedPaths) {
  const t = (fields || {})[path];
  const isNull = value === null || value === undefined || value === "";
  const isFlagged = flaggedPaths.has(path);
  return `<div class="row" id="${rowDomId(docId, path)}">
    <button class="row-b" type="button" aria-expanded="false">
      <span class="k">${esc(label(key))}</span>
      <span class="v ${isNull ? "null" : ""} ${isFlagged && !isNull ? "flag" : ""}">${isNull ? nullText(t) : esc(value)}</span>
      <span class="src">${srcTag(t)}${ICONS.chev}</span>
    </button>
    ${buildCitation(t, isNull)}
  </div>`;
}

function renderObjectHtml(docId, obj, path, fields, flaggedPaths) {
  let html = "";
  for (const [k, v] of Object.entries(obj)) {
    const p = path ? `${path}.${k}` : k;
    if (Array.isArray(v)) {
      if (!v.length) {
        html += renderRow(docId, k, null, p, fields, flaggedPaths);
      } else {
        v.forEach((item, i) => {
          const title = `${label(k)}${v.length > 1 ? " #" + (i + 1) : ""}`;
          const inner = item && typeof item === "object"
            ? renderObjectHtml(docId, item, `${p}[${i}]`, fields, flaggedPaths)
            : renderRow(docId, k, item, `${p}[${i}]`, fields, flaggedPaths);
          html += `<div class="sub"><div class="sub-t">${esc(title)}</div>${inner}</div>`;
        });
      }
    } else if (v && typeof v === "object") {
      const title = k === "data" ? "Dane podmiotu" : label(k);
      html += `<div class="sub"><div class="sub-t">${esc(title)}</div>${renderObjectHtml(docId, v, p, fields, flaggedPaths)}</div>`;
    } else {
      html += renderRow(docId, k, v, p, fields, flaggedPaths);
    }
  }
  return html;
}

function docTitle(doc) {
  if (doc.status === "loading") return doc.file;
  if (doc.status === "error") return doc.file;
  const base = DOC_TYPES[doc.data?.doctype] || "Dokument";
  const r = doc.data?.result;
  const party = r?.Odwolujacy?.[0]?.nazwa || r?.mocodawca?.nazwa || r?.przelew_bankowy?.kwota;
  return party ? `${base} — ${party}` : base;
}

function renderSidebar() {
  const box = $("#docs");
  if (!state.docs.length) {
    box.innerHTML = '<div class="docs-empty">Brak wgranych plików. Upuść PDF powyżej, aby rozpocząć.</div>';
    return;
  }

  box.innerHTML = state.docs.map((doc) => {
    const active = doc.id === state.selectedId ? "active" : "";
    if (doc.status === "loading") {
      return `<div class="doc ${active}">
        <div class="doc-ic">${ICONS.file}</div>
        <div>
          <div class="doc-t">${esc(doc.file)}</div>
          <div class="chip run">Odczytywanie dokumentu…</div>
          <div class="bar"><span></span></div>
        </div>
      </div>`;
    }
    if (doc.status === "error") {
      return `<button class="doc ${active}" type="button" data-select="${doc.id}">
        <div class="doc-ic">${ICONS.file}</div>
        <div>
          <div class="doc-t">Błąd odczytu</div>
          <div class="doc-f">${esc(doc.file)}</div>
          <div class="chip err"><i></i>Nie udało się przetworzyć</div>
        </div>
      </button>`;
    }
    const typeLabel = DOC_TYPES[doc.data.doctype] || "Nie rozpoznano";
    const revCount = doc.analysis.review.length;
    const chip = !doc.data.doctype
      ? '<div class="chip err"><i></i>Nie rozpoznano typu</div>'
      : revCount
        ? `<div class="chip warn"><i></i>${revCount} ${revCount === 1 ? "pole" : revCount < 5 ? "pola" : "pól"} do sprawdzenia</div>`
        : '<div class="chip ok"><i></i>Gotowe</div>';

    return `<button class="doc ${active}" type="button" data-select="${doc.id}">
      <div class="doc-ic">${ICONS.file}</div>
      <div>
        <div class="doc-t">${esc(typeLabel)}</div>
        <div class="doc-f">${esc(doc.file)}</div>
        ${chip}
      </div>
    </button>`;
  }).join("");

  box.querySelectorAll("[data-select]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.selectedId = Number(btn.dataset.select);
      render();
    });
  });
}

function renderMain() {
  const main = $("#main");
  const doc = state.docs.find((d) => d.id === state.selectedId);
  main.classList.toggle("is-empty", !doc || doc.status === "loading");

  if (!doc) {
    main.innerHTML = `<article class="panel panel-welcome" id="welcome-drop">
      <div class="empty">
        <div class="empty-mark" aria-hidden="true">${ICONS.braces}</div>
        <div class="empty-pill">Obsługa spraw KIO · PDF → JSON</div>
        <h2>Automatyczny odczyt akt sprawy KIO</h2>
        <p class="empty-lead">Upuść pliki PDF po lewej lub <button class="link" type="button" id="btn-empty-upload">wybierz z dysku</button> — obsługiwane są także skany OCR.</p>

        <div class="doc-kinds">
          <span class="doc-kind">${ICONS.gavel} Odwołanie KIO</span>
          <span class="doc-kind">${ICONS.user} Pełnomocnictwo</span>
          <span class="doc-kind">${ICONS.receipt} Potwierdzenie przelewu</span>
        </div>

        <div class="steps">
          <div class="step">
            <div class="step-ic" aria-hidden="true">${ICONS.upload}</div>
            <div class="step-k">Krok 1</div>
            <div class="step-t">Wgraj dokumenty</div>
            <p>Rozpoznawanie klasy pisma oraz odczyt tekstu i skanów OCR.</p>
          </div>
          <div class="step">
            <div class="step-ic" aria-hidden="true">${ICONS.search}</div>
            <div class="step-k">Krok 2</div>
            <div class="step-t">Zweryfikuj cytaty</div>
            <p>Braki i ustalenia AI są oznaczone wraz ze stroną źródłową.</p>
          </div>
          <div class="step">
            <div class="step-ic" aria-hidden="true">${ICONS.dl}</div>
            <div class="step-k">Krok 3</div>
            <div class="step-t">Pobierz JSON</div>
            <p>Gotowy wynik zgodny ze schematem wyeksportujesz jednym kliknięciem.</p>
          </div>
        </div>
      </div>
    </article>`;

    const welcomeDrop = $("#welcome-drop");
    $("#btn-empty-upload").addEventListener("click", () => input.click());
    ["dragenter", "dragover"].forEach((ev) => welcomeDrop.addEventListener(ev, (e) => {
      e.preventDefault();
      welcomeDrop.classList.add("over");
    }));
    ["dragleave", "drop"].forEach((ev) => welcomeDrop.addEventListener(ev, (e) => {
      e.preventDefault();
      welcomeDrop.classList.remove("over");
    }));
    welcomeDrop.addEventListener("drop", (e) => handleFiles(e.dataTransfer.files));
    return;
  }

  if (doc.status === "loading") {
    main.innerHTML = `<article class="panel panel-welcome">
      <div class="empty">
        <div class="empty-mark" aria-hidden="true">${ICONS.braces}</div>
        <div class="empty-pill">Trwa analiza dokumentu</div>
        <h2>Przetwarzanie: ${esc(doc.file)}</h2>
        <p class="empty-lead">Trwa odczyt tekstu i wyodrębnianie danych do struktury JSON…</p>
        <div class="loading-bar"><span></span></div>
      </div>
    </article>`;
    return;
  }

  if (doc.status === "error") {
    main.innerHTML = `<article class="panel">
      <div class="p-head">
        <div>
          <div class="eyebrow">Błąd przetwarzania</div>
          <h1>${esc(doc.file)}</h1>
        </div>
      </div>
      <div class="p-body">
        <div class="err-box">${esc(doc.error)}</div>
      </div>
    </article>`;
    return;
  }

  const d = doc.data;
  if (!d.doctype) {
    main.innerHTML = `<article class="panel">
      <div class="p-head">
        <div>
          <div class="eyebrow">Nie rozpoznano klasy dokumentu</div>
          <h1>${esc(doc.file)}</h1>
          <div class="p-meta">${d.seconds.toFixed(1)} s</div>
        </div>
      </div>
      <div class="p-body">
        <div class="err-box">Dokument nie pasuje do żadnej z obsługiwanych klas (odwołanie, pełnomocnictwo, potwierdzenie przelewu).
          Zgodnie z ustaleniem z organizatorem wynikiem jest pusty obiekt JSON (w trybie wsadowym: plik z <code>{}</code>).</div>
        <pre class="json-pre" style="margin-top:12px">{}</pre>
      </div>
    </article>`;
    return;
  }

  const { total, review, avgConf } = doc.analysis;
  const flaggedPaths = new Set(review.map((r) => r.path));
  const ocr = String(d.text_method || "").startsWith("ocr") ? " · OCR" : "";
  const json = JSON.stringify(d.result, null, 2);
  const reviewShown = review.slice(0, 6);

  const reviewHtml = review.length ? `<section class="review">
    <h2>Sprawdź ${review.length} ${review.length === 1 ? "pole" : review.length < 5 ? "pola" : "pól"} przed użyciem</h2>
    <p class="lead">Pozostałe dane odczytano wprost z tekstu dokumentu.</p>
    ${reviewShown.map((r) => {
      const hasValue = r.value !== null && r.value !== undefined && r.value !== "";
      const hasQuote = hasValue && Boolean(r.trace?.quote);
      return `<div class="r-item">
        <div>
          <div class="r-l">${esc(label(r.key))}</div>
          <div class="r-v">${hasValue ? esc(r.value) : '<span style="color:var(--faint);font-weight:400;font-style:italic">brak</span>'}</div>
          <div class="r-why">${esc(r.why)}</div>
        </div>
        ${hasQuote ? `<button class="link" type="button" data-jump="${rowDomId(doc.id, r.path)}">Pokaż w dokumencie →</button>` : ""}
      </div>`;
    }).join("")}
    ${review.length > reviewShown.length ? `<div class="r-l" style="padding-top:8px">…oraz ${review.length - reviewShown.length} kolejnych pól oznaczonych poniżej.</div>` : ""}
  </section>` : "";

  const sectionsHtml = Object.entries(d.result).map(([k, v]) => {
    let inner = "";
    if (Array.isArray(v)) {
      inner = v.map((item, i) => `
        <div class="sub">
          <div class="sub-t">${esc(label(k))} #${i + 1}</div>
          ${renderObjectHtml(doc.id, item, `${k}[${i}]`, d.fields, flaggedPaths)}
        </div>
      `).join("");
    } else {
      inner = renderObjectHtml(doc.id, v, k, d.fields, flaggedPaths);
    }
    return `<section class="sec">
      <div class="sec-h"><span class="sec-ic">${sectionIcon(k)}</span><h3>${esc(label(k))}</h3></div>
      ${inner}
    </section>`;
  }).join("");

  main.innerHTML = `<article class="panel">
    <div class="p-head">
      <div>
        <div class="eyebrow">${esc(DOC_TYPES[d.doctype] || d.doctype)} · ${d.seconds.toFixed(1)} s${ocr}</div>
        <h1>${esc(docTitle(doc))}</h1>
        <div class="p-meta">${esc(doc.file)}</div>
      </div>
      <div class="actions">
        <button class="btn btn-g" type="button" id="btn-raw">JSON</button>
        <button class="btn btn-p" type="button" id="btn-dl">${ICONS.dl} Pobierz JSON</button>
      </div>
    </div>

    <div class="stats">
      <div class="stat"><b>${total}</b><span>pól odczytanych</span></div>
      <div class="stat ${review.length ? "warn" : ""}"><b>${review.length}</b><span>do sprawdzenia</span></div>
      <div class="stat"><b>${avgConf != null ? avgConf + "%" : "—"}</b><span>średnia pewność</span></div>
    </div>

    <div class="p-body">
      <pre class="raw" id="raw">${esc(json)}</pre>
      ${reviewHtml}
      ${sectionsHtml}
      <div class="foot">Kliknij dowolne pole, aby zobaczyć fragment dokumentu, z którego pochodzi.</div>
    </div>
  </article>`;

  $("#btn-raw").addEventListener("click", () => $("#raw").classList.toggle("show"));
  $("#btn-dl").addEventListener("click", () => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([json], { type: "application/json" }));
    a.download = doc.file.replace(/\.pdf$/i, "") + ".json";
    a.click();
    URL.revokeObjectURL(a.href);
  });

  main.querySelectorAll(".row-b").forEach((btn) => {
    btn.addEventListener("click", () => {
      const row = btn.parentElement;
      const open = row.classList.toggle("open");
      btn.setAttribute("aria-expanded", String(open));
    });
  });

  main.querySelectorAll("[data-jump]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = document.getElementById(btn.dataset.jump);
      if (!target) return;
      target.classList.add("open");
      target.querySelector(".row-b")?.setAttribute("aria-expanded", "true");
      target.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  });
}

function render() {
  renderSidebar();
  renderMain();
}

async function processFile(file) {
  const doc = { id: state.nextId++, file: file.name, status: "loading", data: null, error: null, analysis: null };
  state.docs.unshift(doc);
  if (state.selectedId === null || state.docs.length === 1) state.selectedId = doc.id;
  render();

  const t0 = performance.now();
  try {
    const r = await fetch("/api/process", {
      method: "POST",
      headers: { "Content-Type": "application/pdf", "X-Filename": encodeURIComponent(file.name) },
      body: file,
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
    data.seconds = (performance.now() - t0) / 1000;
    doc.status = "done";
    doc.data = data;
    doc.analysis = analyzeDoc(data);
  } catch (e) {
    doc.status = "error";
    doc.error = e.message;
  }
  render();
}

function handleFiles(list) {
  const pdfs = [...list].filter((f) => /\.pdf$/i.test(f.name) || f.type === "application/pdf");
  pdfs.forEach(processFile);
}

const drop = $("#drop");
const input = $("#file");
drop.addEventListener("click", () => input.click());
drop.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    input.click();
  }
});
input.addEventListener("change", () => {
  handleFiles(input.files);
  input.value = "";
});
["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => {
  e.preventDefault();
  drop.classList.add("over");
}));
["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => {
  e.preventDefault();
  drop.classList.remove("over");
}));
drop.addEventListener("drop", (e) => handleFiles(e.dataTransfer.files));

render();
