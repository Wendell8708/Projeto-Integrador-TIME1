CREATE SCHEMA IF NOT EXISTS monitoramento;
SET search_path TO monitoramento, public;

CREATE TABLE IF NOT EXISTS usuario (
 id_usuario BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 nome VARCHAR(120) NOT NULL,
 email VARCHAR(160) NOT NULL UNIQUE,
 senha VARCHAR(255) NOT NULL,
 funcao VARCHAR(30) NOT NULL,
 situacao VARCHAR(20) NOT NULL DEFAULT 'ATIVO',
 data_cadastro TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 data_hora_atualizacao TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 ultimo_acesso TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS fruta (
 id_fruta BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 nome VARCHAR(100) NOT NULL UNIQUE,
 descricao TEXT,
 situacao VARCHAR(20) NOT NULL DEFAULT 'ATIVA'
);

CREATE TABLE IF NOT EXISTS parametro_fruta (
 id_parametro BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 id_fruta BIGINT NOT NULL REFERENCES fruta(id_fruta),
 temperatura_minima NUMERIC(6,2) NOT NULL,
 temperatura_maxima NUMERIC(6,2) NOT NULL,
 umidade_minima NUMERIC(5,2) NOT NULL,
 umidade_maxima NUMERIC(5,2) NOT NULL,
 impacto_maximo NUMERIC(8,3) NOT NULL,
 situacao VARCHAR(20) NOT NULL DEFAULT 'ATIVO',
 data_cadastro TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 data_hora_atualizacao TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT chk_parametro_temperatura CHECK (temperatura_minima < temperatura_maxima),
 CONSTRAINT chk_parametro_umidade CHECK (umidade_minima BETWEEN 0 AND 100 AND umidade_maxima BETWEEN 0 AND 100 AND umidade_minima < umidade_maxima),
 CONSTRAINT chk_parametro_impacto CHECK (impacto_maximo >= 0)
);

CREATE TABLE IF NOT EXISTS dispositivo (
 id_dispositivo BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 codigo VARCHAR(60) NOT NULL UNIQUE,
 nome VARCHAR(100) NOT NULL,
 situacao VARCHAR(20) NOT NULL DEFAULT 'ATIVO',
 tipo_ultima_conexao VARCHAR(20),
 ssid_wifi VARCHAR(100),
 data_hora_ultima_comunicacao TIMESTAMPTZ,
 data_cadastro TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 data_hora_atualizacao TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS credencial_dispositivo (
 id_credencial_dispositivo BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 id_dispositivo BIGINT NOT NULL REFERENCES dispositivo(id_dispositivo),
 segredo_hash VARCHAR(255) NOT NULL,
 situacao VARCHAR(20) NOT NULL DEFAULT 'ATIVA',
 data_cadastro TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 data_hora_revogacao TIMESTAMPTZ,
 CONSTRAINT chk_credencial_revogacao CHECK (data_hora_revogacao IS NULL OR data_hora_revogacao >= data_cadastro)
);

CREATE TABLE IF NOT EXISTS viagem (
 id_viagem BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 id_usuario BIGINT NOT NULL REFERENCES usuario(id_usuario),
 id_fruta BIGINT NOT NULL REFERENCES fruta(id_fruta),
 id_dispositivo BIGINT NOT NULL REFERENCES dispositivo(id_dispositivo),
 codigo VARCHAR(50) NOT NULL UNIQUE,
 origem VARCHAR(150) NOT NULL,
 destino VARCHAR(150) NOT NULL,
 data_hora_inicio TIMESTAMPTZ NOT NULL,
 data_hora_fim TIMESTAMPTZ,
 situacao VARCHAR(20) NOT NULL DEFAULT 'PLANEJADA',
 temperatura_minima NUMERIC(6,2) NOT NULL,
 temperatura_maxima NUMERIC(6,2) NOT NULL,
 umidade_minima NUMERIC(5,2) NOT NULL,
 umidade_maxima NUMERIC(5,2) NOT NULL,
 impacto_maximo NUMERIC(8,3) NOT NULL,
 data_cadastro TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 data_hora_atualizacao TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT chk_viagem_periodo CHECK (data_hora_fim IS NULL OR data_hora_fim >= data_hora_inicio),
 CONSTRAINT chk_viagem_temperatura CHECK (temperatura_minima < temperatura_maxima),
 CONSTRAINT chk_viagem_umidade CHECK (umidade_minima BETWEEN 0 AND 100 AND umidade_maxima BETWEEN 0 AND 100 AND umidade_minima < umidade_maxima),
 CONSTRAINT chk_viagem_impacto CHECK (impacto_maximo >= 0)
);

CREATE TABLE IF NOT EXISTS medicao (
 id_medicao BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 id_viagem BIGINT NOT NULL REFERENCES viagem(id_viagem),
 id_dispositivo BIGINT NOT NULL REFERENCES dispositivo(id_dispositivo),
 sequencia BIGINT NOT NULL,
 temperatura NUMERIC(6,2) NOT NULL,
 umidade NUMERIC(5,2) NOT NULL,
 pico_impacto NUMERIC(8,3),
 rede VARCHAR(20),
 data_hora_medicao TIMESTAMPTZ NOT NULL,
 data_hora_recebimento TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT uq_medicao_dispositivo_sequencia UNIQUE(id_dispositivo, sequencia),
 CONSTRAINT chk_medicao_umidade CHECK (umidade BETWEEN 0 AND 100),
 CONSTRAINT chk_medicao_impacto CHECK (pico_impacto IS NULL OR pico_impacto >= 0)
);

CREATE TABLE IF NOT EXISTS evento_impacto (
 id_evento_impacto BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 id_viagem BIGINT NOT NULL REFERENCES viagem(id_viagem),
 id_dispositivo BIGINT NOT NULL REFERENCES dispositivo(id_dispositivo),
 codigo_evento VARCHAR(80) NOT NULL,
 pico_impacto NUMERIC(8,3) NOT NULL,
 rede VARCHAR(20),
 data_hora_registro TIMESTAMPTZ NOT NULL,
 data_hora_recebimento TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT uq_evento_dispositivo_codigo UNIQUE(id_dispositivo, codigo_evento),
 CONSTRAINT chk_evento_impacto CHECK (pico_impacto >= 0)
);

CREATE TABLE IF NOT EXISTS alerta (
 id_alerta BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 id_viagem BIGINT NOT NULL REFERENCES viagem(id_viagem),
 id_medicao BIGINT REFERENCES medicao(id_medicao),
 id_evento_impacto BIGINT REFERENCES evento_impacto(id_evento_impacto),
 tipo_alerta VARCHAR(40) NOT NULL,
 nivel VARCHAR(20) NOT NULL,
 descricao TEXT NOT NULL,
 situacao VARCHAR(20) NOT NULL DEFAULT 'ABERTO',
 data_hora_geracao TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 data_hora_resolucao TIMESTAMPTZ,
 CONSTRAINT chk_alerta_origem CHECK (NOT (id_medicao IS NOT NULL AND id_evento_impacto IS NOT NULL)),
 CONSTRAINT chk_alerta_resolucao CHECK (data_hora_resolucao IS NULL OR data_hora_resolucao >= data_hora_geracao)
);

CREATE TABLE IF NOT EXISTS inspecao_final (
 id_inspecao BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 id_viagem BIGINT NOT NULL UNIQUE REFERENCES viagem(id_viagem),
 id_usuario BIGINT NOT NULL REFERENCES usuario(id_usuario),
 condicao VARCHAR(40) NOT NULL,
 notas TEXT,
 data_hora_inspecao TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS foto_inspecao (
 id_foto BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 id_inspecao BIGINT NOT NULL REFERENCES inspecao_final(id_inspecao) ON DELETE CASCADE,
 caminho_arquivo TEXT NOT NULL,
 descricao TEXT,
 data_hora_cadastro TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
