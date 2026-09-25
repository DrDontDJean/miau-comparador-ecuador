param([ValidateSet('iniciar','detener','sincronizar','restaurar')][string]$Accion='iniciar', [switch]$SinNavegador)
$ErrorActionPreference='Stop'
$env:PYTHONIOENCODING='utf-8'
Set-Location -LiteralPath $PSScriptRoot
$logFrecuento=Join-Path $PSScriptRoot 'data\logs'
$controlFrecuento=Join-Path $PSScriptRoot 'data\procesos.json'
New-Item -ItemType Directory -Force -Path $logFrecuento | Out-Null
function Es-ProcesoProyecto($numeroFrecuento) {
    $pFrecuento=Get-CimInstance Win32_Process -Filter "ProcessId = $numeroFrecuento" -ErrorAction SilentlyContinue
    return $pFrecuento -and $pFrecuento.CommandLine -and $pFrecuento.CommandLine.Contains($PSScriptRoot)
}
try {
    $procesosFrecuento=@{}
    if(Test-Path -LiteralPath $controlFrecuento){
        $jsonFrecuento=Get-Content -LiteralPath $controlFrecuento -Raw | ConvertFrom-Json
        foreach($propFrecuento in $jsonFrecuento.PSObject.Properties){$procesosFrecuento[$propFrecuento.Name]=$propFrecuento.Value}
    }
    if($Accion -eq 'detener') {
        foreach($nombreFrecuento in @('web','programador')) {
            $numeroFrecuento=$procesosFrecuento[$nombreFrecuento]
            if($numeroFrecuento -and (Es-ProcesoProyecto $numeroFrecuento)){
                # El ejecutable del venv puede iniciar un intérprete hijo real.
                Get-CimInstance Win32_Process -Filter "ParentProcessId = $numeroFrecuento" |
                    Where-Object { $_.CommandLine -and $_.CommandLine.Contains($PSScriptRoot) } |
                    ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
                Stop-Process -Id $numeroFrecuento -ErrorAction SilentlyContinue
            }
        }
        Write-Host 'Web y programador detenidos. MongoDB permanece disponible para Compass.'
        exit 0
    }
    $pythonFrecuento=$null
    foreach($candidatoFrecuento in @((Join-Path $PSScriptRoot '.venv\Scripts\python.exe'))) {
        if(Test-Path -LiteralPath $candidatoFrecuento){$pythonFrecuento=(Resolve-Path -LiteralPath $candidatoFrecuento).Path;break}
    }
    if(-not $pythonFrecuento) {
        $comandoFrecuento=Get-Command python.exe -ErrorAction SilentlyContinue
        if(Get-Command py.exe -ErrorAction SilentlyContinue){$baseFrecuento=& py.exe -3 -c 'import sys; print(sys.executable)'}
        elseif($comandoFrecuento){$baseFrecuento=$comandoFrecuento.Source}
        else {throw 'Instala Python 3.11 o superior desde python.org y vuelve a ejecutar este archivo.'}
        & $baseFrecuento -c 'import sys; assert sys.version_info >= (3,11)'
        if($LASTEXITCODE -ne 0){throw 'Se necesita Python 3.11 o superior.'}
        & $baseFrecuento -m venv (Join-Path $PSScriptRoot '.venv')
        if($LASTEXITCODE -ne 0){throw 'No se pudo crear el entorno Python.'}
        $pythonFrecuento=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    }
    & $pythonFrecuento (Join-Path $PSScriptRoot 'entorno.py') dependencias
    if($LASTEXITCODE -ne 0) {
        & $pythonFrecuento -m pip install -r (Join-Path $PSScriptRoot 'requirements.txt')
        if($LASTEXITCODE -ne 0){throw 'No se pudieron instalar las dependencias.'}
    }
    if(-not(Test-Path -LiteralPath '.env')){Copy-Item -LiteralPath '.env.example' -Destination '.env'}
    & $pythonFrecuento (Join-Path $PSScriptRoot 'entorno.py') mongo
    if($LASTEXITCODE -ne 0) {
        $puertoMongoFrecuento=& $pythonFrecuento (Join-Path $PSScriptRoot 'entorno.py') puerto-mongo
        if($puertoMongoFrecuento -eq 'REMOTO'){throw 'No se pudo conectar a MongoDB remoto. Revisa .env y los permisos de red.'}
        $mongoFrecuento=$null
        foreach($candidatoFrecuento in @((Join-Path $PSScriptRoot 'data\runtime\mongod.exe'))) {
            if(Test-Path -LiteralPath $candidatoFrecuento){$mongoFrecuento=(Resolve-Path -LiteralPath $candidatoFrecuento).Path;break}
        }
        if(-not $mongoFrecuento){$cmdMongoFrecuento=Get-Command mongod.exe -ErrorAction SilentlyContinue;if($cmdMongoFrecuento){$mongoFrecuento=$cmdMongoFrecuento.Source}}
        if(-not $mongoFrecuento){$mongoFrecuento=Get-ChildItem 'C:\Program Files\MongoDB\Server\*\bin\mongod.exe' -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName}
        if(-not $mongoFrecuento){throw 'Instala MongoDB Community Server o coloca mongod.exe en data\runtime. Vuelve a abrir el lanzador.'}
        $dbFrecuento=Join-Path $PSScriptRoot 'data\mongodb'
        New-Item -ItemType Directory -Force -Path $dbFrecuento | Out-Null
        Start-Process -FilePath $mongoFrecuento -ArgumentList @('--dbpath',('"'+$dbFrecuento+'"'),'--bind_ip','127.0.0.1','--port',$puertoMongoFrecuento,'--logpath',('"'+(Join-Path $logFrecuento 'mongodb.log')+'"'),'--logappend') -WindowStyle Hidden | Out-Null
        & $pythonFrecuento (Join-Path $PSScriptRoot 'entorno.py') mongo
        if($LASTEXITCODE -ne 0){throw 'MongoDB no pudo iniciarse. Revisa data\logs\mongodb.log.'}
    }
    $scriptFrecuento=Join-Path $PSScriptRoot 'ejecutar.py'
    if($Accion -eq 'restaurar') {& $pythonFrecuento -u (Join-Path $PSScriptRoot 'transferir_catalogo.py') restaurar;exit $LASTEXITCODE}
    if($Accion -eq 'sincronizar') {& $pythonFrecuento -u $scriptFrecuento sincronizar;exit $LASTEXITCODE}
    foreach($nombreFrecuento in @('web','programador')) {
        $numeroFrecuento=$procesosFrecuento[$nombreFrecuento]
        if(-not($numeroFrecuento -and (Es-ProcesoProyecto $numeroFrecuento))) {
            $procesoFrecuento=Start-Process -FilePath $pythonFrecuento -ArgumentList @('-u',('"'+$scriptFrecuento+'"'),$nombreFrecuento) -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logFrecuento ($nombreFrecuento+'.out.log')) -RedirectStandardError (Join-Path $logFrecuento ($nombreFrecuento+'.err.log'))
            $procesosFrecuento[$nombreFrecuento]=$procesoFrecuento.Id
        }
    }
    $procesosFrecuento | ConvertTo-Json | Set-Content -LiteralPath $controlFrecuento -Encoding UTF8
    $puertoWebFrecuento=& $pythonFrecuento (Join-Path $PSScriptRoot 'entorno.py') puerto-web
    $urlFrecuento="http://127.0.0.1:$puertoWebFrecuento"
    $listaFrecuento=$false
    for($iFrecuento=0;$iFrecuento -lt 15;$iFrecuento++) {
        try {$rFrecuento=Invoke-RestMethod -Uri "$urlFrecuento/salud" -TimeoutSec 2;if($rFrecuento.aplicacion -eq 'frecuento-etapa1'){$listaFrecuento=$true;break}} catch {}
        Start-Sleep -Seconds 1
    }
    if(-not $listaFrecuento){throw 'La web no respondió. Revisa data\logs\web.err.log y el puerto configurado.'}
    if(-not $SinNavegador){Start-Process $urlFrecuento}
    Write-Host "Aplicacion disponible en $urlFrecuento. Actualizacion diaria segun .env."
} catch {Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red;exit 1}
