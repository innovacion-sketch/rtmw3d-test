# RESULTADOS FASE 2 — Puente WebSocket RTMW3D → espejo web

Estado: server y cliente de prueba implementados; **medición en PC de oficina pendiente**.

## Cómo arrancar el server

En la PC con GPU (venv activado):

```powershell
cd C:\proyectos\rtmw3d-test
.\.venv\Scripts\Activate.ps1
python bridge\server.py
```

Debe imprimir en orden: `[ws] sirviendo en ws://localhost:8765`, `[modelos] cargando...`,
`[modelos] listos`, `[camara] indice 0 abierta...` y luego `[FPS] ...` cada segundo.
Detener con Ctrl+C.

Configuración (índice de cámara, resolución, puerto, device, umbral del detector):
constantes al inicio de `bridge\server.py`.

## Cómo probar extremo a extremo

Con el server corriendo, abrir `bridge\test_client.html` en el navegador (doble clic).
Muestra: estado de conexión, FPS del server, latencia aproximada (ms), y los
puntos de pies dibujados sobre canvas negro — talón (punto grande), dedo gordo,
dedo chico, tobillo (anillo), con líneas talón→dedos. Verde = izquierdo, naranja = derecho.
La opacidad de cada punto refleja su score (pies ocultos → puntos casi transparentes).

## Formato del mensaje (JSON por frame)

```json
{"t": 1760000000000, "w": 640, "h": 480, "fps": 13.2,
 "left":  {"ankle": [x,y,z], "toe": [x,y,z], "small_toe": [x,y,z], "heel": [x,y,z],
           "score": {"ankle": 0.8, "toe": 0.7, "small_toe": 0.7, "heel": 0.8}},
 "right": {"..."}}
```

- `x, y`: píxeles de la imagen de cámara (origen arriba-izquierda).
- `z`: profundidad relativa del modelo RTMW3D (menor = más cerca de la cámara).
- `toe` = dedo gordo. Sin persona detectada: `left`/`right` = `null`.
- Con varias personas en cuadro se publica solo la de bbox más grande (la más cercana).

## Mediciones (pendientes de la PC de oficina)

| Métrica | Valor |
|---|---|
| FPS pipeline completo (captura+inferencia+envío) | PENDIENTE (esperado ~13, igual que benchmark) |
| Latencia server→navegador | PENDIENTE (esperado <5 ms en localhost) |
| Estabilidad de Z pie de frente vs perfil | PENDIENTE — observar el valor `z` del talón en el test_client |

## Notas de diseño

- Usa la API de inferencia de mmpose (`init_detector`/`init_model`/`inference_topdown`),
  NO subprocesos del demo, y NADA de matplotlib (el cuello de 0.5 FPS del demo).
- Inferencia en un hilo dedicado; asyncio + `websockets` solo para publicar
  (broadcast a todos los clientes conectados).
- Loop resiliente: si la cámara se cae o se desconecta, reintenta cada 3 s sin tumbar el server.
- El siguiente paso tras validar será conectar el HTML real del espejo (Three.js)
  al mismo WebSocket — el test_client.html sirve de referencia de parsing.
