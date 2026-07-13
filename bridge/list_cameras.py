"""Sondea indices de camara 0..5 con OpenCV y reporta cual abre y a que resolucion.

Uso (venv activado):  python bridge\\list_cameras.py

Para saber que indice es la ELP "Global Shutter Camera": correr esto, luego
comparar contra los nombres que da PowerShell:
  Get-CimInstance Win32_PnPEntity | ? { $_.PNPClass -in 'Camera','Image' } | Select Name
El orden de los indices DSHOW suele coincidir con el orden de esa lista.
"""
import cv2

for idx in range(6):
    cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
    ok, frame = cap.read()
    if ok:
        h, w = frame.shape[:2]
        print(f'indice {idx}: ABRE  {w}x{h}')
    else:
        print(f'indice {idx}: no disponible')
    cap.release()
