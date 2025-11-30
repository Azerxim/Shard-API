#!/bin/bash

# Shard API Manager - Main Menu
# Interactive script to run various project tasks

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
            if [ -d ".env" ]; then
                echo -e "${YELLOW}Virtual environment already exists. Activating...${NC}"
                source .env/bin/activate
                echo -e "${GREEN}Virtual environment activated!${NC}"
                echo -e "${CYAN}Python version: $(python --version)${NC}"
            else
                echo -e "${YELLOW}Creating virtual environment...${NC}"
                python3 -m venv .env
                echo -e "${GREEN}Virtual environment created!${NC}"
                echo -e "${YELLOW}Activating virtual environment...${NC}"
                source .env/bin/activate
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
            echo -e "${GREEN}Starting API...${NC}"
            echo -e "${CYAN}Server will be available at http://localhost:8000${NC}"
            echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
            echo ""
            python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
            echo ""
            read -p "Press any key to continue..." -n 1
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
