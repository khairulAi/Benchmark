$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback,8787)
try { $listener.Start() } catch { Write-Host 'Port 8787 is unavailable. Close the other server or open http://localhost:8787/.'; exit 1 }
try { Start-Process 'http://localhost:8787/' } catch { Write-Host 'Open http://localhost:8787/ in your browser.' }
Write-Host 'MedDesk: http://localhost:8787/ . Keep this window open. Ctrl+C stops the server.'
$types = @{'.html'='text/html; charset=utf-8';'.js'='text/javascript; charset=utf-8';'.css'='text/css; charset=utf-8';'.aac'='audio/aac';'.mp4'='audio/mp4';'.ogg'='audio/ogg';'.wav'='audio/wav';'.mp3'='audio/mpeg';'.m4a'='audio/mp4';'.webm'='audio/webm'}
try {
 while ($true) {
  $client = $listener.AcceptTcpClient()
  try {
   $client.ReceiveTimeout = 5000
   $network = $client.GetStream()
   $reader = [IO.StreamReader]::new($network)
   $request = $reader.ReadLine()
   if (!$request) { continue }
   while ($reader.ReadLine()) {}
   $parts = $request.Split(' ')
   $relative = [Uri]::UnescapeDataString(($parts[1].Split('?')[0])).TrimStart('/')
   if (!$relative) { $relative = 'index.html' }
   $path = [IO.Path]::GetFullPath((Join-Path $taskRoot $relative))
   $extension = [IO.Path]::GetExtension($path).ToLowerInvariant()
   $status = '200 OK'
   $contentType = 'text/plain'
   if ($parts[0] -notin @('GET','HEAD')) { $status = '405 Method Not Allowed'; $bytes = [Text.Encoding]::UTF8.GetBytes('Method not allowed') }
   elseif (!$path.StartsWith($taskRoot + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { $status = '403 Forbidden'; $bytes = [Text.Encoding]::UTF8.GetBytes('Forbidden') }
   elseif (!(Test-Path -LiteralPath $path -PathType Leaf) -or !$types.ContainsKey($extension)) { $status = '404 Not Found'; $bytes = [Text.Encoding]::UTF8.GetBytes('Not found') }
   else { $bytes = [IO.File]::ReadAllBytes($path); $contentType = $types[$extension] }
   $header = [Text.Encoding]::ASCII.GetBytes("HTTP/1.1 $status`r`nContent-Type: $contentType`r`nContent-Length: $($bytes.Length)`r`nCache-Control: no-cache`r`nConnection: close`r`n`r`n")
   $network.Write($header,0,$header.Length)
   if ($parts[0] -ne 'HEAD') { $network.Write($bytes,0,$bytes.Length) }
  } catch { Write-Host 'A request was interrupted.' } finally { $client.Close() }
 }
} finally { $listener.Stop() }
