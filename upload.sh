#!/bin/bash

# Configuracion
BAUD=115200
PROJECT_DIR="led_matrix_project"

# Colores para la salida
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Deteccion automatica del puerto si no se pasa como argumento
if [ -n "$1" ]; then
    PORT="$1"
else
    # Buscar el primer puerto USB serial disponible (macOS)
    PORT=$(ls /dev/cu.usbmodem* /dev/cu.usbserial* /dev/cu.SLAB_USB* /dev/cu.wchusbserial* 2>/dev/null | head -1)
    if [ -z "$PORT" ]; then
        echo -e "${RED}Error: no se encontro ningun puerto serial.${NC}"
        echo "Conecta el ESP32 por USB o indica el puerto manualmente:"
        echo "  $0 /dev/cu.usbmodemXXXX"
        exit 1
    fi
fi

echo -e "${BLUE}=== Iniciando despliegue al ESP32 ===${NC}"
echo -e "Puerto: ${GREEN}$PORT${NC}"
echo -e "Proyecto: ${GREEN}$PROJECT_DIR${NC}"

# Verificar que el puerto existe
if [ ! -e "$PORT" ]; then
    echo -e "${RED}Error: el puerto $PORT no existe.${NC}"
    echo "Puertos disponibles:"
    ls /dev/cu.usbmodem* /dev/cu.usbserial* 2>/dev/null
    exit 1
fi

# Verificar si rshell esta instalado
if ! command -v rshell &> /dev/null; then
    echo -e "${RED}Error: rshell no esta instalado.${NC} Ejecuta 'pip install rshell' primero."
    exit 1
fi

# Subir archivos
echo -e "${BLUE}Subiendo archivos...${NC}"
# rshell copia recursivamente el contenido del directorio del proyecto
rshell -p "$PORT" -b "$BAUD" --timing cp -r "$PROJECT_DIR"/* /pyboard/

if [ $? -eq 0 ]; then
    echo -e "${GREEN}¡Archivos subidos correctamente!${NC}"
    echo -e "${BLUE}Reiniciando el ESP32...${NC}"
    # Reinicio remoto (soft reset via mpremote si esta disponible)
    if command -v mpremote &> /dev/null; then
        mpremote -p "$PORT" reset >/dev/null 2>&1
        echo -e "${GREEN}Dispositivo reiniciado. Espera ~10s y recarga la UI.${NC}"
    else
        echo -e "${YELLOW}mpremote no encontrado. Pulsa el boton RESET del ESP32 o CTRL+D en REPL.${NC}"
    fi
else
    echo -e "${RED}Hubo un error al subir los archivos.${NC}"
    exit 1
fi
