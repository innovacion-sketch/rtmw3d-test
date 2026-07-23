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
# Resolucion de CAPTURA: a mas pixeles, keypoints mas finos (la ELP AR0234 es
# de ~2MP; a 640x480 se desperdiciaba). Alta resolucion por USB EXIGE MJPG.
# Si la camara no la soporta, abrir_camara() cae solo a 640x480.
CAM_WIDTH = 1600
CAM_HEIGHT = 1200
# Resolucion de SALIDA: video al navegador y espacio de coordenadas de los
# keypoints. Se infiere en alta y se reescala aqui -> precision de alta
# resolucion sin canvas gigantes ni ancho de banda de mas.
OUT_MAX_W = 960
WS_HOST = "localhost"
WS_PORT = 8765
DEVICE = "cuda:0"   # "cpu" para probar sin GPU
BBOX_THR = 0.5      # umbral del detector de personas
SEND_VIDEO = True   # enviar el frame JPEG en cada mensaje (campo "img").
                    # Necesario para el espejo web: la camara es exclusiva
                    # del server, el navegador no puede abrirla a la vez.
JPEG_QUALITY = 72
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

# Manos (para el control por gestos). Bloque de mano = 21 kpts:
# 0=muñeca, +9=nudillo medio (mmcp), tips: indice+8, medio+12, anular+16, meñique+20
# left_hand empieza en 91, right_hand en 112.
HANDS = {
    "left":  {"wrist": 91,  "mmcp": 100, "tips": [99, 103, 107, 111]},
    "right": {"wrist": 112, "mmcp": 121, "tips": [120, 124, 128, 132]},
}
HAND_THR = 0.3   # score minimo de la muñeca para tomar la mano como puntero

CLIENTS = set()


def _intentar(cap, wid, hei, mjpg):
    """Configura formato/resolucion y devuelve un frame si transmite."""
    if mjpg:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    if wid and hei:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, wid)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, hei)
    ok, frame = cap.read()
    return frame if ok else None


def abrir_camara():
    """Abre la camara probando MSMF -> DSHOW -> ANY.

    Intenta primero la resolucion alta en MJPG (necesaria para que quepa en
    el ancho de banda USB); si la camara no la entrega, baja a 640x480 y
    por ultimo al formato por default. Nunca deja el kiosco sin camara.
    """
    intentos = []
    if CAM_WIDTH and CAM_HEIGHT:
        intentos.append((CAM_WIDTH, CAM_HEIGHT, True))
    intentos.append((640, 480, True))
    intentos.append((0, 0, False))     # lo que de la camara por default

    for backend in (cv2.CAP_MSMF, cv2.CAP_DSHOW, cv2.CAP_ANY):
        cap = cv2.VideoCapture(CAM_ID, backend)
        if not cap.isOpened():
            cap.release()
            continue
        for (wid, hei, mjpg) in intentos:
            frame = _intentar(cap, wid, hei, mjpg)
            if frame is not None:
                rh, rw = frame.shape[:2]
                print(f"[camara] indice {CAM_ID} @ {rw}x{rh} "
                      f"({cap.getBackendName()})", flush=True)
                return cap
        cap.release()
    return None


def lado_json(kpts3d, kpts2d, scores, lado, esc=1.0):
    """esc = factor captura -> salida (se infiere en alta, se reporta en OUT)."""
    pts = {}
    sc = {}
    for nombre, idx in KP[lado].items():
        x, y = float(kpts2d[idx][0]) * esc, float(kpts2d[idx][1]) * esc
        z = float(kpts3d[idx][2])
        pts[nombre] = [round(x, 1), round(y, 1), round(z, 4)]
        sc[nombre] = round(float(scores[idx]), 3)
    pts["score"] = sc
    return pts


def mano_json(kpts2d, scores, esc=1.0):
    """Mano-puntero para el control por gestos, o None.

    Devuelve la mano mas levantada y con muñeca confiable:
      x, y  = base de la palma (nudillo medio) en pixeles -> posicion del cursor
      open  = apertura: dedos lejos de la muñeca -> mano abierta; cerca -> puño.
              Se normaliza por el tamaño de la mano, asi no depende de la
              distancia a la camara (abierta ~2.5, puño ~1.2).
      score = confianza de la muñeca.
    """
    mejor = None
    for lado, ix in HANDS.items():
        sc = float(scores[ix["wrist"]])
        if sc < HAND_THR:
            continue
        wx, wy = float(kpts2d[ix["wrist"]][0]), float(kpts2d[ix["wrist"]][1])
        mx, my = float(kpts2d[ix["mmcp"]][0]), float(kpts2d[ix["mmcp"]][1])
        hand_size = ((wx - mx) ** 2 + (wy - my) ** 2) ** 0.5 + 1e-6
        d = 0.0
        for tip in ix["tips"]:
            tx, ty = float(kpts2d[tip][0]), float(kpts2d[tip][1])
            d += ((tx - wx) ** 2 + (ty - wy) ** 2) ** 0.5
        openness = (d / len(ix["tips"])) / hand_size   # ratio: no depende de esc
        cand = {"lado": lado, "x": round(mx * esc, 1), "y": round(my * esc, 1),
                "open": round(openness, 2), "score": round(sc, 3), "_y": my}
        # la mano puntero = la mas levantada (menor y en pantalla)
        if mejor is None or cand["_y"] < mejor["_y"]:
            mejor = cand
    if mejor is not None:
        mejor.pop("_y")
    return mejor


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
        # Inferencia en la resolucion de captura (alta); coordenadas y video
        # se reportan reescalados a OUT_MAX_W.
        esc = OUT_MAX_W / w if (OUT_MAX_W and w > OUT_MAX_W) else 1.0
        ow, oh = int(round(w * esc)), int(round(h * esc))
        msg = {"t": int(time.time() * 1000), "w": ow, "h": oh,
               "fps": round(fps_actual, 1), "left": None, "right": None,
               "hand": None}

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
                msg["left"] = lado_json(kpts3d, kpts2d, scores, "left", esc)
                msg["right"] = lado_json(kpts3d, kpts2d, scores, "right", esc)
                msg["hand"] = mano_json(kpts2d, scores, esc)

        if SEND_VIDEO and CLIENTS:
            envio = frame if esc == 1.0 else cv2.resize(
                frame, (ow, oh), interpolation=cv2.INTER_AREA)
            ok_enc, jpg = cv2.imencode(
                ".jpg", envio, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
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
