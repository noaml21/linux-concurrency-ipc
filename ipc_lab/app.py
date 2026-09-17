"""Textual front end. All benchmark work is delegated to the C CLI runner."""

import asyncio
import time
from pathlib import Path

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button, Checkbox, DataTable, Footer, Header, Input, Label, ProgressBar,
    RichLog, Select, SelectionList, Sparkline, Static, TabbedContent, TabPane,
)

from .models import Config, MODES, RING_CAPACITIES, parse_integer
from .presentation import detail, rate, relative_bar
from .records import Run
from .runner import Progress, run_experiment
from .storage import History, compare_runs


ROOT = Path(__file__).resolve().parent.parent


class LabApp(App):
    TITLE = "Linux Concurrency & IPC Lab"
    SUB_TITLE = "C engine · live experiments"
    CSS_PATH = "lab.tcss"
    BINDINGS = [
        Binding("ctrl+r", "start", "Run"),
        Binding("ctrl+x", "cancel", "Cancel"),
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+c", "quit", show=False, priority=True),
    ]

    def __init__(self, binary: Path = ROOT / "build/linux-concurrency-ipc-release",
                 history_dir: Path = ROOT / "results/lab"):
        super().__init__()
        self.binary = binary
        self.history = History(history_dir)
        self.running = False
        self.cancel_event = asyncio.Event()
        self.current: Run | None = None
        self.runs: dict[str, Run] = {}
        self.baseline: Run | None = None
        self.current_case_started = 0.0
        self.current_case_label = ""
        self.last_error = ""
        self.quit_pending = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("EXPERIMENT / OBSERVE / UNDERSTAND", id="brand")
        with TabbedContent(initial="configure", id="tabs"):
            with TabPane("Configure", id="configure"):
                with VerticalScroll(id="form"):
                    yield Static("Choose a workload. Measure correctness and throughput together.", classes="lead")
                    with Horizontal(id="choices"):
                        with Vertical(classes="choice"):
                            yield Label("Experiment family")
                            yield Select([("IPC · record transport", "ipc"),
                                          ("Sync · shared counters", "sync")],
                                         value="ipc", allow_blank=False, id="family")
                            yield Static("Select mechanisms with Space.\nTab moves between fields.", classes="hint")
                        with Vertical(classes="choice"):
                            yield Label("Mechanisms")
                            yield SelectionList(*[(mode, mode, True) for mode in MODES["ipc"]], id="mechanisms")
                    with Horizontal(id="parameters"):
                        for label, value, ident in (("Workers / producers", "2", "workers"),
                                                    ("Items per worker", "2000", "amount"),
                                                    ("Repetitions", "3", "repetitions"),
                                                    ("Ring capacity", "64", "capacity")):
                            with Vertical(classes="parameter"):
                                yield Label(label)
                                yield Input(value, id=ident, select_on_focus=True)
                    yield Checkbox("Sweep shm-ring capacity", id="sweep")
                    yield Input(", ".join(map(str, RING_CAPACITIES)), id="capacities", disabled=True)
                    yield Static("Limits: 32 workers, 200,000 items per execution, 15 repetitions; 5M items per experiment.\nCancellation finishes the active execution so the engine can clean up.", classes="hint")
                yield Static("Ready · default workload runs all four IPC mechanisms.", id="validation", markup=False)
                with Horizontal(classes="actions"):
                    yield Button("Run experiment", variant="primary", id="run")
            with TabPane("Live", id="live"):
                yield Static("Ready to execute", id="live-current", markup=False)
                yield ProgressBar(total=1, show_eta=False, id="progress")
                yield Static("Completed 0 · failures 0", id="live-counts", markup=False)
                yield RichLog(id="events", wrap=True, markup=False, highlight=False)
                yield Static("Progress counts completed executions; the C CLI reports only when a case finishes.", classes="hint")
                with Horizontal(classes="actions"):
                    yield Button("Cancel after current", variant="warning", id="cancel", disabled=True)
            with TabPane("Results", id="results"):
                with VerticalScroll():
                    yield Static("No experiment yet. Configure a run or open one from History.", id="result-title", markup=False)
                    yield Static("Median / minimum / maximum • rates use accepted samples only", id="summary-hint")
                    yield DataTable(id="summary", cursor_type="row", zebra_stripes=True)
                    yield Static("Select a result row to inspect correctness.", id="detail", markup=False)
                    yield Label("Accepted throughput samples · execution order")
                    yield Sparkline([], id="samples", summary_function=max)
                    yield Static("Counters are totals across parsed repetitions. Bars compare medians within this run.\nEnvironment, workload and scheduling affect timings; no significance claim is implied.", classes="hint")
                    yield RichLog(id="raw", wrap=True, markup=False, highlight=False)
                with Horizontal(classes="actions"):
                    yield Button("Export summary CSV", id="export", disabled=True)
                    yield Button("Save run again", id="save", disabled=True)
                yield Static("", id="result-message", markup=False)
            with TabPane("History", id="history"):
                with VerticalScroll():
                    yield Static("Local runs · select a row, then open or pin it for comparison", classes="lead")
                    yield DataTable(id="history-table", cursor_type="row", zebra_stripes=True)
                    with Horizontal(classes="actions"):
                        yield Button("Open", id="open-history")
                        yield Button("Pin baseline", id="pin")
                        yield Button("Compare", id="compare")
                        yield Button("Refresh", id="refresh")
                    yield Static("No baseline pinned.", id="history-message", markup=False)
                    yield Static("", id="metadata", markup=False)
                    yield DataTable(id="comparison", cursor_type="row", zebra_stripes=True)
                    yield Static("Comparison requires identical configuration, engine and system metadata.\nDelta is descriptive; it does not establish a performance improvement.", classes="hint")
        yield Footer()

    def on_mount(self) -> None:
        self.theme = "textual-dark"
        self.query_one("#summary", DataTable).add_columns("Mechanism / capacity", "n", "Median/s", "Min/s", "Max/s", "State", "Relative median")
        self.query_one("#history-table", DataTable).add_columns("Started (UTC)", "State", "Family", "Workload", "Done", "Run")
        self.query_one("#comparison", DataTable).add_columns("Mechanism / capacity", "Baseline/s", "Selected/s", "Delta")
        self.refresh_history()
        self.set_interval(1, self.update_elapsed)

    @on(Select.Changed, "#family")
    def family_changed(self, event: Select.Changed) -> None:
        modes = MODES[str(event.value)]
        selections = self.query_one("#mechanisms", SelectionList)
        selections.clear_options()
        selections.add_options([(mode, mode, True) for mode in modes])
        sync = event.value == "sync"
        self.query_one("#capacity", Input).disabled = sync
        self.query_one("#sweep", Checkbox).disabled = sync
        if sync:
            self.query_one("#sweep", Checkbox).value = False

    @on(Checkbox.Changed, "#sweep")
    def sweep_changed(self, event: Checkbox.Changed) -> None:
        self.query_one("#capacities", Input).disabled = not event.value
        if event.value:
            self.query_one("#mechanisms", SelectionList).select("shm-ring")

    def read_config(self) -> Config:
        def number(ident: str, maximum: int) -> int:
            return parse_integer(self.query_one(f"#{ident}", Input).value, ident.capitalize(), maximum)

        family = str(self.query_one("#family", Select).value)
        selected = self.query_one("#mechanisms", SelectionList).selected
        sweep = ()
        if self.query_one("#sweep", Checkbox).value:
            sweep = tuple(parse_integer(value, "Sweep capacity", 32767)
                          for value in self.query_one("#capacities", Input).value.split(","))
        return Config(family, tuple(mode for mode in MODES[family] if mode in selected),
                      number("workers", 32), number("amount", 100000),
                      number("repetitions", 15), number("capacity", 32767) if family == "ipc" else 64,
                      sweep)

    @on(Button.Pressed, "#run")
    def action_start(self) -> None:
        if self.running:
            return
        try:
            config = self.read_config()
            if not self.binary.is_file():
                raise ValueError("Release binary missing. Run make release, then try again.")
        except ValueError as error:
            self.last_error = str(error)
            self.query_one("#validation", Static).update(self.last_error)
            self.query_one("#tabs", TabbedContent).active = "configure"
            return
        self.last_error = ""
        self.running = True
        self.cancel_event = asyncio.Event()
        self.query_one("#run", Button).disabled = True
        self.query_one("#cancel", Button).disabled = False
        self.query_one("#validation", Static).update(f"Running {config.total} executions · {config.workers} × {config.amount:,} items each")
        self.query_one("#progress", ProgressBar).update(total=config.total, progress=0)
        self.query_one("#events", RichLog).clear()
        self.query_one("#live-counts", Static).update(f"Completed 0/{config.total} · failures 0")
        self.query_one("#tabs", TabbedContent).active = "live"
        self.perform_run(config)

    @work
    async def perform_run(self, config: Config) -> None:
        try:
            run = await run_experiment(config, self.binary, self.cancel_event, self.progress_changed)
            self.show_results(run)
            try:
                path = await asyncio.to_thread(self.history.save, run)
                message = f"Saved {path}"
            except (OSError, ValueError) as error:
                message = f"History save failed: {error}. Results retained; use Save run again."
            self.query_one("#result-message", Static).update(message)
            self.query_one("#live-current", Static).update(f"{run.status} · {len(run.attempts)}/{config.total} executions completed")
            self.query_one("#validation", Static).update(f"{run.status} · ready for another experiment")
            self.query_one("#tabs", TabbedContent).active = "results"
            self.refresh_history()
        except (OSError, ValueError) as error:
            self.last_error = str(error)
            self.query_one("#live-current", Static).update(f"Unable to run: {error}")
            self.query_one("#validation", Static).update(f"Unable to run: {error}")
        finally:
            self.running = False
            self.query_one("#run", Button).disabled = False
            self.query_one("#cancel", Button).disabled = True
            if self.quit_pending:
                self.exit()

    def progress_changed(self, event: Progress) -> None:
        run = event.run
        if event.phase == "started":
            self.current_case_started = time.monotonic()
            self.current_case_label = f"{event.case.name} · repetition {event.repetition}/{run.config.repetitions}"
            self.update_elapsed()
        else:
            attempt = run.attempts[-1]
            self.query_one("#progress", ProgressBar).update(progress=len(run.attempts))
            self.query_one("#live-counts", Static).update(f"Completed {len(run.attempts)}/{run.config.total} · failures {run.failures} · last correctness: {attempt.correctness}")
            self.query_one("#events", RichLog).write(Text(f"{len(run.attempts):02d}  {event.case.name}  repetition {event.repetition}  {attempt.correctness}"))
            if attempt.error:
                self.query_one("#events", RichLog).write(Text(attempt.error))

    def update_elapsed(self) -> None:
        if not self.running or not self.current_case_label:
            return
        elapsed = time.monotonic() - self.current_case_started
        suffix = "Cancellation requested · finishing current execution safely." if self.cancel_event.is_set() else "Waiting for the C engine's result."
        if elapsed > 30:
            suffix += " Longer than usual; engine is still running."
        self.query_one("#live-current", Static).update(f"{self.current_case_label}\nElapsed {elapsed:.0f}s · {suffix}")

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        if self.running:
            self.cancel_event.set()
            self.query_one("#cancel", Button).disabled = True
            self.update_elapsed()

    async def action_quit(self) -> None:
        if self.running:
            self.quit_pending = True
            self.action_cancel()
            self.query_one("#tabs", TabbedContent).active = "live"
        else:
            self.exit()

    def show_results(self, run: Run) -> None:
        self.current = run
        unit = "records/sec" if run.config.family == "ipc" else "operations/sec (unsafe: attempted)"
        self.query_one("#result-title", Static).update(f"{run.status} · {len(run.attempts)}/{run.config.total} executions · {unit}\n{run.started[:19]} UTC · {run.config.workers} workers/producers × {run.config.amount:,} items")
        table = self.query_one("#summary", DataTable)
        table.clear()
        summaries = run.summaries()
        table.styles.height = min(11, len(summaries) + 3)
        # Unsafe and synchronized rates are not put on a common relative scale.
        maximum = max((s.median_rate or 0 for s in summaries if s.case.mode != "process-unsafe"), default=0)
        for index, summary in enumerate(summaries):
            color = {"PASS": "green", "FAIL": "red", "RACY": "yellow", "NOT RUN": "dim"}[summary.correctness]
            bar = "not comparable" if summary.case.mode == "process-unsafe" else relative_bar(summary.median_rate, maximum)
            table.add_row(summary.case.name, f"{summary.accepted}/{run.config.repetitions}",
                          rate(summary.median_rate), rate(summary.min_rate), rate(summary.max_rate),
                          Text(summary.correctness, style=color), Text(bar, style="cyan"), key=str(index))
        self.query_one("#export", Button).disabled = False
        self.query_one("#save", Button).disabled = False
        if summaries:
            self.show_detail(0)

    def show_detail(self, index: int) -> None:
        if self.current is None:
            return
        summaries = self.current.summaries()
        if index >= len(summaries):
            return
        summary = summaries[index]
        self.query_one("#detail", Static).update(detail(summary))
        self.query_one("#samples", Sparkline).data = list(summary.rates)
        raw = self.query_one("#raw", RichLog)
        raw.clear()
        for attempt in self.current.attempts:
            if attempt.case == summary.case:
                raw.write(Text(f"Repetition {attempt.repetition} · {attempt.correctness}"))
                raw.write(Text(attempt.stdout or attempt.error))
                if attempt.error and attempt.stdout:
                    raw.write(Text(attempt.error))

    @on(DataTable.RowHighlighted, "#summary")
    def result_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self.show_detail(int(event.row_key.value))

    @on(Button.Pressed, "#export")
    @work
    async def export_current(self) -> None:
        if self.current:
            try:
                path = await asyncio.to_thread(self.history.export_csv, self.current)
                message = f"Exported {path}"
            except (OSError, ValueError) as error:
                message = f"Export failed: {error}"
            self.query_one("#result-message", Static).update(message)

    @on(Button.Pressed, "#save")
    @work
    async def save_current(self) -> None:
        if self.current:
            try:
                path = await asyncio.to_thread(self.history.save, self.current)
                message = f"Saved {path}"
                self.refresh_history()
            except (OSError, ValueError) as error:
                message = f"Save failed: {error}"
            self.query_one("#result-message", Static).update(message)

    @on(Button.Pressed, "#refresh")
    @work(exclusive=True, group="history")
    async def refresh_history(self) -> None:
        try:
            runs, errors = await asyncio.to_thread(self.history.list_runs)
        except OSError as error:
            self.query_one("#history-message", Static).update(f"History unavailable: {error}")
            return
        self.runs = {run.run_id: run for run in runs}
        table = self.query_one("#history-table", DataTable)
        table.clear()
        for run in runs:
            table.add_row(run.started[:19], run.status, run.config.family,
                          f"{run.config.workers} × {run.config.amount:,}",
                          f"{len(run.attempts)}/{run.config.total}", run.run_id[:8], key=run.run_id)
        if errors:
            self.query_one("#history-message", Static).update(f"Skipped {len(errors)} unreadable history file(s): {errors[0]}")
        elif not runs:
            self.query_one("#history-message", Static).update("No saved runs yet. Complete an experiment to create one.")

    def selected_run(self) -> Run | None:
        table = self.query_one("#history-table", DataTable)
        if not table.row_count:
            return None
        return self.runs.get(str(table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value))

    @on(DataTable.RowHighlighted, "#history-table")
    def history_highlighted(self) -> None:
        run = self.selected_run()
        if run:
            system = run.system
            self.query_one("#metadata", Static).update(f"{run.run_id}\n{', '.join(run.config.modes)} · repetitions {run.config.repetitions} · capacity {run.config.capacity} · sweep {run.config.sweep or 'none'}\n{system['system']} {system['release']} · {system['machine']} · CPUs {system['cpu_count']}\nEngine SHA-256: {system['engine_sha256']}")

    @on(Button.Pressed, "#open-history")
    def open_history(self) -> None:
        run = self.selected_run()
        if run:
            self.show_results(run)
            self.query_one("#result-message", Static).update(f"Viewing saved run {run.run_id}")
            self.query_one("#tabs", TabbedContent).active = "results"

    @on(Button.Pressed, "#pin")
    def pin_baseline(self) -> None:
        self.baseline = self.selected_run()
        if self.baseline:
            self.query_one("#history-message", Static).update(f"Baseline: {self.baseline.run_id[:8]}. Select a compatible run and Compare.")

    @on(Button.Pressed, "#compare")
    def compare_selected(self) -> None:
        selected = self.selected_run()
        table = self.query_one("#comparison", DataTable)
        table.clear()
        try:
            if not selected or not self.baseline:
                raise ValueError("Pin a baseline and select a second run first.")
            if selected.run_id == self.baseline.run_id:
                raise ValueError("Select a different run from the pinned baseline.")
            rows = compare_runs(self.baseline, selected)
            for name, before, after, delta in rows:
                table.add_row(name, rate(before), rate(after), f"{delta:+.1f}%" if delta is not None else "—")
            self.query_one("#history-message", Static).update(f"Baseline {self.baseline.run_id[:8]} → selected {selected.run_id[:8]}. Descriptive median changes only.")
        except ValueError as error:
            self.query_one("#history-message", Static).update(str(error))
