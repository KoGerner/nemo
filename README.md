# nemo

nemo is designed as an experiment to showcase what AI can do across the BIA and BCM lifecycle. It walks a
department manager through a Business Impact Analysis in chat: it reads the company's files, interviews the
manager, checks the answers against the method, and writes the record.

nemo is separate from the [AI4BCM Guidance](https://github.com/AI4BCM/guidance). It reads that guidance to answer
questions, but the guidance does not depend on it.

It is an experiment. Expect rough edges and breaking changes, and do not rely on its output for a real BIA without
checking it yourself. The name has no link to NVIDIA's NeMo.

## What you need

- Linux or macOS with Python 3.12
- Your own model key. nemo ships with none, and you pay your model provider for what you use.

## Install

```bash
git clone https://github.com/KoGerner/nemo.git
cd nemo
python3.12 -m venv .venv
.venv/bin/pip install -r skin/requirements.txt
.venv/bin/pip install -e .
```

## Connect a model

nemo sends every model call to a [LiteLLM](https://docs.litellm.ai/) gateway on `127.0.0.1:4000`, and that gateway
holds your key. The example config points nemo's model names at [OpenRouter](https://openrouter.ai/). To use another
provider, change the `model` lines in the file.

```bash
python3.12 -m venv ~/.litellm-venv
~/.litellm-venv/bin/pip install 'litellm[proxy]'
export OPENROUTER_API_KEY=your-key-here
~/.litellm-venv/bin/litellm --config litellm.example.yaml --host 127.0.0.1 --port 4000
```

Leave that running. Whatever you type into nemo goes to the provider you chose, along with the files nemo reads, so
check that provider's data terms before you use anything but the sample company.

## Run

In a second terminal:

```bash
./run.sh
```

Open <http://127.0.0.1:8473/new> to get a new room. Rooms and logs are kept in `run/`.

The run script listens on this machine only, and it has no login of its own. Put your own login and TLS in front of
it before you let anyone else reach it.

Guidance questions are answered from the public connector at `mcp.ai4bcm.org`, which needs no key.

## The sample company

`seed/` holds Marschkamp, an invented meat producer. It has an org chart, a method, supplier and asset registers,
interview transcripts and last year's records. Every new room starts as a copy of it. Marschkamp and its people are
made up.

To try your own company, copy `seed/` and point `NEMO_SEED` at your copy. It has to keep the same files and layout.

## Where things are

| Path | What it holds |
|---|---|
| `src/nemo/` | The engine: the five stages, the record, the checks. It has no runtime dependencies. |
| `skin/` | The chat app, built on [Chainlit](https://chainlit.io/), and its charts and pages. |
| `features/` | Behaviour scenarios for the engine. |
| `seed/` | The sample company. |
| `CONTEXT.md` | The glossary. |

Files named `PROTOTYPE_*` are the running app. They kept the name they were first written under.

## Tests

```bash
.venv/bin/pip install -e '.[dev]'
./gate.sh
```

These are the engine's tests and the behaviour scenarios. No test calls a model. The chat app's own larger test suite
stays in the private repository, because it reads the build tooling and logs of past test walks.

Comments in the code mention ticket numbers, working sessions and the box nemo was built on. Those tickets and
sessions are not in this repository.

## This repository

`SOURCE` names the commit of the private working repository that this tree was exported from. Each update is one
commit, and the history before it stays private. The export leaves out tickets, build tooling and archives, and it
changes home-folder paths to `/home/user`.

## Licence

[MIT](LICENSE), copyright Konstantin Gerner. Files carrying someone else's terms:

- Fonts in `skin/harbour/assets/fonts/` are under the SIL Open Font License. See `OFL-NOTICE.txt` in that folder.
- Guidance excerpts in `tests/fixtures/ask/` come from the [AI4BCM Guidance](https://github.com/AI4BCM/guidance),
  CC BY 4.0.
