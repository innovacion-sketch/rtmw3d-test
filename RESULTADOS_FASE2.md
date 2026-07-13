# RESULTADOS FASE 2 — Puente WebSocket RTMW3D → espejo web

## ✅ FASE 2 APROBADA (2026-07-13, PC oficina GTX 1660 + ELP)

`python bridge\server.py` corriendo + `test_client.html` mostrando los pies
en vivo: **11.1 FPS de pipeline completo, 46 ms de latencia**, tracking de
pies estable y sin alucinaciones según prueba en vivo.

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

## Mediciones (PC oficina, GTX 1660, ELP 640×480)

| Métrica | Valor |
|---|---|
| FPS pipeline completo (captura+inferencia+envío) | **11.1 FPS** (vs 13.6 de inferencia pura: el costo de captura+JSON+broadcast es ~2.5 FPS) |
| Latencia captura→navegador | **46 ms** (incluye la inferencia del frame; sobra para efecto espejo) |
| Tracking de pies en vivo | Sigue el pie correctamente, sin alucinaciones (prueba cualitativa en vivo) |
| Estabilidad de Z | **Pie quieto: z estable (sin oscilación visible). Pie en movimiento: varía en el 2º decimal.** Con ambos pies apoyados a igual distancia, las z de ambos talones coinciden (~5.24 vs ~5.27). No se aprecia jitter que requiera filtrado; si el render 3D lo pidiera, un One-Euro suave sobraría. |

## Notas de diseño

- Usa la API de inferencia de mmpose (`init_detector`/`init_model`/`inference_topdown`),
  NO subprocesos del demo, y NADA de matplotlib (el cuello de 0.5 FPS del demo).
- Inferencia en un hilo dedicado; asyncio + `websockets` solo para publicar
  (broadcast a todos los clientes conectados).
- Loop resiliente: si la cámara se cae o se desconecta, reintenta cada 3 s sin tumbar el server.
- El siguiente paso tras validar será conectar el HTML real del espejo (Three.js)
  al mismo WebSocket — el test_client.html sirve de referencia de parsing.
