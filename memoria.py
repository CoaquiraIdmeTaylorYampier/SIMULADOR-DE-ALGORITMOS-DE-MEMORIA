import collections
import copy
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import psutil


# ══════════════════════════════════════════════
#  PALETA
# ══════════════════════════════════════════════
BG_DARK = "#0A0E17"
BG_PANEL = "#111827"
BG_CARD = "#1A2235"
BG_INPUT = "#1F2D42"
BORDER = "#2A3A52"
ACCENT_BLUE = "#3D8EF0"
ACCENT_CYAN = "#22D3EE"
ACCENT_GRN = "#34D399"
ACCENT_RED = "#F87171"
ACCENT_AMB = "#FBBF24"
TEXT_PRI = "#E2E8F0"
TEXT_SEC = "#94A3B8"
TEXT_MUT = "#475569"
SO_COLOR = "#2D3748"
FREE_COLOR = "#0F2A1E"
FREE_TEXT = "#34D399"

PROC_COLORS = [
    "#3D8EF0", "#34D399", "#FBBF24", "#F87171",
    "#A78BFA", "#22D3EE", "#FB923C", "#4ADE80",
    "#F472B6", "#60A5FA", "#FACC15", "#C084FC",
]

MEM_ALGOS = ("Primer Ajuste", "Mejor Ajuste", "Peor Ajuste", "Gemelos (Buddy)")
CPU_ALGOS = ("FCFS", "SPN", "SRT", "Round Robin")


# ══════════════════════════════════════════════
#  ESTRUCTURAS MEMORIA
# ══════════════════════════════════════════════
class Proceso:
    def __init__(self, nombre, memoria, tiempo):
        self.nombre = nombre
        self.memoria = memoria
        self.tiempo = tiempo
        self.inicio = None
        self.fin = None
        self.particion = None
        self.asignado = False


class Particion:
    def __init__(self, idx, tamanio, inicio=0):
        self.idx = idx
        self.tamanio = tamanio
        self.inicio = inicio
        self.ocupante = None
        self.libre = True


# ══════════════════════════════════════════════
#  ESTRUCTURAS CPU
# ══════════════════════════════════════════════
class FilaDatos:
    def __init__(self, proceso="", llegada=0, ejecucion=0):
        self.proceso = proceso
        self.llegada = llegada
        self.ejecucion = [ejecucion, ejecucion]
        self.inicio = []
        self.fina = []
        self.completado = False
        self.enCola = False


# ══════════════════════════════════════════════
#  LECTURA
# ══════════════════════════════════════════════
def leer_archivo_memoria(path, tipo):
    with open(path, "r", encoding="utf-8") as f:
        lineas = [l.strip() for l in f if l.strip()]

    particiones_tam = None
    start = 1

    if tipo == "Fija":
        partes = lineas[0].split()
        particiones_tam = [int(x) for x in partes]

    procesos = []
    for linea in lineas[start:]:
        partes = linea.split()
        if len(partes) >= 3:
            procesos.append(Proceso(partes[0], int(partes[1]), float(partes[2])))

    return procesos, particiones_tam


def leer_procesos_cpu(path):
    tabla = []
    with open(path, "r", encoding="utf-8") as f:
        for linea in f:
            partes = linea.split()
            if len(partes) >= 3:
                tabla.append(FilaDatos(partes[0], int(partes[1]), int(partes[2])))
    return tabla


# ══════════════════════════════════════════════
#  ALGORITMOS DE MEMORIA
# ══════════════════════════════════════════════
def primer_ajuste(particiones, proceso):
    for p in particiones:
        if p.libre and p.tamanio >= proceso.memoria:
            return p
    return None


def mejor_ajuste(particiones, proceso):
    cands = [p for p in particiones if p.libre and p.tamanio >= proceso.memoria]
    return min(cands, key=lambda p: p.tamanio - proceso.memoria) if cands else None


def peor_ajuste(particiones, proceso):
    cands = [p for p in particiones if p.libre and p.tamanio >= proceso.memoria]
    return max(cands, key=lambda p: p.tamanio) if cands else None


def es_potencia_de_2(n):
    return n > 0 and (n & (n - 1)) == 0


def siguiente_potencia_2(n):
    p = 1
    while p < n:
        p *= 2
    return p


def buddy_ajuste(particiones, proceso):
    req = siguiente_potencia_2(proceso.memoria)
    cands = [p for p in particiones if p.libre and p.tamanio >= req]
    return min(cands, key=lambda p: (p.tamanio, p.inicio)) if cands else None


MEM_ALGO_FNS = {
    "Primer Ajuste": primer_ajuste,
    "Mejor Ajuste": mejor_ajuste,
    "Peor Ajuste": peor_ajuste,
    "Gemelos (Buddy)": buddy_ajuste,
}


def unir_huecos_libres(particiones):
    particiones.sort(key=lambda p: p.inicio)
    nuevas = []
    for part in particiones:
        if part.libre and nuevas and nuevas[-1].libre:
            nuevas[-1].tamanio += part.tamanio
        else:
            nuevas.append(part)

    for i, part in enumerate(nuevas):
        part.idx = i
    return nuevas


def es_buddy(part1, part2):
    if not part1.libre or not part2.libre:
        return False
    if part1.tamanio != part2.tamanio:
        return False

    menor = min(part1.inicio, part2.inicio)
    mayor = max(part1.inicio, part2.inicio)
    return mayor == menor + part1.tamanio and menor % (part1.tamanio * 2) == 0


def fusionar_buddies(particiones):
    cambio = True
    while cambio:
        cambio = False
        particiones.sort(key=lambda p: p.inicio)
        nuevas = []
        i = 0
        while i < len(particiones):
            if i + 1 < len(particiones) and es_buddy(particiones[i], particiones[i + 1]):
                nuevas.append(Particion(0, particiones[i].tamanio * 2, particiones[i].inicio))
                i += 2
                cambio = True
            else:
                nuevas.append(particiones[i])
                i += 1
        particiones = nuevas

    particiones.sort(key=lambda p: p.inicio)
    for i, p in enumerate(particiones):
        p.idx = i
    return particiones


def simular_memoria(procesos, particiones_obj, algo_fn, dinamica=False):
    procs = [copy.deepcopy(p) for p in procesos]
    parts = [copy.deepcopy(p) for p in particiones_obj]
    cola = list(procs)
    activos = []
    events = []
    tiempo = 0.0
    EPS = 1e-9
    es_buddy_algo = algo_fn == buddy_ajuste

    max_iter = 0
    while (cola or activos) and max_iter < 10000:
        max_iter += 1

        while cola:
            proc = cola[0]
            part = algo_fn(parts, proc)
            if not part:
                break

            if dinamica and es_buddy_algo:
                req = siguiente_potencia_2(proc.memoria)
                while part.tamanio // 2 >= req:
                    idx = parts.index(part)
                    mitad = part.tamanio // 2
                    izq = Particion(0, mitad, part.inicio)
                    der = Particion(0, mitad, part.inicio + mitad)
                    parts.pop(idx)
                    parts.insert(idx, der)
                    parts.insert(idx, izq)
                    for i, p in enumerate(parts):
                        p.idx = i
                    part = izq

                part.libre = False
                part.ocupante = proc.nombre

            elif dinamica:
                idx = parts.index(part)
                sobrante = part.tamanio - proc.memoria
                inicio_original = part.inicio
                part.tamanio = proc.memoria
                part.inicio = inicio_original
                part.libre = False
                part.ocupante = proc.nombre
                if sobrante > 0:
                    parts.insert(idx + 1, Particion(0, sobrante, inicio_original + proc.memoria))

            else:
                part.libre = False
                part.ocupante = proc.nombre

            parts.sort(key=lambda p: p.inicio)
            for i, p in enumerate(parts):
                p.idx = i

            proc.inicio = round(tiempo, 6)
            proc.fin = round(tiempo + proc.tiempo, 6)
            proc.particion = part.idx
            proc.asignado = True
            activos.append((proc, part, proc.fin))
            cola.pop(0)

            events.append({
                "tiempo": round(tiempo, 6),
                "tipo": "entrada",
                "proceso": proc,
                "snapshot": copy.deepcopy(parts),
            })

        if not activos:
            break

        tiempo = min(a[2] for a in activos)
        nuevos_activos = []
        for proc, part, fin in activos:
            if abs(fin - tiempo) < EPS:
                part.libre = True
                part.ocupante = None
                if dinamica and es_buddy_algo:
                    parts = fusionar_buddies(parts)
                elif dinamica:
                    parts = unir_huecos_libres(parts)

                events.append({
                    "tiempo": round(tiempo, 6),
                    "tipo": "salida",
                    "proceso": proc,
                    "snapshot": copy.deepcopy(parts),
                })
            else:
                nuevos_activos.append((proc, part, fin))
        activos = nuevos_activos

    return procs, events


# ══════════════════════════════════════════════
#  ALGORITMOS CPU
# ══════════════════════════════════════════════
def calcular_promedios_cpu(tabla):
    prom_tr = prom_te = 0.0
    for p in tabla:
        tr = p.fina[-1] - p.llegada
        te = tr - p.ejecucion[0]
        prom_tr += tr
        prom_te += te
    n = len(tabla)
    return prom_tr / n, prom_te / n


def FCFS(path):
    tabla = leer_procesos_cpu(path)
    if not tabla:
        return None
    tabla.sort(key=lambda p: p.llegada)
    tiempo = tabla[0].llegada
    for p in tabla:
        if tiempo < p.llegada:
            tiempo = p.llegada
        p.inicio.append(tiempo)
        tiempo += p.ejecucion[0]
        p.fina.append(tiempo)
    avg_tr, avg_te = calcular_promedios_cpu(tabla)
    return tabla, avg_tr, avg_te


def SPN(path):
    tabla = leer_procesos_cpu(path)
    if not tabla:
        return None
    n = len(tabla)
    terminados = 0
    tiempo = min(p.llegada for p in tabla)

    while terminados < n:
        candidatos = [i for i, p in enumerate(tabla) if not p.completado and p.llegada <= tiempo]
        if not candidatos:
            tiempo = min(p.llegada for p in tabla if not p.completado)
            continue

        idx = min(candidatos, key=lambda i: tabla[i].ejecucion[0])
        p = tabla[idx]
        p.inicio.append(tiempo)
        tiempo += p.ejecucion[0]
        p.fina.append(tiempo)
        p.completado = True
        terminados += 1

    avg_tr, avg_te = calcular_promedios_cpu(tabla)
    return tabla, avg_tr, avg_te


def SRT(path):
    tabla = leer_procesos_cpu(path)
    if not tabla:
        return None
    n = len(tabla)
    completados = 0
    tiempo = min(p.llegada for p in tabla)
    actual_idx = None

    while completados < n:
        candidatos = [
            i for i, p in enumerate(tabla)
            if not p.completado and p.llegada <= tiempo and p.ejecucion[1] > 0
        ]
        if not candidatos:
            tiempo = min(p.llegada for p in tabla if not p.completado)
            actual_idx = None
            continue

        idx = min(candidatos, key=lambda i: (tabla[i].ejecucion[1], tabla[i].llegada, i))
        if actual_idx != idx:
            if actual_idx is not None and not tabla[actual_idx].completado:
                tabla[actual_idx].fina.append(tiempo)
            tabla[idx].inicio.append(tiempo)
            actual_idx = idx

        tabla[idx].ejecucion[1] -= 1
        tiempo += 1

        if tabla[idx].ejecucion[1] == 0:
            tabla[idx].completado = True
            tabla[idx].fina.append(tiempo)
            completados += 1
            actual_idx = None

    avg_tr, avg_te = calcular_promedios_cpu(tabla)
    return tabla, avg_tr, avg_te


def RR(path, quantum):
    tabla = leer_procesos_cpu(path)
    if not tabla:
        return None

    cola = collections.deque()
    tiempo = min(p.llegada for p in tabla)
    completados = 0
    n = len(tabla)

    while completados < n:
        for i, p in enumerate(tabla):
            if not p.completado and not p.enCola and p.llegada <= tiempo:
                cola.append(i)
                p.enCola = True

        if not cola:
            tiempo = min(p.llegada for p in tabla if not p.completado)
            continue

        idx = cola.popleft()
        p = tabla[idx]
        p.inicio.append(tiempo)
        ejec = min(quantum, p.ejecucion[1])

        for _ in range(ejec):
            tiempo += 1
            p.ejecucion[1] -= 1
            for i2, p2 in enumerate(tabla):
                if not p2.completado and not p2.enCola and p2.llegada <= tiempo:
                    cola.append(i2)
                    p2.enCola = True

        p.fina.append(tiempo)
        if p.ejecucion[1] == 0:
            p.completado = True
            completados += 1
        else:
            cola.append(idx)

    avg_tr, avg_te = calcular_promedios_cpu(tabla)
    return tabla, avg_tr, avg_te


# ══════════════════════════════════════════════
#  MONITOR
# ══════════════════════════════════════════════
class MiniMonitor(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG_PANEL, **kw)
        self._cpu = 0.0
        self._ram = 0.0
        self._build()
        threading.Thread(target=self._init, daemon=True).start()
        self.after(1200, self._refresh)

    def _init(self):
        self._cpu = psutil.cpu_percent(interval=1.0)
        self._ram = psutil.virtual_memory().percent

    def _measure(self):
        self._cpu = psutil.cpu_percent(interval=0.5)
        self._ram = psutil.virtual_memory().percent

    def _col(self, v):
        return ACCENT_GRN if v < 60 else (ACCENT_AMB if v < 85 else ACCENT_RED)

    def _build(self):
        row = tk.Frame(self, bg=BG_PANEL)
        row.pack(fill="x")
        for attr, lbl, col in [("_lbl_cpu", "CPU", ACCENT_BLUE), ("_lbl_ram", "RAM", ACCENT_GRN)]:
            card = tk.Frame(row, bg=BG_CARD, highlightthickness=1, highlightbackground=col)
            card.pack(side="left", expand=True, fill="x", padx=(0, 3 if attr == "_lbl_cpu" else 0))
            tk.Label(card, text=lbl, font=("Courier New", 7, "bold"), bg=BG_CARD, fg=col).pack(pady=(5, 0))
            l = tk.Label(card, text="—", font=("Courier New", 16, "bold"), bg=BG_CARD, fg=TEXT_PRI)
            l.pack(pady=(0, 5))
            setattr(self, attr, l)

    def _refresh(self):
        self._lbl_cpu.configure(text=f"{self._cpu:.0f}%", fg=self._col(self._cpu))
        self._lbl_ram.configure(text=f"{self._ram:.0f}%", fg=self._col(self._ram))
        threading.Thread(target=self._measure, daemon=True).start()
        self.after(1000, self._refresh)


# ══════════════════════════════════════════════
#  APLICACIÓN
# ══════════════════════════════════════════════
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gestión de Memoria y Planificación — Simulador")
        self.geometry("1500x900")
        self.resizable(False, False)
        self.configure(bg=BG_DARK)

        self.archivo_path = tk.StringVar()
        self.algoritmo_var = tk.StringVar(value="Primer Ajuste")
        self.tipo_mem_var = tk.StringVar(value="Dinámica")
        self.tam_mem_var = tk.StringVar(value="256")
        self.quantum_var = tk.StringVar(value="2")

        self._procesos = []
        self._particiones = []
        self._color_map = {}
        self._events = []
        self._sim_running = False
        self._cpu_result = None
        self._mode = "memoria"
        self._zoom = 1.0
        self._anim_rows = []
        self._anim_idx = 0

        self._build_ui()
        self._on_alg_change()

    def _build_ui(self):
        hdr = tk.Frame(self, bg=BG_DARK, height=46)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(
            hdr,
            text="Algoritmos de Memoria y Planificación de CPU",
            font=("Courier New", 15, "bold"),
            bg=BG_DARK,
            fg=ACCENT_BLUE,
        ).pack(side="left", padx=20, pady=8)
        tk.Label(
            hdr,
            text="Memoria: First/Best/Worst/Buddy  ·  CPU: FCFS/SPN/SRT/RR",
            font=("Courier New", 8),
            bg=BG_DARK,
            fg=TEXT_MUT,
        ).pack(side="left", pady=13)

        metrics_frame = tk.Frame(hdr, bg=BG_DARK)
        metrics_frame.pack(side="right", padx=16, pady=5)
        for attr, label, color in [("_hdr_tr", "Ø T.Retorno", ACCENT_CYAN), ("_hdr_te", "Ø T.Espera", ACCENT_AMB)]:
            card = tk.Frame(metrics_frame, bg=BG_CARD, highlightthickness=1, highlightbackground=color)
            card.pack(side="left", padx=(0, 6))
            tk.Label(card, text=label, font=("Courier New", 7, "bold"), bg=BG_CARD, fg=color).pack(side="left", padx=(8, 4), pady=6)
            lbl = tk.Label(card, text="—", font=("Courier New", 13, "bold"), bg=BG_CARD, fg=TEXT_PRI)
            lbl.pack(side="left", padx=(0, 10), pady=6)
            setattr(self, attr, lbl)

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        top = tk.Frame(self, bg=BG_DARK)
        top.pack(fill="both", expand=False, padx=14, pady=(10, 4))
        self._build_left(top)
        self._build_table(top)

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=14)

        bot = tk.Frame(self, bg=BG_DARK)
        bot.pack(fill="both", expand=True, padx=14, pady=(4, 10))
        self._build_mem_viz(bot)
        self._build_gantt(bot)

    def _build_left(self, parent):
        frame = tk.Frame(parent, bg=BG_PANEL, width=320)
        frame.pack(side="left", fill="y", padx=(0, 10))
        frame.pack_propagate(False)

        self._sec(frame, "⚙  ALGORITMO")
        self.combo_alg = ttk.Combobox(
            frame,
            textvariable=self.algoritmo_var,
            values=list(MEM_ALGOS) + list(CPU_ALGOS),
            state="readonly",
            font=("Courier New", 9, "bold"),
        )
        self.combo_alg.pack(fill="x", padx=10, pady=(2, 0), ipady=3)
        self.combo_alg.bind("<<ComboboxSelected>>", self._on_alg_change)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "TCombobox",
            fieldbackground=BG_INPUT,
            background=BG_INPUT,
            foreground=TEXT_PRI,
            selectbackground=ACCENT_BLUE,
            selectforeground=TEXT_PRI,
            bordercolor=BORDER,
            arrowcolor=ACCENT_BLUE,
        )

        self._sec(frame, "💾  TIPO DE MEMORIA / QUANTUM")
        mode_row = tk.Frame(frame, bg=BG_PANEL)
        mode_row.pack(fill="x", padx=10, pady=(2, 0))
        self.mem_type_buttons = []
        for t in ("Dinámica", "Fija"):
            rb = tk.Radiobutton(
                mode_row,
                text=t,
                variable=self.tipo_mem_var,
                value=t,
                font=("Courier New", 8, "bold"),
                bg=BG_PANEL,
                fg=TEXT_PRI,
                activebackground=BG_PANEL,
                activeforeground=ACCENT_CYAN,
                selectcolor=BG_INPUT,
                indicatoron=0,
                bd=0,
                padx=8,
                pady=4,
                relief="flat",
                cursor="hand2",
                width=9,
            )
            rb.pack(side="left", padx=(0, 4))
            self.mem_type_buttons.append(rb)

        self.q_panel = tk.Frame(mode_row, bg=BG_INPUT, highlightthickness=1, highlightbackground=BORDER)
        self.q_panel.pack(side="left", fill="x", expand=True, padx=(4, 0))
        tk.Label(self.q_panel, text="Q:", font=("Courier New", 8, "bold"), bg=BG_INPUT, fg=TEXT_MUT).pack(side="left", padx=(6, 2))
        self.quantum_entry = tk.Entry(
            self.q_panel,
            textvariable=self.quantum_var,
            font=("Courier New", 10, "bold"),
            width=5,
            bg=BG_INPUT,
            fg=TEXT_MUT,
            insertbackground=ACCENT_AMB,
            disabledbackground=BG_INPUT,
            disabledforeground=TEXT_MUT,
            bd=0,
            relief="flat",
            state="disabled",
        )
        self.quantum_entry.pack(side="left", ipady=3)
        self.quantum_hint = tk.Label(self.q_panel, text="—", font=("Courier New", 7), bg=BG_INPUT, fg=TEXT_MUT)
        self.quantum_hint.pack(side="left", padx=(4, 4))

        self._sec(frame, "📂  ARCHIVO DE DATOS")
        fr = tk.Frame(frame, bg=BG_PANEL)
        fr.pack(fill="x", padx=10, pady=(2, 0))
        self.file_lbl = tk.Label(fr, text="Sin archivo…", font=("Courier New", 8), bg=BG_INPUT, fg=TEXT_MUT, anchor="w", width=18, padx=5, pady=4)
        self.file_lbl.pack(side="left", fill="x", expand=True)
        self._btn(fr, "Buscar", self._browse, ACCENT_BLUE).pack(side="left", padx=(5, 0))

        self._sec(frame, "📐  TAMAÑO DE MEMORIA (KB)")
        row_tam = tk.Frame(frame, bg=BG_PANEL)
        row_tam.pack(fill="x", padx=10, pady=(2, 0))
        self.tam_entry = tk.Entry(
            row_tam,
            textvariable=self.tam_mem_var,
            font=("Courier New", 10, "bold"),
            width=8,
            bg=BG_INPUT,
            fg=ACCENT_AMB,
            insertbackground=ACCENT_AMB,
            disabledbackground=BG_INPUT,
            disabledforeground=TEXT_MUT,
            bd=0,
            highlightthickness=1,
            highlightcolor=ACCENT_BLUE,
            highlightbackground=BORDER,
            relief="flat",
        )
        self.tam_entry.pack(side="left", ipady=4)
        tk.Label(row_tam, text=" KB", font=("Courier New", 9), bg=BG_PANEL, fg=TEXT_SEC).pack(side="left")
        tk.Button(
            row_tam,
            text="▶ SIMULAR",
            font=("Courier New", 9, "bold"),
            bg=ACCENT_GRN,
            fg="#0A0E17",
            activebackground="#059669",
            activeforeground="#0A0E17",
            bd=0,
            padx=10,
            pady=5,
            cursor="hand2",
            relief="flat",
            command=self._ejecutar,
        ).pack(side="left", padx=(10, 0))

        tk.Button(
            frame,
            text="⏹  DETENER",
            font=("Courier New", 8),
            bg=BG_INPUT,
            fg=ACCENT_RED,
            activebackground=BORDER,
            activeforeground=ACCENT_RED,
            bd=0,
            pady=4,
            cursor="hand2",
            relief="flat",
            command=self._detener,
        ).pack(fill="x", padx=10, pady=(6, 6))

        tk.Frame(frame, bg=BORDER, height=1).pack(fill="x", padx=8)
        self._sec(frame, "")
        mon_row = tk.Frame(frame, bg=BG_PANEL)
        mon_row.pack(fill="x", padx=10, pady=(0, 6))
        self.monitor = MiniMonitor(mon_row)
        self.monitor.pack(fill="x")

    def _build_table(self, parent):
        frame = tk.Frame(parent, bg=BG_PANEL)
        frame.pack(side="left", fill="both", expand=True)
        self._sec(frame, "🗂  TABLA DE PROCESOS")
        cols = ("Proceso", "Mem(KB)", "Tiempo", "T.Inicio", "T.Fin", "T.Retorno", "T.Espera")

        style = ttk.Style()
        style.configure("M.Treeview", background=BG_CARD, foreground=TEXT_PRI, rowheight=27, fieldbackground=BG_CARD, bordercolor=BORDER, relief="flat", font=("Courier New", 9))
        style.configure("M.Treeview.Heading", background=BG_INPUT, foreground=ACCENT_BLUE, font=("Courier New", 9, "bold"), relief="flat")
        style.map("M.Treeview", background=[("selected", "#1a3050")], foreground=[("selected", TEXT_PRI)])

        wrap = tk.Frame(frame, bg=BG_PANEL)
        wrap.pack(fill="both", expand=True, padx=10, pady=(2, 10))
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", style="M.Treeview", height=10)
        widths = [90, 85, 80, 90, 90, 100, 95]
        for c, w in zip(cols, widths):
            self.tree.heading(c, text=c)
            self.tree.column(c, anchor="center", width=w)

        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(wrap, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)

    def _build_mem_viz(self, parent):
        frame = tk.Frame(parent, bg=BG_PANEL, width=230)
        frame.pack(side="left", fill="y", padx=(0, 8))
        frame.pack_propagate(False)
        self._sec_lbl = tk.Label(frame, text="🧠  MAPA DE MEMORIA", font=("Courier New", 7, "bold"), bg=BG_PANEL, fg=TEXT_MUT)
        self._sec_lbl.pack(anchor="w", padx=8, pady=(8, 2))
        self.mem_canvas = tk.Canvas(frame, bg=BG_DARK, highlightthickness=0, bd=0)
        self.mem_canvas.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _build_gantt(self, parent):
        frame = tk.Frame(parent, bg=BG_PANEL)
        frame.pack(side="left", fill="both", expand=True)
        hdr = tk.Frame(frame, bg=BG_PANEL)
        hdr.pack(fill="x", padx=10, pady=(8, 2))
        tk.Label(hdr, text="📈  DIAGRAMA DE GANTT", font=("Courier New", 8, "bold"), bg=BG_PANEL, fg=TEXT_MUT).pack(side="left")
        self.leyenda_frame = tk.Frame(hdr, bg=BG_PANEL)
        self.leyenda_frame.pack(side="left", padx=(12, 0))

        zf = tk.Frame(hdr, bg=BG_PANEL)
        zf.pack(side="right")
        tk.Label(zf, text="Zoom:", font=("Courier New", 8), bg=BG_PANEL, fg=TEXT_MUT).pack(side="left", padx=(0, 4))
        for txt, delta in (("−", -0.25), ("+", 0.25)):
            tk.Button(zf, text=txt, font=("Courier New", 11, "bold"), bg=BG_INPUT, fg=ACCENT_CYAN, activebackground=BORDER, activeforeground=ACCENT_CYAN, bd=0, padx=9, pady=0, cursor="hand2", relief="flat", command=lambda d=delta: self._zoom_gantt(d)).pack(side="left", padx=2)
        tk.Button(zf, text="Reset", font=("Courier New", 8), bg=BG_INPUT, fg=TEXT_SEC, activebackground=BORDER, activeforeground=TEXT_PRI, bd=0, padx=8, pady=1, cursor="hand2", relief="flat", command=lambda: self._zoom_gantt(reset=True)).pack(side="left", padx=(4, 0))
        self._zoom_label = tk.Label(zf, text="100%", font=("Courier New", 8, "bold"), bg=BG_PANEL, fg=ACCENT_AMB)
        self._zoom_label.pack(side="left", padx=(6, 0))

        wrap = tk.Frame(frame, bg=BG_DARK)
        wrap.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self.gantt_canvas = tk.Canvas(wrap, bg=BG_DARK, highlightthickness=0, bd=0)
        hscb = ttk.Scrollbar(wrap, orient="horizontal", command=self.gantt_canvas.xview)
        vscb = ttk.Scrollbar(wrap, orient="vertical", command=self.gantt_canvas.yview)
        self.gantt_canvas.configure(xscrollcommand=hscb.set, yscrollcommand=vscb.set)
        hscb.pack(side="bottom", fill="x")
        vscb.pack(side="right", fill="y")
        self.gantt_canvas.pack(side="left", fill="both", expand=True)
        self.gantt_canvas.bind("<MouseWheel>", lambda e: self.gantt_canvas.yview_scroll(-1 * (e.delta // 120), "units"))
        self.gantt_canvas.bind("<Shift-MouseWheel>", lambda e: self.gantt_canvas.xview_scroll(-1 * (e.delta // 120), "units"))
        self.gantt_canvas.bind("<Control-MouseWheel>", lambda e: self._zoom_gantt(0.25 if e.delta > 0 else -0.25))

    def _sec(self, parent, txt):
        tk.Label(parent, text=txt, font=("Courier New", 7, "bold"), bg=BG_PANEL, fg=TEXT_MUT).pack(anchor="w", padx=10, pady=(10, 1))

    def _btn(self, parent, txt, cmd, color):
        return tk.Button(parent, text=txt, font=("Courier New", 8, "bold"), bg=color, fg="#0A0E17", activebackground=color, bd=0, padx=9, pady=4, cursor="hand2", relief="flat", command=cmd)

    def _browse(self):
        path = filedialog.askopenfilename(title="Seleccionar archivo", filetypes=[("Texto/CSV", "*.txt *.csv"), ("Todos", "*.*")])
        if path:
            self.archivo_path.set(path)
            self.file_lbl.configure(text=path.split("/")[-1], fg=TEXT_PRI)

    def _on_alg_change(self, event=None):
        alg = self.algoritmo_var.get()
        is_mem = alg in MEM_ALGOS
        is_rr = alg == "Round Robin"
        self._mode = "memoria" if is_mem else "cpu"

        state_mem = "normal" if is_mem else "disabled"
        self.tam_entry.configure(state=state_mem, fg=ACCENT_AMB if is_mem else TEXT_MUT)
        for rb in self.mem_type_buttons:
            rb.configure(state=state_mem, fg=TEXT_PRI if is_mem else TEXT_MUT)

        if is_rr:
            self.quantum_entry.configure(state="normal", fg=ACCENT_AMB)
            self.quantum_hint.configure(text="RR", fg=ACCENT_AMB)
        else:
            self.quantum_entry.configure(state="disabled", fg=TEXT_MUT)
            self.quantum_hint.configure(text="—", fg=TEXT_MUT)

        if not is_mem:
            self._draw_mem_not_applicable()

    def _lighten(self, hx, amt=55):
        r = min(255, int(hx[1:3], 16) + amt)
        g = min(255, int(hx[3:5], 16) + amt)
        b = min(255, int(hx[5:7], 16) + amt)
        return f"#{r:02X}{g:02X}{b:02X}"

    def _detener(self):
        self._sim_running = False

    def _limpiar(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        self.mem_canvas.delete("all")
        self.gantt_canvas.delete("all")
        for w in self.leyenda_frame.winfo_children():
            w.destroy()
        self._hdr_tr.configure(text="—")
        self._hdr_te.configure(text="—")

    def _ejecutar(self):
        if not self.archivo_path.get():
            messagebox.showwarning("Sin archivo", "Selecciona un archivo primero.")
            return
        self._detener()
        self._limpiar()

        alg = self.algoritmo_var.get()
        if alg in MEM_ALGOS:
            self._ejecutar_memoria(alg)
        else:
            self._ejecutar_cpu(alg)

    def _crear_particiones_fijas(self, particiones_tam):
        parts = []
        inicio = 0
        for i, tam in enumerate(particiones_tam):
            parts.append(Particion(i, tam, inicio))
            inicio += tam
        return parts

    def _ejecutar_memoria(self, alg):
        try:
            tam_total = int(self.tam_mem_var.get())
            if tam_total < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Tamaño de memoria inválido.")
            return

        if alg == "Gemelos (Buddy)":
            if self.tipo_mem_var.get() != "Dinámica":
                messagebox.showerror("Error", "El algoritmo Gemelos (Buddy) solo funciona con memoria dinámica.")
                return
            if not es_potencia_de_2(tam_total):
                messagebox.showerror("Error", "Para Gemelos (Buddy), el tamaño de memoria debe ser potencia de 2: 32, 64, 128, 256...")
                return

        try:
            procesos, particiones_tam = leer_archivo_memoria(self.archivo_path.get(), self.tipo_mem_var.get())
        except Exception as e:
            messagebox.showerror("Error leyendo archivo", str(e))
            return
        if not procesos:
            messagebox.showwarning("Vacío", "No se encontraron procesos.")
            return

        if self.tipo_mem_var.get() == "Fija" and particiones_tam:
            self._particiones = self._crear_particiones_fijas(particiones_tam)
        else:
            self._particiones = [Particion(0, tam_total, 0)]

        self._color_map = {p.nombre: PROC_COLORS[i % len(PROC_COLORS)] for i, p in enumerate(procesos)}
        algo_fn = MEM_ALGO_FNS[alg]
        es_dinamica = self.tipo_mem_var.get() == "Dinámica"
        procs, events = simular_memoria(procesos, self._particiones, algo_fn, es_dinamica)
        self._procesos = procs
        self._events = events
        self._cpu_result = None
        self._mode = "memoria"

        if self.tipo_mem_var.get() == "Fija" and particiones_tam:
            self._particiones = self._crear_particiones_fijas(particiones_tam)
        else:
            self._particiones = [Particion(0, tam_total, 0)]

        for i, p in enumerate(procs):
            if p.asignado:
                tr = round(p.fin, 4)
                te = round(p.inicio, 4)
            else:
                tr = te = "—"
            tag = "even" if i % 2 == 0 else "odd"
            self.tree.insert("", "end", tags=(tag,), values=(p.nombre, p.memoria, p.tiempo, p.inicio if p.asignado else "—", p.fin if p.asignado else "—", tr, te))
        self.tree.tag_configure("even", background=BG_CARD)
        self.tree.tag_configure("odd", background=BG_INPUT)

        asignados = [p for p in procs if p.asignado]
        if asignados:
            self._hdr_tr.configure(text=str(round(sum(p.fin for p in asignados) / len(asignados), 3)))
            self._hdr_te.configure(text=str(round(sum(p.inicio for p in asignados) / len(asignados), 3)))

        self._build_leyenda(self._color_map)
        self._draw_mem_snapshot(tam_total, {})
        self._build_memory_gantt_layout()
        self._sim_running = True
        self._animate_mem_events(0, tam_total)

    def _ejecutar_cpu(self, alg):
        try:
            if alg == "FCFS":
                res = FCFS(self.archivo_path.get())
            elif alg == "SPN":
                res = SPN(self.archivo_path.get())
            elif alg == "SRT":
                res = SRT(self.archivo_path.get())
            else:
                q = int(self.quantum_var.get())
                if q < 1:
                    raise ValueError
                res = RR(self.archivo_path.get(), q)
        except ValueError:
            messagebox.showerror("Quantum inválido", "El quantum debe ser entero mayor o igual a 1.")
            return
        except Exception as e:
            messagebox.showerror("Error leyendo archivo", str(e))
            return

        if res is None:
            messagebox.showerror("Error", "No se pudo leer el archivo.")
            return

        tabla, avg_tr, avg_te = res
        self._cpu_result = res
        self._mode = "cpu"
        self._hdr_tr.configure(text=f"{avg_tr:.2f}")
        self._hdr_te.configure(text=f"{avg_te:.2f}")
        self._color_map = {p.proceso: PROC_COLORS[i % len(PROC_COLORS)] for i, p in enumerate(tabla)}
        self._build_leyenda(self._color_map)
        self._draw_mem_not_applicable()

        self._anim_rows = list(tabla)
        self._anim_idx = 0
        self._animate_cpu_table_row()
        self._draw_cpu_gantt(tabla)

    def _animate_cpu_table_row(self):
        if self._anim_idx >= len(self._anim_rows):
            return
        p = self._anim_rows[self._anim_idx]
        tr = p.fina[-1] - p.llegada
        te = tr - p.ejecucion[0]
        tag = "even" if self._anim_idx % 2 == 0 else "odd"
        self.tree.insert("", "end", tags=(tag,), values=(p.proceso, p.ejecucion[0], p.llegada, p.inicio[0] if p.inicio else "—", p.fina[-1] if p.fina else "—", tr, te))
        self.tree.tag_configure("even", background=BG_CARD)
        self.tree.tag_configure("odd", background=BG_INPUT)
        self._anim_idx += 1
        self.after(180, self._animate_cpu_table_row)

    def _zoom_gantt(self, delta=0, reset=False):
        if reset:
            self._zoom = 1.0
        else:
            self._zoom = max(0.25, min(4.0, self._zoom + delta))
        self._zoom_label.configure(text=f"{int(self._zoom * 100)}%")
        if self._mode == "cpu" and self._cpu_result:
            self._draw_cpu_gantt(self._cpu_result[0])
        elif self._mode == "memoria" and self._procesos:
            self._build_memory_gantt_layout()
            for ev in self._events:
                if ev["tipo"] == "entrada":
                    self._draw_memory_gantt_segment(ev["proceso"])

    # ══ MEMORIA: MAPA Y GANTT ═════════════════════
    def _animate_mem_events(self, idx, tam_total):
        if not self._sim_running:
            return
        if idx >= len(self._events):
            return
        ev = self._events[idx]
        self._particiones = copy.deepcopy(ev["snapshot"])
        ocupadas = {p.idx: p.ocupante for p in self._particiones if not p.libre}
        self._draw_mem_snapshot(tam_total, ocupadas)
        if ev["tipo"] == "entrada":
            self._draw_memory_gantt_segment(ev["proceso"])
        self.after(600, self._animate_mem_events, idx + 1, tam_total)

    def _draw_mem_snapshot(self, tam_total, ocupadas):
        cv = self.mem_canvas
        cv.delete("all")
        W = cv.winfo_width()
        if W < 10:
            W = 210
        PAD_X = 16
        X1 = PAD_X
        X2 = W - PAD_X
        H = cv.winfo_height()
        if H < 50:
            H = 380
        SO_H = max(28, int((H - 16) * 0.08))
        MEM_H = H - 16
        AVAIL_H = MEM_H - SO_H
        Y0 = 8
        cv.create_rectangle(X1 - 2, Y0 - 2, X2 + 2, Y0 + MEM_H + 2, outline=ACCENT_BLUE, width=2, fill="")
        cv.create_rectangle(X1, Y0, X2, Y0 + SO_H, fill=SO_COLOR, outline=BORDER, width=1)
        cv.create_text((X1 + X2) // 2, Y0 + SO_H // 2, text="S.O.", font=("Courier New", 8, "bold"), fill=ACCENT_BLUE)

        total_tam = sum(p.tamanio for p in self._particiones)
        if total_tam == 0:
            return
        py = Y0 + SO_H
        es_fija = self.tipo_mem_var.get() == "Fija"
        part_border_col = "#000000" if es_fija else BORDER
        part_border_w = 3 if es_fija else 1
        MIN_PH = max(8, AVAIL_H // max(len(self._particiones), 1))
        SHOW_TEXT = MIN_PH >= 22

        for pos, part in enumerate(self._particiones):
            ph = max(8, int(AVAIL_H * (part.tamanio / total_tam)))
            if pos == len(self._particiones) - 1:
                ph = (Y0 + MEM_H) - py
            nombre_proc = ocupadas.get(part.idx)

            if nombre_proc:
                color = self._color_map.get(nombre_proc, ACCENT_BLUE)
                proc_obj = next((p for p in self._procesos if p.nombre == nombre_proc), None)
                if proc_obj and es_fija:
                    proc_h = max(4, int(ph * (proc_obj.memoria / part.tamanio)))
                    frag_h = ph - proc_h
                    cv.create_rectangle(X1, py, X2, py + proc_h, fill=color, outline=part_border_col, width=part_border_w)
                    if SHOW_TEXT and proc_h >= 14:
                        cv.create_text((X1 + X2) // 2, py + proc_h // 2, text=f"{nombre_proc}\n{proc_obj.memoria}KB", font=("Courier New", 7, "bold"), fill="#0A0E17", justify="center")
                    if frag_h > 4:
                        frag_kb = part.tamanio - proc_obj.memoria
                        cv.create_rectangle(X1, py + proc_h, X2, py + ph, fill="#2D1010", outline=ACCENT_RED, width=1, dash=(3, 2))
                        if frag_h >= 12:
                            cv.create_text((X1 + X2) // 2, py + proc_h + frag_h // 2, text=f"Frag\n{frag_kb}KB", font=("Courier New", 6, "bold"), fill=ACCENT_RED, justify="center")
                else:
                    cv.create_rectangle(X1, py, X2, py + ph, fill=color, outline=part_border_col, width=part_border_w)
                    if SHOW_TEXT and ph >= 14:
                        cv.create_text((X1 + X2) // 2, py + ph // 2, text=f"{nombre_proc}\n{part.tamanio}KB", font=("Courier New", 7, "bold"), fill="#0A0E17", justify="center")
            else:
                cv.create_rectangle(X1, py, X2, py + ph, fill=FREE_COLOR, outline=part_border_col, width=part_border_w)
                if SHOW_TEXT and ph >= 14:
                    cv.create_text((X1 + X2) // 2, py + ph // 2, text=f"LIBRE\n{part.tamanio}KB", font=("Courier New", 7, "bold"), fill=FREE_TEXT, justify="center")

            if ph >= 10:
                cv.create_text(X2 + 4, py + ph // 2, text=f"P{part.idx}", font=("Courier New", 6), fill=TEXT_MUT, anchor="w")
            py += ph

    def _draw_mem_not_applicable(self):
        cv = self.mem_canvas
        cv.delete("all")
        W = cv.winfo_width() or 210
        H = cv.winfo_height() or 380
        cv.create_rectangle(14, 14, W - 14, H - 14, outline=BORDER, width=1, fill=BG_CARD)
        cv.create_text(W // 2, H // 2, text="MAPA DE MEMORIA\nNO APLICA", font=("Courier New", 10, "bold"), fill=TEXT_MUT, justify="center")

    def _build_memory_gantt_layout(self):
        cv = self.gantt_canvas
        cv.delete("all")
        n = len(self._procesos)
        t_max = max((p.fin for p in self._procesos if p.asignado), default=1.0)
        z = self._zoom
        self._g_ROW_H = max(22, int(34 * z))
        self._g_ROW_PAD = max(3, int(6 * z))
        self._g_LABEL_W = 72
        self._g_TOP_PAD = max(16, int(20 * z))
        self._g_LEG_H = max(12, int(16 * z))
        self._g_PX_PER_T = max(25, int(70 * z))
        self._g_row = {p.nombre: i for i, p in enumerate(self._procesos)}
        self._g_t_max = t_max

        cw = self._g_LABEL_W + t_max * self._g_PX_PER_T + 80
        ch = self._g_LEG_H + self._g_TOP_PAD + n * (self._g_ROW_H + self._g_ROW_PAD) + 35
        cv.configure(scrollregion=(0, 0, cw, ch))

        for i, p in enumerate(self._procesos):
            color = self._color_map[p.nombre]
            y0 = self._g_LEG_H + self._g_TOP_PAD + i * (self._g_ROW_H + self._g_ROW_PAD)
            bg = BG_CARD if i % 2 == 0 else BG_INPUT
            cv.create_rectangle(0, y0, cw, y0 + self._g_ROW_H, fill=bg, outline="", tags="bg")
            cv.create_rectangle(0, y0, 5, y0 + self._g_ROW_H, fill=color, outline="", tags="bg")
            cv.create_text(self._g_LABEL_W - 8, y0 + self._g_ROW_H // 2, text=p.nombre, font=("Courier New", 9, "bold"), fill=color, anchor="e", tags="bg")

    def _draw_memory_gantt_segment(self, proc):
        cv = self.gantt_canvas
        row_i = self._g_row.get(proc.nombre, 0)
        col = self._color_map[proc.nombre]
        y0 = self._g_LEG_H + self._g_TOP_PAD + row_i * (self._g_ROW_H + self._g_ROW_PAD)
        yt = y0 + 4
        yb = y0 + self._g_ROW_H - 4
        x1 = self._g_LABEL_W + proc.inicio * self._g_PX_PER_T + 1
        x2 = self._g_LABEL_W + proc.fin * self._g_PX_PER_T - 1
        cv.create_rectangle(x1 + 2, yt + 2, x2 + 2, yb + 2, fill="#000000", outline="")
        cv.create_rectangle(x1, yt, x2, yb, fill=col, outline="")
        cv.create_rectangle(x1, yt, x2, yt + 3, fill=self._lighten(col), outline="")
        if x2 - x1 > 40:
            cv.create_text((x1 + x2) / 2, (yt + yb) / 2, text=f"{proc.nombre}\n{proc.memoria}KB", font=("Courier New", 8, "bold"), fill="#0A0E17", justify="center")
        self._draw_memory_ticks()

    def _draw_memory_ticks(self):
        cv = self.gantt_canvas
        cv.delete("ticks")
        cv.delete("grid")
        n = len(self._procesos)
        y_top = self._g_LEG_H + self._g_TOP_PAD
        y_bot = y_top + n * (self._g_ROW_H + self._g_ROW_PAD)
        tick_y = y_bot + 5
        tiempos = sorted(set([0.0] + [round(p.inicio, 4) for p in self._procesos if p.asignado] + [round(p.fin, 4) for p in self._procesos if p.asignado]))
        last_tick_x = -999
        for t in tiempos:
            x = self._g_LABEL_W + t * self._g_PX_PER_T
            cv.create_line(x, y_top, x, y_bot, fill=BORDER, dash=(2, 4), tags="grid")
            cv.create_line(x, tick_y, x, tick_y + 5, fill=TEXT_SEC, tags="ticks")
            if x - last_tick_x >= 28:
                cv.create_text(x, tick_y + 15, text=str(round(t, 3)), font=("Courier New", 7), fill=TEXT_SEC, tags="ticks")
                last_tick_x = x

    # ══ CPU: GANTT ════════════════════════════════
    def _draw_cpu_gantt(self, tabla):
        cv = self.gantt_canvas
        cv.delete("all")
        color_map = {p.proceso: PROC_COLORS[i % len(PROC_COLORS)] for i, p in enumerate(tabla)}
        z = self._zoom
        ROW_H = max(18, int(42 * z))
        ROW_PAD = max(4, int(8 * z))
        LABEL_W = 84
        TICK_H = max(14, int(22 * z))
        TOP_PAD = max(10, int(20 * z))
        LEG_H = max(12, int(16 * z))
        PX_PER_T = max(10, int(36 * z))
        t_max = max((p.fina[-1] for p in tabla if p.fina), default=1)
        n = len(tabla)
        cw = LABEL_W + t_max * PX_PER_T + 50
        ch = LEG_H + TOP_PAD + n * (ROW_H + ROW_PAD) + TICK_H + 14
        cv.configure(scrollregion=(0, 0, cw, ch))

        lx = LABEL_W
        for nombre, col in color_map.items():
            cv.create_rectangle(lx, 3, lx + 12, LEG_H - 3, fill=col, outline="")
            cv.create_text(lx + 16, LEG_H // 2, text=nombre, font=("Courier New", 7), fill=TEXT_SEC, anchor="w")
            lx += len(nombre) * 7 + 28

        for ri, p in enumerate(tabla):
            y0 = LEG_H + TOP_PAD + ri * (ROW_H + ROW_PAD)
            bg = BG_CARD if ri % 2 == 0 else BG_INPUT
            cv.create_rectangle(0, y0, cw, y0 + ROW_H, fill=bg, outline="")
            col = color_map[p.proceso]
            cv.create_rectangle(0, y0, 5, y0 + ROW_H, fill=col, outline="")
            cv.create_text(LABEL_W - 8, y0 + ROW_H // 2, text=p.proceso, font=("Courier New", 9, "bold"), fill=col, anchor="e")

        for t in range(t_max + 1):
            x = LABEL_W + t * PX_PER_T
            cv.create_line(x, LEG_H + TOP_PAD, x, LEG_H + TOP_PAD + n * (ROW_H + ROW_PAD), fill=BORDER, dash=(2, 4))

        segs = sorted(
            [(ri, p, ini, p.fina[si], color_map[p.proceso]) for ri, p in enumerate(tabla) for si, ini in enumerate(p.inicio)],
            key=lambda s: s[2],
        )
        self._segs = segs
        self._gantt_meta = (LEG_H, TOP_PAD, ROW_H, ROW_PAD, LABEL_W, PX_PER_T, t_max, n, TICK_H)
        self._draw_cpu_seg(0)

    def _draw_cpu_seg(self, idx):
        if idx >= len(self._segs):
            self._draw_cpu_ticks()
            return
        LEG_H, TOP_PAD, ROW_H, ROW_PAD, LABEL_W, PX_PER_T, t_max, n, TICK_H = self._gantt_meta
        cv = self.gantt_canvas
        ri, p, ini, fin, col = self._segs[idx]
        y0 = LEG_H + TOP_PAD + ri * (ROW_H + ROW_PAD)
        yt, yb = y0 + 3, y0 + ROW_H - 3
        x1 = LABEL_W + ini * PX_PER_T + 1
        x2 = LABEL_W + fin * PX_PER_T - 1
        cv.create_rectangle(x1 + 2, yt + 2, x2 + 2, yb + 2, fill="#000000", outline="")
        cv.create_rectangle(x1, yt, x2, yb, fill=col, outline="")
        cv.create_rectangle(x1, yt, x2, yt + 3, fill=self._lighten(col), outline="")
        if x2 - x1 > 18:
            cv.create_text((x1 + x2) / 2, (yt + yb) / 2, text=str(fin - ini), font=("Courier New", 8, "bold"), fill="#0A0E17")
        self.after(110, self._draw_cpu_seg, idx + 1)

    def _draw_cpu_ticks(self):
        LEG_H, TOP_PAD, ROW_H, ROW_PAD, LABEL_W, PX_PER_T, t_max, n, TICK_H = self._gantt_meta
        cv = self.gantt_canvas
        ty = LEG_H + TOP_PAD + n * (ROW_H + ROW_PAD) + 5
        for t in range(t_max + 1):
            x = LABEL_W + t * PX_PER_T
            cv.create_line(x, ty, x, ty + 4, fill=TEXT_SEC)
            cv.create_text(x, ty + 13, text=str(t), font=("Courier New", 7), fill=TEXT_SEC)

    def _build_leyenda(self, color_map):
        for w in self.leyenda_frame.winfo_children():
            w.destroy()
        for nombre, color in color_map.items():
            f = tk.Frame(self.leyenda_frame, bg=BG_PANEL)
            f.pack(side="left", padx=3)
            tk.Frame(f, bg=color, width=10, height=10).pack(side="left")
            tk.Label(f, text=nombre, font=("Courier New", 7), bg=BG_PANEL, fg=TEXT_SEC).pack(side="left", padx=(2, 0))


if __name__ == "__main__":
    app = App()
    app.mainloop()
