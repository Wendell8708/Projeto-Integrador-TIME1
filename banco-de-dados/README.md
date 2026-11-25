# Banco de Dados – Monitoramento de Transporte de Frutas

## Visão geral

Esta pasta contém a modelagem e a implementação da camada de dados do Projeto Integrador de monitoramento do transporte de frutas.

O banco foi implementado em **PostgreSQL**, hospedado no **Neon**, utilizando o esquema `monitoramento`.

## Estrutura principal

O modelo possui 11 tabelas:

1. `usuario`
2. `fruta`
3. `parametro_fruta`
4. `dispositivo`
5. `credencial_dispositivo`
6. `viagem`
7. `medicao`
8. `evento_impacto`
9. `alerta`
10. `inspecao_final`
11. `foto_inspecao`

## Funcionalidades implementadas

- chaves primárias e estrangeiras;
- restrições `CHECK` e `UNIQUE`;
- prevenção de duplicidade de medições e eventos de impacto;
- índices para consultas frequentes;
- alertas automáticos por funções e gatilhos;
- dados fictícios para validação;
- consultas de conferência.

## Ordem de execução

Execute os arquivos da pasta `scripts` nesta ordem:

1. `01_criacao_esquema_tabelas.sql`
2. `02_indices.sql`
3. `03_funcoes_gatilhos.sql`
4. `04_dados_teste.sql`
5. `05_consultas_validacao.sql`

## Integração

A string de conexão deve ser armazenada em variável de ambiente:

```env
DATABASE_URL=postgresql://...
```

O arquivo `.env` não deve ser publicado no GitHub. As tabelas estão no esquema `monitoramento`, portanto o Back-End deve utilizar o `search_path`:

```text
monitoramento,public
```

## Segurança

- não publicar strings de conexão, senhas ou arquivos `.env`;
- usar a branch do Neon `testes-backend` durante testes;
- manter a branch `production` protegida contra testes destrutivos.

## Responsável

Wendel Kleyton Neri Brasiliano
