-- =====================================================================
-- Migração: CPF criptografado + coluna cpf_hash (deduplicação e busca)
-- =====================================================================
--
-- POR QUE ISTO É NECESSÁRIO
--   1. O django-cryptography grava o CPF cifrado em BINÁRIO (~89 bytes).
--      As colunas atuais são varchar(11): não cabem.
--   2. O CPF cifrado é diferente a cada gravação (é aleatório de propósito),
--      então um índice UNIQUE na coluna `cpf` não impede duplicados.
--      A coluna `cpf_hash` (HMAC do CPF) é sempre igual para o mesmo CPF:
--      é nela que fica o índice UNIQUE e a busca por igualdade.
--
-- COMO RODAR (nesta ordem)
--   0. FAÇA BACKUP:  mysqldump -u USUARIO -p bd_naire2 > backup_antes_cpf_hash.sql
--   1. mysql -u USUARIO -p bd_naire2 < Dump_banco/migracao_cpf_hash.sql
--   2. python criptografar_banco.py          (cifra CPFs que ainda estão em texto)
--   3. python manage.py migrate              (cria o grupo LGPD)
--   4. python manage.py preencher_cpf_hash   (calcula o hash dos registros antigos)
--
-- Se o passo 4 apontar CPFs duplicados, resolva-os manualmente (são
-- cadastros repetidos que já existiam) e rode o passo 4 de novo.
-- =====================================================================

-- ---------- Responsáveis ----------
-- O índice único antigo no CPF não funciona mais com CPF cifrado.
-- (Se der erro "Can't DROP 'cpf_UNIQUE'", o índice já não existe: pode
--  comentar esta linha e seguir.)
ALTER TABLE tb_cadastro_responsavel DROP INDEX cpf_UNIQUE;
ALTER TABLE tb_cadastro_responsavel
    MODIFY cpf VARBINARY(255) NULL,
    ADD COLUMN cpf_hash CHAR(64) NULL AFTER cpf,
    ADD UNIQUE KEY uq_responsavel_cpf_hash (cpf_hash);

-- ---------- Crianças ----------
ALTER TABLE tb_filhos_responsavel
    MODIFY cpf VARBINARY(255) NULL,
    ADD COLUMN cpf_hash CHAR(64) NULL AFTER cpf,
    ADD UNIQUE KEY uq_filho_cpf_hash (cpf_hash);

-- ---------- Madrinhas / Padrinhos ----------
ALTER TABLE tb_madrinha_padrinho
    MODIFY cpf VARBINARY(255) NULL,
    ADD COLUMN cpf_hash CHAR(64) NULL AFTER cpf,
    ADD UNIQUE KEY uq_mad_pad_cpf_hash (cpf_hash);

-- ---------- Funcionários ----------
ALTER TABLE tb_funcionario
    MODIFY cpf VARBINARY(255) NULL,
    ADD COLUMN cpf_hash CHAR(64) NULL AFTER cpf,
    ADD UNIQUE KEY uq_funcionario_cpf_hash (cpf_hash);

-- Observação: NULL não conflita com UNIQUE no MySQL, então registros sem
-- CPF (crianças, padrinhos anônimos, cadastros anonimizados) convivem bem.
