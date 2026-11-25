SET search_path TO monitoramento, public;

CREATE OR REPLACE FUNCTION gerar_alertas_medicao()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE v viagem%ROWTYPE;
BEGIN
 SELECT * INTO v FROM viagem WHERE id_viagem=NEW.id_viagem;
 IF NEW.temperatura < v.temperatura_minima THEN INSERT INTO alerta(id_viagem,id_medicao,tipo_alerta,nivel,descricao) VALUES(NEW.id_viagem,NEW.id_medicao,'TEMPERATURA_BAIXA','ALTO','Temperatura abaixo do limite mínimo da viagem'); END IF;
 IF NEW.temperatura > v.temperatura_maxima THEN INSERT INTO alerta(id_viagem,id_medicao,tipo_alerta,nivel,descricao) VALUES(NEW.id_viagem,NEW.id_medicao,'TEMPERATURA_ALTA','ALTO','Temperatura acima do limite máximo da viagem'); END IF;
 IF NEW.umidade < v.umidade_minima THEN INSERT INTO alerta(id_viagem,id_medicao,tipo_alerta,nivel,descricao) VALUES(NEW.id_viagem,NEW.id_medicao,'UMIDADE_BAIXA','ALTO','Umidade abaixo do limite mínimo da viagem'); END IF;
 IF NEW.umidade > v.umidade_maxima THEN INSERT INTO alerta(id_viagem,id_medicao,tipo_alerta,nivel,descricao) VALUES(NEW.id_viagem,NEW.id_medicao,'UMIDADE_ALTA','ALTO','Umidade acima do limite máximo da viagem'); END IF;
 IF NEW.pico_impacto IS NOT NULL AND NEW.pico_impacto > v.impacto_maximo THEN INSERT INTO alerta(id_viagem,id_medicao,tipo_alerta,nivel,descricao) VALUES(NEW.id_viagem,NEW.id_medicao,'IMPACTO_ACIMA_LIMITE','ALTO','Pico de impacto da medição acima do limite da viagem'); END IF;
 RETURN NEW;
END; $$;
DROP TRIGGER IF EXISTS trg_gerar_alertas_medicao ON medicao;
CREATE TRIGGER trg_gerar_alertas_medicao AFTER INSERT ON medicao FOR EACH ROW EXECUTE FUNCTION gerar_alertas_medicao();

CREATE OR REPLACE FUNCTION gerar_alerta_evento_impacto()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE limite NUMERIC(8,3);
BEGIN
 SELECT impacto_maximo INTO limite FROM viagem WHERE id_viagem=NEW.id_viagem;
 IF NEW.pico_impacto > limite THEN
  INSERT INTO alerta(id_viagem,id_evento_impacto,tipo_alerta,nivel,descricao)
  VALUES(NEW.id_viagem,NEW.id_evento_impacto,'IMPACTO_ACIMA_LIMITE','ALTO','Evento de impacto acima do limite máximo da viagem');
 END IF;
 RETURN NEW;
END; $$;
DROP TRIGGER IF EXISTS trg_gerar_alerta_evento_impacto ON evento_impacto;
CREATE TRIGGER trg_gerar_alerta_evento_impacto AFTER INSERT ON evento_impacto FOR EACH ROW EXECUTE FUNCTION gerar_alerta_evento_impacto();
