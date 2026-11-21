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
Każde pole zapisuje ślad (metoda, wzorzec, fragment źródłowy) do trace.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from . import normalize

LEAF_KEYS = {"regex", "rules", "take", "const", "from", "llm", "jev"}
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
    from . import jev

    cfg = leaf["jev"]
    if not jev.enabled():
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
        idx, prob, _ = jev.choice(state, cfg["question"], options)
    except Exception as e:  # serwer niedostępny -> brak wartości, pipeline działa dalej
        return None, {"method": "jev", "error": str(e)}
    how = {"method": "jev", "question": cfg["question"], "answer": options[idx], "prob": round(prob, 3), "source": state[:300]}
    if idx >= len(keys) or prob < cfg.get("min_prob", 0.0):
        return None, how
    return keys[idx], how


def _snippet(txt: str, m: re.Match[str]) -> str:
    return normalize.ws(txt[max(0, m.start() - 40): m.end() + 40])


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
        if txt is not None and leaf.get("take") == "item":
            value, how = txt, {"method": "item", "source": normalize.ws(txt)[:200]}
        elif txt is not None and "rules" in leaf:
            for rule in leaf["rules"]:
                m = _compile(rule["pattern"]).search(txt)
                if m:
                    value = rule["value"]
                    how = {"method": "rule", "pattern": rule["pattern"], "source": _snippet(txt, m)}
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
                    how = {"method": "regex", "pattern": pat, "source": _snippet(txt, m)}
                    break
                if value is not None:
                    break
        if value is None and "jev" in leaf:
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
    ctx.trace.append({"field": path, "value": value, **how})
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


def run_llm(result: Any, ctx: Ctx) -> None:
    """Jedno wywołanie LLM dla wszystkich pól bez wartości, które mają w YAML klucz `llm` (opis pola)."""
    from . import llm

    if not ctx.pending or not llm.enabled():
        return
    ids = {re.sub(r"\W+", "_", p).strip("_"): (p, leaf, item) for p, leaf, item in ctx.pending}
    fields = {
        fid: {"desc": leaf["llm"], "context": normalize.ws(item)[:200] if item else None}
        for fid, (_, leaf, item) in ids.items()
    }
    try:
        answers = llm.extract(ctx.spec["name"], ctx.text, fields)
    except Exception as e:  # serwer niedostępny -> pola zostają puste
        ctx.trace.append({"field": "*", "method": "llm", "error": str(e)})
        return
    strict = llm.settings().get("require_grounding", True)
    for fid, (raw, grounded) in answers.items():
        path, leaf, _ = ids[fid]
        value = None
        if raw is not None and (grounded or not strict):
            value = normalize.apply(raw, leaf.get("normalize"))
            if value is not None and leaf.get("validate") and not re.fullmatch(leaf["validate"], str(value)):
                value = None
        if value is not None:
            _set_path(result, path, value)
        ctx.trace.append({"field": path, "value": value, "method": "llm", "raw": raw, "grounded": grounded})


def extract(text: str, spec: dict[str, Any]) -> tuple[Any, list[dict[str, Any]]]:
    ctx = Ctx(text=text, spec=spec, sections=find_sections(text, spec))
    result = build(spec["output"], ctx)
    run_llm(result, ctx)
    return result, ctx.trace
