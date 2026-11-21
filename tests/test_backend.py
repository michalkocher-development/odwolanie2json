"""Model decyzyjny techniką logprobs (System One na LLM) – na podstawionych odpowiedziach serwera, bez sieci."""

import math

import pytest

from app import backend


@pytest.fixture
def fake_server(monkeypatch):
    calls = []
    token_of = {"answer=": ["t:1", "t:2"], "answer=0": ["t:1", "t:2", "token_id:15"],
                "answer=1": ["t:1", "t:2", "token_id:16"], "answer=2": ["t:1", "t:2", "token_id:17"]}

    def post(path, body, kind="llm"):
        calls.append((path, body))
        if path == "/completions":
            return {"choices": [{"logprobs": {"tokens": token_of[body["prompt"]]}}]}
        top = [{"token": "token_id:15", "logprob": math.log(0.1)}, {"token": "token_id:16", "logprob": math.log(0.8)},
               {"token": "token_id:17", "logprob": math.log(0.1)}]
        return {"choices": [{"logprobs": {"content": [{"top_logprobs": top}]}}]}

    monkeypatch.setenv("PROVIDER", "privatemode")
    monkeypatch.setenv("DECISION_MODEL", "test-model")
    monkeypatch.setattr(backend, "_post", post)
    backend._token_cache.clear()
    return calls


def test_choose_with_logprobs(fake_server):
    idx, prob = backend.choose("Zamawiający unieważnił postępowanie.", "Jaka czynność?", ["odrzucenie", "unieważnienie", "inna"])
    assert idx == 1 and prob == pytest.approx(0.8)
    path, body = fake_server[-1]
    assert path == "/chat/completions"
    assert body["messages"][-1] == {"role": "assistant", "content": "answer="}
    assert body["allowed_token_ids"] == [15, 16, 17] and body["max_tokens"] == 1


def test_noul_is_yes_no_choice(fake_server):
    p = backend.noul("tekst", "Czy?")
    assert 0.0 <= p <= 1.0
