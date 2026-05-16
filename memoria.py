import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import psutil
import threading
import copy

# ══════════════════════════════════════════════
#  PALETA
# ══════════════════════════════════════════════
BG_DARK     = "#0A0E17"
BG_PANEL    = "#111827"
BG_CARD     = "#1A2235"
BG_INPUT    = "#1F2D42"
BORDER      = "#2A3A52"
ACCENT_BLUE = "#3D8EF0"
ACCENT_CYAN = "#22D3EE"
ACCENT_GRN  = "#34D399"
ACCENT_RED  = "#F87171"
ACCENT_AMB  = "#FBBF24"
TEXT_PRI    = "#E2E8F0"
TEXT_SEC    = "#94A3B8"
TEXT_MUT    = "#475569"
SO_COLOR    = "#2D3748"
FREE_COLOR  = "#0F2A1E"
FREE_TEXT   = "#34D399"

PROC_COLORS = [
    "#3D8EF0","#34D399","#FBBF24","#F87171",
    "#A78BFA","#22D3EE","#FB923C","#4ADE80",
    "#F472B6","#60A5FA","#FACC15","#C084FC",
]

# ══════════════════════════════════════════════
#  ESTRUCTURAS
# ══════════════════════════════════════════════
class Proceso:
    def __init__(self, nombre, memoria, tiempo):
        self.nombre   = nombre
        self.memoria  = memoria
        self.tiempo   = tiempo
        self.inicio   = None
        self.fin      = None
        self.particion = None   # índice de partición asignada
        self.asignado = False

class Particion:
    def __init__(self, idx, tamanio):
        self.idx      = idx
        self.tamanio  = tamanio
        self.ocupante = None    # nombre del proceso o None
        self.libre    = True

# ══════════════════════════════════════════════
#  ALGORITMOS DE ASIGNACIÓN
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

def buddy_ajuste(particiones, proceso):
    """Buddy system: busca la potencia de 2 más cercana."""
    def sig_pot2(n):
        p = 1
        while p < n: p *= 2
        return p
    req = sig_pot2(proceso.memoria)
    cands = [p for p in particiones if p.libre and p.tamanio >= req]
    return min(cands, key=lambda p: p.tamanio) if cands else None

ALGOS = {
    "Primer Ajuste" : primer_ajuste,
    "Mejor Ajuste"  : mejor_ajuste,
    "Peor Ajuste"   : peor_ajuste,
    "Gemelos (Buddy)": buddy_ajuste,
}

# ══════════════════════════════════════════════
#  LECTURA DE ARCHIVO
# ══════════════════════════════════════════════
def leer_archivo(path, tipo):
    with open(path, 'r') as f:
        lineas = [l.strip() for l in f if l.strip()]

    particiones_tam = None
    start = 1  # siempre saltamos la primera línea

    if tipo == "Fija":
        partes = lineas[0].split()
        particiones_tam = [int(x) for x in partes]

    procesos = []
    for linea in lineas[start:]:
        partes = linea.split()
        if len(partes) < 3:
            continue
        procesos.append(Proceso(partes[0], int(partes[1]), float(partes[2])))

    return procesos, particiones_tam

# ══════════════════════════════════════════════
#  SIMULACIÓN COMPLETA (lógica correcta)
# ══════════════════════════════════════════════
def simular(procesos, particiones_obj, algo_fn):
    """
    Devuelve:
      - procesos con inicio/fin/particion calculados
      - events: lista de dicts para la animación Gantt/Memoria
        cada evento: {tiempo, tipo: 'entrada'|'salida', proceso, particion_idx}
    """
    procs = [copy.deepcopy(p) for p in procesos]
    parts = [copy.deepcopy(p) for p in particiones_obj]

    # Cola de espera (procesos no asignados aún)
    cola = list(procs)
    activos = []   # (proceso, particion, fin_time)
    events  = []
    tiempo  = 0.0
    EPS     = 1e-9

    max_iter = 0
    while (cola or activos) and max_iter < 10000:
        max_iter += 1

        # 1. Recoger todos los tiempos de fin de activos
        tiempos_fin = sorted(set(round(a[2], 6) for a in activos))

        # 2. Asignar desde la cola mientras haya particiones libres
        asignados_en_este_ciclo = True
        while asignados_en_este_ciclo and cola:
            asignados_en_este_ciclo = False
            for proc in cola[:]:
                part = algo_fn(parts, proc)
                if part:
                    part.libre    = False
                    part.ocupante = proc.nombre
                    proc.inicio   = round(tiempo, 6)
                    proc.fin      = round(tiempo + proc.tiempo, 6)
                    proc.particion = part.idx
                    proc.asignado  = True
                    activos.append((proc, part, proc.fin))
                    cola.remove(proc)
                    events.append({
                        "tiempo"  : round(tiempo, 6),
                        "tipo"    : "entrada",
                        "proceso" : proc,
                        "part_idx": part.idx,
                    })
                    asignados_en_este_ciclo = True

        if not activos:
            break

        # 3. Avanzar al próximo evento de fin
        proximo_fin = min(a[2] for a in activos)
        tiempo = proximo_fin

        # 4. Liberar los que terminan en este tiempo
        nuevos_activos = []
        for (proc, part, fin) in activos:
            if abs(fin - tiempo) < EPS:
                part.libre    = True
                part.ocupante = None
                events.append({
                    "tiempo"  : round(tiempo, 6),
                    "tipo"    : "salida",
                    "proceso" : proc,
                    "part_idx": part.idx,
                })
            else:
                nuevos_activos.append((proc, part, fin))
        activos = nuevos_activos

    return procs, events

# ══════════════════════════════════════════════
#  MONITOR CPU/RAM
# ══════════════════════════════════════════════
class MiniMonitor(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG_PANEL, **kw)
        self._cpu = 0.0; self._ram = 0.0
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
        for attr, lbl, col in [("_lbl_cpu","CPU",ACCENT_BLUE),("_lbl_ram","RAM",ACCENT_GRN)]:
            card = tk.Frame(row, bg=BG_CARD, highlightthickness=1, highlightbackground=col)
            card.pack(side="left", expand=True, fill="x", padx=(0,3 if attr=="_lbl_cpu" else 0))
            tk.Label(card, text=lbl, font=("Courier New",7,"bold"), bg=BG_CARD, fg=col).pack(pady=(5,0))
            l = tk.Label(card, text="—", font=("Courier New",16,"bold"), bg=BG_CARD, fg=TEXT_PRI)
            l.pack(pady=(0,5))
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
        self.title("Gestión de Memoria — Simulador")
        self.geometry("1500x900")
        self.resizable(False, False)
        self.configure(bg=BG_DARK)

        self.archivo_path  = tk.StringVar()
        self.algoritmo_var = tk.StringVar(value="Primer Ajuste")
        self.tipo_mem_var  = tk.StringVar(value="Dinámica")
        self.tam_mem_var   = tk.StringVar(value="256")

        self._procesos   = []
        self._particiones = []
        self._color_map  = {}
        self._events     = []
        self._sim_running = False
        self._gantt_data = []   # snapshot por cada evento para animación

        self._build_ui()

    # ══ CONSTRUCCIÓN UI ═══════════════════════════
    def _build_ui(self):
        hdr = tk.Frame(self, bg=BG_DARK, height=46)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="MEMORY MANAGEMENT SIMULATOR",
                 font=("Courier New",15,"bold"), bg=BG_DARK, fg=ACCENT_BLUE
                 ).pack(side="left", padx=20, pady=8)
        tk.Label(hdr, text="Primer Ajuste  ·  Mejor Ajuste  ·  Peor Ajuste  ·  Gemelos",
                 font=("Courier New",8), bg=BG_DARK, fg=TEXT_MUT
                 ).pack(side="left", pady=13)

        # Tarjetas de promedios en el lado derecho del header
        metrics_frame = tk.Frame(hdr, bg=BG_DARK)
        metrics_frame.pack(side="right", padx=16, pady=5)

        for attr, label, color in [("_hdr_tr","Ø T.Retorno",ACCENT_CYAN),
                                    ("_hdr_te","Ø T.Espera", ACCENT_AMB)]:
            card = tk.Frame(metrics_frame, bg=BG_CARD,
                             highlightthickness=1, highlightbackground=color)
            card.pack(side="left", padx=(0,6))
            tk.Label(card, text=label, font=("Courier New",7,"bold"),
                     bg=BG_CARD, fg=color).pack(side="left", padx=(8,4), pady=6)
            lbl = tk.Label(card, text="—", font=("Courier New",13,"bold"),
                            bg=BG_CARD, fg=TEXT_PRI)
            lbl.pack(side="left", padx=(0,10), pady=6)
            setattr(self, attr, lbl)

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        top = tk.Frame(self, bg=BG_DARK)
        top.pack(fill="both", expand=False, padx=14, pady=(10,4))
        self._build_left(top)
        self._build_table(top)

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=14)

        bot = tk.Frame(self, bg=BG_DARK)
        bot.pack(fill="both", expand=True, padx=14, pady=(4,10))
        self._build_mem_viz(bot)
        self._build_gantt(bot)

    # ── Panel izquierdo ───────────────────────────
    def _build_left(self, parent):
        frame = tk.Frame(parent, bg=BG_PANEL, width=290)
        frame.pack(side="left", fill="y", padx=(0,10))
        frame.pack_propagate(False)

        # Algoritmo (combo desplegable)
        self._sec(frame, "⚙  ALGORITMO")
        combo = ttk.Combobox(frame, textvariable=self.algoritmo_var,
                              values=list(ALGOS.keys()),
                              state="readonly",
                              font=("Courier New",9,"bold"))
        combo.pack(fill="x", padx=10, pady=(2,0), ipady=3)
        style = ttk.Style()
        style.configure("TCombobox",
                        fieldbackground=BG_INPUT,
                        background=BG_INPUT,
                        foreground=TEXT_PRI,
                        selectbackground=ACCENT_BLUE,
                        selectforeground=TEXT_PRI,
                        bordercolor=BORDER,
                        arrowcolor=ACCENT_BLUE)

        # Tipo de memoria
        self._sec(frame, "💾  TIPO DE MEMORIA")
        tm_row = tk.Frame(frame, bg=BG_PANEL)
        tm_row.pack(fill="x", padx=10, pady=(2,0))
        for t in ("Dinámica", "Fija"):
            tk.Radiobutton(tm_row, text=t, variable=self.tipo_mem_var, value=t,
                           font=("Courier New",9,"bold"), bg=BG_PANEL, fg=TEXT_PRI,
                           activebackground=BG_PANEL, activeforeground=ACCENT_CYAN,
                           selectcolor=BG_INPUT, indicatoron=0,
                           bd=0, padx=10, pady=4, relief="flat", cursor="hand2",
                           width=10).pack(side="left", padx=(0,5))

        # Archivo
        self._sec(frame, "📂  ARCHIVO DE DATOS")
        fr = tk.Frame(frame, bg=BG_PANEL)
        fr.pack(fill="x", padx=10, pady=(2,0))
        self.file_lbl = tk.Label(fr, text="Sin archivo…",
                                  font=("Courier New",8), bg=BG_INPUT, fg=TEXT_MUT,
                                  anchor="w", width=18, padx=5, pady=4)
        self.file_lbl.pack(side="left", fill="x", expand=True)
        self._btn(fr, "Buscar", self._browse, ACCENT_BLUE).pack(side="left", padx=(5,0))

        # Tamaño + botón ejecutar en la misma fila
        self._sec(frame, "📐  TAMAÑO DE MEMORIA (KB)")
        row_tam = tk.Frame(frame, bg=BG_PANEL)
        row_tam.pack(fill="x", padx=10, pady=(2,0))
        tk.Entry(row_tam, textvariable=self.tam_mem_var,
                 font=("Courier New",10,"bold"), width=8,
                 bg=BG_INPUT, fg=ACCENT_AMB, insertbackground=ACCENT_AMB,
                 bd=0, highlightthickness=1, highlightcolor=ACCENT_BLUE,
                 highlightbackground=BORDER, relief="flat"
                 ).pack(side="left", ipady=4)
        tk.Label(row_tam, text=" KB", font=("Courier New",9),
                 bg=BG_PANEL, fg=TEXT_SEC).pack(side="left")
        tk.Button(row_tam, text="▶ SIMULAR",
                  font=("Courier New",9,"bold"),
                  bg=ACCENT_GRN, fg="#0A0E17",
                  activebackground="#059669", activeforeground="#0A0E17",
                  bd=0, padx=10, pady=5, cursor="hand2", relief="flat",
                  command=self._ejecutar).pack(side="left", padx=(10,0))

        # Detener
        tk.Button(frame, text="⏹  DETENER",
                  font=("Courier New",8),
                  bg=BG_INPUT, fg=ACCENT_RED,
                  activebackground=BORDER, activeforeground=ACCENT_RED,
                  bd=0, pady=4, cursor="hand2", relief="flat",
                  command=self._detener).pack(fill="x", padx=10, pady=(6,6))

        tk.Frame(frame, bg=BORDER, height=1).pack(fill="x", padx=8)

        # Monitor CPU/RAM
        self._sec(frame, "")  # pequeño espacio
        mon_row = tk.Frame(frame, bg=BG_PANEL)
        mon_row.pack(fill="x", padx=10, pady=(0,6))
        self.monitor = MiniMonitor(mon_row)
        self.monitor.pack(fill="x")

    # ── Tabla procesos ────────────────────────────
    def _build_table(self, parent):
        frame = tk.Frame(parent, bg=BG_PANEL)
        frame.pack(side="left", fill="both", expand=True)
        self._sec(frame, "🗂  TABLA DE PROCESOS")

        cols = ("Proceso","Mem(KB)","Tiempo",
                "T.Inicio","T.Fin","T.Retorno","T.Espera")
        style = ttk.Style()
        style.configure("M.Treeview",
                        background=BG_CARD, foreground=TEXT_PRI,
                        rowheight=27, fieldbackground=BG_CARD,
                        bordercolor=BORDER, relief="flat",
                        font=("Courier New",9))
        style.configure("M.Treeview.Heading",
                        background=BG_INPUT, foreground=ACCENT_BLUE,
                        font=("Courier New",9,"bold"), relief="flat")
        style.map("M.Treeview",
                  background=[("selected","#1a3050")],
                  foreground=[("selected",TEXT_PRI)])

        wrap = tk.Frame(frame, bg=BG_PANEL)
        wrap.pack(fill="both", expand=True, padx=10, pady=(2,10))

        self.tree = ttk.Treeview(wrap, columns=cols, show="headings",
                                  style="M.Treeview", height=10)
        widths = [90,85,80,90,90,100,95]
        for c, w in zip(cols, widths):
            self.tree.heading(c, text=c)
            self.tree.column(c, anchor="center", width=w)

        vsb = ttk.Scrollbar(wrap, orient="vertical",   command=self.tree.yview)
        hsb = ttk.Scrollbar(wrap, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)

    # ── Visualización memoria ─────────────────────
    def _build_mem_viz(self, parent):
        frame = tk.Frame(parent, bg=BG_PANEL, width=230)
        frame.pack(side="left", fill="y", padx=(0,8))
        frame.pack_propagate(False)

        self._sec_lbl = tk.Label(frame, text="🧠  MAPA DE MEMORIA",
                                  font=("Courier New",7,"bold"),
                                  bg=BG_PANEL, fg=TEXT_MUT)
        self._sec_lbl.pack(anchor="w", padx=8, pady=(8,2))

        self.mem_canvas = tk.Canvas(frame, bg=BG_DARK,
                                     highlightthickness=0, bd=0)
        self.mem_canvas.pack(fill="both", expand=True, padx=8, pady=(0,8))

    # ── Gantt ─────────────────────────────────────
    def _build_gantt(self, parent):
        frame = tk.Frame(parent, bg=BG_PANEL)
        frame.pack(side="left", fill="both", expand=True)

        hdr = tk.Frame(frame, bg=BG_PANEL)
        hdr.pack(fill="x", padx=10, pady=(8,2))
        tk.Label(hdr, text="📈  DIAGRAMA DE GANTT  (ejecución por proceso)",
                 font=("Courier New",8,"bold"), bg=BG_PANEL, fg=TEXT_MUT).pack(side="left")
        self.leyenda_frame = tk.Frame(hdr, bg=BG_PANEL)
        self.leyenda_frame.pack(side="right")

        wrap = tk.Frame(frame, bg=BG_DARK)
        wrap.pack(fill="both", expand=True, padx=10, pady=(0,8))

        self.gantt_canvas = tk.Canvas(wrap, bg=BG_DARK,
                                       highlightthickness=0, bd=0)
        hscb = ttk.Scrollbar(wrap, orient="horizontal",
                              command=self.gantt_canvas.xview)
        vscb = ttk.Scrollbar(wrap, orient="vertical",
                              command=self.gantt_canvas.yview)
        self.gantt_canvas.configure(xscrollcommand=hscb.set,
                                     yscrollcommand=vscb.set)
        hscb.pack(side="bottom", fill="x")
        vscb.pack(side="right",  fill="y")
        self.gantt_canvas.pack(side="left", fill="both", expand=True)
        self.gantt_canvas.bind("<MouseWheel>",
            lambda e: self.gantt_canvas.yview_scroll(-1*(e.delta//120), "units"))
        self.gantt_canvas.bind("<Shift-MouseWheel>",
            lambda e: self.gantt_canvas.xview_scroll(-1*(e.delta//120), "units"))

    # ══ Helpers ════════════════════════════════════
    def _sec(self, parent, txt):
        tk.Label(parent, text=txt, font=("Courier New",7,"bold"),
                 bg=BG_PANEL, fg=TEXT_MUT).pack(anchor="w", padx=10, pady=(10,1))

    def _btn(self, parent, txt, cmd, color):
        return tk.Button(parent, text=txt, font=("Courier New",8,"bold"),
                         bg=color, fg="#0A0E17", activebackground=color,
                         bd=0, padx=9, pady=4, cursor="hand2", relief="flat",
                         command=cmd)

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Seleccionar archivo",
            filetypes=[("Texto/CSV","*.txt *.csv"), ("Todos","*.*")])
        if path:
            self.archivo_path.set(path)
            self.file_lbl.configure(text=path.split("/")[-1], fg=TEXT_PRI)

    def _lighten(self, hx, amt=55):
        r = min(255, int(hx[1:3],16)+amt)
        g = min(255, int(hx[3:5],16)+amt)
        b = min(255, int(hx[5:7],16)+amt)
        return f"#{r:02X}{g:02X}{b:02X}"

    # ══ EJECUTAR ═══════════════════════════════════
    def _ejecutar(self):
        if not self.archivo_path.get():
            messagebox.showwarning("Sin archivo", "Selecciona un archivo primero.")
            return
        try:
            tam_total = int(self.tam_mem_var.get())
            if tam_total < 1: raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Tamaño de memoria inválido.")
            return

        self._detener()
        self._limpiar()

        try:
            procesos, particiones_tam = leer_archivo(
                self.archivo_path.get(), self.tipo_mem_var.get())
        except Exception as e:
            messagebox.showerror("Error leyendo archivo", str(e))
            return

        if not procesos:
            messagebox.showwarning("Vacío", "No se encontraron procesos.")
            return

        # Construir particiones
        if self.tipo_mem_var.get() == "Fija" and particiones_tam:
            self._particiones = [Particion(i, t)
                                  for i, t in enumerate(particiones_tam)]
        else:
            # Dinámica: una partición por proceso (tamaño = memoria del proceso)
            self._particiones = [Particion(i, p.memoria)
                                  for i, p in enumerate(procesos)]

        # Colores
        self._color_map = {p.nombre: PROC_COLORS[i % len(PROC_COLORS)]
                           for i, p in enumerate(procesos)}

        # Simular
        algo_fn = ALGOS[self.algoritmo_var.get()]
        procs, events = simular(procesos, self._particiones, algo_fn)
        self._procesos = procs
        self._events   = events

        # Recalcular particiones originales para el mapa de memoria
        if self.tipo_mem_var.get() == "Fija" and particiones_tam:
            self._particiones = [Particion(i, t)
                                  for i, t in enumerate(particiones_tam)]
        else:
            self._particiones = [Particion(i, p.memoria)
                                  for i, p in enumerate(procesos)]

        # Poblar tabla
        # todos los procesos llegan en T=0 (T.llegada = 0)
        for i, p in enumerate(procs):
            if p.asignado:
                tr = round(p.fin - 0, 4)          # TR = T.fin - T.llegada(0)
                te = round(p.inicio - 0, 4)        # TE = T.inicio - T.llegada(0)
            else:
                tr = te = "—"
            tag = "even" if i % 2 == 0 else "odd"
            self.tree.insert("", "end", tags=(tag,), values=(
                p.nombre, p.memoria, p.tiempo,
                p.inicio if p.asignado else "—",
                p.fin    if p.asignado else "—",
                tr, te,
            ))
        self.tree.tag_configure("even", background=BG_CARD)
        self.tree.tag_configure("odd",  background=BG_INPUT)

        # Actualizar promedios en header
        asignados = [p for p in procs if p.asignado]
        if asignados:
            avg_tr = round(sum(p.fin - 0 for p in asignados) / len(asignados), 3)
            avg_te = round(sum(p.inicio - 0 for p in asignados) / len(asignados), 3)
            self._hdr_tr.configure(text=str(avg_tr))
            self._hdr_te.configure(text=str(avg_te))
        else:
            self._hdr_tr.configure(text="—")
            self._hdr_te.configure(text="—")

        # Leyenda
        self._build_leyenda()

        # Dibujar mapa de memoria (estado inicial)
        self._draw_mem_snapshot(tam_total, {})

        # Preparar y arrancar animación Gantt + Memoria
        self._build_gantt_layout()
        self._sim_running = True
        self._animate_events(0, tam_total)

    def _detener(self):
        self._sim_running = False

    def _limpiar(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        self.mem_canvas.delete("all")
        self.gantt_canvas.delete("all")
        for w in self.leyenda_frame.winfo_children():
            w.destroy()

    # ══ ANIMACIÓN ══════════════════════════════════
    def _animate_events(self, idx, tam_total):
        if not self._sim_running:
            return
        if idx >= len(self._events):
            return

        ev = self._events[idx]

        # Actualizar estado de particiones
        for p in self._particiones:
            if p.idx == ev["part_idx"]:
                if ev["tipo"] == "entrada":
                    p.libre    = False
                    p.ocupante = ev["proceso"].nombre
                else:
                    p.libre    = True
                    p.ocupante = None
                break

        # Redibujar mapa de memoria
        ocupadas = {p.idx: p.ocupante for p in self._particiones if not p.libre}
        self._draw_mem_snapshot(tam_total, ocupadas)

        # Pintar segmento Gantt
        if ev["tipo"] == "entrada":
            proc = ev["proceso"]
            self._draw_gantt_segment(proc)

        # Siguiente evento con delay proporcional
        delay = 600
        self.after(delay, self._animate_events, idx + 1, tam_total)

    # ══ MAPA DE MEMORIA ════════════════════════════
    def _draw_mem_snapshot(self, tam_total, ocupadas):
        cv = self.mem_canvas
        cv.delete("all")

        W = cv.winfo_width()
        if W < 10: W = 210

        PAD_X  = 16
        BW     = W - 2*PAD_X        # ancho de la barra
        X1     = PAD_X
        X2     = PAD_X + BW
        H      = cv.winfo_height()
        if H < 50: H = 380

        SO_RATIO = 0.08              # S.O. ocupa 8% visual fijo
        MEM_H    = H - 16           # altura disponible para la memoria

        SO_H     = max(28, int(MEM_H * SO_RATIO))
        AVAIL_H  = MEM_H - SO_H     # altura para las particiones
        Y0       = 8

        # ── Borde exterior ──
        cv.create_rectangle(X1-2, Y0-2, X2+2, Y0+MEM_H+2,
                             outline=ACCENT_BLUE, width=2, fill="")

        # ── Segmento S.O. ──
        cv.create_rectangle(X1, Y0, X2, Y0+SO_H,
                             fill=SO_COLOR, outline=BORDER, width=1)
        cv.create_text((X1+X2)//2, Y0+SO_H//2,
                        text="S.O.", font=("Courier New",8,"bold"), fill=ACCENT_BLUE)

        # ── Particiones ──
        total_tam = sum(p.tamanio for p in self._particiones)
        if total_tam == 0: return

        py = Y0 + SO_H

        # Borde más grueso y oscuro para particiones fijas
        es_fija = self.tipo_mem_var.get() == "Fija"
        part_border_col = "#000000" if es_fija else BORDER
        part_border_w   = 3        if es_fija else 1

        # Altura mínima por partición (sin texto si hay muchas)
        MIN_PH    = max(8, AVAIL_H // max(len(self._particiones), 1))
        SHOW_TEXT = MIN_PH >= 22   # mostrar texto solo si hay espacio suficiente

        for part in self._particiones:
            ratio = part.tamanio / total_tam
            ph    = max(8, int(AVAIL_H * ratio))
            if part.idx == self._particiones[-1].idx:
                ph = (Y0 + MEM_H) - py

            nombre_proc = ocupadas.get(part.idx, None)

            if nombre_proc:
                color    = self._color_map.get(nombre_proc, ACCENT_BLUE)
                proc_obj = next((p for p in self._procesos if p.nombre == nombre_proc), None)

                if proc_obj and self.tipo_mem_var.get() == "Fija":
                    proc_ratio = proc_obj.memoria / part.tamanio
                    proc_h     = max(4, int(ph * proc_ratio))
                    frag_h     = ph - proc_h

                    cv.create_rectangle(X1, py, X2, py+proc_h,
                                         fill=color, outline=part_border_col, width=part_border_w)
                    if SHOW_TEXT and proc_h >= 14:
                        cv.create_text((X1+X2)//2, py+proc_h//2,
                                        text=f"{nombre_proc}\n{proc_obj.memoria}KB",
                                        font=("Courier New",7,"bold"),
                                        fill="#0A0E17", justify="center")
                    elif proc_h >= 10:
                        cv.create_text((X1+X2)//2, py+proc_h//2,
                                        text=nombre_proc,
                                        font=("Courier New",6,"bold"),
                                        fill="#0A0E17")

                    if frag_h > 4:
                        frag_kb = part.tamanio - proc_obj.memoria
                        cv.create_rectangle(X1, py+proc_h, X2, py+ph,
                                             fill="#2D1010", outline=ACCENT_RED,
                                             width=1, dash=(3,2))
                        if frag_h >= 12:
                            cv.create_text((X1+X2)//2, py+proc_h+frag_h//2,
                                            text=f"F {frag_kb}K" if frag_h < 22 else f"Frag\n{frag_kb}KB",
                                            font=("Courier New",6,"bold"),
                                            fill=ACCENT_RED, justify="center")
                else:
                    cv.create_rectangle(X1, py, X2, py+ph,
                                         fill=color, outline=part_border_col, width=part_border_w)
                    if SHOW_TEXT and ph >= 14:
                        cv.create_text((X1+X2)//2, py+ph//2,
                                        text=f"{nombre_proc}\n{part.tamanio}KB",
                                        font=("Courier New",7,"bold"),
                                        fill="#0A0E17", justify="center")
                    elif ph >= 10:
                        cv.create_text((X1+X2)//2, py+ph//2,
                                        text=nombre_proc,
                                        font=("Courier New",6,"bold"),
                                        fill="#0A0E17")
            else:
                cv.create_rectangle(X1, py, X2, py+ph,
                                     fill=FREE_COLOR, outline=part_border_col,
                                     width=part_border_w)
                if SHOW_TEXT and ph >= 14:
                    cv.create_text((X1+X2)//2, py+ph//2,
                                    text=f"LIBRE\n{part.tamanio}KB",
                                    font=("Courier New",7,"bold"),
                                    fill=FREE_TEXT, justify="center")
                elif ph >= 10:
                    cv.create_text((X1+X2)//2, py+ph//2,
                                    text="·",
                                    font=("Courier New",8),
                                    fill=FREE_TEXT)

            # Etiqueta P# a la derecha solo si hay espacio
            if ph >= 10:
                cv.create_text(X2+4, py+ph//2,
                                text=f"P{part.idx}",
                                font=("Courier New",6), fill=TEXT_MUT, anchor="w")
            py += ph

    # ══ GANTT ══════════════════════════════════════
    def _build_gantt_layout(self):
        cv = self.gantt_canvas
        cv.delete("all")

        n     = len(self._procesos)
        t_max = max((p.fin    for p in self._procesos if p.asignado), default=1.0)
        t_min = min((p.tiempo for p in self._procesos if p.asignado), default=1.0)

        cv.update_idletasks()
        cv_w = cv.winfo_width()
        if cv_w < 200: cv_w = 860

        usable = cv_w - 90
        px_fit     = usable / t_max
        px_min_blk = max(90, usable / max(n, 1))
        px_for_min = px_min_blk / t_min if t_min > 0 else px_fit
        self._g_PX_PER_T = max(px_fit, px_for_min, 80)

        self._g_ROW_H    = max(26, min(46, 300 // max(n, 1)))
        self._g_ROW_PAD  = max(3,  min(8,  self._g_ROW_H // 7))
        self._g_LABEL_W  = 72
        self._g_TOP_PAD  = 18
        self._g_LEG_H    = 14
        self._g_row      = {p.nombre: i for i, p in enumerate(self._procesos)}
        self._g_t_max    = t_max

        for i, p in enumerate(self._procesos):
            color = self._color_map[p.nombre]
            y0 = self._g_LEG_H + self._g_TOP_PAD + i*(self._g_ROW_H+self._g_ROW_PAD)
            bg = BG_CARD if i%2==0 else BG_INPUT
            cv.create_rectangle(0, y0, 99999, y0+self._g_ROW_H, fill=bg, outline="", tags="bg")
            cv.create_rectangle(0, y0, 5, y0+self._g_ROW_H, fill=color, outline="", tags="bg")
            cv.create_text(self._g_LABEL_W-8, y0+self._g_ROW_H//2,
                            text=p.nombre, font=("Courier New",9,"bold"),
                            fill=color, anchor="e", tags="bg")

        self._update_gantt_scroll()

    def _update_gantt_scroll(self):
        n  = len(self._procesos)
        cw = self._g_LABEL_W + self._g_t_max * self._g_PX_PER_T + 80
        ch = self._g_LEG_H + self._g_TOP_PAD + n*(self._g_ROW_H+self._g_ROW_PAD) + 30
        self.gantt_canvas.configure(scrollregion=(0, 0, cw, ch))

    def _draw_gantt_segment(self, proc):
        cv    = self.gantt_canvas
        row_i = self._g_row.get(proc.nombre, 0)
        col   = self._color_map[proc.nombre]

        y0 = self._g_LEG_H + self._g_TOP_PAD + row_i*(self._g_ROW_H+self._g_ROW_PAD)
        yt = y0 + 4
        yb = y0 + self._g_ROW_H - 4

        x1 = self._g_LABEL_W + proc.inicio * self._g_PX_PER_T + 1
        x2 = self._g_LABEL_W + proc.fin    * self._g_PX_PER_T - 1

        cv.create_rectangle(x1+2, yt+2, x2+2, yb+2, fill="#000000", outline="")
        cv.create_rectangle(x1, yt, x2, yb, fill=col, outline="")
        cv.create_rectangle(x1, yt, x2, yt+3, fill=self._lighten(col), outline="")

        blk_w = x2 - x1
        if blk_w > 40:
            cv.create_text((x1+x2)/2, (yt+yb)/2,
                            text=f"{proc.nombre}\n{proc.memoria}KB",
                            font=("Courier New",8,"bold"), fill="#0A0E17", justify="center")
        elif blk_w > 20:
            cv.create_text((x1+x2)/2, (yt+yb)/2,
                            text=f"{proc.memoria}KB",
                            font=("Courier New",7,"bold"), fill="#0A0E17")

        cv.delete("ticks")
        cv.delete("grid")

        n     = len(self._procesos)
        y_top = self._g_LEG_H + self._g_TOP_PAD
        y_bot = y_top + n*(self._g_ROW_H+self._g_ROW_PAD)
        tick_y = y_bot + 5

        tiempos = sorted(set(
            [0.0] +
            [round(p.inicio, 4) for p in self._procesos if p.asignado] +
            [round(p.fin,    4) for p in self._procesos if p.asignado]
        ))

        last_tick_x = -999
        for t in tiempos:
            x = self._g_LABEL_W + t * self._g_PX_PER_T
            cv.create_line(x, y_top, x, y_bot, fill=BORDER, dash=(2,4), tags="grid")
            cv.create_line(x, tick_y, x, tick_y+5, fill=TEXT_SEC, tags="ticks")
            if x - last_tick_x >= 28:
                cv.create_text(x, tick_y+15, text=str(round(t,3)),
                                font=("Courier New",7), fill=TEXT_SEC, tags="ticks")
                last_tick_x = x

        self._update_gantt_scroll()

    # ══ LEYENDA ════════════════════════════════════
    def _build_leyenda(self):
        for w in self.leyenda_frame.winfo_children():
            w.destroy()
        for nombre, color in self._color_map.items():
            f = tk.Frame(self.leyenda_frame, bg=BG_PANEL)
            f.pack(side="left", padx=3)
            tk.Frame(f, bg=color, width=10, height=10).pack(side="left")
            tk.Label(f, text=nombre, font=("Courier New",7),
                     bg=BG_PANEL, fg=TEXT_SEC).pack(side="left", padx=(2,0))


# ══════════════════════════════════════════════
if __name__ == "__main__":
    app = App()
    app.mainloop()