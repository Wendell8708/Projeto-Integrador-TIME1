# Modelo de ameaças — Caminho do Vale (monitoramento do transporte de frutas)

**O que protegemos:** as contas de vendedores, compradores, motoristas e administradores da plataforma; as placas ESP32-C3 e seus dados; viagens, itens, leituras, impactos, alertas e cadastros de veículos e locais.

**Arquitetura analisada:** dispositivos enviam leituras para a API Django por meio da credencial `X-Device-Key`; a API persiste os dados no PostgreSQL (Neon); o painel web/PWA acessa a API usando JWT. O projeto também possui integração MQTT, com riscos específicos descritos abaixo.

**Critério de avaliação:** os controles das ameaças 1 e 2 foram testados antes e depois na API publicada (evidências em `seguranca/evidencias/`). **Mitigada** não significa risco eliminado: cada linha indica o que continua aberto.

Classificação STRIDE: **S** = falsificação de identidade; **T** = adulteração; **I** = divulgação indevida de informação; **D** = negação de serviço; **E** = elevação de privilégio.

| # | Ameaça (STRIDE) | Cenário/impacto | Estado e controles identificados | Risco residual |
| --- | --- | --- | --- | --- |
| **1** | **Senha vazada/roubada** (S) | Um terceiro obtém a senha e tenta acessar cargas, clientes, rotas e comandos de viagem. | **Mitigada no código pelo 2FA/TOTP:** autenticação por senha passa por etapa `mfa_token`; validação do código ocorre no servidor; há QR Code de cadastro e códigos de recuperação de uso único (`usuarios/dois_fatores.py`, `usuarios/views.py`). | Phishing em tempo real, roubo de token/sessão, perda ou comprometimento do autenticador e indisponibilidade não são eliminados por TOTP. |
| **2** | **IDOR por substituição de ID** (I, T, E) | Usuário autenticado troca o ID de recursos de outra conta, podendo visualizar dados ou tentar alterações. | **Mitigada no código por autorização no servidor:** filtros em `usuarios/acesso.py` aplicados às views de viagens/itens, placas/leituras, alertas, **veículos e locais**. Acesso indevido a detalhe não visível retorna em geral 404; alteração de cadastro visível sem propriedade pode retornar 403. | Novos endpoints sem os mesmos filtros podem reintroduzir IDOR; privilégios administrativos exigem governança e auditoria. |
| **3** | **Placa falsa ou chave extraída** (S, T) | Uma placa clonada ou agente malicioso envia telemetria falsa, prejudicando alertas e avaliação da carga. | **Mitigação parcial:** API exige `X-Device-Key` e armazena o hash da credencial, conforme implementação de ingestão IoT. | Quem obtiver acesso físico e extrair o segredo do dispositivo ainda poderá imitá-lo. |
| **4** | **MQTT em broker público** (I, T) | Um terceiro descobre tópicos e lê ou publica mensagens falsas no fluxo em tempo real. | **Aberta:** histórico oficial é mantido via API, mas isso não protege o broker público. | Adotar broker privado com autenticação, autorização por tópico e TLS; avaliar validação da origem das mensagens. |
| **5** | **Força bruta e negação de serviço no login/OTP** (S, D) | Muitas tentativas buscam adivinhar senha/OTP ou sobrecarregar a aplicação. | **Mitigação parcial implementada:** `THROTTLE_LOGIN` padrão `10/min` e `THROTTLE_MFA` padrão **`10/min`** em `piADS04/settings.py`; o 2FA usa `ScopedRateThrottle` com escopo `mfa` em `usuarios/views.py`. | Limites podem ser modificados pelo ambiente e não garantem proteção contra ataques distribuídos, evasão de limitação ou sobrecarga do serviço. |

## Por que as ameaças 1 e 2 foram priorizadas

1. Não dependem de acesso físico à placa: uma senha descoberta ou uma conta comum podem abrir caminho para ataques.
2. Podem expor dados comerciais e comandos críticos de viagens entre participantes diferentes.
3. Os testes anteriores registraram falhas verificáveis em 17/11/2026: `seguranca/evidencias/otp-antes.txt` mostra login emitindo token apenas com senha; `seguranca/evidencias/idor-antes.txt` mostra seis de seis tentativas de acesso indevido aceitas. Esses registros **não** são provas do comportamento após a correção.

## Abrangência da mitigação IDOR

- **Viagens:** visíveis ao criador, comprador, motorista ou dono da placa da viagem, além da plataforma.
- **Placas:** visíveis ao proprietário, além da plataforma.
- **Itens, leituras, impactos e alertas:** seguem a autorização da viagem associada.
- **Veículos e locais:** próprios, compartilhados sem dono ou vinculados a viagens autorizadas podem ser visualizados; **alterar ou excluir** exige proprietário ou plataforma.
- **Plataforma:** superusuários ou grupo `Administrador` possuem acesso amplo previsto nas regras do projeto.

Referências de código: `usuarios/acesso.py`, `transporte/views.py`, `iot/views.py`, `alertas/views.py` e `dominio/views.py`.

## Riscos ainda abertos e próximos passos

1. **Comprometimento físico dos dispositivos:** estudar armazenamento seguro, rotação/revogação de credenciais e resposta a roubo da placa.
2. **MQTT público:** migrar para broker com autenticação, permissões por tópico e TLS.
3. **Negação de serviço e força bruta distribuída:** validar rate limiting em produção, observar logs e considerar proteção complementar na borda; a taxa padrão de OTP de 10/min **já está implementada no código**.
4. **Roubo de sessão e phishing avançado:** TOTP não impede todos os tipos de comprometimento de sessão; manter proteção dos tokens, políticas de expiração e monitoramento.
5. **Regressões de autorização:** manter testes de acesso cruzado em novas rotas e nas regras diferenciadas de edição/leitura.

**Evidências:** o antes e o depois das ameaças 1 e 2 estão em `seguranca/evidencias/` (`TIME1-otp-*` e `TIME1-idor-*`), e o passo a passo para repetir os testes está no `seguranca/README.md`.
