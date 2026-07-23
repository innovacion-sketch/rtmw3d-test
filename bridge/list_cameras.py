"""Sondea camaras y las resoluciones que soportan de verdad.

Uso (venv activado):  python bridge\\list_cameras.py

Prueba MSMF y DSHOW en los indices 0..5. Para el primer indice que abra,
sondea una lista de resoluciones en MJPG y reporta la que ENTREGA (no la
que acepta: MSMF suele aceptar el set() y devolver otra distinta).

IMPORTANTE: cerrar cualquier app que use la camara (app Camara, Teams, OBS,
navegador con el espejo) y detener bridge\\server.py antes de correr esto.
"""
import cv2

BACKENDS = [('MSMF', cv2.CAP_MSMF), ('DSHOW', cv2.CAP_DSHOW)]
RESOLUCIONES = [(1920, 1200), (1920, 1080), (1600, 1200),
                (1280, 960), (1280, 720), (800, 600), (640, 480)]


def abre(idx, backend):
    """Devuelve (cap, w, h) si logra leer un frame, si no (None, 0, 0)."""
    cap = cv2.VideoCapture(idx, backend)
    if not cap.isOpened():
        cap.release()
        return None, 0, 0
    ok, frame = cap.read()
    if not ok:
        # conecta pero no transmite: reintentar en MJPG 640x480
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        ok, frame = cap.read()
    if not ok:
        cap.release()
        return None, 0, 0
    h, w = frame.shape[:2]
    return cap, w, h


def sondear_resoluciones(cap):
    print('    resoluciones (pedida -> entregada, en MJPG):')
    vistas = set()
    for (wid, hei) in RESOLUCIONES:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, wid)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, hei)
        ok, frame = cap.read()
        if not ok:
            print(f'      {wid}x{hei} -> no transmite')
            continue
        h, w = frame.shape[:2]
        marca = ' <-- EXACTA' if (w == wid and h == hei) else ''
        print(f'      {wid}x{hei} -> {w}x{h}{marca}')
        vistas.add((w, h))
    if vistas:
        mejor = max(vistas, key=lambda r: r[0] * r[1])
        print(f'    MEJOR REAL: {mejor[0]}x{mejor[1]}')


encontrada = False
for idx in range(6):
    for nombre, backend in BACKENDS:
        cap, w, h = abre(idx, backend)
        if cap is None:
            continue
        print(f'indice {idx}: ABRE con {nombre} (default {w}x{h})')
        if not encontrada:
            sondear_resoluciones(cap)
            encontrada = True
        cap.release()
        break
    else:
        print(f'indice {idx}: no disponible')
