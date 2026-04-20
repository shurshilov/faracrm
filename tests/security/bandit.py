import os
import subprocess


def run_security_scan():
    # 1. Решаем проблему с кодировкой (UTF-8 для Windows)
    os.environ["PYTHONUTF8"] = "1"

    # 2. Настраиваем параметры (можете менять под себя)
    target_dir = "backend"
    report_file = "report.html"

    # Исключаемые папки
    exclude_dirs = ["**/tests/*", "**/benchmarks/*", "**/.venv/*"]

    # Игнорируемые правила (B110 - try/except/pass, B101 - assert)
    skip_rules = "B110,B101"

    # 3. Формируем команду для Bandit
    # (HTML отчет поддерживается бандитом «из коробки»)
    bandit_cmd = [
        "bandit",
        "-r",
        target_dir,
        "-x",
        ",".join(exclude_dirs),
        "-s",
        skip_rules,
        "-f",
        "html",
        "-o",
        report_file,
    ]

    print(f"🚀 Запускаю проверку безопасности в папке: {target_dir}...")

    try:
        # Запускаем процесс
        result = subprocess.run(
            bandit_cmd, capture_output=True, text=True, encoding="utf-8"
        )

        if result.returncode == 0 or result.returncode == 1:
            # Bandit возвращает 1, если найдены уязвимости — это нормально
            print(f"✅ Проверка завершена. Отчет сохранен в: {report_file}")
        else:
            print("❌ Ошибка при выполнении сканирования:")
            print(result.stderr)

    except FileNotFoundError:
        print(
            "❌ Ошибка: Bandit не установлен. Попробуйте 'pip install bandit'"
        )
    except Exception as e:
        print(f"❌ Произошла непредвиденная ошибка: {e}")


if __name__ == "__main__":
    run_security_scan()
