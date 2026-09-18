# Passerelle chatbot FastAPI compatible OpenAI — design

Date : 2026-09-18
Dépôt : `Wihrt/fastapi-langchain` (vide au démarrage, aucun commit)

## 1. Objectif

Exposer une API HTTP **compatible avec l'interface OpenAI** (`/chat/completions`,
`/models`) servie par FastAPI, versionnée par préfixe d'URL, alimentée en interne
par LangChain. N'importe quel client OpenAI (SDK Python, `curl`, Bruno) doit
fonctionner en changeant uniquement `base_url`.

Livrables : l'application, une image Docker, des hooks pre-commit, une suite
Bruno, une CI GitHub Actions qui publie l'image sur GHCR, le tout outillé par
mise avec des tasks **inline** dans `mise.toml`.

## 2. Décisions actées

Réponses de l'utilisateur au round de spec. Seul le point 3 (versioning) n'a pas
été tranché explicitement : il suit la recommandation émise, signalée « hypothèse ».

| # | Sujet | Décision |
|---|-------|----------|
| 1 | Sens de « interface OpenAI » | On **expose** le contrat OpenAI ; on consomme un upstream. |
| 2 | Moteur interne | **LangChain** (`langchain-openai`), derrière une interface `ChatProvider`. |
| 3 | Versioning | *Hypothèse* : préfixe d'URL, deux versions vivantes `/v1` et `/v2`, schémas disjoints. |
| 4 | Streaming SSE | **Oui**, `"stream": true` supporté. |
| 5 | Périmètre | `chat/completions`, `models`, `healthz`. Stateless, pas de RAG, pas de persistance. |
| 6 | Variables d'env | Nommage OpenAI : `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`. Pas d'auth propriétaire. |
| 7 | Cible Bruno | Tourne **contre le conteneur**, **jamais en CI** (lancement manuel). Modèle fourni par Docker Compose (Model Runner). |
| 8 | CI | Un job **par type de vérification** ; build Docker sur PR, build **et push** sur `main` ; release automatique par **cog**, merge commits ignorés. |
| 9 | Python | **3.13**. |

## 3. Architecture

```
app/
  main.py            create_app() : monte les routers, les handlers d'erreur
  config.py          Settings (pydantic-settings), validées au démarrage
  errors.py          enveloppe d'erreur OpenAI + handlers d'exception
  domain.py          types neutres échangés avec le provider
  dependencies.py    fourniture du provider (override-able en test)
  providers/
    base.py          Protocol ChatProvider
    langchain.py     LangChainChatProvider (ChatOpenAI)
  api/
    v1/router.py     contrat OpenAI strict
    v1/schemas.py
    v2/router.py     contrat étendu
    v2/schemas.py
tests/               pytest, provider factice
bruno/               collection + environnements
```

### Le seam qui rend le versioning réel

Le provider ne parle **jamais** les schémas HTTP. Il parle `domain.py` :
`ChatRequest`, `ChatResult`, `ChatChunk`, `ModelInfo` (dataclasses). Chaque
version d'API possède ses propres modèles Pydantic et fait la traduction
`schéma de version ↔ domaine`. Conséquence : `/v2` peut changer sa forme de
requête ou de réponse sans toucher `/v1` ni le provider, et `/v1` reste figé sur
le contrat OpenAI. Aucun modèle Pydantic n'est partagé entre `v1` et `v2` —
c'est volontaire, la duplication est le prix du découplage de version.

### Contrat `/v1` (OpenAI strict)

- `POST /v1/chat/completions` — `model`, `messages[]`, `temperature`, `top_p`,
  `max_tokens`, `stream`, `stop`, `n` (rejeté si ≠ 1). Réponse
  `object: "chat.completion"`, `choices[].message`, `usage`.
- `GET /v1/models` — `object: "list"`, `data[].object: "model"`.
- Streaming : `text/event-stream`, chunks `chat.completion.chunk`, premier chunk
  portant `delta.role`, dernier portant `finish_reason`, puis `data: [DONE]`.

### Contrat `/v2` (extension)

Identique à `/v1`, plus :
- `request_id` sur chaque réponse (et propagé dans l'en-tête `X-Request-ID`) ;
- bloc `provider` : `{"name": ..., "model": ...}` ;
- `latency_ms` mesuré côté passerelle ;
- `usage` toujours présent (jamais `null`), même quand l'upstream ne le fournit
  pas — champs à 0 plutôt qu'absents.

### Erreurs

Enveloppe OpenAI systématique :
`{"error": {"message", "type", "param", "code"}}`.

| Cas | HTTP | `type` |
|-----|------|--------|
| Corps invalide (Pydantic 422 remappé) | 400 | `invalid_request_error` |
| Modèle inconnu | 404 | `invalid_request_error` |
| Clé upstream refusée | 401 | `authentication_error` |
| Quota upstream | 429 | `rate_limit_error` |
| Upstream injoignable / 5xx | 502 | `api_error` |

Le 422 par défaut de FastAPI est remplacé : OpenAI répond 400.

### Configuration

| Variable | Défaut | Rôle |
|----------|--------|------|
| `OPENAI_API_KEY` | — (requis) | clé de l'upstream |
| `OPENAI_MODEL` | `gpt-4o-mini` | modèle par défaut si la requête n'en impose pas |
| `OPENAI_BASE_URL` | vide | upstream alternatif (Docker Model Runner, Ollama, vLLM) |
| `LOG_LEVEL` | `INFO` | verbosité |

Validation au démarrage : clé absente ⇒ l'application refuse de démarrer.
La clé est un `SecretStr`, jamais journalisée.

## 4. Outillage

`mise.toml`, tasks **inline** (`[tasks.x]`, pas de `mise-tasks/`) :
`install`, `lint`, `format`, `typecheck`, `test`, `check` (les quatre),
`dev`, `docker-build`, `up`, `down`, `bruno`, `hooks`, `check-commits`, `release`.

Outils : `python 3.13`, `uv`, `ruff`, `ty`, `pre-commit`, `cocogitto` (binaire
`cog`), `node`, `npm:@usebruno/cli` (Bruno est absent du registre mise —
backend npm).
Lockfile mise activé (`settings.lockfile = true`) pour figer les versions.

`pre-commit` : `ruff check --fix`, `ruff format`, `ty check`, plus les hygiènes
standard (fin de fichier, espaces, YAML/TOML), et un hook `commit-msg` lançant
`cog verify`. Les hooks tournent via mise pour ne pas dépendre d'un
`mise activate` dans le shell de l'utilisateur.

Qualité PEP : PEP-8 et PEP-257 appliqués par ruff (`E`, `W`, `D`, `N`, `I`,
`UP`, `B`, `ANN`, `S`), PEP-484 par `ty` en mode strict sur `app/`.

## 5. Docker

Multi-stage : étage builder `python:3.13-slim` + `uv sync --frozen --no-dev`
dans un venv `/app/.venv` ; étage final `python:3.13-slim` recevant le venv et
`app/`. Utilisateur non-root, `HEALTHCHECK` sur `/healthz`, `uvicorn` en
entrypoint, port 8000. Pas de `uv` dans l'image finale.

## 6. Tests

- **pytest** : `httpx.ASGITransport` contre l'app, provider factice injecté par
  `dependency_overrides`. Couvre : conformité des schémas v1/v2, streaming SSE
  (ordre des chunks, `[DONE]`), remappage des erreurs, validation de config.
- **Bruno** : la vérification externe, **manuelle**, hors CI. Elle tape le
  conteneur lancé par `compose.yaml`, dont l'upstream est un modèle servi
  localement par **Docker Model Runner** déclaré dans le Compose lui-même :

  ```yaml
  services:
    api:
      models:
        chat:
          endpoint_var: OPENAI_BASE_URL
          model_var: OPENAI_MODEL
  models:
    chat:
      model: ai/gemma4:e4b-q4_K_M
      context_size: 4096
  ```

  La syntaxe longue mappe l'URL et le nom du modèle directement sur nos deux
  variables d'environnement — aucune glue à écrire. Le modèle d'exemple est
  **Gemma 4** de Google (`ai/gemma4:e4b-q4_K_M`, quantification GGUF adaptée à
  une exécution locale) ; le README documente un repli plus léger
  (`ai/smollm2`) pour les postes contraints en RAM. Prérequis : Compose ≥ 2.38
  (poste courant : 5.3.1, Model Runner 1.2.6). Un environnement Bruno `live`
  permet de viser le vrai OpenAI en fixant `OPENAI_API_KEY`/`OPENAI_BASE_URL`.

  Les assertions portent sur la **forme** (statut, champs, types, `object`,
  ordre des chunks SSE), jamais sur le texte généré : le modèle local est petit
  et non déterministe.

  La collection se découpe en deux familles, ce qui la rend jouable sans
  modèle : `01`, `02`, `06`, `07` (santé, listes de modèles, erreur de
  validation) ne sollicitent jamais l'upstream et passent contre le conteneur
  seul ; `03`, `04`, `05` (complétions et streaming) exigent un modèle servi.

## 7. CI (GitHub Actions)

Un seul workflow, `ci.yml`. Chaque step passe par une task mise inline.

### Vérifications — sur pull request et sur `main`

Un job **par type de vérification**, en parallèle, tous sur `mise-action` :

| Job | Commande |
|-----|----------|
| `lint` | `mise run lint` (`ruff check`) |
| `format` | `mise run format-check` (`ruff format --check`) |
| `typecheck` | `mise run typecheck` (`ty check`) |
| `test` | `mise run test` (`pytest`) |
| `commits` | `mise run check-commits` (`cog check`) |

Puis `docker`, qui dépend des cinq :
- sur **pull request** : build seul (`push: false`), cache GHA, plateforme hôte —
  on prouve que l'image se construit, on ne publie rien ;
- sur **`main`** : build **et push** vers `ghcr.io/wihrt/fastapi-langchain`,
  multi-arch `amd64/arm64`, tags `sha-<court>` et `latest`.

Bruno n'apparaît dans aucun job : validation externe manuelle (décision 7).

### Release — job du même workflow, `main` uniquement

Un workflow séparé aurait exigé un `workflow_run` pour s'enchaîner après les
vérifications ; un job `needs: [docker]` gardé par `if: github.ref ==
'refs/heads/main'` fait la même chose sans indirection.

`cog bump --auto` calcule la version depuis les commits conventionnels, écrit
`CHANGELOG.md`, crée le tag `vX.Y.Z` (poussé par ses `post_bump_hooks`) et la
release GitHub. `cog.toml` porte
`ignore_merge_commits = true` : les merge commits de PR ne polluent ni le calcul
de version ni le changelog. Quand un tag est produit, le même job pousse l'image
avec les tags sémantiques `X.Y.Z`, `X.Y`, `X`.

Le push de l'image sémantique est fait **dans ce job**, pas dans un workflow
déclenché par le tag : un tag poussé avec `GITHUB_TOKEN` ne redéclenche pas de
workflow, un `on: push: tags` resterait muet.

Versions épinglées : `jdx/mise-action@v4`, `actions/checkout@v7`,
`docker/{login,metadata,setup-buildx,build-push}-action` v4/v6/v4/v7.
Permissions : `contents: write` (release), `packages: write` (GHCR).

### Conséquence sur les commits

La release dépendant de `cog`, **tous** les commits suivent Conventional
Commits, et un hook `commit-msg` (`cog verify`) le garantit localement.

## 8. Ce qui n'est PAS couvert

Pas d'authentification sur notre propre API, pas de rate limiting, pas de
persistance ni d'historique côté serveur, pas d'embeddings, pas de RAG, pas de
`tools`/function calling, pas de multi-provider (l'interface le permet, une
seule implémentation existe), pas de déploiement (l'image s'arrête à GHCR).

## 9. Modes de défaillance anticipés

- **Dérive de conformité OpenAI** sur le streaming (chunks, `[DONE]`) : couvert
  par un test pytest d'ordre des chunks et une requête Bruno dédiée.
- **Fuite de la clé** dans les logs ou les erreurs upstream : `SecretStr` +
  messages d'erreur reformulés, jamais le corps brut de l'upstream.
- **`ty` en préversion** (0.0.x) : version épinglée dans `mise.lock` ; si un
  faux positif bloque, `# ty: ignore[...]` ciblé et commenté, jamais un
  assouplissement global.
- **Modèle Compose indisponible** (Compose trop vieux, pas de Model Runner) :
  documenté dans le README avec le repli `OPENAI_BASE_URL` vers un upstream
  externe ; Bruno étant manuel, la CI n'en dépend pas.
- **Tag poussé par `GITHUB_TOKEN` ne déclenchant aucun workflow** : contourné en
  publiant l'image sémantique dans le job de release lui-même.
- **`cog bump` sur un dépôt sans tag** : le premier bump part de `0.1.0` ;
  vérifié au premier passage sur `main`.
- **Réponses lentes du modèle local** (Gemma 4 sur CPU) : timeouts Bruno
  relevés, `max_tokens` bas dans les requêtes de la collection.

## 10. Plan d'exécution

Le dépôt étant vide, un commit initial sur `main` (ce design + `README`) sert de
base ; l'implémentation se fait ensuite dans un **git worktree** sur
`feat/openai-compatible-gateway`, et arrive par **pull request** (dépôt GitHub,
donc `gh pr`, l'équivalent de la MR GitLab). Terminé = pipeline verte.
