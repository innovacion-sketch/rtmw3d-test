"""Puente RTMW3D -> WebSocket para el espejo web (Fase 2).

Captura la camara, corre detector + RTMW3D-L y publica los keypoints de
pies + tobillos por WebSocket en ws://localhost:8765 como JSON:

  {"t": <ms epoch>, "w": <ancho px>, "h": <alto px>, "fps": <fps inferencia>,
   "left":  {"ankle": [x,y,z], "toe": [x,y,z], "small_toe": [x,y,z], "heel": [x,y,z],
             "score": {"ankle": s, "toe": s, "small_toe": s, "heel": s}},
   "right": {...igual...}}

x,y en PIXELES de la imagen de camara (origen arriba-izquierda); z es la
profundidad relativa que entrega RTMW3D (unidades del modelo, menor = mas
cerca de la camara). "toe" = dedo gordo. Si no hay persona: left/right = null.

Uso (venv activado):   python bridge\\server.py
Detener: Ctrl+C
"""
import asyncio
import base64
import json
import sys
import threading
import time
from pathlib import Path

import cv2
import numpy as np

# ----------------- CONFIGURACION -----------------
CAM_ID = 0          # indice de camara (ver bridge/list_cameras.py)
CAM_WIDTH = 0       # 0 = dejar resolucion default de la camara
CAM_HEIGHT = 0
WS_HOST = "localhost"
WS_PORT = 8765
DEVICE = "cuda:0"   # "cpu" para probar sin GPU
BBOX_THR = 0.5      # umbral del detector de personas
SEND_VIDEO = True   # enviar el frame JPEG en cada mensaje (campo "img").
                    # Necesario para el espejo web: la camara es exclusiva
                    # del server, el navegador no puede abrirla a la vez.
JPEG_QUALITY = 70
# --------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
RTMPOSE3D_DIR = ROOT / "mmpose" / "projects" / "rtmpose3d"
sys.path.insert(0, str(RTMPOSE3D_DIR))

DET_CONFIG = str(RTMPOSE3D_DIR / "demo" / "rtmdet_m_640-8xb32_coco-person.py")
DET_CKPT = str(RTMPOSE3D_DIR / "checkpoints" /
               "rtmdet_m_8xb32-100e_coco-obj365-person-235e8209.pth")
POSE_CONFIG = str(RTMPOSE3D_DIR / "configs" /
                  "rtmw3d-l_8xb64_cocktail14-384x288.py")
POSE_CKPT = str(RTMPOSE3D_DIR / "checkpoints" /
                "rtmw3d-l_8xb64_cocktail14-384x288-794dbc78_20240626.pth")

# indices COCO-WholeBody (133 kpts)
KP = {
    "left":  {"ankle": 15, "toe": 17, "small_toe": 18, "heel": 19},
    "right": {"ankle": 16, "toe": 20, "small_toe": 21, "heel": 22},
}

CLIENTS = set()


def abrir_camara():
    """Abre la camara probando MSMF -> DSHOW -> ANY, con fallback MJPG."""
    for backend in (cv2.CAP_MSMF, cv2.CAP_DSHOW, cv2.CAP_ANY):
        cap = cv2.VideoCapture(CAM_ID, backend)
        if CAM_WIDTH and CAM_HEIGHT:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_HEIGHT)
        ok, _ = cap.read()
        if not ok and cap.isOpened():
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            ok, _ = cap.read()
        if ok:
            print(f"[camara] indice {CAM_ID} abierta con "
                  f"{cap.getBackendName()}", flush=True)
            return cap
        cap.release()
    return None


def lado_json(kpts3d, kpts2d, scores, lado):
    pts = {}
    sc = {}
    for nombre, idx in KP[lado].items():
        x, y = float(kpts2d[idx][0]), float(kpts2d[idx][1])
        z = float(kpts3d[idx][2])
        pts[nombre] = [round(x, 1), round(y, 1), round(z, 4)]
        sc[nombre] = round(float(scores[idx]), 3)
    pts["score"] = sc
    return pts


def inference_loop(loop):
    """Corre en un hilo: captura + inferencia + publicacion."""
    # imports pesados aqui para que el server arranque a imprimir de inmediato
    from mmdet.apis import inference_detector, init_detector
    from mmpose.apis import inference_topdown, init_model
    from mmpose.utils import adapt_mmdet_pipeline
    import rtmpose3d  # noqa: F401  (registra los modelos del proyecto)

    print("[modelos] cargando detector y RTMW3D-L ...", flush=True)
    detector = init_detector(DET_CONFIG, DET_CKPT, device=DEVICE)
    detector.cfg = adapt_mmdet_pipeline(detector.cfg)
    pose = init_model(POSE_CONFIG, POSE_CKPT, device=DEVICE)
    print("[modelos] listos", flush=True)

    cap = None
    fps_t0 = time.time()
    fps_n = 0
    fps_actual = 0.0

    while True:
        if cap is None:
            cap = abrir_camara()
            if cap is None:
                print("[camara] no disponible, reintento en 3s ...",
                      flush=True)
                time.sleep(3)
                continue

        ok, frame = cap.read()
        if not ok:
            print("[camara] se perdio la captura, reabriendo ...", flush=True)
            cap.release()
            cap = None
            continue

        h, w = frame.shape[:2]
        msg = {"t": int(time.time() * 1000), "w": w, "h": h,
               "fps": round(fps_actual, 1), "left": None, "right": None}

        det = inference_detector(detector, frame)
        pred = det.pred_instances.cpu().numpy()
        mask = np.logical_and(pred.labels == 0, pred.scores > BBOX_THR)
        bboxes = pred.bboxes[mask]
        if len(bboxes) > 0:
            # persona principal = bbox de mayor area (la mas cercana al espejo)
            areas = (bboxes[:, 2] - bboxes[:, 0]) * (bboxes[:, 3] - bboxes[:, 1])
            bbox = bboxes[np.argmax(areas)][None, :]
            results = inference_topdown(pose, frame, bbox)
            if results:
                inst = results[0].pred_instances
                kpts3d = inst.keypoints[0]          # (133,3) con z del modelo
                scores = inst.keypoint_scores
                if scores.ndim == 2:
                    scores = scores[0]
                # 2D en pixeles: transformed_keypoints si existe
                if hasattr(inst, "transformed_keypoints"):
                    kpts2d = inst.transformed_keypoints[0]
                else:
                    kpts2d = kpts3d[:, :2]
                msg["left"] = lado_json(kpts3d, kpts2d, scores, "left")
                msg["right"] = lado_json(kpts3d, kpts2d, scores, "right")

        if SEND_VIDEO and CLIENTS:
            ok_enc, jpg = cv2.imencode(
                ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            if ok_enc:
                msg["img"] = ("data:image/jpeg;base64," +
                              base64.b64encode(jpg).decode("ascii"))

        data = json.dumps(msg)
        loop.call_soon_threadsafe(publicar, data)

        fps_n += 1
        now = time.time()
        if now - fps_t0 >= 1.0:
            fps_actual = fps_n / (now - fps_t0)
            print(f"[FPS] {fps_actual:.2f} | clientes: {len(CLIENTS)}",
                  flush=True)
            fps_t0 = now
            fps_n = 0


def publicar(data):
    from websockets.asyncio.server import broadcast
    broadcast(CLIENTS, data)


async def handler(conn):
    CLIENTS.add(conn)
    print(f"[ws] cliente conectado ({len(CLIENTS)})", flush=True)
    try:
        async for _ in conn:   # se ignoran mensajes entrantes
            pass
    finally:
        CLIENTS.discard(conn)
        print(f"[ws] cliente desconectado ({len(CLIENTS)})", flush=True)


async def main():
    from websockets.asyncio.server import serve
    loop = asyncio.get_running_loop()
    threading.Thread(target=inference_loop, args=(loop,), daemon=True).start()
    async with serve(handler, WS_HOST, WS_PORT):
        print(f"[ws] sirviendo en ws://{WS_HOST}:{WS_PORT}", flush=True)
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[server] detenido")
