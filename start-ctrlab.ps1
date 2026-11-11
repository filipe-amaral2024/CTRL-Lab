[CmdletBinding()]
param(
    [string]$RaspberryHost = "192.168.15.75",
    [string]$RaspberryUser = "ctrl-lab",
    [int]$CameraDevice = 0,
    [int]$DashboardPort = 8000,
    [int]$MqttTunnelPort = 1884,
    [int]$CameraTunnelPort = 8081,
    [string]$AccessModel = "",
    [string]$AccessClasses = "person,lab_coat"
)

$ErrorActionPreference = "Stop"
$repositoryRoot = $PSScriptRoot

function Stop-WithMessage {
    param([string]$Message)
    throw $Message
}

function Invoke-CheckedCommand {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$FailureMessage
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        Stop-WithMessage "$FailureMessage (exit code $LASTEXITCODE)."
    }
}

function New-RandomToken {
    $bytes = New-Object byte[] 24
    $random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $random.GetBytes($bytes)
    }
    finally {
        $random.Dispose()
    }
    return ([BitConverter]::ToString($bytes)).Replace("-", "").ToLowerInvariant()
}

function ConvertTo-EncodedPowerShell {
    param([string]$ScriptText)
    return [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($ScriptText))
}

function Invoke-RemoteBash {
    param(
        [string]$SshPath,
        [string[]]$SshArguments,
        [string]$Target,
        [string]$ScriptText,
        [switch]$AllocateTty,
        [string]$FailureMessage
    )

    $ScriptText = $ScriptText.Replace("`r`n", "`n").Replace("`r", "`n")
    $encodedScript = [Convert]::ToBase64String(
        [Text.Encoding]::UTF8.GetBytes($ScriptText)
    )
    $remoteCommand = "printf '%s' '$encodedScript' | base64 -d | bash"
    $sshOptions = @()
    if ($AllocateTty) {
        $sshOptions += "-t"
    }
    Invoke-CheckedCommand `
        -FilePath $SshPath `
        -Arguments (@($sshOptions) + @($SshArguments) + @($Target, $remoteCommand)) `
        -FailureMessage $FailureMessage
}

function Test-TcpPortInUse {
    param([int]$Port)
    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $Port)
    try {
        $listener.Start()
        return $false
    }
    catch [Net.Sockets.SocketException] {
        return $true
    }
    finally {
        $listener.Stop()
    }
}

function Test-TcpConnection {
    param(
        [string]$HostName,
        [int]$Port,
        [int]$TimeoutMilliseconds = 3000
    )

    $client = [Net.Sockets.TcpClient]::new()
    try {
        $connection = $client.BeginConnect($HostName, $Port, $null, $null)
        if (-not $connection.AsyncWaitHandle.WaitOne($TimeoutMilliseconds)) {
            return $false
        }
        $client.EndConnect($connection)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Close()
    }
}

function Start-PowerShellWindow {
    param([string]$ScriptText)

    $encoded = ConvertTo-EncodedPowerShell -ScriptText $ScriptText
    $powerShellExecutable = if ($PSVersionTable.PSEdition -eq "Core") {
        Join-Path $PSHOME "pwsh.exe"
    }
    else {
        Join-Path $PSHOME "powershell.exe"
    }
    Start-Process `
        -FilePath $powerShellExecutable `
        -ArgumentList @("-NoExit", "-EncodedCommand", $encoded) `
        -PassThru
}

if ($RaspberryHost -notmatch '^[A-Za-z0-9.-]+$') {
    Stop-WithMessage "Host invalido. Use um IP ou hostname simples. Exemplo: raspberrypi.local"
}
if ($RaspberryUser -notmatch '^[A-Za-z0-9._-]+$') {
    Stop-WithMessage "Usuario SSH invalido."
}
if ($CameraDevice -lt 0) {
    Stop-WithMessage "CameraDevice deve ser zero ou maior."
}
foreach ($port in @($DashboardPort, $MqttTunnelPort, $CameraTunnelPort)) {
    if ($port -lt 1 -or $port -gt 65535) {
        Stop-WithMessage "As portas devem estar entre 1 e 65535."
    }
}
if ($AccessModel) {
    if (-not (Test-Path -LiteralPath $AccessModel -PathType Leaf)) {
        Stop-WithMessage "Arquivo do modelo de acesso nao encontrado: $AccessModel"
    }
    if ([IO.Path]::GetExtension($AccessModel) -ne ".onnx") {
        Stop-WithMessage "O modelo de acesso deve estar no formato ONNX."
    }
    $AccessModel = (Resolve-Path -LiteralPath $AccessModel).Path
}
if ($AccessClasses -notmatch '^[A-Za-z0-9_,]+$') {
    Stop-WithMessage "AccessClasses deve conter apenas nomes de classe separados por virgula."
}
$accessClassList = @(
    $AccessClasses.Split(',') |
        ForEach-Object { $_.Trim().ToLowerInvariant() }
)
$hasSeparateEquipmentClasses = (
    $accessClassList -contains "person" -and
    $accessClassList -contains "lab_coat"
)
$hasPersonStatusClasses = (
    $accessClassList -contains "person_with_labcoat" -and
    $accessClassList -contains "person_without_labcoat"
)
if (-not $hasSeparateEquipmentClasses -and -not $hasPersonStatusClasses) {
    Stop-WithMessage (
        "AccessClasses deve incluir person,lab_coat ou " +
        "person_with_labcoat,person_without_labcoat."
    )
}

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCommand) {
    Stop-WithMessage "Python nao foi encontrado no PATH do Windows."
}
$localVenvPython = Join-Path $repositoryRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $localVenvPython)) {
    Invoke-CheckedCommand `
        -FilePath $pythonCommand.Source `
        -Arguments @("-m", "venv", (Join-Path $repositoryRoot ".venv")) `
        -FailureMessage "Falha ao criar o ambiente virtual local"
}
$sshCommand = Get-Command ssh.exe -ErrorAction SilentlyContinue
$scpCommand = Get-Command scp.exe -ErrorAction SilentlyContinue
if (-not $sshCommand -or -not $scpCommand) {
    Stop-WithMessage "OpenSSH Client (ssh.exe e scp.exe) nao foi encontrado no Windows."
}
$keygenCommand = Get-Command ssh-keygen.exe -ErrorAction SilentlyContinue
if (-not $keygenCommand) {
    Stop-WithMessage "ssh-keygen.exe nao foi encontrado. Instale o recurso OpenSSH Client do Windows."
}

foreach ($port in @($DashboardPort, $MqttTunnelPort, $CameraTunnelPort)) {
    if (Test-TcpPortInUse -Port $port) {
        Stop-WithMessage "A porta local $port ja esta em uso. Feche o servico correspondente ou escolha outra porta."
    }
}

$target = "$RaspberryUser@$RaspberryHost"
if (-not (Test-TcpConnection -HostName $RaspberryHost -Port 22)) {
    Stop-WithMessage (
        "Nao foi possivel conectar a $RaspberryHost na porta SSH 22. " +
        "Isso e um problema de rede/IP, nao da chave SSH. Confirme se o Pi esta ligado " +
        "na mesma rede, encontre o IPv4 atual na lista DHCP do roteador e teste com " +
        "Test-NetConnection <IP-ATUAL> -Port 22. Depois rode " +
        ".\start-ctrlab.ps1 -RaspberryHost <IP-ATUAL>."
    )
}
$cameraToken = New-RandomToken
$controlToken = New-RandomToken
$tunnelProcess = $null
$dashboardProcess = $null
$sshDirectory = Join-Path $env:USERPROFILE ".ssh"
$sshPrivateKey = Join-Path $sshDirectory "ctrlab_pi_ed25519"
$sshPublicKey = "$sshPrivateKey.pub"
if (-not (Test-Path $sshDirectory)) {
    New-Item -ItemType Directory -Path $sshDirectory | Out-Null
}
if (-not (Test-Path $sshPrivateKey)) {
    Write-Host "Criando chave SSH local sem senha de chave. Proteja sua conta do Windows."
    Invoke-CheckedCommand `
        -FilePath $keygenCommand.Source `
        -Arguments @("-t", "ed25519", "-N", '""', "-f", $sshPrivateKey, "-C", "ctrlab-raspberry") `
        -FailureMessage "Falha ao criar uma chave SSH"
}
$sshAuthArguments = @("-i", $sshPrivateKey, "-o", "IdentitiesOnly=yes")

Write-Host "Instalando/verificando dependencias Python no PC..."
Invoke-CheckedCommand `
    -FilePath $localVenvPython `
    -Arguments @("-m", "pip", "install", "-r", (Join-Path $repositoryRoot "requirements.txt")) `
    -FailureMessage "Falha ao instalar dependencias Python no PC"

Write-Host "Configurando autenticacao SSH para $target..."
$keyAuthenticationWorks = $false
& $sshCommand.Source @($sshAuthArguments) -o BatchMode=yes $target "true"
if ($LASTEXITCODE -eq 0) {
    $keyAuthenticationWorks = $true
}
else {
    $publicKey = (Get-Content -Path $sshPublicKey -Raw).Trim()
    $publicKeyBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($publicKey))
    $installKeyScript = @'
set -euo pipefail
umask 077
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"
touch "$HOME/.ssh/authorized_keys"
key_file=$(mktemp)
trap 'rm -f "$key_file"' EXIT
printf '%s' '__PUBLIC_KEY_BASE64__' | base64 -d > "$key_file"
if ! grep -qxFf "$key_file" "$HOME/.ssh/authorized_keys"; then
    cat "$key_file" >> "$HOME/.ssh/authorized_keys"
fi
chmod 600 "$HOME/.ssh/authorized_keys"
'@
    $installKeyScript = $installKeyScript.Replace(
        "__PUBLIC_KEY_BASE64__",
        $publicKeyBase64
    )
    Write-Host "A proxima conexao solicitara a senha SSH uma vez para instalar a chave publica."
    Invoke-RemoteBash `
        -SshPath $sshCommand.Source `
        -SshArguments @() `
        -Target $target `
        -ScriptText $installKeyScript `
        -AllocateTty `
        -FailureMessage "Nao foi possivel instalar a chave SSH no Raspberry Pi"
    & $sshCommand.Source @($sshAuthArguments) -o BatchMode=yes $target "true"
    if ($LASTEXITCODE -ne 0) {
        Stop-WithMessage "A chave SSH foi instalada, mas a autenticacao por chave ainda falhou."
    }
    $keyAuthenticationWorks = $true
}
if (-not $keyAuthenticationWorks) {
    Stop-WithMessage "Nao foi possivel configurar a autenticacao SSH."
}

$raspberryAddresses = & $sshCommand.Source @($sshAuthArguments) $target "hostname -I"
if ($LASTEXITCODE -ne 0) {
    Stop-WithMessage "Conectei por SSH, mas nao consegui obter o IP do Raspberry Pi."
}
$raspberryIp = @(
    "$raspberryAddresses" -split '\s+' |
        Where-Object { $_ -match '^\d{1,3}(\.\d{1,3}){3}$' }
) | Select-Object -First 1
if (-not $raspberryIp) {
    Write-Warning "O Pi nao retornou um IPv4 via hostname -I; continuarei usando $RaspberryHost."
}
else {
    Write-Host "Raspberry Pi identificado: usuario $RaspberryUser, host $RaspberryHost, IP $raspberryIp"
}

Write-Host "Sincronizando os modulos necessarios para o Raspberry Pi..."
Invoke-CheckedCommand `
    -FilePath $sshCommand.Source `
    -Arguments (@($sshAuthArguments) + @($target, "mkdir -p ~/CTRL-Lab")) `
    -FailureMessage "Nao foi possivel criar ~/CTRL-Lab no Raspberry Pi"

$sourcePaths = @("app", "central", "raspberry_pi", "requirements.txt") |
    ForEach-Object { Join-Path $repositoryRoot $_ }
$scpArguments = @("-r") + $sourcePaths + @("${target}:~/CTRL-Lab/")
$scpArguments = @($sshAuthArguments) + $scpArguments
Invoke-CheckedCommand `
    -FilePath $scpCommand.Source `
    -Arguments $scpArguments `
    -FailureMessage "Falha ao copiar os modulos do projeto para o Raspberry Pi"
if ($AccessModel) {
    Invoke-CheckedCommand `
        -FilePath $sshCommand.Source `
        -Arguments (@($sshAuthArguments) + @($target, "mkdir -p ~/CTRL-Lab/models")) `
        -FailureMessage "Nao foi possivel preparar o diretorio do modelo no Raspberry Pi"
    Invoke-CheckedCommand `
        -FilePath $scpCommand.Source `
        -Arguments (@($sshAuthArguments) + @($AccessModel, "${target}:~/CTRL-Lab/models/ctrlab-access.onnx")) `
        -FailureMessage "Falha ao copiar o modelo de acesso para o Raspberry Pi"
}

$setupScript = @'
set -euo pipefail
cd "$HOME/CTRL-Lab"

case "$(. /etc/os-release; printf '%s' "${VERSION_CODENAME:-}")" in
    bookworm|trixie) gpio_package=python3-rpi-lgpio ;;
    *) gpio_package=python3-rpi.gpio ;;
esac
packages=(python3-venv python3-pip "$gpio_package" mosquitto mosquitto-clients libgpiod-dev)
missing=()
for package in "${packages[@]}"; do
    if ! dpkg-query -W -f='${db:Status-Status}' "$package" 2>/dev/null | grep -qx installed; then
        missing+=("$package")
    fi
done
if ((${#missing[@]})); then
    sudo apt-get update
    sudo apt-get install -y "${missing[@]}"
fi

sudo systemctl enable --now mosquitto
if [[ ! -x .venv/bin/python ]]; then
    python3 -m venv --system-site-packages .venv
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install adafruit-circuitpython-dht
.venv/bin/python -m pip install 'gpiod>=2.2.2,<3'
.venv/bin/python -c 'import site; from pathlib import Path; Path(site.getsitepackages()[0], "ctrlab_system_gpio.pth").write_text("/usr/lib/python3/dist-packages\n")'

if ! .venv/bin/python -c 'import paho.mqtt.client, cv2, adafruit_dht, board, gpiod, RPi.GPIO'; then
    echo "Uma ou mais dependencias Python do Raspberry Pi nao puderam ser importadas." >&2
    echo "Verifique python3-rpi-lgpio no sistema, o caminho dist-packages no venv e gpiod." >&2
    exit 1
fi
echo "Dependencias e Mosquitto prontos."
'@
Write-Host "Verificando dependencias no Raspberry Pi (sudo podera pedir sua senha)..."
Invoke-RemoteBash `
    -SshPath $sshCommand.Source `
    -SshArguments $sshAuthArguments `
    -Target $target `
    -ScriptText $setupScript `
    -AllocateTty `
    -FailureMessage "Falha ao preparar dependencias no Raspberry Pi"

$runtimeScript = @'
set -euo pipefail
cd "$HOME/CTRL-Lab"
runtime_pid_file="$HOME/CTRL-Lab/ctrlab_runtime.pid"

stop_ctrlab_runtime() {
    local pid="$1"
    local cwd=""
    local state=""
    local matched_module="false"
    local -a command=()

    if [[ ! "$pid" =~ ^[0-9]+$ ]] || [[ ! -r "/proc/$pid/stat" ]]; then
        return 0
    fi

    state=$(awk '{print $3}' "/proc/$pid/stat" 2>/dev/null || true)
    if [[ "$state" == "Z" ]]; then
        return 0
    fi

    cwd=$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)
    mapfile -d '' -t command < "/proc/$pid/cmdline"
    if [[ "$cwd" == "$HOME/CTRL-Lab" ]] &&
        [[ "${command[0]:-}" == ".venv/bin/python" ||
            "${command[0]:-}" == "$HOME/CTRL-Lab/.venv/bin/python" ]]; then
        for ((index = 0; index + 1 < ${#command[@]}; index++)); do
            if [[ "${command[index]}" == "-m" &&
                "${command[index + 1]}" == "raspberry_pi.main" ]]; then
                matched_module="true"
                break
            fi
        done
    fi

    if [[ "$matched_module" != "true" ]]; then
        echo "PID $pid nao corresponde ao runtime deste projeto; nao sera encerrado." >&2
        return 2
    fi

    echo "Encerrando runtime anterior do CTRL-Lab (PID $pid)..."
    kill -TERM "$pid"
    for _ in {1..10}; do
        if [[ ! -r "/proc/$pid/stat" ]]; then
            return 0
        fi
        state=$(awk '{print $3}' "/proc/$pid/stat" 2>/dev/null || true)
        if [[ "$state" == "Z" ]]; then
            return 0
        fi
        sleep 1
    done

    echo "O runtime PID $pid nao encerrou graciosamente em 10 segundos." >&2
    return 1
}

if [[ -f "$runtime_pid_file" ]]; then
    previous_pid=$(cat "$runtime_pid_file")
    if [[ "$previous_pid" =~ ^[0-9]+$ ]] && kill -0 "$previous_pid" 2>/dev/null; then
        stop_ctrlab_runtime "$previous_pid"
    fi
    rm -f "$runtime_pid_file"
fi

while read -r existing_pid; do
    [[ -n "$existing_pid" ]] || continue
    existing_cmdline=$(tr '\0' ' ' < "/proc/$existing_pid/cmdline" 2>/dev/null || true)
    if [[ "$existing_cmdline" == *"$HOME/CTRL-Lab/.venv/bin/python"*"-m raspberry_pi.main"* ]]; then
        stop_ctrlab_runtime "$existing_pid"
    fi
done < <(pgrep -f '[p]ython.*-m raspberry_pi.main' || true)

export CTRL_LAB_CAMERA_TOKEN="__CAMERA_TOKEN__"
runtime_args=(
    --broker localhost
    --camera-device __CAMERA_DEVICE__
    --camera-stream-token "$CTRL_LAB_CAMERA_TOKEN"
    --camera-stream-host 127.0.0.1
)
if [[ "__ACCESS_MODEL_ENABLED__" == "true" ]]; then
    runtime_args+=(
        --access-model models/ctrlab-access.onnx
        --access-classes "__ACCESS_CLASSES__"
    )
fi
nohup .venv/bin/python -m raspberry_pi.main "${runtime_args[@]}" \
    > ctrlab_runtime.log 2>&1 < /dev/null &
runtime_pid=$!
sleep 4
if ! kill -0 "$runtime_pid" 2>/dev/null; then
    echo "O runtime encerrou durante a inicializacao. Ultimos logs:" >&2
    tail -n 50 ctrlab_runtime.log >&2
    exit 1
fi
if ps -o stat= -p "$runtime_pid" | grep -q '^Z'; then
    echo "O runtime encerrou durante a inicializacao. Ultimos logs:" >&2
    tail -n 50 ctrlab_runtime.log >&2
    exit 1
fi
echo "Runtime iniciado no Raspberry Pi (PID $runtime_pid)."
echo "$runtime_pid" > "$runtime_pid_file"
tail -n 8 ctrlab_runtime.log
'@
$runtimeScript = $runtimeScript.Replace("__CAMERA_TOKEN__", $cameraToken)
$runtimeScript = $runtimeScript.Replace("__CAMERA_DEVICE__", [string]$CameraDevice)
$accessModelEnabled = if ($AccessModel) { "true" } else { "false" }
$runtimeScript = $runtimeScript.Replace(
    "__ACCESS_MODEL_ENABLED__",
    $accessModelEnabled
)
$runtimeScript = $runtimeScript.Replace("__ACCESS_CLASSES__", $AccessClasses)
if ($AccessModel) {
    Write-Host "Iniciando sensores e inferencia de pessoa/jaleco no Raspberry Pi..."
}
else {
    Write-Host "Iniciando sensores e pre-visualizacao sem IA no Raspberry Pi..."
}
Invoke-RemoteBash `
    -SshPath $sshCommand.Source `
    -SshArguments $sshAuthArguments `
    -Target $target `
    -ScriptText $runtimeScript `
    -FailureMessage "Falha ao iniciar o runtime no Raspberry Pi"

$tunnelScript = @"
`$ErrorActionPreference = 'Continue'
Write-Host 'Tunel SSH ativo. Mantenha esta janela aberta.'
`$sshArguments = @(
    '-i', '$sshPrivateKey',
    '-o', 'IdentitiesOnly=yes',
    '-o', 'ExitOnForwardFailure=yes',
    '-N',
    '-L', '$($MqttTunnelPort):127.0.0.1:1883',
    '-L', '$($CameraTunnelPort):127.0.0.1:8081',
    '$target'
)
& '$($sshCommand.Source)' @sshArguments
if (`$LASTEXITCODE -ne 0) {
    Write-Host 'O tunel SSH terminou com erro. Confira as portas e a conexao.'
    Read-Host 'Pressione Enter para fechar esta janela'
}
"@
$tunnelProcess = Start-PowerShellWindow -ScriptText $tunnelScript

$tunnelReady = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Seconds 1
    if ((Test-TcpPortInUse -Port $MqttTunnelPort) -and
            (Test-TcpPortInUse -Port $CameraTunnelPort)) {
        $tunnelReady = $true
        break
    }
    if ($tunnelProcess.HasExited) {
        Stop-WithMessage "O processo do tunel SSH encerrou antes de abrir as portas. Confira a janela do tunel."
    }
}
if (-not $tunnelReady) {
    Stop-WithMessage "O tunel SSH nao abriu as portas locais. Confira a janela do tunel e a autenticacao SSH."
}

$cameraReady = $false
$cameraDeadline = [DateTime]::UtcNow.AddSeconds(60)
$cameraLastError = $null
Write-Host "Aguardando a camera e a primeira inferencia do modelo..."
while (-not $cameraReady -and [DateTime]::UtcNow -lt $cameraDeadline) {
    $cameraResponse = $null
    try {
        $cameraRequest = [Net.HttpWebRequest]::Create(
            "http://127.0.0.1:$CameraTunnelPort/video.mjpg"
        )
        $cameraRequest.Method = "GET"
        $cameraRequest.Timeout = 3000
        $cameraRequest.ReadWriteTimeout = 3000
        $cameraRequest.Headers.Add("X-CTRL-Lab-Token", $cameraToken)
        $cameraResponse = $cameraRequest.GetResponse()
        $cameraReady = [int]$cameraResponse.StatusCode -eq 200
        if (-not $cameraReady) {
            $cameraLastError = "HTTP $([int]$cameraResponse.StatusCode)"
        }
    }
    catch [Net.WebException] {
        $cameraResponse = $_.Exception.Response
        if ($cameraResponse -and [int]$cameraResponse.StatusCode -ne 503) {
            $cameraLastError = "HTTP $([int]$cameraResponse.StatusCode)"
            $cameraDeadline = [DateTime]::UtcNow
        }
        elseif (-not $cameraResponse) {
            $cameraLastError = $_.Exception.Message
        }
    }
    finally {
        if ($cameraResponse) {
            $cameraResponse.Close()
        }
    }

    if (-not $cameraReady -and [DateTime]::UtcNow -lt $cameraDeadline) {
        Start-Sleep -Milliseconds 500
    }
}

if (-not $cameraReady) {
    Invoke-RemoteBash `
        -SshPath $sshCommand.Source `
        -SshArguments $sshAuthArguments `
        -Target $target `
        -ScriptText 'cd "$HOME/CTRL-Lab" && tail -n 30 ctrlab_runtime.log' `
        -FailureMessage "Falha ao consultar os logs do runtime"
    if ($cameraLastError) {
        Stop-WithMessage "A pre-visualizacao da camera nao ficou pronta em 60 segundos. Ultimo erro: $cameraLastError"
    }
    Stop-WithMessage "A pre-visualizacao da camera nao ficou pronta em 60 segundos. Confira a camera USB, o indice configurado e os logs acima."
}

$dashboardScript = @"
Set-Location '$repositoryRoot'
Write-Host 'Dashboard CTRL-Lab. Interrompa com Ctrl+C para encerrar.'
`$dashboardArguments = @(
    '-m', 'central.dashboard',
    '--host', '127.0.0.1',
    '--port', '$DashboardPort',
    '--broker', '127.0.0.1',
    '--mqtt-port', '$MqttTunnelPort',
    '--control-token', '$controlToken',
    '--camera-stream-token', '$cameraToken',
    '--camera-stream-url', 'http://127.0.0.1:$CameraTunnelPort/video.mjpg'
)
& '$localVenvPython' @dashboardArguments
if (`$LASTEXITCODE -ne 0) {
    Write-Host 'O dashboard terminou com erro.'
    Read-Host 'Pressione Enter para fechar esta janela'
}
"@
$dashboardProcess = Start-PowerShellWindow -ScriptText $dashboardScript

$dashboardUrl = "http://127.0.0.1:$DashboardPort"
$dashboardReady = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Seconds 1
    try {
        $state = Invoke-RestMethod -Uri "$dashboardUrl/api/state" -TimeoutSec 2
        if ($state.mqtt_connected -and $state.status) {
            $dashboardReady = $true
            break
        }
    }
    catch {
        if ($dashboardProcess.HasExited) {
            Stop-WithMessage "O processo do dashboard encerrou durante a inicializacao."
        }
    }
}

Start-Process $dashboardUrl
Write-Host ""
if ($dashboardReady) {
    Write-Host "Dashboard conectado ao MQTT e aberto em $dashboardUrl"
}
else {
    Write-Warning "Dashboard aberto, mas ainda nao recebeu status MQTT. Confira as janelas do runtime e do tunel SSH."
}
if ($dashboardReady -and
        ($null -eq $state.status.temperature_c -or
        $null -eq $state.status.humidity_pct)) {
    Write-Warning "Dashboard conectado, mas o DHT22 nao forneceu valores validos. Confira fiacao, pull-up e logs no Pi."
}
Write-Host "Token de controle para informar no dashboard: $controlToken"
Write-Host "Token de camera gerado para esta execucao; ele foi configurado automaticamente no Pi e no dashboard."
Write-Host ""
if ($AccessModel) {
    Write-Host "Modo iniciado: inferencia de pessoa/jaleco; deteccao visual de fogo/fumaca nao configurada."
    Write-Host "Sensores fisicos configurados no runtime continuam ativos."
}
else {
    Write-Host "Modo iniciado: pre-visualizacao sem IA (nao detecta fogo, fumaca ou EPI)."
}
Write-Host "Log do runtime no Pi: ~/CTRL-Lab/ctrlab_runtime.log"
Write-Host "Para parar o runtime no Pi: ssh $target 'kill `$(cat ~/CTRL-Lab/ctrlab_runtime.pid)'"
Write-Host "Feche as janelas do dashboard e do tunel SSH quando terminar."
