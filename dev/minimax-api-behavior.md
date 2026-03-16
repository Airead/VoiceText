# MiniMax M2.5 API Behavior Notes

Findings from testing MiniMax M2.5 API (2026-03-16) against both available models
via the OpenAI-compatible endpoint at `https://api.minimaxi.com/v1`.

Applies to: `MiniMax-M2.5` and `MiniMax-M2.5-highspeed`.

---

## 1. Thinking Cannot Be Disabled

MiniMax does not support turning off thinking. This was [confirmed by the MiniMax
team](https://github.com/MiniMax-AI/MiniMax-M2/issues/68#issuecomment-3908572270):

> "Currently, turning off thinking is not supported. As we pay more attention to
> the final results, we do not focus much on non-thinking modes at this stage."

### Parameters tested (all ineffective)

| Parameter                                        | Result             |
|--------------------------------------------------|--------------------|
| `extra_body={"thinking": false}`                 | Still has `<think>` |
| `extra_body={"chat_template_kwargs": {"enable_thinking": false}}` | Still has `<think>` |
| `extra_body={"reasoning_split": true}`           | **Works** — see §2 |

Only `reasoning_split` has any effect, and it does not disable thinking — it
merely moves the thinking content out of `content` into a separate field.

### Raw test results

```
=== extra_body={"thinking": false} ===
content: "<think>\nThe user is simply asking me to say hi...\n</think>\n\nHi there! 👋"
Has <think> tags: True

=== extra_body={"chat_template_kwargs": {"enable_thinking": false}} ===
content: "<think>\nThe user is simply asking me to say hi...\n</think>\n\nHi"
Has <think> tags: True

=== extra_body={"reasoning_split": true} ===
content: "Hi! 👋 How can I help you today?"
Has <think> tags: False
```

---

## 2. Thinking Output Format

### Default (no `reasoning_split`): inline `<think>` tags

Thinking is embedded directly in `delta.content` / `message.content` as XML-like tags:

```json
{
  "content": "<think>\nThe user wants me to say hi. This is a simple greeting request.\n</think>\n\nHi there! 👋 How can I help you?",
  "role": "assistant",
  "name": "MiniMax AI"
}
```

In streaming, the `<think>` tags appear across multiple `delta.content` chunks.
There is **no** `reasoning_content` field (unlike DeepSeek).

### With `reasoning_split=true`: separate `reasoning_details`

```json
{
  "content": "Hi! 👋 How can I help you today?",
  "role": "assistant",
  "name": "MiniMax AI",
  "reasoning_details": [
    {
      "type": "reasoning.text",
      "id": "reasoning-text-1",
      "format": "MiniMax-response-v1",
      "index": 0,
      "text": "The user wants me to say hi. This is a simple greeting request."
    }
  ]
}
```

Note: there is no `reasoning_content` field — MiniMax uses `reasoning_details`
(an array of objects), which is different from DeepSeek's `reasoning_content`
(a string).

### How WenZi handles this

We do **not** set `reasoning_split` in requests. Instead, `ThinkTagParser` in
`enhance/enhancer.py` incrementally parses `<think>...</think>` tags from
streaming `delta.content` and yields them as `is_thinking=True` segments.

Advantages:
- No extra API configuration needed per provider
- Works for any model that uses inline `<think>` tags (not just MiniMax)
- Handles tags split across chunk boundaries and partial tag buffering
- Strips leading whitespace after `</think>` to prevent blank lines in the UI

For non-streaming responses, `strip_think_tags()` removes `<think>` blocks.

---

## 3. Token Usage Reporting

### No cache token information

Neither model reports prompt cache hits. All cache-related fields are absent or null.

Actual response from `MiniMax-M2.5-highspeed` (identical structure from `MiniMax-M2.5`):

```json
{
  "prompt_tokens": 321,
  "completion_tokens": 30,
  "total_tokens": 351,
  "prompt_tokens_details": null,
  "completion_tokens_details": {
    "accepted_prediction_tokens": null,
    "audio_tokens": null,
    "reasoning_tokens": 30,
    "rejected_prediction_tokens": null
  },
  "total_characters": 0
}
```

Two identical requests with 321 prompt tokens — second call shows **no change**
in `prompt_tokens` and no cache fields appear. Tested with both non-streaming
and streaming (`stream_options={"include_usage": true}`).

### Comparison with other providers

| Provider  | Cache field                                 | Location                     |
|-----------|---------------------------------------------|------------------------------|
| OpenAI    | `cached_tokens`                             | `prompt_tokens_details`      |
| DeepSeek  | `prompt_cache_hit_tokens`                   | Top-level usage field        |
| GLM (智谱) | `cache_tokens`                              | `prompt_tokens_details`      |
| **MiniMax** | **None**                                  | `prompt_tokens_details` is `null` |

`_extract_cache_read_tokens()` in `enhancer.py` returns 0 for MiniMax.
No special handling is needed.

### `reasoning_tokens` — the only useful detail field

`completion_tokens_details.reasoning_tokens` reports how many tokens were spent
on thinking. This value is **included within** `completion_tokens` (not additive).

Example: if `completion_tokens=48` and `reasoning_tokens=42`, the actual content
output used only 6 tokens.

This field is not currently used by WenZi but could be displayed in the UI
alongside the existing thinking token counter for more accurate reporting.

### `total_characters` field

MiniMax returns an extra `total_characters: 0` field in usage. This is always 0
in chat completion responses and appears to be unused. It does not appear in the
OpenAI SDK's typed model, so it is silently ignored.

---

## 4. Other Observations

### Model name in response

MiniMax sets `message.name = "MiniMax AI"` in responses. This is an unusual field
that most other providers leave unset. It has no effect on WenZi's processing.

### `audio_content` field

Responses include an empty `audio_content: ""` field, suggesting TTS capabilities
in the API. Not used by WenZi.

### Streaming behavior

Streaming works with `stream_options={"include_usage": true}`. The final chunk
contains `usage` with the same structure as non-streaming responses. During
streaming, `<think>` tags flow through `delta.content` chunks normally — they are
not delivered in a separate field unless `reasoning_split=true` is set.
