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
-- Table structure for table `tb_apadrinhamento_crianca`
--

DROP TABLE IF EXISTS `tb_apadrinhamento_crianca`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tb_apadrinhamento_crianca` (
  `id_apadrinhamento` int(11) NOT NULL AUTO_INCREMENT,
  `id_mad_pad` int(11) DEFAULT NULL,
  `id_filho` int(11) DEFAULT NULL,
  `data_cadastro` datetime(6) DEFAULT current_timestamp(6),
  `flag_ativo` varchar(1) DEFAULT 'S',
  PRIMARY KEY (`id_apadrinhamento`),
  KEY `fk_mad_pad_crianca_idx` (`id_mad_pad`),
  KEY `fk_crianca_idx` (`id_filho`),
  CONSTRAINT `fk_crianca` FOREIGN KEY (`id_filho`) REFERENCES `tb_filhos_responsavel` (`id_filho`) ON DELETE NO ACTION ON UPDATE NO ACTION,
  CONSTRAINT `fk_mad_pad_crianca` FOREIGN KEY (`id_mad_pad`) REFERENCES `tb_madrinha_padrinho` (`id_mad_pad`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tb_apadrinhamento_crianca`
--

LOCK TABLES `tb_apadrinhamento_crianca` WRITE;
/*!40000 ALTER TABLE `tb_apadrinhamento_crianca` DISABLE KEYS */;
INSERT INTO `tb_apadrinhamento_crianca` VALUES (1,3,8,'2026-05-19 18:14:38.860557','S'),(2,3,3,'2026-05-19 19:59:42.517909','S'),(3,2,7,'2026-05-19 20:02:27.299378','S'),(4,2,7,'2026-05-19 20:03:09.785769','S'),(5,2,7,'2026-05-19 20:03:55.160158','S'),(6,2,6,'2026-05-19 20:40:54.823213','S'),(7,2,6,'2026-05-19 20:42:44.347416','S'),(8,4,9,'2026-05-19 22:21:54.818481','S'),(9,3,5,'2026-05-19 22:44:30.744728','S'),(10,4,3,'2026-05-19 22:50:08.723076','S'),(11,4,9,'2026-05-20 21:06:30.885124','S'),(12,3,4,'2026-05-20 22:11:06.465768','S');
/*!40000 ALTER TABLE `tb_apadrinhamento_crianca` ENABLE KEYS */;
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
