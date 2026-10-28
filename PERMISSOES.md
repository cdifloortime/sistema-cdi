# Perfis de acesso — CDI MVP 1.1

- **Terapeuta:** login próprio vinculado a um profissional; pode consultar somente os próprios atendimentos (data, horário, nome do paciente, especialidade e situação) e registrar uma única evolução diária por atendimento confirmado como realizado. Não pode alterar presença, agenda, cadastro, financeiro, repasse ou usuários. A restrição é aplicada também nas rotas do servidor.
- **Recepção:** agenda, cadastro básico de pacientes e terapeutas, confirmação de presença; sem prontuário e sem financeiro.
- **Financeiro:** apenas painel resumido e lançamentos financeiros; sem acesso a prontuários.
- **Administrador:** acesso aos módulos administrativos e evolução, com rastreio básico de ações.

## Avisos antes de usar dados reais
Protótipo para testes com dados fictícios, **não apto para produção**. Antes de cadastrar crianças e dados clínicos reais, implementar e testar CSRF, HTTPS, cookies seguros, autenticação forte/MFA, recuperação de senha, logs e trilha de auditoria imutável, backup/restauração, políticas de retenção, segregação de dados, proteção de dados sensíveis sob a LGPD, controles de sessão e revisão de segurança. Definir ainda regras de assinatura e retificação de prontuários e regras de cobrança e repasse para faltas/cancelamentos.
