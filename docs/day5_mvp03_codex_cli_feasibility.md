# MVP-03 Codex CLI feasibility & security review

Audit date: 2026-11-12. Baseline: commit `94a0027`, tag `mvp03-offline-v1`,
branch `agent/day5-controlled-host`.

**Decision: NO-GO for a scientifically valid Pre-Spatial Codex live evaluation
in the current environment. CONDITIONAL GO for a future synthetic compatibility
probe after isolation and authentication are verified and the researcher separately
authorizes invocation. Prefer the existing Responses API backend for the first
scientific evaluation, subject to credentials, model choice and controlled spending.**

## Verified locally versus documented

Inspected the five requested Agent files and `docs/agent_handoff.md`. Existing
`model.respond(history, tools)` remains the integration boundary. Python owns
scientific dispatch, modes, source checks, citations, budgets and abstention.
The accepted required-tool setting and negation correction are present.

| Capability | Local observation | Not established by this audit |
| --- | --- | --- |
| CLI version | PATH-first desktop executable: `0.167.2`; IDE executable: `0.167.0-alpha.4.1` | Versions are not interchangeable; pin an executable and version |
| Non-interactive input | `exec`, stdin through `-`, explicit `--model`, `--cd`, `--skip-git-repo-check` advertised by help | Successful inference or bounded model latency |
| Structured output | `--output-schema`, `--output-last-message`, `--json` advertised | Actual schema compliance, supported schema subset, refusal behavior |
| Isolation controls | `--sandbox` choices, global `--ask-for-approval`; Windows sandbox readable-root options advertised | Effective policy, filesystem denial, tool removal or credential separation |
| Context/session controls | `--ephemeral`, `--ignore-user-config`, `--ignore-rules`, `exec resume` advertised | Clean startup context, no inherited integrations or session leakage |
| Authentication | Login help supports ChatGPT/device login, API keys and access tokens | Active researcher login, plan, model entitlement or quota |
| Alternative interface | Experimental app-server and schema-generation help available | Protocol compatibility or runtime enforcement |

The desktop executable resolves to
`C:\Users\Wen\AppData\Local\Programs\OpenAI\Codex\bin\codex.exe`.
All CLI informational invocations warned that the home directory could not be
found. `codex login status` exited 1; its raw output was captured and reduced to
a credential-safe status. `codex features list` failed to resolve `CODEX_HOME`.
No credentials were printed, copied or refreshed, and no home/config workaround
was applied. This command environment does not verify the researcher's normal
desktop authentication. Windows reports version `10.0.26300.0`; that alone does
not prove a supported, enabled or correctly configured sandbox.

Official documentation supports ChatGPT subscription authentication and separate
API-key usage. Plan usage is limited/shared according to the applicable plan;
subscription access is not unlimited free API access. Account-specific capacity
and model access remain unknown. [Authentication](https://learn.chatgpt.com/docs/auth),
[usage and pricing](https://learn.chatgpt.com/docs/pricing).

The documented JSONL stream provides thread/item events, completion/failure and
usage. Schema output constrains the **final message**, not all actions taken
before it. Actual CLI model identifiers and service response IDs were not
observed; do not substitute a requested model or thread ID for a verified serving
model or native Responses response ID. [Non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode).

## Smallest proposed adapter, not implemented

Use fresh, ephemeral `codex exec` invocations, one per Python `respond` call.
Pass a bounded serialized transcript and only that mode's tool descriptions over
stdin. Avoid command interpolation and scientific paths. Ask for one closed JSON
object such as:

```json
{"name":"get_temporal_summary","arguments_json":"{}"}
```

Constrain `name` to the current allowlist plus `submit_assessment`. Python strictly
decodes both JSON layers, applies the existing limits and dispatch, and assigns
a unique host call ID. Normalize into the existing `calls`, `assistant_items`,
`response_id`, `model`, `usage` return shape. Reconstruct transcript-only assistant
items for replay; they are adapter-generated bookkeeping, not native Codex tool
calls. `submit_assessment` remains the terminal proposal.

Record `backend=codex_cli`, `protocol=structured_action_proposal`, executable
version, verified auth kind, requested/observed model separately, thread IDs,
reported usage and invocation status. Missing metadata stays unknown. Record
redacted public events without persisting private reasoning or secrets.

Reject malformed/multiple proposals, nonzero exit, missing final completion,
unexpected tool activity, timeouts and oversized output. Rejecting a trace after
execution is only detection: prohibited tools must already be blocked. The
Host's eight tool requests, ten turns and byte caps do not bound Codex's internal
agent steps; subprocess-tree lifetime and output limits need additional control.
No equivalent to the API's 4,096 output-token setting was verified locally.

Fresh calls simplify mode separation and explicit replay, at the cost of process
startup, auth/config loading and repeated input. Overhead is unmeasured. Resume
can retain hidden context and requires deliberate per-run/per-mode IDs; never use
`--last`. It is not the smallest first integration. App-server offers structured
turns, richer routing metadata and experimental dynamic tools, but adds protocol
and lifecycle work without automatically solving isolation.
[App-server documentation](https://learn.chatgpt.com/docs/app-server).

## Critical evidence boundary

A new working directory and `read-only` mode are insufficient: prevented writes
do not imply prevented reads or prevented computation. The actual repository
contains post-spatial arrays and researcher selections. Codex must not discover
them through shell, file tools, preloaded instructions, memories, sessions,
plugins, MCP, browser, connectors or child agents.

Documented permission profiles can restrict command reads, but do not cover every
Codex surface. Windows MXC and legacy elevated enforcement differ from the
unelevated fallback, which does not support denied read paths. No implementation
or effective policy was verified here. There must be no silent fallback to broad
reads or full access. [Permission scope](https://learn.chatgpt.com/docs/permissions#scope-and-enforcement),
[Windows sandbox](https://learn.chatgpt.com/docs/windows/windows-sandbox).

Before any research-backed Codex run, establish and verify:

1. An isolated execution context for the CLI and its children, containing only
   runtime necessities and Host-approved input; no research-repository mount or
   access to host documents, other sessions, output directories or unrelated secrets.
2. An audited startup configuration without inherited instructions, memories,
   hooks, integrations or other evidence sources. Disable execution and external
   capabilities before invocation. `features.shell_tool=false` is a documented
   control, not proof that every tool is disabled. `--ignore-user-config` still
   uses `CODEX_HOME` for auth and is not a clean-room guarantee.
3. Authentication available to the trusted CLI transport without tokens becoming
   model-visible through filesystem, environment inspection or tool execution.
   Use supported researcher login; do not extract ChatGPT tokens into the API adapter.
4. Independent enforcement checks using synthetic canary files outside the allowed
   root, blocked command/tool attempts, network restrictions, subprocess termination
   and startup-context review. A no-tool trace alone does not prove denial.

These controls are prerequisites, not changes made by this audit. A verified
disposable VM/container boundary may be necessary; minimal cwd or WSL alone is
not sufficient. Do not configure accounts, ACLs, sandboxes or new services under
this audit. [Documented configuration controls](https://learn.chatgpt.com/docs/config-file/config-reference),
[approvals and security](https://learn.chatgpt.com/docs/agent-approvals-security).

## Proposed synthetic probe and decision

**A safe probe is not established in the current command environment.** After the
prerequisites and separate researcher approval, use an isolated, disposable context
with no research files and a synthetic question: “A fictional sample count is
missing. Propose exactly one call to `get_synthetic_count` with `{}` arguments.”
Provide only that fictional function description and a closed two-field schema;
register no executable scientific tools. Use the pinned executable, explicit
researcher model, stdin, JSONL events and final schema output. Do not run it from
this repository. Require valid final JSON, the expected proposal, normal completion,
and zero command/file/MCP/search/other tool executions. Follow with a fictional
Host result to check model-dependent continuation. This tests compatibility only,
not scientific reasoning, evidence isolation by itself, or a completed live Agent.
No probe was run.

| Backend | Additional work and limits | Recommendation |
| --- | --- | --- |
| Codex CLI / ChatGPT | Small transcript/proposal bridge, but substantial isolation verification, process bounds and metadata tests; structured final text differs from native function calling. Plan quotas and actual latency unverified. | **NO-GO now for scientific pre mode; CONDITIONAL GO for isolated synthetic probe** |
| Existing Responses API | Already implements native required function calls and Host-only evidence exposure; model receives no local filesystem tools. SDK is now installed, but API key and researcher model are unset. Requires separately controlled API usage; live behavior still unverified. | **Preferred first scientific backend, conditional on setup and researcher invocation** |
| Local Ollama | New client integration, suitable hardware/model choice and scientific-reasoning evaluation still needed; local hosting alone does not guarantee grounding. | **Defer as future comparison; no deployment** |

Next justified step: resolve CLI auth visibility in the intended researcher-run
environment and design the isolation proof without research data. Only after those
pass should a separately approved synthetic probe or small adapter be considered.
Avoid replacing the existing Python Host or adding a general Agent framework.

## Audit record

Executed informational commands: `Get-Command codex -All`, both executables'
`--version`, `codex --help`, `codex exec --help`, `codex exec resume --help`,
`codex login --help`, credential-safe capture of `codex login status`,
`codex features --help`, `codex features list`, `codex sandbox --help`,
`codex app-server --help`, and `codex app-server generate-json-schema --help`.
Read source/docs, Git status/commit/tag, OS version, artifact existence and SDK/env
presence only. No schema generator, sandbox setup/test command, app-server,
scientific Agent, external model, scientific calculation or test suite was run.

Only this report was created. Existing implementation, tests, configuration,
research bundles and backups were preserved. No dependency installation,
authorization/signing/Store operation, commit, push, merge or PR occurred.

Windows Local Isolation: **NOT VERIFIED**  
Trusted Human Authorization: **NOT VERIFIED**  
Execution Eligibility: **FALSE**

Stopped at Feasibility & Security Review.
