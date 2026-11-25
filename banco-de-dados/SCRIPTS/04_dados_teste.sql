SET search_path TO monitoramento, public;
-- Dados exclusivamente fictícios para validação acadêmica.
INSERT INTO usuario(nome,email,senha,funcao) VALUES('Usuario Teste','usuario.teste@pi.com','hash_senha_teste','OPERADOR');
INSERT INTO fruta(nome,descricao) VALUES('Uva','Uva destinada ao transporte refrigerado');
INSERT INTO dispositivo(codigo,nome,tipo_ultima_conexao,ssid_wifi) VALUES('ESP32-C3-001','Dispositivo de Monitoramento 01','WIFI','REDE_TESTE');
INSERT INTO parametro_fruta(id_fruta,temperatura_minima,temperatura_maxima,umidade_minima,umidade_maxima,impacto_maximo) VALUES(1,2.00,8.00,60.00,90.00,3.000);
INSERT INTO credencial_dispositivo(id_dispositivo,segredo_hash) VALUES(1,'hash_segredo_dispositivo_teste');
INSERT INTO viagem(id_usuario,id_fruta,id_dispositivo,codigo,origem,destino,data_hora_inicio,situacao,temperatura_minima,temperatura_maxima,umidade_minima,umidade_maxima,impacto_maximo) VALUES(1,1,1,'VIAGEM-001','Petrolina - PE','Recife - PE',CURRENT_TIMESTAMP,'EM_ANDAMENTO',2.00,8.00,60.00,90.00,3.000);
