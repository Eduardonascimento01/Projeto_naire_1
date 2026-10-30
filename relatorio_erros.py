import argparse
import html
import subprocess
import sys
import tokenize
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
IGNORED_DIRECTORIES = {".git", ".venv", "venv", "ENV", "__pycache__", "node_modules"}


def check_python_syntax():
    errors = []
    checked_files = 0

    for path in sorted(ROOT.rglob("*.py")):
        relative_path = path.relative_to(ROOT)
        if IGNORED_DIRECTORIES.intersection(relative_path.parts):
            continue

        checked_files += 1
        try:
            with tokenize.open(path) as source_file:
                source = source_file.read()
            compile(source, str(relative_path), "exec")
        except SyntaxError as error:
            location = f":{error.lineno}" if error.lineno else ""
            errors.append(f"{relative_path}{location}: {error.msg}")
        except (OSError, UnicodeDecodeError) as error:
            errors.append(f"{relative_path}: não foi possível ler o arquivo: {error}")

    return checked_files, errors


def run_command(name, command, command_label):
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or ""
        stderr = error.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return {
            "name": name,
            "command": command_label,
            "passed": False,
            "output": f"Tempo limite de 5 minutos excedido.\n{stdout}\n{stderr}".strip(),
        }

    output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    return {
        "name": name,
        "command": command_label,
        "passed": result.returncode == 0,
        "output": output or "Sem mensagens.",
    }


def write_report(destination, syntax_result, command_results):
    checked_files, syntax_errors = syntax_result
    results = [
        {
            "name": "Sintaxe Python",
            "command": f"{checked_files} arquivo(s) analisado(s)",
            "passed": not syntax_errors,
            "output": "\n".join(syntax_errors) if syntax_errors else "Nenhum erro de sintaxe encontrado.",
        },
        *command_results,
    ]
    passed_count = sum(result["passed"] for result in results)
    failed_count = len(results) - passed_count

    lines = [
        "# Relatório de verificação do projeto",
        "",
        f"- Gerado em: {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')}",
        f"- Resultado: **{passed_count} aprovado(s), {failed_count} com erro**",
        "",
        "Esta verificação não executa o pentest nem altera o banco de dados. "
        "A suíte de testes do Django usa o banco de teste configurado pelo próprio Django.",
        "",
    ]

    for result in results:
        status = "APROVADO" if result["passed"] else "ERRO"
        lines.extend(
            [
                f"## {status}: {result['name']}",
                "",
                f"Comando: `{result['command']}`",
                "",
                "<details>",
                "<summary>Detalhes</summary>",
                "",
                f"<pre>{html.escape(result['output'])}</pre>",
                "</details>",
                "",
            ]
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines), encoding="utf-8")
    return passed_count, failed_count


def main():
    parser = argparse.ArgumentParser(
        description="Verifica sintaxe, configurações e testes do projeto Django."
    )
    parser.add_argument(
        "--saida",
        type=Path,
        default=ROOT / "relatorio_erros.md",
        help="caminho do relatório Markdown (padrão: relatorio_erros.md)",
    )
    args = parser.parse_args()
    destination = args.saida if args.saida.is_absolute() else ROOT / args.saida

    syntax_result = check_python_syntax()
    command_results = [
        run_command(
            "Checagens do Django",
            [sys.executable, "manage.py", "check"],
            "python manage.py check",
        ),
        run_command(
            "Testes do Django",
            [sys.executable, "manage.py", "test"],
            "python manage.py test",
        ),
    ]
    passed_count, failed_count = write_report(destination, syntax_result, command_results)

    print(f"Relatorio salvo em: {destination}")
    print(f"Resultado: {passed_count} aprovado(s), {failed_count} com erro.")
    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
