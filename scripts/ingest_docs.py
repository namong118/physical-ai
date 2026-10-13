"""홈페이지 문서 챗봇용 문서 넣기 스크립트.

docs.json 에 있는 문서(.md)를 제목 단위 조각으로 나누고, Gemini 임베딩을 만들어
Supabase 의 site_documents · site_chunks 에 넣습니다.

  python scripts/ingest_docs.py --dry-run          # 조각 나누기만 확인 (네트워크·키 없이)
  python scripts/ingest_docs.py --dry-run --show 3 # 문서마다 조각 3개 미리보기
  python scripts/ingest_docs.py                    # 실제 넣기 (.env 필요, 바뀐 문서만)
  python scripts/ingest_docs.py --force            # 바뀌지 않은 문서도 다시 넣기

실제 넣기에 필요한 값(.env, 커밋하지 않음): SUPABASE_URL, SUPABASE_SECRET_KEY, GEMINI_API_KEY
키 값은 화면에 출력하지 않습니다.

임베딩 모델·차원·입력 형식은 supabase/functions/_shared/embedding.json 한 곳에서 정하고,
site-chat Edge Function 도 같은 파일을 읽습니다.
"""

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 조각 나누기 설정 — 바꾸면 모든 문서의 content_hash 가 바뀌어 다시 들어갑니다
CHUNK_VERSION = "1"
MAX_CHARS = 1200      # 조각 본문 최대 길이(글자)
MIN_CHARS = 40        # 이보다 짧은 절은 건너뜀 (제목만 있는 절 등)
ALLOWED_DIRS = ("PRD/", "report/")

# docs.json 밖에서 함께 넣는 페이지 — 문서 카드 목록(docs.json)에는 나타나지 않음.
# docs.json 에 없다고 지우는 규칙에서도 제외됨.
PAGES = [{"id": "homepage", "title": "홈페이지", "file": "index.html"}]

# 임베딩 — 설정은 site-chat 과 공유하는 파일에서 읽음
EMBED_CONFIG = json.loads((ROOT / "supabase/functions/_shared/embedding.json").read_text(encoding="utf-8"))
EMBED_MODEL = EMBED_CONFIG["model"]
EMBED_DIM = EMBED_CONFIG["dimensions"]
DB_DIM = 768          # 마이그레이션의 vector(768). 설정 파일과 다르면 실행을 멈춤
EMBED_BATCH = 50
EMBED_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{EMBED_MODEL}:batchEmbedContents"
)

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


# ---------- 문서 목록 ----------

def load_docs():
    data = json.loads((ROOT / "docs.json").read_text(encoding="utf-8"))
    docs = []
    for d in data["docs"]:
        file = d["file"]
        if not file.startswith(ALLOWED_DIRS) or not file.endswith(".md") or ".." in file:
            sys.exit(f"허용하지 않는 문서 경로: {file}")
        docs.append(d)
    return docs


# ---------- 홈페이지 본문 ----------

class PageText(HTMLParser):
    """index.html 의 <section> 별 본문만 모음.

    빼는 것: script·style·svg·img·header·nav·footer·button, 아이콘 글자(material-symbols),
    aria-hidden 요소, #docs(docs.json 으로 그리는 동적 영역),
    'Hero visual' 주석 바로 다음 요소(히어로의 보호자 앱 화면 예시 — 장식용 예시 화면).
    """
    SKIP_TAGS = {"script", "style", "svg", "img", "header", "nav", "footer", "button", "noscript", "template"}
    VOID_TAGS = {"br", "img", "hr", "input", "meta", "link", "source", "wbr"}
    BLOCK_TAGS = {"p", "div", "li", "ul", "ol", "h1", "h2", "h4", "h5", "h6", "tr", "table",
                  "figcaption", "blockquote", "dt", "dd"}
    BREAK = " "   # h3 앞 블록 경계 (조각을 나눌 수 있는 자리)

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.skip_at = None       # 건너뛰는 요소가 열린 깊이
        self.skip_next = False
        self.title_at = None      # 섹션 제목(h1·h2)이 열린 깊이
        self.sections = []
        self.cur = None

    def handle_comment(self, data):
        if "Hero visual" in data:
            self.skip_next = True

    def handle_starttag(self, tag, attrs):
        if tag in self.VOID_TAGS:
            if tag == "br" and self.cur is not None and self.skip_at is None:
                (self.cur["title"] if self.title_at else self.cur["body"]).append(" ")
            return
        a = dict(attrs)
        self.stack.append(tag)
        if tag == "section":
            self.cur = {"id": a.get("id"), "title": [], "body": []}
            self.sections.append(self.cur)
        if self.cur is None or self.skip_at is not None:
            return
        if (self.skip_next or tag in self.SKIP_TAGS or a.get("aria-hidden") == "true"
                or "material-symbols" in (a.get("class") or "") or self.cur["id"] == "docs"):
            self.skip_next = False
            self.skip_at = len(self.stack)
            return
        if tag in ("h1", "h2") and not self.cur["title"]:
            self.title_at = len(self.stack)
        elif tag == "h3":
            self.cur["body"].append(self.BREAK)
        elif tag in self.BLOCK_TAGS:
            self.cur["body"].append("\n")

    def handle_endtag(self, tag):
        if tag in self.VOID_TAGS or tag not in self.stack:
            return
        while self.stack:
            depth = len(self.stack)
            t = self.stack.pop()
            if self.skip_at is not None and depth <= self.skip_at:
                self.skip_at = None
            if self.title_at is not None and depth <= self.title_at:
                self.title_at = None
            if t == tag:
                break
        if self.cur is not None and self.skip_at is None and tag in self.BLOCK_TAGS | {"h3"}:
            self.cur["body"].append("\n")
        if tag == "section":
            self.cur = None

    def handle_data(self, data):
        if self.cur is None or self.skip_at is not None:
            return
        (self.cur["title"] if self.title_at else self.cur["body"]).append(data)


def tidy_block(text):
    """공백 정리, 빈 줄 제거. 카드의 '무엇을 / 언제 / 왜' 라벨은 다음 줄 값과 한 줄로 합침."""
    lines = [re.sub(r"\s+", " ", l).strip() for l in text.split("\n")]
    lines = [l for l in lines if l]
    out = []
    for l in lines:
        if out and out[-1] in ("무엇을", "언제", "왜"):
            out[-1] = f"{out[-1]}: {l}"
        else:
            out.append(l)
    return "\n".join(out)


def page_markdown(page):
    """홈페이지를 '# 제목 > ## 섹션 제목 > 본문' 형태로 바꿔 문서와 같은 조각 나누기를 씀."""
    parser = PageText()
    parser.feed((ROOT / page["file"]).read_text(encoding="utf-8"))
    parts = [f"# {page['title']}"]
    for sec in parser.sections:
        title = re.sub(r"\s+", " ", "".join(sec["title"])).strip()
        blocks = [tidy_block(b) for b in "".join(sec["body"]).split(PageText.BREAK)]
        body = "\n\n".join(b for b in blocks if b)
        if not body:
            continue
        parts.append(f"## {title or page['title']}\n\n{body}")
    return "\n\n".join(parts) + "\n"


# ---------- 조각 나누기 ----------

def plain_heading(text):
    """제목 줄의 마크다운 꾸밈(굵게, 코드, 링크)을 걷어냄."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return re.sub(r"[*_`]", "", text).strip()


def split_sections(md):
    """제목 기준으로 (제목 경로, 본문) 목록을 만듦. 코드 블록 안의 # 줄은 제목으로 보지 않음."""
    sections = []
    path = []          # [(level, title)]
    buf = []
    in_fence = False

    def flush():
        body = "\n".join(buf).strip()
        if body:
            sections.append((" > ".join(t for _, t in path), body))
        buf.clear()

    for line in md.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            buf.append(line)
            continue
        m = None if in_fence else HEADING_RE.match(line)
        if m:
            flush()
            level = len(m.group(1))
            while path and path[-1][0] >= level:
                path.pop()
            path.append((level, plain_heading(m.group(2))))
        else:
            buf.append(line)
    flush()
    return sections


def split_blocks(body):
    """빈 줄 기준 블록으로 나눔. 코드 블록은 안에 빈 줄이 있어도 한 블록."""
    blocks, cur, in_fence = [], [], False
    for line in body.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
        if not line.strip() and not in_fence:
            if cur:
                blocks.append("\n".join(cur))
                cur = []
        else:
            cur.append(line)
    if cur:
        blocks.append("\n".join(cur))
    return blocks


def split_long(block):
    """한 블록이 MAX_CHARS 를 넘으면 줄 단위로 자름 (긴 표·목록)."""
    if len(block) <= MAX_CHARS:
        return [block]
    lines = block.splitlines()
    # 표라면 머리글 두 줄을 각 조각에 반복
    header = lines[:2] if len(lines) > 2 and lines[0].lstrip().startswith("|") and set(lines[1].replace("|", "").strip()) <= set("-: ") else []
    rest = lines[len(header):]
    parts, cur = [], list(header)
    for line in rest:
        if len("\n".join(cur + [line])) > MAX_CHARS and len(cur) > len(header):
            parts.append("\n".join(cur))
            cur = list(header)
        cur.append(line)
    if len(cur) > len(header):
        parts.append("\n".join(cur))
    return parts


def chunk_section(body):
    pieces = []
    for block in split_blocks(body):
        pieces.extend(split_long(block))
    chunks, cur = [], ""
    for p in pieces:
        if cur and len(cur) + 2 + len(p) > MAX_CHARS:
            chunks.append(cur)
            cur = p
        else:
            cur = f"{cur}\n\n{p}" if cur else p
    if cur:
        chunks.append(cur)
    return chunks


def build_chunks(doc, md):
    out = []
    for heading, body in split_sections(md):
        if len(body) < MIN_CHARS:
            continue
        for text in chunk_section(body):
            out.append({"heading": heading or doc["title"], "content": text})
    for i, c in enumerate(out):
        c["chunk_index"] = i
    return out


def embed_text(doc, chunk):
    """문서용 입력 형식(설정 파일)에 제목 경로(문서 # 제목부터)와 본문을 넣음. DB 의 content 는 본문만."""
    return EMBED_CONFIG["document_format"].replace("{title}", chunk["heading"]).replace("{content}", chunk["content"])


def content_hash(md):
    """본문 + 조각 나누기·임베딩 설정. 설정이 바뀌면 모든 문서를 다시 넣게 됨."""
    config = json.dumps(EMBED_CONFIG, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(f"{CHUNK_VERSION}:{config}\n{md}".encode("utf-8")).hexdigest()


def check_config():
    if EMBED_DIM != DB_DIM:
        sys.exit(f"embedding.json 의 dimensions({EMBED_DIM})가 DB vector({DB_DIM})와 다릅니다.")
    for key in ("document_format", "query_format"):
        if "{content}" not in EMBED_CONFIG[key]:
            sys.exit(f"embedding.json 의 {key} 에 {{content}} 가 없습니다.")


# ---------- 네트워크 (실제 넣기에서만) ----------

def load_env():
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    missing = [k for k in ("SUPABASE_URL", "SUPABASE_SECRET_KEY", "GEMINI_API_KEY") if not os.environ.get(k)]
    if missing:
        sys.exit(f".env 에 값이 없습니다: {', '.join(missing)}")


def request(method, url, headers, body=None, retries=3):
    data = None if body is None else json.dumps(body).encode("utf-8")
    for attempt in range(retries):
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                raw = res.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "replace")[:500]
            if e.code in (429, 500, 502, 503) and attempt < retries - 1:
                time.sleep(2 ** attempt * 5)
                continue
            # 주소의 쿼리·헤더는 출력하지 않음 (키 노출 방지)
            sys.exit(f"요청 실패 {e.code} {method} {url.split('?')[0]}\n{msg}")


def embed(texts):
    headers = {"Content-Type": "application/json", "x-goog-api-key": os.environ["GEMINI_API_KEY"]}
    vectors = []
    for i in range(0, len(texts), EMBED_BATCH):
        batch = texts[i:i + EMBED_BATCH]
        body = {"requests": [
            {
                "model": f"models/{EMBED_MODEL}",
                "content": {"parts": [{"text": t}]},
                "outputDimensionality": EMBED_DIM,   # task_type 대신 입력 형식(접두어)으로 작업을 지정
            }
            for t in batch
        ]}
        res = request("POST", EMBED_URL, headers, body)
        for e in res["embeddings"]:
            v = e["values"]
            if len(v) != EMBED_DIM:
                sys.exit(f"임베딩 차원이 {EMBED_DIM}이 아님: {len(v)}")
            n = math.sqrt(sum(x * x for x in v)) or 1.0   # 모델이 정규화해 주지만 한 번 더 맞춤
            vectors.append([x / n for x in v])
    return vectors


class Supabase:
    def __init__(self):
        self.base = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1"
        # 새 secret 키(sb_secret_...)는 JWT 가 아니라 apikey 헤더로만 보냄 (Authorization: Bearer 아님)
        self.headers = {"apikey": os.environ["SUPABASE_SECRET_KEY"], "Content-Type": "application/json"}

    def call(self, method, path, body=None, prefer=None):
        headers = dict(self.headers)
        if prefer:
            headers["Prefer"] = prefer
        return request(method, f"{self.base}/{path}", headers, body)

    def existing_hashes(self):
        rows = self.call("GET", "site_documents?select=id,content_hash") or []
        return {r["id"]: r["content_hash"] for r in rows}


def ingest(docs, prepared, force):
    load_env()
    db = Supabase()
    existing = db.existing_hashes()

    for doc, md, chunks in prepared:
        h = content_hash(md)
        if not force and existing.get(doc["id"]) == h:
            print(f"  건너뜀 (바뀌지 않음): {doc['file']}")
            continue
        vectors = embed([embed_text(doc, c) for c in chunks])
        db.call("POST", "site_documents?on_conflict=id", [{
            "id": doc["id"], "title": doc["title"], "file": doc["file"],
            "version": doc.get("version"), "doc_date": doc.get("date"),
            "content_hash": h, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }], prefer="resolution=merge-duplicates,return=minimal")
        db.call("DELETE", f"site_chunks?document_id=eq.{doc['id']}", prefer="return=minimal")
        db.call("POST", "site_chunks", [
            {"document_id": doc["id"], "chunk_index": c["chunk_index"], "heading": c["heading"],
             "content": c["content"], "embedding": "[" + ",".join(f"{x:.7f}" for x in v) + "]"}
            for c, v in zip(chunks, vectors)
        ], prefer="return=minimal")
        print(f"  넣음: {doc['file']} — 조각 {len(chunks)}개")

    # docs.json 에서 빠진 문서는 지움 (조각은 on delete cascade)
    removed = sorted(set(existing) - {d["id"] for d in docs} - {p["id"] for p in PAGES})
    for doc_id in removed:
        db.call("DELETE", f"site_documents?id=eq.{doc_id}", prefer="return=minimal")
        print(f"  지움 (docs.json 에 없음): {doc_id}")


# ---------- 실행 ----------

def main():
    ap = argparse.ArgumentParser(description="docs.json 문서를 챗봇용 조각·임베딩으로 넣기")
    ap.add_argument("--dry-run", action="store_true", help="조각 나누기만 하고 네트워크를 쓰지 않음")
    ap.add_argument("--show", type=int, default=0, help="--dry-run 에서 문서마다 미리 볼 조각 수")
    ap.add_argument("--force", action="store_true", help="바뀌지 않은 문서도 다시 넣기")
    args = ap.parse_args()

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    check_config()
    docs = load_docs()
    prepared = []
    for doc in docs:
        md = (ROOT / doc["file"]).read_text(encoding="utf-8")
        prepared.append((doc, md, build_chunks(doc, md)))
    for page in PAGES:
        md = page_markdown(page)
        prepared.append((page, md, build_chunks(page, md)))

    total = 0
    print(f"임베딩: {EMBED_MODEL}, {EMBED_DIM}차원 (embedding.json)")
    print(f"문서 {len(docs)}개 (docs.json) + 페이지 {len(PAGES)}개 (PAGES)")
    for doc, md, chunks in prepared:
        lens = [len(c["content"]) for c in chunks]
        total += len(chunks)
        print(f"- {doc['file']}  조각 {len(chunks)}개, 글자 수 최소 {min(lens)} / 평균 {sum(lens) // len(lens)} / 최대 {max(lens)}")
        for c in chunks[:args.show] if args.dry_run else []:
            preview = c["content"][:160].replace("\n", " ⏎ ")
            print(f"    [{c['chunk_index']}] {c['heading']}\n        {preview}")
    print(f"조각 합계 {total}개")

    if args.dry_run:
        print("--dry-run: 임베딩·DB 쓰기를 하지 않았습니다.")
        return
    ingest(docs, prepared, args.force)


if __name__ == "__main__":
    main()
