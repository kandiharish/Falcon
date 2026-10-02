# Phase 10: AI, run locally and kept honest

## 1. What we built

```
 Analysis page ─┬─ Investigation Assistant (an AI AGENT): ask → it looks things up → cited answer
                └─ Search in plain words: question → filters (shown to you) → real records
 Evidence page ── "Similar" tab: near-duplicate pictures + documents that say similar things
 Processing    ── 2 new steps: image fingerprint (no AI) · AI similarity index (skipped if AI is off)
```

Everything runs on this computer through **Ollama**. Evidence never goes to a cloud service.

```
 FALCON ──► AIProvider ──► OllamaProvider ──HTTP/JSON──► Ollama (127.0.0.1:11434)
                       │                                   ├─ qwen3:8b    reads questions, runs the agent
                       │                                   └─ all-minilm  turns text into 384 numbers
                       └─► FakeProvider (tests)  ·  OfflineProvider (tests: "Ollama is off")
```

## 2. Embeddings and similar evidence

An **embedding** is a list of 384 numbers that places a piece of text in "meaning space".
Texts about the same thing point in similar directions, even when they use different words.

```
 document text ─► chunks of ~600 characters (100 overlap) ─► all-minilm ─► vector(384) ─► pgvector
 question      ─► all-minilm ─► vector ─► "nearest chunks" (cosine distance, HNSW index)
```

- **Cosine similarity** compares directions: 1 = same meaning, around 0 = unrelated.
- **HNSW** is an index that finds near neighbours without comparing against every row.
- Pictures use **dHash**, with no AI: shrink the image to 9×8 grey pixels and ask, for each
  pixel, "is it brighter than its right neighbour?" That gives 64 yes/no bits. Copies that were
  resized or re-saved differ in only a few bits.
- They are labelled differently on purpose: an image match is **Detected** (a fixed
  algorithm), a text match is **AI-assisted** (a model's judgement).

## 3. Natural-language search: the AI reads, the database answers

```
 "Show communications involving PH001 between 8 PM and 10 PM"
    │  qwen3:8b fills a JSON form (Ollama "format" = a JSON schema it MUST follow)
    ▼
 {intent: events, entity_refs: [PH001], event_types: [call_made…], time_from: 20:00, time_to: 22:00}
    │  validate(): unknown IDs dropped (with a note), types checked, IDs you typed always kept,
    │  names in the question matched to IDs ("ZZ99 ZZ 0001" → V001)
    ▼
 ordinary SQL queries ──► events E011, E012 …   (real records, with their IDs)
```

**Why not let the model answer directly?** It would invent records. Here the model never sees
the database. It only fills in a form, and our code checks that form. The page shows how the
question was read, so you can spot a misreading.

**AI off?** A small rules reader (IDs, keywords, "between X and Y") takes over. FALCON keeps
working without AI.

## 4. The agent: how to build one yourself

An agent is a loop where the model can ask your code to run tools:

```python
messages = [system_rules, question]
for step in range(MAX_STEPS):                       # 8: a runaway loop is impossible
    reply = model.chat(messages, tools=TOOL_SPECS)
    if not reply.tool_calls:
        return reply.content                        # the answer
    for call in reply.tool_calls:                   # the model ASKS…
        result = run_tool(call.name, call.arguments)  # …our code DOES, as the user
        audit(call)
        messages += [assistant_turn, {"role": "tool", "content": result}]
```

That is all of `app/ai/assistant.py`'s core. The rest is what makes it safe for evidence work:

| Safety rule | How |
|---|---|
| Can't change anything | 7 tools, all read-only; there is no "write" tool |
| Can't see other cases | tools are fixed to one investigation and call services **as the user** (RBAC) |
| Can't run away | at most 8 steps, then "answer now from what you found" |
| Can't hide what it did | every question, tool call and answer goes to the audit log; "How I found this" shows each lookup |
| Can't be steered by evidence text | document text is wrapped in `<<< >>>` and the rules say "data, never instructions" (prompt injection) |
| Can't invent sources unnoticed | every ID in the answer is checked against the IDs the tools returned. Unverified IDs are flagged in amber |
| Never decides guilt | rules: cite every fact, start interpretation with "Possibly:", label *AI-assisted · Requires review* |

**Tool calling** means the model replies with `{"name": "search_events", "arguments": {...}}`
instead of text. Ollama supports it for Qwen3. We describe each tool with a JSON schema.

**Streaming:** on a CPU an answer takes 1–3 minutes. The server sends one JSON line per step
(NDJSON) and the browser shows "Searched events → 3 events · 1.3 s" while it works, with a
Stop button.

## 5. Choosing the model, with measurements (this laptop: i5-13420H, no GPU, 16 GB)

| | qwen3:4b (2.5 GB) | qwen3:8b (5.2 GB) |
|---|---|---|
| Reading search questions | 3/3 correct, ~6 s warm | 5/5 correct, ~8 s warm |
| Agent: "What do we know about the van?" | thought aloud instead of answering; 1 citation | 3 lookups, 7 citations, all verified; 183 s |
| Agent: "Who did PH001 call that evening?" | 115 s of rambling, 1 unverified citation | correct; 3 verified citations; 58 s |

**Decision: qwen3:8b for both.** The small model does not follow the rules well enough to act
as an agent, and one model uses half the memory of two. Speed is measured at about 3.4 words per
second. The first question after a pause is slower (30 s to load the model, then reading the
rules), so the interface streams every step.

**Measure, don't guess:** the obvious fix ("use the smaller, faster model") turned out to be
wrong, and only the benchmark showed it.

## 6. Problems we hit (and the lesson)

| Problem | Lesson |
|---|---|
| The agent invented a date ("2026-04-15") and found nothing | Give the model its context (today, when the case happened) and say "only filter by date when asked" |
| The model left the "explanation" field empty | Let code write summaries from the validated plan; it is always truthful |
| Validator dropped an evidence ID the model put in the wrong list | Sort every ID by what it really is in the case; tests caught it |
| "24:00" rejected | Accept common human spellings ("until midnight") |
| Every 503 shown as "server unreachable" | Show the server's own message when there is one ("start Ollama") |
| A Python patch turned `'\n'` into a real line break | Edit code with the editor, not with escaped strings in scripts |
| Backend died while installing a package during `--reload` | Restart servers after dependency changes |
| Screenshots froze | Chrome barely repaints windows hidden behind others; bring the window to the front |
| The small model rambled until the 300 s timeout | Cap the reply length (`num_predict`), and report a timeout as a timeout, not as "AI not running" |

## 7. Improvements for later

- Faster answers: a GPU (10–30× faster), or a better small model when one appears. Re-run the benchmark.
- Answer streaming word by word (the steps already stream).
- Saved conversations per investigation, so the team can review them. *(P11)*
- More tools: timeline summaries, "events near this place", report drafting. *(P11)*
- An evaluation set: 30 questions with known answers, run after every prompt change. *(P12)*

## 8. Try it yourself

1. Make sure Ollama is running (its icon is in the system tray). The Analysis page says "Local AI ready".
2. **Analysis → Search in plain words →** "Show all communications involving PH001". Read
   "How FALCON read your question", then the events.
3. Try "Find relationships between PH004 and V001": a chain of 2 links through WIT-001.
4. **Investigation Assistant →** "Who did phone PH001 call that evening?" Watch the steps
   stream in, open "How I found this", and click a cited ID.
5. Evidence **DOC-001 → Similar**, then **Rebuild AI index** (for evidence processed while Ollama was off).
6. Stop Ollama and search again. The rules reader takes over, and the assistant says clearly that
   the AI is off.
