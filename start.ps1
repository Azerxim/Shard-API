# PLCSim Campaign Test Manager - Main Menu
# Interactive script to run various project tasks

# Configuration
$VENV_DIR = ".venv"

while ($true) {
    Clear-Host
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host "  Shard API Manager" -ForegroundColor Green
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Select an option:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "1) Create/Activate virtual environment" -ForegroundColor White
    Write-Host "2) Install dependencies" -ForegroundColor White
    Write-Host "3) Start API" -ForegroundColor White
    Write-Host "4) Exit" -ForegroundColor White
    Write-Host ""

    $choice = Read-Host "Enter your choice [1-4]"

    switch ($choice) {
        "1" {
            Write-Host ""
            if (Test-Path "$VENV_DIR") {
                Write-Host "Virtual environment already exists. Activating..." -ForegroundColor Yellow
                .\$VENV_DIR\Scripts\Activate.ps1
                Write-Host "Virtual environment activated!" -ForegroundColor Green
                Write-Host "Python version: $(python --version)" -ForegroundColor Cyan
            } else {
                Write-Host "Creating virtual environment..." -ForegroundColor Yellow
                python -m venv $VENV_DIR
                Write-Host "Virtual environment created!" -ForegroundColor Green
                Write-Host "Activating virtual environment..." -ForegroundColor Yellow
                .\$VENV_DIR\Scripts\Activate.ps1
                Write-Host "Virtual environment activated!" -ForegroundColor Green
                Write-Host "Python version: $(python --version)" -ForegroundColor Cyan
                Write-Host ""
                Write-Host "Installing dependencies..." -ForegroundColor Yellow
                python -m pip install --upgrade pip
            }
            Write-Host ""
            Write-Host "Press any key to continue..." -ForegroundColor Gray
            $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        }
        "2" {
            Write-Host ""
            Write-Host "--- Install Dependencies ---" -ForegroundColor Cyan
            Write-Host ""
            Write-Host "Installing dependencies..." -ForegroundColor Green
            python -m pip install --upgrade -r requirements.txt
            Write-Host ""
            Write-Host "Dependencies installed!" -ForegroundColor Green
            Write-Host ""
            Write-Host "Press any key to continue..." -ForegroundColor Gray
            $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        }
        "3" {
            Write-Host ""
            Write-Host "Reading configuration from config.json..." -ForegroundColor Yellow
            
            # Lire config.json
            $config = Get-Content "config.json" | ConvertFrom-Json
            $host_ip = $config.api.ip
            $host_port = $config.api.port
            
            # Demander le mode de développement
            Write-Host ""
            Write-Host "Development mode:" -ForegroundColor Cyan
            Write-Host "1) Developer mode (--reload enabled)"
            Write-Host "2) Production mode (--reload disabled)"
            Write-Host ""
            $dev_mode = Read-Host "Choose mode [1-2] (default: 1)"
            
            # Définir le flag reload
            if ($dev_mode -eq "2") {
                $reload_flag = ""
                $mode_text = "production"
            } else {
                $reload_flag = "--reload"
                $mode_text = "developer"
            }
            
            Write-Host ""
            Write-Host "Starting API in $mode_text mode..." -ForegroundColor Green
            Write-Host "Server will be available at http://$($host_ip):$($host_port)" -ForegroundColor Cyan
            Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
            Write-Host ""
            uvicorn api.main:app $reload_flag --host $host_ip --port $host_port
            Write-Host ""
            Write-Host "Press any key to continue..." -ForegroundColor Gray
            $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        }
        "4" {
            Write-Host ""
            Write-Host "Goodbye!" -ForegroundColor Green    
            exit 0
        }
        default {
            Write-Host ""
            Write-Host "Invalid option. Please try again." -ForegroundColor Red
            Write-Host ""
            Write-Host "Press any key to continue..." -ForegroundColor Gray
            $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        }
    }
}
