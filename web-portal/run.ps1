# A360 Portal Launch Script
# This script sets up and runs the Streamlit web portal for B360 project management

param(
    [Parameter(Mandatory=$false)]
    [switch]$Install,
    
    [Parameter(Mandatory=$false)]
    [switch]$Dev,
    
    [Parameter(Mandatory=$false)]
    [int]$Port = 8501
)

Write-Host "🚀 A360 Portal Launcher" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Cyan

# Get the script directory
$PortalDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Push-Location $PortalDir

try {
    # Check if Python is available
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        Write-Host "❌ Python not found. Please install Python 3.8+ first." -ForegroundColor Red
        exit 1
    }

    Write-Host "✅ Python found: $($pythonCmd.Source)" -ForegroundColor Green

    # Install dependencies if requested
    if ($Install) {
        Write-Host "📦 Installing dependencies..." -ForegroundColor Yellow
        python -m pip install --upgrade pip
        python -m pip install -r requirements.txt
        Write-Host "✅ Dependencies installed successfully!" -ForegroundColor Green
    }

    # Check if .env file exists
    if (-not (Test-Path ".env")) {
        if (Test-Path ".env.example") {
            Write-Host "⚠️  No .env file found. Copying from .env.example..." -ForegroundColor Yellow
            Copy-Item ".env.example" ".env"
            Write-Host "📝 Please edit .env file with your configuration before running the portal." -ForegroundColor Cyan
            
            $editChoice = Read-Host "Would you like to edit .env now? (y/N)"
            if ($editChoice -eq "y" -or $editChoice -eq "Y") {
                notepad ".env"
                Write-Host "Press any key to continue once you've saved your .env configuration..."
                $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
            }
        } else {
            Write-Host "❌ No .env.example file found. Cannot create configuration." -ForegroundColor Red
            exit 1
        }
    }

    # Create utils directory if it doesn't exist
    if (-not (Test-Path "utils")) {
        New-Item -ItemType Directory -Path "utils" -Force | Out-Null
    }

    # Create __init__.py in utils if it doesn't exist
    if (-not (Test-Path "utils\__init__.py")) {
        New-Item -ItemType File -Path "utils\__init__.py" -Force | Out-Null
    }

    # Launch the portal
    Write-Host "🌐 Starting A360 Portal..." -ForegroundColor Green
    Write-Host "Portal will be available at: http://localhost:$Port" -ForegroundColor Cyan
    Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
    Write-Host "===============================================" -ForegroundColor Cyan

    $streamlitArgs = @(
        "run", 
        "main.py",
        "--server.port", $Port,
        "--server.headless", "true",
        "--server.enableCORS", "false",
        "--server.enableXsrfProtection", "false"
    )

    if ($Dev) {
        $streamlitArgs += @("--server.runOnSave", "true")
        Write-Host "🔧 Development mode: Auto-reload enabled" -ForegroundColor Magenta
    }

    # Start Streamlit
    python -m streamlit $streamlitArgs

} catch {
    Write-Host "❌ Error starting portal: $($_.Exception.Message)" -ForegroundColor Red
} finally {
    Pop-Location
}

Write-Host "👋 A360 Portal stopped." -ForegroundColor Yellow