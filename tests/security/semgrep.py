import os
import subprocess


def run_semgrep_scan():
    # 1. Лечим ошибку кодировки 'charmap' в Windows
    os.environ["PYTHONUTF8"] = "1"

    # 2. Настройки путей
    target_dir = "backend"
    report_file = "semgrep_report.txt"

    # 3. Формируем команду
    # Мы используем --exclude для папок и --exclude-rule для конкретных проверок
    semgrep_cmd = [
        "semgrep",
        "scan",
        "--config",
        "auto",
        "--exclude",
        "**/tests/*",
        "--exclude",
        "**/benchmarks/*",
        # Исключаем аналог B110 (try-except-pass)
        "--exclude-rule",
        "python.lang.maintainability.useless-inner-function.try-except-pass",
        # Исключаем аналог B101 (assert)
        "--exclude-rule",
        "python.lang.security.audit.assert-used",
        "--text",  # Вывод в текстовом формате
        "-o",
        report_file,
        target_dir,
    ]

    print(f"🔍 Запускаю Semgrep в папке: {target_dir}...")
    print("Это может занять некоторое время (загрузка правил)...")

    try:
        # Запуск процесса с принудительной кодировкой utf-8
        result = subprocess.run(
            semgrep_cmd, capture_output=True, text=True, encoding="utf-8"
        )

        if result.returncode == 0:
            print(
                f"✅ Проверка завершена! Ошибок не найдено или все они проигнорированы."
            )
        elif result.returncode == 1:
            print(
                f"⚠️ Найдены потенциальные уязвимости. Проверьте файл: {report_file}"
            )
        else:
            print("❌ Ошибка при выполнении Semgrep:")
            print(result.stderr)

    except FileNotFoundError:
        print(
            "❌ Ошибка: Semgrep не установлен. Выполните: pip install semgrep"
        )
    except Exception as e:
        print(f"❌ Произошла ошибка: {e}")


if __name__ == "__main__":
    run_semgrep_scan()
