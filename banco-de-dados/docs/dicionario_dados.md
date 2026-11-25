# Dicionário de Dados

| Tabela | Finalidade | Chaves e regras principais |
|---|---|---|
| usuario | Usuários do sistema | PK `id_usuario`; e-mail único |
| fruta | Tipos de fruta | PK `id_fruta`; nome único |
| parametro_fruta | Limites atuais por fruta | FK `id_fruta`; checks de temperatura, umidade e impacto |
| dispositivo | Equipamento IoT | PK `id_dispositivo`; código único |
| credencial_dispositivo | Autenticação do dispositivo | FK `id_dispositivo`; segredo armazenado como hash |
| viagem | Unidade central do monitoramento | FKs de usuário, fruta e dispositivo; limites congelados |
| medicao | Telemetria periódica | FKs de viagem e dispositivo; sequência única por dispositivo |
| evento_impacto | Impactos pontuais | FKs de viagem e dispositivo; código do evento único por dispositivo |
| alerta | Violações de limites | FK obrigatória de viagem; medição ou impacto opcionais |
| inspecao_final | Avaliação no destino | Uma inspeção por viagem; usuário responsável |
| foto_inspecao | Referências das fotos | FK de inspeção; exclusão em cascata |
