$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$reportFolder = Join-Path $taskRoot 'submission\final_project_summary'
$docPath = Join-Path $reportFolder 'ResolveGuard_Final_Project_Summary_Report.docx'
$pdfPath = Join-Path $reportFolder 'ResolveGuard_Final_Project_Summary_Report.pdf'
$wordApp = $null
$reportDoc = $null
try {
    $wordApp = New-Object -ComObject Word.Application
    $wordApp.Visible = $false
    $wordApp.DisplayAlerts = 0
    $reportDoc = $wordApp.Documents.Open($docPath, $false, $false)
    $reportDoc.Repaginate()
    $pageCount = $reportDoc.ComputeStatistics(2)
    $headingPages = @()
    foreach ($heading in @('1. Executive Summary', '2. Customer Problem', '3. How Do We Know', '4. Evaluation Results', '5. From AI Mistakes', '6. How This Project', '7. Outcomes, Lessons')) {
        $searchRange = $reportDoc.Content.Duplicate
        if ($searchRange.Find.Execute($heading)) {
            $headingPages += [PSCustomObject]@{ heading = $heading; page = $searchRange.Information(3) }
        }
    }
    $reportDoc.ExportAsFixedFormat($pdfPath, 17)
    $reportDoc.Save()
    $renderResult = [PSCustomObject]@{ renderer = 'Microsoft Word'; docx_pages = $pageCount; heading_pages = $headingPages; pdf_export = 'SUCCESS'; visual_inspection = 'PENDING'; pdf_path = $pdfPath }
    $renderResult | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $reportFolder 'WORD_RENDER.json') -Encoding UTF8
    $renderResult | ConvertTo-Json -Depth 5
} finally {
    if ($null -ne $reportDoc) { $reportDoc.Close(0); [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($reportDoc) }
    if ($null -ne $wordApp) { $wordApp.Quit(); [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($wordApp) }
}
