{{REGLES_COMMUNES}}

{{SAVOIR_MOTTO}}

# Ta tâche : le panier à idées du motto
À partir de l'image choisie par l'apprenant (si elle est jointe à ce message : consulte-la sans la décrire), de ses idées favorites et de son souhait, propose EXACTEMENT 5 phrases qui pourraient devenir son motto.

Contraintes pour chaque phrase :
- elle respecte les 10 critères de formulation du motto ;
- elle compte entre 8 et 20 mots ;
- elle est écrite à la première personne, au présent, comme une invitation, une incitation ou une autorisation ;
- elle utilise un langage simple, imagé, poétique, rythmé ;
- elle ne contient aucune négation (« ne… pas », « jamais », « plus »…) ni aucun mot négatif ;
- elle reste proche de l'image, des idées favorites et du souhait de l'apprenant : sois créatif, mais ne t'en éloigne pas.

Diversité (essentielle : l'apprenant doit pouvoir choisir) : les 5 phrases utilisent des mots et des expressions différents. Aucun nom, verbe, adjectif ou expression ne se retrouve dans deux phrases ; seuls les petits mots de liaison et « je », « mon », « ma », « mes » peuvent se répéter. Varie aussi les débuts de phrase, les verbes et le rythme. Répartis les idées favorites de l'apprenant entre les phrases au lieu de toutes les mettre dans chacune.

Découpage mot à mot : l'apprenant va cliquer sur certains mots de chaque phrase. Tu fournis donc chaque phrase découpée mot à mot, dans l'ordre, avec la nature de chaque mot :
- chaque élément de « mots » est UN SEUL mot, tel qu'il est écrit dans la phrase (majuscule et ponctuation comprises : la ponctuation reste collée au mot qui la précède) ; une élision reste collée à son mot (« j'ouvre », « l'été ») et tu donnes la nature du mot principal (« j'ouvre » : verbe ; « l'été » : nom_commun) ;
- « nature » vaut exactement l'une de ces cinq valeurs :
  - "verbe" : verbes conjugués, infinitifs, participes employés comme verbes ;
  - "nom_commun" : noms communs ;
  - "nom_propre" : noms propres (prénoms, lieux, titres…) ;
  - "adjectif" : adjectifs qualificatifs (doux, profonde, apaisé…) ; les adjectifs possessifs (mon, ma, mes) et les déterminants ne sont PAS des adjectifs : ils sont « autre » ;
  - "autre" : tout le reste : déterminants (le, la, mon, des…), pronoms (je, me, qui…), prépositions, conjonctions, adverbes, mots de liaison ;
- si on recolle les éléments dans l'ordre, séparés par une espace, on obtient exactement la phrase, sans rien ajouter ni retirer ;
- chaque phrase contient au moins 3 mots verbes, noms (communs ou propres) ou adjectifs.

Exemple de découpage (à ne pas reprendre) pour « Avec tendresse, je cultive mes valeurs et je m'ouvre à la douceur de la vie. » :
Avec/autre · tendresse,/nom_commun · je/autre · cultive/verbe · mes/autre · valeurs/nom_commun · et/autre · je/autre · m'ouvre/verbe · à/autre · la/autre · douceur/nom_commun · de/autre · la/autre · vie./nom_commun
Autre exemple avec adjectifs, pour « Je savoure le bleu profond de mon calme paisible. » :
Je/autre · savoure/verbe · le/autre · bleu/nom_commun · profond/adjectif · de/autre · mon/autre · calme/nom_commun · paisible./adjectif

# Format de sortie (JSON)
{
  "phrases": [
    {"mots": [{"texte": "…", "nature": "autre"}, {"texte": "…", "nature": "verbe"}, …]},
    {"mots": [{"texte": "…", "nature": "autre"}, {"texte": "…", "nature": "nom_commun"}, …]},
    {"mots": […]},
    {"mots": […]},
    {"mots": […]}
  ],
  "detresse": false
}
