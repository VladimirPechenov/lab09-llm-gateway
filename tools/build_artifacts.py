"""Build six-page report, chart and video from measured JSON files."""

import json
import os
import textwrap
from pathlib import Path
from xml.sax.saxutils import escape

import imageio
import matplotlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image as PDFImage
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FONTDIR = Path(os.getenv("LAB_FONT_DIR", "C:/Windows/Fonts"))
REPO = "https://github.com/VladimirPechenov/lab09-llm-gateway"
BG, INK, ACCENT = "#f3f6fa", "#18304b", "#087d84"


def font(size):
    return ImageFont.truetype(str(FONTDIR / "arial.ttf"), size)


def draw_wrapped(draw, text, xy, width=75, size=24, color=INK):
    x, y = xy
    for source in text.splitlines():
        for line in textwrap.wrap(source, width=width, break_long_words=True) or [""]:
            draw.text((x, y), line, font=font(size), fill=color)
            y += size + 10
    return y


def demo_frame(scene, index, progress=1):
    im = Image.new("RGB", (1280, 800), BG)
    d = ImageDraw.Draw(im)
    d.text((35, 25), "ЛР 9 · LLM gateway для диалогов NPC", font=font(34), fill=INK)
    d.text((35, 78), scene["title"], font=font(27), fill=ACCENT)
    d.rounded_rectangle((30, 125, 1250, 700), radius=15, fill="white")
    y = draw_wrapped(d, "POST /v1/chat  ·  provider=mock  ·  Redis", (55, 145), size=23)
    y = draw_wrapped(d, json.dumps(scene["request"], ensure_ascii=False), (55, y + 12), width=82, size=23)
    d.text((55, y + 14), f"HTTP {scene['status']}", font=font(28), fill="#b54439" if scene["status"] >= 400 else ACCENT)
    y += 60
    response = json.dumps(scene["response"], ensure_ascii=False, indent=2)
    draw_wrapped(d, response, (55, y), width=91, size=21)
    d.text((35, 724), "Визуализация сохранённых API-ответов; сбои провайдера внедрены явно.", font=font(21), fill=INK)
    d.rectangle((35, 770, 1245, 778), fill="#dbe4ec")
    d.rectangle((35, 770, 35 + int(1210 * progress), 778), fill=ACCENT)
    d.text((1100, 25), f"{index + 1} / 11", font=font(23), fill=INK)
    return im


def architecture():
    im = Image.new("RGB", (1400, 450), "white")
    d = ImageDraw.Draw(im)
    boxes = [
        (25, 40, "Игра / API key"),
        (360, 40, "Auth → token bucket"),
        (695, 40, "Входной фильтр"),
        (1030, 40, "Router / Redis cache"),
        (1030, 265, "LLM → retry → fallback"),
        (695, 265, "Выходной фильтр"),
        (360, 265, "Кеш / JSON-ответ"),
        (25, 265, "Логи / Prometheus"),
    ]
    for x, y, label in boxes:
        d.rounded_rectangle((x, y, x + 310, y + 105), radius=12, fill=BG, outline=ACCENT, width=3)
        draw_wrapped(d, label, (x + 15, y + 28), width=21, size=24)
    for a, b in [
        ((335, 92), (360, 92)),
        ((670, 92), (695, 92)),
        ((1005, 92), (1030, 92)),
        ((1185, 145), (1185, 265)),
        ((1030, 317), (1005, 317)),
        ((695, 317), (670, 317)),
        ((360, 317), (335, 317)),
    ]:
        d.line((a, b), fill=ACCENT, width=4)
    d.text(
        (40, 405),
        "Cache hit возвращает проверенный ответ без вызова LLM. Redis недоступен → HTTP 503.",
        font=font(24),
        fill=INK,
    )
    im.save(ROOT / "docs/img/architecture.png")


def chart(data):
    runs = data["runs"]
    names = ["Без кеша", "С кешем"]
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.4))
    for ax, key, title in zip(
        axes,
        ["p95_ms", "throughput_rps", "cache_hit_percent"],
        ["p95, мс", "Запросов / с", "Попадания в кеш, %"],
        strict=True,
    ):
        vals = [runs[x][key] for x in ("no_cache", "with_cache")]
        bars = ax.bar(names, vals, color=["#778da6", "#087d84"], width=0.55)
        ax.set_title(title)
        ax.set_ylim(0, max(vals) * 1.3 if max(vals) else 1)
        ax.spines[["top", "right"]].set_visible(False)
        ax.bar_label(bars, fmt="%.2f", padding=5)
    fig.suptitle("Locust: 50 пользователей × 300 с; mock LLM, задержка 150 мс")
    fig.tight_layout()
    fig.savefig(ROOT / "docs/img/benchmark.png", dpi=180)
    plt.close(fig)


def sections(data, demo):
    a, b = data["runs"]["no_cache"], data["runs"]["with_cache"]
    first, second = demo[1]["response"], demo[2]["response"]
    return [
        (
            "1. Цель работы и постановка задачи",
            [
                "Лабораторная работа № 9. Интеграция API LLM в игровой компонент.",
                "Дисциплина: «Игровой искусственный интеллект». Студент: Печенов В. В., группа ИВТ-465. Дата: 17.11.2026. Стек: Python 3.12, FastAPI, Redis 7, Docker Compose, Locust, Prometheus.",
                "Цель: создать сервер-посредник между игровым клиентом и языковой моделью, который управляет доступом, нагрузкой и повторным использованием ответов. Компонент предназначен для диалогов торговца Барта и стражницы Ирмы.",
                "2. Постановка задачи",
                "Нужно реализовать аутентификацию клиентов, ограничитель частоты в Redis, маршрутизацию запросов, Redis-кеш, входную и выходную модерацию, timeout, повторные попытки и резервный ответ. Дополнительно требуются журналирование, нагрузочные измерения latency/throughput/cache hit, контейнерный запуск и материалы сдачи.",
                "Работа выполнена в собственной копии шаблона преподавателя с последовательными коммитами step-1 и далее. Предусмотрены тег v1.0 и GitHub Release. Исходный шаблон сохранён в истории.",
                "Выбран разрешённый заданием автономный режим LLM_PROVIDER=mock с искусственной задержкой 150 мс. В нём нет вызовов платного API: возвращаются фиксированные реплики NPC, а поля model показывают решение маршрутизатора. Качество генеративного диалога этим экспериментом не измеряется.",
                "Отдельные методические указания и официальный титульный лист не предоставлены; пользователь подтвердил, что вводные ограничены репозиторием. Использованы опубликованные разделы отчёта и объём 5–7 страниц. ФИО преподавателя не выдумывается; соответствие неизвестному кафедральному шаблону не заявляется.",
            ],
        ),
        (
            "3. Описание реализации: API и Redis",
            [
                "FastAPI предоставляет POST /v1/chat, GET /health, GET /metrics и интерактивную схему /docs. Вход содержит npc из списка trader/guard и непустую строку message до 4000 символов. Некорректная структура возвращает 422, отсутствующий либо неверный X-API-Key - 401.",
                "Ключ сравнивается через compare_digest. В Redis используется SHA-256 отпечаток ключа, а в журнале - первые 12 символов отпечатка. Секрет и текст диалога в журнал не записываются. Клиенту возвращается X-Request-ID для поиска события.",
                "Token bucket реализован одним Lua-скриптом: Redis TIME задаёт часы, HMGET/HSET сохраняют остаток токенов и время, EXPIRE удаляет неактивные корзины через 120 с. Ёмкость равна RATE_LIMIT_PER_MIN, скорость пополнения - capacity/60 токенов в секунду. Это общий лимит для всех процессов с одним Redis.",
                "При исчерпании токенов возвращаются 429 и Retry-After. При значении 30 мгновенный burst допускает 30 запросов, затем новый токен появляется примерно каждые 2 с. Это непрерывное пополнение, а не строгое скользящее окно на 60 с.",
                "Маршрутизатор выбирает strong_model для текста длиннее 200 символов или содержащего «почему», «объясни», «расскажи историю», «план». Остальные сообщения идут в cheap_model. Это прозрачная эвристика; она не определяет смысловую сложность безошибочно.",
                "Ключ кеша - SHA-256 JSON-массива из версии промпта, провайдера, роли NPC, текста, выбранной и резервной моделей. Сохраняются регистр и разделители: разные реплики не склеиваются. SET с EX задаёт TTL 3600 с. Счётчики hit/miss живут в Redis и видны в /health.",
            ],
        ),
        (
            "3. Надёжность, фильтрация и наблюдаемость",
            [
                "Порядок обработки: auth → token bucket → входной фильтр → routing → cache → LLM → выходной фильтр → cache write → ответ. Поэтому запрещённое сообщение не может обойти проверку через кеш, а попадания в кеш тоже расходуют лимит клиента.",
                "Нормализация Unicode NFKC и casefold предшествует проверке блок-листа. На входе блокируются демонстрационные фразы обхода инструкций и запрещённые темы. Небезопасный либо пустой выход заменяется нейтральной репликой с moderated=true. Такой ответ не сохраняется в кеше.",
                "SDK OpenAI и Anthropic получают ограничение timeout и max_retries=0. Повторы управляются только gateway: до 3 попыток на модель, паузы 0.1 и 0.2 с. Повторяются сетевые ошибки, timeout, 408/409/429 и 5xx. Остальные ошибки, включая 401, переходят к fallback без бесполезных повторов.",
                "После отказа основной модели используется FALLBACK_MODEL, затем fallback-static. Дублирование одной и той же модели исключено. Неверный ключ провайдера обычно лишает доступа ко всем его моделям, поэтому последним резервом служит статическая реплика. degraded=true и attempts делают эту ситуацию явной.",
                "Резервные ответы не кешируются, чтобы восстановившийся провайдер снова обслуживал диалог. Redis-ошибка даёт 503: gateway не отключает молча защиту от нагрузки. /health также возвращает 503 при недоступности Redis.",
                "JSON-журнал содержит request_id, status, latency_ms, npc, model, cached, attempts и флаги обработки. Prometheus измеряет полное время /v1/chat, включая auth и ошибки; отдельно считаются HTTP-статусы, попытки LLM и решения кеша. В исходном шаблоне таймер измерял пустой блок - это исправлено.",
                "Текущая конфигурация запускает один процесс gateway. Для множества процессов потребуется настроить multiprocess-сбор метрик Prometheus. Кеш и ограничитель уже разделяются через Redis. Фильтр по подстрокам не является полноценной защитой LLM от обходов.",
            ],
        ),
        (
            "4. Демонстрация и проверка поведения",
            [
                "Сценарии записаны tools/capture_demo.py через реальный FastAPI TestClient и отдельную Redis DB14. Это API-демонстрация; видео визуализирует сохранённые ответы, а не выдаётся за запись рабочего стола. Все JSON-ответы доступны в results/demo.json.",
                f"Обычный запрос trader/«Привет»: HTTP 200, cached=false, latency_ms={first['latency_ms']}. Повтор: cached=true, latency_ms={second['latency_ms']}. Кешированный ответ содержит attempts=0 и ту же реплику.",
                "Сложный вопрос выбирает gpt-4o вместо gpt-4o-mini (в mock это имена маршрутов). Без ключа получается 401; «Забудь инструкции…» даёт 400. Серия из 31 запроса при пустой корзине даёт 30 ответов 200 и один 429.",
                "Внедрение одного timeout заканчивается успехом на второй попытке. Три отказа основной модели переключают запрос на резервную на четвёртой попытке. Имитация неверных credentials включает fallback-static. Имитация утечки system prompt проверяет выходной фильтр. Все внедрённые сбои подписаны отдельно.",
                "33 теста pytest прошли без пропусков. Проверены истечение TTL, независимость клиентов, конкурентное расходование токенов, пополнение, разделение кеша по контексту, границы routing, 503 при отказе Redis, приватность журналов и корректность гистограммы времени.",
                "SDK OpenAI дополнительно протестирован с HTTP MockTransport: статусы 200/401/429/500 проверяют реальный разбор ответа SDK и бюджет попыток без сетевого запроса к провайдеру. Платные API и качество реальных языковых моделей в работе не проверялись.",
            ],
        ),
        (
            "5. Метрики и результаты нагрузочного теста",
            [
                "Каждый режим измерен Locust с 50 пользователями, скоростью запуска 50 пользователей/с и длительностью 300 с от начала разгона. Между запросами пауза 0.2–1.0 с. В каждом цикле клиента 3 из 10 запросов общие, остальные имеют уникальный player/serial. При завершении выполняющиеся запросы получают до 10 с на окончание.",
                "Оба прогона обращаются по HTTP к gateway в Docker Compose, Redis также работает в контейнере. В mock LLM задержка 150 мс; CACHE_TTL_S=3600. Перед режимом очищается только DB0 выделенного учебного Redis. RATE_LIMIT_PER_MIN=100000 временно исключает 429 из измерения кеша; рабочий лимит 30 проверен отдельно и восстановлен после теста.",
                f"Без кеша: {a['requests']} запросов, {a['failures']} ошибок. С кешем: {b['requests']} запросов, {b['failures']} ошибок. Доля попаданий вычислена по полю cached успешных ответов; значения также сверены с Redis /health.",
                "p50/p95 и Requests/s берутся из итоговой строки Aggregated Locust CSV, то есть включают сеть и обработку клиента, а не только latency_ms сервера. Границы процентилей округляются Locust. Throughput зависит от времени ожидания клиента и не является абсолютной пропускной способностью сервера.",
                "Один прогон на режим не позволяет оценить доверительный интервал. Постоянная задержка заглушки не моделирует очереди, токены, стоимость и распределение времени реального API. Полученные числа относятся только к данной конфигурации; они не повторяют примерные числа преподавателя.",
            ],
        ),
        (
            "6. Выводы и 7. Список литературы",
            [
                "Создан воспроизводимый шлюз для игровых диалогов, отделяющий ключи провайдера от клиента. Redis обеспечивает общий ограничитель и кеш. Фильтры, валидация и метаданные ответов позволяют контролировать обработку запроса. Повторные попытки и резервная ветка сохраняют работоспособность при сбое LLM.",
                f"Нагрузочное измерение показало {b['cache_hit_percent']:.2f}% попаданий в кеш при целевой доле 30% общих запросов; throughput изменился с {a['throughput_rps']:.2f} до {b['throughput_rps']:.2f} запросов/с. Эффект нужно интерпретировать с учётом пауз клиента и фиксированной задержки mock.",
                "Тесты и Docker smoke-test выполняются в GitHub Actions; матрица Python 3.11/3.12 использует настоящий Redis. JUnit сохраняется как артефакт. В репозитории есть исходный CSV, метрики Prometheus, демонстрационный протокол, график и пошаговая история.",
                "Дальнейшее развитие: семантическая модерация, лимиты стоимости и токенов, общий deadline запроса, защита от stampede одновременных cache miss, независимый резервный провайдер, секреты через менеджер, TLS и закрытие /metrics на внешнем периметре.",
                "7. Список литературы",
                "1. Шаблон ЛР9 и требования: https://github.com/kolesnikov-vstu-gameai/lab09-llm-gateway",
                "2. FastAPI, Testing Dependencies: https://fastapi.tiangolo.com/advanced/testing-dependencies/",
                "3. Redis, Scripting with Lua: https://redis.io/docs/latest/develop/programmability/eval-intro/",
                "4. OpenAI Python SDK, timeout/retries: https://github.com/openai/openai-python",
                "5. Locust, headless mode: https://docs.locust.io/en/stable/running-without-web-ui.html",
                "Приложение. Репозиторий и воспроизводимость",
                REPO,
                "Запуск: скопировать .env.example в .env; docker compose up -d --build --wait. Для тестов: pip install -r requirements.txt; pytest. Для повторения замеров: python -X utf8 tools/benchmark.py. Перед FLUSHDB использовать отдельный учебный Redis; чужие данные в DB0 недопустимы.",
                "Исходники отчёта: docs/report.md. Генератор PDF и видео: tools/build_artifacts.py. Отдельный архив сдачи и PDF приложены к Release v1.0; MP4 публикуется на Google Диске, ссылка приведена в README.",
            ],
        ),
    ]


def table_data(data):
    a, b = data["runs"]["no_cache"], data["runs"]["with_cache"]
    return [
        ["Метрика", "Без кеша", "С кешем"],
        ["p50 latency, мс", f"{a['p50_ms']:.2f}", f"{b['p50_ms']:.2f}"],
        ["p95 latency, мс", f"{a['p95_ms']:.2f}", f"{b['p95_ms']:.2f}"],
        ["Throughput, req/s", f"{a['throughput_rps']:.2f}", f"{b['throughput_rps']:.2f}"],
        ["Cache hit, %", f"{a['cache_hit_percent']:.2f}", f"{b['cache_hit_percent']:.2f}"],
    ]


def main():
    data = json.loads((ROOT / "results/benchmark.json").read_text(encoding="utf-8"))
    demo = json.loads((ROOT / "results/demo.json").read_text(encoding="utf-8"))
    architecture()
    chart(data)
    demo_frame(demo[2], 2).save(ROOT / "docs/img/demo.png")
    pdfmetrics.registerFont(TTFont("Arial", str(FONTDIR / "arial.ttf")))
    pdfmetrics.registerFont(TTFont("ArialBold", str(FONTDIR / "arialbd.ttf")))
    normal = ParagraphStyle("body", fontName="Arial", fontSize=10.5, leading=14.7, spaceAfter=9)
    heading = ParagraphStyle("heading", fontName="ArialBold", fontSize=16, leading=20, spaceAfter=15)
    small = ParagraphStyle("small", parent=normal, fontSize=9, leading=12)
    story, markdown = [], ["# Отчёт по лабораторной работе № 9\n"]
    for i, (title, paragraphs) in enumerate(sections(data, demo)):
        if i:
            story.append(PageBreak())
        story.append(Paragraph(escape(title), heading))
        markdown.append("## " + title + "\n")
        for j, text in enumerate(paragraphs):
            story.append(Paragraph(escape(text), small if i == 5 and j >= 5 else normal))
            markdown.append(text + "\n")
            if i == 1 and j == 0:
                story.extend(
                    [PDFImage(str(ROOT / "docs/img/architecture.png"), width=170 * mm, height=54.6 * mm), Spacer(1, 8)]
                )
            if i == 3 and j == 1:
                story.extend(
                    [PDFImage(str(ROOT / "docs/img/demo.png"), width=165 * mm, height=103.1 * mm), Spacer(1, 8)]
                )
            if i == 4 and j == 2:
                cells = [[Paragraph(escape(str(x)), small) for x in row] for row in table_data(data)]
                table = Table(cells, colWidths=[80 * mm, 45 * mm, 45 * mm])
                table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5f2f2")),
                            ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
                            ("TOPPADDING", (0, 0), (-1, -1), 5),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                        ]
                    )
                )
                story.extend(
                    [
                        table,
                        Spacer(1, 10),
                        PDFImage(str(ROOT / "docs/img/benchmark.png"), width=170 * mm, height=52.5 * mm),
                    ]
                )
                markdown.extend(["\n| Метрика | Без кеша | С кешем |", "|---|---:|---:|"])
                markdown.extend("| " + " | ".join(row) + " |" for row in table_data(data)[1:])
                markdown.append("\n")

    def footer(canvas, doc):
        canvas.setFont("Arial", 9)
        canvas.setFillColor(colors.HexColor(INK))
        canvas.drawString(20 * mm, 12 * mm, "Печенов В. В. · ИВТ-465 · ЛР 9 · 17.11.2026")
        canvas.drawRightString(190 * mm, 12 * mm, str(doc.page))

    SimpleDocTemplate(
        str(ROOT / "docs/report.pdf"),
        pagesize=(210 * mm, 297 * mm),
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title="Лабораторная работа №9 — Печенов В. В.",
    ).build(story, onFirstPage=footer, onLaterPages=footer)
    (ROOT / "docs/report.md").write_text("\n".join(markdown), encoding="utf-8")
    (ROOT / "videos").mkdir(exist_ok=True)
    with imageio.get_writer(
        str(ROOT / "videos/lab09_demo.mp4"), fps=2, codec="libx264", quality=8, macro_block_size=16
    ) as writer:
        for i, scene in enumerate(demo):
            for frame in range(20):
                writer.append_data(np.asarray(demo_frame(scene, i, (frame + 1) / 20)))
    (ROOT / "videos/chapters.json").write_text(
        json.dumps(
            [{"start_s": i * 10, "title": s["title"]} for i, s in enumerate(demo)], ensure_ascii=False, indent=2
        ),
        encoding="utf-8",
    )
    print("Built report, chart and 110-second API demonstration")


if __name__ == "__main__":
    main()
