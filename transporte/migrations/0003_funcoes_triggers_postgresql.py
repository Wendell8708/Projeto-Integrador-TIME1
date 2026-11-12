
from django.db import migrations


# =====================================================
# FUNÇÕES E TRIGGERS DO POSTGRESQL
# =====================================================

SQL_CRIAR = """

-- Função para atualizar automaticamente updated_at.

CREATE OR REPLACE FUNCTION fn_update_timestamp()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;


-- Trigger da tabela de viagens.

CREATE TRIGGER trg_shipments_updated_at
BEFORE UPDATE ON shipments
FOR EACH ROW
EXECUTE FUNCTION fn_update_timestamp();


-- Trigger da tabela de dispositivos.

CREATE TRIGGER trg_devices_updated_at
BEFORE UPDATE ON devices
FOR EACH ROW
EXECUTE FUNCTION fn_update_timestamp();


-- Função para calcular estatísticas de uma viagem.

CREATE OR REPLACE FUNCTION fn_shipment_statistics(
    p_shipment_id BIGINT
)
RETURNS TABLE (
    total_readings BIGINT,
    min_temperature NUMERIC,
    max_temperature NUMERIC,
    avg_temperature NUMERIC,
    min_humidity NUMERIC,
    max_humidity NUMERIC,
    avg_humidity NUMERIC
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        COUNT(r.id)::BIGINT,
        MIN(r.temperature_c),
        MAX(r.temperature_c),
        AVG(r.temperature_c),
        MIN(r.humidity_pct),
        MAX(r.humidity_pct),
        AVG(r.humidity_pct)
    FROM readings AS r
    WHERE r.shipment_id = p_shipment_id;
$$;

"""


# =====================================================
# SQL PARA DESFAZER A MIGRAÇÃO
# =====================================================

SQL_DESFAZER = """

DROP TRIGGER IF EXISTS trg_devices_updated_at
ON devices;

DROP TRIGGER IF EXISTS trg_shipments_updated_at
ON shipments;

DROP FUNCTION IF EXISTS fn_shipment_statistics(BIGINT);

DROP FUNCTION IF EXISTS fn_update_timestamp();

"""


# =====================================================
# CLASSE OBRIGATÓRIA DA MIGRAÇÃO
# =====================================================

class Migration(migrations.Migration):

    dependencies = [
        (
            'transporte',
            '0002_shipment_limits_snapshot_alter_shipment_started_at_and_more'
        ),
        (
            'iot',
            '0001_initial'
        ),
    ]

    operations = [
        migrations.RunSQL(
            sql=SQL_CRIAR,
            reverse_sql=SQL_DESFAZER,
        ),
    ]
