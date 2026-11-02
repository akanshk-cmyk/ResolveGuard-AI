$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[void][Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
[void][Windows.Data.Pdf.PdfDocument, Windows.Data.Pdf, ContentType=WindowsRuntime]
[void][Windows.Storage.Streams.InMemoryRandomAccessStream, Windows.Storage.Streams, ContentType=WindowsRuntime]
$genericAwait = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } | Select-Object -First 1
$actionAwait = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and -not $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction' } | Select-Object -First 1
function Wait-Operation($Operation, $ResultType) {
    $task = $genericAwait.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    $task.Wait()
    return $task.Result
}
$root = Split-Path -Parent $PSScriptRoot
$folder = Join-Path $root 'submission\final_project_summary'
$pdfPath = Join-Path $folder 'ResolveGuard_Final_Project_Summary_Report.pdf'
$file = Wait-Operation ([Windows.Storage.StorageFile]::GetFileFromPathAsync($pdfPath)) ([Windows.Storage.StorageFile])
$pdf = Wait-Operation ([Windows.Data.Pdf.PdfDocument]::LoadFromFileAsync($file)) ([Windows.Data.Pdf.PdfDocument])
$preview = Join-Path $folder 'rendered_pages'
[void][System.IO.Directory]::CreateDirectory($preview)
for ($i=0; $i -lt $pdf.PageCount; $i++) {
    $page = $pdf.GetPage($i)
    $stream = New-Object Windows.Storage.Streams.InMemoryRandomAccessStream
    $options = New-Object Windows.Data.Pdf.PdfPageRenderOptions
    $options.DestinationWidth = 1200
    $actionTask = $actionAwait.Invoke($null, @($page.RenderToStreamAsync($stream, $options)))
    $actionTask.Wait()
    $stream.Seek(0)
    $reader = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($stream)
    $output = [System.IO.File]::Create((Join-Path $preview ('page-{0:D2}.png' -f ($i+1))))
    $reader.CopyTo($output)
    $output.Dispose()
    $reader.Dispose()
    $page.Dispose()
}
[PSCustomObject]@{ pdf_pages=$pdf.PageCount; preview_folder=$preview; renderer='Windows.Data.Pdf' } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $folder 'PDF_RENDER.json') -Encoding UTF8
Write-Output ('Rendered PDF pages: ' + $pdf.PageCount)
