# RESULTADOS FASE 1 — Validación RTMW3D (pose 3D cuerpo completo)

Fecha: 2026-07-12
Máquina de prueba: laptop SIN GPU NVIDIA (solo Intel Iris Xe) → validación funcional en CPU.
**Los FPS en GPU (GTX 1660) quedan pendientes para la PC de oficina** — ver `README.md` / `setup_oficina.ps1`.

## Veredicto

| Criterio | Resultado |
|---|---|
| Pipeline detector + RTMW3D-L corre | ✅ Sí (CPU) |
| Esqueleto 3D generado (imagen de prueba) | ✅ Sí, 2D + 3D correctos |
| Demo con webcam en vivo | ✅ Sí, 20/20 frames con detección |
| Keypoints de pies (133 kpts, índices 17–22) | ✅ Presentes con nombre, XYZ y score |
| FPS conocido | ✅ CPU: **0.30 FPS** (inviable, esperado). GPU: pendiente |
| Comando reproducible documentado | ✅ Abajo |

## Versiones verificadas (salida real)

```
numpy 1.26.4 | torch 2.1.2+cu118 | CUDA: False   <- False solo porque esta máquina no tiene NVIDIA
mmcv 2.1.0 | mmdet 3.3.0 | mmpose 1.3.2
```

Extras fijados: `opencv-python==4.10.0.84`, `matplotlib==3.9.4`, `websockets 16.1`, `wheel`, `setuptools`, `chumpy 0.70`.

## Checkpoints usados (URLs reales del README de rtmpose3d)

Carpeta: `mmpose\projects\rtmpose3d\checkpoints\`

| Modelo | Archivo | URL |
|---|---|---|
| Detector personas (RTMDet-M) | `rtmdet_m_8xb32-100e_coco-obj365-person-235e8209.pth` (94.4 MB) | https://download.openmmlab.com/mmpose/v1/projects/rtmpose/rtmdet_m_8xb32-100e_coco-obj365-person-235e8209.pth |
| RTMW3D-L | `rtmw3d-l_8xb64_cocktail14-384x288-794dbc78_20240626.pth` (220 MB) | https://download.openmmlab.com/mmpose/v1/wholebody_3d_keypoint/rtmw3d/rtmw3d-l_8xb64_cocktail14-384x288-794dbc78_20240626.pth |
| RTMW3D-X (no probado) | — | https://download.openmmlab.com/mmpose/v1/wholebody_3d_keypoint/rtmw3d/rtmw3d-x_8xb64_cocktail14-384x288-b0a0eab7_20240626.pth |

**Nota**: NO existen variantes M/S de RTMW3D — solo L y X. L ya es la más chica; si en la 1660 no alcanza FPS, las opciones son bajar resolución de entrada o cambiar de modelo, no hay variante menor.

## Comandos exactos que funcionaron

Desde `mmpose\projects\rtmpose3d\` con el venv activado y `PYTHONPATH=.`:

Imagen de prueba:
```powershell
$env:PYTHONPATH = "."
python demo\body3d_img2pose_demo.py `
  demo\rtmdet_m_640-8xb32_coco-person.py `
  checkpoints\rtmdet_m_8xb32-100e_coco-obj365-person-235e8209.pth `
  configs\rtmw3d-l_8xb64_cocktail14-384x288.py `
  checkpoints\rtmw3d-l_8xb64_cocktail14-384x288-794dbc78_20240626.pth `
  --input ..\..\tests\data\coco\000000000785.jpg `
  --output-root C:\proyectos\rtmw3d-test\out_fase1 --save-predictions --device cpu
```

Webcam (usa la copia instrumentada en `bridge\`, con selector de cámara y contador FPS):
```powershell
$env:PYTHONPATH = "."
python C:\proyectos\rtmw3d-test\bridge\body3d_cam_demo.py `
  demo\rtmdet_m_640-8xb32_coco-person.py `
  checkpoints\rtmdet_m_8xb32-100e_coco-obj365-person-235e8209.pth `
  configs\rtmw3d-l_8xb64_cocktail14-384x288.py `
  checkpoints\rtmw3d-l_8xb64_cocktail14-384x288-794dbc78_20240626.pth `
  --input webcam --cam-id 0 --show --device cuda:0
```
En la PC de oficina: `--device cuda:0`, y elegir la ELP con `--cam-id N` (probar índices con `bridge\list_cameras.py`). `--max-frames 100` para una medición acotada sin tocar teclado; sin él, ESC cierra.

## FPS medidos

| Dispositivo | Modelo | FPS promedio |
|---|---|---|
| CPU (Iris Xe, laptop) | RTMW3D-L | **0.30 FPS** (20 frames, 66.9 s; rango 0.23–0.34) |
| GTX 1660 | RTMW3D-L | **PENDIENTE** (mañana en PC de oficina) |

## Observaciones de keypoints de pies

Formato COCO-WholeBody 133 kpts. Los pies son índices **17–22**: `left_big_toe(17), left_small_toe(18), left_heel(19), right_big_toe(20), right_small_toe(21), right_heel(22)`; tobillos en 15/16.

- **Imagen (esquiadora COCO)**: los 6 puntos presentes y anatómicamente coherentes — talón detrás del dedo, Z del pie de apoyo ~0 (rebase al piso), scores 0.57–0.78. Ambas vistas (2D y 3D) los dibujan bien.
- **Webcam en vivo**: detección en 20/20 frames. Scores de pies bajos (0.11–0.23) porque los pies estaban FUERA de encuadre (webcam de laptop apuntando al torso) — el modelo degrada el score en vez de alucinar posiciones firmes, que es el comportamiento deseado para gatear visibilidad en el espejo.
- **Estabilidad de Z pie de frente vs de perfil**: NO evaluable con rigor a 0.3 FPS y sin los pies en cuadro. Queda como prueba clave para la GTX 1660 (punto 3 del plan de mañana en README).

## Problemas encontrados y solución

1. **Red doméstica inestable cortó pip** (torch 2.6 GB se perdía al 43%): pip no reanuda. Solución: bajar los wheels con `curl -C -` (reanudable) en bucle de reintento y `pip install` desde archivo local. El script `setup_oficina.ps1` ya lo hace así.
2. **chumpy: `invalid command 'bdist_wheel'`** incluso con `--no-build-isolation`: faltaba el paquete `wheel` en el venv. Solución: `pip install wheel setuptools` antes de chumpy.
3. **`pip install -e` de mmpose rompe los configs `mmpose::`** en Windows: mmengine busca `site-packages\mmpose\.mim\model-index.yml`, que el modo editable no crea. NO parchear a mano dentro de site-packages (crea un namespace package que tapa el import). Solución: instalar mmpose **no-editable** (`pip install .\mmpose --no-build-isolation`) — crea `.mim` correcto.
4. **matplotlib ≥3.10 rompe el visualizador 3D** (`FigureCanvas... no attribute 'tostring_rgb'`, API eliminada). Solución: `matplotlib==3.9.4`.
5. **numpy**: se mantuvo en 1.26.4 todo el proceso (re-pin al final de cada tanda de installs, verificado).
6. **El README de rtmpose3d tiene rutas imprecisas**: el demo real es `demo\body3d_img2pose_demo.py` y el config del detector `demo\rtmdet_m_640-8xb32_coco-person.py` (verificado con listado recursivo). Checkpoints con las URLs de arriba.
7. **El demo hardcodea `VideoCapture(0)`**: sin flag de cámara. Solución: copia en `bridge\body3d_cam_demo.py` con `--cam-id` (usa `CAP_DSHOW`, abre mucho más rápido en Windows), `--max-frames` y contador FPS impreso cada segundo + promedio final.
8. **Esta máquina no es la del kiosco**: sin GTX 1660 ni cámara ELP (solo webcam integrada). CUDA False esperado. La validación GPU + ELP se hace en la PC de oficina con `setup_oficina.ps1`.
