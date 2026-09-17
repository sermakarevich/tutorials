# Jev (TypeSafe) tutorial

Jupyter notebook showing how to use the **Jev** model from [TypeSafe](https://docs.typesafe.ai) in Python.

Jev is a *System One* model: it does not generate text. You send it **state** (text or JSON: a message, a record, a source file) plus **typed questions**, and it returns numbers your code can use directly.

| Question type | You ask | You get back |
|---|---|---|
| `Choice` | pick one option from a labelled list | `choice`, `probabilities` per option, `confidence` |
| `Score` | rate the state on an ordered rubric | `score` (may land between levels), `probabilities`, `confidence` |
| `Noul` | is this statement true? | `noul`, a number 0 (no) to 1 (yes) |

All questions in one request are evaluated in parallel against the same state, so extra questions cost almost nothing.

## What the notebook covers

1. **Setup**: client, retry policy, usage counter, model list.
2. **Basic examples from the docs**: the quick-start support ticket, what is inside an answer, dict state, structured criteria, raw dict questions, errors and logging, the async client.
3. **Patterns**: confidence-gated routing, composite scoring (resume screening with role-dependent weights), speculative fan-out.
4. **Advanced, "Jev, how should I improve this repo?"**: Jev cannot write advice, so the question is rephrased so Jev is the judge and you supply the candidates. Architecture scorecard, "which area first" as one `Choice`, a ranked improvement backlog, and a per-file code-smell scan of ~200 Python files against the project's own coding rules. This section points at a local checkout of a private repo (`~/git/fleet`); change `FLEET` to any repo you like.
5. **Cost**: token totals and an estimated dollar amount for the whole run (a few cents).

Outputs are saved in the notebook, so it can be read without running it.

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) and [`just`](https://github.com/casey/just).
- A TypeSafe API key from https://console.typesafe.ai/settings/keys, exported as `TYPESAFE_API_KEY` or placed in a local `justfile.env` (gitignored).

## Run it

```bash
just install     # uv sync
just check-key   # fails if TYPESAFE_API_KEY is missing
just models      # lists models available to your key
just jupyter     # JupyterLab on http://localhost:8899 with the notebook open
just run         # execute the whole notebook headless
just clean       # strip outputs
```

## Notes

- Probabilities are normalized to sum to 1, so the model always picks something. Check `confidence`, or add an `other` / `none of the above` option.
- `Noul` answers have no `confidence`; distance from 0.5 is a rough proxy.
- Request budget is about 32k tokens (~150k characters) shared by state and questions.
- The response reports the concrete model version (for example `jev-1.13.0`) even when you asked for `jev-latest`. Pin the version if your thresholds depend on it.

## Further reading

[TypeSafe docs](https://docs.typesafe.ai/introduction) · [Quick start](https://docs.typesafe.ai/introduction/quickstart) · [Python SDK](https://docs.typesafe.ai/sdk/python/usage) · [Confidence](https://docs.typesafe.ai/confidence) · [Patterns](https://docs.typesafe.ai/patterns)
