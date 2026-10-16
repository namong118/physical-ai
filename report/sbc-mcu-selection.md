# 별일없지 — SBC·MCU 부품 선정

> 문서 버전 v1.0 · 작성일 2026-10-16
> 관련 문서: [PRD](../PRD/PRD.md) · [Edge SBC 컨테이너 구조](edge-container-architecture.md) · [Edge 추론 엔진 선택](inference-engine-selection.md) · [하드웨어 부품 정리](hardware-parts.md)

> **현재 상태:** 문서 조사 기반 선정. Raspberry Pi 실측 전.
> 이 문서는 별일없지의 두뇌(SBC)와 센서 보드(MCU)를 왜 이 부품으로 골랐는지, 어떤 조건에서 바꾸는지를 정리합니다. 사양은 공식 문서에서 옮긴 값이며(7장 출처), 우리가 측정한 값이 아닙니다. 부품 구성은 [PRD](../PRD/PRD.md) 4장과 같고, 이 문서에서 바꾸지 않습니다.

---

## 요약

| 항목 | SBC (판단) | MCU (센서) |
|---|---|---|
| 선정 | **Raspberry Pi 5 (8GB)** (PRD 4장, 가정) | **ESP32-S3** — DevKitC-1 호환 보드, 모듈 ESP32-S3-WROOM-1-N16R8 (개발 레포 펌웨어 기준) |
| 맡는 일 | 리눅스 + Docker 컨테이너, 카메라 영상의 비전 AI(사람 검출·자세 추정), 상태 판단 | 현관·화장실 PIR·도어 센서를 상시 읽고 Wi-Fi로 Cloudflare Worker에 직접 보고, 10분 heartbeat |
| 고른 이유 | 리눅스·Docker, 8GB 메모리, Ultralytics 공식 Pi 가이드와 NCNN 경로, USB·CSI 카메라 입력 | Wi-Fi 내장으로 Pi 없이 서버 직결, 펌웨어·heartbeat를 실기기로 검증한 보드 |
| 전환 후보 | Pi 5 + AI HAT+ (검출), RK3588 보드 (pose 포함) — 5 FPS 미달 때 | ESP32-C3 — 대량 배치 때 / ESP32-H2·C6 — 전지 센서·Matter/Thread 때 |
| 남은 검증 | Pi 5에서 전체 FPS·메모리 실측 ([Edge 추론 엔진 선택](inference-engine-selection.md) 5장) | 도어 센서 펌웨어, 장기 안정성 ([하드웨어 부품 정리](hardware-parts.md) 5장) |

---

## 1. 역할 나누기

별일없지는 **판단하는 부품과 센서를 읽는 부품을 나눕니다.**

| | SBC — Raspberry Pi 5 | MCU — ESP32-S3 |
|---|---|---|
| 역할 | 판단 — 영상에서 사람·자세를 읽고 상태를 정함 | 센서 — 문 열림·움직임을 놓치지 않고 바로 보냄 |
| 실행 환경 | 리눅스 OS 위에 Docker 컨테이너 여러 개 ([Edge SBC 컨테이너 구조](edge-container-architecture.md)) | OS 없이 펌웨어 하나 |
| 켜질 때 | OS 부팅을 거친 뒤 컨테이너가 올라옴 | 전원을 넣으면 바로 펌웨어가 돎 (부팅 시간은 실측 전) |
| 맡는 공간 | 거실·주방(Edge #1), 침실(Edge #2) | 현관·화장실 (카메라 없음) |

### 1.1 Pi가 멈춰도 센서 신호는 간다

ESP32는 **Pi를 거치지 않고** Wi-Fi 2.4GHz + HTTPS(JSON)로 Cloudflare Worker에 직접 보고합니다([하드웨어 부품 정리](hardware-parts.md) 4장).

| 공간 | 경로 |
|---|---|
| 현관·화장실 | PIR·도어 센서 → ESP32-S3 → Wi-Fi·HTTPS → Cloudflare Worker → 가족 앱 |
| 거실·주방·침실 | 카메라 → Raspberry Pi 5 → Wi-Fi·HTTPS → Cloudflare Worker → 가족 앱 |

- Pi가 멈추거나 재부팅되어도 현관·화장실의 출입·움직임 신호는 계속 Worker로 갑니다.
- 반대로 ESP32가 멈춰도 Pi의 판단은 계속됩니다. 두 경로가 서로를 기다리지 않습니다.

### 1.2 멈춘 장치는 heartbeat로 알아챈다

- ESP32는 10분마다 heartbeat를 보내고, Worker는 heartbeat가 끊긴 기기를 **OFFLINE으로** 판정합니다(개발 레포 PoC, ESP32에서 검증 — [Edge SBC 컨테이너 구조](edge-container-architecture.md) 3장).
- Pi도 같은 방식으로 heartbeat를 보내도록 계획했습니다([Edge SBC 컨테이너 구조](edge-container-architecture.md) 3장). Pi 안에서 추론만 멈추면 "Edge 판단 불가"를 보내고, Pi 전체가 멈추면 heartbeat가 끊겨 OFFLINE이 됩니다.
- 그래서 어느 장치가 멈춰도 가족 앱에 "이상 없음"이 계속 보이지 않도록 설계합니다. Pi 쪽 동작은 검증 전입니다.

---

## 2. 선정 조건

### 2.1 판단 질문

부품은 아래 질문 순서로 고릅니다. 답이 바뀌면 고르는 부품도 바뀝니다(5장).

| 질문 | 별일없지의 답 | 결과 |
|---|---|---|
| ① 리눅스·Docker·비전 AI가 필요한가 | 거실·주방·침실은 필요, 현관·화장실은 불필요 | 카메라 공간은 SBC, 센서 공간은 MCU |
| ② 꺼지면 안 되는가, 빨리 켜져야 하는가 | 센서는 상시 동작해야 함 | 센서는 OS 없는 MCU에 맡김 |
| ③ 무선은 무엇인가 | 집 공유기 Wi-Fi로 서버 직결 (Thread 없음) | Wi-Fi 내장 칩 |
| ④ 전원은 무엇인가 | 모든 장치가 콘센트 어댑터 (전지 없음, [하드웨어 부품 정리](hardware-parts.md) 2장) | 저전력보다 연결 안정성 우선 |

### 2.2 역할별 조건

| 조건 | SBC 기준 | MCU 기준 |
|---|---|---|
| 리눅스·Docker | 필수 — 컨테이너 4개로 실패 격리 | 불필요 |
| 전원 | 5V USB-C 상시 전원, 27W 어댑터 [S1] | 5V USB 상시 전원 [S7] |
| AI 연산 | YOLO nano급 + 자세 추정을 ≥ 5 FPS (PRD 3장, 가정) | 불필요 (켜짐/꺼짐 신호만) |
| 실시간 | 분 단위 판단이라 엄격한 실시간 불필요 | 센서 신호를 놓치지 않을 것 |
| 무선 | Wi-Fi (이더넷 선택) | Wi-Fi 2.4GHz 내장, 서버 직결 |
| 카메라 | USB 웹캠(거실·주방) + CSI NoIR(침실) | 없음 |

---

## 3. SBC 비교

| 항목 | Raspberry Pi 5 (8GB) | Pi Zero 2 W | Jetson Orin Nano Super | RK3588 보드 | Pi 5 + AI HAT+ |
|---|---|---|---|---|---|
| 리눅스·Docker | ✓ 64비트 Arm 리눅스 [R1]. Docker 동작은 Pi 실측 전 | △ 리눅스는 되나 RAM 512MB라 컨테이너 4개는 빠듯함 (판단) [B1] | △ Jetson Linux [B2]. Docker는 확인 필요 | △ 칩이 Linux·Android 지원 [B3]. 보드별 OS·Docker는 확인 필요 | ✓ Pi 5와 같음 |
| 메모리 | ✓ 8GB (1–16GB 중 선택) [R1] | ✕ 512MB [B1] | ✓ 8GB [B2] | ✓ 보드별 (Orange Pi 5: 4·8·16GB [B5]) | ✓ Pi 5와 같음 |
| AI 연산 | △ NPU 없음, CPU(A76 4코어)만 [R1]. YOLO26n NCNN 공개 수치는 67 ms/장 [U1] — 전처리·후처리 제외, 실측 전 | ✕ A53 4코어 1GHz [B1] | ✓ GPU, 67 INT8 TOPS [B2] | ✓ NPU 6 TOPS [B3] | ✓ Hailo-8L 13 / Hailo-8 26 TOPS [R2]. 단 YOLO26-pose 미지원 [U8] |
| YOLO 경로 | ✓ Ultralytics 공식 Pi 가이드, NCNN 권장 [U1] | ✕ Ultralytics Pi 가이드 대상(Pi 3·4·5)이 아님 [U1] | 확인 필요 | △ RKNN 내보내기 — 검출·pose 지원, INT8은 검출만, 내보내기는 x86 Linux에서만 [U9] | △ Hailo 내보내기는 INT8 전용, 컴파일은 x86 Linux [U8] |
| 카메라 입력 | ✓ USB + CSI(22핀 mini) [S4] | △ CSI-2 커넥터 1개, USB는 micro USB OTG 1개 [B1] | 확인 필요 | △ 칩은 MIPI CSI-2 여러 개 지원 [B3]. 보드 커넥터는 확인 필요 | ✓ Pi 5와 같음 |
| 전원 | ✓ 5V 5A USB-C [S1] | ✓ micro USB 전원 [B1] | △ 7–25W 전력 모드 [B2] — 어댑터·발열 별도 검토 | △ 보드별 확인 필요 | △ HAT 전력 추가, 확인 필요 |
| 자료·생태계 | ✓ 보드·카메라·쿨러·AI HAT+를 같은 제조사 공식 문서로 확인 [R1][R2][S4] | △ | ✓ NVIDIA 공식 문서 | △ 보드 제조사마다 문서가 다름. Orange Pi 5는 RK3588S 칩 [B5] | ✓ Raspberry Pi 공식 문서 [R2] |
| 비용 | PRD 6.1: Edge 2대 360,000원 (가정) | 확인 필요 | 확인 필요 | 확인 필요 | 확인 필요 (Pi 5에 HAT 추가) |

### 3.1 Raspberry Pi 5를 고른 이유

1. **컨테이너 구조를 그대로 올릴 수 있습니다.** 리눅스·Docker가 되고 8GB 메모리가 있어 camera-capture·uplink-guardian·broker·ai-inference 4개를 한 장치에 둡니다([Edge SBC 컨테이너 구조](edge-container-architecture.md)).
2. **추론 경로가 공식 문서로 정리되어 있습니다.** Ultralytics가 Pi용 가이드와 엔진별 벤치마크를 내고 NCNN을 권장합니다 [U1]. 공개 수치(67 ms/장, 추론만)로는 5 FPS 목표에 여유가 있지만 실측 전입니다.
3. **카메라 두 종류를 바로 붙입니다.** 거실·주방 USB 웹캠과 침실 Camera Module 3 NoIR(CSI)을 같은 보드에서 씁니다 [S4].
4. **나중에 NPU를 더할 수 있습니다.** PCIe 2.0 x1 [R1]에 AI HAT+를 붙이는 길이 있어, 보드를 바꾸지 않고 가속을 검토할 수 있습니다(5장).

- **8GB를 고른 이유**는 컨테이너 4개와 후보 A의 엔진 2개(NCNN + MediaPipe 안의 TFLite)를 함께 돌릴 여유입니다. 측정한 값이 아니며, 4GB로 충분한지는 Pi 실측 후 판단합니다.
- **약점:** NPU가 없어 CPU 여유가 곧 목표 달성 여유입니다. Pi 5 실측에서 5 FPS를 넘는지가 이 선정의 전제입니다.

### 3.2 고르지 않은 이유

| 후보 | 이유 |
|---|---|
| Pi Zero 2 W | RAM 512MB, A53 1GHz로 컨테이너 4개와 비전 AI를 함께 돌리기 어렵습니다 [B1] |
| Jetson Orin Nano Super | 연산은 가장 크지만 별일없지는 가구당 Edge 2대가 필요하고, 다중 카메라 실시간 처리 수준의 연산은 요구하지 않습니다. 전력 모드 7–25W [B2]. 가격은 확인 필요 |
| RK3588 보드 | NPU가 있지만 보드 제조사마다 문서·OS가 달라 처음 구성 부담이 큽니다. pose 경로가 있어 전환 후보로 둡니다(5장) |
| Pi 5 + AI HAT+ | 지금은 CPU만으로 목표를 낼 수 있는지 먼저 확인합니다. 실측에서 부족하면 첫 번째 전환 후보입니다(5장) |

---

## 4. MCU 비교

| 항목 | ESP32-S3 | ESP32-C3 | ESP32-C6 | ESP32-H2 | nRF52840 | Pico W |
|---|---|---|---|---|---|---|
| Wi-Fi 서버 직결 | ✓ 802.11 b/g/n 2.4GHz [S6] | ✓ 802.11 b/g/n 2.4GHz [E2] | ✓ Wi-Fi 6, 2.4GHz [E3] | ✕ Wi-Fi 없음 [E4] | ✕ Wi-Fi 없음 [D1] | ✓ 2.4GHz 802.11n [P1] |
| Thread (802.15.4) | ✕ 없음 [S6] | ✕ 없음 [E2] | ✓ Thread 1.3·Zigbee 3.0 [E3] | ✓ Thread 1.4·Zigbee 3.0 [E4] | ✓ Thread·Zigbee [D1] | ✕ Wi-Fi·Bluetooth만 [P1] |
| CPU | ✓ Xtensa LX7 2코어 240MHz, AI·DSP용 SIMD 명령 [S6] | △ RISC-V 1코어 160MHz [E2] | △ RISC-V 160MHz + 저전력 코어 20MHz [E3] | △ RISC-V 1코어 96MHz [E4] | △ Cortex-M4F 64MHz [D1] | △ Cortex-M0+ 2코어 133MHz [P1] |
| 메모리 | ✓ 플래시 16MB + PSRAM 8MB (N16R8 모듈) [E1] | 확인 필요 | 확인 필요 | 확인 필요 | 플래시 1MB, RAM 256KB [D1] | SRAM 264KB [P1] |
| 실기기 검증 | ✓ PIR → GPIO4 → Wi-Fi → Worker, heartbeat 왕복 [F1] | ✕ | ✕ | ✕ | ✕ | ✕ |
| 기존 펌웨어 재사용 | ✓ 그대로 [F1] | △ 같은 Espressif 도구라 이식 쉬울 것 (판단, 확인 전) | △ 같음 | △ Wi-Fi 코드는 못 씀 | ✕ 개발 환경이 다름 (판단) | ✕ 개발 환경이 다름 (판단) |
| 비용 | PRD 6.1: ESP32 센서 4세트 40,000원 (가정) | 확인 필요 | 확인 필요 | 확인 필요 | 확인 필요 | 확인 필요 |

### 4.1 ESP32-S3를 고른 이유

1. **펌웨어를 실기기로 검증한 보드입니다.** HC-SR501 PIR → GPIO4 → Wi-Fi → Cloudflare Worker → 앱 반영과 heartbeat 왕복을 확인했습니다 [F1]. 이미 가진 보드라 새로 살 부품이 없습니다.
2. **Wi-Fi가 칩에 있어 Pi 없이 서버로 갑니다.** 1.1절의 "Pi가 멈춰도 센서 신호는 간다"가 이 덕분입니다.
3. **콘센트 전원이라 저전력 칩의 장점이 크지 않습니다.** 전지로 오래 버텨야 하는 상황이 아니므로 연결 안정성과 검증된 코드를 우선합니다.

- **약점:** PIR·도어 센서만 읽기에는 사양이 큰 편입니다. 가구 수가 많아지면 C3가 맞을 수 있습니다(5장).
- **보드 표기:** 개발 레포 펌웨어는 N16R8 보드를 기준으로 합니다 [F1]. 모듈 ESP32-S3-WROOM-1-N16R8의 사양(플래시 16MB, 옥탈 PSRAM 8MB)은 확인했지만 [E1], Espressif DevKitC-1 v1.1 사용자 가이드의 주문 목록에는 N16R8 품번이 없습니다 [S7]. 보드 품번은 확인 필요입니다.

---

## 5. 전환 조건

| 상황 | 대응 | 상태 |
|---|---|---|
| Pi 5 실측에서 전체 FPS가 5 미만 | 먼저 엔진·해상도·분석 빈도를 조정하고([Edge 추론 엔진 선택](inference-engine-selection.md) 3.5·3.6절), 그래도 부족하면 아래 NPU를 검토 | 실측 전 |
| └ 검출만 가속하면 되는 경우 | **Pi 5 + AI HAT+** — 보드를 그대로 두고 PCIe로 NPU 추가 [R2]. 단 Hailo 내보내기는 **YOLO26-pose를 지원하지 않음** [U8] | 검토 예정 |
| └ pose 모델까지 가속해야 하는 경우 (후보 B) | **RK3588 보드** — Ultralytics RKNN 내보내기가 YOLO26 pose를 지원. 단 INT8은 검출만, 내보내기는 x86 Linux에서만 [U9] | 검토 예정 |
| 가구 수가 늘어 센서 보드 단가가 중요해짐 | **ESP32-C3** — Wi-Fi·BLE 내장, 같은 Espressif 계열 [E2]. 펌웨어 이식과 실기기 검증 필요 | 검토 예정 |
| 전지 센서가 필요해짐, 또는 Matter/Thread로 바꿈 | **ESP32-H2·C6** — 802.15.4 내장 [E3][E4], Matter over Thread 기기로 사용 가능 [E5]. 집 쪽 보더 라우터는 아래 두 선택지 | 검토 예정 |
| └ 보더 라우터 선택지 1 | Pi에 OTBR·Matter 서버 컨테이너 + Thread 무선 동글 ([Edge SBC 컨테이너 구조](edge-container-architecture.md) 7장) | 검토 예정 |
| └ 보더 라우터 선택지 2 | **ESP32-S3 + ESP32-H2 보더 라우터 구성** (Espressif esp-thread-br) — S3가 Wi-Fi 호스트, H2가 802.15.4 무선(RCP). Pi와 따로 동작 [E6] | 검토 예정 |

- 어느 전환이든 PRD 6장 ROI의 장치 비용이 바뀝니다. 전환할 때 PRD를 함께 고칩니다.
- 보더 라우터 선택지 2는 Pi가 멈춰도 Thread 센서 경로가 살아 있다는 점에서 1.1절 원칙과 맞습니다. 다만 장치가 하나 늘어납니다(판단, 검토 전).

---

## 6. 확인하지 못한 항목

| 항목 | 상태 |
|---|---|
| Pi 5에서 컨테이너 4개 + 추론의 전체 FPS·메모리 | 실측 전 ([Edge 추론 엔진 선택](inference-engine-selection.md) 5장) |
| 8GB 대신 4GB로 충분한지 | 실측 전 |
| Pi 5·ESP32 부팅 시간 | 공식 수치 없음. 실측 전 |
| 보드 가격 (Pi 5 8GB, Pi Zero 2 W, Jetson Orin Nano Super, RK3588 보드, AI HAT+, ESP32 계열, nRF52840, Pico W) | 확인 필요. 비용 비교는 PRD 6.1 가정값(Edge 2대 360,000원, ESP32 센서 4세트 40,000원)만 씀 |
| Jetson Orin Nano Super 기본 전력 모드 | NVIDIA 문서마다 15W·25W로 다름. 확인 필요 |
| AI HAT+·RK3588 보드의 전력과 카메라 입력 | 보드별 확인 필요 |
| ESP32-S3 DevKitC-1 N16R8 보드 품번 | 공식 사용자 가이드 주문 목록에 없음. 확인 필요 |
| ESP32-C3·C6·H2 메모리 구성 | 이번에 확인하지 않음 |
| nRF52840의 Matter 지원 | 공식 페이지 비교표를 판단하지 못함. 확인 필요 |
| Pico W 무선 표기 | Raspberry Pi 문서 안에서 2.4GHz 802.11n과 듀얼밴드 802.11ac 표기가 섞여 있음. 제품 페이지 값(2.4GHz 802.11n)을 씀 |
| ESP32-C3로 펌웨어 이식 | 확인 전 |
| RKNN 경로의 pose FP16 속도, AI HAT+ 속도의 우리 구성 적용 | 실측 전 |

---

## 7. 출처

R·U는 [Edge 추론 엔진 선택](inference-engine-selection.md) 6장, S·F는 [하드웨어 부품 정리](hardware-parts.md)와 같은 기호입니다. 표시가 없는 것은 2026-10-16에 확인했습니다.

| 기호 | 문서 | 확인한 내용 |
|---|---|---|
| R1 | [Raspberry Pi 5 제품 페이지](https://www.raspberrypi.com/products/raspberry-pi-5/) | BCM2712 Cortex-A76 4코어 2.4GHz, NPU 언급 없음, RAM 1·2·4·8·16GB, PCIe 2.0 x1, 듀얼밴드 802.11ac Wi-Fi, Bluetooth 5.0 |
| R2 | [Raspberry Pi 공식 문서 — AI HAT+](https://www.raspberrypi.com/documentation/accessories/ai-hat-plus.html) | Hailo-8L 13 TOPS / Hailo-8 26 TOPS, Pi 5 PCIe 연결 (2026-10-15 확인) |
| U1 | [Ultralytics — Raspberry Pi 가이드](https://docs.ultralytics.com/guides/raspberry-pi/) | Pi 5 YOLO26n NCNN 67.03 ms/장(FP32, 640, 전처리·후처리 제외), NCNN 권장 (2026-10-15 확인). 비교 대상은 Pi 3·4·5, Zero 2 W는 언급 없음 (2026-10-16 확인) |
| U8 | [Ultralytics — Hailo 통합](https://docs.ultralytics.com/integrations/hailo/) | INT8 전용, 컴파일은 Linux x86_64, YOLO26-pose 미지원 (2026-10-15 확인) |
| U9 | [Ultralytics — Rockchip RKNN 통합](https://docs.ultralytics.com/integrations/rockchip-rknn/) | YOLOv8·YOLO11·YOLO26의 Detect·Segment·Classify·Pose·OBB 내보내기, INT8은 검출 모델만, 내보내기는 x86 Linux에서만 |
| B1 | [Raspberry Pi Zero 2 W 제품 페이지](https://www.raspberrypi.com/products/raspberry-pi-zero-2-w/) | RP3A0, Cortex-A53 4코어 1GHz, RAM 512MB, 2.4GHz 802.11 b/g/n, Bluetooth 4.2, CSI-2 커넥터, micro USB OTG, micro USB 전원 |
| B2 | [NVIDIA Jetson Orin Nano Super Developer Kit](https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/nano-super-developer-kit/) | 67 INT8 TOPS, 7–25W, 8GB LPDDR5, Cortex-A78AE 6코어, CUDA 코어 1024개, Jetson Linux 개발자 가이드 참조. Docker·카메라 커넥터·USB는 페이지에 없음 |
| B3 | [Rockchip RK3588](https://www.rock-chips.com/a/en/products/RK35_Series/2022/0926/1660.html) | Cortex-A76 4코어 + A55 4코어, NPU 6 TOPS, Android·Linux OS, MIPI CSI-2 여러 개 |
| B4 | [Radxa ROCK 5B](https://radxa.com/products/rock5/5b/) | A76 4코어 + A55 4코어, NPU 최대 6 TOPS. Ultralytics RKNN 테스트 기기 [U9] |
| B5 | [Orange Pi 5](http://www.orangepi.org/html/hardWare/computerAndMicrocontrollers/details/Orange-Pi-5.html) | **RK3588S** 칩, NPU 6 TOPS, RAM 4·8·16GB |
| S1 | [Raspberry Pi 공식 문서 — Power supply](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#power-supply) | Pi 5 권장 전원 5.0A |
| S4 | [Raspberry Pi 공식 문서 — Camera](https://www.raspberrypi.com/documentation/accessories/camera.html) | Pi 5는 22핀 mini 카메라 커넥터 |
| S6 | [ESP32-S3 Series Datasheet v2.2](https://documentation.espressif.com/esp32-s3_datasheet_en.pdf) | Xtensa LX7 2코어 최대 240MHz, 802.11 b/g/n 2.4GHz, Bluetooth 5 (LE), 무선 기능은 Wi-Fi·BLE뿐(802.15.4 없음), AI·DSP용 SIMD 명령(PIE) |
| S7 | [ESP32-S3-DevKitC-1 사용자 가이드 v1.1](https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/user_guide_v1.1.html) | USB 포트 전원, 주문 목록(N8R8, N32R16V 등)에 N16R8 없음 |
| E1 | [ESP32-S3-WROOM-1/1U Datasheet v1.8](https://documentation.espressif.com/esp32-s3-wroom-1_wroom-1u_datasheet_en.pdf) | N16R8: 플래시 16MB(Quad SPI), PSRAM 8MB(Octal SPI) |
| E2 | [ESP32-C3 Series Datasheet v2.4](https://documentation.espressif.com/esp32-c3_datasheet_en.pdf) | RISC-V 1코어 최대 160MHz, 802.11 b/g/n 2.4GHz, Bluetooth 5 (LE) |
| E3 | [ESP32-C6 Series Datasheet v1.5](https://documentation.espressif.com/esp32-c6_datasheet_en.pdf) | RISC-V 고성능 코어 160MHz + 저전력 코어 20MHz, Wi-Fi 6 2.4GHz, Bluetooth 5.3, 802.15.4(Thread 1.3, Zigbee 3.0) |
| E4 | [ESP32-H2 Series Datasheet v1.3](https://documentation.espressif.com/esp32-h2_datasheet_en.pdf) | RISC-V 1코어 최대 96MHz, Bluetooth 5.3, 802.15.4(Thread 1.4, Zigbee 3.0), Wi-Fi 없음 |
| E5 | [Espressif esp-matter 소개](https://docs.espressif.com/projects/esp-matter/en/latest/esp32/introduction.html) | 802.15.4가 있는 ESP32-H 계열·C5·C6로 Matter Thread 기기, ESP32·C·S 계열로 Matter Wi-Fi 기기 |
| E6 | [Espressif esp-thread-br 하드웨어 플랫폼](https://docs.espressif.com/projects/esp-thread-br/en/latest/hardware_platforms.html) | 보더 라우터 = Wi-Fi 호스트 ESP32-S3 + 802.15.4 RCP ESP32-H2(또는 C6) |
| D1 | [Nordic nRF52840](https://www.nordicsemi.com/Products/nRF52840) | Cortex-M4F 64MHz, 플래시 1MB·RAM 256KB, Bluetooth LE·802.15.4·Thread·Zigbee, Wi-Fi 언급 없음 |
| P1 | [Raspberry Pi Pico 제품 페이지](https://www.raspberrypi.com/products/raspberry-pi-pico/) | Pico W: RP2040 Cortex-M0+ 2코어 133MHz, SRAM 264KB, 2.4GHz 802.11n, Bluetooth 5.2 |
| F1 | [Byeolileopji `firmware/esp32-pir`](https://github.com/namong118/Byeolileopji/tree/main/firmware/esp32-pir) | N16R8 보드 기준 핀 정리, PIR → GPIO4, 10분 heartbeat, 실기기 검증 범위 |
