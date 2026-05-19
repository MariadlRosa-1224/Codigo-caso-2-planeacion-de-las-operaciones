# Código-caso-2-planeación-de-las-operaciones

El propósito de este repositorio es alojar temporalmente el código usado para la resolución del caso 2 de la materia Planeación de Operaciones y explicar su funcionamiento. El código puede ser observado en [el único otro archivo dentro del repositorio](./codigo-caso.py).

El presente archivo explica el funcionamiento general del programa, obviando detalles demasiado técnicos y enfocándose en la lógica usada para programar la producción.

## Parámetros

En esta sección se definen los datos fijos del problema. Estos valores representan las condiciones bajo las cuales trabaja la planta y son usados por todo el programa para calcular tiempos, ingresos, costos y restricciones.

```python
JORNADA_INICIO = 5
JORNADA_FIN    = 23
```

Estas variables indican que la planta solo trabaja desde las 5:00 hasta las 23:00. Por lo tanto, el programa no debe programar operaciones durante la noche. Si una operación no cabe antes de las 23:00, se mueve al siguiente día a las 5:00.

```python
GALLETAS_POR_CAJA = {"Diamond": 20, "Gold": 30, "Silver": 60, "Bronze": 40}
PRECIO_CAJA       = {"Diamond": 16_000, "Gold": 14_000, "Silver": 10_000, "Bronze": 8_000}
TASA_MEZCLA       = {"Diamond": 1000, "Gold": 1200, "Silver": 1500, "Bronze": 2400}
```

Estos diccionarios guardan la información principal de cada referencia. Para cada tipo de galleta se conoce cuántas galletas trae una caja, cuál es su precio de venta y cuántas galletas por hora puede procesar la etapa de mezcla.

Esta información permite convertir una orden en tiempos de producción e ingresos. Por ejemplo, si una orden tiene muchas cajas, el programa calcula cuántas galletas representa y cuánto tiempo necesita en mezcla.

```python
SETUP = {
    "Diamond": {"Diamond": 0, "Gold": 1, "Silver": 2, "Bronze": 2},
    "Gold":    {"Diamond": 1, "Gold": 0, "Silver": 2, "Bronze": 0},
    "Silver":  {"Diamond": 2, "Gold": 2, "Silver": 0, "Bronze": 0},
    "Bronze":  {"Diamond": 2, "Gold": 0, "Silver": 0, "Bronze": 0},
}
```

La matriz `SETUP` indica el tiempo de alistamiento cuando se cambia de una referencia a otra en la etapa de mezcla. Si se produce la misma referencia seguida, el setup puede ser cero. Si se cambia a otra referencia, puede requerirse una o dos horas adicionales.

Esta matriz es importante porque afecta la conveniencia de una secuencia. Una secuencia con muchos cambios costosos puede aumentar el tiempo total de producción.

```python
T_MOLDEADO    = 3
T_EMPAQUE     = {"Diamond": 3, "Gold": 2, "Silver": 4, "Bronze": 3}
DESCUENTO_INV = 0.20
```

El tiempo de moldeado es fijo para todas las órdenes y vale 3 horas. El tiempo de empaque depende de la referencia producida. También se define un descuento del 20%, que se aplica cuando una orden se termina con demasiada anticipación y queda mucho tiempo en inventario.

```python
HEURISTICAS = {
    "1": "EDD + Setup + SPT + Revenue  (greedy compuesto)",
    "2": "Algoritmo de Johnson  (3 maquinas)",
    "3": "Algoritmo de Hodgson-Moore   (min. trabajos tardios)",
    "4": "Minimo Costo Total   (min. ventas perdidas + descuentos)",
}
```

Este diccionario guarda las opciones de heurísticas disponibles. Cada número se asocia con una regla de secuenciación diferente. Más adelante, el usuario puede escoger una de estas opciones desde el menú.

```python
ORDENES_DIA = {
    15: [
        (1,  "Diamond", 150, 16),
        (2,  "Gold",     80, 17),
        ...
    ],
    ...
}
```

Este bloque contiene las órdenes predefinidas del caso, organizadas por día de ingreso. Cada orden se escribe usando la siguiente estructura:

```python
(id, referencia, cajas, fecha_entrega)
```

Por ejemplo:

```python
(1, "Diamond", 150, 16)
```

Esto significa que la orden 1 es de tipo Diamond, tiene 150 cajas y debe entregarse el día 16.

## Funciones auxiliares

Estas funciones ayudan a manejar el tiempo dentro del programa. Como el caso usa varios días y horas, el código convierte las fechas en una escala más fácil de calcular.

```python
def hora_abs(dia: int, hora: float) -> float:
    return (dia - 15) * 24 + hora
```

Esta función convierte un día y una hora en una hora absoluta. Esto permite comparar fácilmente tiempos de distintos días. Por ejemplo, el día 16 a las 5:00 queda representado como 24 horas después del inicio del día 15.

```python
def hora_relativa(h: float):
    return 15 + int(h // 24), h % 24
```

Esta función hace lo contrario: toma una hora absoluta y la convierte nuevamente en día y hora. Es útil para mostrar los resultados en un formato que el usuario pueda entender.

```python
def fmt(h: float) -> str:
    dia, hh = hora_relativa(h)
    return f"Dia {dia} {hh:05.2f}h"
```

Esta función formatea los tiempos para que aparezcan de forma clara en los reportes. En lugar de mostrar solo un número, muestra algo como:

```text
Dia 16 08.50h
```

```python
def ajustar_jornada(t: float, dur: float) -> float:
```

Esta función verifica si una operación puede realizarse dentro de la jornada laboral. Si una operación inicia antes de las 5:00, se mueve al inicio de la jornada. Si no alcanza a terminar antes de las 23:00, se traslada al siguiente día a las 5:00.

Su lógica es clave porque evita que el programa programe producción cuando la planta está cerrada.

```python
def makespan_efectivo(t_ini: float, t_fin: float) -> float:
```

Esta función calcula el tiempo total efectivo de producción, descontando las horas nocturnas en las que la planta no trabaja. Esto permite obtener un makespan más representativo del tiempo realmente disponible.

## Modelos de datos

Los modelos de datos representan las partes principales del sistema. En este programa existen dos elementos centrales: la orden de producción y el scheduler.

La orden representa un pedido específico. El scheduler representa el sistema completo que organiza las órdenes y simula la producción.

### Orden

La clase `Orden` representa cada pedido de producción.

```python
@dataclass
class Orden:
    id: int
    referencia: str
    cajas: int
    fecha_entrega: int
    dia_ingreso: int
```

Cada orden tiene un identificador, una referencia, una cantidad de cajas, una fecha de entrega y un día de ingreso. Estos son los datos básicos que describen el pedido.

```python
hora_limite: float = 6.0
```

La hora límite indica la hora máxima de entrega dentro del día comprometido. En este caso, se usa una hora fija de las 6:00 para evaluar si la orden fue entregada a tiempo.

```python
t_mezcla:   float = field(init=False)
t_moldeado: float = field(init=False)
t_empaque:  float = field(init=False)
```

Estos tiempos no se ingresan manualmente. El programa los calcula automáticamente a partir de la referencia y la cantidad de cajas.

```python
inicio_mezcla: Optional[float] = field(default=None, repr=False)
fin_mezcla:    Optional[float] = field(default=None, repr=False)
inicio_moldeo: Optional[float] = field(default=None, repr=False)
fin_moldeo:    Optional[float] = field(default=None, repr=False)
inicio_empaq:  Optional[float] = field(default=None, repr=False)
fin_empaq:     Optional[float] = field(default=None, repr=False)
```

Estos campos guardan los tiempos programados de cada orden. Indican cuándo empieza y termina la orden en mezcla, moldeado y empaque. Al inicio están vacíos porque la orden todavía no ha sido simulada.

```python
congelada: bool = False
```

Este campo indica si una orden ya quedó fija dentro de la programación. Una orden congelada no se modifica cuando se vuelve a simular, porque representa producción que ya fue realizada o decidida.

Las siguientes son funciones y propiedades principales de la clase `Orden`.

```python
def __post_init__(self):
    g = self.cajas * GALLETAS_POR_CAJA[self.referencia]
    self.t_mezcla   = g / TASA_MEZCLA[self.referencia]
    self.t_moldeado = T_MOLDEADO
    self.t_empaque  = T_EMPAQUE[self.referencia]
```

Esta parte calcula los tiempos de procesamiento. Primero calcula cuántas galletas tiene la orden. Luego calcula el tiempo de mezcla dividiendo esa cantidad entre la tasa de mezcla. El moldeado es fijo y el empaque depende de la referencia.

```python
def reset(self):
    if not self.congelada:
        self.inicio_mezcla = self.fin_mezcla = None
        self.inicio_moldeo = self.fin_moldeo = None
        self.inicio_empaq  = self.fin_empaq  = None
```

Este método borra la programación de una orden cuando se necesita volver a simular. Sin embargo, si la orden está congelada, no se borra. Esto permite mantener fijas las órdenes que ya fueron decididas o producidas.

```python
@property
def deadline_abs(self):
    return (self.fecha_entrega - 15) * 24 + self.hora_limite
```

Esta propiedad calcula la fecha límite de entrega en la misma escala de tiempo usada por el programa. Así se puede comparar directamente contra el tiempo en que termina el empaque.

```python
@property
def ingreso_bruto(self):
    return self.cajas * PRECIO_CAJA[self.referencia]
```

Esta propiedad calcula el ingreso total esperado de la orden antes de considerar tardanzas o descuentos. Se obtiene multiplicando el número de cajas por el precio de cada caja.

```python
@property
def completada(self):
    return self.fin_empaq is not None
```

Esta propiedad indica si la orden ya terminó todo el proceso productivo. Una orden se considera completada cuando ya tiene una hora de fin en empaque.

```python
@property
def tardia(self):
    return self.completada and self.fin_empaq > self.deadline_abs
```

Esta propiedad indica si una orden terminó tarde. Una orden es tardía si ya fue completada y su hora de finalización en empaque es mayor que su fecha límite.

```python
@property
def tardanza_horas(self):
    return max(0.0, self.fin_empaq - self.deadline_abs) if self.completada else 0.0
```

Esta propiedad calcula cuántas horas de retraso tuvo la orden. Si la orden no fue tardía, la tardanza es cero.

```python
@property
def tiempo_en_inventario(self):
    if not self.completada or self.tardia:
        return 0.0
    return self.deadline_abs - self.fin_empaq
```

Esta propiedad calcula cuánto tiempo pasa una orden terminada antes de su fecha límite. Si la orden terminó tarde o no se ha completado, no se considera inventario.

```python
@property
def costo_ventas_perdidas(self):
    return self.ingreso_bruto if self.tardia else 0.0
```

Si una orden es tardía, se asume que se pierde la venta. Por eso, el costo de ventas perdidas es igual al ingreso bruto de esa orden.

```python
@property
def descuento_inventario(self):
    if self.tardia or not self.completada:
        return 0.0
    return self.ingreso_bruto * DESCUENTO_INV if self.tiempo_en_inventario > 24 else 0.0
```

Si una orden termina con más de 24 horas de anticipación, se aplica un descuento por inventario. Este descuento representa el costo de tener producto terminado demasiado temprano.

```python
@property
def ingreso_neto(self):
    return 0.0 if self.tardia else self.ingreso_bruto - self.descuento_inventario
```

Esta propiedad calcula el ingreso final de la orden. Si la orden fue tardía, se considera que no genera ingreso. Si no fue tardía, genera su ingreso bruto menos el posible descuento por inventario.

En general, la clase `Orden` concentra todos los datos de una orden y permite evaluar si fue producida a tiempo, cuánto ingresó y qué impacto económico tuvo.

### Scheduler

El scheduler es el componente principal del programa. Se encarga de administrar las órdenes, aplicar la heurística seleccionada, simular la producción y generar los resultados.

```python
class MagicCookiesScheduler:
```

Esta clase representa el sistema completo de programación de producción.

```python
def __init__(self, heuristica: str = "1"):
    self.ordenes: list       = []
    self.secuencia: list     = []
    self.dia_actual: int     = 15
    self._t_mez: float       = hora_abs(15, JORNADA_INICIO)
    self._t_mol: float       = hora_abs(15, JORNADA_INICIO)
    self._t_emp: float       = hora_abs(15, JORNADA_INICIO)
    self._ultima_ref: Optional[str] = None
    self._seq_congelada: list = []
    self.heuristica: str      = heuristica
```

Al crear el scheduler, se inicializan las órdenes, la secuencia de producción y el estado de las máquinas. Las tres máquinas empiezan libres el día 15 a las 5:00.

También se guarda la última referencia procesada en mezcla. Esto es necesario porque el tiempo de setup depende de qué referencia se produjo antes.

```python
def _secuenciar(self, pool, ref_act, t_mez=None, t_mol=None, t_emp=None,
                desde_dia=15, hasta_dia=19):
    fn = MAPA_HEURISTICAS[self.heuristica]
    return fn(pool, ref_act,
              t_mez_0=t_mez or self._t_mez,
              t_mol_0=t_mol or self._t_mol,
              t_emp_0=t_emp or self._t_emp,
              desde_dia=desde_dia, hasta_dia=hasta_dia)
```

Este método llama a la heurística activa. Recibe las órdenes pendientes y devuelve la secuencia en la que se deberían producir.

La ventaja de tener este método es que el resto del programa no necesita saber cuál heurística se está usando. Solo llama a `_secuenciar`, y este método se encarga de aplicar la opción seleccionada.

```python
def agregar_orden(self, id_, ref, cajas, fecha_entrega, dia_ingreso=None):
```

Este método permite agregar una orden nueva al sistema. Valida que la referencia exista, que el ID no esté repetido y luego crea una nueva orden.

```python
def cargar_dia(self, dia: int):
```

Este método carga automáticamente las órdenes predefinidas de un día. Sirve para ingresar rápidamente la demanda del caso sin escribir cada orden manualmente.

```python
def cerrar_dia(self, dia: int):
```

Este método fija las órdenes que ya empezaron a producirse hasta cierto día. Al cerrarlas, esas órdenes quedan congeladas y no se modifican en futuras simulaciones.

Además, este método actualiza la disponibilidad de las máquinas y la última referencia producida, para que la siguiente simulación comience desde el estado real del sistema.

## Heurísticas

Las heurísticas son las reglas que usa el programa para decidir el orden de producción. Todas reciben una lista de órdenes pendientes y devuelven una secuencia.

```python
HEURISTICAS = {
    "1": "EDD + Setup + SPT + Revenue  (greedy compuesto)",
    "2": "Algoritmo de Johnson  (3 maquinas)",
    "3": "Algoritmo de Hodgson-Moore   (min. trabajos tardios)",
    "4": "Minimo Costo Total   (min. ventas perdidas + descuentos)",
}
```

Este diccionario muestra las heurísticas disponibles para el usuario.

```python
def heuristica_greedy(pool: list, ref_act: Optional[str], **kw) -> list:
```

La primera heurística usa una regla compuesta. Ordena las órdenes teniendo en cuenta varios criterios: primero la fecha de entrega más cercana, luego el menor setup, después el menor tiempo de mezcla y finalmente el mayor ingreso.

La lógica es intentar cumplir fechas de entrega, reducir alistamientos, procesar rápido y priorizar órdenes valiosas.

```python
def score(o, ref):
    s = SETUP[ref][o.referencia] if ref else 0
    return (o.deadline_abs, s, o.t_mezcla, -o.ingreso_bruto)
```

Esta función interna calcula la prioridad de cada orden. Una orden es más atractiva si vence pronto, requiere poco setup, tiene menor tiempo de mezcla y genera más ingreso.

```python
def heuristica_johnson_3m(pool: list, ref_act: Optional[str], **kw) -> list:
```

La segunda heurística adapta el algoritmo de Johnson para tres máquinas: mezcla, moldeado y empaque.

```python
jobs = [(o, o.t_mezcla + o.t_moldeado, o.t_moldeado + o.t_empaque) for o in pool]
```

Para poder aplicar Johnson, el programa crea dos tiempos ficticios:

```text
G = mezcla + moldeado
H = moldeado + empaque
```

Luego ordena las órdenes usando esos dos tiempos. La intención es reducir el tiempo total de finalización de las órdenes.

```python
def heuristica_hodgson(pool: list, ref_act: Optional[str], ...):
```

La tercera heurística busca minimizar el número de órdenes tardías.

Primero ordena las órdenes por fecha de entrega. Luego simula rápidamente la secuencia. Si detecta que una orden queda tardía, retira de la secuencia la orden que más tiempo de mezcla consume y la manda al final.

```python
culpable = max(E[:i+1], key=lambda x: x.t_mezcla)
E.remove(culpable)
L.append(culpable)
```

La lógica es que, si una orden grande está causando retrasos, puede convenir moverla al final para permitir que otras órdenes más pequeñas se completen a tiempo.

```python
def heuristica_min_costo(pool: list, ref_act: Optional[str], ...):
```

La cuarta heurística se enfoca en el resultado económico. Busca reducir ventas perdidas por tardanza y descuentos por inventario.

```python
en_riesgo = []
holgadas  = []
```

Primero separa las órdenes en dos grupos. Las órdenes en riesgo son las que tienen poco margen para llegar a tiempo. Las holgadas son las que todavía tienen más espacio antes de su fecha de entrega.

```python
en_riesgo.sort(key=lambda x: (-x[1].ingreso_bruto, x[1].deadline_abs))
holgadas.sort(key=lambda x: (x[1].deadline_abs, x[0]))
```

Las órdenes en riesgo se ordenan dando prioridad a las de mayor ingreso. Las órdenes holgadas se ordenan por fecha de entrega y margen. Así se intenta proteger las órdenes más valiosas sin descuidar las fechas límite.

```python
def reordenar_por_setup(grupo, ref_inicio):
```

Después de organizar las órdenes por prioridad, esta parte intenta reducir los setups dentro de cada grupo. La idea es mantener el objetivo principal de la heurística, pero evitando cambios de referencia innecesariamente costosos.

```python
MAPA_HEURISTICAS = {
    "1": heuristica_greedy,
    "2": heuristica_johnson_3m,
    "3": heuristica_hodgson,
    "4": heuristica_min_costo,
}
```

Este diccionario conecta la opción elegida por el usuario con la función de heurística correspondiente.

## Simulación

La simulación asigna horarios reales de producción a las órdenes. El flujo productivo considerado es:

```text
Mezcla → Moldeado → Empaque
```

```python
def simular(self, desde_dia=15, hasta_dia=19,
            t_mez_0=None, t_mol_0=None, t_emp_0=None,
            uref_0=None, pool=None):
```

Este método simula la producción desde un día inicial hasta un día final. También puede recibir el estado actual de las máquinas, lo cual es útil cuando se re-simula después de cerrar un día.

```python
activas = pool if pool is not None else [o for o in self.ordenes if not o.congelada]
for o in activas:
    o.reset()
```

Primero identifica las órdenes activas, es decir, las que todavía pueden ser modificadas. Luego borra su programación anterior para recalcularla.

```python
pendientes = list(activas)
procesadas = []
```

Las órdenes pendientes son las que aún no han sido programadas en mezcla. Las procesadas son las que ya lograron entrar al flujo productivo.

```python
for dia in range(desde_dia, hasta_dia + 1):
    jf  = hora_abs(dia, JORNADA_FIN)
    seq = self._secuenciar(pendientes, u_ref, ...)
```

Para cada día, el programa calcula una secuencia usando la heurística activa. Luego intenta programar las órdenes en la etapa de mezcla.

```python
setup = SETUP[u_ref][orden.referencia] if u_ref else 0
t_ini = max(t_mez, hora_abs(dia, JORNADA_INICIO))
t_sf  = t_ini + setup
```

Antes de mezclar una orden, se calcula el setup necesario. Después se determina la hora más temprana en la que puede iniciar.

```python
if t_mf > jf:
    break
```

Si la orden no cabe dentro de la jornada, no se programa ese día y se pasa al día siguiente.

```python
orden.inicio_mezcla = t_mi
orden.fin_mezcla = t_mf
```

Si la orden sí cabe, se guardan sus tiempos de inicio y fin en mezcla.

```python
for o in procesadas:
    t = ajustar_jornada(max(t_mol, o.fin_mezcla), o.t_moldeado)
    o.inicio_moldeo = t
    o.fin_moldeo = t + o.t_moldeado
```

Después de mezcla, el programa agenda el moldeado. Una orden solo puede iniciar moldeado cuando ya terminó mezcla y cuando la máquina de moldeado está libre.

```python
for o in procesadas:
    t = ajustar_jornada(max(t_emp, o.fin_moldeo), o.t_empaque)
    o.inicio_empaq = t
    o.fin_empaq = t + o.t_empaque
```

Finalmente se agenda el empaque. Una orden solo puede iniciar empaque cuando ya terminó moldeado y cuando la máquina de empaque está disponible.

```python
self.secuencia = self._seq_congelada + [o.id for o in procesadas]
```

Al final se guarda la secuencia completa. Esta incluye las órdenes congeladas y las órdenes recién procesadas.

## Ejecución

La ejecución del programa se realiza principalmente mediante un menú interactivo. Desde allí el usuario puede cargar órdenes, escoger heurísticas, simular, revisar reportes y analizar resultados.

### Menú

```python
def menu_heuristica() -> str:
```

Esta función muestra el primer menú del programa. Su objetivo es que el usuario seleccione la heurística que desea usar antes de iniciar la simulación.

```python
for k, v in HEURISTICAS.items():
    print(f"  {k}.  {v}")
```

Esta parte imprime las heurísticas disponibles. Luego el usuario escoge una opción entre 1 y 4.

```python
def menu():
```

Esta función controla el menú principal del programa. Primero pide al usuario seleccionar una heurística y luego crea el scheduler.

```python
heuristica = menu_heuristica()
s = MagicCookiesScheduler(heuristica=heuristica)
```

Después muestra las opciones disponibles:

```python
ops = {
    "1":  "Agregar orden individual",
    "2":  "Cargar ordenes predefinidas de un dia",
    "3":  "Ejecutar simulacion completa",
    ...
}
```

Cada opción ejecuta una acción diferente. Por ejemplo, una opción agrega órdenes, otra ejecuta la simulación y otra muestra KPIs.

```python
while True:
    op = input("  Opcion: ").strip().upper()
```

El menú se repite hasta que el usuario decida salir. Esto permite usar el programa de manera interactiva.

### Registro de carga de órdenes

El registro de órdenes ocurre principalmente mediante dos métodos.

```python
def agregar_orden(self, id_, ref, cajas, fecha_entrega, dia_ingreso=None):
```

Este método registra una orden individual. El usuario ingresa los datos y el programa crea la orden correspondiente.

```python
ref_n = next((r for r in GALLETAS_POR_CAJA if r.lower() == ref.lower()), None)
if not ref_n:
    raise ValueError(f"Referencia '{ref}' invalida.")
```

Esta parte valida que la referencia ingresada exista. Si el usuario escribe una referencia que no corresponde a Diamond, Gold, Silver o Bronze, el programa muestra un error.

```python
if any(o.id == id_ for o in self.ordenes):
    raise ValueError(f"ID {id_} ya existe.")
```

Esta parte evita que existan dos órdenes con el mismo identificador.

```python
o = Orden(id=id_, referencia=ref_n, cajas=cajas, fecha_entrega=fecha_entrega, dia_ingreso=d)
self.ordenes.append(o)
```

Si los datos son válidos, se crea la orden y se agrega a la lista general de órdenes del sistema.

```python
def cargar_dia(self, dia: int):
```

Este método carga todas las órdenes predefinidas de un día específico.

```python
for id_, ref, cajas, fecha in ORDENES_DIA[dia]:
    self.agregar_orden(id_, ref, cajas, fecha, dia_ingreso=dia)
```

La lógica es recorrer las órdenes guardadas para ese día y agregarlas una por una al sistema.

### Ingreso de demanda

```python
def ingresar_demanda_dia(self):
```

Esta función permite ingresar nueva demanda en días posteriores y re-simular el plan.

```python
dia_nuevo = int(input("\n  Dia de las nuevas ordenes (16-19): ").strip())
```

Primero se pide el día en que ingresan las nuevas órdenes.

```python
self.cerrar_dia(dia_nuevo - 1)
```

Luego se cierra el día anterior. Esto congela las órdenes que ya comenzaron y actualiza el estado de las máquinas.

```python
if modo == "a":
    self.cargar_dia(dia_nuevo)
else:
    # ingreso manual orden por orden
```

Después se pueden cargar automáticamente las órdenes de ese día o ingresarlas manualmente.

```python
pendientes = [o for o in self.ordenes if not o.congelada]
```

Esta línea identifica las órdenes que todavía pueden ser reprogramadas. Las órdenes congeladas quedan fuera de la nueva simulación.

```python
self.simular(desde_dia=dia_nuevo, hasta_dia=19,
             t_mez_0=self._t_mez, t_mol_0=self._t_mol, t_emp_0=self._t_emp,
             uref_0=self._ultima_ref, pool=pendientes)
```

Finalmente se re-simula desde el nuevo día, manteniendo fijas las órdenes anteriores. Esta lógica permite actualizar el plan sin cambiar lo que ya fue decidido.

### Reportes, KPIs y visualización de resultados

Esta parte del programa muestra los resultados obtenidos después de simular.

```python
def reporte_programacion(self):
```

Este reporte muestra una tabla con cada orden completada. Incluye su referencia, cajas, fecha de entrega, fin de empaque, si fue tardía, tardanza, inventario e ingreso neto.

```python
def reporte_kpis(self):
```

Este método calcula los indicadores acumulados de toda la programación.

```python
makespan = makespan_efectivo(min(o.inicio_mezcla for o in p),
                             max(o.fin_empaq for o in p))
tard = sum(o.tardanza_horas for o in p)
vp   = sum(o.costo_ventas_perdidas for o in p)
desc = sum(o.descuento_inventario for o in p)
ing  = sum(o.ingreso_neto for o in p)
```

Aquí se calculan los principales resultados: makespan efectivo, tardanza total, ventas perdidas, descuentos por inventario e ingreso neto total.

```python
def reporte_kpis_dia(self, dia: int):
```

Este método calcula los KPIs de un día específico. Solo considera las órdenes que terminaron empaque durante ese día.

```python
def gantt_consola(self, dia: int):
```

Esta función muestra una visualización tipo Gantt en la consola. Presenta qué orden se procesa en cada máquina y en cada hora del día.

```python
def detalle_mezcla(self):
```

Este reporte muestra el detalle de la etapa de mezcla. Es útil porque allí se aplican los setups entre referencias.

```python
def estado_sistema(self):
```

Este método muestra el estado actual del sistema: heurística activa, día actual, última referencia procesada, disponibilidad de las máquinas, órdenes congeladas y órdenes activas.

## Modo demo

El modo demo sirve como una herramienta rápida para comparar las heurísticas sin tener que usar manualmente todas las opciones del menú.

```python
def demo():
```

El modo demo permite comparar automáticamente las cuatro heurísticas usando las órdenes del día 15.

```python
for h in HEURISTICAS:
    s = MagicCookiesScheduler(heuristica=h)
    s.cargar_dia(15)
    s.simular(15, 19)
    s.reporte_kpis()
```

La lógica es sencilla: para cada heurística se crea un scheduler nuevo, se cargan las mismas órdenes, se simula la producción y se muestran los KPIs.

Esto permite comparar cuál heurística obtiene mejores resultados en términos de tardanza, ventas perdidas, descuentos e ingreso neto.

```python
if __name__ == "__main__":
    import sys
    if "--demo" in sys.argv:
        demo()
    else:
        menu()
```

Esta última parte decide cómo se ejecuta el programa. Si se usa el argumento `--demo`, se corre la comparación automática. Si no se usa, se abre el menú interactivo.


