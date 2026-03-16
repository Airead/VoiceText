# Why Error Correction Is So Powerful

闻字 doesn't just transcribe — it builds a multi-layered correction system that gets smarter every time you use it.

## Table of Contents

- [The Problem](#the-problem) — Why raw ASR output isn't good enough
- [Five Layers of Correction](#five-layers-of-correction) — How 闻字 stacks multiple strategies
- [Layer 1: AI Enhancement](#layer-1-ai-enhancement) — LLM-powered proofreading and formatting
- [Layer 2: Vocabulary Retrieval](#layer-2-vocabulary-retrieval) — Embedding-based personal dictionary
- [Layer 3: Conversation History](#layer-3-conversation-history) — Learning from your confirmed corrections
- [Layer 4: Preview Panel](#layer-4-preview-panel) — Human-in-the-loop review
- [Layer 5: Self-Improving Loop](#layer-5-self-improving-loop) — Every correction makes the system better
- [Full Example: All Layers in Action](#full-example-all-layers-in-action) — See all five layers in action
- [Compared to Other Tools](#compared-to-other-tools) — What makes 闻字 different

## The Problem

Every speech-to-text engine makes mistakes. Even the best ASR models produce errors — especially with:

- **Proper nouns** — People's names, product names, and brand names that the model has never seen
- **Technical terms** — Domain-specific jargon like "Kubernetes", "OAuth", or "hemoglobin A1C"
- **Homophones** — "Ciriel" (a name) heard as "cereal", "their" vs "there" vs "they're", "affect" vs "effect"
- **Punctuation and formatting** — ASR engines output raw text with little or no punctuation
- **Context loss** — Each transcription is independent — the engine doesn't know what you said 30 seconds ago

Most voice input tools stop at the ASR output and leave you to manually fix these errors. **闻字 takes a fundamentally different approach** — it layers five independent correction strategies to catch what any single strategy would miss.

## Five Layers of Correction

Instead of relying on a single technique, 闻字 stacks multiple correction layers. Each layer catches errors that the previous layers missed:

```
  Voice Input
      |
      v
 [ ASR Engine ]  ........  raw transcription (contains errors)
      |
      v
 [ Layer 1 ]  ...........  AI Enhancement (LLM proofreading)
      |
      v
 [ Layer 2 ]  ...........  Vocabulary Retrieval (personal dictionary)
      |
      v
 [ Layer 3 ]  ...........  Conversation History (recent context)
      |
      v
 [ Layer 4 ]  ...........  Preview Panel (human review)
      |
      v
 [ Layer 5 ]  ...........  Self-Improving Loop (corrections feed back)
      |
      v
  Final Text  ........... accurate, formatted, and personalized
```

Layers 2 and 3 work by enriching the LLM's system prompt with relevant context. Layer 4 adds human oversight. Layer 5 closes the loop by feeding your corrections back into Layers 2 and 3. The result is a system that **improves with every use**.

## Layer 1: AI Enhancement

When you enable an enhancement mode (like the built-in **Proofread** mode), 闻字 sends your ASR output to an LLM with a carefully crafted system prompt. The LLM acts as an intelligent post-processor:

- **Fixes homophones and near-homophones** by understanding context
- **Adds punctuation** that ASR engines typically omit
- **Corrects grammar** without changing your meaning
- **Preserves your voice** — the prompt explicitly tells the LLM to make minimal changes

**Example:**

- **ASR output:** lets meet tomorrow at three to discuss the progress on the cereal project
- **Enhanced:** Let's meet tomorrow at three to discuss the progress on the Ciriel project.

The key advantage: the LLM understands *meaning*, not just sound. It can distinguish between homophones based on sentence context — something ASR engines alone cannot do.

> Enhancement modes are fully customizable Markdown files. You can create modes for translation, formatting, code generation, or any other text transformation. See [AI Enhancement Modes](enhance-modes.md) for details.

## Layer 2: Vocabulary Retrieval

Generic LLMs don't know your colleague's name, your company's product names, or the technical terms you use daily. 闻字 solves this with an **embedding-based personal vocabulary system**:

1. **Build** — 闻字 extracts proper nouns and technical terms from your correction history using an LLM. Each term includes its correct form, category, and common ASR misrecognitions.
2. **Index** — Terms are embedded into a vector space using a multilingual model (`paraphrase-multilingual-MiniLM-L12-v2`), creating a semantic search index. Runs 100% locally.
3. **Retrieve** — When you speak, your ASR text is embedded and matched against the index. Only the top-K most relevant terms are injected into the LLM's system prompt.

**How it helps:**

- **ASR output:** deploy the service to cooper netties
- **Vocab match:** Kubernetes (container orchestration) — variants: cooper netties, kuber nettis
- **Enhanced:** Deploy the service to Kubernetes.

Why embedding retrieval instead of keyword matching? Because ASR errors are **phonetically similar but orthographically different**. Multilingual embeddings capture phonetic proximity that simple string matching cannot. And unlike dumping your entire vocabulary into every prompt, retrieval scales efficiently — you only inject what's relevant.

> **Key insight:** The vocabulary system is essentially a lightweight, local RAG (Retrieval-Augmented Generation) pipeline — purpose-built for voice input correction.

## Layer 3: Conversation History

Real conversations have continuity. When you say "she was happy today", the word "she" only makes sense in the context of a previous sentence. 闻字 addresses this by injecting your **recent confirmed outputs** into the LLM's prompt.

The core insight: **your confirmed output is the highest-quality signal for what you actually mean.** Unlike raw ASR text (which has errors) or AI output (which may over-correct), the final confirmed text represents your true intent.

### What Gets Injected

Only sessions where you used the Preview panel and confirmed the result are included. This is a deliberate quality decision — a smaller set of verified data beats a larger set of unverified data.

**Injected context (token-efficient format):**

```
- Add a toggle for the conversation history injection feature in the menu bar.
- Now test the history context injection feature.
- I met cereal at the park today. → I met Ciriel at the park today.
- cereal told me she had noodles today. → Ciriel told me she had noodles today.
```

The arrow notation shows correction patterns. When the LLM sees that "cereal" was corrected to "Ciriel" in a previous turn, it can make the same correction automatically in subsequent inputs — **without you ever adding it to a dictionary**.

### Three Problems This Solves

- **Consistent entity resolution** — Once you confirm "Ciriel", subsequent mentions are corrected automatically.
- **Topic-aware enhancement** — The LLM understands the current conversation topic and makes contextually appropriate decisions.
- **Style adaptation** — The LLM observes your writing patterns and matches your tone and formatting preferences.

## Layer 4: Preview Panel

The Preview panel is 闻字.s **human-in-the-loop** interface. Before text is typed into your active application, you can review and refine it:

- **Compare** the raw ASR output with the AI-enhanced result side by side
- **Edit** the final text directly in an editable field
- **Switch modes** on the fly with keyboard shortcuts (`⌘1`–`⌘9`) and re-enhance instantly
- **Inspect thinking** — see the LLM's reasoning process (if the model supports it)

This is more than a convenience feature. Every edit you make in the Preview panel becomes a **training signal** for the system. When you correct "cereal" to "Ciriel", that correction is recorded with a `user_corrected: true` flag, feeding back into Layers 2 and 3.

> The Preview panel also serves as a **prompt tuning workbench**. You can test different prompts, compare models, and systematically improve enhancement quality. See [Prompt Optimization Workflow](prompt-optimization-workflow.md) for the full process.

## Layer 5: Self-Improving Loop

This is what ties everything together. 闻字 creates a **virtuous cycle** where every correction you make improves future corrections:

```
  You speak  ──►  ASR  ──►  AI + Vocab + History  ──►  Preview Panel
                                                            |
          ┌─────────────────────────────────────────────────┘
          |  (user confirms or corrects)
          v
  conversation_history.jsonl
          |
          ├──►  Vocabulary Builder  ──►  vocabulary.json  ──►  Embedding Index
          |     (extracts terms)         (proper nouns)        (semantic search)
          |
          └──►  History Injection  ──►  recent context for LLM
```

1. **You correct** an error in the Preview panel (e.g., "cereal" → "Ciriel")
2. **闻字 records** the ASR text, AI output, and your final confirmed text
3. **Conversation history** uses this immediately — the next input already benefits from your correction
4. **Vocabulary builder** periodically extracts new terms from your correction history and rebuilds the embedding index
5. **Future inputs** get better enhancement because the LLM now has both recent context and a personal vocabulary

> **The more you use 闻字, the better it gets.** Your corrections aren't just fixing the current text — they're teaching the system your vocabulary, your preferences, and your common topics. Over time, you'll find yourself making fewer and fewer corrections.

## Full Example: All Layers in Action

Let's trace a real scenario through all five layers:

**Scenario:** Talking about a colleague "Ciriel" and a project using Kubernetes.

**Step 1 — ASR Output:**
You say: "Ciriel said just deploy the service to Kubernetes and we're good"
ASR produces: `cereal said just deploy the service to cooper netties and were good`
Errors: "Ciriel" → "cereal", "Kubernetes" → "cooper netties", "we're" → "were"

**Step 2 — Vocabulary Retrieval Kicks In:**
The embedding index finds **Kubernetes** (variants: cooper netties, kuber nettis) is semantically close to the input. This term is injected into the LLM prompt.

**Step 3 — Conversation History Provides Context:**
Your recent history shows: `cereal told me she had noodles today. → Ciriel told me she had noodles today.` The LLM now knows "cereal" should be "Ciriel".

**Step 4 — AI Enhancement Result (Layers 1+2+3):**
The LLM, armed with vocabulary context and conversation history, produces:
*Ciriel said just deploy the service to Kubernetes and we're good.*
All errors corrected. Punctuation added.

**Step 5 — Preview Panel: You Confirm:**
The result looks perfect. You press Enter to confirm. The text is typed into your active application.

**Step 6 — Self-Improving: Recorded for the Future:**
This session is logged. Next time you mention "Ciriel" or "Kubernetes", the system will be even more confident in making the right correction.

## Compared to Other Tools

Most voice input tools fall into one of two categories:

- **Basic Voice Input** — Transcribes speech and types it directly. No correction, no context, no learning. You fix every error manually.
- **Cloud Voice Assistants** — Good accuracy for general speech, but no customization for your vocabulary. No correction loop. Privacy concerns with always-on cloud processing.

闻字 is different because it combines **local-first processing** (your data stays on your machine) with **intelligent, layered correction** that adapts to you:

| Capability | Basic Tools | Cloud Assistants | 闻字 |
|---|---|---|---|
| Offline support | Some | No | **Yes (default)** |
| AI error correction | No | Limited | **Customizable LLM** |
| Personal vocabulary | No | No | **Embedding-based RAG** |
| Learns from corrections | No | No | **Yes (automatic)** |
| Conversation context | No | Session-based | **Cross-session history** |
| Human review | No | No | **Preview Panel** |
| Privacy | Varies | Cloud-dependent | **100% local option** |
