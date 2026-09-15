# Présentation — Une vie de fourmi

**Équipe : Romain • Lisa • Yannis**

## 1 — Une vie de fourmi
**Intervenant : Romain**

Du plus court chemin à l'optimisation d'un trafic multi-agents.

- Python • Algorithmique
- NetworkX
- Flot maximal
- Graphe temporel
- Visualisation

**Objectif :** faire arriver la dernière fourmi le plus tôt possible.

## 2 — Le problème en une image
**Intervenant : Romain**

Ce n'est pas un problème de chemin : c'est un problème de trafic.

**Analogie réseau de métro :**
- Salles → stations
- Tunnels → lignes
- Fourmis → passagers
- Capacités → quais limités

**Question centrale :** comment faire arriver la dernière fourmi le plus tôt possible ?

## 3 — Les règles à respecter
**Intervenant : Romain**

1. Toutes les fourmis partent de Sv et terminent dans Sd.
2. À chaque étape : attendre OU aller dans une salle adjacente.
3. Capacité 1 par défaut dans les salles intermédiaires, sauf `SN{X}`.
4. Sv et Sd ne sont pas limitants.
5. Les mouvements d'une même étape sont simultanés.
6. On minimise le nombre total d'étapes jusqu'à la dernière arrivée.

**Point clé :** une fourmi peut entrer pendant que l'occupante sort.

## 4 — Modéliser la fourmilière en graphe
**Intervenant : Romain**

- Salle → sommet
- Tunnel → arête
- Capacité → contrainte
- Déplacement → transition

**Matrice d'adjacence du cas simple :**

| | Sv | S1 | S2 | Sd |
|---|---:|---:|---:|---:|
| Sv | 0 | 1 | 1 | 0 |
| S1 | 1 | 0 | 0 | 1 |
| S2 | 1 | 0 | 0 | 1 |
| Sd | 0 | 1 | 1 | 0 |

NetworkX nous donne la structure du graphe ; notre travail ajoute le temps, les capacités et la recherche d'optimalité.

## 5 — Pourquoi le plus court chemin ne suffit pas
**Intervenante : Lisa**

Optimiser une fourmi ≠ optimiser toute la colonie.

- Un chemin très court mais de capacité 1 crée une file d'attente.
- Plusieurs chemins en parallèle peuvent réduire le temps total.
- La métrique pertinente est le temps d'arrivée de **la dernière fourmi**.

## 6 — Notre idée : déplier le temps
**Intervenante : Lisa**

Transformer un problème dynamique en réseau de flot.

Pour chaque instant `t = 0 ... T`, on crée une copie de chaque salle.

- `salle(t) → voisine(t+1)` = déplacement
- `salle(t) → salle(t+1)` = attente
- salle `in → out` avec capacité X = capacité de la salle

Chaque chemin dans ce graphe représente une trajectoire possible dans le temps.

## 7 — Comment garantir le nombre minimum d'étapes
**Intervenante : Lisa**

1. Calculer `d`, longueur du plus court chemin Sv → Sd.
2. Tester `T = d` en construisant le graphe temporel.
3. Calculer le max-flow : atteint-il F ?
4. Sinon tester `T + 1`.

**Premier T faisable = minimum garanti.**

Aucune solution ne peut exister pour les horizons plus petits déjà testés.

## 8 — Une solution optimale… et lisible
**Intervenante : Lisa**

**Max-flow :** répond à la question « existe-t-il une organisation qui fait arriver F fourmis en T étapes ? »

Il garantit :
- la faisabilité ;
- le respect des capacités ;
- l'optimalité de T grâce à la recherche croissante.

**Min-cost-flow :** à horizon déjà optimal, privilégie :
- les arrivées précoces ;
- moins d'attentes ;
- moins de détours inutiles.

Puis le flot est décomposé en `f1`, `f2`, `f3`, etc.

## 9 — Architecture du projet
**Intervenant : Yannis**

**ants.py — cœur**
- modèle ;
- parsing ;
- graphe temporel ;
- max-flow / min-cost-flow ;
- validation finale.

**main.py — orchestration**
- CLI fichier ou dossier ;
- lancement ;
- création des outputs ;
- export.

**visualization.py — visuel**
- graphe ;
- images étape par étape ;
- animation GIF.

**tests/test_ants.py :** 6 tests automatiques.  
**README.md :** installation, explication, preuve, sources.

## 10 — Démonstration : le cas simple du sujet
**Intervenant : Yannis**

**3 fourmis • 2 chemins • optimum = 3 étapes**

**E1**
- f1 : Sv → S1
- f2 : Sv → S2

**E2**
- f1 : S1 → Sd
- f2 : S2 → Sd
- f3 : Sv → S1

**E3**
- f3 : S1 → Sd

E2 illustre la simultanéité : f3 entre dans S1 au même moment où f1 la quitte.

## 11 — Tests, validation et sorties
**Intervenant : Yannis**

**6 / 6 tests automatiques OK**

Cas vérifiés :
- cas simple ;
- tunnel direct ;
- capacité 1 ;
- capacité 2 ;
- graphe inaccessible ;
- validation complète.

Validation post-solution :
- chaque mouvement correspond à une arête ;
- les capacités ne sont jamais dépassées ;
- toutes les fourmis terminent dans Sd.

Fichiers produits : `solution.txt`, `graphe.png`, `matrice_adjacence.csv`, `animation.gif`, `etapes/etape_XX.png`.

## 12 — Conclusion
**Intervenant : Yannis**

1. **Modélisation fidèle** — salles, capacités, attentes et mouvements simultanés sont explicites.
2. **Optimalité garantie** — le premier horizon T faisable est le nombre minimal d'étapes.
3. **Rendu complet** — étapes texte, graphe, matrice, images, GIF, tests et documentation.

> **Le plus court chemin optimise un trajet. Notre algorithme optimise tout le trafic.**

**Questions ?**

## 13 — Annexe : sources et validation

- Sujet : « Une vie de fourmi » — La Plateforme.
- NetworkX : `networkx.org/documentation/stable/tutorial.html`
- Matrice d'adjacence : `people.revoledu.com/kardi/tutorial/GraphTheory/Adjacency-Matrix.html`

Le sujet demande explicitement : graphe, étapes, visualisation, diaporama et repository public avec `ants.py`, `main.py` et `README.md`.

**Jeu de données officiel :** le lien Google Drive présent dans le PDF a été identifié, mais le fichier n'était pas accessible depuis l'environnement de génération. Le parseur et l'algorithme sont prêts à exécuter ces cas dès que le fichier est fourni.
