[CmdletBinding()]
param(
    [string]$EthernetInterfaceAlias = "Ethernet",
    [string]$RaspberryHost = "192.168.50.2",
    [string]$RaspberryUser = "ctrl-lab",
    [int]$CameraDevice = 0,
    [int]$DashboardPort = 8000,
    [int]$MqttTunnelPort = 1884,
    [int]$CameraTunnelPort = 8081,
    [string]$AccessModel = "",
    [string]$AccessClasses = "person_with_labcoat,person_without_labcoat"
)

$ErrorActionPreference = "Stop"

function Stop-WithMessage {
    param([string]$Message)
    throw $Message
}

$parsedRaspberryAddress = $null
if (
    -not [Net.IPAddress]::TryParse($RaspberryHost, [ref]$parsedRaspberryAddress) -or
    $parsedRaspberryAddress.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork
) {
    Stop-WithMessage "RaspberryHost deve ser um endereco IPv4 literal, sem depender de DNS."
}

$adapter = Get-NetAdapter -Name $EthernetInterfaceAlias -ErrorAction SilentlyContinue
if (-not $adapter) {
    $availableAdapters = Get-NetAdapter |
        ForEach-Object { "  $($_.Name) [$($_.Status)]" }
    Stop-WithMessage (
        "Interface Ethernet '$EthernetInterfaceAlias' nao encontrada. " +
        "Interfaces disponiveis:`n$($availableAdapters -join "`n")"
    )
}
if ($adapter.Status -ne "Up") {
    Stop-WithMessage (
        "A interface '$EthernetInterfaceAlias' nao esta conectada. " +
        "Conecte o cabo RJ45 ao Raspberry Pi e tente novamente."
    )
}

$expectedAddress = "192.168.50.1"
$address = Get-NetIPAddress `
    -InterfaceIndex $adapter.ifIndex `
    -AddressFamily IPv4 `
    -ErrorAction SilentlyContinue |
    Where-Object {
        $_.IPAddress -eq $expectedAddress -and $_.PrefixLength -eq 24
    } |
    Select-Object -First 1
if (-not $address) {
    Stop-WithMessage (
        "Configure '$EthernetInterfaceAlias' com IPv4 $expectedAddress/24, " +
        "sem gateway e sem DNS. Este script nao altera configuracoes de rede."
    )
}

$defaultRoute = Get-NetRoute `
    -InterfaceIndex $adapter.ifIndex `
    -DestinationPrefix "0.0.0.0/0" `
    -ErrorAction SilentlyContinue |
    Select-Object -First 1
if ($defaultRoute) {
    Stop-WithMessage (
        "A interface '$EthernetInterfaceAlias' possui uma rota padrao " +
        "($($defaultRoute.NextHop)). Remova o gateway dessa interface para " +
        "garantir que o cabo direto nao altere a rota da Internet."
    )
}

$route = Find-NetRoute -RemoteIPAddress $RaspberryHost -ErrorAction SilentlyContinue |
    Where-Object { $_.InterfaceIndex -eq $adapter.ifIndex } |
    Select-Object -First 1
if (-not $route) {
    Stop-WithMessage (
        "Nao existe rota local de '$EthernetInterfaceAlias' para $RaspberryHost. " +
        "Configure o Raspberry como 192.168.50.2/24, sem gateway."
    )
}

if (-not (Test-NetConnection `
        -ComputerName $RaspberryHost `
        -Port 22 `
        -InformationLevel Quiet `
        -WarningAction SilentlyContinue)) {
    Stop-WithMessage (
        "SSH nao responde em ${RaspberryHost}:22. Confira o IP estatico do Pi, " +
        "o cabo e se o servico SSH esta ativo."
    )
}

$repositoryRoot = $PSScriptRoot
$launcher = Join-Path $repositoryRoot "start-ctrlab.ps1"
if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) {
    Stop-WithMessage "Inicializador principal nao encontrado: $launcher"
}

$launcherArguments = @{
    RaspberryHost = $RaspberryHost
    RaspberryUser = $RaspberryUser
    CameraDevice = $CameraDevice
    DashboardPort = $DashboardPort
    MqttTunnelPort = $MqttTunnelPort
    CameraTunnelPort = $CameraTunnelPort
    AccessClasses = $AccessClasses
}
if ($AccessModel) {
    $launcherArguments.AccessModel = $AccessModel
}

Write-Host (
    "Usando Ethernet '$EthernetInterfaceAlias' ($expectedAddress/24) " +
    "para acessar o Raspberry em $RaspberryHost. Gateway e DNS nao foram alterados."
)
Push-Location $repositoryRoot
try {
    & $launcher @launcherArguments
}
finally {
    Pop-Location
}
