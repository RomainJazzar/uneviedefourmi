# Rendu de contrôle visuel (Windows + Microsoft Office installé) :
#   powershell -File tools/render_office.ps1 <fichier.pptx|.docx> <dossier_sortie>
# .pptx -> une image PNG par slide ; .docx -> PDF (via Word) puis contrôle séparé.
param([string]$InputPath, [string]$OutDir)
$InputPath = (Resolve-Path $InputPath).Path
New-Item -ItemType Directory -Force $OutDir | Out-Null
$OutDir = (Resolve-Path $OutDir).Path
if ($InputPath -like "*.pptx") {
    $app = New-Object -ComObject PowerPoint.Application
    $pres = $app.Presentations.Open($InputPath, $true, $false, $false)
    $i = 1
    foreach ($slide in $pres.Slides) {
        $slide.Export((Join-Path $OutDir ("slide-{0:D2}.png" -f $i)), "PNG", 1600, 900)
        $i++
    }
    $pres.Close(); $app.Quit()
} elseif ($InputPath -like "*.docx") {
    $word = New-Object -ComObject Word.Application
    $doc = $word.Documents.Open($InputPath, $false, $true)
    [string]$pdf = [IO.Path]::Combine($OutDir, [IO.Path]::GetFileNameWithoutExtension($InputPath) + ".pdf")
    $doc.ExportAsFixedFormat($pdf, 17)
    $doc.Close([ref]0); $word.Quit()
}
