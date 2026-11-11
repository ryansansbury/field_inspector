"""How the read reaches a model. Every backend answers the same call, model(system, user, image) -> (text, meta), where
image is {"media_type": "image/jpeg", "bytes": ...} or None.

- AnthropicAPI calls the Anthropic Messages API with the photo as a base64 image block before the text. It records the
  Claude runs.
- OpenAICompatible calls the Chat Completions protocol with the photo as a data URL at high detail.

Adapted from the Call Companion's model layer, with images added and its fallback path dropped. Every backend sits
behind the same prompt, validation and single repair request in owner/record_ai_runs.py, so a model from either vendor
faces the same checks. The caller hands each API key in because keys live in the macOS Keychain and never in the repo.
The build calls none of this. It replays what the owner's runs recorded and validates each one again.
"""
import base64
import json
import sys
import time
import urllib.error
import urllib.request

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
RETRY_STATUS = (429, 500, 502, 503, 504, 529)
MAX_TOKENS = 4000           # every field with its value, label and box fits well inside this
TIMEOUT = 300
REASONING_MAX_TOKENS = 32000    # reasoning models count their hidden reasoning against the output budget
REASONING_TIMEOUT = 600


def urllib_transport(url, headers, body, timeout):
    """POST body to url. Returns (status, response bytes), with an HTTP error's status and body returned too."""
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def cost(tokens_in, tokens_out, price_in, price_out):
    """Dollars from token counts and list prices per million tokens, or None when a price or a count is missing."""
    if None in (tokens_in, tokens_out, price_in, price_out):
        return None
    return round(tokens_in * price_in / 1e6 + tokens_out * price_out / 1e6, 6)


def encoded(image):
    return base64.b64encode(image["bytes"]).decode("ascii")


def error_text(raw):
    try:
        e = json.loads(raw).get("error") or {}
        return f"{e.get('type', '')} {e.get('message', '')}".strip()[:300]
    except (ValueError, AttributeError):
        return (raw.decode(errors="replace") if isinstance(raw, bytes) else str(raw))[:300]


class AnthropicAPI:
    """model(system, user, image) through the Messages API, with two retries on rate limits and server errors."""

    def __init__(self, key, model, max_tokens=MAX_TOKENS, timeout=TIMEOUT, retries=2, transport=None, sleep=time.sleep,
                 price_in=None, price_out=None, keychain=""):
        if not key:
            raise ValueError("The Anthropic API needs a key.")
        self.key, self.model, self.keychain = key, model, keychain
        self.max_tokens, self.timeout, self.retries = max_tokens, timeout, retries
        self.transport, self.sleep = transport or urllib_transport, sleep
        self.price_in, self.price_out = price_in, price_out

    def request(self, system, user, image=None):
        content = []
        if image:
            content.append({"type": "image", "source": {"type": "base64", "media_type": image["media_type"],
                                                        "data": encoded(image)}})
        content.append({"type": "text", "text": user})
        headers = {"x-api-key": self.key, "anthropic-version": API_VERSION, "content-type": "application/json"}
        body = {"model": self.model, "max_tokens": self.max_tokens, "system": system,
                "messages": [{"role": "user", "content": content}]}
        return headers, json.dumps(body).encode()

    def __call__(self, system, user, image=None):
        headers, body = self.request(system, user, image)
        t0 = time.time()
        for attempt in range(self.retries + 1):
            status, raw = self.transport(API_URL, headers, body, self.timeout)
            if status == 200:
                text, meta = parse_api(raw, (time.time() - t0) * 1000)
                meta["cost_usd"] = cost(meta["input_tokens"], meta["output_tokens"], self.price_in, self.price_out)
                return text, meta
            if status == 401:
                raise RuntimeError(f"The Anthropic API refused the key (401). Check the Keychain item {self.keychain}.")
            if status in RETRY_STATUS and attempt < self.retries:
                self.sleep(2 * 3 ** attempt)
                continue
            raise RuntimeError(f"The Anthropic API answered {status}: {error_text(raw)}")

    def described(self):
        return {"backend": "anthropic-api", "model": self.model}


def parse_api(raw, ms):
    """The reply's text and what the API reported about the call. The cost comes from the list prices."""
    data = json.loads(raw)
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    usage = data.get("usage") or {}
    return text, {"ms": round(ms), "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
                  "cost_usd": None, "models": [data["model"]] if data.get("model") else [],
                  "stop_reason": data.get("stop_reason")}


class OpenAICompatible:
    """model(system, user, image) through Chat Completions. A reasoning model counts its hidden reasoning against the
    output budget, so the budget leaves room for the reply after it, and the wait is longer. Four retries back off up to
    45 seconds."""

    def __init__(self, key, model, base_url, vendor="", label="", keychain="", token_param="max_tokens",
                 max_tokens=REASONING_MAX_TOKENS, timeout=REASONING_TIMEOUT, retries=4, transport=None, sleep=time.sleep,
                 price_in=None, price_out=None, notify=None, reasoning_effort=None):
        if not key:
            raise ValueError(f"{vendor or 'This vendor'} needs an API key in the Keychain under {keychain or 'its item'}.")
        self.key, self.model, self.url = key, model, base_url.rstrip("/") + "/chat/completions"
        self.vendor, self.label, self.keychain, self.token_param = vendor, label, keychain, token_param
        self.max_tokens, self.timeout, self.retries = max_tokens, timeout, retries
        self.transport, self.sleep = transport or urllib_transport, sleep
        self.price_in, self.price_out = price_in, price_out
        self.reasoning_effort = reasoning_effort
        self.notify = notify or (lambda line: print(line, file=sys.stderr, flush=True))

    def request(self, system, user, image=None):
        content = [{"type": "text", "text": user}]
        if image:
            url = f"data:{image['media_type']};base64,{encoded(image)}"
            content.append({"type": "image_url", "image_url": {"url": url, "detail": "high"}})
        headers = {"authorization": f"Bearer {self.key}", "content-type": "application/json"}
        body = {"model": self.model, "messages": [{"role": "system", "content": system},
                                                  {"role": "user", "content": content}],
                self.token_param: self.max_tokens}
        if self.reasoning_effort:
            body["reasoning_effort"] = self.reasoning_effort
        return headers, json.dumps(body).encode()

    def __call__(self, system, user, image=None):
        headers, body = self.request(system, user, image)
        t0 = time.time()
        for attempt in range(self.retries + 1):
            status, raw = self.transport(self.url, headers, body, self.timeout)
            if status == 200:
                return parse_openai(raw, (time.time() - t0) * 1000, self.price_in, self.price_out)
            if status in (401, 403):
                raise RuntimeError(f"{self.vendor or 'The vendor'} refused the key ({status}). Check the Keychain item "
                                   f"{self.keychain}.")
            if status in RETRY_STATUS and attempt < self.retries:
                wait = min(2 * 3 ** attempt, 45)
                self.notify(f"    {self.label or self.model}: {self.vendor or 'the vendor'} answered {status} "
                            f"({error_text(raw)[:160]}). Trying again in {wait} s.")
                self.sleep(wait)
                continue
            raise RuntimeError(f"{self.vendor or 'The vendor'} answered {status}: {error_text(raw)}")

    def described(self):
        return {"backend": "openai-compatible", "vendor": self.vendor, "model": self.model, "label": self.label}


def billed(usage):
    """(input, output) tokens the way the vendor bills them. Reasoning sits inside completion_tokens for OpenAI, and
    some endpoints count it only in total_tokens. The billed output is everything in the total beyond the prompt."""
    tokens_in, tokens_out, total = usage.get("prompt_tokens"), usage.get("completion_tokens"), usage.get("total_tokens")
    if None not in (tokens_in, tokens_out, total) and total > tokens_in + tokens_out:
        tokens_out = total - tokens_in
    return tokens_in, tokens_out


def parse_openai(raw, ms, price_in=None, price_out=None):
    """The reply's text, its tokens, and its cost at the given list prices, with the vendor's whole usage report kept."""
    data = json.loads(raw)
    choice = (data.get("choices") or [{}])[0]
    content = (choice.get("message") or {}).get("content") or ""
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    usage = data.get("usage") or {}
    tokens_in, tokens_out = billed(usage)
    return content, {"ms": round(ms), "input_tokens": tokens_in, "output_tokens": tokens_out,
                     "cost_usd": cost(tokens_in, tokens_out, price_in, price_out), "usage": usage,
                     "models": [data["model"]] if data.get("model") else [], "stop_reason": choice.get("finish_reason")}


def backend_for(entry, key_for):
    """The backend a config/models.json entry describes. key_for(item) returns that Keychain item's key. It's owner
    code, and this module never reads a key itself."""
    prices = {"price_in": entry.get("price_in"), "price_out": entry.get("price_out")}
    if entry.get("via") == "anthropic":
        return AnthropicAPI(key_for(entry["keychain"]), entry["model"], keychain=entry["keychain"], **prices)
    if entry.get("via") == "openai":
        limits = {k: entry[k] for k in ("max_tokens", "timeout", "reasoning_effort") if entry.get(k)}
        return OpenAICompatible(key_for(entry["keychain"]), entry["model"], entry["base_url"],
                                vendor=entry.get("vendor", ""), label=entry.get("label", ""),
                                keychain=entry.get("keychain", ""), token_param=entry.get("token_param", "max_tokens"),
                                **prices, **limits)
    raise ValueError(f"{entry.get('id')} names an unknown way to reach its model: {entry.get('via')}")
