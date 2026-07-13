"""Sondea indices de camara 0..5 con varios backends y formatos de OpenCV.

Uso (venv activado):  python bridge\\list_cameras.py

Prueba MSMF y DSHOW; si la camara conecta pero no transmite (tipico de ELP
por ancho de banda USB), reintenta pidiendo MJPG y 640x480.
IMPORTANTE: cerrar cualquier app que use la camara (app Camara, Teams, OBS,
navegador) antes de correr esto — si otra app la tiene abierta, no transmite.
"""
import cv2

BACKENDS = [('MSMF', cv2.CAP_MSMF), ('DSHOW', cv2.CAP_DSHOW)]


def probar(idx, backend):
    """Devuelve descripcion si logra leer un frame, si no None."""
    cap = cv2.VideoCapture(idx, backend)
    if not cap.isOpened():
        cap.release()
        return None
    ok, frame = cap.read()
    if ok:
        h, w = frame.shape[:2]
        cap.release()
        return f'{w}x{h} (formato default)'
    # conecta pero no transmite: reintentar con MJPG 640x480 (ancho de banda)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    ok, frame = cap.read()
    cap.release()
    if ok:
        h, w = frame.shape[:2]
        return f'{w}x{h} (requiere MJPG/640x480)'
    return None


for idx in range(6):
    resultados = []
    for nombre, backend in BACKENDS:
        r = probar(idx, backend)
        if r:
            resultados.append(f'{nombre} {r}')
    if resultados:
        print(f'indice {idx}: ABRE con ' + ' y '.join(resultados))
    else:
        print(f'indice {idx}: no disponible')
