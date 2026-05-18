"""
Magic Cookies - Programador de Produccion
==========================================
Pontificia Universidad Javeriana - Planeacion de Operaciones 2026-10
Caso 2: Programacion de la Produccion

Heuristicas disponibles:
  1. EDD + Setup + SPT + Revenue  (greedy compuesto - original)
  2. Algoritmo de Johnson para 3 maquinas
  3. Algoritmo de Hodgson-Moore   (minimizar trabajos tardios)
  4. Minimo Costo Total           (minimiza ventas perdidas + descuentos)
"""

from dataclasses import dataclass, field
from typing import Optional
import itertools

# ─── Constantes ─────────────────────────────────────────────────────────────
JORNADA_INICIO = 5
JORNADA_FIN    = 23

GALLETAS_POR_CAJA = {"Diamond": 20, "Gold": 30, "Silver": 60, "Bronze": 40}
PRECIO_CAJA       = {"Diamond": 16_000, "Gold": 14_000, "Silver": 10_000, "Bronze": 8_000}
TASA_MEZCLA       = {"Diamond": 1000,   "Gold": 1200,   "Silver": 1500,   "Bronze": 2400}
SETUP = {
    "Diamond": {"Diamond": 0, "Gold": 1, "Silver": 2, "Bronze": 2},
    "Gold":    {"Diamond": 1, "Gold": 0, "Silver": 2, "Bronze": 0},
    "Silver":  {"Diamond": 2, "Gold": 2, "Silver": 0, "Bronze": 0},
    "Bronze":  {"Diamond": 2, "Gold": 0, "Silver": 0, "Bronze": 0},
}
T_MOLDEADO    = 3
T_EMPAQUE     = {"Diamond": 3, "Gold": 2, "Silver": 4, "Bronze": 3}
DESCUENTO_INV = 0.20

HEURISTICAS = {
    "1": "EDD + Setup + SPT + Revenue  (greedy compuesto)",
    "2": "Algoritmo de Johnson  (3 maquinas)",
    "3": "Algoritmo de Hodgson-Moore   (min. trabajos tardios)",
    "4": "Minimo Costo Total   (min. ventas perdidas + descuentos)",
}

# Ordenes predefinidas por dia (imagen entregada + enunciado)
ORDENES_DIA = {
    15: [
        (1,  "Diamond", 150, 16),
        (2,  "Gold",     80, 17),
        (3,  "Silver",   75, 16),
        (4,  "Bronze",  120, 17),
        (5,  "Gold",    160, 18),
        (6,  "Silver",   50, 17),
    ],
    16: [
        (7,  "Diamond",  50, 17),
        (8,  "Gold",     80, 17),
        (9,  "Silver",  100, 18),
        (10, "Bronze",  180, 17),
        (11, "Silver",  150, 18),
        (12, "Bronze",  240, 18),
        (13, "Gold",     80, 17),
        (14, "Bronze",  300, 19),
    ],
    17: [
        (15, "Silver",  150, 19),
        (16, "Gold",     40, 19),
        (17, "Gold",    120, 18),
        (18, "Bronze",  240, 19),
        (19, "Gold",     80, 18),
    ],
    18: [
        (20, "Diamond",  50, 20),
        (21, "Silver",  150, 21),
        (22, "Diamond", 100, 19),
        (23, "Bronze",  120, 19),
        (24, "Silver",  100, 20),
        (25, "Bronze",  240, 19),
    ],
    19: [
        (26, "Diamond", 100, 20),
        (27, "Bronze",  120, 21),
        (28, "Silver",  125, 22),
        (29, "Silver",  100, 20),
        (30, "Bronze",  300, 21),
    ],
}


# ─── Utilidades de tiempo ────────────────────────────────────────────────────
def hora_abs(dia: int, hora: float) -> float:
    return (dia - 15) * 24 + hora

def hora_relativa(h: float):
    return 15 + int(h // 24), h % 24

def fmt(h: float) -> str:
    dia, hh = hora_relativa(h)
    return f"Dia {dia} {hh:05.2f}h"

def ajustar_jornada(t: float, dur: float) -> float:
    dia, h = hora_relativa(t)
    if h < JORNADA_INICIO:
        t = hora_abs(dia, JORNADA_INICIO); dia, h = hora_relativa(t)
    if h >= JORNADA_FIN or h + dur > JORNADA_FIN:
        t = hora_abs(dia + 1, JORNADA_INICIO)
    return t

def makespan_efectivo(t_ini: float, t_fin: float) -> float:
    """Makespan descontando cierres nocturnos (23:00-05:00 = 6h/noche)."""
    if t_fin <= t_ini:
        return 0.0
    dia_ini, _ = hora_relativa(t_ini)
    dia_fin, _ = hora_relativa(t_fin)
    noches = dia_fin - dia_ini
    return (t_fin - t_ini) - noches * (24 - (JORNADA_FIN - JORNADA_INICIO))


# ─── Modelo de Orden ─────────────────────────────────────────────────────────
@dataclass
class Orden:
    id: int
    referencia: str
    cajas: int
    fecha_entrega: int
    dia_ingreso: int
    hora_limite: float = 6.0
    t_mezcla:   float = field(init=False)
    t_moldeado: float = field(init=False)
    t_empaque:  float = field(init=False)
    inicio_mezcla: Optional[float] = field(default=None, repr=False)
    fin_mezcla:    Optional[float] = field(default=None, repr=False)
    inicio_moldeo: Optional[float] = field(default=None, repr=False)
    fin_moldeo:    Optional[float] = field(default=None, repr=False)
    inicio_empaq:  Optional[float] = field(default=None, repr=False)
    fin_empaq:     Optional[float] = field(default=None, repr=False)
    congelada: bool = False

    def __post_init__(self):
        g = self.cajas * GALLETAS_POR_CAJA[self.referencia]
        self.t_mezcla   = g / TASA_MEZCLA[self.referencia]
        self.t_moldeado = T_MOLDEADO
        self.t_empaque  = T_EMPAQUE[self.referencia]

    def reset(self):
        if not self.congelada:
            self.inicio_mezcla = self.fin_mezcla = None
            self.inicio_moldeo = self.fin_moldeo = None
            self.inicio_empaq  = self.fin_empaq  = None

    @property
    def deadline_abs(self):
        return (self.fecha_entrega - 15) * 24 + self.hora_limite

    @property
    def ingreso_bruto(self):
        return self.cajas * PRECIO_CAJA[self.referencia]

    @property
    def completada(self):
        return self.fin_empaq is not None

    @property
    def tardia(self):
        return self.completada and self.fin_empaq > self.deadline_abs

    @property
    def tardanza_horas(self):
        return max(0.0, self.fin_empaq - self.deadline_abs) if self.completada else 0.0

    @property
    def tiempo_en_inventario(self):
        if not self.completada or self.tardia:
            return 0.0
        return self.deadline_abs - self.fin_empaq

    @property
    def costo_ventas_perdidas(self):
        return self.ingreso_bruto if self.tardia else 0.0

    @property
    def descuento_inventario(self):
        if self.tardia or not self.completada:
            return 0.0
        return self.ingreso_bruto * DESCUENTO_INV if self.tiempo_en_inventario > 24 else 0.0

    @property
    def ingreso_neto(self):
        return 0.0 if self.tardia else self.ingreso_bruto - self.descuento_inventario


# ─── Heuristicas de secuenciacion ───────────────────────────────────────────

def heuristica_greedy(pool: list, ref_act: Optional[str], **kw) -> list:
    """
    H1: Greedy compuesto  EDD → menor setup → SPT → mayor ingreso.
    Adaptada para considerar setup desde la referencia actual.
    """
    def score(o, ref):
        s = SETUP[ref][o.referencia] if ref else 0
        return (o.deadline_abs, s, o.t_mezcla, -o.ingreso_bruto)

    p = list(pool); r = []; ref = ref_act
    while p:
        p.sort(key=lambda o: score(o, ref))
        e = p.pop(0); r.append(e); ref = e.referencia
    return r


def heuristica_johnson_3m(pool: list, ref_act: Optional[str], **kw) -> list:
    """
    H2: Algoritmo de Johnson extendido a 3 maquinas.
    Maquina 1 = Mezcla, Maquina 2 = Moldeado (fija = 3h), Maquina 3 = Empaque.

    Condicion de aplicabilidad de Johnson 3M:
      min(M1) >= max(M2)  O  min(M3) >= max(M2)
    Si no se cumple, se aplica de todas formas como aproximacion.

    Paso: combinar maquinas ficticias G = M1+M2, H = M2+M3 y aplicar
    Johnson de 2 maquinas sobre (G, H).
    """
    if not pool:
        return []

    # Tiempos ficticios para Johnson 3M
    jobs = [(o, o.t_mezcla + o.t_moldeado, o.t_moldeado + o.t_empaque) for o in pool]

    # Johnson 2M sobre (G, H)
    left  = []   # trabajos que van al frente
    right = []   # trabajos que van al final

    for o, g, h in jobs:
        if g <= h:
            left.append((g, o))
        else:
            right.append((h, o))

    left.sort(key=lambda x: x[0])
    right.sort(key=lambda x: x[0], reverse=True)

    seq = [o for _, o in left] + [o for _, o in right]
    return seq


def heuristica_hodgson(pool: list, ref_act: Optional[str],
                       t_mez_0: float = 0, t_mol_0: float = 0, t_emp_0: float = 0,
                       desde_dia: int = 15, hasta_dia: int = 19, **kw) -> list:
    """
    H3: Algoritmo de Hodgson-Moore — minimiza el numero de trabajos tardios.

    Procedimiento:
      1. Ordenar por EDD.
      2. Simular en orden; cuando se detecta una orden tardia, eliminar del
         conjunto la orden con mayor tiempo de mezcla (la que mas "consume"
         capacidad) y moverla al final (conjunto L).
      3. Repetir hasta que no haya tardios.
      4. Secuencia final = conjunto E (a tiempo) + conjunto L.

    Para estimar si una orden es tardia se usa una simulacion simplificada
    del tiempo de finalizacion (ignorando setup para la clasificacion).
    """
    if not pool:
        return []

    # Ordenar por EDD inicial
    E = sorted(pool, key=lambda o: o.deadline_abs)
    L = []

    def estimar_fin_empaq(secuencia, t_mez_ini, t_mol_ini, t_emp_ini, dia_ini, dia_fin):
        """Simulacion rapida sin setup para clasificacion Hodgson."""
        t_m = t_mez_ini; t_mo = t_mol_ini; t_e = t_emp_ini
        fins = {}
        for o in secuencia:
            t_m  = ajustar_jornada(t_m,  o.t_mezcla);   t_m  += o.t_mezcla
            t_mo = ajustar_jornada(max(t_mo, t_m), o.t_moldeado); t_mo += o.t_moldeado
            t_e  = ajustar_jornada(max(t_e,  t_mo), o.t_empaque);  t_e  += o.t_empaque
            fins[o.id] = t_e
        return fins

    changed = True
    while changed:
        changed = False
        fins = estimar_fin_empaq(E, t_mez_0, t_mol_0, t_emp_0, desde_dia, hasta_dia)
        for i, o in enumerate(E):
            if fins[o.id] > o.deadline_abs:
                # Encontrar la orden con mayor t_mezcla en E[0..i]
                culpable = max(E[:i+1], key=lambda x: x.t_mezcla)
                E.remove(culpable)
                L.append(culpable)
                changed = True
                break   # reiniciar desde el principio

    return E + L


def heuristica_min_costo(pool: list, ref_act: Optional[str],
                         t_mez_0: float = 0, t_mol_0: float = 0, t_emp_0: float = 0,
                         desde_dia: int = 15, hasta_dia: int = 19, **kw) -> list:
    """
    H4: Minimo Costo Total — minimiza (ventas perdidas + descuentos por inventario).

    Estrategia:
      a) Separar ordenes en "en riesgo de tardanza" y "holgadas".
      b) Las en riesgo se ordenan por: mayor ingreso primero (para salvar
         las mas valiosas) desempatando por EDD.
      c) Las holgadas se ordenan por EDD desempatando por menor tiempo
         en inventario estimado (para evitar descuentos del 20%).
      d) Considerar setup minimo al encadenar referencias.

    Esta heuristica es especifica para el objetivo de maximizar ingresos netos.
    """
    if not pool:
        return []

    # Estimacion rapida de fin de empaque para cada orden si fuera primera
    def estimar_fin_solo(o, t_mez, t_mol, t_emp):
        tm  = ajustar_jornada(t_mez, o.t_mezcla)  + o.t_mezcla
        tmo = ajustar_jornada(max(t_mol, tm), o.t_moldeado) + o.t_moldeado
        te  = ajustar_jornada(max(t_emp, tmo), o.t_empaque) + o.t_empaque
        return te

    # Clasificar ordenes
    en_riesgo = []
    holgadas  = []
    for o in pool:
        fin_est = estimar_fin_solo(o, t_mez_0, t_mol_0, t_emp_0)
        margen  = o.deadline_abs - fin_est   # positivo = holgada
        if margen < (o.t_mezcla + o.t_moldeado + o.t_empaque):
            en_riesgo.append((margen, o))
        else:
            holgadas.append((margen, o))

    # En riesgo: primero mayor ingreso, desempate EDD
    en_riesgo.sort(key=lambda x: (-x[1].ingreso_bruto, x[1].deadline_abs))
    # Holgadas: EDD, desempate menor margen (las mas justas al limite primero
    # para evitar que pasen 24h en inventario)
    holgadas.sort(key=lambda x: (x[1].deadline_abs, x[0]))

    candidatos = [o for _, o in en_riesgo] + [o for _, o in holgadas]

    # Ajuste de setup: reordenar localmente para minimizar tiempos de alistamiento
    # usando un greedy de vecino mas cercano sobre la secuencia candidata,
    # pero respetando el orden de prioridad de grupos (en_riesgo primero).
    n_riesgo = len(en_riesgo)
    grupo_riesgo = candidatos[:n_riesgo]
    grupo_holgado = candidatos[n_riesgo:]

    def reordenar_por_setup(grupo, ref_inicio):
        if not grupo:
            return []
        pool2 = list(grupo); r2 = []; ref = ref_inicio
        while pool2:
            # Menor setup desde ref actual, desempate por orden original
            pool2.sort(key=lambda o: (SETUP[ref][o.referencia] if ref else 0,
                                      grupo.index(o)))
            e = pool2.pop(0); r2.append(e); ref = e.referencia
        return r2

    seq_riesgo  = reordenar_por_setup(grupo_riesgo,  ref_act)
    ref_tras_riesgo = seq_riesgo[-1].referencia if seq_riesgo else ref_act
    seq_holgado = reordenar_por_setup(grupo_holgado, ref_tras_riesgo)

    return seq_riesgo + seq_holgado


# Mapa de heuristicas
MAPA_HEURISTICAS = {
    "1": heuristica_greedy,
    "2": heuristica_johnson_3m,
    "3": heuristica_hodgson,
    "4": heuristica_min_costo,
}


# ─── Scheduler ───────────────────────────────────────────────────────────────
class MagicCookiesScheduler:
    def __init__(self, heuristica: str = "1"):
        self.ordenes: list       = []
        self.secuencia: list     = []
        self.dia_actual: int     = 15
        self._t_mez: float       = hora_abs(15, JORNADA_INICIO)
        self._t_mol: float       = hora_abs(15, JORNADA_INICIO)
        self._t_emp: float       = hora_abs(15, JORNADA_INICIO)
        self._ultima_ref: Optional[str] = None
        self._seq_congelada: list = []
        self.heuristica: str      = heuristica   # "1" | "2" | "3" | "4"

    def _secuenciar(self, pool, ref_act, t_mez=None, t_mol=None, t_emp=None,
                    desde_dia=15, hasta_dia=19):
        fn = MAPA_HEURISTICAS[self.heuristica]
        return fn(pool, ref_act,
                  t_mez_0=t_mez or self._t_mez,
                  t_mol_0=t_mol or self._t_mol,
                  t_emp_0=t_emp or self._t_emp,
                  desde_dia=desde_dia, hasta_dia=hasta_dia)

    def agregar_orden(self, id_, ref, cajas, fecha_entrega, dia_ingreso=None):
        ref_n = next((r for r in GALLETAS_POR_CAJA if r.lower() == ref.lower()), None)
        if not ref_n:
            raise ValueError(f"Referencia '{ref}' invalida.")
        if any(o.id == id_ for o in self.ordenes):
            raise ValueError(f"ID {id_} ya existe.")
        d = dia_ingreso if dia_ingreso is not None else self.dia_actual
        o = Orden(id=id_, referencia=ref_n, cajas=cajas, fecha_entrega=fecha_entrega, dia_ingreso=d)
        self.ordenes.append(o)
        print(f"    + Orden {id_:>3} | {ref_n:<8} | {cajas:>5} cajas | "
              f"Entrega dia {fecha_entrega} | Ingresada dia {d}")

    def cargar_dia(self, dia: int):
        """Carga automaticamente las ordenes predefinidas de un dia."""
        if dia not in ORDENES_DIA:
            print(f"  ! No hay ordenes predefinidas para el dia {dia}.")
            return
        print(f"\n  Cargando ordenes predefinidas del dia {dia}...")
        for id_, ref, cajas, fecha in ORDENES_DIA[dia]:
            try:
                self.agregar_orden(id_, ref, cajas, fecha, dia_ingreso=dia)
            except ValueError as e:
                print(f"    ! {e}")

    # ── Simulacion ───────────────────────────────────────────────────────────
    def simular(self, desde_dia=15, hasta_dia=19,
                t_mez_0=None, t_mol_0=None, t_emp_0=None,
                uref_0=None, pool=None):
        t_mez = t_mez_0 if t_mez_0 is not None else self._t_mez
        t_mol = t_mol_0 if t_mol_0 is not None else self._t_mol
        t_emp = t_emp_0 if t_emp_0 is not None else self._t_emp
        u_ref = uref_0  if uref_0  is not None else self._ultima_ref

        activas = pool if pool is not None else [o for o in self.ordenes if not o.congelada]
        for o in activas:
            o.reset()

        pendientes = list(activas)
        procesadas = []

        # MEZCLA
        for dia in range(desde_dia, hasta_dia + 1):
            jf  = hora_abs(dia, JORNADA_FIN)
            seq = self._secuenciar(pendientes, u_ref,
                                   t_mez=t_mez, t_mol=t_mol, t_emp=t_emp,
                                   desde_dia=dia, hasta_dia=hasta_dia)
            for orden in seq:
                setup = SETUP[u_ref][orden.referencia] if u_ref else 0
                t_ini = max(t_mez, hora_abs(dia, JORNADA_INICIO))
                t_sf  = t_ini + setup
                if t_sf > jf:
                    break
                t_mi = t_sf; t_mf = t_mi + orden.t_mezcla
                if t_mf > jf:
                    if setup > 0 and t_sf <= jf:
                        t_mez = t_sf; u_ref = orden.referencia
                    break
                orden.inicio_mezcla = t_mi; orden.fin_mezcla = t_mf
                t_mez = t_mf; u_ref = orden.referencia
                pendientes.remove(orden); procesadas.append(orden)
            if not pendientes:
                break
            t_mez = hora_abs(dia + 1, JORNADA_INICIO)

        # MOLDEADO
        for o in procesadas:
            t = ajustar_jornada(max(t_mol, o.fin_mezcla), o.t_moldeado)
            o.inicio_moldeo = t; o.fin_moldeo = t + o.t_moldeado; t_mol = o.fin_moldeo

        # EMPAQUE
        for o in procesadas:
            t = ajustar_jornada(max(t_emp, o.fin_moldeo), o.t_empaque)
            o.inicio_empaq = t; o.fin_empaq = t + o.t_empaque; t_emp = o.fin_empaq

        self.secuencia = self._seq_congelada + [o.id for o in procesadas]

    # ── Cerrar dia ───────────────────────────────────────────────────────────
    def cerrar_dia(self, dia: int):
        rc = []
        for o in self.ordenes:
            if o.congelada or o.inicio_mezcla is None:
                continue
            d_ini, _ = hora_relativa(o.inicio_mezcla)
            if d_ini <= dia:
                o.congelada = True; rc.append(o)
        if not rc:
            print(f"  ! No hay ordenes para congelar en el dia {dia}.")
            return
        mez = [o for o in rc if o.fin_mezcla is not None]
        if mez:
            um = max(mez, key=lambda o: o.fin_mezcla)
            self._t_mez = um.fin_mezcla; self._ultima_ref = um.referencia
        mol = [o for o in rc if o.fin_moldeo is not None]
        if mol:
            self._t_mol = max(o.fin_moldeo for o in mol)
        emp = [o for o in rc if o.fin_empaq is not None]
        if emp:
            self._t_emp = max(o.fin_empaq for o in emp)
        self._seq_congelada = [o.id for o in self.ordenes if o.congelada]
        self.dia_actual = dia + 1
        print(f"\n  [CIERRE DIA {dia}] Ordenes congeladas: {[o.id for o in rc]}")
        print(f"    Estado maquinas para el dia {dia+1}:")
        print(f"      Mezcla   libre: {fmt(self._t_mez)}  (ultima ref: {self._ultima_ref})")
        print(f"      Moldeado libre: {fmt(self._t_mol)}")
        print(f"      Empaque  libre: {fmt(self._t_emp)}")

    # ── Opcion 9: ingresar demanda de un dia nuevo y re-simular ─────────────
    def ingresar_demanda_dia(self):
        print("\n" + "=" * 65)
        print("  OPCION 9 - Ingresar demanda de un nuevo dia y re-simular")
        print(f"  Heuristica activa: [{self.heuristica}] {HEURISTICAS[self.heuristica]}")
        print("=" * 65)
        print("  1. Cierra el dia anterior (procesos ya realizados quedan FIJOS)")
        print("  2. Ingresa nuevas ordenes (manual o carga automatica del dia)")
        print("  3. Re-simula desde ese dia manteniendo dias previos intactos")
        print("=" * 65)

        try:
            dia_nuevo = int(input("\n  Dia de las nuevas ordenes (16-19): ").strip())
        except ValueError:
            print("  ! Entrada invalida."); return
        if not (16 <= dia_nuevo <= 19):
            print("  ! Solo se permiten dias entre 16 y 19."); return

        # Paso 1 - cerrar dia anterior
        print(f"\n  --- PASO 1: Cerrando dia {dia_nuevo - 1} ---")
        self.cerrar_dia(dia_nuevo - 1)

        # Paso 2 - ingresar ordenes
        print(f"\n  --- PASO 2: Ingreso de ordenes del dia {dia_nuevo} ---")
        print("  a) Carga automatica (ordenes predefinidas del dia)")
        print("  b) Ingreso manual   (orden por orden)")
        modo = input("  Modo [a/b]: ").strip().lower()

        if modo == "a":
            self.cargar_dia(dia_nuevo)
        else:
            print("  Referencias: Diamond, Gold, Silver, Bronze")
            print("  (Escriba 'fin' en Referencia para terminar)")
            sig_id = max((o.id for o in self.ordenes), default=0) + 1
            while True:
                print(f"\n  Nueva orden  (ID sugerido: {sig_id})")
                raw_id  = input("    ID (Enter=auto)  : ").strip()
                id_ord  = int(raw_id) if raw_id.isdigit() else sig_id
                raw_ref = input("    Referencia       : ").strip()
                if raw_ref.lower() == "fin":
                    break
                try:
                    cajas = int(input("    Num. de cajas    : ").strip())
                    fecha = int(input("    Fecha de entrega : ").strip())
                    self.agregar_orden(id_ord, raw_ref, cajas, fecha, dia_ingreso=dia_nuevo)
                    sig_id = max(o.id for o in self.ordenes) + 1
                except (ValueError, StopIteration) as e:
                    print(f"    ! Error: {e}")

        pendientes = [o for o in self.ordenes if not o.congelada]
        if not pendientes:
            print("  ! No hay ordenes pendientes para simular."); return

        # Paso 3 - re-simular
        print(f"\n  --- PASO 3: Re-simulacion desde dia {dia_nuevo} "
              f"[{HEURISTICAS[self.heuristica]}] ---")
        print(f"  Ordenes a secuenciar: {[o.id for o in pendientes]}")

        self.simular(desde_dia=dia_nuevo, hasta_dia=19,
                     t_mez_0=self._t_mez, t_mol_0=self._t_mol, t_emp_0=self._t_emp,
                     uref_0=self._ultima_ref, pool=pendientes)

        print(f"\n  Secuencia completa: {self.secuencia}")
        self.reporte_programacion()
        self.reporte_kpis_dia(dia_nuevo)
        self.reporte_kpis()
        self.gantt_consola(dia_nuevo)

    # ── Reportes ─────────────────────────────────────────────────────────────
    def reporte_programacion(self):
        print("\n" + "=" * 100)
        print(f"  MAGIC COOKIES -- PROGRAMACION  "
              f"[Heuristica: {self.heuristica} - {HEURISTICAS[self.heuristica]}]")
        print("=" * 100)
        proc   = [o for o in self.ordenes if o.completada]
        no_ini = [o for o in self.ordenes if not o.completada]
        print(f"  {'ID':<5} {'Ref':<8} {'Cajas':<6} {'Ent.':<5} {'Fin Empaque':<20} "
              f"{'Tardia':<8} {'Tard(h)':<9} {'Inv(h)':<9} {'Ingreso Neto':>14}  Estado")
        print("  " + "-" * 96)
        for o in sorted(proc, key=lambda x: (x.inicio_mezcla or 0, x.id)):
            est = "[FIJO]" if o.congelada else "[activo]"
            print(f"  {o.id:<5} {o.referencia:<8} {o.cajas:<6} {o.fecha_entrega:<5} "
                  f"{fmt(o.fin_empaq):<20} {'SI' if o.tardia else 'No':<8} "
                  f"{o.tardanza_horas:<9.1f} {o.tiempo_en_inventario:<9.1f} "
                  f"${o.ingreso_neto:>13,.0f}  {est}")
        if no_ini:
            print(f"\n  Ordenes SIN programar: {', '.join(str(o.id) for o in no_ini)}")

    def reporte_kpis(self):
        p = [o for o in self.ordenes if o.completada]
        if not p:
            print("  Sin ordenes completadas."); return
        makespan = makespan_efectivo(min(o.inicio_mezcla for o in p),
                                     max(o.fin_empaq     for o in p))
        tard = sum(o.tardanza_horas for o in p)
        vp   = sum(o.costo_ventas_perdidas for o in p)
        desc = sum(o.descuento_inventario  for o in p)
        ing  = sum(o.ingreso_neto for o in p)
        print("\n  " + "-" * 54)
        print(f"  KPIs ACUMULADOS  [{self.heuristica} - {HEURISTICAS[self.heuristica]}]")
        print("  " + "-" * 54)
        print(f"  Makespan efectivo (sin noches)    : {makespan:.2f} h")
        print(f"  Tardanza total                    : {tard:.2f} h")
        print(f"  Ordenes tardias                   : {sum(1 for o in p if o.tardia)}")
        print(f"  Ventas perdidas                   : ${vp:>14,.0f}")
        print(f"  Descuentos por inventario         : ${desc:>14,.0f}")
        print(f"  INGRESO NETO TOTAL                : ${ing:>14,.0f}")
        print("  " + "-" * 54)

    def reporte_kpis_dia(self, dia: int):
        """KPIs unicamente de las ordenes finalizadas (empaque terminado) en el dia dado."""
        j_ini = hora_abs(dia, JORNADA_INICIO)
        j_fin = hora_abs(dia, JORNADA_FIN)
        del_dia = [o for o in self.ordenes
                   if o.completada and j_ini <= o.fin_empaq <= j_fin]

        print("\n" + "=" * 72)
        print(f"  KPIs DEL DIA {dia}  (ordenes con empaque terminado entre "
              f"{JORNADA_INICIO}:00 y {JORNADA_FIN}:00)")
        print("=" * 72)
        if not del_dia:
            print(f"  No hay ordenes finalizadas en empaque el dia {dia}.")
            print("=" * 72); return

        print(f"\n  {'ID':<5} {'Ref':<8} {'Cajas':<6} {'Ent.':<5} "
              f"{'Ini Mezcla':<18} {'Fin Empaque':<18} "
              f"{'Tardia':<8} {'Tard(h)':<9} {'Inv(h)':<9} {'Ingreso Neto':>14}")
        print("  " + "-" * 104)
        for o in sorted(del_dia, key=lambda x: x.fin_empaq):
            print(f"  {o.id:<5} {o.referencia:<8} {o.cajas:<6} {o.fecha_entrega:<5} "
                  f"{fmt(o.inicio_mezcla):<18} {fmt(o.fin_empaq):<18} "
                  f"{'SI' if o.tardia else 'No':<8} "
                  f"{o.tardanza_horas:<9.1f} {o.tiempo_en_inventario:<9.1f} "
                  f"${o.ingreso_neto:>13,.0f}")

        ini_t = min(o.inicio_mezcla for o in del_dia)
        fin_t = max(o.fin_empaq     for o in del_dia)
        ms_cal   = fin_t - ini_t
        ms_efect = makespan_efectivo(ini_t, fin_t)
        tard_d   = sum(o.tardanza_horas        for o in del_dia)
        vp_d     = sum(o.costo_ventas_perdidas for o in del_dia)
        desc_d   = sum(o.descuento_inventario  for o in del_dia)
        ing_d    = sum(o.ingreso_neto          for o in del_dia)

        print("\n  " + "-" * 57)
        print(f"  Ordenes finalizadas el dia {dia}        : {len(del_dia)}")
        print(f"  IDs                                   : {[o.id for o in del_dia]}")
        print(f"  Primera mezcla iniciada               : {fmt(ini_t)}")
        print(f"  Ultimo empaque terminado              : {fmt(fin_t)}")
        print(f"  Makespan calendario (con noches)      : {ms_cal:.2f} h")
        print(f"  MAKESPAN EFECTIVO   (sin noches)      : {ms_efect:.2f} h"
              f"  [{int(ms_cal - ms_efect)} h noche descontadas]")
        print(f"  Tardanza acumulada del dia            : {tard_d:.2f} h")
        print(f"  Ordenes tardias del dia               : {sum(1 for o in del_dia if o.tardia)}")
        print(f"  Ventas perdidas del dia               : ${vp_d:>14,.0f}")
        print(f"  Descuentos por inventario             : ${desc_d:>14,.0f}")
        print(f"  INGRESO NETO DEL DIA                  : ${ing_d:>14,.0f}")
        print("  " + "-" * 57)

        prev_dia = [o for o in del_dia if hora_relativa(o.inicio_mezcla)[0] < dia]
        if prev_dia:
            print(f"\n  Nota: {len(prev_dia)} orden(es) iniciaron mezcla en dias anteriores"
                  f"  (IDs: {[o.id for o in prev_dia]})")
        print("=" * 72)

    def gantt_consola(self, dia: int):
        horas = list(range(5, 24)); ac = 3
        print(f"\n  GANTT -- Dia {dia}  "
              f"[{self.heuristica} - {HEURISTICAS[self.heuristica]}]")
        print("  " + "-" * (10 + len(horas) * ac))
        print("  Hora    :" + "".join(f"{h:>{ac}}" for h in horas))
        print("  " + "-" * (10 + len(horas) * ac))
        for lab, ai, af in [("Mezcla  ", "inicio_mezcla", "fin_mezcla"),
                             ("Moldeado", "inicio_moldeo", "fin_moldeo"),
                             ("Empaque ", "inicio_empaq",  "fin_empaq")]:
            fila = ["·"] * len(horas)
            for o in self.ordenes:
                ini = getattr(o, ai); fin = getattr(o, af)
                if ini is None: continue
                for idx, h in enumerate(horas):
                    if ini <= hora_abs(dia, h) < fin:
                        fila[idx] = str(o.id)
            print(f"  {lab}:" + "".join(f"{c:>{ac}}" for c in fila))
        print()

    def detalle_mezcla(self):
        print("\n  DETALLE OPERACION DE MEZCLA")
        print(f"  {'ID':<6} {'Ref':<9} {'Inicio':>20} {'Fin':>20} "
              f"{'T.Proc':>8}  {'Setup':>6}  Estado")
        print("  " + "-" * 80)
        prev = None
        for o in sorted(self.ordenes, key=lambda x: (x.inicio_mezcla or 9999, x.id)):
            if o.inicio_mezcla is None: continue
            s = SETUP[prev][o.referencia] if prev else 0
            est = "[FIJO]" if o.congelada else "[activo]"
            print(f"  {o.id:<6} {o.referencia:<9} {fmt(o.inicio_mezcla):>20} "
                  f"{fmt(o.fin_mezcla):>20} {o.t_mezcla:>7.2f}h  {s:>5}h  {est}")
            prev = o.referencia

    def estado_sistema(self):
        print("\n  ESTADO DEL SISTEMA")
        print(f"  Heuristica activa      : [{self.heuristica}] {HEURISTICAS[self.heuristica]}")
        print(f"  Dia actual             : {self.dia_actual}")
        print(f"  Ultima ref mezcla      : {self._ultima_ref or 'N/A'}")
        print(f"  Mezcla   libre desde   : {fmt(self._t_mez)}")
        print(f"  Moldeado libre desde   : {fmt(self._t_mol)}")
        print(f"  Empaque  libre desde   : {fmt(self._t_emp)}")
        fijos   = [o.id for o in self.ordenes if o.congelada]
        activos = [o.id for o in self.ordenes if not o.congelada]
        print(f"  Ordenes congeladas     : {fijos or 'Ninguna'}")
        print(f"  Ordenes activas        : {activos or 'Ninguna'}")


# ─── Utilidades del menu ──────────────────────────────────────────────────────
def reset_s(s: MagicCookiesScheduler):
    s.ordenes.clear(); s.secuencia.clear(); s._seq_congelada.clear()
    s.dia_actual = 15
    s._t_mez = hora_abs(15, JORNADA_INICIO)
    s._t_mol = hora_abs(15, JORNADA_INICIO)
    s._t_emp = hora_abs(15, JORNADA_INICIO)
    s._ultima_ref = None

def pedir_ref():
    raw = input("  Referencia (Diamond/Gold/Silver/Bronze): ").strip()
    m = next((r for r in GALLETAS_POR_CAJA if r.lower() == raw.lower()), None)
    if not m: raise ValueError(f"Referencia '{raw}' invalida.")
    return m

def menu_heuristica() -> str:
    """Menu inicial para elegir la heuristica. Retorna la clave elegida."""
    print("\n" + "╔" + "═" * 66 + "╗")
    print("║   MAGIC COOKIES -- Programador de Produccion                    ║")
    print("║   Pontificia Universidad Javeriana | PO 2026-10                 ║")
    print("╠" + "═" * 66 + "╣")
    print("║   Seleccione la heuristica de secuenciacion a utilizar:         ║")
    print("╚" + "═" * 66 + "╝")
    print()
    for k, v in HEURISTICAS.items():
        print(f"  {k}.  {v}")
    print()

    while True:
        op = input("  Heuristica [1/2/3/4]: ").strip()
        if op in HEURISTICAS:
            print(f"\n  Heuristica seleccionada: [{op}] {HEURISTICAS[op]}")
            print("  " + "─" * 60)
            return op
        print("  ! Opcion invalida. Ingrese 1, 2, 3 o 4.")


def menu():
    heuristica = menu_heuristica()
    s = MagicCookiesScheduler(heuristica=heuristica)

    ops = {
        "1":  "Agregar orden individual",
        "2":  "Cargar ordenes predefinidas de un dia  (15/16/17/18/19)",
        "3":  "Ejecutar simulacion completa",
        "4":  "Ver reporte de programacion",
        "5":  "Ver KPIs acumulados  (makespan, tardanza, ingresos)",
        "6":  "Ver Gantt de un dia especifico",
        "7":  "Ver detalle de operacion de Mezcla",
        "8":  "Ver estado del sistema  (maquinas / congelamiento)",
        "9":  "*** Ingresar demanda de un nuevo dia y re-simular ***",
        "10": "KPIs y makespan de un dia especifico",
        "H":  "Cambiar heuristica (reinicia el sistema)",
        "C":  "Limpiar ordenes y reiniciar",
        "0":  "Salir",
    }

    while True:
        print(f"\n  MENU PRINCIPAL  "
              f"[Heuristica: {s.heuristica} - {HEURISTICAS[s.heuristica]}]")
        print("  " + "-" * 60)
        for k, v in ops.items():
            print(f"  {k:>2}.  {v}")
        print("  " + "-" * 60)
        op = input("  Opcion: ").strip().upper()

        if op == "1":
            try:
                id_   = int(input("  ID           : "))
                ref   = pedir_ref()
                cajas = int(input("  Cajas        : "))
                fecha = int(input("  Fecha entrega: "))
                s.agregar_orden(id_, ref, cajas, fecha)
            except ValueError as e:
                print(f"  ! {e}")

        elif op == "2":
            try:
                dia = int(input("  Dia a cargar (15/16/17/18/19): ").strip())
                if dia == 15:
                    reset_s(s)
                s.cargar_dia(dia)
            except ValueError:
                print("  ! Dia invalido.")

        elif op == "3":
            if not s.ordenes:
                print("  ! No hay ordenes. Use opcion 1 o 2."); continue
            try:
                ri = input("  Dia inicio [15]: ").strip()
                rf = input("  Dia fin    [19]: ").strip()
                d_ini = int(ri) if ri else 15
                d_fin = int(rf) if rf else 19
                s.simular(d_ini, d_fin)
                print(f"  Secuencia: {s.secuencia}")
            except Exception as e:
                print(f"  ! Error: {e}")

        elif op == "4":
            s.reporte_programacion()

        elif op == "5":
            s.reporte_kpis()

        elif op == "6":
            try:
                s.gantt_consola(int(input("  Dia (15-22): ")))
            except ValueError:
                print("  ! Dia invalido.")

        elif op == "7":
            s.detalle_mezcla()

        elif op == "8":
            s.estado_sistema()

        elif op == "9":
            s.ingresar_demanda_dia()

        elif op == "10":
            try:
                dia = int(input("  Dia a analizar (15-22): ").strip())
                s.reporte_kpis_dia(dia)
            except ValueError:
                print("  ! Dia invalido.")

        elif op == "H":
            print()
            nueva = menu_heuristica()
            reset_s(s)
            s.heuristica = nueva
            print("  Sistema reiniciado con nueva heuristica.")

        elif op == "C":
            reset_s(s); print("  Sistema reiniciado.")

        elif op == "0":
            print("\n  Hasta luego!\n"); break

        else:
            print("  ! Opcion no valida.")


# ─── Demo ─────────────────────────────────────────────────────────────────────
def demo():
    print("\n" + "=" * 65)
    print("  DEMO -- Comparacion de heuristicas con ordenes del dia 15")
    print("=" * 65)

    for h in HEURISTICAS:
        print(f"\n{'='*65}")
        print(f"  [{h}] {HEURISTICAS[h]}")
        print(f"{'='*65}")
        s = MagicCookiesScheduler(heuristica=h)
        s.cargar_dia(15)
        s.simular(15, 19)
        print(f"  Secuencia: {s.secuencia}")
        s.reporte_kpis()


if __name__ == "__main__":
    import sys
    if "--demo" in sys.argv:
        demo()
    else:
        menu()