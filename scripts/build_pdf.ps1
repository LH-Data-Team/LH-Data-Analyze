# report.md -> report.pdf (pandoc + puppeteer)
# Run from project root. Files: report.md, report.html, report.pdf

$ErrorActionPreference = "Stop"
$base = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $base

# Get largest .md file (main report) - avoids Korean filename encoding
$mdSrc = Get-ChildItem -Filter "*.md" | Sort-Object Length -Descending | Select-Object -First 1
if (-not $mdSrc) { Write-Host "Error: No .md file found" -ForegroundColor Red; exit 1 }
Copy-Item $mdSrc.FullName -Destination "report_temp.md" -Force

Write-Host "[1/2] Markdown -> HTML (pandoc)..." -ForegroundColor Cyan
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
pandoc report_temp.md -o report_temp.html -s --standalone --mathjax `
  --metadata title="LH" `
  -c assets/report-style.css

$destHtml = Join-Path $base ($mdSrc.BaseName + ".html")
Copy-Item report_temp.html -Destination $destHtml -Force
Remove-Item report_temp.md, report_temp.html -Force

Write-Host "[2/2] HTML -> PDF (Puppeteer)..." -ForegroundColor Cyan
node scripts/html_to_pdf.js $destHtml

$destPdf = $destHtml -replace '\.html$', '.pdf'
Start-Process $destPdf
Write-Host "`nDone - PDF opened" -ForegroundColor Green
