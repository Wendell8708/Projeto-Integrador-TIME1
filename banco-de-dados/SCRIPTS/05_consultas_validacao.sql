SET search_path TO monitoramento, public;
SELECT table_name FROM information_schema.tables WHERE table_schema='monitoramento' ORDER BY table_name;
SELECT * FROM viagem ORDER BY id_viagem DESC;
SELECT * FROM medicao ORDER BY id_medicao DESC;
SELECT * FROM evento_impacto ORDER BY id_evento_impacto DESC;
SELECT a.id_alerta,v.codigo AS viagem,a.tipo_alerta,a.nivel,a.situacao,a.id_medicao,a.id_evento_impacto,a.data_hora_geracao FROM alerta a JOIN viagem v ON v.id_viagem=a.id_viagem ORDER BY a.id_alerta;
