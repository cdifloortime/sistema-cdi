# CDI - Correção de inicialização no Render

Erro corrigido: `no such table: session_times` na primeira requisição. Antes, `init()` só rodava em `python app.py`; agora executa também quando Gunicorn importa `app`.

1. Substitua `app.py` e `requirements.txt` no repositório privado GitHub.
2. Render > Environment: configure `CDI_ADMIN_PASSWORD` com senha forte e `SECRET_KEY` com valor aleatório longo. Não publique esses valores no GitHub. Opcional: `CDI_ADMIN_USER`.
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `gunicorn --workers 1 --bind 0.0.0.0:$PORT app:app`
5. Faça deploy e teste somente com dados fictícios.

**Limitações importantes:** banco SQLite local em instância gratuita é efêmero, pode perder dados a qualquer reinicialização/redeploy; a reconciliação dos cronômetros só roda durante requisições, não é um agendador persistente. Ainda faltam CSRF, autenticação robusta, backups, segurança clínica e validação LGPD. Não use dados reais.
