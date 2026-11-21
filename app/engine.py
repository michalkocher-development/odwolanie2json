"""Silnik ekstrakcji sterowany konfiguracją YAML (config/doctypes/*.yaml).

Drzewo `output` w YAML odwzorowuje strukturę wynikowego JSON:
- dict z kluczem z LEAF_KEYS  -> pole (liść),
- zwykły dict                 -> obiekt zagnieżdżony,
- lista z jednym szablonem    -> lista obiektów (`_each` / `_scope` w szablonie).

Klucze liścia:
  scope:     nazwa sekcji z `sections` albo "head" (pierwsze head_chars znaków)
  within:    regex zawężający tekst do pierwszego dopasowania
  regex:     wzorzec lub lista wzorców; pierwsze trafienie wygrywa
  group:     numer/nazwa grupy (domyślnie 1 albo cały match gdy brak grup)
  rules:     lista {pattern, value}; pierwsza pasująca reguła daje wartość
  take:      "item" -> tekst bieżącego elementu listy
  const:     stała wartość (np. null)
  from+enum: mapowanie wartości innego pola przez słownik z `enums`
  normalize: nazwa normalizatora lub lista (app/normalize.py)
  default:   wartość, gdy nic nie znaleziono
  jev:       model decyzyjny (wybór z `enum`); prefer: jev -> model najpierw, reguły/regex jako zapas
  llm:       opis pola dla fallbacku LLM (gdy reguły nic nie dały); verify: opis do weryfikacji (opcjonalnie)
Każde pole zapisuje ślad (metoda, wzorzec, fragment źródłowy) do trace.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from . import normalize

LEAF_KEYS = {"regex", "rules", "take", "const", "from", "llm", "jev", "candidates"}
FLAGS = re.MULTILINE | re.IGNORECASE


@dataclass
class Ctx:
    text: str
    spec: dict[str, Any]
    sections: dict[str, str]
    trace: list[dict[str, Any]] = field(default_factory=list)
    values: dict[str, Any] = field(default_factory=dict)  # path -> value (dla `from`)
    idx: list[int] = field(default_factory=list)  # indeksy bieżących elementów list (stos)
    lens: list[int] = field(default_factory=list)  # długości bieżących list (stos)
    pending: list[tuple[str, dict[str, Any], str | None]] = field(default_factory=list)  # pola dla LLM
    alt_text: str | None = None  # drugi wariant kolejności tekstu (strumień PDF) – dla LLM i ugruntowania
    pending_lists: list[tuple[str, dict[str, Any], str | None]] = field(default_factory=list)  # listy dla LLM
    verify: list[tuple[str, dict[str, Any], str | None, Any, dict[str, Any]]] = field(default_factory=list)  # do weryfikacji
    selects: list[tuple[str, dict[str, Any], str | None]] = field(default_factory=list)  # listy z polem `select_one`


def _compile(pattern: str, ci: bool = True) -> re.Pattern[str]:
    return re.compile(pattern, FLAGS if ci else re.MULTILINE)


def find_sections(text: str, spec: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {"all": text, "head": text[: spec.get("head_chars", 6000)]}
    for name, s in (spec.get("sections") or {}).items():
        starts = s["start"] if isinstance(s["start"], list) else [s["start"]]
        for st in starts:
            m = _compile(st, s.get("ci", True)).search(text)
            if not m:
                continue
            begin = m.end() if not s.get("include_start") else m.start()
            rest = text[begin:]
            end = len(rest)
            if s.get("end"):
                e = _compile(s["end"], s.get("ci", True)).search(rest)
                if e:
                    end = e.start()
            out[name] = rest[: min(end, s.get("max_chars", 4000))]
            break
    return out


def _scope_text(leaf: dict[str, Any], ctx: Ctx, item: str | None) -> str | None:
    scope = leaf.get("scope")
    if scope:
        txt = ctx.sections.get(scope)
        if txt is None and leaf.get("scope_fallback"):
            txt = ctx.sections.get(leaf["scope_fallback"])
    else:
        txt = item if item is not None else ctx.text
    if txt is not None and leaf.get("within"):
        # lista wzorców: łączymy pierwsze trafienia każdego (w kolejności z YAML)
        pats = leaf["within"] if isinstance(leaf["within"], list) else [leaf["within"]]
        parts = []
        for pat in pats:
            alts = pat if isinstance(pat, list) else [pat]  # podlista = alternatywy, pierwsza trafiona wygrywa
            for alt in alts:
                if m := _compile(alt).search(txt):
                    parts.append(m.group(0))
                    break
        txt = "\n".join(parts) if parts else None
    return txt


def _jev_fallback(leaf: dict[str, Any], ctx: Ctx, item: str | None) -> tuple[Any, dict[str, Any]]:
    """Model decyzyjny JEV: wybór jednej z opcji (enum z YAML) na podstawie zawężonego tekstu."""
    from . import backend, jev

    cfg = leaf["jev"]
    if not jev.enabled():  # JEV_DISABLE=1 wyłącza decyzje niezależnie od dostawcy
        return None, {}
    state = _scope_text({**leaf, **{k: cfg[k] for k in ("scope", "within") if k in cfg}}, ctx, item)
    if not state and cfg.get("fallback_scope"):  # dokument o innym układzie: szerszy kontekst
        sec = ctx.sections.get(cfg["fallback_scope"])
        if sec and cfg.get("fallback_after"):
            m = _compile(cfg["fallback_after"]).search(sec)
            sec = sec[m.start():] if m else sec
        state = sec
    if not state:
        return None, {}
    state = normalize.ws(state)[: cfg.get("max_chars", 2500)]
    table = ctx.spec["enums"][cfg["enum"]]
    keys = list(table)
    options = [str(table[k]) for k in keys] + ([cfg["other"]] if cfg.get("other") else [])
    try:
        idx, prob = backend.choose(state, cfg["question"], options)
    except Exception as e:  # serwer niedostępny -> brak wartości, pipeline działa dalej
        return None, {"method": "jev", "error": str(e)}
    how = {"method": f"decision:{backend.decision_provider()}", "question": cfg["question"], "answer": options[idx],
           "prob": round(prob, 3) if prob is not None else None, **_cite(ctx, state[:600])}
    if idx >= len(keys) or (prob is not None and prob < cfg.get("min_prob", 0.0)):
        return None, how
    return keys[idx], how


def _cite(ctx: Ctx, quote: str | None, txt: str | None = None, start: int | None = None) -> dict[str, Any]:
    """Cytat źródłowy pola: dokładny fragment tekstu, nr strony i kontekst (dla interfejsu / audytu).

    Pozycja: jeśli znamy dopasowanie w tekście zakresu (`txt`, `start`), przeliczamy ją na pozycję
    w całym dokumencie; inaczej szukamy cytatu w dokumencie (odporne na różnice białych znaków).
    """
    if not quote or not str(quote).strip():
        return {}
    text, quote = ctx.text, str(quote)
    a = b = -1

    def find(needle: str, hay: str, base: int = 0) -> tuple[int, int]:
        words = re.findall(r"\S+", needle)[:60]
        m = re.search(r"\s+".join(map(re.escape, words)), hay, re.IGNORECASE) if words else None
        return (base + m.start(), base + m.end()) if m else (-1, -1)

    if txt is not None and start is not None and (off := text.find(txt)) >= 0:
        a, b = off + start, off + start + len(quote)
    elif txt is not None and start is not None:
        # tekst zakresu sklejony z kilku fragmentów: szukamy cytatu razem z jego otoczeniem
        anchor = txt[max(0, start - 60): start + len(quote) + 60]
        aa, bb = find(anchor, text)
        if aa >= 0:
            a, b = find(quote, text[aa:bb], aa)
    if a < 0:
        a, b = find(quote, text)
    if a < 0:
        return {"quote": normalize.ws(quote)[:500]}
    while a > 0 and text[a - 1].isalnum():  # cytat do granic słów (reguły dopasowują rdzenie)
        a -= 1
    while b < len(text) and text[b].isalnum():
        b += 1
    w = 160
    return {
        "quote": normalize.ws(text[a:b]),
        "page": text.count("\f", 0, a) + 1,
        "before": normalize.ws(text[max(0, a - w): a]),
        "after": normalize.ws(text[b: b + w]),
    }


def _candidates(leaf: dict[str, Any], ctx: Ctx, item: str | None) -> tuple[Any, dict[str, Any]]:
    """`candidates`: zbierz wszystkie dopasowania luźnego wzorca w zakresie; 1 kandydat -> bierzemy,
    kilku -> wybór modelem decyzyjnym (z opcją „brak”). Model nie wymyśla wartości – tylko wybiera z tekstu.
    `nominative: true` – forma po „w/we” (miejscownik) jest zamieniana na mianownik przez LLM z kontrolą rdzenia."""
    from . import backend, jev

    cfg = leaf["candidates"]
    keys = ("scope", "scope_fallback", "within")
    src = cfg if any(k in cfg for k in keys) else leaf  # zakres kandydatów może być inny niż zakres regexu
    txt = _scope_text({k: src[k] for k in keys if k in src}, ctx, item)
    if txt and cfg.get("within_line"):  # tylko pierwsza linia zawierająca wzorzec (np. linia z datą w nagłówku)
        line = re.search(rf"^[^\n]*(?:{cfg['within_line']})[^\n]*", txt, re.MULTILINE)
        txt = line.group(0) if line else None
    if not txt:
        return None, {}
    seen: dict[str, re.Match[str]] = {}
    for m in _compile(cfg["regex"], cfg.get("ci", False)).finditer(txt):
        raw = normalize.ws(m.group(1) if m.re.groups else m.group(0))
        if raw and raw.lower() not in {s.lower() for s in cfg.get("exclude", [])}:
            seen.setdefault(raw, m)
    if not seen:
        return None, {}
    cands = list(seen)
    prob = None
    if len(cands) == 1:
        idx = 0
    else:
        if not jev.enabled():
            return None, {}
        try:
            idx, prob = backend.choose(normalize.ws(txt)[:2000], cfg["question"], cands + [cfg.get("none", "Brak")])
        except Exception:
            return None, {}
        if idx >= len(cands):
            return None, {"method": "decision:candidates", "answer": cfg.get("none", "Brak"), "prob": prob}
    raw, m = cands[idx], seen[cands[idx]]
    how = {"method": "candidate" if prob is None else "decision:candidates", "candidates": cands,
           "prob": round(prob, 3) if prob is not None else None,
           **_cite(ctx, m.group(1) if m.re.groups else m.group(0), txt, m.start(1) if m.re.groups else m.start())}
    if cfg.get("nominative") and re.search(r"\bwe?\s+$", txt[: m.start(1) if m.re.groups else m.start()]):
        raw = _to_nominative(raw) or raw
        how["nominative"] = raw
    return normalize.apply(raw, leaf.get("normalize")), how


def _to_nominative(word: str) -> str | None:
    """Miejscownik -> mianownik nazwy miejscowości ("Wrocławiu" -> "Wrocław") przez LLM; wynik musi mieć ten sam rdzeń."""
    from . import backend, llm

    if not llm.enabled():
        return None
    try:
        out = backend.generate_json(
            f"Podaj nazwę miejscowości w mianowniku (np. 'w Gdańsku' -> 'Gdańsk', 'w Łodzi' -> 'Łódź'): 'w {word}'",
            {"type": "object", "properties": {"mianownik": {"type": "string"}}, "required": ["mianownik"]})
    except Exception:
        return None
    nom = str(out.get("mianownik", "")).strip()
    stem = lambda w: re.sub(r"[^\w]", "", w.lower())[:3]  # noqa: E731
    return nom if nom and stem(nom) == stem(word) else None


def extract_leaf(leaf: dict[str, Any], ctx: Ctx, path: str, item: str | None) -> Any:
    value: Any = None
    how: dict[str, Any] = {}

    if "const" in leaf:
        value, how = leaf["const"], {"method": "const"}
    elif "from" in leaf:
        src = ctx.values.get(leaf["from"])
        table = ctx.spec.get("enums", {}).get(leaf["enum"], {})
        value = table.get(src) if src is not None else None
        how = {"method": "enum", "from": leaf["from"]}
    else:
        txt = _scope_text(leaf, ctx, item)
        if leaf.get("prefer") == "jev" and "jev" in leaf:  # model decyzyjny najpierw, reguły jako zapas
            value, how = _jev_fallback(leaf, ctx, item)
            if value is not None:
                txt = None  # pomiń reguły/regex
        if txt is not None and leaf.get("take") == "item":
            value, how = txt, {"method": "item", **_cite(ctx, txt.strip())}
        elif txt is not None and "rules" in leaf:
            for rule in leaf["rules"]:
                m = _compile(rule["pattern"]).search(txt)
                if m:
                    value = rule["value"]
                    how = {"method": "rule", "pattern": rule["pattern"], **_cite(ctx, m.group(0), txt, m.start())}
                    break
        elif txt is not None and "regex" in leaf:
            pats = leaf["regex"] if isinstance(leaf["regex"], list) else [leaf["regex"]]
            for pat in pats:
                nth = 1
                if isinstance(pat, dict):  # {pattern, nth}: weź n-te poprawne trafienie
                    pat, nth = pat["pattern"], pat.get("nth", 1)
                for m in _compile(pat, leaf.get("ci", True)).finditer(txt):
                    g = leaf.get("group", 1 if m.re.groups else 0)
                    raw = m.group(g)
                    if raw is None:
                        continue
                    cand = normalize.apply(raw, leaf.get("normalize"))
                    if cand in (None, ""):
                        continue
                    if leaf.get("validate") and not re.fullmatch(leaf["validate"], str(cand)):
                        continue
                    nth -= 1
                    if nth > 0:
                        continue
                    value = cand
                    how = {"method": "regex", "pattern": pat, **_cite(ctx, raw, txt, m.start(g))}
                    break
                if value is not None:
                    break
        if value is None and "candidates" in leaf:
            value, how = _candidates(leaf, ctx, item)
        if value is None and "jev" in leaf and leaf.get("prefer") != "jev":
            value, how = _jev_fallback(leaf, ctx, item)
        if value is None and "llm" in leaf and "default" not in leaf:
            ctx.pending.append((path, leaf, item))  # uzupełni run_llm() po zbudowaniu drzewa
            how = {"method": "llm_pending"}

    if value is not None and "normalize" in leaf and how.get("method") in ("rule", "item", "enum"):
        value = normalize.apply(value, leaf["normalize"])
    if value is None and "default_if_many" in leaf and ctx.lens and ctx.lens[-1] > 1:
        value, how = leaf["default_if_many"], {"method": "default_if_many"}
    if value is None and "default" in leaf:
        value, how = leaf["default"], {"method": "default"}
    ctx.values[path.split(".")[-1]] = value
    ctx.values[path] = value
    entry = {"field": path, "value": value, **how}
    ctx.trace.append(entry)
    if value is not None and "verify" in leaf and how.get("method") in ("regex", "rule", "item"):
        ctx.verify.append((path, leaf, item, value, entry))  # sprawdzi run_verify() modelem decyzyjnym
    return value


def build(node: Any, ctx: Ctx, path: str = "", item: str | None = None) -> Any:
    if isinstance(node, dict):
        if LEAF_KEYS & node.keys():
            return extract_leaf(node, ctx, path, item)
        return {
            k: build(v, ctx, f"{path}.{k}" if path else k, item)
            for k, v in node.items()
            if not k.startswith("_")
        }
    if isinstance(node, list):
        tmpl = node[0]
        items = _list_items(tmpl, ctx, item)
        if items == [""] and tmpl.get("_each") and "_llm" in tmpl:
            ctx.pending_lists.append((path, tmpl, item))  # regex nic nie znalazł -> lista z LLM (run_llm)
        elif len(items) == 1 and "_count_check" in tmpl and "_llm" in tmpl and _more_items(tmpl, ctx, item):
            ctx.pending_lists.append((path, tmpl, item))  # model decyzyjny: elementów jest więcej niż znalazł regex
        if any(isinstance(v, dict) and "select_one" in v for v in tmpl.values()):
            ctx.selects.append((path, tmpl, item))
        out = []
        for i, it in enumerate(items):
            ctx.idx.append(i)
            ctx.lens.append(len(items))
            out.append(build(tmpl, ctx, f"{path}[{i}]", it))
            ctx.idx.pop()
            ctx.lens.pop()
        return out
    return node


def _list_items(tmpl: dict[str, Any], ctx: Ctx, item: str | None) -> list[str]:
    base = ctx.sections.get(tmpl["_scope"]) if "_scope" in tmpl else (item or ctx.text)
    if base is None:
        return [] if tmpl.get("_optional") else [""]
    if tmpl.get("_blocks") and ctx.idx:
        # Tekst dzielony na bloki nagłówkiem (np. "W imieniu X:"); element rodzica nr i dostaje blok nr i.
        heads = list(_compile(tmpl["_blocks"]).finditer(base))
        if len(heads) >= 2:
            i = ctx.idx[-1]
            if i >= len(heads):
                return []
            end = heads[i + 1].start() if i + 1 < len(heads) else len(base)
            base = base[heads[i].end(): end]
    each = tmpl.get("_each")
    if not each:
        return [base]
    seen: list[str] = []
    keys: set[str] = set()
    for m in _compile(each, tmpl.get("_ci", True)).finditer(base):
        it = m.group(1) if m.re.groups else m.group(0)
        p = normalize.person(re.sub(r"\(.*", "", it, flags=re.S))
        key = " ".join(re.findall(r"[^\W\d_][\w-]*", p)[:2]).lower()  # imię + nazwisko
        if key not in keys:
            keys.add(key)
            seen.append(it)
    if not seen and tmpl.get("_each_fallback") == "whole":
        return [base]
    if not seen and not tmpl.get("_optional"):
        return [""]
    return seen


def _set_path(obj: Any, path: str, value: Any) -> None:
    tokens = [int(t) if t.isdigit() else t for t in re.findall(r"[^.\[\]]+", path)]
    for t in tokens[:-1]:
        obj = obj[t]
    obj[tokens[-1]] = value


def _grounding(leaf: dict[str, Any]) -> str:
    norm = leaf.get("normalize") or []
    return leaf.get("llm_grounding") or ("stem" if "person" in ([norm] if isinstance(norm, str) else norm) else "exact")


def _llm_value(raw: str | None, ok: bool, leaf: dict[str, Any], strict: bool) -> Any:
    if raw is None or not (ok or not strict):
        return None
    value = normalize.apply(raw, leaf.get("normalize"))
    if value is not None and leaf.get("validate") and not re.fullmatch(leaf["validate"], str(value)):
        return None
    return value


def run_llm(result: Any, ctx: Ctx) -> None:
    """Jedno wywołanie LLM dla wszystkich pustych pól z kluczem `llm` (opis pola) i pustych list z `_llm`."""
    from . import llm

    if not (ctx.pending or ctx.pending_lists) or not llm.enabled():
        return
    fid = lambda p: re.sub(r"\W+", "_", p).strip("_")  # noqa: E731
    ids: dict[str, tuple[str, dict[str, Any], str | None, bool]] = {}
    fields: dict[str, dict[str, Any]] = {}
    for p, leaf, item in ctx.pending:
        ids[fid(p)] = (p, leaf, item, False)
        fields[fid(p)] = {"desc": leaf["llm"], "context": normalize.ws(item)[:200] if item else None,
                          "grounding": _grounding(leaf)}
    for p, tmpl, item in ctx.pending_lists:
        leaves = {k: v for k, v in tmpl.items() if isinstance(v, dict) and LEAF_KEYS & v.keys()
                  and k not in tmpl.get("_llm_skip", [])}
        ids[fid(p)] = (p, tmpl, item, True)
        fields[fid(p)] = {"desc": tmpl["_llm"], "context": normalize.ws(item)[:200] if item else None,
                          "items": {k: {"desc": v.get("llm", k), "grounding": _grounding(v)} for k, v in leaves.items()}}
    try:
        answers = llm.extract(ctx.spec["name"], ctx.alt_text or ctx.text, fields, ground=[ctx.text])
    except Exception as e:  # serwer niedostępny -> pola zostają puste
        ctx.trace.append({"field": "*", "method": "llm", "error": str(e)})
        return
    strict = llm.settings().get("require_grounding", True)
    for key, ans in answers.items():
        path, node, _, is_list = ids[key]
        if not is_list:
            raw, ok = ans
            value = _llm_value(raw, ok, node, strict)
            if value is not None:
                _set_path(result, path, value)
            ctx.trace.append({"field": path, "value": value, "method": "llm", "raw": raw, "grounded": ok,
                              **(_cite(ctx, raw) if ok else {})})
            continue
        rows = []
        for i, row in enumerate(ans):
            obj = {}
            for k, (raw, ok) in row.items():
                obj[k] = _llm_value(raw, ok, node[k], strict)
                ctx.trace.append({"field": f"{path}[{i}].{k}", "value": obj[k], "method": "llm", "raw": raw,
                                  "grounded": ok, **(_cite(ctx, raw) if ok else {})})
            if any(v is not None for v in obj.values()):
                # pełna struktura wg szablonu (pola pominięte w LLM, np. flagi z select_one -> None)
                rows.append({k: obj.get(k) for k in node if not k.startswith("_")})
        if rows:
            _set_path(result, path, rows)


def _more_items(tmpl: dict[str, Any], ctx: Ctx, item: str | None) -> bool:
    """`_count_check`: pytanie tak/nie do modelu decyzyjnego, czy lista ma więcej niż jeden element."""
    from . import backend, jev

    if not jev.enabled():
        return False
    state = ctx.sections.get(tmpl.get("_scope", "")) or item or ctx.sections.get("head") or ctx.text
    try:
        p = backend.noul(normalize.ws(state)[:2000], tmpl["_count_check"])
    except Exception:
        return False
    ctx.trace.append({"field": "*", "method": "decision:count_check", "question": tmpl["_count_check"], "prob": round(p, 3)})
    return p >= 0.5


def _get_path(obj: Any, path: str) -> Any:
    for t in [int(t) if t.isdigit() else t for t in re.findall(r"[^.\[\]]+", path)]:
        obj = obj[t]
    return obj


def run_select(result: Any, ctx: Ctx) -> None:
    """`select_one`: przy liście z >1 elementem model decyzyjny wskazuje jeden element (np. zamawiającego
    prowadzącego postępowanie) -> 1, pozostałe -> 0. Pomijane, gdy reguły już wskazały element (wartość 1)."""
    from . import backend, jev

    for path, tmpl, item in ctx.selects:
        try:
            lst = _get_path(result, path)
        except (KeyError, IndexError, TypeError):
            continue
        for key, leaf in tmpl.items():
            if not (isinstance(leaf, dict) and "select_one" in leaf) or len(lst) < 2:
                continue
            cfg = leaf["select_one"]
            if any(el.get(key) == 1 for el in lst):
                continue
            labels = [str(el.get(cfg.get("label", "nazwa")) or f"element {i + 1}") for i, el in enumerate(lst)]
            options = labels + [cfg.get("none", "Nie wskazano")]
            chosen = None
            if jev.enabled():
                state = ctx.sections.get(tmpl.get("_scope", "")) or ctx.sections.get("head") or ctx.text
                try:
                    chosen, p = backend.choose(normalize.ws(state)[:2500], cfg["question"], options)
                    ctx.trace.append({"field": f"{path}[*].{key}", "method": "decision:select_one",
                                      "question": cfg["question"], "answer": options[chosen], "prob": p})
                except Exception:
                    chosen = None
            for i, el in enumerate(lst):
                el[key] = 1 if chosen == i else 0
                ctx.trace.append({"field": f"{path}[{i}].{key}", "value": el[key], "method": "decision:select_one",
                                  "question": cfg["question"], "answer": options[chosen] if chosen is not None else None})


def run_verify(result: Any, ctx: Ctx) -> None:
    """Weryfikacja wartości z regexu modelem decyzyjnym (klucz `verify:` w YAML = czym ma być pole).

    Pytanie tak/nie na kontekście cytatu; wartość z prawdopodobieństwem < progu jest odrzucana i (jeśli pole ma
    `llm:`) trafia do fallbacku LLM. Tanie: jedno krótkie wywołanie modelu decyzyjnego na pole, równolegle.
    """
    from concurrent.futures import ThreadPoolExecutor

    from . import backend, jev

    cfg = backend.settings().get("decisions") or {}
    if not ctx.verify or not jev.enabled() or not cfg.get("verify", False):
        return
    threshold = cfg.get("verify_threshold", 0.5)

    def ask(job: tuple[str, dict[str, Any], str | None, Any, dict[str, Any]]) -> float | None:
        _, leaf, item, value, entry = job
        state = " ".join(x for x in (entry.get("before"), entry.get("quote"), entry.get("after")) if x)
        state = state or normalize.ws(item or ctx.text)[:1500]
        try:
            return backend.noul(state, f"Czy «{value}» to {leaf['verify']}?")
        except Exception:  # model niedostępny -> zostawiamy wartość z regexu
            return None

    with ThreadPoolExecutor(max_workers=8) as ex:
        probs = list(ex.map(ask, ctx.verify))
    for (path, leaf, item, value, entry), p in zip(ctx.verify, probs):
        if p is None:
            continue
        entry["verified"] = round(p, 3)
        if p >= threshold:
            continue
        _set_path(result, path, None)
        ctx.trace.append({"field": path, "value": None, "method": "verify_rejected", "rejected": value,
                          "prob": round(p, 3), "question": leaf["verify"]})
        if "llm" in leaf:
            ctx.pending.append((path, leaf, item))


def extract(text: str, spec: dict[str, Any], alt_text: str | None = None) -> tuple[Any, list[dict[str, Any]]]:
    ctx = Ctx(text=text, spec=spec, sections=find_sections(text, spec), alt_text=alt_text)
    result = build(spec["output"], ctx)
    run_verify(result, ctx)
    run_llm(result, ctx)
    run_select(result, ctx)
    return result, ctx.trace
