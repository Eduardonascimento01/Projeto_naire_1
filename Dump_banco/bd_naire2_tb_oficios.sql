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
-- Table structure for table `tb_oficios`
--

DROP TABLE IF EXISTS `tb_oficios`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tb_oficios` (
  `id_oficio` int(11) NOT NULL AUTO_INCREMENT,
  `data_criacao` timestamp(6) NULL DEFAULT current_timestamp(6),
  `id_usuario` int(11) NOT NULL,
  `destinatario` varchar(255) DEFAULT NULL,
  `mensagem` longtext DEFAULT NULL,
  PRIMARY KEY (`id_oficio`),
  KEY `id_usuario_oficio_fk_idx` (`id_usuario`),
  CONSTRAINT `id_usuario_oficio_fk` FOREIGN KEY (`id_usuario`) REFERENCES `auth_user` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tb_oficios`
--

LOCK TABLES `tb_oficios` WRITE;
/*!40000 ALTER TABLE `tb_oficios` DISABLE KEYS */;
INSERT INTO `tb_oficios` VALUES (6,'2026-05-19 17:18:46.613120',3,'JOSE PEREIRA','Mensagem de CLAYTON para JOSE PEREIRA: Queremos expressar nossa profunda gratidão pela sua doação à [nome da ONG]. Seu gesto de solidariedade é essencial para que possamos continuar levando esperança e apoio a quem mais precisa.\r \r Com a sua ajuda, conseguimos [exemplo: fornecer alimentação a 50 famílias / custear tratamentos de saúde / apoiar crianças com material escolar]. Cada contribuição faz a diferença e nos motiva a seguir em frente com nossa missão.\r \r Você não é apenas um doador(a), é parte da nossa rede do bem. Muito obrigado(a) por acreditar no nosso trabalho e por tornar o mundo um lugar mais justo e humano.\r \r Com gratidão,\r Equipe [nome da ONG]'),(8,'2026-05-20 01:35:28.288746',2,'PEDRO JOSE','Mensagem de CLAYTON para PEDRO JOSE: Parabéns! Que o seu dia seja incrível, repleto de sorrisos,\r\npaz e rodeado de pessoas especiais. Desejo que este novo ciclo\r\nchegue com muita saúde, amor e a realização dos seus maiores sonhos.\r\n\r\n\r\nAproveite muito o seu dia!'),(10,'2026-05-23 00:56:00.712391',2,'PATRICIA','Mensagem de ANTONIO para PATRICIA: Olá, Patricia, tudo bem?\r\nNós, da [Nome da sua causa/projeto], não podemos agradecer o suficiente pela sua generosidade. Recebemos sua doação de [Valor ou item doado] e queremos que saiba o quanto ela é importante para nós. O seu apoio nos ajudará diretamente a [mencione o objetivo, ex: custear as cirurgias do projeto / comprar as cestas básicas deste mês]. Sem pessoas como você, não conseguiríamos transformar essa realidade.Nosso muito obrigado! Acompanhe nossos resultados através do [Link do Instagram/Site do projeto].\r\n\r\nCom carinho, Diretoria/Instituto NAIRE');
/*!40000 ALTER TABLE `tb_oficios` ENABLE KEYS */;
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
