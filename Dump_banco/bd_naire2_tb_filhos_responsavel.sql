-- MySQL dump 10.13  Distrib 8.0.45, for Win64 (x86_64)
--
-- Host: 127.0.0.1    Database: bd_naire2
-- ------------------------------------------------------
-- Server version	5.5.5-10.11.16-MariaDB

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `tb_filhos_responsavel`
--

DROP TABLE IF EXISTS `tb_filhos_responsavel`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tb_filhos_responsavel` (
  `id_filho` int(11) NOT NULL AUTO_INCREMENT,
  `id_responsavel` int(11) NOT NULL,
  `id_usuario_cad` int(11) DEFAULT NULL,
  `pnome` varchar(100) DEFAULT NULL,
  `snome` varchar(255) DEFAULT NULL,
  `data_nascimento` varchar(10) DEFAULT NULL,
  `cpf` varchar(11) DEFAULT NULL,
  `sexo` varchar(2) DEFAULT NULL,
  `numero_roupa` varchar(15) DEFAULT NULL,
  `numero_sapato` int(15) DEFAULT NULL,
  `cadastro_outra_ong` varchar(1) DEFAULT 'N',
  `url_imagem` varchar(255) DEFAULT NULL,
  `data_cadastro` timestamp(6) NULL DEFAULT current_timestamp(6),
  `data_atualizacao` timestamp(6) NULL DEFAULT current_timestamp(6) ON UPDATE current_timestamp(6),
  `flag_ativo` varchar(1) DEFAULT 'S',
  PRIMARY KEY (`id_filho`,`id_responsavel`),
  KEY `id_usuario_cad_filho_fk_idx` (`id_usuario_cad`),
  KEY `id_responsavel_fk_idx` (`id_responsavel`),
  CONSTRAINT `id_responsavel_fk` FOREIGN KEY (`id_responsavel`) REFERENCES `tb_cadastro_responsavel` (`id_responsavel`) ON DELETE NO ACTION ON UPDATE NO ACTION,
  CONSTRAINT `id_usuario_cad_filho_fk` FOREIGN KEY (`id_usuario_cad`) REFERENCES `auth_user` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tb_filhos_responsavel`
--

LOCK TABLES `tb_filhos_responsavel` WRITE;
/*!40000 ALTER TABLE `tb_filhos_responsavel` DISABLE KEYS */;
INSERT INTO `tb_filhos_responsavel` VALUES (3,9,2,'ANNITA','GIACCOMETTI','05/10/2020','12398745620','F','6',34,'N',NULL,'2026-05-18 21:14:05.344790','2026-05-18 21:15:24.096523','N'),(4,8,2,'CARLOS','JOSE DA SILVA','05/05/2021','58471632954','M','5',25,'S',NULL,'2026-05-18 21:39:20.961697','2026-05-18 21:39:20.961697','S'),(5,8,2,'KATIA','NASCIMENTO','06/12/2012','12365489721','F','10',35,'N',NULL,'2026-05-18 21:45:59.870161','2026-05-18 21:45:59.870161','S'),(6,9,2,'PATRICIA','CARDOSO DE JESUS','04/01/2020','57395127645','F','10',37,'S',NULL,'2026-05-18 22:01:26.164340','2026-05-18 22:01:26.164340','S'),(7,8,4,'KAIKE','SHARLON','15/01/2022','12365478542','M','10',37,'S',NULL,'2026-05-19 00:52:37.744875','2026-05-19 00:52:37.744875','S'),(8,12,4,'KARLA','SANTOS','15/12/2019','14587456235','F','8',34,'N',NULL,'2026-05-19 00:53:41.143058','2026-05-19 00:53:41.143058','N'),(9,13,5,'CLAYSON','SANTOS','05/05/2021','45621398574','M','10',37,'N',NULL,'2026-05-20 01:01:44.484196','2026-05-20 01:01:44.484196','S'),(10,10,2,'ENZO','GABRIEL DA SILVA','20/2//05/1','00995977054','M','8',35,'N',NULL,'2026-05-23 04:41:35.501172','2026-05-23 04:41:35.501172','S');
/*!40000 ALTER TABLE `tb_filhos_responsavel` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-05-23  5:17:46
