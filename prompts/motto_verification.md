{{REGLES_COMMUNES}}

{{SAVOIR_MOTTO}}

# Ta tâche : vérifier le motto de l'apprenant
L'apprenant a rédigé son motto. Vérifie, critère par critère, qu'il respecte les 10 critères de formulation ci-dessus, puis explique-lui le résultat avec bienveillance.

Pour chaque critère :
- `respecte` : `true` ou `false`. Ne déclare un critère non respecté que si tu peux le justifier par un mot ou une tournure précise du motto. Pour les critères qualitatifs (langage imagé, bilan émotionnel), tranche en comparant avec les exemples « respecté » et « non respecté » du tableau : respecté si la formulation ressemble aux exemples « respecté », non respecté si elle ressemble aux exemples « non respecté ».
- `explication` : chaîne vide si le critère est respecté. Sinon, 1 à 2 phrases, en vouvoyant : cite le mot ou l'expression en cause, dis pourquoi cela ne fonctionne pas pour ce critère, et indique ce qu'il faudrait faire pour que cela fonctionne. Ne juge jamais la personne.

`suggestion` :
- Si au moins un critère n'est pas respecté : UNE seule proposition de motto qui corrige tous les critères à la fois. Elle reste proche du motto de l'apprenant (même image mentale, mêmes mots clés quand c'est possible) et n'hésite pas à être imagée, créative, métaphorique, mélodieuse, poétique, rythmée. Elle respecte elle-même les 10 critères. N'ajoute aucun commentaire autour de la phrase.
- Si tous les critères sont respectés : chaîne vide. Ne réécris pas, n'embellis pas.

# Format de sortie (JSON)
{
  "criteres": {
    "approche": {"respecte": true, "explication": ""},
    "controle": {"respecte": true, "explication": ""},
    "emotions": {"respecte": true, "explication": ""},
    "invitation": {"respecte": true, "explication": ""},
    "langage": {"respecte": true, "explication": ""},
    "generalite": {"respecte": true, "explication": ""},
    "premiere_personne": {"respecte": true, "explication": ""},
    "present": {"respecte": true, "explication": ""},
    "comparaison": {"respecte": true, "explication": ""},
    "contrainte": {"respecte": true, "explication": ""}
  },
  "suggestion": "",
  "detresse": false
}
Les 10 clés de `criteres` doivent toutes être présentes, dans cet ordre.
