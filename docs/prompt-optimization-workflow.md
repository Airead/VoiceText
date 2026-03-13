# Prompt Optimization Workflow

A practical guide for advanced users who want to systematically improve AI enhancement quality using the Preview panel's built-in tools.

## Prerequisites

- Preview mode enabled (Settings → General → Preview)
- At least one LLM provider configured (Settings → LLM)
- An enhancement mode selected (Settings → AI)

## The Preview Panel at a Glance

```
┌─────────────────────────────────────────────────────┐
│  ASR   [FunASR ▾]  10.6s    ☐ Punc   Play ▶  Save  │  ← Raw speech recognition
│  ┌─────────────────────────────────────────────┐    │
│  │ 根据目前程序的preview界面你能想到用户...       │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  [ Off ] [纠错润色] [翻译为英文] [润色+翻译EN] [...]  │  ← Mode switcher (⌘1–⌘9)
│                                                     │
│  AI  [provider/model ▾]  Tokens: 897 (↑878 ↓19)    │
│                                ☐ thinking  🧠 Prompt│  ← Enhancement controls
│  ┌─────────────────────────────────────────────┐    │
│  │ AI enhanced result (read-only)               │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  Final Result (editable)                  Translate ↗│
│  ┌─────────────────────────────────────────────┐    │
│  │ Your final text — edit here before confirm   │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  [History]                      [Cancel]  [Copy ⌘↵] │
└─────────────────────────────────────────────────────┘
```

## Core Tools for Prompt Optimization

### 1. Play ▶ — Verify What You Actually Said

Before blaming ASR or AI, play back the recording. This tells you which layer the problem is in:

| What you hear | Diagnosis | Action |
|---|---|---|
| You misspoke or were unclear | Source problem | Re-record with clearer speech |
| Speech was fine, ASR text is wrong | ASR problem | Switch ASR engine, enable Punc, or try a different model |
| ASR text is correct, AI output is wrong | Prompt problem | Inspect and iterate on the prompt (see below) |

### 2. Prompt Button — See the Actual System Prompt

Click **Prompt ⓘ** after enhancement completes to see the exact system prompt sent to the LLM. This is the single most important tool for optimization — you cannot improve what you cannot see.

What to look for:

- Is the instruction clear and specific enough?
- Does it mention that input comes from ASR (which may contain errors)?
- Does it have an output-only rule to prevent commentary?
- Are there edge cases the prompt doesn't cover?

### 3. Mode Switcher (⌘1–⌘9) — Compare Modes Instantly

Press `⌘1` through `⌘9` to switch modes without re-recording. Results are cached — switching back shows the previous result instantly (marked `[cached]`).

Use this to:

- Compare how different prompts handle the same input
- A/B test a new mode against existing ones
- Find which mode handles specific content types best

### 4. LLM Model Dropdown — Compare Models

Switch models from the AI dropdown to see how the same prompt performs across different LLMs. Each (mode, model, thinking) combination is cached independently.

### 5. Thinking Mode — Observe AI Reasoning

Enable the thinking checkbox, then click the **🧠** (brain) button after enhancement to read the AI's reasoning process. This reveals:

- Why the AI made specific word choices
- Where the AI is confused or uncertain
- Whether the AI understood your intent correctly

This is invaluable for diagnosing prompt issues — if the AI's reasoning is wrong, the prompt needs clarification.

### 6. Final Result — Correct and Train

Edit the Final Result to fix any remaining issues before confirming. Each edit is recorded with a `user_corrected` flag, which feeds into the vocabulary system over time.

## Step-by-Step Optimization Workflow

### Phase 1: Identify the Problem

1. **Record** a representative sentence.
2. **Play ▶** the recording to confirm you said what you meant.
3. **Read the ASR text** — is the transcription accurate?
4. **Read the AI result** — did the enhancement improve or damage the text?
5. **Click Prompt** — read the system prompt that produced this result.

### Phase 2: Diagnose

Use the controls to narrow down the issue:

| Symptom | Diagnostic step | Likely cause |
|---|---|---|
| AI adds unwanted commentary | Check Prompt — missing output-only rule | Prompt needs "Output only... without explanation" |
| AI over-corrects correct text | Check Prompt — too aggressive instruction | Prompt needs "Preserve original text when correct" |
| AI misunderstands domain terms | Enable thinking, read 🧠 | Prompt needs domain context or examples |
| Good with one model, bad with another | Switch models via dropdown | Prompt too model-dependent; add more explicit rules |
| Works for short input, fails for long | Test both via re-recording | Prompt needs length-aware handling |

### Phase 3: Edit the Mode

1. Open `~/.config/VoiceText/enhance_modes/<mode_id>.md` in a text editor.
   Or use Settings → AI → select mode → edit.
2. Make targeted changes based on your diagnosis.
3. Restart the app (or reload config) to load the updated prompt.
4. Re-record the same sentence and compare results.

### Phase 4: Validate

1. **⌘1–⌘9** to switch between the updated mode and other modes — is the updated one better?
2. **Switch LLM models** — does the improvement hold across models?
3. **Test edge cases** — try short input, long input, mixed languages, noisy speech.
4. **Enable thinking** — does the AI's reasoning now match your intent?

### Phase 5: Refine Over Time

- **Correct Final Results** consistently — the vocabulary system learns from your edits.
- **Review History** (click History button) — look for patterns in what the AI gets wrong.
- **Build vocabulary** (Settings → AI → Build Vocabulary) — domain terms accumulate automatically.

## Practical Examples

### Example 1: AI Adds Explanation After Translation

**Problem:** The "翻译为英文" mode outputs "Translation: ..." with a prefix.

**Diagnosis:** Click Prompt → the prompt says "translate to English" but doesn't explicitly forbid commentary.

**Fix:** Add to the prompt:
```
Output only the translated text.
Do not add any prefix, label, or explanation.
```

### Example 2: AI Corrects a Name Incorrectly

**Problem:** You say "找萍萍确认一下" but AI changes it to "找平平确认一下".

**Diagnosis:** Enable thinking → the AI treats "萍萍" as an ASR error for "平平" because it lacks context.

**Fix options:**
- Edit Final Result to "萍萍" → the correction is logged and builds vocabulary over time
- Enable Conversation History (Settings → AI) so the AI sees prior confirmed uses of "萍萍"
- Manually build vocabulary after accumulating corrections

### Example 3: Mode Works on One Model But Not Another

**Problem:** "命令行大神" produces clean shell commands on GPT-4 but adds markdown fences on a local model.

**Diagnosis:** Switch models via dropdown, compare outputs. Click Prompt to check.

**Fix:** Make the prompt more explicit:
```
Output only the raw command.
Do not wrap in markdown code blocks or backticks.
Do not add any explanation.
```

## Quick Reference

| Shortcut / Button | Purpose in optimization |
|---|---|
| **Play ▶** | Verify source audio — is the problem in your speech? |
| **Punc** | Toggle punctuation — does it improve ASR accuracy? |
| **⌘1–⌘9** | A/B test modes on the same audio |
| **AI dropdown** | A/B test models with the same prompt |
| **Prompt ⓘ** | Read the actual prompt sent to the LLM |
| **☐ Thinking** | Enable AI reasoning trace |
| **🧠** | Read the AI's reasoning — diagnose misunderstandings |
| **Final Result** | Correct errors — trains vocabulary over time |
| **Translate ↗** | Cross-check with Google Translate |
| **History** | Review patterns in past corrections |

## Tips

- **One change at a time.** When editing a prompt, change one thing, then test. Multiple changes make it hard to know what helped.
- **Save good test cases.** Use **Save** to export recordings that expose prompt issues. Replay them after editing the prompt to verify the fix.
- **Use numbered rules.** LLMs follow structured prompts with numbered rules more consistently than paragraph instructions.
- **Always mention ASR context.** Include "The user's input comes from ASR and may contain recognition errors" in your prompts — it significantly improves error tolerance.
- **Check token counts.** The Tokens display (↑prompt ↓completion) helps you judge prompt efficiency. A prompt with high ↑ and low ↓ may be too verbose.
