#!/usr/bin/env bash
# exit on error
set -o errexit

# Instala as dependências do Python
pip install -r requirements.txt

# --- Instalação do Firefox e geckodriver ---
echo "Instalando Firefox e dependências..."
apt-get update
apt-get install -y wget bzip2 libdbus-glib-1-2

echo "Baixando Firefox..."
wget -O firefox.tar.bz2 "https://download.mozilla.org/?product=firefox-latest-ssl&os=linux64&lang=en-US"
tar -xjf firefox.tar.bz2 -C /opt/

echo "Criando link simbólico para o Firefox..."
ln -s /opt/firefox/firefox /usr/bin/firefox

echo "Baixando geckodriver..."
GECKODRIVER_VERSION=$(curl -s "https://api.github.com/repos/mozilla/geckodriver/releases/latest" | grep -Po '"tag_name": "\K.*?(?=")')
wget -O geckodriver.tar.gz "https://github.com/mozilla/geckodriver/releases/download/$GECKODRIVER_VERSION/geckodriver-$GECKODRIVER_VERSION-linux64.tar.gz"
tar -xzf geckodriver.tar.gz
mv geckodriver /usr/bin/

echo "Instalação concluída com sucesso!" 