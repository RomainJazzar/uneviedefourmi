# Génération des livrables

Tous les livrables (images, GIF, statistiques, PowerPoint, PDF, DOCX, ZIP) sont générés par le code du repository :

```bash
python tools/build_all.py
```

GitHub Actions refait exactement la même chaîne à chaque push (tests compris) et publie le résultat comme artefact du workflow « Générer les livrables du projet ».

Contrôle visuel sous Windows avec Microsoft Office : `powershell -File tools/render_office.ps1 docs/Presentation_Une_vie_de_fourmi_Romain_Lisa_Yannis.pptx rendu/` exporte chaque slide en PNG.
