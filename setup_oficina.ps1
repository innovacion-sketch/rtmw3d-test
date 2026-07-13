# setup_oficina.ps1 — Setup completo RTMW3D en PC nueva (Windows + NVIDIA)
# Uso:  clonar este repo en C:\proyectos\rtmw3d-test  y correr:
#   powershell -ExecutionPolicy Bypass -File .\setup_oficina.ps1
# Reanudable: si se corta la red, volver a correrlo — las descargas continúan donde quedaron.

$ErrorActionPreference = "Stop"
$ROOT = $PSScriptRoot
Set-Location $ROOT

function Retry-Curl($url, $out) {
    for ($i = 1; $i -le 100; $i++) {
        & curl.exe -L -C - --connect-timeout 30 -o $out $url
        if ($LASTEXITCODE -eq 0) { return }
        Write-Host "== corte de red, reintento $i para $out"
        Start-Sleep -Seconds 5
    }
    throw "No se pudo descargar $url"
}

# --- 1. venv con Python 3.10 ---
if (-not (Test-Path "$ROOT\.venv")) {
    Write-Host "== Creando venv (requiere Python 3.10 instalado)"
    & py -3.10 -m venv "$ROOT\.venv"
}
$PY = "$ROOT\.venv\Scripts\python.exe"
& $PY -m pip install --upgrade pip

# --- 2. torch 2.1.2+cu118 desde wheel local (descarga reanudable, pip NO reanuda) ---
# Si el venv ya tiene torch 2.1.2 (p. ej. setup previo en esta PC), no se re-descarga.
$torchOk = $false
& $PY -c "import torch; assert torch.__version__.startswith('2.1.2')" 2>$null
if ($LASTEXITCODE -eq 0) {
    $torchOk = $true
    Write-Host "== torch 2.1.2 ya presente en el venv, salto descarga de 2.6 GB"
}
if (-not $torchOk) {
    New-Item -ItemType Directory -Force "$ROOT\wheels" | Out-Null
    $TORCH_WHL = "$ROOT\wheels\torch-2.1.2+cu118-cp310-cp310-win_amd64.whl"
    $TV_WHL    = "$ROOT\wheels\torchvision-0.16.2+cu118-cp310-cp310-win_amd64.whl"
    if (-not (Test-Path $TORCH_WHL) -or (Get-Item $TORCH_WHL).Length -lt 2500MB) {
        Write-Host "== Descargando torch (2.6 GB, reanudable)"
        Retry-Curl "https://download.pytorch.org/whl/cu118/torch-2.1.2%2Bcu118-cp310-cp310-win_amd64.whl" $TORCH_WHL
    }
    if (-not (Test-Path $TV_WHL)) {
        Retry-Curl "https://download.pytorch.org/whl/cu118/torchvision-0.16.2%2Bcu118-cp310-cp310-win_amd64.whl" $TV_WHL
    }
    & $PY -m pip install $TORCH_WHL $TV_WHL
}
& $PY -m pip install "numpy==1.26.4" "wheel" "setuptools"

# --- 3. stack OpenMMLab (versiones clavadas a propósito, NO subir) ---
& $PY -m pip install mmengine "mmcv==2.1.0" -f https://download.openmmlab.com/mmcv/dist/cu118/torch2.1/index.html
& $PY -m pip install "mmdet>=3.1.0"

# --- 4. mmpose: clonar + chumpy + instalar NO-editable ---
# (-e rompe los configs "mmpose::" en Windows: no crea site-packages\mmpose\.mim)
if (-not (Test-Path "$ROOT\mmpose")) {
    Write-Host "== Clonando mmpose"
    & git clone --depth 1 https://github.com/open-mmlab/mmpose.git "$ROOT\mmpose"
}
& $PY -m pip install chumpy --no-build-isolation
& $PY -m pip install "$ROOT\mmpose" --no-build-isolation

# --- 5. re-pin final (algún paquete puede haber subido numpy) + extras ---
& $PY -m pip install "numpy==1.26.4" "opencv-python==4.10.0.84" "matplotlib==3.9.4" websockets

# --- 6. checkpoints (URLs del README de rtmpose3d, verificadas) ---
$CK = "$ROOT\mmpose\projects\rtmpose3d\checkpoints"
New-Item -ItemType Directory -Force $CK | Out-Null
if (-not (Test-Path "$CK\rtmdet_m_8xb32-100e_coco-obj365-person-235e8209.pth")) {
    Retry-Curl "https://download.openmmlab.com/mmpose/v1/projects/rtmpose/rtmdet_m_8xb32-100e_coco-obj365-person-235e8209.pth" "$CK\rtmdet_m_8xb32-100e_coco-obj365-person-235e8209.pth"
}
if (-not (Test-Path "$CK\rtmw3d-l_8xb64_cocktail14-384x288-794dbc78_20240626.pth")) {
    Retry-Curl "https://download.openmmlab.com/mmpose/v1/wholebody_3d_keypoint/rtmw3d/rtmw3d-l_8xb64_cocktail14-384x288-794dbc78_20240626.pth" "$CK\rtmw3d-l_8xb64_cocktail14-384x288-794dbc78_20240626.pth"
}

# --- 7. verificación final ---
Write-Host "`n== VERIFICACION (debe decir CUDA: True en la PC con GTX 1660) =="
& $PY -c "import numpy, torch, mmcv, mmdet, mmpose; print('numpy', numpy.__version__, '| torch', torch.__version__, '| CUDA:', torch.cuda.is_available()); print('mmcv', mmcv.__version__, '| mmdet', mmdet.__version__, '| mmpose', mmpose.__version__)"
Write-Host "`n== Listo. Siguiente paso: ver README.md seccion 'Prueba en GPU' =="
