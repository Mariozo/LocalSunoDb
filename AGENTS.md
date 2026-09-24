# LocalSunoDb — Agent Working Rules

> **Product behavior is the source of truth during development. Git and CI record and verify working states; they do not define the product.**

These rules apply to coding agents and ChatGPT work on LocalSunoDb.

## 1. One user task = one work line

Keep one user-requested change on one working line until it is solved.

- Do not create a new branch, PR, task, or release process merely because another test iteration is needed.
- A failed attempt is part of the same task.
- Start a new branch/task only for a genuinely separate piece of work.

## 2. Version number = visible test identity

Every user-delivered iteration must have a new visible version identity so the user can immediately verify that the newly delivered build is actually running.

- A version bump is **not** by itself a reason for a new branch, PR, or task.
- Keep runtime-visible version metadata consistent.
- Use the same iteration identity for browser asset cache-busting where needed, so stale CSS/JS cannot masquerade as the new build.

## 3. Make the product work before Git ceremony

Normal development order:

**user requirement -> code change -> focused syntax/static checks -> real product/browser test -> fix if needed -> user-visible test build -> PASS -> Git checkpoint/PR -> CI -> merge**

GitHub PRs, CI, and release packaging must not be used as the primary way to discover whether the requested behavior works.

If the relevant behavior has not actually been exercised, report it as **UNVERIFIED**, not PASS.

## 4. Test at the level of the problem

Use the narrowest test that can prove the requested behavior.

- Python logic -> Python/unit/integration test as appropriate.
- JavaScript syntax -> JavaScript syntax/runtime check.
- Database migration -> isolated DB migration/integrity test.
- Browser/UI behavior -> real browser-level test when practical.

For UI work such as clicks, dropdowns, visibility, layout, focus, selection, or browser state, unit tests and string assertions are not sufficient evidence of PASS by themselves. The final verification must exercise the real browser behavior when practical.

Tests should preserve a **confirmed product contract**, not merely encode an agent's unverified implementation assumption.

## 5. Git stores useful checkpoints, not every experiment

Git is the project history and recovery mechanism.

- Commit/PR the useful working state.
- Do not turn every failed implementation attempt into a new branch/PR/release.
- Temporary user-test ZIPs/builds are test artifacts, not automatically releases.
- Do not maintain SHA baselines for live source code.
- Use hashes only where byte identity genuinely matters, such as immutable release artifacts, migration input snapshots, or fixed fixtures.

## 6. CI is the final safety net, not the development manager

CI should verify the already-understood change with focused checks.

- Keep workflows aligned with their actual purpose.
- Do not expand a narrowly named workflow into a universal project gate.
- A CI/guard failure is not automatically a product failure.
- Distinguish **PRODUCT FAIL**, **TEST FAIL**, **CI/GUARD ERROR**, and **UNVERIFIED**.
- CI must never auto-repair, auto-revert, move files, rewrite baselines, or create new development scope.

## 7. Stay inside the requested scope

Do not add unrelated cleanup, architecture work, release machinery, CI work, or refactors unless they are required to make the requested behavior correct.

If an additional technical change is necessary, explain the reason briefly and keep it bounded.

Cross-module edits are not automatically a user decision. The agent should justify and handle technically necessary cross-module work itself unless it creates a material product, data, compatibility, or irreversible decision.

## 8. Ask the user only about meaningful product choices

Do not ask the user to approve internal technical scope that the agent should be able to evaluate.

When a real product/data choice exists, present it as:

**A) Option name**  
Short description  
**+** advantage  
**+** advantage  
**-** disadvantage  
**-** disadvantage  

**B) Option name**  
Short description  
**+** advantage  
**+** advantage  
**-** disadvantage  
**-** disadvantage  

**Which option do you want?**

Only present multiple options when they are genuinely viable and materially different.

## 9. Preserve working behavior and user data

Never trade an unrelated working feature for progress on the current task.

Treat user DB, audio, settings, playlists, tags, and other user-owned data as protected. Any migration or destructive change requires an explicit safety plan and verification appropriate to the risk.

## 10. Keep process lightweight

The repository structure may contain many modules. Do not create protection bureaucracy merely to mirror the folder count.

Prefer:

**clear module boundaries + focused diffs + real behavior tests + Git history + small CI checks**

over:

**large manifests + live-code SHA catalogs + nested approval workflows + self-expanding guards**.
