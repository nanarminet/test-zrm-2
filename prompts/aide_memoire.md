{{REGLES_COMMUNES}}

{{SAVOIR_RESSOURCES}}

# Ta tâche : le panier à idées des aide-mémoire
À partir de l'image choisie par l'apprenant (jointe à ce message : consulte-la sans la décrire), de son motto et des autres éléments qu'il a renseignés (idées favorites, souhait), propose des idées d'aide-mémoire pour lui rappeler son motto :
- EXACTEMENT 4 aide-mémoire FIXES (ils ne peuvent pas bouger) ;
- EXACTEMENT 4 aide-mémoire MOBILES (la personne peut les emporter avec elle).

Consignes :
- Cherche des idées dans 3 catégories : objet, odeur, musique. Renseigne la catégorie de chaque idée dans le champ `categorie`, mais ne l'écris pas dans le texte de l'idée.
- Propose une majorité d'objets : au moins 5 idées sur 8 de catégorie « objet ».
- Sois extrêmement concret et actionnable : l'apprenant doit pouvoir le mettre en place dans les prochains jours. Chaque idée est un court groupe nominal (de 4 à 14 mots), sur le modèle « un porte-clés en forme d'aigle ».
- Odeurs : associe-les à un support matériel précis (une bougie, une huile essentielle, un savon…).
- Musiques et sons : choisis des éléments très connus, associés à du concret (une sonnerie de téléphone, une alarme de réveil…).
- Précise le support quand l'objet peut être fixe ou mobile (fond d'écran du téléphone ou de l'ordinateur de bureau, par exemple).
- Si l'objet est probablement déjà possédé, ajoute ce qui lui donnera une nouvelle signification (un ruban, un nœud, une étiquette…).
- Les 8 idées sont toutes différentes, et chacune s'appuie sur l'image, le motto ou le souhait de l'apprenant. Ne recopie pas les exemples de calibrage.

# Format de sortie (JSON)
`categorie` vaut `objet`, `odeur` ou `musique`.
{
  "fixes": [{"idee": "…", "categorie": "objet"}, {"idee": "…", "categorie": "objet"}, {"idee": "…", "categorie": "odeur"}, {"idee": "…", "categorie": "musique"}],
  "mobiles": [{"idee": "…", "categorie": "objet"}, {"idee": "…", "categorie": "objet"}, {"idee": "…", "categorie": "objet"}, {"idee": "…", "categorie": "musique"}],
  "detresse": false
}
