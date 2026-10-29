# POC « Parcours ZRM » – activités IA (Le Vinatier)

Simulation (Streamlit) du parcours de l'aidant·e dans le ZRM, **écrans fixes compris**, avec les 4 usages de l'IA
branchés aux bons endroits. Sert à éprouver les prompts, le contrat JSON et les contrôles en code avant
l'intégration JS. Aucune donnée n'est stockée par l'application.

Parcours simulé, des **consignes du choix de l'image** jusqu'au choix des **mouvements**, puis un **récapitulatif téléchargeable**
(textes repris des PowerPoint « 2. Découverte de ses besoins », « 3. Formulation du motto – Textes octobre 2026 »
et « 4. Identification des ressources ») :

| Étape | Contenu | IA |
|---|---|---|
| 1. Découverte de ses besoins | consignes du choix d'image (premier écran), choix de l'image parmi 45 (5 par ligne, avec confirmation), raisons, mots associés à l'image (liste de cases à cocher à droite de l'image) + mots libres, réflexion, souhait | **lecture du souhait** (repérage d'une détresse uniquement, aucun texte généré) |
| 2. Formulation du motto | infographie, synthèse, **5 phrases dont les verbes, noms communs, noms propres et adjectifs sont cliquables**, rédaction avec **composeur de phrase** (glisser-déposer), **vérification** (10 critères), amélioration, synthèse finale | phrases du motto, vérification du motto |
| 3. Identification des ressources | aide-mémoire, ressources corporelles (mouvements) | **aide-mémoire** (4 fixes + 4 mobiles), **mouvements** (3 macro + 3 micro) |
| Récapitulatif | tous les choix et les ressources associées, fichier HTML à télécharger (image intégrée, imprimable en PDF depuis le navigateur) | aucune |

Le menu, le bilan émotionnel et les ressources sociales ne sont pas simulés ; leurs textes restent dans
`contenus/textes.toml` (blocs inutilisés) pour les réintégrer.
Les audios, vidéos, témoignages et l'infographie ne sont pas inclus : un encadré « Contenu non inclus dans ce test »
tient leur place.

**Accessibilité** : chaque témoignage de Sophie a sous son encadré une transcription écrite (« Lire la transcription du
témoignage »), reprise mot pour mot du document Drive « Témoignage Sophie » (bloc `[transcriptions]` de `textes.toml`).
Les autres médias (podcast de relaxation, vidéos, expériences corps-pensées, infographie) n'ont pas encore d'alternative
textuelle.

**Phrases du motto** : les mots cliquables sont les verbes, noms communs, noms propres et adjectifs. Le modèle indique la
nature de chaque mot ; le code force en « non cliquable » les mots-outils (pronoms, déterminants, y compris les
adjectifs possessifs mon/ma/mes, prépositions, conjonctions, auxiliaires courants) et exige au moins 3 mots cliquables par
phrase. Les adverbes ne sont pas cliquables. Il n'y a **pas** de bouton pour regénérer des phrases (limite des appels API) :
l'IA n'est rappelée que si l'image, les mots ou le souhait changent, ou après un échec (« Réessayer »). La longueur d'une
phrase va de **8 à 20 mots**.

**Composeur de phrase** (écran de rédaction, au-dessus du champ libre) : les mots retenus s'affichent dans un composant
de glisser-déposer (`streamlit-sortables`, paquet tiers, version fixée dans `requirements.txt`) ; sous lui, une zone de
texte libre avant le premier mot et après chaque mot, et un aperçu de la phrase. Le bouton « Placer cette phrase dans mon
champ de rédaction » remplace le contenu du champ libre. Si le paquet n'est pas installé, les mots restent dans l'ordre de la
sélection (message affiché). Le glisser-déposer n'est pas utilisable au clavier : les zones de texte libre le sont.

**Lecture du souhait** : au clic sur « Suivant », l'IA lit le souhait (un appel, relancé seulement si le texte change) et ne
renvoie que le drapeau de détresse. Si elle (ou le filet de mots-clés) en repère une, le message de détresse (15 / 3114)
s'affiche sous le champ et la personne reste sur l'écran ; un second clic sur « Suivant », avec le même texte, la
laisse continuer.

**Boutons de validation** : Streamlit n'envoie le contenu d'un champ texte qu'une fois la saisie validée (clic ailleurs
ou Ctrl+Entrée), pas à chaque lettre. Un bouton ne peut donc pas suivre la frappe pour passer de grisé à actif. Les boutons
« Suivant » du souhait et « Vérifier mon motto » sont donc toujours actifs (rouges) ; si le champ est vide, un message
l'indique et l'on n'avance pas.

## Lancer en local

Python 3.11 ou plus récent.

```powershell
cd poc_activites_ia                       # important : depuis ce dossier
pip install -r requirements.txt
$env:OLLAMA_API_KEY = "votre_clé_ollama"
streamlit run app.py
```

(Linux / macOS : `export OLLAMA_API_KEY=...`.) Alternative : copier `.streamlit/secrets.toml.example`
en `.streamlit/secrets.toml` et y mettre la clé.

**Essayer l'interface sans IA ni clé** : `$env:LLM_PROVIDER = "mock"` (réponses figées, qui ne disent rien de la qualité du modèle).

## Héberger sur Streamlit Community Cloud

1. Déposer le dossier dans un dépôt GitHub (le dossier `images/` et `data/mots_images.json` doivent y être ;
   `data/Mots_Images_ZRM.pptx` est ignoré par `.gitignore` : il pèse 84 Mo et n'est utile qu'à l'extraction).
2. Créer l'application sur share.streamlit.io avec `app.py` comme fichier principal.
3. Dans **Settings > Secrets**, coller par exemple : `OLLAMA_API_KEY = "votre_clé"` (voir `.streamlit/secrets.toml.example`).

Attention : une application publique est accessible à toute personne qui a le lien et **chaque visite consomme
votre quota d'API**. Les images du livret ZRM y sont visibles (voir « Droits des images »).

## Passer de Ollama à Mistral

Il suffit de **remplacer la variable de la clé** :

```powershell
Remove-Item Env:OLLAMA_API_KEY
$env:MISTRAL_API_KEY = "votre_clé_mistral"
streamlit run app.py
```

(Sur Streamlit Cloud : remplacer `OLLAMA_API_KEY` par `MISTRAL_API_KEY` dans les Secrets.)

L'URL (`https://api.mistral.ai/v1`) et le modèle (`mistral-medium-3-5`) sont déduits du fournisseur ; ils sont
regroupés dans `PRESETS` en tête de `llm.py`. Trois précisions :

- La clé Mistral doit aller dans `MISTRAL_API_KEY`. La mettre dans `OLLAMA_API_KEY` l'enverrait à ollama.com (erreur 401).
- Si **les deux** clés sont présentes, l'application refuse de choisir : ajoutez `LLM_PROVIDER=mistral`.
- Autre modèle : `LLM_MODEL` (ex. `mistral-small-2603`). Raisonnement : `LLM_REASONING_EFFORT` (facultatif, non envoyé si vide).

**Image envoyée au modèle** : par défaut, l'image choisie est jointe aux appels (elle guide la construction du motto, en
plus des mots). `LLM_ENVOYER_IMAGE=non` ne l'envoie plus (mots et souhait seuls) : utile pour comparer, ou si le modèle
choisi ne gère pas les images.

## Modifier les textes

Tous les textes fixes sont dans **`contenus/textes.toml`** (un bloc par écran, en Markdown), repris tels quels des
PowerPoint, coquilles comprises (« les flèche de votre clavier », « le champs libre », « sur sur vos idées »…).
Corrigez-les dans ce fichier, sans toucher au code. Les messages de sécurité (détresse, suspension, motto conforme)
sont dans `textes.py`.

## Droits des images

Les 45 images viennent du livre Krause / Storch, *Ressourcen aktivieren mit dem Unbewussten* (Hogrefe, 2022). Leur
page de mentions réserve les droits, y compris la fouille de textes et de données (entraînement d'IA). Ici, l'image
choisie est **envoyée au modèle** à chaque appel, et les images sont publiées avec l'application : à faire valider
par Hogrefe / le Vinatier avant tout usage au-delà de ce test.

## Ce que fait le code en plus du modèle

Le modèle n'est pas cru sur parole (`activites.py`, `checks.py`, `schemas.py`) :

1. **Contrat JSON** : réponse validée (types, nombres d'éléments, 10 critères présents). Schéma envoyé au fournisseur
   (`json_schema`, repli automatique sur `json_object` s'il le refuse) **et** revérifié en local.
2. **Contrôles déterministes** : 8–20 mots par phrase, nature de chaque mot (5 à 25 mots par phrase, 3 cliquables au minimum), négation,
   formule de contrainte, « je », phrases trop proches entre elles, 5 objets minimum sur 8 idées d'aide-mémoire, doublons.
3. **Une relance corrective** (2 appels maximum) avec la liste des défauts. Si un défaut persiste, le résultat est
   affiché tel quel et l'alerte va dans les journaux du serveur (jamais de boucle).
4. **Vérification du motto** : si le code trouve une négation, une contrainte ou l'absence de « je », le critère est
   marqué non respecté même si le modèle l'avait validé ; un motto non conforme exige une suggestion.
   Dans le parcours : motto conforme = message de confirmation seul ; non conforme = seulement les points à ajuster
   + un exemple conforme. Si l'apprenant modifie son motto, il est **revérifié par l'IA** ; il peut avancer avec un motto
   non conforme après une fenêtre d'alerte.
5. **Pas d'emojis** : interdits dans les prompts, détectés dans les réponses (relance), retirés avant affichage, et
   test automatique sur tous les fichiers du dépôt.
6. **Détresse** : drapeau `detresse` du modèle **ou** mots-clés en code (sur toutes les saisies libres) → message fixe
   (`textes.DETRESSE`), jamais généré.
7. **Panne** : si le service est injoignable (après 3 essais), clé refusée ou quota dépassé → message de suspension
   (`textes.SUSPENSION`) avec bouton « Réessayer », saisies conservées.
8. **Injection** : saisies placées dans `<saisie_apprenant>`, chevrons neutralisés, 600 caractères maximum par champ.

Les durées, tokens et problèmes de chaque appel vont dans les **journaux du serveur** (logger `zrm.ia`), pas à l'écran.

## Fichiers

```
app.py                interface : configuration, puis parcours
parcours.py           les écrans, l'état et la navigation
recapitulatif.py      contenu du récapitulatif (écran + fichier HTML téléchargeable)
contenus/textes.toml  textes fixes des écrans (PowerPoint) + textes du récapitulatif
images/               les 45 images (JPEG, orientation corrigée)
data/mots_images.json mots associés à chaque image (10 à 20 mots, fixes)
scripts/              extraire_images_mots.py : régénère images/ et mots_images.json depuis le .pptx
activites.py          les 4 activités IA : appel, contrôles, relance
llm.py                appel HTTP (format OpenAI-compatible), PRESETS, configuration
schemas.py            contrat JSON (+ les 10 critères)
checks.py             vérifications sans IA (mots, négation, détresse, emojis…)
textes.py             messages de sécurité (conforme, détresse, suspension)
prompts.py            assemblage des prompts, nettoyage des saisies, VERSION_PROMPTS
prompts/*.md          system prompts (modifiables sans toucher au code) + savoir ZRM partagé
simulation.py         réponses figées du mode mock
tests/                pytest
```

Pour les développeurs JS : les `prompts/*.md`, le schéma (`schemas.py`), les règles de `checks.py` (volontairement
simples, des regex) et `textes.py` se reprennent tels quels ; le payload HTTP est visible dans `llm.appeler`.

## Tests

```powershell
pip install -r requirements-dev.txt
python -m pytest
```

Les tests n'appellent aucun service : réseau simulé, activités en mode `mock`, et le **parcours complet déroulé avec un
faux module Streamlit** (`tests/faux_streamlit.py`). Ce faux module ne remplace pas un essai dans le navigateur :
les appels Streamlit n'ont pas été exécutés pour de vrai lors de la construction.

## À faire valider (hypothèses de ce POC)

| Sujet | Choix actuel | À valider avec |
|---|---|---|
| Message de détresse | Bienveillant + **15** et **3114**. Les consultantes parlent du « 117 » : ce n'est pas un numéro d'urgence psychique en France (le 116 117 est celui des médecins de garde) | Vinatier / consultantes |
| Mots-clés de détresse | Liste courte et prudente (`checks._DETRESSE`) | Professionnels du Vinatier |
| 8–20 mots par phrase | Maquette : 10 à 20 ; borne basse abaissée à 8 sur demande (les 8 mottos officiels du livret font 8 à 15 mots) | Consultantes |
| Mots associés aux images | Repris tels quels des notes du PowerPoint, dont certains à connotation négative (non retirés) | Consultantes |
| Critère 7 (possessifs) | « mon/ma/mes » exigés pour ce qui appartient à la personne | Consultantes |
| Critère 10 | « Je peux… » accepté comme permission | Consultantes |
| Critère 3 | Estimation qualitative du ton, pas une mesure des émotions | Consultantes |
| Mouvements | Avertissement fixe « propositions à adapter à votre condition physique » | Consultantes |
| Mots cliquables | Verbes, noms communs, noms propres, adjectifs ; adverbes exclus | Consultantes |
| Critère 4 (invitation) | « Je choisis de… » et toute attitude à vivre à la 1re personne sont admis ; refus seulement pour un état constaté (« Je suis calme ») ou un ordre. Les débuts de phrase du livret + « Je choisis de » sont admis d'office par le code | Consultantes |
| Détresse dans le souhait | Message affiché, la personne peut continuer au second clic | Vinatier / consultantes |

## Limites connues

- Les appels réels à Ollama Cloud / Mistral et l'affichage réel Streamlit n'ont pas pu être testés lors de la
  construction (pas d'accès réseau ni de Streamlit installable dans l'environnement de développement) : le premier essai
  réel peut révéler un écart (nom de modèle, format de réponse, réponse tronquée si le modèle « réfléchit » beaucoup,
  rendu d'un composant).
- Les modèles et leurs conditions changent : fixer la version du modèle en production (`LLM_MODEL`) et relire les
  conditions de rétention / ZDR de Mistral avant tout usage avec de vraies données.
- Non traité ici : hébergement et protection de la clé côté JS, RGPD / DPA, plafonds de dépense, accessibilité des médias autres que les témoignages de Sophie (voir plus haut).
