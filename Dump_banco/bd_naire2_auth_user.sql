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
-- Table structure for table `auth_user`
--

DROP TABLE IF EXISTS `auth_user`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_user` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `password` varchar(128) NOT NULL,
  `last_login` datetime(6) DEFAULT NULL,
  `is_superuser` tinyint(1) NOT NULL,
  `username` varchar(150) NOT NULL,
  `first_name` varchar(150) NOT NULL,
  `last_name` varchar(150) NOT NULL,
  `email` varchar(254) NOT NULL,
  `is_staff` tinyint(1) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `date_joined` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_user`
--

LOCK TABLES `auth_user` WRITE;
/*!40000 ALTER TABLE `auth_user` DISABLE KEYS */;
INSERT INTO `auth_user` VALUES (1,'pbkdf2_sha256$1200000$J1lFxmZNVY71JIIY8MNOW4$i8w4lsnYXNTLvc68/4sOgUAyEUIiOpGcnsnmGcUVJ/4=',NULL,0,'clayton.sousa','','','',0,1,'2026-05-17 19:46:06.706553'),(2,'pbkdf2_sha256$1200000$vePTnE8QJ7UavPgyDNk1kW$XFvPqGmbYGefr6WFjr/GKk/xBQwL1Uso2pVbs0thXnw=','2026-05-23 00:17:49.445943',0,'clayton','','','',0,1,'2026-05-17 19:46:36.544597'),(3,'pbkdf2_sha256$1200000$8Mv4ChCYsNM2DHzNuA9LqV$0ZJWroonI0hb6mvRQef6v4EJhhs3seTK6MtzS5jJXLE=','2026-05-19 17:02:26.787911',0,'pedro','','','',0,1,'2026-05-17 20:23:06.352319'),(4,'pbkdf2_sha256$1200000$NdObNYk8ODiOcahup8c62n$xFm7gusPgQCErT6ybP0/i4IKrJARD7xZoqOaeepisXY=','2026-05-19 00:46:20.270683',0,'teste1','','','',0,1,'2026-05-19 00:46:09.181236'),(5,'pbkdf2_sha256$1200000$ubOzIAzaQQEYBQ9ZWczFvG$MdA5ZnluOTyMLjPuqxHkLDz20CHM/WH281XOsIS5+Gg=','2026-05-20 00:49:17.220532',0,'gabriel','','','',0,1,'2026-05-20 00:49:07.798187'),(6,'pbkdf2_sha256$1200000$R1REGZMscpIwlH1mVIlNQH$6CPR/sVXRM2dQAZ7PT2+5Bizit8KVGOPrFasoryxR2c=','2026-05-20 01:19:39.053299',0,'annita','','','',0,1,'2026-05-20 01:19:29.366245'),(7,'pbkdf2_sha256$1200000$2kQZ1XhORC2wXuVLrUvq5N$/QHfKZUYW64O3sKmEONCbUypdAaB/ogvD50ciGW8oGE=','2026-05-20 01:47:12.901969',0,'fulano','','','',0,1,'2026-05-20 01:46:41.047792'),(8,'pbkdf2_sha256$1200000$HfC4vlXxwuM9cew7VYtF9d$okBs3VAHRwjCc58VtgdOoj3WbUrMGGSSScXKz1ZGVKg=','2026-05-21 17:15:08.010828',0,'samuel','','','',0,1,'2026-05-21 17:14:59.391439');
/*!40000 ALTER TABLE `auth_user` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-05-23  5:17:45
