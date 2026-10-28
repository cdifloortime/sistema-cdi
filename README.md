# CDI Gestão Integrada — MVP 1.0

Protótipo funcional local de aplicação web, **não homologado para produção ou dados reais de pacientes**.

## Iniciar no Windows (PowerShell)

1. Instale Python 3.11+.
2. Abra PowerShell na pasta extraída.
3. Execute:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:CDI_ADMIN_PASSWORD="EscolhaUmaSenhaForteDePeloMenos16Caracteres!"
$env:SECRET_KEY="TroquePorUmaChaveLongaAleatoria"
python app.py
```

4. Acesse http://127.0.0.1:5000 e entre com usuário `admin` e a senha configurada.
5. Para novos inícios, mantenha a senha original definida na primeira inicialização; o banco `cdi.db` preserva usuários e dados.

## Fluxo de teste

Cadastre terapeuta (com valor de repasse) e paciente fictícios. Crie agendamento, abra-o, marque como realizado e registre evolução. Consulte o financeiro para ver receita e repasse criados automaticamente. Cadastre usuários por perfil.

## Limites conhecidos / não usar com dados reais

- Não há hospedagem, HTTPS, backups, autenticação multifator, gestão de sessões em produção, proteção CSRF, assinatura eletrônica, políticas de retenção ou adequação integral à LGPD.
- O SQLite é para demonstração local, não para acesso simultâneo em escala.
- Controle de acesso é preliminar; administradores podem consultar evoluções; recepção não pode.
- Evoluções são imutáveis nesta versão, mas não há assinatura digital certificada.
- O caixa é simplificado: não inclui conciliação, estornos, regras de convênios, notas fiscais ou múltiplas contas.
- Uma sessão realizada gera receita e repasse pendentes. Cancelar sessão após quitação exige ajuste manual; não há estorno automático.
- Não há regras de cobrança por faltas, pacotes, autorizações ou validação de faturamento de convênios.
- Não existe publicação online automática; implantar em servidor exige projeto de segurança e operação.
