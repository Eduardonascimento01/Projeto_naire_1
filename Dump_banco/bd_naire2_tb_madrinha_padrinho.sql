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
-- Table structure for table `tb_madrinha_padrinho`
--

DROP TABLE IF EXISTS `tb_madrinha_padrinho`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tb_madrinha_padrinho` (
  `id_mad_pad` int(11) NOT NULL AUTO_INCREMENT,
  `id_usuario_cad` int(11) DEFAULT NULL,
  `cpf` varchar(11) DEFAULT NULL,
  `flag_anonimo` varchar(1) DEFAULT 'N',
  `pnome` varchar(100) DEFAULT NULL,
  `snome` varchar(255) DEFAULT NULL,
  `endereco` varchar(255) DEFAULT NULL,
  `complemento` varchar(255) DEFAULT NULL,
  `bairro` varchar(255) DEFAULT NULL,
  `cidade` varchar(255) DEFAULT NULL,
  `estado` varchar(255) DEFAULT NULL,
  `data_cadastro` timestamp(6) NULL DEFAULT current_timestamp(6),
  `atualizacao_cad` timestamp(6) NULL DEFAULT current_timestamp(6) ON UPDATE current_timestamp(6),
  `flag_ativo` varchar(1) DEFAULT 'S',
  PRIMARY KEY (`id_mad_pad`),
  KEY `id_usuariocad_fk_idx` (`id_usuario_cad`),
  CONSTRAINT `id_usuariocad_fk` FOREIGN KEY (`id_usuario_cad`) REFERENCES `auth_user` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tb_madrinha_padrinho`
--

LOCK TABLES `tb_madrinha_padrinho` WRITE;
/*!40000 ALTER TABLE `tb_madrinha_padrinho` DISABLE KEYS */;
INSERT INTO `tb_madrinha_padrinho` VALUES (2,3,'28946438886',NULL,'CLAYTON','BERNARDINO','RUA DOIS, 250','FUNDOS','JUNDIAPEBA','MOGI DAS CRUZES','SP','2026-05-19 19:17:45.495095','2026-05-19 19:23:11.771272','S'),(3,3,'12345678925',NULL,'PEDRO','CARDOSO','RUA BRASIL PARA CRISTO, 100','','CENTRO','MOGI DAS CRUZES','SP','2026-05-19 20:21:26.766777','2026-05-19 20:21:26.766777','S'),(4,2,'21364578984','N','ALOISIO','FRANCISCO E SILVA','TRAVESSA NOSSA SENHORA, 205','CASA 2','CENTRO','SAO PAOULO','SP','2026-05-19 23:07:48.911959','2026-05-19 23:07:48.911959','S');
/*!40000 ALTER TABLE `tb_madrinha_padrinho` ENABLE KEYS */;
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
