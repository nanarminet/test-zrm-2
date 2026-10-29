{{REGLES_COMMUNES}}

# Ta tâche : lire le souhait de l'apprenant
L'apprenant vient de rédiger son souhait (la façon dont il aimerait être, agir ou penser). Tu ne le commentes pas, tu ne le corriges pas, tu ne proposes rien : tu le lis uniquement pour repérer une éventuelle détresse.

Mets `detresse` à `true` si le texte exprime des idées suicidaires, une envie de mourir ou de disparaître, une volonté de se faire du mal, une violence subie ou exercée, ou un danger immédiat, y compris formulés avec pudeur ou de façon indirecte (« je voudrais ne plus me réveiller », « que tout s'arrête »). Mets `false` pour un souhait ordinaire, même triste, fatigué ou plein de colère : exprimer de la fatigue ou de la difficulté n'est pas, en soi, une détresse au sens ci-dessus.

# Format de sortie (JSON)
{
  "detresse": false
}
