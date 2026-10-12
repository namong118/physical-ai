# 나만의 피지컬 AI 제품 만들기

이 폴더는 과제 제출용 작업 폴더입니다.
나만의 피지컬 AI 제품을 기획하고, 그 제품을 소개하는 홈페이지를 만들어 GitHub Pages로 배포합니다.

## 폴더 구성

```
physicalAI/
├── README.md          ← 지금 보고 있는 안내 문서
├── index.html         ← 제품 소개 홈페이지 (GitHub Pages 시작 파일)
├── images/            ← 홈페이지에 쓸 이미지 (제품 사진, 스케치 등)
├── PRD/
│   └── PRD.md         ← 제품 요구사항 문서 (무엇을, 왜, 어떻게 만들지)
└── report/
    └── report.md      ← 과제 보고서 (과정, 회고, 배운 점)
```

## GitHub Pages 배포 방법

GitHub Pages는 `main` 브랜치를 그대로 서비스합니다. `main`에 push하면 곧 공개됩니다.

### 처음 한 번 (빈 원격 레포에 올릴 때)

```bash
git init
git add .
git commit -m "처음 커밋"
git branch -M main
git remote add origin https://github.com/namong118/physical-ai.git
git push -u origin main
```

### 평소 수정할 때

```bash
git status                       # 바뀐 파일 확인
git add <수정한 파일>              # 필요한 파일만 (미추적 파일을 한꺼번에 넣지 않음)
git commit -m "수정 내용에 대한 설명"
git push origin main
```

- 강제 push(`--force`, `-f`)는 **원칙적으로 사용하지 않습니다.** 원격의 기록을 덮어써 다른 곳에서 올린 커밋이 사라질 수 있습니다.
- push가 거절되면(원격에 새 커밋이 있으면) 강제로 덮지 말고 `git pull --rebase origin main`으로 받은 뒤 다시 push합니다.
- 이미 push한 커밋은 고쳐 쓰지(amend, rebase) 않고 새 커밋으로 수정합니다.
