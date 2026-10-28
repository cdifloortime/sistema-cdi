# CDI Gestão Integrada — MVP 1.3

- Terapeuta pode iniciar manualmente no horário marcado.
- Se não iniciar, registro automático do início programado + 5 segundos.
- Se não finalizar, encerramento automático no horário agendado para o fim.
- Registros indicam origem `manual` ou `automatico`.
- A presença depende de confirmação da recepção; cronômetro automático não comprova atendimento.
- Rotina de reconciliação executa a cada segundo no servidor de desenvolvimento e também em requisições.
- O registro automático é um horário operacional previsto, não comprovação de realização efetiva.

**Atenção:** Para produção, usar agendador persistente separado do servidor web, armazenamento seguro, autenticação reforçada, CSRF, testes e auditoria LGPD. Não inserir dados reais nesta versão de demonstração.
