"""Status każdego pola wyniku – czy brak wartości jest błędem, czy normalną sytuacją.

found           – wartość znaleziona
absent_ok       – brak wartości, ale to typowe (YAML: `absent_ok: "powód"`), np. PESEL, numer TED
not_applicable  – pole nie dotyczy tego dokumentu (YAML: `applies_if`), np. imię i nazwisko mocodawcy-spółki
missing         – brak wartości w polu, które zwykle występuje (ostrzeżenie)

`applies_if` (w liściu YAML):
  {field: "typ", equals: "osoba_fizyczna"}       – pole siostrzane w tym samym obiekcie
  {field: "../przez-pelnomocnika", equals: 1}    – pole w obiekcie nadrzędnym ("../" = poziom wyżej)
  {list_min: 2}                                  – tylko gdy lista zawierająca obiekt ma >= 2 elementy
  note: "opis"                                   – wyjaśnienie dla użytkownika
"""

from __future__ import annotations

from typing import Any

from .engine import LEAF_KEYS  # noqa: E402


def _applies(cond: dict[str, Any], stack: list[tuple[dict[str, Any], int]]) -> bool:
    if "list_min" in cond:
        return bool(stack) and stack[-1][1] >= cond["list_min"]
    ref = cond.get("field", "")
    level = len(stack) - 1
    while ref.startswith("../"):
        ref, level = ref[3:], level - 1
    if level < 0 or not stack:
        return True
    return stack[level][0].get(ref) == cond.get("equals")


def field_status(spec_output: Any, result: Any) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}

    def walk(spec: Any, res: Any, path: str, stack: list[tuple[dict[str, Any], int]]) -> None:
        if isinstance(spec, dict) and LEAF_KEYS & spec.keys():
            if res is not None and res != "":
                out[path] = {"status": "found"}
            elif spec.get("applies_if") and not _applies(spec["applies_if"], stack):
                out[path] = {"status": "not_applicable", "note": spec["applies_if"].get("note", "nie dotyczy")}
            elif "absent_ok" in spec:
                out[path] = {"status": "absent_ok", "note": spec["absent_ok"]}
            else:
                out[path] = {"status": "missing", "note": "brak wartości w polu, które zwykle występuje"}
            return
        if isinstance(spec, dict) and isinstance(res, dict):
            n = stack[-1][1] if stack else 1
            new_stack = stack + [(res, n)]
            for k, v in spec.items():
                if not k.startswith("_"):
                    walk(v, res.get(k), f"{path}.{k}" if path else k, new_stack)
        elif isinstance(spec, list) and isinstance(res, list):
            for i, item in enumerate(res):
                walk_item(spec[0], item, f"{path}[{i}]", stack, len(res))

    def walk_item(spec: Any, res: Any, path: str, stack: list[tuple[dict[str, Any], int]], n: int) -> None:
        if isinstance(spec, dict) and isinstance(res, dict) and not (LEAF_KEYS & spec.keys()):
            new_stack = stack + [(res, n)]
            for k, v in spec.items():
                if not k.startswith("_"):
                    walk(v, res.get(k), f"{path}.{k}", new_stack)
        else:
            walk(spec, res, path, stack)

    walk(spec_output, result, "", [])
    return out
