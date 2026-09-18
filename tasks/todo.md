# Passerelle chatbot FastAPI compatible OpenAI

Design : `docs/superpowers/specs/2026-09-18-fastapi-openai-gateway-design.md`
Branche d'implémentation : `feat/openai-compatible-gateway` (worktree)
PR : dépôt GitHub → `gh pr` (équivalent de la MR GitLab). **Une seule PR**,
un commit conventionnel par étape.

## 1. Outillage mise

- [x] `mise.toml` : outils (python 3.13, uv, ruff, ty, pre-commit, cocogitto, node, `npm:@usebruno/cli`)
- [x] `mise.toml` : tasks **inline** — `install`, `lint`, `format`, `format-check`, `typecheck`, `test`, `check`, `check-commits`, `dev`, `docker-build`, `up`, `down`, `bruno`, `hooks`, `release`
- [x] `mise.lock` généré et commité (`settings.lockfile = true`)
- [x] `pyproject.toml` : métadonnées, deps runtime, groupe dev, config ruff (PEP-8/257/484) + pytest
- [x] `uv.lock` généré et commité
- [x] `.pre-commit-config.yaml` : ruff check --fix, ruff format, ty check, hygiène fichiers, `commit-msg` → `cog verify`
- [x] `cog.toml` : `ignore_merge_commits = true`, changelog `CHANGELOG.md`
- [x] hooks installés et vérifiés sur un commit réel

## 2. Application

- [x] `app/config.py` — `Settings` pydantic-settings, `OPENAI_API_KEY`/`OPENAI_MODEL`/`OPENAI_BASE_URL`/`LOG_LEVEL`, `SecretStr`, fail-fast
- [x] `app/domain.py` — `ChatRequest`, `ChatResult`, `ChatChunk`, `ModelInfo` neutres
- [x] `app/errors.py` — enveloppe OpenAI + handlers (422→400, 401, 429, 502)
- [x] `app/providers/base.py` — `Protocol ChatProvider`
- [x] `app/providers/langchain.py` — `LangChainChatProvider` (`ChatOpenAI`, `ainvoke` + `astream`)
- [x] `app/dependencies.py` — fourniture du provider, override-able en test
- [x] `app/api/v1/{schemas,router}.py` — contrat OpenAI strict + SSE
- [x] `app/api/v2/{schemas,router}.py` — extension `request_id`/`provider`/`latency_ms`
- [x] `app/main.py` — `create_app()`, `/healthz`, montage des routers

## 3. Tests (TDD — rouge avant vert)

- [x] conformité `/v1/chat/completions` (forme de réponse, `object`, `usage`)
- [x] streaming SSE : ordre des chunks, `delta.role` initial, `finish_reason`, `[DONE]`
- [x] `/v1/models`
- [x] extensions `/v2` et indépendance des schémas v1/v2
- [x] remappage des erreurs (corps invalide, upstream 401/429/5xx)
- [x] validation de configuration (clé absente ⇒ démarrage refusé)

## 4. Conteneur

- [x] `Dockerfile` multi-stage, non-root, healthcheck, sans `uv` dans l'image finale
- [x] `.dockerignore`
- [x] `compose.yaml` avec `models:` top-level (Docker Model Runner), exemple **Gemma 4** (`ai/gemma4:e4b-q4_K_M`), mappé sur `OPENAI_BASE_URL`/`OPENAI_MODEL`
- [x] image buildée et démarrée, `/healthz` prouvé OK

## 5. Bruno (manuel, hors CI)

- [x] collection `bruno/` : health, models v1/v2, chat v1, chat v2, chat streaming, erreur 400
- [x] environnements `local` (Compose) et `live` (vrai OpenAI)
- [x] suite exécutée contre le conteneur (4/4 requêtes, 5/5 tests, 8/8 assertions), sortie réelle dans la PR
- [ ] requêtes `03`/`04`/`05` (complétions, streaming) jouées contre un modèle servi — **non faites** : poste insuffisant pour Docker Model Runner

## 6. CI GitHub Actions

- [x] `ci.yml` — un job par vérification : `lint`, `format`, `typecheck`, `test`, `commits`
- [x] `ci.yml` — job `docker` : build seul sur PR, build **et push** GHCR sur `main` (multi-arch, `sha-…` + `latest`)
- [x] job `release` (dans `ci.yml`) — `cog bump --auto` sur `main`, tag + `CHANGELOG.md` + release GitHub, puis push image `X.Y.Z`/`X.Y`/`X`
- [x] pipeline verte sur la PR

## 7. Clôture

- [x] `README.md` : démarrage, variables d'env, compose+modèle, Bruno, tasks mise
- [x] tous les commits en Conventional Commits (`cog check` vert)
- [x] PR ouverte avec section `## Verification` (sorties de commandes réelles)
- [x] pipeline verte = terminé

## Revue

**Livré.** Passerelle FastAPI exposant le contrat OpenAI sur deux versions
vivantes (`/v1` strict, `/v2` enrichi) au-dessus d'un moteur LangChain, image
Docker non-root, suite Bruno, CI GitHub Actions publiant sur GHCR, release
automatique par cog. 38 tests, lint, format et typage verts.

**Écarts avec le plan initial.**

1. `release.yml` a fusionné dans `ci.yml` : un workflow séparé aurait exigé un
   `workflow_run` pour s'enchaîner après les vérifications, là où un job
   `needs: [docker]` gardé sur `main` fait la même chose sans indirection.
2. Le stub d'upstream prévu à l'origine a disparu : la décision 7 (Bruno hors
   CI, contre le conteneur, modèle fourni par Compose) l'a rendu inutile.

**Non vérifié.** Les requêtes Bruno de complétion et de streaming (`03`, `04`,
`05`) n'ont pas été jouées contre un modèle réel : la machine n'a pas la
puissance pour faire tourner Gemma 4 via Docker Model Runner. Le `compose.yaml`
a toutefois été démarré avec succès une fois avant cet arrêt, et Compose y a
bien injecté `OPENAI_MODEL=ai/gemma4:e4b-q4_K_M` et `OPENAI_BASE_URL` dans le
conteneur. Le chemin de chat a été prouvé autrement : requête réelle vers un
upstream injoignable, traduite en 502 `api_error` au format OpenAI, sans fuite
de l'URL amont. Le format SSE, lui, est couvert par pytest (ordre des
fragments, `delta.role` initial, `finish_reason` terminal, `[DONE]`).

**Suggestions pour plus tard, hors périmètre de cette PR.**

- Authentification sur la passerelle elle-même (`Authorization: Bearer`), aujourd'hui absente.
- `GET /v1/models` n'énumère que le modèle configuré ; interroger l'upstream donnerait la vraie liste.
- Le support de `tools` / function calling, absent des deux versions.
