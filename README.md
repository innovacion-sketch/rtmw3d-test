# rtmw3d-test — Validación RTMW3D para probador virtual de tenis

Motor de tracking 3D de cuerpo completo (MMPose / proyecto rtmpose3d) evaluado como
reemplazo de MediaPipe para el "espejo mágico" de kiosco. Estado y mediciones: **[RESULTADOS_FASE1.md](RESULTADOS_FASE1.md)**.

Este repo contiene solo el código propio y los scripts de setup. Lo pesado
(venv, mmpose clonado, wheels de torch, checkpoints) se regenera con el script.

## Setup en PC nueva (oficina, GTX 1660)

Requisitos previos: Python 3.10 (`py -3.10` debe funcionar), git, driver NVIDIA instalado (`nvidia-smi` debe responder).

```powershell
git clone <URL-DE-ESTE-REPO> C:\proyectos\rtmw3d-test
cd C:\proyectos\rtmw3d-test
powershell -ExecutionPolicy Bypass -File .\setup_oficina.ps1
```

El script es **reanudable**: si la red se corta, correrlo de nuevo y continúa donde quedó.
Descarga ~3 GB (torch 2.6 GB + checkpoints 315 MB). Atajo: copiar por USB las carpetas
`wheels\` y `mmpose\projects\rtmpose3d\checkpoints\` de la laptop — el script las detecta y no re-descarga.

Al final debe imprimir `CUDA: True`. Si no: revisar driver NVIDIA, no tocar versiones de torch/mmcv.

## Prueba en GPU (plan de mañana)

1. **Identificar la ELP**: activar venv (`.\.venv\Scripts\Activate.ps1`) y correr `python bridge\list_cameras.py`.
2. **Demo con webcam + FPS** (desde `mmpose\projects\rtmpose3d\`):

```powershell
cd mmpose\projects\rtmpose3d
$env:PYTHONPATH = "."
python ..\..\..\bridge\body3d_cam_demo.py `
  demo\rtmdet_m_640-8xb32_coco-person.py `
  checkpoints\rtmdet_m_8xb32-100e_coco-obj365-person-235e8209.pth `
  configs\rtmw3d-l_8xb64_cocktail14-384x288.py `
  checkpoints\rtmw3d-l_8xb64_cocktail14-384x288-794dbc78_20240626.pth `
  --input webcam --cam-id <INDICE_ELP> --show --device cuda:0
```

   Imprime `[FPS] ...` cada segundo y el promedio al salir (ESC para cerrar, o `--max-frames 200` para corte automático).

3. **Checklist de validación** (criterios Fase 1):
   - [ ] FPS promedio en GTX 1660 con RTMW3D-L (umbral: ≥8 FPS)
   - [ ] Keypoints de pies (17–22) dibujados y siguiendo el movimiento real de los pies
   - [ ] Estabilidad de Z con el pie apuntando a cámara vs de perfil
   - [ ] Si FPS < 8: NO hay variante menor de RTMW3D (solo L y X) — probar bajando resolución de captura antes de descartar

## Estructura

- `bridge\body3d_cam_demo.py` — copia del demo oficial con `--cam-id`, `--max-frames` y contador de FPS (el original hardcodea cámara 0 y no mide).
- `bridge\list_cameras.py` — sondeo de índices de cámara.
- `setup_oficina.ps1` — setup completo automatizado con todos los fixes conocidos.
- `RESULTADOS_FASE1.md` — reporte: versiones, URLs de checkpoints, comandos, FPS, problemas y soluciones.
- Fase 2 (pendiente, tras validar FPS): `bridge\server.py` con WebSocket de keypoints de pies hacia la app web Three.js.

## Trampas conocidas (no pisar de nuevo)

Detalle completo en RESULTADOS_FASE1.md. En corto: numpy SIEMPRE 1.26.4; mmpose se instala **no-editable** (el `-e` rompe `.mim` en Windows); `wheel` antes de chumpy; matplotlib ≤3.9.x; los wheels grandes se bajan con curl reanudable, no con pip directo.
