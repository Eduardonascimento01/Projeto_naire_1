import os
import django
import pandas as pd
from sklearn.ensemble import IsolationForest

# Conecta o script isolado ao núcleo do Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')
django.setup()

from gerencias.models import TbLogAuditoria

print("🔎 Coletando logs de acesso...")
logs = TbLogAuditoria.objects.all().values('id_log', 'usuario', 'acao', 'rota', 'data_hora', 'ip')
df = pd.DataFrame(logs)

if len(df) < 15:
    print("⚠️ Ainda não há dados suficientes para treinar a Inteligência Artificial.")
    print("Navegue mais pelo sistema abrindo várias páginas diferentes e tente novamente.")
else:
    print("🧠 Treinando o algoritmo Isolation Forest...")
    
    # 1. Engenharia de Recursos (Feature Engineering)
    # Transforma os dados de texto em números para a matemática da IA entender
    df['hora'] = df['data_hora'].dt.hour
    df['usuario_cod'] = df['usuario'].astype('category').cat.codes
    df['rota_cod'] = df['rota'].astype('category').cat.codes

    # 2. Configura e treina o modelo
    # contamination=0.1 significa que mandamos a IA procurar os 10% mais estranhos dos acessos
    modelo = IsolationForest(contamination=0.1, random_state=42)
    
    # A IA analisa a combinação: Quem acessou + Qual Rota + Que Horas
    df['anomalia'] = modelo.fit_predict(df[['usuario_cod', 'hora', 'rota_cod']])

    # 3. Filtra os resultados (-1 significa que a IA considerou uma anomalia)
    suspeitos = df[df['anomalia'] == -1]

    print("\n=======================================================")
    print(" RESULTADO DA AUDITORIA DE SEGURANÇA (LGPD)")
    print("=======================================================")
    
    if suspeitos.empty:
        print("✅ Nenhum comportamento suspeito detectado.")
    else:
        print("🚨 ALERTA: COMPORTAMENTOS ANÔMALOS DETECTADOS 🚨\n")
        for index, row in suspeitos.iterrows():
            data_formatada = row['data_hora'].strftime('%d/%m/%Y %H:%M:%S')
            print(f"[{data_formatada}] IP: {row['ip']} | Usuário: {row['usuario']} | Rota: {row['rota']}")
    print("=======================================================\n")