import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import psutil
import threading
import math
import time

# ══════════════════════════════════════════════
#  PALETA
# ══════════════════════════════════════════════
BG_DARK      = "#0A0E17"
BG_PANEL     = "#111827"
BG_CARD      = "#1A2235"
BG_INPUT     = "#1F2D42"
BORDER       = "#2A3A52"
ACCENT_BLUE  = "#3D8EF0"
ACCENT_CYAN  = "#22D3EE"
ACCENT_GREEN = "#34D399"
ACCENT_RED   = "#F87171"
ACCENT_AMBER = "#FBBF24"
ACCENT_PURP  = "#A78BFA"
TEXT_PRI     = "#E2E8F0"
TEXT_SEC     = "#94A3B8"
TEXT_MUT     = "#475569"
SO_COLOR     = "#374151"

PROC_COLORS = [
    "#3D8EF0","#34D399","#FBBF24","#F87171",
    "#A78BFA","#22D3EE","#FB923C","#4ADE80",
    "#F472B6","#60A5FA","#FACC15","#C084FC",
]

FREE_COLOR   = "#1E3A2F"
FREE_TEXT    = "#34D399"

# ══════════════════════════════════════════════
#  ESTRUCTURAS DE DATOS
# ══════════════════════════════════════════════
class Proceso:
    def __init__(self, nombre, memoria, tiempo):
        self.nombre  = nombre
        self.memoria = memoria   # tamaño en KB/MB
        self.tiempo  = tiempo    # duración (unidades de tiempo)
        self.inicio  = None
        self.fin     = None
        self.bloque  = None      # índice de bloque asignado (fija) o dirección (dinámica)
        self.asignado = False

class BloqueMemoria:
    def __init__(self, inicio, tamanio):
        self.inicio   = inicio
        self.tamanio  = tamanio
        self.proceso  = None      # None = libre
        self.libre    = True

# ══════════════════════════════════════════════
#  ALGORITMOS DE GESTIÓN
# ══════════════════════════════════════════════

def primer_ajuste(bloques, proceso):
    for b in bloques:
        if b.libre and b.tamanio >= proceso.memoria:
            return b
    return None

def mejor_ajuste(bloques, proceso):
    candidatos = [b for b in bloques if b.libre and b.tamanio >= proceso.memoria]
    if not candidatos:
        return None
    return min(candidatos, key=lambda b: b.tamanio - proceso.memoria)

def peor_ajuste(bloques, proceso):
    candidatos = [b for b in bloques if b.libre and b.tamanio >= proceso.memoria]
    if not candidatos:
        return None
    return max(candidatos, key=lambda b: b.tamanio)

def algoritmo_gemelos(bloques, proceso):
    """Buddy system simplificado: busca bloque de potencia de 2 suficiente."""
    def siguiente_pot2(n):
        p = 1
        while p < n:
            p *= 2
        return p
    tam_req = siguiente_pot2(proceso.memoria)
    candidatos = [b for b in bloques if b.libre and b.tamanio >= tam_req]
    if not candidatos:
        return None
    return min(candidatos, key=lambda b: b.tamanio)

ALGOS = {
    "Primer Ajuste":    primer_ajuste,
    "Mejor Ajuste":     mejor_ajuste,
    "Peor Ajuste":      peor_ajuste,
    "Gemelos (Buddy)":  algoritmo_gemelos,
}

# ══════════════════════════════════════════════
#  LECTURA DE ARCHIVO
# ══════════════════════════════════════════════
def leer_archivo(path, tipo_memoria):
    """
    Retorna (procesos, particiones_fijas_o_None).
    Si tipo_memoria=='Fija', la primera línea contiene tamaños de partición.
    """
    procesos   = []
    particiones = None

    with open(path, 'r') as f:
        lineas = [l.strip() for l in f if l.strip()]

    start = 0
    if tipo_memoria == "Fija":
        partes = lineas[0].split()
        particiones = [int(p) for p in partes]
        start = 1           # saltar primera línea en particiones fijas
    else:
        start = 1           # ignorar primera línea en dinámica

    for linea in lineas[start:]:
        partes = linea.split()
        if len(partes) < 3:
            continue
        nombre  = partes[0]
        memoria = int(partes[1])
        tiempo  = float(partes[2])
        procesos.append(Proceso(nombre, memoria, tiempo))

    return procesos, particiones

# ══════════════════════════════════════════════
#  MONITOR CPU/RAM
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

    def _color(self, v):
        if v < 60:   return ACCENT_GREEN
        elif v < 85: return ACCENT_AMBER
        else:        return ACCENT_RED

    def _build(self):
        for attr, label, col in [("_lbl_cpu","CPU",ACCENT_BLUE),("_lbl_ram","RAM",ACCENT_GREEN)]:
            card = tk.Frame(self, bg=BG_CARD, highlightthickness=1, highlightbackground=col)
            card.pack(side="left", expand=True, fill="x", padx=(0 if attr=="_lbl_ram" else 0, 4 if attr=="_lbl_cpu" else 0))
            tk.Label(card, text=label, font=("Courier New",7,"bold"), bg=BG_CARD, fg=col).pack(pady=(6,0))
            lbl = tk.Label(card, text="—", font=("Courier New",18,"bold"), bg=BG_CARD, fg=TEXT_PRI)
            lbl.pack(pady=(0,6))
            setattr(self, attr, lbl)

    def _refresh(self):
        self._lbl_cpu.configure(text=f"{self._cpu:.0f}%", fg=self._color(self._cpu))
        self._lbl_ram.configure(text=f"{self._ram:.0f}%", fg=self._color(self._ram))
        threading.Thread(target=self._measure, daemon=True).start()
        self.after(1000, self._refresh)

# ══════════════════════════════════════════════
#  APLICACIÓN PRINCIPAL
# ══════════════════════════════════════════════
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gestión de Memoria — Simulador")
        self.geometry("1500x900")
        self.resizable(False, False)
        self.configure(bg=BG_DARK)

        # Estado
        self.archivo_path  = tk.StringVar()
        self.algoritmo_var = tk.StringVar(value="Primer Ajuste")
        self.tipo_mem_var  = tk.StringVar(value="Dinámica")
        self.tam_mem_var   = tk.StringVar(value="256")

        self._procesos   = []
        self._bloques    = []
        self._color_map  = {}
        self._sim_running = False
        self._sim_tick   = 0
        self._timeline   = []   # lista de (tick, nombre_proc, color)
        self._gantt_seg  = []   # segmentos pintados en gantt

        self._build_ui()

    # ══ UI ══════════════════════════════════════
    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg=BG_DARK, height=46)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="MEMORY MANAGEMENT SIMULATOR",
                 font=("Courier New",15,"bold"), bg=BG_DARK, fg=ACCENT_BLUE).pack(side="left", padx=20, pady=8)
        tk.Label(hdr, text="Primer Ajuste  ·  Mejor Ajuste  ·  Peor Ajuste  ·  Gemelos",
                 font=("Courier New",8), bg=BG_DARK, fg=TEXT_MUT).pack(side="left", pady=13)
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        # Zona superior: izquierda | tabla
        top = tk.Frame(self, bg=BG_DARK)
        top.pack(fill="both", expand=False, padx=14, pady=(10,4))

        self._build_left(top)
        self._build_table(top)

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=14)

        # Zona inferior: memoria visual | gantt
        bot = tk.Frame(self, bg=BG_DARK)
        bot.pack(fill="both", expand=True, padx=14, pady=(4,10))

        self._build_memory_viz(bot)
        self._build_gantt(bot)

    # ── Panel izquierdo ──────────────────────────
    def _build_left(self, parent):
        frame = tk.Frame(parent, bg=BG_PANEL, width=290)
        frame.pack(side="left", fill="y", padx=(0,10))
        frame.pack_propagate(False)

        # Algoritmo
        self._sec(frame, "⚙  ALGORITMO")
        alg_frame = tk.Frame(frame, bg=BG_PANEL)
        alg_frame.pack(fill="x", padx=10, pady=(2,0))
        for alg in ALGOS:
            tk.Radiobutton(alg_frame, text=alg, variable=self.algoritmo_var, value=alg,
                           font=("Courier New",8,"bold"), bg=BG_PANEL, fg=TEXT_PRI,
                           activebackground=BG_PANEL, activeforeground=ACCENT_BLUE,
                           selectcolor=BG_INPUT, indicatoron=0,
                           bd=0, padx=8, pady=3, relief="flat", cursor="hand2",
                           anchor="w", width=20).pack(fill="x", pady=1)

        # Tipo memoria
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

        # Tamaño total de memoria
        self._sec(frame, "📐  TAMAÑO DE MEMORIA (KB)")
        tm_entry_row = tk.Frame(frame, bg=BG_PANEL)
        tm_entry_row.pack(fill="x", padx=10, pady=(2,0))
        tk.Entry(tm_entry_row, textvariable=self.tam_mem_var,
                 font=("Courier New",10,"bold"), width=10,
                 bg=BG_INPUT, fg=ACCENT_AMBER, insertbackground=ACCENT_AMBER,
                 bd=0, highlightthickness=1, highlightcolor=ACCENT_BLUE,
                 highlightbackground=BORDER, relief="flat"
                 ).pack(side="left", ipady=4)
        tk.Label(tm_entry_row, text=" KB", font=("Courier New",9),
                 bg=BG_PANEL, fg=TEXT_SEC).pack(side="left")

        # Ejecutar
        tk.Button(frame, text="▶  SIMULAR",
                  font=("Courier New",10,"bold"),
                  bg=ACCENT_GREEN, fg="#0A0E17",
                  activebackground="#059669", activeforeground="#0A0E17",
                  bd=0, pady=8, cursor="hand2", relief="flat",
                  command=self._ejecutar).pack(fill="x", padx=10, pady=10)

        tk.Button(frame, text="⏹  DETENER",
                  font=("Courier New",9),
                  bg=BG_INPUT, fg=ACCENT_RED,
                  activebackground=BORDER, activeforeground=ACCENT_RED,
                  bd=0, pady=5, cursor="hand2", relief="flat",
                  command=self._detener).pack(fill="x", padx=10, pady=(0,8))

        tk.Frame(frame, bg=BORDER, height=1).pack(fill="x", padx=8)

        # Monitor CPU/RAM
        mon_row = tk.Frame(frame, bg=BG_PANEL)
        mon_row.pack(fill="x", padx=10, pady=(8,6))
        self.monitor = MiniMonitor(mon_row)
        self.monitor.pack(fill="x")

    # ── Tabla derecha ────────────────────────────
    def _build_table(self, parent):
        frame = tk.Frame(parent, bg=BG_PANEL)
        frame.pack(side="left", fill="both", expand=True)
        self._sec(frame, "🗂  TABLA DE PROCESOS")

        cols = ("Proceso","Memoria (KB)","Tiempo","Bloque/Dir","T.Inicio","T.Fin","T.Retorno","T.Espera")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("M.Treeview",
                        background=BG_CARD, foreground=TEXT_PRI,
                        rowheight=28, fieldbackground=BG_CARD,
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
        widths = [80,95,70,90,70,70,90,80]
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

    # ── Visualización de memoria (izq inferior) ──
    def _build_memory_viz(self, parent):
        frame = tk.Frame(parent, bg=BG_PANEL, width=260)
        frame.pack(side="left", fill="y", padx=(0,8))
        frame.pack_propagate(False)

        self._sec_inline(frame, "🧠  MAPA DE MEMORIA")

        wrap = tk.Frame(frame, bg=BG_DARK)
        wrap.pack(fill="both", expand=True, padx=8, pady=(2,8))

        self.mem_canvas = tk.Canvas(wrap, bg=BG_DARK,
                                     highlightthickness=0, bd=0, width=240)
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.mem_canvas.yview)
        self.mem_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.mem_canvas.pack(side="left", fill="both", expand=True)
        self.mem_canvas.bind("<MouseWheel>",
            lambda e: self.mem_canvas.yview_scroll(-1*(e.delta//120), "units"))

    # ── Diagrama de Gantt (der inferior) ─────────
    def _build_gantt(self, parent):
        frame = tk.Frame(parent, bg=BG_PANEL)
        frame.pack(side="left", fill="both", expand=True)

        hdr = tk.Frame(frame, bg=BG_PANEL)
        hdr.pack(fill="x", padx=10, pady=(8,2))
        tk.Label(hdr, text="⏱  DIAGRAMA DE EJECUCIÓN (Gantt por segundos)",
                 font=("Courier New",8,"bold"), bg=BG_PANEL, fg=TEXT_MUT).pack(side="left")

        # Leyenda dinámica
        self.leyenda_frame = tk.Frame(hdr, bg=BG_PANEL)
        self.leyenda_frame.pack(side="right")

        wrap = tk.Frame(frame, bg=BG_DARK)
        wrap.pack(fill="both", expand=True, padx=10, pady=(0,8))

        self.gantt_canvas = tk.Canvas(wrap, bg=BG_DARK,
                                       highlightthickness=0, bd=0)
        hscroll = ttk.Scrollbar(wrap, orient="horizontal",
                                 command=self.gantt_canvas.xview)
        vscroll = ttk.Scrollbar(wrap, orient="vertical",
                                 command=self.gantt_canvas.yview)
        self.gantt_canvas.configure(xscrollcommand=hscroll.set,
                                     yscrollcommand=vscroll.set)
        hscroll.pack(side="bottom", fill="x")
        vscroll.pack(side="right",  fill="y")
        self.gantt_canvas.pack(side="left", fill="both", expand=True)

    # ══ Helpers UI ════════════════════════════════
    def _sec(self, parent, txt):
        tk.Label(parent, text=txt, font=("Courier New",7,"bold"),
                 bg=BG_PANEL, fg=TEXT_MUT).pack(anchor="w", padx=10, pady=(10,1))

    def _sec_inline(self, parent, txt):
        tk.Label(parent, text=txt, font=("Courier New",7,"bold"),
                 bg=BG_PANEL, fg=TEXT_MUT).pack(anchor="w", padx=8, pady=(8,2))

    def _btn(self, parent, txt, cmd, color):
        return tk.Button(parent, text=txt, font=("Courier New",8,"bold"),
                         bg=color, fg="#0A0E17",
                         activebackground=color, bd=0, padx=9, pady=4,
                         cursor="hand2", relief="flat", command=cmd)

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Seleccionar archivo",
            filetypes=[("Texto/CSV","*.txt *.csv"), ("Todos","*.*")])
        if path:
            self.archivo_path.set(path)
            self.file_lbl.configure(text=path.split("/")[-1], fg=TEXT_PRI)

    # ══ Lógica principal ══════════════════════════
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
            procesos, particiones = leer_archivo(
                self.archivo_path.get(), self.tipo_mem_var.get())
        except Exception as e:
            messagebox.showerror("Error leyendo archivo", str(e))
            return

        if not procesos:
            messagebox.showwarning("Vacío", "No se encontraron procesos en el archivo.")
            return

        self._procesos = procesos
        # Asignar colores
        for i, p in enumerate(procesos):
            self._color_map[p.nombre] = PROC_COLORS[i % len(PROC_COLORS)]

        # Construir bloques de memoria
        if self.tipo_mem_var.get() == "Fija" and particiones:
            self._bloques = []
            addr = 0
            for t in particiones:
                self._bloques.append(BloqueMemoria(addr, t))
                addr += t
        else:
            # Un solo bloque dinámico igual al tamaño total
            self._bloques = [BloqueMemoria(0, tam_total)]

        # Asignar procesos a bloques
        algo_fn = ALGOS[self.algoritmo_var.get()]
        tiempo_cursor = 0.0

        for p in self._procesos:
            bloque = algo_fn(self._bloques, p)
            if bloque:
                p.inicio  = tiempo_cursor
                p.fin     = round(tiempo_cursor + p.tiempo, 4)
                p.bloque  = bloque.inicio
                p.asignado = True
                bloque.libre   = False
                bloque.proceso = p
                tiempo_cursor  = p.fin

                # Liberar bloque después del tiempo de uso
                # (simulación secuencial simplificada)
                bloque.libre   = True
                bloque.proceso = None
            else:
                p.inicio = None
                p.fin    = None
                p.asignado = False

        # Poblar tabla
        for i, p in enumerate(self._procesos):
            tr = round(p.fin - p.inicio, 4) if p.asignado else "—"
            te = round(tr - p.tiempo, 4)    if p.asignado else "—"
            tag = "even" if i % 2 == 0 else "odd"
            self.tree.insert("", "end", tags=(tag,), values=(
                p.nombre,
                p.memoria,
                p.tiempo,
                p.bloque if p.asignado else "N/A",
                p.inicio if p.asignado else "—",
                p.fin    if p.asignado else "—",
                tr, te,
            ))
        self.tree.tag_configure("even", background=BG_CARD)
        self.tree.tag_configure("odd",  background=BG_INPUT)

        # Construir timeline segundo a segundo
        self._build_timeline()

        # Dibujar mapa de memoria estático
        self._draw_memory(tam_total, particiones)

        # Leyenda
        self._build_legend()

        # Iniciar animación
        self._sim_running = True
        self._sim_tick    = 0
        self._gantt_seg   = []
        self._init_gantt_canvas()
        self._animate_gantt()

    def _detener(self):
        self._sim_running = False

    def _limpiar(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        self.mem_canvas.delete("all")
        self.gantt_canvas.delete("all")
        for w in self.leyenda_frame.winfo_children():
            w.destroy()
        self._timeline = []
        self._gantt_seg = []

    # ══ Timeline ══════════════════════════════════
    def _build_timeline(self):
        """Construye lista tick→proceso para la animación."""
        self._timeline = []
        for p in self._procesos:
            if not p.asignado:
                continue
            t_start = p.inicio
            t_end   = p.fin
            # Convertir a ticks enteros (1 tick = 0.1 unidades)
            tick_start = int(round(t_start * 10))
            tick_end   = int(round(t_end   * 10))
            for t in range(tick_start, tick_end):
                self._timeline.append((t, p.nombre, self._color_map[p.nombre]))

        self._timeline.sort(key=lambda x: x[0])
        self._total_ticks = self._timeline[-1][0] + 1 if self._timeline else 0

    # ══ Mapa de Memoria ═══════════════════════════
    def _draw_memory(self, tam_total, particiones):
        cv = self.mem_canvas
        cv.delete("all")

        W        = 200
        PAD_X    = 20
        PAD_TOP  = 10
        SO_H     = 36
        BAR_W    = W - 2 * PAD_X
        TOTAL_H  = 460
        RECT_X1  = PAD_X
        RECT_X2  = PAD_X + BAR_W

        # Borde exterior del rectangulo de memoria
        cv.create_rectangle(RECT_X1 - 2, PAD_TOP - 2,
                             RECT_X2 + 2, PAD_TOP + SO_H + TOTAL_H + 2,
                             outline=ACCENT_BLUE, width=2, fill="")

        # Segmento SO
        cv.create_rectangle(RECT_X1, PAD_TOP, RECT_X2, PAD_TOP + SO_H,
                             fill=SO_COLOR, outline=BORDER, width=1)
        cv.create_text((RECT_X1 + RECT_X2) // 2, PAD_TOP + SO_H // 2,
                        text="S.O.", font=("Courier New", 8, "bold"),
                        fill=ACCENT_BLUE)

        mem_top = PAD_TOP + SO_H

        if self.tipo_mem_var.get() == "Fija" and particiones:
            total_part = sum(particiones)
            py = mem_top
            for i, ts in enumerate(particiones):
                h = max(20, int((ts / total_part) * TOTAL_H))
                proc_asig = None
                for p in self._procesos:
                    if p.asignado and p.bloque == sum(particiones[:i]):
                        proc_asig = p
                        break

                color = self._color_map.get(proc_asig.nombre, FREE_COLOR) if proc_asig else FREE_COLOR
                txt_c = TEXT_PRI if proc_asig else FREE_TEXT
                label = proc_asig.nombre if proc_asig else "LIBRE"

                cv.create_rectangle(RECT_X1, py, RECT_X2, py + h,
                                     fill=color, outline=BORDER, width=1)
                cv.create_text((RECT_X1 + RECT_X2) // 2, py + h // 2,
                                text=f"{label}\n{ts}KB",
                                font=("Courier New", 7, "bold"),
                                fill=txt_c, justify="center")

                # Fragmentación interna si hay proceso
                if proc_asig:
                    frag = ts - proc_asig.memoria
                    if frag > 0:
                        fh = max(8, int((frag / total_part) * TOTAL_H))
                        fy = py + h - fh
                        cv.create_rectangle(RECT_X1, fy, RECT_X2, py + h,
                                             fill="#2D1B1B", outline=ACCENT_RED,
                                             width=1, dash=(3, 2))
                        cv.create_text((RECT_X1 + RECT_X2) // 2, fy + fh // 2,
                                        text=f"Frag\n{frag}KB",
                                        font=("Courier New", 6),
                                        fill=ACCENT_RED, justify="center")
                py += h
        else:
            # Dinámica: dividir proporcionalmente
            procesados = [p for p in self._procesos if p.asignado]
            total_uso  = sum(p.memoria for p in procesados)
            libre_kb   = tam_total - total_uso
            total_ref  = max(tam_total, 1)

            py = mem_top
            for p in procesados:
                h = max(22, int((p.memoria / total_ref) * TOTAL_H))
                color = self._color_map.get(p.nombre, ACCENT_BLUE)
                cv.create_rectangle(RECT_X1, py, RECT_X2, py + h,
                                     fill=color, outline=BORDER, width=1)
                cv.create_text((RECT_X1 + RECT_X2) // 2, py + h // 2,
                                text=f"{p.nombre}\n{p.memoria}KB",
                                font=("Courier New", 7, "bold"),
                                fill="#0A0E17", justify="center")
                py += h

            # Espacio libre
            if libre_kb > 0 and py < mem_top + TOTAL_H:
                h_libre = mem_top + TOTAL_H - py
                cv.create_rectangle(RECT_X1, py, RECT_X2, py + h_libre,
                                     fill=FREE_COLOR, outline=BORDER, width=1)
                cv.create_text((RECT_X1 + RECT_X2) // 2, py + h_libre // 2,
                                text=f"LIBRE\n{libre_kb}KB",
                                font=("Courier New", 7, "bold"),
                                fill=FREE_TEXT, justify="center")

        total_h_canvas = PAD_TOP + SO_H + TOTAL_H + 20
        cv.configure(scrollregion=(0, 0, W, total_h_canvas))

    # ══ Gantt ══════════════════════════════════════
    def _init_gantt_canvas(self):
        self.gantt_canvas.delete("all")
        self._gantt_seg = []
        # Guardamos parámetros de layout
        self._gPX   = 28     # px por tick (0.1 unidades)
        self._gH    = 54     # altura de la barra
        self._gPADY = 20     # padding top
        self._gLW   = 60     # ancho etiqueta izq

    def _animate_gantt(self):
        if not self._sim_running:
            return
        if self._sim_tick >= len(self._timeline):
            self._sim_running = False
            self._draw_gantt_ticks()
            return

        tick, nombre, color = self._timeline[self._sim_tick]
        self._draw_gantt_tick(tick, nombre, color)
        self._sim_tick += 1
        self.after(80, self._animate_gantt)

    def _draw_gantt_tick(self, tick, nombre, color):
        cv   = self.gantt_canvas
        PX   = self._gPX
        H    = self._gH
        PADY = self._gPADY
        LW   = self._gLW

        x1 = LW + tick * PX
        x2 = x1 + PX
        y1 = PADY
        y2 = PADY + H

        # Fondo del bloque
        cv.create_rectangle(x1, y1, x2, y2, fill=color, outline="", tags="block")

        # Línea de brillo superior
        lighter = self._lighten(color, 50)
        cv.create_rectangle(x1, y1, x2, y1 + 4, fill=lighter, outline="", tags="block")

        # Etiqueta cada nuevo proceso
        if not self._gantt_seg or self._gantt_seg[-1][0] != nombre:
            self._gantt_seg.append((nombre, tick, color))
            # Label del proceso centrado cuando cambia
            mid_x = x1 + PX // 2
            cv.create_text(mid_x, y1 + H // 2,
                            text=nombre,
                            font=("Courier New", 7, "bold"),
                            fill="#0A0E17", tags="labels")

        # Marca de tiempo cada 10 ticks
        if tick % 10 == 0:
            t_val = round(tick * 0.1, 1)
            cv.create_line(x1, y2, x1, y2 + 6, fill=TEXT_SEC, tags="ticks")
            cv.create_text(x1, y2 + 14, text=str(t_val),
                            font=("Courier New", 7), fill=TEXT_SEC, tags="ticks")

        # Actualizar scrollregion
        total_w = LW + (self._total_ticks + 2) * PX + 20
        cv.configure(scrollregion=(0, 0, total_w, PADY + H + 30))

        # Auto-scroll para seguir la animación
        cv.xview_moveto(max(0, (x2 - cv.winfo_width()) / total_w))

        # Etiqueta Y "Ejecución"
        cv.delete("ylabel")
        cv.create_text(LW - 5, PADY + H // 2,
                        text="Ejecución",
                        font=("Courier New", 7), fill=TEXT_SEC,
                        anchor="e", tags="ylabel", angle=0)

    def _draw_gantt_ticks(self):
        """Dibuja los ticks finales al terminar la animación."""
        cv   = self.gantt_canvas
        PX   = self._gPX
        H    = self._gH
        PADY = self._gPADY
        LW   = self._gLW
        cv.delete("ticks")
        for tick in range(self._total_ticks + 1):
            x = LW + tick * PX
            t_val = round(tick * 0.1, 1)
            cv.create_line(x, PADY + H, x, PADY + H + 5, fill=TEXT_SEC)
            if tick % 5 == 0:
                cv.create_text(x, PADY + H + 14, text=str(t_val),
                                font=("Courier New", 7), fill=TEXT_SEC)

    # ══ Leyenda ═══════════════════════════════════
    def _build_legend(self):
        for w in self.leyenda_frame.winfo_children():
            w.destroy()
        for nombre, color in self._color_map.items():
            f = tk.Frame(self.leyenda_frame, bg=BG_PANEL)
            f.pack(side="left", padx=4)
            tk.Frame(f, bg=color, width=10, height=10).pack(side="left")
            tk.Label(f, text=nombre, font=("Courier New",7),
                     bg=BG_PANEL, fg=TEXT_SEC).pack(side="left", padx=(2,0))

    # ══ Helpers ═══════════════════════════════════
    def _lighten(self, hx, amt=50):
        r = min(255, int(hx[1:3], 16) + amt)
        g = min(255, int(hx[3:5], 16) + amt)
        b = min(255, int(hx[5:7], 16) + amt)
        return f"#{r:02X}{g:02X}{b:02X}"


if __name__ == "__main__":
    app = App()
    app.mainloop()