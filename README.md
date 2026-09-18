# fastapi-langchain

Passerelle de chatbot qui **expose l'interface OpenAI** (`/chat/completions`,
`/models`) et l'alimente par LangChain. N'importe quel client OpenAI fonctionne
en changeant seulement son `base_url` — SDK Python, `curl`, Bruno.

L'API est versionnée par préfixe d'URL, avec deux versions vivantes :

| Version | Contrat |
|---------|---------|
| `/v1` | OpenAI strict, figé. Rien de plus que ce qu'OpenAI renvoie. |
| `/v2` | Même contrat, plus `request_id`, `provider`, `latency_ms`, et un `usage` toujours présent. |

Les deux versions ont des schémas Pydantic entièrement séparés : `/v1` ne peut
pas dériver quand `/v2` évolue. Elles partagent un seul moteur, qui ne connaît
aucun schéma HTTP.

## Démarrer

Tout l'outillage est déclaré dans `mise.toml` ; les dépendances Python passent
par `uv`.

```bash
mise install      # python, uv, ruff, ty, pre-commit, cocogitto, node, bruno
mise run install  # dépendances du projet (uv sync)
mise run hooks    # hooks pre-commit et commit-msg
mise run dev      # API sur http://localhost:8000
```

## Configuration

Les variables portent les noms d'OpenAI : un déploiement déjà prévu pour OpenAI
n'a rien à renommer.

| Variable | Défaut | Rôle |
|----------|--------|------|
| `OPENAI_API_KEY` | — **requis** | Clé transmise à l'upstream. Absente, l'application refuse de démarrer. |
| `OPENAI_MODEL` | `gpt-4o-mini` | Modèle utilisé quand la requête n'en impose pas. |
| `OPENAI_BASE_URL` | vide | Upstream alternatif compatible OpenAI (Docker Model Runner, Ollama, vLLM). |
| `LOG_LEVEL` | `INFO` | Verbosité. |

Le champ `model` du corps de requête reste accepté ; omis, il retombe sur
`OPENAI_MODEL`. La clé est un `SecretStr` : elle n'apparaît ni dans les
journaux ni dans les messages d'erreur.

## Conteneur

```bash
mise run docker-build
docker run --rm -p 8000:8000 \
  -e OPENAI_API_KEY=sk-... -e OPENAI_MODEL=gpt-4o-mini \
  fastapi-langchain:dev
```

L'image est multi-étage : `uv` installe les dépendances à l'étage de
construction et ne suit pas dans l'image finale, qui tourne en non-root
(uid 10001) avec un `HEALTHCHECK` sur `/healthz`.

### Avec un modèle local, sans rien installer

`compose.yaml` déclare le modèle comme un élément `models` de la spécification
Compose — Docker Model Runner le sert, et Compose injecte son URL et son nom
directement dans `OPENAI_BASE_URL` et `OPENAI_MODEL` :

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

```bash
mise run up    # télécharge Gemma 4 au premier lancement
mise run down
```

Prérequis : Docker Compose ≥ 2.38 et Docker Model Runner. Sur un poste
contraint en RAM ou en CPU, remplacer le modèle par `ai/smollm2`.

## Vérifications

```bash
mise run check   # lint + format + typage + tests
mise run lint    # ruff check
mise run format  # ruff format
mise run typecheck
mise run test
```

PEP-8 et PEP-257 sont tenus par ruff (`E`, `W`, `N`, `D`), PEP-484 par `ty`.
Les hooks pre-commit appellent ces mêmes binaires **via mise**, donc aux
versions figées par `mise.lock` : aucun second jeu de versions à maintenir.

## Suite Bruno

Vérification externe, **manuelle** : elle n'est pas jouée en CI.

```bash
mise run up      # la passerelle et son modèle
mise run bruno   # bru run --env local -r
```

La collection se découpe en deux familles :

- `01`, `02`, `06`, `07` — santé, listes de modèles, erreur de validation.
  Aucun appel au modèle : elles passent contre le conteneur seul.
- `03`, `04`, `05` — complétions et streaming. Elles exigent un modèle servi.

Les assertions portent sur la **forme** (statut, champs, `object`, ordre des
fragments SSE, sentinelle `[DONE]`), jamais sur le texte produit : un petit
modèle local n'est pas déterministe.

L'environnement `live` vise une instance déployée via `GATEWAY_URL` :

```bash
GATEWAY_URL=https://passerelle.exemple.fr mise exec -- bru run --env live -r
```

## CI

`.github/workflows/ci.yml`, un job par type de vérification — `lint`,
`format`, `typecheck`, `test`, `commits` — puis :

- `docker` : sur pull request, l'image est **construite sans être publiée** ;
  sur `main`, elle est publiée sur `ghcr.io/wihrt/fastapi-langchain` en
  `amd64`/`arm64`, tags `sha-<court>` et `latest` ;
- `release` : `cog bump --auto` calcule la version depuis les commits
  conventionnels, écrit `CHANGELOG.md`, pose et pousse le tag `vX.Y.Z`, crée la
  release GitHub, puis publie l'image en `X.Y.Z` / `X.Y` / `X`.

Chaque step appelle une task mise inline. Les messages de commit suivent donc
les Conventional Commits, garantis localement par un hook `commit-msg`
(`cog verify`) et en CI par `cog check`.

## Hors périmètre

Pas d'authentification sur cette API, pas de limitation de débit, pas
d'historique côté serveur (les conversations sont sans état, comme chez
OpenAI), pas d'embeddings, pas de RAG, pas de `tools`. L'interface
`ChatProvider` autorise d'autres moteurs ; une seule implémentation existe.
