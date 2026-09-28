# Genspark AI Chat — API found via headless intercept (2026-09-09)

**Page:** `https://www.genspark.ai/agents?type=ai_chat` — uses cookie auth (`session_id` + `c1` + `c2` on `www.genspark.ai`).

## Endpoint

```
POST https://www.genspark.ai/api/agent/ask_proxy
Content-Type: application/json
Origin: https://www.genspark.ai
Referer: https://www.genspark.ai/agents?type=ai_chat
X-Timezone: Asia/Calcutta
Accept: text/event-stream
Cookie: session_id=...; c1=...; c2=...; (full jar from cookies.json)
```

## Request body

```json
{
  "ai_chat_model": "claude-4-5-haiku",
  "ai_chat_enable_search": true,
  "ai_chat_disable_personalization": false,
  "use_moa_proxy": false,
  "moa_models": [],
  "writingContent": null,
  "sas_ask_origin": "typed",
  "type": "ai_chat",
  "project_id": null,
  "messages": [{"role":"user","id":"<uuid>","content":"<query>","pending":true,"sendStatus":"sending","_deepDiveStateNegContent":"<query>"}],
  "user_s_input": "<query>",
  "client_message_id": "<same uuid>",
  "g_recaptcha_token": "",
  "is_private": true,
  "push_token": "",
  "session_state": {"steps":[],"messages":[{"role":"user","id":"<same uuid>","content":"<query>","pending":true,"sendStatus":"sending","_deepDiveStateNegContent":"<query>"}]},
  "last_seen_event_index": -1,
  "chat_session_id": null
}
```

### Notes

* `ai_chat_model` — see model list below. Default in UI is `claude-4-5-haiku` (stored in localStorage `moa-chat-modelsSelected-ai_chat`). Any value from the list works.
* `ai_chat_enable_search` — `true` makes model do web search (tool call visible as `I'll search for...` + `{"queries":[...]}` in stream). `false` = pure LLM.
* `project_id` + `last_seen_event_index` — for multi-turn in same thread: pass previous response's `project_id` (from `project_start`) and `last_index` (max `_event_index`). Leave `null`/`-1` for new thread.
* `g_recaptcha_token` — **empty string works when cookies are valid** (tested headless with your session — both simple and search queries returned 200). If you hit 403, fetch a real v3 token with sitekey `6LfYyWcsAAAAAK8DUr6Oo1wHl2CJ5kKbO0AK3LIM` (`grecaptcha.enterprise.execute(..., {action:"submit"})`).
* `use_moa_proxy` + `moa_models` — enable Mixture-of-Agents: set `use_moa_proxy:true` and `moa_models:["gpt-5.1-low","claude-sonnet-4-6","gemini-3.1-pro-preview"]` (the 3 models combined via the UI's "Mixture-of-Agents" option). `ai_chat_model` is ignored in MoA mode.
* Required headers: `Origin`, `Referer`, `X-Timezone` — without them Cloudflare returns 403. No `__cf_bm` needed for plain `requests` once cookies are set.

## Response — `text/event-stream`

Each `data: {...}\n\n` line is JSON. Key types:

```
project_start            {"id":"<project_id>", "_event_index":0}
agent_notification/keepalive
message_start            {"message_id":"...","type":"message_start"}
message_field_delta      {"field_name":"content","delta":"<chunk>"}
message_field            {"field_name":"content","field_value":"<full>"}
message_result           {"message":{"content":"<final full answer>","_llm_model":"claude-4-5-haiku", "_finish_reason":"stop"}}
project_field            {"field_name":"name","field_value":"<auto title>"}  and  {"field_name":"status","field_value":"FINISHED"}
```

Stream ends at `project_field status=FINISHED`. Assemble `text` from `delta` chunks; authoritative final is `message_result.message.content`.

## Valid `ai_chat_model` values

Derived from Nuxt hydration + dropdown clicks (lowercase, hyphenated):

| Display (cost in UI) | `ai_chat_model` |
|---|---|
| Mixture-of-Agents | `use_moa_proxy:true` + `moa_models:["gpt-5.1-low","claude-sonnet-4-6","gemini-3.1-pro-preview"]` |
| Claude Opus 5 (5x) | `claude-opus-5` |
| Claude Opus 4.8 (5x) | `claude-opus-4-8` |
| Claude Opus 4.7 (5x) | `claude-opus-4-7` |
| Claude Opus 4.6 (5x) | `claude-opus-4-6` |
| Claude Sonnet 5 (2x) | `claude-sonnet-5` |
| Claude Sonnet 4.6 (3x) | `claude-sonnet-4-6` |
| **Claude Haiku 4.5 (1x) default** | `claude-4-5-haiku` |
| GPT-5.5 Pro (30x) | `gpt-5.5-pro` |
| GPT-5.4 Pro (30x) | `gpt-5.4-pro` |
| GPT-5.2 Pro (21x) | `gpt-5.2-pro` |
| GPT-5.6 Sol (4x) | `gpt-5.6-sol` |
| GPT-5.5 (5x) | `gpt-5.5` |
| GPT-5.4 (3x) | `gpt-5.4` |
| GPT-5.6 Terra (2x) | `gpt-5.6-terra` |
| GPT-5.4 Mini (1x) | `gpt-5.4-mini` |
| GPT-5.6 Luna (0.2x) | `gpt-5.6-luna` |
| GPT-5.4 Nano (0.2x) | `gpt-5.4-nano` |
| Gemini 3.1 Pro Preview (2x) | `gemini-3.1-pro-preview` |
| Gemini 3.8 Flash (0.75x) | `gemini-3.8-flash` |
| Gemini 3.7 Flash (0.75x) | `gemini-3.7-flash` |
| Gemini 3.6 Flash (0.75x) | `gemini-3.6-flash` |
| Gemini 3.5 Flash (2x) | `gemini-3.5-flash` |
| Gemini 3 Flash Preview (0.5x) | `gemini-3-flash-preview` |
| Gemini 3.1 Flash Lite (0.3x) | `gemini-3.1-flash-lite-preview` |
| Grok 4.6 (2x) | `grok-4.6` |
| Grok 4.5 (2x) | `grok-4.5` |
| Muse Spark 1.3 (1x) | `muse-spark-1.3` |
| DeepSeek V4 Pro (2x) | `deepseek-v4-pro` |
| Kimi K3 (3x) | `kimi-k3` |
| Minimax M3 (0.3x) | `minimax-m3` |
| GLM-5.3 (1x) | `glm-5.3` |

Hidden but accepted (not in dropdown): `claude-opus-4-5`, `claude-opus-4-1`, `claude-sonnet-4-5`, `claude-sonnet-4`, `gpt-5-pro`, `gpt-5.2`, `gpt-5.1-low`, `gpt-5.1-medium`, `gpt-5.1-high`, `gemini-2.5-pro`, `gemini-2.5-flash`, `deepseek-v4-pro-0813`, `deepseek-v4-flash`, `deep-seek-v4-flash-vision-exp`, `minimax-m2.7`, `glm-5.2`, `nemotron-3-ultra`, `solar-pro-4`. Test before bulk use — some may 400.

## cURL (single turn, new thread)

```bash
cookies=$(jq -r '.[] | "\(.name)=\(.value)"' cookies.json | paste -sd "; " -)
uuid=$(uuidgen | tr '[:upper:]' '[:lower:]')
curl -N 'https://www.genspark.ai/api/agent/ask_proxy' \
  -H 'content-type: application/json' \
  -H 'origin: https://www.genspark.ai' \
  -H 'referer: https://www.genspark.ai/agents?type=ai_chat' \
  -H 'x-timezone: Asia/Calcutta' \
  -H "cookie: $cookies" \
  --data-raw "{\"ai_chat_model\":\"claude-4-5-haiku\",\"ai_chat_enable_search\":true,\"ai_chat_disable_personalization\":false,\"use_moa_proxy\":false,\"moa_models\":[],\"writingContent\":null,\"sas_ask_origin\":\"typed\",\"type\":\"ai_chat\",\"project_id\":null,\"messages\":[{\"role\":\"user\",\"id\":\"$uuid\",\"content\":\"Briefly: who is the CEO of Genspark?\",\"pending\":true,\"sendStatus\":\"sending\",\"_deepDiveStateNegContent\":\"Briefly: who is the CEO of Genspark?\"}],\"user_s_input\":\"Briefly: who is the CEO of Genspark?\",\"client_message_id\":\"$uuid\",\"g_recaptcha_token\":\"\",\"is_private\":true,\"push_token\":\"\",\"session_state\":{\"steps\":[],\"messages\":[{\"role\":\"user\",\"id\":\"$uuid\",\"content\":\"Briefly: who is the CEO of Genspark?\",\"pending\":true,\"sendStatus\":\"sending\",\"_deepDiveStateNegContent\":\"Briefly: who is the CEO of Genspark?\"}]},\"last_seen_event_index\":-1,\"chat_session_id\":null}"
```

## Python — `genspark_research.py` (headless, terminal)

```bash
pip install requests          # only dep
python genspark_research.py --list-models
python genspark_research.py --cookies cookies.json -q "Research latest AI agent papers June 2026" --model claude-4-5-haiku --stream
python genspark_research.py --cookies cookies.json --file queries.txt --model gpt-5.4-mini -o out.jsonl
python genspark_research.py --cookies cookies.json -q "2+2?" --model gpt-5.4-nano --no-search
python genspark_research.py --cookies cookies.json -q "Compare GPT vs Claude for coding" --moa gpt-5.1-low claude-sonnet-4-6 gemini-3.1-pro-preview
```

`--file` chains turns in same `project_id` (thread). Rotate `cookies.json` after pasting (logout/login invalidates `session_id`/`c1`/`c2`). Keep `cookies.json` out of git.
---

## Model Provider for Harnesses (OpenAI-compatible) — `genspark_provider.py`

Your `agentrouter-proxy` already occupies `8787`, so this provider defaults to **`8788`** (auto-falls back to `8790` if busy).

### Start

```bash
# cookie auth — either file or env
# file:
./start-provider.sh
# or env (useful in CI/containers):
export GENSPARK_COOKIES_JSON='[{"name":"session_id","value":"...","domain":"www.genspark.ai",...}]'
export PORT=8788  # optional
./start-provider.sh

# manual:
python genspark_provider.py --cookies cookies.json --port 8788
curl http://127.0.0.1:8788/health
curl http://127.0.0.1:8788/v1/models | jq '.data[].id'
```

### Harness config (drop-in OpenAI)

```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:8788/v1", api_key="sk-anything")
# optional proxy auth:
# export GENSPARK_PROVIDER_API_KEY="sk-local-secret"
# client = OpenAI(base_url="http://127.0.0.1:8788/v1", api_key=os.environ["GENSPARK_PROVIDER_API_KEY"])

# non-stream
resp = client.chat.completions.create(
    model="claude-4-5-haiku",  # any id from /v1/models
    messages=[{"role":"system","content":"You are concise."}, {"role":"user","content":"2+2?"}]
)
print(resp.choices[0].message.content)

# stream
for chunk in client.chat.completions.create(model="gpt-5.4-mini", messages=[{"role":"user","content":"Say hi"}], stream=True):
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")

# search toggle — suffix or extra_body
resp = client.chat.completions.create(
    model="claude-4-5-haiku:search",  # or :nosearch to force off
    messages=[{"role":"user","content":"Research Genspark pricing with sources"}],
    extra_body={"enable_search": True}  # alternative: extra_body wins
)

# Mixture-of-Agents
resp = client.chat.completions.create(
    model="genspark-moa",  # virtual model, or any model + extra_body
    messages=[{"role":"user","content":"Compare GPT vs Claude for coding"}],
    extra_body={"moa_models": ["gpt-5.1-low","claude-sonnet-4-6","gemini-3.1-pro-preview"]}
)

# multi-turn thread (project_id)
r1 = client.chat.completions.create(model="claude-4-5-haiku", messages=[{"role":"user","content":"My name is Alaq."}])
# harness captures thread ids from response (top-level fields):
# r1.genspark_project_id, r1.genspark_last_index  — SDK exposes via r.model_extra or raw JSON when using requests
import requests, json
raw = requests.post("http://127.0.0.1:8788/v1/chat/completions",
    json={"model":"claude-4-5-haiku","messages":[{"role":"user","content":"My name is Alaq."}]},
    headers={"Content-Type":"application/json"}).json()
pid, last = raw["genspark_project_id"], raw["genspark_last_index"]
raw2 = requests.post("http://127.0.0.1:8788/v1/chat/completions",
    json={"model":"claude-4-5-haiku","messages":[{"role":"user","content":"What is my name?"}],
          "extra_body":{"project_id": pid, "last_seen_event_index": last}},
    headers={"Content-Type":"application/json"}).json()
print(raw2["choices"][0]["message"]["content"])  # -> Alaq!
```

Other harnesses — just set `base_url` / `api_key` / `model`:

```yaml
# LiteLLM config.yaml
model_list:
  - model_name: genspark-claude
    litellm_params:
      model: openai/claude-4-5-haiku
      api_base: http://127.0.0.1:8788/v1
      api_key: sk-anything

# Continue.dev config.json
"models": [{"title":"Genspark Claude","provider":"openai","model":"claude-4-5-haiku","apiBase":"http://127.0.0.1:8788/v1"}]

# Open WebUI → Settings → Connections → OpenAI API → base_url http://127.0.0.1:8788/v1
```

Environment:

```bash
GENSPARK_COOKIES_JSON='[{"name":"session_id","value":"...","domain":"www.genspark.ai",...}]'  # preferred in CI
GENSPARK_COOKIES_FILE=cookies.json        # default file, or comma-separated: cookies.json,cookies_2.json
GENSPARK_RECAPTCHA_TOKEN=""               # leave empty — works logged-in; set if Genspark starts challenging
GENSPARK_PROVIDER_API_KEY=""              # if set, harness must send Authorization: Bearer <key> or x-api-key: <key>
PORT=8788 HOST=127.0.0.1                   # provider bind
```

### Multi-Account Pool & 429 Failover

Drop multiple account cookie files (`cookies.json`, `cookies_2.json`, `cookies_3.json`, etc.) in the provider directory.
The provider automatically:
1. Discovers all `cookies*.json` files.
2. Distributes requests round-robin across all healthy accounts.
3. If an account returns a 429 rate limit, it temporarily marks it in cooldown (60s) and **instantly retries the request on the next available account** with zero client downtime.
4. `/health` returns the live status, request count, and remaining cooldown of each account.

---

## Anthropic Messages API (`POST /v1/messages` and `POST /messages`)

The provider also natively supports Anthropic's Messages protocol. Any tool, CLI, or harness built for Anthropic/Claude (Claude Code, Cursor, Cline, Roo Code, Continue.dev, OpenHands, Aider) works directly.

### Endpoints
- `POST /v1/messages` and `POST /messages` — Messages (both streaming SSE and non-streaming)
- `POST /v1/messages/count_tokens` and `POST /messages/count_tokens` — token counter

### Authentication
Send either:
- `x-api-key: <key>`
- `Authorization: Bearer <key>`
- Optional header: `anthropic-version: 2023-06-01`

If `GENSPARK_PROVIDER_API_KEY` is unset on the provider, any dummy key (e.g. `sk-test`) works.

### Model Aliases
Standard Anthropic model identifiers are automatically mapped to Genspark:
- `claude-3-7-sonnet-20250219`, `claude-3-7-sonnet` -> `claude-sonnet-5`
- `claude-3-5-sonnet-20241022`, `claude-3-5-sonnet` -> `claude-sonnet-5`
- `claude-3-5-sonnet-20240620` -> `claude-sonnet-4-6`
- `claude-3-5-haiku-20241022`, `claude-3-5-haiku` -> `claude-4-5-haiku`
- `claude-3-opus-20240229`, `claude-3-opus` -> `claude-opus-5`
- You can also pass any Genspark model directly: `claude-opus-5`, `claude-sonnet-5`, `claude-4-5-haiku`, `gpt-5.4-mini`, `gemini-3.8-flash`, etc.

### Python with official Anthropic SDK (`anthropic`)

```python
from anthropic import Anthropic

# Point base_url to provider (Anthropic SDK automatically queries /v1/messages)
client = Anthropic(
    base_url="http://127.0.0.1:8788",
    api_key="sk-anything"  # or GENSPARK_PROVIDER_API_KEY if configured
)

# 1. Non-streaming
resp = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    system="You are a research analyst. Be concise.",
    messages=[{"role": "user", "content": "What is 7 times 8?"}]
)
print("Assistant:", resp.content[0].text)
print("Tokens:", resp.usage)

# 2. Streaming (Event iterator)
stream = client.messages.create(
    model="claude-3-7-sonnet",
    max_tokens=1024,
    stream=True,
    messages=[{"role": "user", "content": "Write a short haiku about code."}]
)
for event in stream:
    if event.type == "content_block_delta" and hasattr(event.delta, "text"):
        print(event.delta.text, end="", flush=True)
print()

# 3. Stream context manager (.stream())
with client.messages.stream(
    model="claude-3-5-haiku",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Explain async in one sentence."}]
) as s:
    final = s.get_final_message()
    print("Answer:", final.content[0].text)
```

### cURL (Anthropic format)

```bash
# Non-streaming
curl -s http://127.0.0.1:8788/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: sk-test" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "max_tokens": 512,
    "system": "You are a concise assistant.",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'

# Streaming (SSE)
curl -N http://127.0.0.1:8788/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: sk-test" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "max_tokens": 512,
    "stream": true,
    "messages": [{"role": "user", "content": "Count to 5"}]
  }'
```

### Harness Integration Examples (Anthropic)

**Claude Code CLI:**
```bash
export ANTHROPIC_BASE_URL="http://127.0.0.1:8788"
export ANTHROPIC_API_KEY="sk-anything"
claude
```

**Cursor / Cline / Roo Code (Custom Anthropic / Claude Provider):**
- Provider: `Anthropic`
- Base URL: `http://127.0.0.1:8788` (or `http://127.0.0.1:8788/v1`)
- API Key: `sk-anything`
- Model: `claude-3-5-sonnet-20241022` or `claude-3-7-sonnet`

**Aider (Anthropic mode):**
```bash
aider --anthropic-api-base http://127.0.0.1:8788/v1 --anthropic-api-key sk-anything --model anthropic/claude-3-5-sonnet-20241022
```


