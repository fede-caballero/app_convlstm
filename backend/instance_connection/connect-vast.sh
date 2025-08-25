#!/bin/bash

# Script para conectarse a vast.ai de forma sencilla

# --- Pide los datos de la nueva instancia ---
read -p "Introduce la nueva IP de la instancia: " NEW_IP
read -p "Introduce el nuevo Puerto de la instancia: " NEW_PORT

echo ""
echo "Conectando a root@$NEW_IP en el puerto $NEW_PORT..."
echo "----------------------------------------------------"

# --- Ejecuta el comando SSH con los nuevos datos ---
# Usa la llave SSH que ya sabemos que funciona.
# El '-L 8080:localhost:8080' es para el port forwarding que podrías necesitar después.
ssh -i ~/.ssh/vast_key -p $NEW_PORT root@$NEW_IP -L 8080:localhost:8080

echo "Conexión terminada."