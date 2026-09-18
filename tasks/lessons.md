# Leçons

## Ne pas engager la machine dans une charge lourde sans le demander

**2026-09-18** — J'ai lancé `docker compose up` avec un modèle Gemma 4 servi
par Docker Model Runner pour valider la suite Bruno. Correction reçue :
« Continue, mais sans faire tourner la stack avec docker compose. Pas assez de
puissance. »

**Règle.** Avant de démarrer quoi que ce soit qui télécharge plusieurs
gigaoctets ou occupe durablement le CPU ou la RAM du poste — modèle local,
cluster, build multi-arch émulé, jeu de données volumineux — le demander
d'abord, ou choisir d'emblée la variante légère. Une vérification « réaliste »
ne vaut pas de rendre la machine inutilisable.

**Conséquence sur la preuve.** Quand la vérification lourde est écartée,
chercher la preuve équivalente qui ne coûte rien plutôt que de renoncer : ici,
la route de chat a été prouvée contre un upstream injoignable (traduction en
502 au format OpenAI), et le format SSE reste couvert par pytest. Et dire
explicitement ce qui n'a **pas** été vérifié, dans la PR comme dans le suivi.

## Découper une suite externe pour qu'elle reste jouable dégradée

**2026-09-18** — Corollaire du point précédent. Une collection Bruno dont
chaque requête exige un modèle servi devient invérifiable dès que le modèle
manque. En séparant les requêtes qui ne sollicitent pas l'upstream (santé,
listes, erreurs de validation) de celles qui en ont besoin (complétions,
streaming), la moitié de la suite reste exécutable contre le conteneur seul.
À prévoir dès l'écriture de la suite, pas après coup.
