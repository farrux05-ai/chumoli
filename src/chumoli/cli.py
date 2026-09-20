"""
chumoli.cli
============

Fundament (Bosqich 1) ustidagi eng yupqa CLI qobig'i.

NEGA BU FAYL "QOBIQ" DEB ATALADI, YANGI MANTIQ EMAS
--------------------------------------------------------
Har bir buyruq (`run`, `list`) faqat bitta narsa qiladi: argumentlarni
o'qiydi, mos fundament funksiyasini (`run_pipeline_by_name`,
`ControlStore.list_all`) chaqiradi, natijani inson o'qiy oladigan
qilib chop etadi. Hech qanday yangi biznes-mantiq bu yerda yo'q —
agar kimdir "run qanday ishlaydi" desa, javob `pipeline_runner.py`da,
bu faylda emas. Bu README.md dagi "Qo'lda sinab ko'rish" bo'limidagi
Python kodni terminal buyrug'iga aylantirishdan boshqa narsa emas.

NEGA Typer (Rich bilan birga)
----------------------------------
POSITIONING.md da CLI stack sifatida Typer + Rich belgilangan edi
("CLI (Typer+Rich)"). Bu fayl o'sha tanlovni davom ettiradi — yangi
qaror emas.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from chumoli.connectors import register_builtin_connectors
from chumoli.core.pipeline_runner import run_pipeline_by_name
from chumoli.store.control_store import ControlStore

app = typer.Typer(
    name="chumoli",
    help="Chumoli — O'zbekiston manbalari uchun lightweight EL tool.",
    add_completion=False,
)
console = Console()


@app.command("run")
def run(
    name: str = typer.Argument(..., help="Pipeline nomi (oldindan saqlangan bo'lishi kerak)"),
) -> None:
    """Saqlangan pipeline'ni bir marta ishga tushiradi.

    NEGA QUALITY CHECK MUVAFFAQIYATSIZLIGI HAM EXIT CODE'NI 1 QILADI
    --------------------------------------------------------------
    Load muvaffaqiyatli bo'lsa-yu, quality check muvaffaqiyatsiz
    bo'lsa (masalan kutilganidan kam qator keldi), bu holat CI/cron
    kontekstida "hammasi joyida" deb hisoblanmasligi kerak — aks
    holda quality check'ning butun maqsadi yo'qqa chiqadi (jim
    muvaffaqiyatsizlik). `RunResult.success` atayin faqat load
    holatini bildiradi (pipeline_runner.py dagi izohga qarang); exit
    code qarori shu yerda, chaqiruvchi darajada qabul qilinadi.
    """
    register_builtin_connectors()
    store = ControlStore()

    try:
        result = run_pipeline_by_name(name, store=store)
    except KeyError:
        console.print(f"[red]Xato:[/red] '{name}' nomli pipeline topilmadi.")
        console.print("Mavjud pipeline'larni ko'rish uchun: [bold]chumoli list[/bold]")
        raise typer.Exit(code=1)

    if not result.success:
        console.print(f"[red]✗[/red] '{name}' muvaffaqiyatsiz tugadi.")
        console.print(
            "Batafsil: [bold]dlt pipeline "
            f"{name} failed-jobs[/bold] buyrug'ini ishlating."
        )
        raise typer.Exit(code=1)

    console.print(f"[green]✓[/green] '{name}' muvaffaqiyatli tugadi.")
    if result.row_counts:
        table = Table(title="Yuklangan qatorlar")
        table.add_column("Jadval")
        table.add_column("Qator soni", justify="right")
        for table_name, count in result.row_counts.items():
            table.add_row(table_name, str(count))
        console.print(table)

    if result.quality_report.outcomes:
        quality_table = Table(title="Sifat tekshiruvlari")
        quality_table.add_column("Natija")
        quality_table.add_column("Tafsilot")
        for outcome in result.quality_report.outcomes:
            mark = "[green]✓[/green]" if outcome.passed else "[red]✗[/red]"
            quality_table.add_row(mark, outcome.detail)
        console.print(quality_table)

    if not result.quality_report.all_passed:
        console.print(
            f"[yellow]Ogohlantirish:[/yellow] '{name}' yuklandi, "
            "lekin sifat tekshiruvidan o'tmadi."
        )
        raise typer.Exit(code=1)


@app.command("list")
def list_pipelines() -> None:
    """Barcha saqlangan pipeline'larni ko'rsatadi (credentials KO'RSATILMAYDI)."""
    store = ControlStore()
    pipelines = store.list_all()

    if not pipelines:
        console.print(
            "Hozircha hech qanday pipeline saqlanmagan. "
            "Avval dashboard yoki Python API orqali biror pipeline yarating."
        )
        return

    table = Table(title="Chumoli pipeline'lari")
    table.add_column("Nom")
    table.add_column("Connector")
    table.add_column("Yangilangan")
    for p in pipelines:
        table.add_row(p["name"], p["connector_key"], p["updated_at"])
    console.print(table)



@app.command("ui")
def ui(
    host: str = typer.Option("127.0.0.1", help="Bind host"),
    port: int = typer.Option(8000, help="HTTP port"),
    open_browser: bool = typer.Option(
        True, "--open/--no-open", help="Brauzerni avtomatik ochish"
    ),
) -> None:
    """Dashboard UI ni ishga tushiradi va brauzerda ochadi.

    Ctrl+C bilan to'xtatiladi.
    """
    import threading
    import time
    import webbrowser

    import uvicorn

    url = f"http://{host}:{port}/"
    console.print(f"[bold]Chumoli UI[/bold] → {url}")
    console.print("To'xtatish: [dim]Ctrl+C[/dim]")

    if open_browser:

        def _open() -> None:
            # Server tinglashga ulgurishi uchun biroz kutamiz
            for _ in range(50):
                try:
                    import urllib.request

                    urllib.request.urlopen(f"http://{host}:{port}/api/health", timeout=0.3)
                    break
                except Exception:
                    time.sleep(0.1)
            try:
                webbrowser.open(url)
            except Exception:
                console.print(f"[yellow]Brauzer ochilmadi — qo'lda kiring:[/yellow] {url}")

        threading.Thread(target=_open, daemon=True).start()

    try:
        uvicorn.run(
            "chumoli.api.app:app",
            host=host,
            port=port,
            log_level="info",
        )
    except KeyboardInterrupt:
        console.print("\n[dim]Chumoli to'xtatildi.[/dim]")



def main() -> None:
    app()


if __name__ == "__main__":
    main()
