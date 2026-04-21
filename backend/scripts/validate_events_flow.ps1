
param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$Username = "admin",
    [string]$Password = "admin123",
    [string]$UserFullName = "Manual Event Flow User",
    [string]$DeviceCodePrefix = "manual-edge",
    [switch]$SkipHealthCheck = $false
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Green
}

function Write-WarnLine {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Yellow
}

function Invoke-JsonRequest {
    param(
        [string]$Method,
        [string]$Uri,
        [hashtable]$Headers = @{},
        [object]$Body = $null
    )

    $jsonBody = $null
    if ($null -ne $Body) {
        $jsonBody = if ($Body -is [string]) { $Body } else { $Body | ConvertTo-Json -Depth 10 }
    }

    try {
        $requestArgs = @{
            Method = $Method
            Uri = $Uri
            Headers = $Headers
            ContentType = "application/json"
            UseBasicParsing = $true
        }
        if ($null -ne $jsonBody) {
            $requestArgs.Body = $jsonBody
        }
        $response = Invoke-WebRequest @requestArgs

        $parsed = $null
        if ($response.Content) {
            $parsed = $response.Content | ConvertFrom-Json
        }

        return [pscustomobject]@{
            StatusCode = [int]$response.StatusCode
            Content = $response.Content
            Json = $parsed
        }
    }
    catch {
        $webResponse = $_.Exception.Response
        if ($null -eq $webResponse) {
            throw
        }

        $statusCode = [int]$webResponse.StatusCode
        $reader = New-Object System.IO.StreamReader($webResponse.GetResponseStream())
        $content = $reader.ReadToEnd()
        $reader.Close()

        $parsed = $null
        if ($content) {
            try {
                $parsed = $content | ConvertFrom-Json
            }
            catch {
                $parsed = $null
            }
        }

        return [pscustomobject]@{
            StatusCode = $statusCode
            Content = $content
            Json = $parsed
        }
    }
}

function Get-RequiredProperty {
    param(
        [object]$Object,
        [string]$Name,
        [string]$Context
    )

    if ($null -eq $Object) {
        throw "${Context}: respuesta JSON vacia"
    }

    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property -or $null -eq $property.Value -or "$($property.Value)" -eq "") {
        throw "${Context}: falta propiedad requerida '$Name'"
    }

    return $property.Value
}

function Assert-StatusCode {
    param(
        [int]$Actual,
        [int[]]$Expected,
        [string]$Context,
        [string]$Content
    )

    if ($Expected -contains $Actual) {
        return
    }

    throw "${Context}: status code inesperado $Actual. Esperado: $($Expected -join ', '). Respuesta: $Content"
}

$normalizedBaseUrl = $BaseUrl.TrimEnd('/')

if (-not $SkipHealthCheck) {
    Write-Step "[1/9] Verificando health del backend en $normalizedBaseUrl"
    $health = Invoke-JsonRequest -Method "GET" -Uri "$normalizedBaseUrl/health"
    Assert-StatusCode -Actual $health.StatusCode -Expected @(200) -Context "GET /health" -Content $health.Content
    Write-Ok "Backend disponible"
}

Write-Step "[2/9] Login frontend"
$loginResponse = Invoke-JsonRequest -Method "POST" -Uri "$normalizedBaseUrl/auth/login" -Body @{ username = $Username; password = $Password }
Assert-StatusCode -Actual $loginResponse.StatusCode -Expected @(200) -Context "POST /auth/login" -Content $loginResponse.Content

$jwt = Get-RequiredProperty -Object $loginResponse.Json -Name "access_token" -Context "POST /auth/login"
$frontendHeaders = @{ Authorization = "Bearer $jwt" }
Write-Ok "Login correcto"

$suffix = [guid]::NewGuid().ToString("N").Substring(0, 8)
$deviceCode = "$DeviceCodePrefix-$suffix"

Write-Step "[3/9] Creando usuario de prueba"
$userResponse = Invoke-JsonRequest -Method "POST" -Uri "$normalizedBaseUrl/users" -Headers $frontendHeaders -Body @{ full_name = "$UserFullName $suffix"; birth_date = $null; notes = "Manual backend E2E validation" }
Assert-StatusCode -Actual $userResponse.StatusCode -Expected @(201) -Context "POST /users" -Content $userResponse.Content

$userId = [int](Get-RequiredProperty -Object $userResponse.Json -Name "id" -Context "POST /users")
Write-Ok "Usuario creado: id=$userId"

Write-Step "[4/9] Provisionando dispositivo"
$deviceResponse = Invoke-JsonRequest -Method "POST" -Uri "$normalizedBaseUrl/devices" -Headers $frontendHeaders -Body @{
        user_id = $userId
        device_code = $deviceCode
        device_name = "Manual Edge Device $suffix"
        location_name = "Lab"
        is_active = $true
    }
Assert-StatusCode -Actual $deviceResponse.StatusCode -Expected @(201) -Context "POST /devices" -Content $deviceResponse.Content

$deviceToken = Get-RequiredProperty -Object $deviceResponse.Json -Name "device_token" -Context "POST /devices"
$deviceId = [int](Get-RequiredProperty -Object $deviceResponse.Json -Name "id" -Context "POST /devices")
$deviceHeaders = @{ "X-Device-Token" = "$deviceToken" }
Write-Ok "Dispositivo creado: code=$deviceCode id=$deviceId"

$traceNoAlert = [guid]::NewGuid().ToString()
$traceWithAlert = [guid]::NewGuid().ToString()

$eventNoAlert = @{
    schema_version = "1.0"
    trace_id = $traceNoAlert
    device_code = $deviceCode
    event_type = "conversation_anomaly"
    source = "manual-e2e"
    user_text = "Respuesta incoherente detectada"
}

$eventWithAlert = @{
    schema_version = "1.0"
    trace_id = $traceWithAlert
    device_code = $deviceCode
    event_type = "help_request"
    source = "manual-e2e"
    user_text = "Necesito ayuda por favor"
    payload_json = @{
        reason = "manual_validation"
        location = "Lab"
        can_call = $true
    }
}

Write-Step "[5/9] Enviando evento sin side effects esperados"
$eventNoAlertResponse = Invoke-JsonRequest -Method "POST" -Uri "$normalizedBaseUrl/events" -Headers $deviceHeaders -Body $eventNoAlert
Assert-StatusCode -Actual $eventNoAlertResponse.StatusCode -Expected @(201) -Context "POST /events (conversation_anomaly)" -Content $eventNoAlertResponse.Content
Write-Ok "Evento sin alerta persistido"

Write-Step "[6/9] Enviando evento con incidente/alerta esperados"
$eventWithAlertResponse = Invoke-JsonRequest -Method "POST" -Uri "$normalizedBaseUrl/events" -Headers $deviceHeaders -Body $eventWithAlert
Assert-StatusCode -Actual $eventWithAlertResponse.StatusCode -Expected @(201) -Context "POST /events (help_request)" -Content $eventWithAlertResponse.Content
Write-Ok "Evento con side effects persistido"

Write-Step "[7/9] Reenviando el mismo evento para validar idempotencia"
$idempotentResponse = Invoke-JsonRequest -Method "POST" -Uri "$normalizedBaseUrl/events" -Headers $deviceHeaders -Body $eventWithAlert
Assert-StatusCode -Actual $idempotentResponse.StatusCode -Expected @(200) -Context "POST /events idempotente" -Content $idempotentResponse.Content
Write-Ok "Replay idempotente validado"

Write-Step "[8/9] Consultando resultados por API"
$eventsNoAlert = Invoke-JsonRequest -Method "GET" -Uri "$normalizedBaseUrl/events?trace_id=$traceNoAlert" -Headers $frontendHeaders
$eventsWithAlert = Invoke-JsonRequest -Method "GET" -Uri "$normalizedBaseUrl/events?trace_id=$traceWithAlert" -Headers $frontendHeaders
$incidents = Invoke-JsonRequest -Method "GET" -Uri "$normalizedBaseUrl/incidents?user_id=$userId" -Headers $frontendHeaders
$alerts = Invoke-JsonRequest -Method "GET" -Uri "$normalizedBaseUrl/alerts?user_id=$userId" -Headers $frontendHeaders
$overview = Invoke-JsonRequest -Method "GET" -Uri "$normalizedBaseUrl/users/$userId/overview" -Headers $frontendHeaders
$timeline = Invoke-JsonRequest -Method "GET" -Uri "$normalizedBaseUrl/users/$userId/timeline" -Headers $frontendHeaders

Assert-StatusCode -Actual $eventsNoAlert.StatusCode -Expected @(200) -Context "GET /events trace 1" -Content $eventsNoAlert.Content
Assert-StatusCode -Actual $eventsWithAlert.StatusCode -Expected @(200) -Context "GET /events trace 2" -Content $eventsWithAlert.Content
Assert-StatusCode -Actual $incidents.StatusCode -Expected @(200) -Context "GET /incidents" -Content $incidents.Content
Assert-StatusCode -Actual $alerts.StatusCode -Expected @(200) -Context "GET /alerts" -Content $alerts.Content
Assert-StatusCode -Actual $overview.StatusCode -Expected @(200) -Context "GET /users/{id}/overview" -Content $overview.Content
Assert-StatusCode -Actual $timeline.StatusCode -Expected @(200) -Context "GET /users/{id}/timeline" -Content $timeline.Content

$eventsNoAlertTotal = [int](Get-RequiredProperty -Object $eventsNoAlert.Json -Name "total" -Context "GET /events trace 1")
$eventsWithAlertTotal = [int](Get-RequiredProperty -Object $eventsWithAlert.Json -Name "total" -Context "GET /events trace 2")
$incidentsTotal = [int](Get-RequiredProperty -Object $incidents.Json -Name "total" -Context "GET /incidents")
$alertsTotal = [int](Get-RequiredProperty -Object $alerts.Json -Name "total" -Context "GET /alerts")

$overviewCurrentStatus = Get-RequiredProperty -Object $overview.Json -Name "current_status" -Context "GET /users/{id}/overview"
$timelineEventsCount = ($timeline.Json.events | Measure-Object).Count
$timelineIncidentsCount = ($timeline.Json.incidents | Measure-Object).Count
$timelineAlertsCount = ($timeline.Json.alerts | Measure-Object).Count

Write-Step "[9/9] Resumen final"
Write-Host ""
Write-Host "=== RITA Backend Manual Events Flow ===" -ForegroundColor Green
Write-Host ("Base URL:               " + $normalizedBaseUrl)
Write-Host ("User ID:                " + $userId)
Write-Host ("Device ID:              " + $deviceId)
Write-Host ("Device Code:            " + $deviceCode)
Write-Host ("Trace no-alerta:        " + $traceNoAlert)
Write-Host ("Trace con-alerta:       " + $traceWithAlert)
Write-Host ("POST no-alerta status:  " + $eventNoAlertResponse.StatusCode)
Write-Host ("POST con-alerta status: " + $eventWithAlertResponse.StatusCode)
Write-Host ("POST replay status:     " + $idempotentResponse.StatusCode)
Write-Host ("GET /events trace 1:    total=" + $eventsNoAlertTotal)
Write-Host ("GET /events trace 2:    total=" + $eventsWithAlertTotal)
Write-Host ("GET /incidents:         total=" + $incidentsTotal)
Write-Host ("GET /alerts:            total=" + $alertsTotal)
Write-Host ("Overview status:        " + $overviewCurrentStatus)
Write-Host ("Timeline counts:        events=" + $timelineEventsCount + ", incidents=" + $timelineIncidentsCount + ", alerts=" + $timelineAlertsCount)
Write-Host ""

if ($eventNoAlertResponse.StatusCode -eq 201 -and $eventWithAlertResponse.StatusCode -eq 201 -and $idempotentResponse.StatusCode -eq 200) {
    Write-Ok "Validacion E2E manual completada correctamente"
}
else {
    Write-WarnLine "La validacion termino con respuestas no esperadas"
}