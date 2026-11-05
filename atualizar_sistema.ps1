Write-Host "=================================================" -ForegroundColor Cyan
Write-Host " INICIANDO ESTEIRA DE ATUALIZAÇÃO SEGURA (NAIRE) " -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

# 1. Inicia o servidor em segundo plano (background)
Write-Host "[1/3] Ligando o servidor local..." -ForegroundColor Yellow
$serverProcess = Start-Process -FilePath "python" -ArgumentList "manage.py runserver" -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 4 # Aguarda o servidor ligar

# 2. Executa a varredura do Agente Hacker
Write-Host "[2/3] Rodando Pentest Automatizado..." -ForegroundColor Yellow
python pentest_naire.py

# 3. Desliga o servidor que estava em segundo plano
Write-Host "[3/3] Desligando o servidor de testes..." -ForegroundColor Yellow
Stop-Process -Id $serverProcess.Id -Force

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host " VARREDURA CONCLUÍDA. " -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

# 4. Pergunta se deseja enviar para o GitHub
$resposta = Read-Host "Os testes de segurança passaram? Deseja enviar o código para o GitHub? (S/N)"

if ($resposta -eq 'S' -or $resposta -eq 's') {
    $mensagem = Read-Host "Digite o resumo dessa atualização (Commit)"
    git add .
    git commit -m "$mensagem"
    git push origin minhas-sugestoes
    Write-Host "Código enviado com sucesso e segurança garantida!" -ForegroundColor Green
} else {
    Write-Host "Atualização cancelada pelo usuário. Corrija as vulnerabilidades e tente novamente." -ForegroundColor Red
}