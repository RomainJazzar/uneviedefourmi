# Une vie de fourmi

Projet Python - Algorithmique / graphes / optimisation

**Équipe : Romain - Lisa - Yannis**

## 1. Problématique

Une colonie de `F` fourmis part du vestibule `Sv` et doit rejoindre le dortoir `Sd` en **un minimum d'étapes**. La fourmilière est composée de salles reliées par des tunnels.

À chaque étape, une fourmi peut soit attendre, soit rejoindre une salle voisine. Les salles intermédiaires ont une capacité limitée (1 par défaut, ou `X` pour une salle `SN{X}`). `Sv` et `Sd` ne sont pas limitants.

Le projet doit donc répondre à trois questions :

1. Comment représenter la fourmilière proprement ?
2. Comment trouver un déplacement **réellement optimal**, pas seulement « un chemin court » ?
3. Comment rendre le résultat compréhensible visuellement ?

## 2. Idée de la solution

Nous représentons la fourmilière avec un **graphe non orienté** :

- une salle = un sommet ;
- un tunnel = une arête ;
- la capacité d'une salle = le nombre maximal de fourmis qui peuvent y être simultanément.

Le point important est qu'un simple algorithme de plus court chemin ne suffit pas. Plusieurs fourmis doivent circuler en même temps et peuvent se bloquer à cause des capacités des salles.

Notre solution transforme donc le problème en **flot dans le temps** (*time-expanded network*).

### Principe

Pour tester si toutes les fourmis peuvent arriver en `T` étapes :

- on crée une copie de chaque salle pour chaque instant `0, 1, ..., T` ;
- on relie une salle à elle-même à l'instant suivant pour représenter l'attente ;
- on relie deux salles voisines entre deux instants successifs pour représenter un déplacement ;
- chaque salle intermédiaire est découpée en une entrée et une sortie afin d'imposer sa capacité ;
- on calcule ensuite un **flot maximal** de `Sv` vers `Sd`.

Si le flot maximal vaut `F`, alors les `F` fourmis peuvent atteindre le dortoir en `T` étapes.

Nous commençons à la longueur du plus court chemin entre `Sv` et `Sd`, puis nous augmentons `T` jusqu'au premier horizon réalisable. **Le premier horizon réalisable est donc le nombre minimal d'étapes.**

À cet horizon minimal, un flot de coût minimal est utilisé pour privilégier les arrivées précoces au dortoir et obtenir une solution plus lisible.

## 3. Structure du repository

```text
uneviedefourmi/
├── ants.py                 # Modèle, parsing et algorithme optimal
├── main.py                 # Point d'entrée du programme
├── visualization.py        # Graphe, étapes et GIF animé
├── requirements.txt
├── README.md
├── inputs/
│   ├── cas_simple.txt
│   ├── cas_capacites.txt
│   └── cas_plusieurs_chemins.txt
├── outputs/                # Résultats générés
└── tests/
    └── test_ants.py
```

## 4. Installation

Python 3.11+ est recommandé.

```bash
python -m venv .venv
```

Windows :

```bash
.venv\Scripts\activate
```

Linux / macOS :

```bash
source .venv/bin/activate
```

Puis :

```bash
pip install -r requirements.txt
```

## 5. Lancer le projet

Exemple fourni :

```bash
python main.py inputs/cas_simple.txt
```

Autre dossier de sortie :

```bash
python main.py inputs/cas_simple.txt --output mes_resultats
```

Pour lancer les tests :

```bash
python -m unittest discover -s tests -v
```

## 6. Format des fichiers d'entrée

Le parseur accepte plusieurs écritures pour le nombre de fourmis :

```text
8
```

ou :

```text
F=8
```

ou :

```text
fourmis: 8
```

Puis un tunnel par ligne :

```text
Sv-S1
S1-S2
S2-Sd
```

Une capacité peut être indiquée directement sur une salle :

```text
S1{3}
```

ou dans un tunnel :

```text
Sv-S1{3}
S1-Sd
```

Les lignes commençant par `#` sont utilisables comme commentaires.

## 7. Exemple du sujet

Entrée :

```text
3
Sv-S1
Sv-S2
S1-Sd
S2-Sd
```

Sortie :

```text
+++ E1 +++
f1 - Sv - S1
f2 - Sv - S2
+++ E2 +++
f1 - S1 - Sd
f2 - S2 - Sd
f3 - Sv - S1
+++ E3 +++
f3 - S1 - Sd
```

Les trois fourmis arrivent donc en **3 étapes**, ce qui correspond au cas simple donné dans le sujet.

## 8. Fichiers produits automatiquement

Pour chaque fourmilière, le programme crée :

- `solution.txt` : toutes les étapes de déplacement ;
- `graphe.png` : représentation de la fourmilière ;
- `matrice_adjacence.csv` : matrice d'adjacence ;
- `animation.gif` : animation complète ;
- `etapes/etape_XX.png` : une image pour chaque étape.

## 9. Pourquoi la solution est optimale ?

Soit `d` la longueur du plus court chemin entre `Sv` et `Sd`.

Aucune fourmi ne peut arriver avant `d` étapes. Nous testons donc `T = d`, puis `d + 1`, `d + 2`, etc.

Pour un `T` donné, le graphe temporel représente **tous les déplacements autorisés** pendant ces `T` étapes, avec exactement les mêmes contraintes de capacité que le sujet. Si un flot de valeur `F` existe, il représente `F` trajectoires simultanées valides.

Le premier `T` pour lequel un flot de valeur `F` existe est donc, par construction, le minimum possible.

## 10. Complexité - ce qu'il faut retenir à l'oral

Le graphe temporel contient environ :

- `(T + 1) × nombre_de_salles` copies de salles ;
- des arêtes d'attente ;
- des arêtes de déplacement pour chaque tunnel et chaque étape.

La taille augmente donc avec le nombre de salles, de tunnels et avec l'horizon `T`. Pour un projet pédagogique et des fourmilières de taille raisonnable, cette méthode a un avantage majeur : **elle garantit l'optimalité** et reste simple à justifier.

## 11. Vulgarisation

Imaginez la fourmilière comme un petit réseau de métro. Les salles sont des stations, les tunnels sont les lignes, et chaque station ne peut accueillir qu'un certain nombre de passagers. Envoyer toutes les fourmis par le chemin le plus court provoquerait parfois un embouteillage. Notre programme regarde donc plusieurs itinéraires en même temps et organise les départs pour utiliser au mieux les salles disponibles. Il teste le temps minimum possible et vérifie si toutes les fourmis peuvent arriver sans dépasser la capacité des salles. Dès que c'est possible, il s'arrête : on obtient ainsi le planning le plus rapide.

## 12. Tests réalisés

Le projet vérifie notamment :

- le cas simple du sujet : 3 étapes ;
- un tunnel direct `Sv-Sd` : 1 étape, quel que soit le nombre de fourmis ;
- un chemin avec une salle de capacité 1 : effet de pipeline ;
- une salle de capacité 2 ;
- une fourmilière sans chemin jusqu'au dortoir : erreur claire ;
- le respect des capacités et la présence de toutes les fourmis à `Sd` à la fin.

## 13. Sources techniques

- Sujet fourni : **Une vie de fourmi - La Plateforme**.
- NetworkX - Tutorial : https://networkx.org/documentation/stable/tutorial.html
- Adjacency Matrix - Graph Theory Tutorial : https://people.revoledu.com/kardi/tutorial/GraphTheory/Adjacency-Matrix.html

## Conclusion

Le projet ne cherche pas uniquement un chemin : il construit un **planning simultané optimal** pour toute la colonie. La modélisation par graphe temporel permet de respecter les capacités, d'expliquer clairement le raisonnement, de produire toutes les étapes demandées et de garantir le nombre minimal d'étapes.
