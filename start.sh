#!/bin/bash

# Shard API Manager - Main Menu
# Interactive script to run various project tasks

# Configuration
VENV_DIR=".venv"

# Couleurs ANSI
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Color

while true; do
    clear
    echo -e "${CYAN}==========================================${NC}"
    echo -e "${GREEN}  Shard API Manager${NC}"
    echo -e "${CYAN}==========================================${NC}"
    echo ""
    echo -e "${YELLOW}Select an option:${NC}"
    echo ""
    echo "1) Create/Activate virtual environment"
    echo "2) Install dependencies"
    echo "3) Start API"
    echo "4) Exit"
    echo ""
    read -p "Enter your choice [1-4]: " choice

    case $choice in
        1)
            echo ""
            if [ -d "$VENV_DIR" ]; then
                echo -e "${YELLOW}Virtual environment already exists. Activating...${NC}"
                source "$VENV_DIR/bin/activate"
                echo -e "${GREEN}Virtual environment activated!${NC}"
                echo -e "${CYAN}Python version: $(python --version)${NC}"
            else
                echo -e "${YELLOW}Creating virtual environment...${NC}"
                python3 -m venv "$VENV_DIR"
                echo -e "${GREEN}Virtual environment created!${NC}"
                echo -e "${YELLOW}Activating virtual environment...${NC}"
                source "$VENV_DIR/bin/activate"
                echo -e "${GREEN}Virtual environment activated!${NC}"
                echo -e "${CYAN}Python version: $(python --version)${NC}"
                echo ""
                echo -e "${YELLOW}Installing dependencies...${NC}"
                python -m pip install --upgrade pip
            fi
            echo ""
            read -p "Press any key to continue..." -n 1
            ;;
        2)
            echo ""
            echo -e "${CYAN}--- Install Dependencies ---${NC}"
            echo ""
            echo -e "${GREEN}Installing dependencies...${NC}"
            python -m pip install --upgrade -r requirements.txt
            echo ""
            echo -e "${GREEN}Dependencies installed!${NC}"
            echo ""
            read -p "Press any key to continue..." -n 1
            ;;
        3)
            echo ""
            echo -e "${YELLOW}Reading configuration from config.json...${NC}"
            
            # Lire config.json avec jq ou grep selon la disponibilité
            if command -v jq &> /dev/null; then
                HOST_IP=$(jq -r '.api.ip' config.json)
                HOST_PORT=$(jq -r '.api.port' config.json)
            else
                # Fallback si jq n'est pas disponible
                HOST_IP=$(grep -oP '"ip":\s*"\K[^"]+' config.json)
                HOST_PORT=$(grep -oP '"port":\s*\K[0-9]+' config.json | head -1)
            fi
            
            # Demander le mode de développement
            echo ""
            echo -e "${CYAN}Mode de développement:${NC}"
            echo "1) Mode développeur (--reload activé)"
            echo "2) Mode production (--reload désactivé)"
            echo ""
            read -p "Choisissez le mode [1-2] (défaut: 1): " dev_mode
            
            # Définir le flag reload
            if [ "$dev_mode" = "2" ]; then
                RELOAD_FLAG=""
                MODE_TEXT="production"
            else
                RELOAD_FLAG="--reload"
                MODE_TEXT="développeur"
            fi
            
            echo -e "${GREEN}Démarrage en mode ${MODE_TEXT}...${NC}"
            echo -e "${CYAN}Serveur disponible à http://$HOST_IP:$HOST_PORT${NC}"
            echo -e "${YELLOW}Appuyez sur Ctrl+C pour arrêter le serveur${NC}"
            echo ""
            python -m uvicorn api.main:app $RELOAD_FLAG --host $HOST_IP --port $HOST_PORT
            echo ""
            read -p "Appuyez sur une touche pour continuer..." -n 1
            ;;
        4)
            echo ""
            echo -e "${GREEN}Goodbye!${NC}"
            exit 0
            ;;
        *)
            echo ""
            echo -e "${RED}Invalid option. Please try again.${NC}"
            echo ""
            read -p "Press any key to continue..." -n 1
            ;;
    esac
done
