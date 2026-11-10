-- SENAC RESERVA V1 - MySQL 8.0+
-- Modelo simplificado: PERFIL, USUARIO, SALA, RESERVA
CREATE DATABASE IF NOT EXISTS senac_reserva CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE senac_reserva;

CREATE TABLE IF NOT EXISTS perfil (
 id_perfil INT AUTO_INCREMENT PRIMARY KEY,
 nome VARCHAR(30) NOT NULL UNIQUE,
 descricao VARCHAR(100)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS usuario (
 id_usuario INT AUTO_INCREMENT PRIMARY KEY,
 id_perfil INT NOT NULL,
 nome VARCHAR(100) NOT NULL,
 email VARCHAR(120) NOT NULL UNIQUE,
 senha VARCHAR(255) NOT NULL COMMENT 'Armazenar hash seguro, nunca senha em texto puro',
 ativo BOOLEAN NOT NULL DEFAULT TRUE,
 CONSTRAINT fk_usuario_perfil FOREIGN KEY (id_perfil) REFERENCES perfil(id_perfil)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sala (
 id_sala INT AUTO_INCREMENT PRIMARY KEY,
 nome VARCHAR(50) NOT NULL UNIQUE,
 capacidade INT NOT NULL,
 tipo VARCHAR(30) NOT NULL,
 descricao VARCHAR(200),
 ativa BOOLEAN NOT NULL DEFAULT TRUE,
 CONSTRAINT ck_sala_capacidade CHECK (capacidade > 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS reserva (
 id_reserva INT AUTO_INCREMENT PRIMARY KEY,
 id_usuario INT NOT NULL,
 id_sala INT NOT NULL,
 data_reserva DATE NOT NULL,
 hora_inicio TIME NOT NULL,
 hora_fim TIME NOT NULL,
 finalidade VARCHAR(200) NOT NULL,
 status ENUM('Confirmada','Cancelada') NOT NULL DEFAULT 'Confirmada',
 data_criacao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT fk_reserva_usuario FOREIGN KEY (id_usuario) REFERENCES usuario(id_usuario),
 CONSTRAINT fk_reserva_sala FOREIGN KEY (id_sala) REFERENCES sala(id_sala),
 CONSTRAINT ck_reserva_horario CHECK (hora_inicio < hora_fim),
 INDEX idx_reserva_disponibilidade (id_sala, data_reserva, status, hora_inicio, hora_fim),
 INDEX idx_reserva_usuario (id_usuario, data_reserva)
) ENGINE=InnoDB;

-- Dados iniciais: 3 perfis e 9 salas. Capacidade/tipo são exemplos: ajustar à realidade.
INSERT INTO perfil (id_perfil, nome, descricao) VALUES
(1,'Super Usuário','Acesso total ao sistema'),
(2,'Administrativo','Reservas, gestão de salas e relatórios gerais'),
(3,'Docente','Reservas e relatórios próprios')
ON DUPLICATE KEY UPDATE nome=VALUES(nome), descricao=VALUES(descricao);

INSERT INTO sala (id_sala,nome,capacidade,tipo,descricao) VALUES
(1,'Sala 01',30,'Sala de aula','Capacidade ilustrativa'),
(2,'Sala 02',30,'Sala de aula','Capacidade ilustrativa'),
(3,'Sala 03',30,'Sala de aula','Capacidade ilustrativa'),
(4,'Sala 04',30,'Sala de aula','Capacidade ilustrativa'),
(5,'Sala 05',30,'Sala de aula','Capacidade ilustrativa'),
(6,'Sala 06',30,'Sala de aula','Capacidade ilustrativa'),
(7,'Sala 07',30,'Sala de aula','Capacidade ilustrativa'),
(8,'Sala 08',30,'Sala de aula','Capacidade ilustrativa'),
(9,'Sala 09',30,'Sala de aula','Capacidade ilustrativa')
ON DUPLICATE KEY UPDATE nome=VALUES(nome);

-- Consulta de conflito: retorna reservas que impedem novo agendamento.
-- Exemplo: Sala 01, 10/11/2026, 20h-21h.
SELECT id_reserva, hora_inicio, hora_fim FROM reserva
WHERE id_sala = 1 AND data_reserva = '2026-11-10'
  AND status = 'Confirmada'
  AND hora_inicio < '21:00:00' AND hora_fim > '20:00:00';

-- IMPORTANTE: o SELECT acima é didático; NÃO impede sozinho reservas concorrentes.
-- Na aplicação, bloquear a linha da sala com SELECT ... FOR UPDATE dentro de
-- uma transação, verificar conflito e inserir antes do COMMIT.
-- Exemplo de fluxo transacional (parâmetros substituídos pelo back-end):
-- START TRANSACTION;
-- SELECT id_sala, ativa FROM sala WHERE id_sala = ? FOR UPDATE;
-- SELECT id_reserva FROM reserva WHERE id_sala = ? AND data_reserva = ?
--   AND status = 'Confirmada' AND hora_inicio < ? AND hora_fim > ?;
-- Se sala inativa ou houver conflito: ROLLBACK; senão: INSERT ...; COMMIT.
-- Todos os caminhos de escrita de reservas devem respeitar o mesmo bloqueio.
