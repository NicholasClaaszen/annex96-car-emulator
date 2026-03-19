#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="annex96-ev-emulator"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${APP_DIR}/.venv"
REQ_FILE="${APP_DIR}/requirements.txt"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this installer as root (example: sudo bash scripts/install_pi.sh)"
  exit 1
fi

APP_USER="${SUDO_USER:-}"
if [[ -z "${APP_USER}" || "${APP_USER}" == "root" ]]; then
  APP_USER="pi"
fi

if ! id -u "${APP_USER}" >/dev/null 2>&1; then
  echo "User '${APP_USER}' does not exist. Re-run with SUDO_USER set to your Pi user."
  echo "Example: sudo SUDO_USER=openemulator bash scripts/install_pi.sh"
  exit 1
fi

if [[ ! -f "${REQ_FILE}" ]]; then
  echo "Missing requirements file at ${REQ_FILE}"
  exit 1
fi

CFG_FILE=""
for candidate in /boot/firmware/config.txt /boot/config.txt; do
  if [[ -f "${candidate}" ]]; then
    CFG_FILE="${candidate}"
    break
  fi
done

CMDLINE_FILE=""
for candidate in /boot/firmware/cmdline.txt /boot/cmdline.txt; do
  if [[ -f "${candidate}" ]]; then
    CMDLINE_FILE="${candidate}"
    break
  fi
done

if [[ -z "${CFG_FILE}" || -z "${CMDLINE_FILE}" ]]; then
  echo "Could not find /boot config/cmdline files."
  exit 1
fi

reboot_required=0

echo "[1/7] Installing OS packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
  python3 \
  python3-venv \
  python3-pip \
  python3-dev \
  build-essential \
  python3-rpi.gpio

echo "[2/7] Ensuring user groups for GPIO/UART..."
if ! id -nG "${APP_USER}" | grep -qw "gpio"; then
  usermod -aG gpio "${APP_USER}"
fi
if ! id -nG "${APP_USER}" | grep -qw "dialout"; then
  usermod -aG dialout "${APP_USER}"
fi

echo "[3/7] Enabling UART in ${CFG_FILE}..."
if grep -qE '^\s*enable_uart=' "${CFG_FILE}"; then
  if grep -qE '^\s*enable_uart=0\s*$' "${CFG_FILE}"; then
    sed -i -E 's/^\s*enable_uart=0\s*$/enable_uart=1/' "${CFG_FILE}"
    reboot_required=1
  fi
else
  printf "\n# Annex96 emulator\nenable_uart=1\n" >> "${CFG_FILE}"
  reboot_required=1
fi

echo "[4/7] Disabling Linux serial console in ${CMDLINE_FILE}..."
cmdline_before="$(cat "${CMDLINE_FILE}")"
cmdline_after="$(echo "${cmdline_before}" \
  | sed -E 's/\s*console=serial0,[0-9]+//g' \
  | sed -E 's/\s*console=ttyAMA0,[0-9]+//g' \
  | sed -E 's/\s+/ /g' \
  | sed -E 's/^ //; s/ $//')"
if [[ "${cmdline_after}" != "${cmdline_before}" ]]; then
  echo "${cmdline_after}" > "${CMDLINE_FILE}"
  reboot_required=1
fi

echo "[5/7] Creating/updating virtual environment..."
if [[ ! -d "${VENV_DIR}" ]]; then
  sudo -u "${APP_USER}" python3 -m venv "${VENV_DIR}"
fi

# Repair/seed pip in case the venv pip is broken (e.g. missing pip._vendor modules).
sudo -u "${APP_USER}" "${VENV_DIR}/bin/python" -m ensurepip --upgrade
if ! sudo -u "${APP_USER}" "${VENV_DIR}/bin/python" -m pip --version >/dev/null 2>&1; then
  echo "Detected broken pip in ${VENV_DIR}, recreating virtual environment..."
  rm -rf "${VENV_DIR}"
  sudo -u "${APP_USER}" python3 -m venv "${VENV_DIR}"
  sudo -u "${APP_USER}" "${VENV_DIR}/bin/python" -m ensurepip --upgrade
fi

sudo -u "${APP_USER}" "${VENV_DIR}/bin/python" -m pip install --upgrade --force-reinstall pip setuptools wheel
sudo -u "${APP_USER}" "${VENV_DIR}/bin/python" -m pip install -r "${REQ_FILE}"
sudo -u "${APP_USER}" "${VENV_DIR}/bin/python" -m pip install RPi.GPIO

echo "[6/7] Writing systemd service (${SERVICE_FILE})..."
cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=Annex96 EV Emulator
After=network.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_USER}
SupplementaryGroups=gpio dialout
WorkingDirectory=${APP_DIR}
ExecStart=${VENV_DIR}/bin/python -m daemon.main
Restart=on-failure
RestartSec=2
Environment=PLC_SERIAL_PORT=/dev/serial0
Environment=PLC_HTTP_PORT=8081
Environment=LOG_LEVEL=INFO

[Install]
WantedBy=multi-user.target
EOF

echo "[7/7] Enabling and starting service..."
systemctl daemon-reload
systemctl enable --now "${SERVICE_NAME}.service"
systemctl --no-pager status "${SERVICE_NAME}.service" || true

echo
echo "Install complete."
if [[ "${reboot_required}" -eq 1 ]]; then
  echo "A reboot is required for UART/console changes to fully apply."
  echo "Run: sudo reboot"
else
  echo "No reboot-required boot config changes were detected."
fi

echo "Useful commands:"
echo "  sudo journalctl -u ${SERVICE_NAME}.service -f"
echo "  sudo systemctl restart ${SERVICE_NAME}.service"
