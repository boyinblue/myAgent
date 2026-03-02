<#
.SYNOPSIS
Ollama AI Assistant a versatile PowerShell script that allows you to interact with Ollama AI models. 
It supports both direct command-line prompts and file-based inputs, making it ideal for a wide range of tasks from quick questions to detailed content analysis.

.PARAMETER prompt
A string input for direct interaction with the AI model.

.PARAMETER filePath
The path to a text file to be used as input for the AI model.

.EXAMPLE
# 1. To ask a simple question
./ask-assistant.ps1 -prompt "Hello, who are you?"

# 2. To analyze a file
./ask-assistant.ps1 -filePath "C:\path\to\your\document.txt"

.DESCRIPTION
This script facilitates communication with Ollama AI models. 
It can be configured via an external `config.json` file to specify the model to be used. 
If the configuration file does not exist, it will be created with a default model. 
The script is designed for flexibility, accepting both simple string prompts and larger file-based inputs.
#>
param(
    [Parameter(Mandatory=$false)]
    [string]$prompt,

    [Parameter(Mandatory=$false)]
    [string]$filePath
)

# Configuration file path
$configPath = Join-Path $PSScriptRoot "config.json"

# Default configuration
$defaultConfig = @{
    model = "gemma2:9b"
}

# --- Configuration Management ---
# If config.json doesn't exist, create it with default values
if (-not (Test-Path $configPath)) {
    Write-Host "Configuration file not found. Creating a default config.json..."
    $defaultConfig | ConvertTo-Json | Out-File -FilePath $configPath -Encoding utf8
}

# Load configuration from config.json
$config = Get-Content -Path $configPath | ConvertFrom-Json
$model = $config.model

# --- Input Validation ---
# Ensure that either a prompt or a file path is provided
if (-not $prompt -and -not $filePath) {
    Write-Error "Please provide a prompt using -prompt or a file path using -filePath."
    exit 1
}

# --- Prompt Construction ---
$fullPrompt = ""
if ($filePath) {
    if (-not (Test-Path $filePath)) {
        Write-Error "File not found: $filePath"
        exit 1
    }
    $fileContent = Get-Content -Path $filePath -Raw -Encoding UTF8
    $fullPrompt = "Please analyze the following content:`n`n[File Content]:`n$fileContent"
} else {
    $fullPrompt = $prompt
}

# --- Ollama Execution ---
Write-Host "--- Running Ollama with model: $model ---" -ForegroundColor Yellow
$fullPrompt | ollama run $model
