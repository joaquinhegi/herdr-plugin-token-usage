# Especificación de desarrollo: Herdr Agent Token Usage

## Rol y objetivo

Actuá como desarrollador senior especializado en extensiones de Herdr, Python, Claude Code y Codex CLI. Implementá un **plugin local y seguro de Herdr** que muestre **permanentemente en la barra lateral de agentes** el consumo **acumulado de tokens desde el comienzo de la sesión/tarea de cada agente**, sin necesidad de abrir otro dashboard.

El usuario utiliza Herdr con múltiples agentes y quiere ver el consumo de **cada sesión de forma independiente**. No quiere la cuota general de la cuenta, ni solamente el tamaño de la ventana de contexto, ni los tokens del último turno.

### Apariencia esperada (datos ilustrativos)

```text
agents                         grouped
──────────────────────────────────────
○ Fundanet.Corporate            Claude
  claude · 125.4k tokens · $2.35

○ Pipeline CI/CD                 Codex
  codex · 84.2k tokens · $1.48
```

**Prioridad MVP:** total acumulado de tokens por agente/sesión. El coste monetario es **opcional**, debe poder desactivarse y nunca presentarse como exacto si faltan tarifas o los datos de caché/facturación no permiten calcularlo con fiabilidad.

## Investigación obligatoria antes de programar

1. Comprobá la versión local de Herdr y las APIs de plugins realmente disponibles.
2. Consultá la documentación oficial actual, especialmente:
   - https://herdr.dev/docs/plugins/
   - https://herdr.dev/docs/configuration/
   - https://herdr.dev/docs/cli-reference/
   - https://herdr.dev/docs/socket-api/
3. Inspeccioná los ejemplos públicos de plugins **solo como referencia**, sin instalar ni ejecutar su código.
4. Identificá la forma oficial de relacionar `pane_id` ↔ agente ↔ identificador de sesión nativa Claude/Codex. No supongas que el directorio de trabajo basta para identificar una sesión.
5. Identificá los formatos actuales de eventos de uso y sus diferencias entre versiones. Si alguna estructura no está documentada, confirmala con ejemplos **locales anonimizados**.
6. Si no se puede resolver de manera fiable la sesión asociada a un panel, mostrale `—` o ningún token; **nunca atribuyas tokens de otra sesión**.

## Requisitos funcionales

### RF01: Consumo acumulado por sesión

- Mostrar tokens acumulados **desde el inicio de la sesión del agente asociada al panel actual de Herdr**.
- No reiniciar el contador al completar un prompt, al compactar contexto, al hacer una pausa o al alternar entre agentes.
- Conservar y reconstruir el valor si se reinicia Herdr y luego se reanuda **la misma sesión**.
- Si en un mismo panel se inicia una sesión distinta, reiniciar la cifra para esa nueva sesión y limpiar los metadatos de la sesión anterior.
- La misma sesión reanudada conserva su acumulado; una sesión nueva en el mismo workspace no hereda el anterior.
- Los agentes en paralelo deben tener contadores independientes incluso si comparten proyecto, directorio de trabajo o modelo.

### RF02: Modelos y proveedores

- MVP compatible con **Claude Code** y **Codex CLI**.
- Diseñar adaptadores separados para cada proveedor para poder añadir otros posteriormente.
- Distinguir correctamente eventos de consumo de entrada/salida/caché/razonamiento cuando existan.
- Diferenciar claramente **tokens procesados acumulados**, **contexto actual** y **cuota**, usando solo la primera métrica en el contador principal.
- Documentar si el total incluye lectura/escritura de caché y razonamiento, y evitar dobles sumas.
- Si el origen reporta contadores acumulativos (snapshots), calcular deltas o usar el último acumulado según su semántica; no sumar snapshots enteros repetidos.
- Si el origen reporta consumo por llamada, sumar solo eventos únicos y definitivos; evitar duplicación por reintentos, mensajes parciales y relecturas.

### RF03: Actualización y rendimiento

- Actualizar automáticamente mientras los agentes trabajan, preferentemente por eventos o lectura incremental de los archivos modificados.
- Objetivo de latencia visible de 3 a 10 segundos cuando exista nueva información persistida; no inventar consumos antes de que aparezcan en la fuente.
- No releer todos los historiales desde cero continuamente. Mantener offsets/cursor por archivo, con detección de rotación, truncado y reinicio.
- Limitar CPU, memoria, accesos a disco y número de procesos hijos. No bloquear la interfaz de Herdr.
- Manejar bien JSONL incompleto, líneas truncadas, archivos bloqueados y sesiones cerradas.

### RF04: Barra lateral siempre visible

Usar **metadatos por pane**, no un dashboard independiente:

```bash
herdr pane report-metadata <pane_id> \
  --source local:agent-token-usage \
  --token tokens="125.4k tokens"
```

La estructura es ilustrativa; verificar flags y la compatibilidad con la versión instalada. Usar `HERDR_BIN_PATH` si corresponde al proceso del plugin.

Integrar el token `$tokens` en `~/.config/herdr/config.toml`. Ejemplo de layout inicial (adaptar a la configuración existente sin destruirla):

```toml
[ui.sidebar.agents]
rows = [
  ["state_icon", "workspace", "tab"],
  ["agent", "$tokens"]
]
```

- Si hay `rows_by_agent` para `claude` o `codex`, integrar también el token allí: esos overrides sustituyen a `rows`.
- No sobrescribir ni duplicar tablas TOML existentes.
- Proporcionar una configuración mínima alternativa para conservar filas personalizadas que el usuario ya tenga.
- Los tokens se muestran solo cuando exista una asociación fiable entre pane y sesión.
- Si el coste opcional se implementa, puede mostrarse como `$cost`, o junto a `$tokens` si el espacio disponible lo permite.

### RF05: Formato de la métrica

- 950 → `950 tokens`; 1.250 → `1.3k tokens`; 125.400 → `125.4k tokens`; 1.200.000 → `1.2M tokens`.
- Evitar grandes cadenas que rompan el sidebar.
- Mantener los datos internos en enteros sin redondear. El redondeo es solo visual.
- Cuando no haya datos fiables mostrar `—` o limpiar el token, no `0` engañoso.
- El coste debe aparecer como `~$N.NN` si es una estimación; no calcularlo si no hay información suficiente.

## Requisitos de seguridad (OBLIGATORIOS)

1. **Local-first y offline:** sin telemetría, sin analítica, sin peticiones HTTP externas, sin envío de archivos ni contenidos de conversaciones.
2. **No leer secretos:** evitar `.env`, credenciales, `.ssh`, llaveros, tokens y ficheros que no sean los estrictamente necesarios para contar el uso.
3. **Mínimo privilegio:** acceso de solo lectura a los ficheros de uso/sesión de Claude y Codex; escritura únicamente en el directorio propio de estado del plugin y mediante la API oficial de metadatos de Herdr.
4. **No modificar** `~/.claude/settings.json`, configuración de Codex, hooks globales ni configuraciones de sistema en el MVP.
5. No instalar dependencias ni ejecutar scripts remotos sin consentimiento. Preferir biblioteca estándar de Python si resulta viable.
6. No ejecutar comandos construidos a partir de contenido de un historial. Para subprocesses, argumentos estructurados sin shell y con rutas verificadas.
7. No persistir prompts, respuestas, rutas sensibles, contenido de mensajes ni tokens de autenticación en logs/estado. Guardar solo IDs mínimos, cursores y contadores.
8. Los logs deben contener solo información técnica mínima, sin datos de conversación.
9. Diseñar una desinstalación que borre solo los metadatos y archivos propios y permita revertir exclusivamente los cambios de configuración del plugin.
10. Documentar qué directorios inspecciona el plugin y por qué; si una sesión no es accesible, degradar con seguridad.

## Arquitectura sugerida (ajustar a la API real)

```text
herdr-agent-token-usage/
├── herdr-plugin.toml
├── README.md
├── src/
│   ├── main.py                  # ciclo de vida e integración
│   ├── herdr_client.py          # lectura de panes/sesiones y publicación de metadatos
│   ├── session_resolver.py      # asociación estricta pane ↔ sesión
│   ├── usage_model.py           # normalización y totalización
│   ├── sources/
│   │   ├── claude.py             # parser Claude Code
│   │   └── codex.py              # parser Codex CLI
│   └── state.py                 # offsets, contadores y deduplicación
├── tests/
│   ├── fixtures/                # datos sintéticos, nunca sesiones reales
│   ├── test_claude.py
│   ├── test_codex.py
│   ├── test_session_mapping.py
│   ├── test_replay_and_resume.py
│   └── test_security.py
└── docs/
    └── SECURITY.md
```

Antes de fijar los nombres de archivos y el manifiesto, comprobar el contrato de plugins vigente de Herdr. Preferir hooks oficiales o un proceso local gestionado por Herdr; **no crear un daemon global persistente si no es necesario**.

## Casos que la implementación tiene que superar

1. Dos panes Claude en el mismo repositorio con sesiones distintas → dos contadores independientes.
2. Claude y Codex trabajando en paralelo → cada pane muestra solo su consumo.
3. Un mismo agente completa tres prompts → el contador sigue creciendo sin ponerse a cero.
4. Reinicio de Herdr y reanudación de la misma sesión → se recupera la cifra.
5. Sesión nueva en el pane anterior → desaparece el valor viejo y empieza el nuevo cuando se detecte.
6. Una compactación del contexto → no borra el consumo histórico.
7. Evento duplicado/replay JSONL → no se vuelve a sumar.
8. Una fuente emite varios snapshots acumulativos → no se suman entre sí incorrectamente.
9. Un archivo JSONL crece mientras se lee → lectura incremental segura.
10. Identificador de sesión inexistente/ambiguo → sin cifra, y mensaje de diagnóstico útil.
11. Un pane se cierra → limpiar metadatos/estado propios sin alterar otros agentes.
12. Fallo en un parser → los demás agentes continúan funcionando.
13. Reinicio sin conectividad → el plugin funciona localmente.
14. Sidebar previamente personalizado → se conserva la configuración original.

## Entregables

1. Plugin funcional completo, con manifiesto válido para la versión real de Herdr.
2. Instrucciones de **instalación local** desde el repositorio de trabajo (sin publicar ni instalar nada de terceros).
3. Instrucciones de activación y configuración de la barra lateral, mostrando exactamente qué modificar.
4. Comandos de recarga, comprobación de funcionamiento, logs, desactivación y desinstalación.
5. Tests automatizados para parsers, deduplicación, reanudación, aislamiento por sesión y errores.
6. README con ejemplos y límites conocidos de la precisión de los tokens y de los costes.
7. Informe de seguridad breve con archivos leídos, archivos escritos, comandos ejecutados y riesgos residuales.

## Plan de ejecución obligatorio para el agente

**Fase 1 — Inspección:** investigar versión, API, metadatos de sesiones y formatos de consumo. Informar los hallazgos y limitaciones. No tocar configuración del usuario.

**Fase 2 — MVP:** implementar adaptadores, asociación inequívoca de sesiones, contador acumulado y publicación de `$tokens` en una instalación local de pruebas.

**Fase 3 — Validación:** tests y comprobación manual contra dos sesiones simultáneas. Detectar y resolver doble contabilización y cruces entre sesiones.

**Fase 4 — Integración:** preparar un parche pequeño y reversible de `config.toml`, con backup, mostrando el diff para aprobación antes de modificarlo. No modificar configuración de Claude/Codex.

**Fase 5 — Entrega:** README, instrucciones y demostración de que los tokens cambian mientras los agentes trabajan.

### Criterio de aceptación definitivo

Al abrir Herdr debo ver, debajo de **cada agente Claude o Codex**, una cifra acumulada como `125.4k tokens`, que crezca durante la tarea y siga siendo la misma tras abrir otro pane o reiniciar Herdr y reanudar esa sesión. **No debo abrir dashboards, instalar servicios de red, ni conceder permisos sobre secretos.**

Si una capacidad concreta no está disponible en la versión actual de Herdr, explicá el impedimento, proponé la alternativa más simple y verificable y **no simules una integración inexistente**.

**Empezá por la Fase 1 y después avanzá con la implementación. No ejecutes instalaciones, ediciones en configuraciones reales ni cambios destructivos sin aprobación explícita.**
