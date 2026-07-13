"""Sondea indices de camara 0..5 con varios backends de OpenCV.

Uso (venv activado):  python bridge\\list_cameras.py

En algunas PCs DSHOW no puede abrir por indice; MSMF si. Este script prueba
ambos y reporta cual combinacion funciona. Para saber que indice es la ELP
"Global Shutter Camera", comparar contra los nombres que da PowerShell:
  Get-CimInstance Win32_PnPEntity | ? { $_.PNPClass -in 'Camera','Image' } | Select Name
"""
import cv2

BACKENDS = [('MSMF', cv2.CAP_MSMF), ('DSHOW', cv2.CAP_DSHOW)]

for idx in range(6):
    resultados = []
    for nombre, backend in BACKENDS:
        cap = cv2.VideoCapture(idx, backend)
        ok, frame = cap.read()
        if ok:
            h, w = frame.shape[:2]
            resultados.append(f'{nombre} {w}x{h}')
        cap.release()
    if resultados:
        print(f'indice {idx}: ABRE con ' + ' y '.join(resultados))
    else:
        print(f'indice {idx}: no disponible')
