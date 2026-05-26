import os

# Configurações do Gunicorn para o DocFlow

# Aumenta o tempo limite do worker para 300 segundos (5 minutos) para processar PDFs pesados
timeout = 300

# Mantém apenas 1 worker para poupar memória RAM no container de produção do Railway
workers = 1

# Vincula o host e a porta injetada dinamicamente pelo Railway
bind = f"0.0.0.0:{os.environ.get('PORT', '8080')}"
