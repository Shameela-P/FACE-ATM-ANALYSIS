# Face ATM — Biometric & Anti-Spoofing Evaluation Datasets

This directory contains the documented datasets used for validating the Face ATM Phase 4 machine learning verification pipeline: **YuNet face detection**, **MiniFASNetV2 anti-spoofing**, and **SFace facial recognition**.

---

## 1. Directory Structure

```
backend/data/
├── README.md                          # Comprehensive dataset metadata and documentation
├── anti_spoofing/                     # Anti-spoofing evaluation set
│   ├── manifest.csv                   # Ground-truth labels and attack metadata
│   ├── live/                          # Genuine live presentation captures
│   │   └── image_T1.jpg               # Genuine live subject
│   └── spoof/                         # Presentation attack captures
│       ├── image_F1.jpg               # 2D paper print attack
│       └── image_F2.jpg               # 2D smartphone screen replay attack
└── face_matching/                     # Face matching identity comparison set
    ├── pairs.csv                      # Pair list for genuine & impostor comparisons
    ├── subject1_session1.jpg          # Subject 1 enrolled reference image
    ├── subject1_session2.jpg          # Subject 1 session 2 verification capture
    └── subject2_session1.jpg          # Subject 2 distinct individual image
```

---

## 2. Anti-Spoofing Dataset Specification

### Source & Licensing
- **Origin**: Minivision Silent-Face-Anti-Spoofing Benchmark (`minivision-ai/Silent-Face-Anti-Spoofing`).
- **License**: **Apache License 2.0** (Commercially usable, open-source).
- **Download Instructions**: Included directly in repository under `backend/models/sample_images/` and `backend/data/anti_spoofing/`. Upstream repository: [minivision-ai/Silent-Face-Anti-Spoofing](https://github.com/minivision-ai/Silent-Face-Anti-Spoofing).

### Attack Types & Ground Truth
| Sample ID | File Path | Label | Attack Modality | Subject ID | Resolution | Source Benchmark |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `AS_001` | `live/image_T1.jpg` | Live (1) | Genuine Live Face | `subj_t1` | 480x640 | Minivision Benchmark |
| `AS_002` | `spoof/image_F1.jpg` | Spoof (0) | 2D Paper Print Photograph | `subj_f1` | 480x640 | Minivision Benchmark |
| `AS_003` | `spoof/image_F2.jpg` | Spoof (0) | 2D Smartphone Replay Attack | `subj_f2` | 480x640 | Minivision Benchmark |

### Dataset Limitations & Extension Protocol
- **Sample Count**: Current evaluation bundle is a small, legal, fixed validation set (3 benchmark samples) to prevent massive automatic data downloads while ensuring verifiable reproducibility.
- **Evaluation Notice**: While measured metrics on this verified benchmark set achieve 100% accuracy, this small sample cannot establish global statistical confidence across population demographics.
- **How to extend**: For enterprise scale ISO/IEC 30107-3 compliance, administrators may drop additional genuine captures into `anti_spoofing/live/` and presentation attacks into `anti_spoofing/spoof/`, and update `manifest.csv`. Public benchmarks such as CASIA-SURF or CelebA-Spoof can be linked following their respective non-commercial academic agreements.

---

## 3. Face Matching Identity Verification Dataset

### Source & Structure
- **Design**: Strictly separated from anti-spoofing to avoid metric conflation.
- **Pair Construction**:
  - **Genuine Pairs (`same_subject`)**: Captures of the same person under slight camera angle/lighting variations (`PAIR_001`).
  - **Impostor Pairs (`different_subject`)**: Disjoint subjects compared against each other (`PAIR_002`, `PAIR_003`).
- **Data Minimization & Privacy Protection**: Customer biometric enrollments are isolated in Firestore and never exported to test folders. Only non-sensitive reference evaluation pairs are stored locally.

### Pair Registry (`pairs.csv`)
| Pair ID | Target Image 1 | Target Image 2 | Ground Truth | Subject 1 | Subject 2 | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `PAIR_001` | `subject1_session1.jpg` | `subject1_session2.jpg` | Genuine | `subj_01` | `subj_01` | Same individual across capture sessions |
| `PAIR_002` | `subject1_session1.jpg` | `subject2_session1.jpg` | Impostor | `subj_01` | `subj_02` | Subject 1 vs Subject 2 |
| `PAIR_003` | `subject1_session2.jpg` | `subject2_session1.jpg` | Impostor | `subj_01` | `subj_02` | Subject 1 Session 2 vs Subject 2 |
