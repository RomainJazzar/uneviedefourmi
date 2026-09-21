# Résultats sur les fourmilières officielles

**9 / 9 fichiers résolus**, toutes les solutions vérifiées (capacités, tunnels existants, simultanéité, arrivée de toutes les fourmis).

| fichier | F | salles | salles interm. | tunnels | cap. min | cap. max | cap. moy. | d (BFS) | T optimal | mouvements | attentes | tunnels utilisés | tunnels inutilisés | débit max/étape | temps (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| fourmiliere_zero.txt | 2 | 4 | 2 | 4 | 1 | 1 | 1.0 | 2 | 2 | 4 | 0 | 4 | 0 | 2 | 0.8 |
| fourmiliere_un.txt | 5 | 4 | 2 | 3 | 1 | 1 | 1.0 | 3 | 7 | 15 | 10 | 3 | 0 | 1 | 5.1 |
| fourmiliere_deux.txt | 5 | 4 | 2 | 4 | 1 | 1 | 1.0 | 1 | 1 | 5 | 0 | 1 | 3 | illimité | 0.4 |
| fourmiliere_trois.txt | 5 | 6 | 4 | 5 | 1 | 1 | 1.0 | 3 | 7 | 15 | 10 | 3 | 2 | 1 | 7.1 |
| fourmiliere_quatre.txt | 10 | 8 | 6 | 9 | 1 | 2 | 1.33 | 5 | 9 | 50 | 20 | 9 | 0 | 2 | 17.2 |
| fourmiliere_cinq.txt | 50 | 16 | 14 | 20 | 1 | 8 | 2.93 | 5 | 11 | 272 | 134 | 20 | 0 | 8 | 66.3 |
| fourmiliere_3D.txt | 50 | 11 | 9 | 15 | 1 | 6 | 3.56 | 4 | 14 | 228 | 227 | 12 | 3 | 5 | 66.6 |
| La_hormiguera_de_la_muerte.txt | 30 | 12 | 10 | 46 | 2 | 5 | 3.3 | 4 | 9 | 120 | 75 | 10 | 36 | 5 | 50.3 |
| salle_d_at-ant.txt | 100 | 23 | 21 | 28 | 1 | 50 | 13.95 | 6 | 15 | 684 | 378 | 28 | 0 | 12 | 243.3 |

- **d** : plus court chemin Sv → Sd (BFS), borne basse : aucune fourmi n'arrive avant.
- **T optimal** : premier horizon pour lequel le max-flow du graphe temporel vaut F.
- **attentes** : nombre de fois où une fourmi pas encore arrivée reste sur place pendant une étape.
- **débit max/étape** : coupe minimale du graphe des salles (fourmis pouvant arriver par étape en régime établi).
- **temps** : résolution complète (recherche de T + min-cost + décomposition), meilleur de 3 exécutions.
