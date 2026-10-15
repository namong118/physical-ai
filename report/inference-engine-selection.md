# 별일없지 — Edge 추론 엔진 선택

> 문서 버전 v1.0 · 작성일 2026-10-15
> 관련 문서: [PRD](../PRD/PRD.md) · [모델·학습·검증 계획](model-training-validation.md) · [하드웨어 부품 정리](hardware-parts.md)

> **현재 상태:** 문서 조사 기반 선택. Raspberry Pi 실측 전.
> Raspberry Pi가 없어 이번에는 측정하지 않았습니다. 이 문서의 속도 수치는 모두 **출처 기준 공개 자료의 값**이며, 우리가 측정한 값이 아닙니다. 출처는 2026-10-15에 확인했습니다.

---

## 요약

| 항목 | 내용 |
|---|---|
| 선택 | **NCNN** (YOLO 추론 엔진) |
| 2순위 | **ONNX Runtime** — 전환 후보이자 실측 비교 기준 |
| 탈락 | OpenVINO, LiteRT (TFLite) |
| 실행 경로 | 첫 실측은 Ultralytics 경로, 무거움이 확인되면 ncnn 직접 경로로 전환 |
| 근거 | 공식 문서·공개 벤치마크 조사 (6장 출처) |
| 남은 검증 | Raspberry Pi 5에서 같은 모델로 엔진별 FPS 비교 (5장) |

> **모델과 추론 엔진은 별개의 결정입니다.** 어떤 모델(YOLO26n, YOLO26n-pose, MediaPipe Pose)을 쓸지는 [모델·학습·검증 계획](model-training-validation.md) 2.2절에서 정확도와 속도로 정합니다. 이 문서는 고른 모델을 Pi에서 **무엇으로 실행할지**만 다룹니다. 같은 `.pt` 모델을 여러 엔진 형식으로 내보낼 수 있어서 두 결정은 따로 바꿀 수 있습니다. 단 MediaPipe Pose는 실행 엔진이 정해져 있습니다(4장).

---

## 1. 선택 조건

별일없지의 Edge 장치는 **Raspberry Pi 5 (8GB)** 입니다(PRD 4장, 가정). Pi 5의 CPU는 **Arm Cortex-A76 4코어 2.4GHz**이고, 제품 페이지에 NPU(AI 가속기)는 없습니다 [R1]. 그래서 엔진은 **ARM CPU만으로** 목표 속도를 내야 합니다.

| 조건 | 기준 | 근거 |
|---|---|---|
| 처리 속도 | **≥ 5 FPS** (Raspberry Pi 5 기준, 가정) | PRD 3장 성공 지표 |
| 실행 장치 | ARM64 Linux, CPU 전용 | Pi 5 사양 [R1] |
| 설치 | Pi에서 pip 휠로 설치 가능 | 개인 PoC 규모, 빌드 부담 최소화 |
| 모델 호환 | Ultralytics YOLO(검출·pose)를 내보내 그대로 실행 | 모델 계획 문서 2장 |
| Python | Python API로 기존 파이프라인 코드와 연결 | 파이프라인 코드가 Python |
| 라이선스 | 런타임 자체가 상용 사용에 제약이 적을 것 | 공개 레포·상용 확장 고려 |

> **라이선스는 별도 과제입니다.** AGPL-3.0은 엔진이 아니라 YOLO 모델·가중치에 적용되므로(Ultralytics 라이선스 페이지 [U4]), 엔진 선택(NCNN / ONNX Runtime)과 무관하게 상용 시 기업 라이선스 여부를 따로 정해야 합니다.

---

## 2. 4종 비교표

| 항목 | ONNX Runtime | NCNN | OpenVINO | LiteRT (TFLite) |
|---|---|---|---|---|
| Pi 5 설치 (pip 휠) | `pip install onnxruntime` — 1.31.0, Linux aarch64 휠 (CPython 3.11–3.14) [O1] | `pip install ncnn` — 1.0.20260526, Linux aarch64 휠 (CPython 3.8–3.14) [N1] | `pip install openvino` — 2026.4.1, Linux aarch64 휠 (CPython 3.10–3.14). **glibc 2.35 이상** 필요 [V1] | `pip install ai-edge-litert` — 2.3.0, Linux aarch64 휠 (CPython 3.10–3.14) [L1]. 기존 `tflite-runtime`은 앞으로 기능 업데이트 없음 [L3] |
| ARM CPU 가속 | 기본 CPU 실행기의 수학 라이브러리(MLAS)에 Arm KleidiAI 커널 통합 [O3]. pip 휠에서 기본 사용 여부는 확인 필요. XNNPACK·ACL은 별도 빌드, ACL은 preview [O4] | ARM NEON 최적화, 멀티코어 스케줄링 [N2] | Arm Compute Library·oneDNN 사용. Arm에서는 기능·최적화가 x86과 다를 수 있음 [V2] | 기본 CPU 커널이 ARM Neon에 최적화 [L4]. XNNPACK 기본 사용 여부는 확인 필요 |
| YOLO 내보내기 | `format=onnx` [U2] | `format=ncnn`, Detect·Pose 지원 명시 [U3] | `format=openvino` [U2] | `format=litert` [U2]. **Pi에서는 내보내기 불가** — x86이나 macOS에서 변환 후 복사 [U1] |
| MediaPipe와의 관계 | 없음 | 없음 | 없음 | MediaPipe가 내부에서 TFLite 모델을 실행 [M2] (mediapipe 휠에 포함 [M1]) |
| INT8 양자화 | Ultralytics `quantize=8` 지원(정적 양자화, 보정 데이터 필요) [U2]. Arm dot-product 명령이 있으면 유리 [O2] | Ultralytics 내보내기는 **FP32·FP16만** [U2]. ncnn 자체는 INT8 추론·양자화 도구 제공 [N2] — 우리 모델 적용은 확인 필요 | Ultralytics `quantize=8` 지원(NNCF) [U2]. 단 **Arm은 INT8 정밀도 목록에 없고 양자화 모델을 시뮬레이션 모드로 실행** [V2] | Ultralytics `quantize=8` 지원 [U2] |
| Python API | 표준 API | Ultralytics `YOLO("…_ncnn_model")`로 실행 [U3], 또는 ncnn Python 바인딩 [N2] | 표준 API | `ai_edge_litert.interpreter` — 기존 tflite와 패키지 이름만 다름 [L3] |
| 라이선스 | MIT [O1] | BSD-3 [N1] | Apache-2.0 [V1] | Apache-2.0 [L1] |
| 비Intel ARM 지원 | — | — | 지원하나 x86과 기능 차이, INT8 시뮬레이션, Windows ARM64 미지원 [V2]. 예전 Arm 플러그인 문서의 "Intel 정식 검증 없음" 문구는 현재 문서에서 확인 필요 | — |
| Pi 5 공개 속도 (출처 기준) | 125.99 ms/장 (약 7.9 FPS) [U1] | **67.03 ms/장 (약 14.9 FPS)** [U1] | 104.55 ms/장 (약 9.6 FPS) [U1] | 123.30 ms/장 (약 8.1 FPS) [U1] |

### 2.1 공개 벤치마크의 조건과 한계

마지막 행의 속도는 Ultralytics 공식 Raspberry Pi 가이드의 표입니다 [U1]. **우리가 측정한 값이 아닙니다.**

| 항목 | 내용 |
|---|---|
| 모델 | YOLO26n (검출). 같은 표의 YOLO26s도 순서가 같음 — NCNN 172.88 / OpenVINO 281.78 / ONNX 355.69 / LiteRT 360.00 ms |
| 조건 | Raspberry Pi 5, FP32, 입력 640, Ultralytics 8.4.108 |
| FPS | 표의 ms 값을 1000으로 나눠 이 문서에서 환산한 값 |
| 정확도 | 표의 mAP50-95는 네 엔진이 0.4730–0.4784로 거의 같음 |
| 데이터셋 | 표에 명시 없음. 재현 명령 예시는 `coco128.yaml` — 확인 필요 |
| 가이드 결론 | "NCNN delivers the best inference performance on Raspberry Pi devices" |

이 수치에는 다음 한계가 있습니다.

- **Ultralytics 래퍼로 잰 추론 시간만**입니다. 전처리·후처리 시간은 빠져 있습니다 [U1]. 카메라 입력부터 판정까지의 실제 FPS는 이보다 낮습니다.
- **YOLO 1개만** 잰 값입니다. 후보 A의 MediaPipe Pose, 후보 B의 pose 모델(`yolo26n-pose`)은 Pi 5 공개 수치를 찾지 못했습니다.
- **ONNX Runtime은 기본 설정**이고, 버전은 Ultralytics 8.4.108 시점 기준입니다. ONNX Runtime에 최근 들어간 Arm 최적화(KleidiAI의 MLAS 통합 [O3])가 반영되면 차이가 줄 수 있습니다.
- 오버클럭·냉각 조건은 표에 명시가 없습니다.
- 그래서 **5장 검증 계획의 Pi 실측으로 다시 확인합니다.**

---

## 3. 선택과 이유

### 3.1 선택: NCNN

1. **5 FPS 목표의 여유가 가장 큽니다.** 공개 벤치마크 기준으로 4종 중 가장 빠르고(67 ms, ONNX Runtime 126 ms), 정확도는 거의 같습니다 [U1]. Pi 5에는 NPU가 없어 CPU 효율이 곧 목표 달성 여유입니다. 모델 2개를 돌리는 후보 A에서 이 여유가 특히 중요합니다.
2. **Ultralytics가 Pi용으로 권장합니다** [U1]. Detect·Pose 내보내기를 모두 지원합니다 [U3].
3. **설치와 라이선스 부담이 적습니다.** aarch64 pip 휠이 있고 BSD-3입니다 [N1].

**약점**
- Ultralytics 내보내기로는 INT8을 쓸 수 없습니다(FP32·FP16만) [U2].
- ncnn을 직접 쓰면 전처리·후처리를 직접 작성해야 합니다(3.4).

### 3.2 2순위: ONNX Runtime

ONNX Runtime은 탈락이 아니라 **전환 후보이자 실측 비교 기준**입니다.
- MIT 라이선스입니다 [O1].
- 노트북 실습 환경에 이미 설치해 써 봤습니다(onnxruntime 1.31.0, [비전 모델 실습 보고서](vision-models-practice.md)).
- Ultralytics INT8 내보내기를 지원합니다 [U2].
- FP32 공개 벤치마크로는 NCNN보다 느립니다 [U1].

### 3.3 탈락 이유

| 엔진 | 탈락 이유 |
|---|---|
| OpenVINO | Arm에서는 INT8을 실제로 쓰지 못하고 시뮬레이션 모드로 실행합니다. Arm에서는 기능·최적화가 x86과 다를 수 있습니다 [V2]. 공개 벤치마크 2위(104.55 ms)지만 NCNN과 차이가 큽니다 [U1] |
| LiteRT (TFLite) | Pi에서 YOLO를 내보낼 수 없습니다 [U1]. 공개 벤치마크로 ONNX Runtime과 비슷합니다(123.30 ms) [U1]. MediaPipe가 내부에서 TFLite를 쓰지만, YOLO와 런타임을 공유해 이득이 있다는 근거는 찾지 못했습니다 |

### 3.4 실행 경로: Ultralytics 경로 → ncnn 직접 경로

| | Ultralytics 경로 | ncnn 직접 경로 |
|---|---|---|
| 실행 | `YOLO("yolo26n_ncnn_model")` [U3] | `ncnn` Python 바인딩 [N2] |
| Pi 의존성 | 무거움 — `ultralytics` 필수 의존성에 `torch`·`torchvision` 포함, torch 없이 설치하는 방법은 문서에 없음 [U5][U6] | 가벼움 — ncnn과 영상 처리 라이브러리 정도 |
| 코드 작성량 | 전처리·후처리를 Ultralytics가 처리 | 전처리·후처리 직접 작성. YOLO26은 NMS 없는 end-to-end 출력 `(N, 300, 6)`을 지원해 후처리가 짧음 [U7]. pose 출력 처리는 확인 필요 |
| 라이선스 | 패키지·모델 모두 AGPL-3.0 [U4][U5] | 런타임은 BSD-3, **YOLO 모델·가중치는 여전히 AGPL-3.0** [U4] |
| 사용 시점 | **첫 실측** — 빠르게 동작을 확인 | Ultralytics 경로가 무겁다고 확인되면 전환 (메모리, 시작 시간, 설치 크기) |

### 3.5 전환 조건

| 상황 | 대응 |
|---|---|
| Pi 실측에서 NCNN 구성이 5 FPS 미달 | ONNX Runtime(FP32·INT8)을 같은 조건으로 비교해 더 나은 쪽으로 전환. 둘 다 미달이면 3.6절(CPU가 부족할 때) 검토 |
| 변환 모델이 원본(`.pt`)과 다른 결과를 냄 | **parity check**: 같은 프레임에서 원본과 변환 모델의 검출 박스·관절 좌표 차이와 자세 판정 일치를 비교. NCNN 변환 모델의 정확도가 떨어지면 NCNN으로 바꾸지 않고 **ONNX Runtime 유지**. 허용 차이 기준은 검증 전에 정함(미정) |
| Pi 설치·통합 문제(휠 호환, 모델 변환 오류 등) | ONNX Runtime으로 전환 |
| Ultralytics 경로의 메모리·시작 시간이 과함 | 엔진은 그대로 두고 ncnn 직접 경로로 전환 |

### 3.6 CPU가 부족할 때

엔진을 바꿔도 5 FPS에 못 미치면 아래를 검토합니다. 모두 **검토 예정**이며, 효과는 실측 전입니다.

| 방법 | 내용 | 주의 |
|---|---|---|
| 입력 해상도 축소 | 내보내기·추론 입력 크기(`imgsz`)를 640보다 줄임 | 화면에 작게 잡히는 사람의 검출·관절 정확도가 떨어질 수 있음. parity check와 정확도 비교를 함께 함 |
| 분석 빈도 조절 | 카메라 30fps 중 처리할 프레임 수를 조절 ([Vision 전처리·후처리 설계](vision-preprocessing-design.md) 2번 프레임 샘플링, 판단 단위는 분 단위) | 5 FPS 미만으로 내리면 PRD 3장 목표(≥ 5 FPS) 자체를 바꾸는 것이라 PRD 수정이 필요함 |
| 경량 모델 | 이미 nano급(YOLO26n)이므로 더 작은 모델보다는 모델 수를 줄이는 쪽 — 후보 B(pose 단독)로 MediaPipe 단계를 없앰 | 작게 찍힌 사람의 관절 정확도 비교 필요 (모델 계획 문서 2.2절) |
| NPU 확장 | Raspberry Pi AI HAT 계열 추가 (아래) | 부품 추가 비용, 모델 지원 범위 확인 필요 |

**NPU 확장 — 공식 출처로 확인한 내용**

| 항목 | 내용 | 출처 |
|---|---|---|
| AI HAT+ | Hailo-8L 13 TOPS / Hailo-8 26 TOPS 두 종류, Raspberry Pi 5 전용, PCIe 포트로 연결 | R2 |
| AI HAT+ 2 | Hailo-10H, 40 TOPS(INT4), 보드 RAM 8GB, $200. 주 용도는 LLM·VLM이고, 비전 성능은 AI HAT+(26 TOPS)와 비슷하다고 적혀 있음 | R3 |
| YOLO 내보내기 | Ultralytics `format=hailo` — INT8 전용, 컴파일은 **Linux x86_64**와 Hailo Dataflow Compiler 필요(추론은 장치의 HailoRT) | U8 |
| 지원 작업 | 검출 지원. pose는 YOLOv8·YOLO11만 지원하고 **YOLO26-pose는 현재 미지원** | U8 |
| 공개 속도 (출처 기준) | YOLO26n 검출, Pi 5 + AI HAT+ (Hailo-8): 21.7 ms/장, mAP50-95 0.455 (COCO128, 전처리·후처리 제외) | U8 |

- 위 속도는 우리가 측정한 값이 아니며, CPU 엔진 표(2장)와 정확도 조건이 같지 않습니다.
- 후보 A의 MediaPipe Pose는 NPU로 옮겨지지 않고 CPU에서 그대로 돕니다. NPU 경로와 MediaPipe의 관계는 확인 필요입니다.
- AI HAT+(13·26 TOPS) 가격은 이번에 공식 페이지에서 확인하지 못했습니다(확인 필요). 도입하면 PRD 6장 ROI의 장치 비용이 바뀝니다.

---

## 4. 모델 구성과의 관계

후보 A·B는 [모델·학습·검증 계획](model-training-validation.md) 2.2절의 비교 후보입니다.

| 구성 | 필요한 엔진 | 참고 |
|---|---|---|
| **A** YOLO26n → crop → MediaPipe Pose | **엔진 2개**가 함께 돎: YOLO용 NCNN과 MediaPipe 안의 TFLite [M2] | MediaPipe 쪽 엔진은 우리가 고를 수 없음. 두 엔진이 CPU 4코어를 나눠 써서 스레드 설정이 FPS에 영향을 줄 수 있음(실측 전) |
| **B** YOLO26n-pose 단독 | **엔진 1개** (NCNN) | pose 모델의 Pi 5 공개 수치는 없음 — 실측 필요 |

어느 구성이든 **YOLO 엔진 선택(NCNN)은 그대로**입니다. A·B 선택은 Pi 실측(구성 × 엔진)으로 정합니다.

---

## 5. 검증 계획

### 5.1 개발 단계 전략

| 단계 | 장소 | 할 일 |
|---|---|---|
| 1 | 지금 PC (Windows x86) | Ultralytics로 `.pt` 모델(`yolo26n`, `yolo26n-pose`)을 써서 파이프라인을 개발하고, 모델 선택(정확도)을 검증. 엔진 속도는 여기서 비교하지 않음 |
| 2 | Raspberry Pi 5 확보 후 | **같은 `.pt`에서 내보낸** NCNN과 ONNX Runtime 모델로 parity check와 FPS 비교 (5.2) |
| 3 | 결과 정리 | 3.5절 전환 조건에 따라 엔진을 확정하고 이 문서·PRD·홈페이지를 갱신 |

**PC(Windows)에서 NCNN을 쓸 수 있는지 (공식 문서 기준)**

| 항목 | 확인 결과 | 출처 |
|---|---|---|
| ncnn Python 휠 | Windows x86_64(`win_amd64`) 휠 있음 — CPython 3.8–3.14 (실습 환경 Python 3.14 포함) | N1 |
| Ultralytics NCNN 통합 문서 | NCNN 배포 대상으로 "Linux, Windows, macOS에서 개발·학습·평가"를 언급 | U3 |
| Windows에서 Ultralytics `format=ncnn` 내보내기·`YOLO("…_ncnn_model")` 실행 | 이를 직접 명시한 문장은 찾지 못함 — **확인 필요** | — |

- Windows에서 NCNN이 동작하더라도 PC 속도는 엔진 선택 근거로 쓰지 않습니다(아래 원칙).
- PC에서 parity check를 미리 해 볼 수는 있지만, ARM에서 같은 결과가 나온다는 보장은 없어 Pi에서 다시 확인합니다.

### 5.2 Raspberry Pi 검증

> **x86 노트북 결과는 Raspberry Pi 결과를 대신할 수 없습니다.** 엔진별 상대 속도는 CPU 구조(x86과 ARM)에 따라 달라지므로, 엔진 비교는 Pi 5에서만 판단합니다. 노트북은 코드 동작 확인용으로만 씁니다.

| 항목 | 내용 |
|---|---|
| 장치 | Raspberry Pi 5 (8GB), Active Cooler 장착, 기본 클럭(오버클럭 안 함) |
| 모델 | 같은 가중치에서 내보낸 `yolo26n`, `yolo26n-pose` — NCNN(FP32), ONNX Runtime(FP32, INT8) |
| 구성 | 후보 A(NCNN YOLO + MediaPipe Pose), 후보 B(NCNN pose 단독), 비교용 ONNX Runtime 같은 구성 |
| 입력 | 직접 촬영한 시나리오 영상, 입력 크기 고정 |
| 측정 값 | ① 추론만의 시간 ② **전처리·후처리를 포함한 전체 FPS** ③ CPU 온도·스로틀링 여부 ④ 메모리 사용량 ⑤ 정확도(원본 대비 변화) |
| Parity check | 같은 프레임에서 원본(`.pt`)과 변환 모델(NCNN, ONNX Runtime)의 검출 박스·관절 좌표 차이, 자세 판정 일치. 허용 기준은 검증 전에 정함 — **실측 전** |
| 반복 | 워밍업 후 구간을 정해 여러 번 측정, 평균과 최저값 기록 |
| 실행 경로 | Ultralytics 경로로 먼저 측정. 메모리·시작 시간이 과하면 ncnn 직접 경로 측정을 추가 |
| 판정 | 전체 FPS ≥ 5 (PRD 3장)인 구성 중 정확도가 충분한 쪽. 3.5절 전환 조건 적용 |

**결과 기록 표 (실측 전)**

| 구성 | 엔진 | 추론 시간 | 전체 FPS | 메모리 | Parity (원본 대비 좌표 차이) | 비고 |
|---|---|---|---|---|---|---|
| A | NCNN + MediaPipe | 실측 전 | 실측 전 | 실측 전 | 실측 전 | |
| A | ONNX Runtime + MediaPipe | 실측 전 | 실측 전 | 실측 전 | 실측 전 | |
| B | NCNN | 실측 전 | 실측 전 | 실측 전 | 실측 전 | |
| B | ONNX Runtime | 실측 전 | 실측 전 | 실측 전 | 실측 전 | |

**확인하지 못한 항목**
- ONNX Runtime pip aarch64 휠에서 KleidiAI·XNNPACK이 기본으로 쓰이는지
- LiteRT Python 휠의 기본 CPU 경로가 XNNPACK인지
- OpenVINO의 "Intel 정식 검증 없음" 문구가 현재 문서에도 있는지, Pi OS의 glibc 버전이 OpenVINO 휠 조건(2.35 이상)을 만족하는지
- Ultralytics 벤치마크의 데이터셋·오버클럭 여부, pose 모델과 MediaPipe Pose의 Pi 5 공개 수치
- ncnn 자체 INT8 도구를 YOLO26에 쓸 수 있는지
- 내보낸 모델(NCNN 형식 등)에 대한 Ultralytics 라이선스 해석, MediaPipe 모델 번들(.task)의 재배포 조건
- Windows에서 Ultralytics NCNN 내보내기·실행이 되는지 (5.1)
- AI HAT+(13·26 TOPS) 가격, NPU 경로와 MediaPipe의 관계 (3.6)

---

## 6. 출처

모두 2026-10-15 확인.

| 기호 | 문서 | 확인한 내용 |
|---|---|---|
| R1 | [Raspberry Pi 5 제품 페이지](https://www.raspberrypi.com/products/raspberry-pi-5/) | Broadcom BCM2712 2.4GHz 4코어 Arm Cortex-A76, NPU 언급 없음 |
| R2 | [Raspberry Pi 공식 문서 — AI HAT+](https://www.raspberrypi.com/documentation/accessories/ai-hat-plus.html) | Hailo-8L 13 TOPS / Hailo-8 26 TOPS, Raspberry Pi 5 PCIe 포트 연결 |
| R3 | [Raspberry Pi AI HAT+ 2 제품 페이지](https://www.raspberrypi.com/products/ai-hat-plus-2/) | Hailo-10H 40 TOPS(INT4), 보드 RAM 8GB, $200, LLM·VLM 용도, 비전 성능은 AI HAT+(26 TOPS)와 비슷 |
| U1 | [Ultralytics — Raspberry Pi 가이드](https://docs.ultralytics.com/guides/raspberry-pi/) | Pi 5 형식별 벤치마크(FP32, 640, 8.4.108, 전처리·후처리 제외), NCNN 권장, LiteRT는 Pi에서 내보내기 불가 |
| U2 | [Ultralytics — Export](https://docs.ultralytics.com/modes/export/) | 형식별 `format` 인자, INT8(`quantize=8`) 지원 여부 — NCNN은 FP32·FP16만 |
| U3 | [Ultralytics — NCNN 통합](https://docs.ultralytics.com/integrations/ncnn/) | Detect·Pose 등 지원 작업, `YOLO("…_ncnn_model")` 실행, Linux·Windows·macOS 개발·평가 배포 언급 |
| U4 | [Ultralytics — License](https://www.ultralytics.com/license) | AGPL-3.0이 학습된 모델·가중치에도 적용, 상용 시 Enterprise 라이선스 |
| U5 | [Ultralytics `pyproject.toml`](https://github.com/ultralytics/ultralytics/blob/main/pyproject.toml) | 라이선스 AGPL-3.0, 필수 의존성에 torch·torchvision |
| U6 | [Ultralytics — Quickstart](https://docs.ultralytics.com/quickstart/) | 설치 조건 "PyTorch>=1.8", torch 없이 설치하는 방법 없음 |
| U7 | [Ultralytics — YOLO26](https://docs.ultralytics.com/models/yolo26/) | NMS 없는 end-to-end 출력 `(N, 300, 6)`, pose 모델 제공 |
| U8 | [Ultralytics — Hailo 통합](https://docs.ultralytics.com/integrations/hailo/) | `format=hailo` INT8 전용, 컴파일은 Linux x86_64 + Hailo DFC, YOLO26-pose 미지원, Pi 5 + AI HAT+(Hailo-8) YOLO26n 21.7 ms/장(COCO128, 전처리·후처리 제외) |
| O1 | [PyPI onnxruntime](https://pypi.org/project/onnxruntime/) | 1.31.0, Linux aarch64 휠, MIT |
| O2 | [ONNX Runtime — Quantization](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html) | 정적·동적 INT8, QDQ, Arm dot-product 명령 언급 |
| O3 | [ONNX Runtime — Arm KleidiAI](https://onnxruntime.ai/docs/performance/kleidiai/) · [v1.22 릴리스](https://github.com/microsoft/onnxruntime/releases/tag/v1.22.0) · [v1.25 릴리스](https://github.com/microsoft/onnxruntime/releases/tag/v1.25.0) | KleidiAI 커널을 MLAS에 통합 |
| O4 | [ONNX Runtime — Execution Providers](https://onnxruntime.ai/docs/execution-providers/) · [빌드 옵션](https://onnxruntime.ai/docs/build/eps.html) | XNNPACK은 별도 빌드, ACL·Arm NN은 preview |
| N1 | [PyPI ncnn](https://pypi.org/project/ncnn/) | 1.0.20260526, Linux aarch64 휠, Windows x86_64 휠(CPython 3.8–3.14), BSD-3 |
| N2 | [Tencent/ncnn README](https://github.com/Tencent/ncnn) | ARM NEON 최적화, INT8 추론, Python 바인딩 |
| V1 | [PyPI openvino](https://pypi.org/project/openvino/) | 2026.4.1, Linux aarch64 휠(glibc 2.35+), Apache-2.0 |
| V2 | [OpenVINO CPU Device 문서 원문](https://github.com/openvinotoolkit/openvino/blob/master/docs/articles_en/openvino-workflow/running-inference/inference-devices-and-modes/cpu-device.rst) | Arm 정밀도 FP32·FP16, INT8 미포함, 양자화 모델 시뮬레이션 실행, Windows ARM64 미지원 |
| L1 | [PyPI ai-edge-litert](https://pypi.org/project/ai-edge-litert/) | 2.3.0, Linux aarch64 휠, Apache-2.0 |
| L2 | [LiteRT 개요](https://developers.google.com/edge/litert) | TensorFlow Lite 기반, Linux 지원, PyTorch·TF·JAX에서 변환 |
| L3 | [LiteRT 마이그레이션](https://developers.google.com/edge/litert/migration) | 기존 TFLite 패키지는 기능 업데이트 없음, 패키지 이름만 바꾸면 됨 |
| L4 | [LiteRT 델리게이트](https://developers.google.com/edge/litert/performance/delegates) | 기본 CPU 커널이 ARM Neon에 최적화 |
| M1 | [PyPI mediapipe](https://pypi.org/project/mediapipe/) | 1.1.1, Linux aarch64 휠, Apache-2.0 |
| M2 | [MediaPipe `inference_calculator.proto`](https://github.com/google-ai-edge/mediapipe/blob/master/mediapipe/calculators/tensor/inference_calculator.proto) | 추론 계산기가 TFLite 모델을 실행, XNNPACK·GPU 델리게이트 옵션 |
