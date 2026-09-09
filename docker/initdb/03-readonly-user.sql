-- Text-to-SQL 에이전트 전용 읽기 전용 계정.
-- LLM 이 만든 SQL 에 대한 1차 방어선(DB 권한 레벨).
CREATE USER IF NOT EXISTS 't2s_ro'@'%' IDENTIFIED BY 't2s_ro_pw';
GRANT SELECT, SHOW VIEW ON sakila.* TO 't2s_ro'@'%';
FLUSH PRIVILEGES;
