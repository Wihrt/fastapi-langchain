# Passerelle chatbot FastAPI compatible OpenAI

Design : `docs/superpowers/specs/2026-09-18-fastapi-openai-gateway-design.md`
Branche d'implémentation : `feat/openai-compatible-gateway` (worktree)
PR : dépôt GitHub → `gh pr` (équivalent de la MR GitLab). **Une seule PR**,
un commit conventionnel par étape.

## 1. Outillage mise

- [ ] `mise.toml` : outils (python 3.13, uv, ruff, ty, pre-commit, cocogitto, node, `npm:@usebruno/cli`)
- [ ] `mise.toml` : tasks **inline** — `install`, `lint`, `format`, `format-check`, `typecheck`, `test`, `check`, `check-commits`, `dev`, `docker-build`, `up`, `down`, `bruno`, `hooks`, `release`
- [ ] `mise.lock` généré et commité (`settings.lockfile = true`)
- [ ] `pyproject.toml` : métadonnées, deps runtime, groupe dev, config ruff (PEP-8/257/484) + pytest
- [ ] `uv.lock` généré et commité
- [ ] `.pre-commit-config.yaml` : ruff check --fix, ruff format, ty check, hygiène fichiers, `commit-msg` → `cog verify`
- [ ] `cog.toml` : `ignore_merge_commits = true`, changelog `CHANGELOG.md`
- [ ] hooks installés et vérifiés sur un commit réel

## 2. Application

- [ ] `app/config.py` — `Settings` pydantic-settings, `OPENAI_API_KEY`/`OPENAI_MODEL`/`OPENAI_BASE_URL`/`LOG_LEVEL`, `SecretStr`, fail-fast
- [ ] `app/domain.py` — `ChatRequest`, `ChatResult`, `ChatChunk`, `ModelInfo` neutres
- [ ] `app/errors.py` — enveloppe OpenAI + handlers (422→400, 401, 429, 502)
- [ ] `app/providers/base.py` — `Protocol ChatProvider`
- [ ] `app/providers/langchain.py` — `LangChainChatProvider` (`ChatOpenAI`, `ainvoke` + `astream`)
- [ ] `app/dependencies.py` — fourniture du provider, override-able en test
- [ ] `app/api/v1/{schemas,router}.py` — contrat OpenAI strict + SSE
- [ ] `app/api/v2/{schemas,router}.py` — extension `request_id`/`provider`/`latency_ms`
- [ ] `app/main.py` — `create_app()`, `/healthz`, montage des routers

## 3. Tests (TDD — rouge avant vert)

- [ ] conformité `/v1/chat/completions` (forme de réponse, `object`, `usage`)
- [ ] streaming SSE : ordre des chunks, `delta.role` initial, `finish_reason`, `[DONE]`
- [ ] `/v1/models`
- [ ] extensions `/v2` et indépendance des schémas v1/v2
- [ ] remappage des erreurs (corps invalide, upstream 401/429/5xx)
- [ ] validation de configuration (clé absente ⇒ démarrage refusé)

## 4. Conteneur

- [ ] `Dockerfile` multi-stage, non-root, healthcheck, sans `uv` dans l'image finale
- [ ] `.dockerignore`
- [ ] `compose.yaml` avec `models:` top-level (Docker Model Runner), exemple **Gemma 4** (`ai/gemma4:e4b-q4_K_M`), mappé sur `OPENAI_BASE_URL`/`OPENAI_MODEL`
- [ ] image buildée et démarrée, `/healthz` prouvé OK

## 5. Bruno (manuel, hors CI)

- [ ] collection `bruno/` : health, models v1/v2, chat v1, chat v2, chat streaming, erreur 400
- [ ] environnements `local` (Compose) et `live` (vrai OpenAI)
- [ ] suite exécutée contre le conteneur, sortie réelle collée dans la PR

## 6. CI GitHub Actions

- [ ] `ci.yml` — un job par vérification : `lint`, `format`, `typecheck`, `test`, `commits`
- [ ] `ci.yml` — job `docker` : build seul sur PR, build **et push** GHCR sur `main` (multi-arch, `sha-…` + `latest`)
- [ ] `release.yml` — `cog bump --auto` sur `main`, tag + `CHANGELOG.md` + release GitHub, puis push image `X.Y.Z`/`X.Y`/`X`
- [ ] pipeline verte sur la PR

## 7. Clôture

- [ ] `README.md` : démarrage, variables d'env, compose+modèle, Bruno, tasks mise
- [ ] tous les commits en Conventional Commits (`cog check` vert)
- [ ] PR ouverte avec section `## Verification` (sorties de commandes réelles)
- [ ] pipeline verte = terminé

## Revue

*(à remplir en fin de travaux)*
