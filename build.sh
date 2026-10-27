#!/usr/bin/env bash
# Roda a cada deploy no Render: prepara o ambiente e deixa o banco com a estrutura do codigo.
set -o errexit   # para no primeiro erro (um deploy quebrado nao pode ficar pela metade)

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input
python manage.py criar_grupos
