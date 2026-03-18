#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import requests


USER_AGENT = "reddit-local-summary-tool/1.2"
OLLAMA_URL_DEFAULT = "http://127.0.0.1:11434/api/generate"


# -----------------------------
# Utility
# -----------------------------

def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def save_json(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    text = text.replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def safe_filename(text: str, max_len: int = 80) -> str:
    text = re.sub(r"[^\w\-]+", "_", text, flags=re.UNICODE)
    text = text.strip("_")
    return text[:max_len] or "reddit_post"


def now_ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def split_batches(items: List[str], size: int) -> List[List[str]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


# -----------------------------
# Reddit fetch + extract
# -----------------------------

def reddit_json_url(post_url: str) -> str:
    base = post_url.rstrip("/")
    # limit ovdje pomaže da početni listing vrati više komentara prije "more" grananja
    return base + ".json?limit=500&raw_json=1"


def fetch_reddit_json(post_url: str, timeout: int = 30) -> Any:
    url = reddit_json_url(post_url)
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def extract_gallery_urls(post_data: Dict[str, Any]) -> List[str]:
    urls: List[str] = []

    media_metadata = post_data.get("media_metadata") or {}
    for _, item in media_metadata.items():
        s = item.get("s") or {}
        u = s.get("u")
        if u:
            urls.append(u.replace("&amp;", "&"))

    preview = post_data.get("preview") or {}
    images = preview.get("images") or []
    for img in images:
        src = ((img.get("source") or {}).get("url") or "").replace("&amp;", "&")
        if src and src not in urls:
            urls.append(src)

    return urls


def extract_post(post_data: Dict[str, Any], source_url: str) -> Dict[str, Any]:
    selftext = clean_text(post_data.get("selftext", ""))

    return {
        "post_id": post_data.get("id"),
        "thing_id": post_data.get("name"),  # npr. t3_xxxxx
        "title": clean_text(post_data.get("title", "")),
        "selftext": selftext,
        "author": post_data.get("author"),
        "subreddit": post_data.get("subreddit"),
        "subreddit_name_prefixed": post_data.get("subreddit_name_prefixed"),
        "score": post_data.get("score"),
        "upvote_ratio": post_data.get("upvote_ratio"),
        "num_comments": post_data.get("num_comments"),
        "created_utc": post_data.get("created_utc"),
        "permalink": post_data.get("permalink"),
        "url": source_url,
        "domain": post_data.get("domain"),
        "post_hint": post_data.get("post_hint"),
        "post_flair_text": post_data.get("link_flair_text"),
        "is_gallery": bool(post_data.get("is_gallery", False)),
        "gallery_urls": extract_gallery_urls(post_data),
        "over_18": bool(post_data.get("over_18", False)),
        "spoiler": bool(post_data.get("spoiler", False)),
        "locked": bool(post_data.get("locked", False)),
        "stickied": bool(post_data.get("stickied", False)),
        "distinguished": post_data.get("distinguished"),
        "language_guess": None,
        "text_tokens_est": estimate_tokens(selftext),
    }


def fetch_more_comments(children_ids: List[str], link_id: str, timeout: int = 30) -> List[Dict[str, Any]]:
    """
    Dohvat "more" komentara preko javnog Reddit endpointa.
    Batchamo po 100 da izbjegnemo preduge queryje.
    """
    headers = {"User-Agent": USER_AGENT}
    url = "https://www.reddit.com/api/morechildren"
    out: List[Dict[str, Any]] = []

    for batch in split_batches(children_ids, 100):
        params = {
            "api_type": "json",
            "link_id": link_id,              # npr. t3_1rvjxcq
            "children": ",".join(batch),
            "raw_json": 1,
        }

        resp = requests.get(url, headers=headers, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

        things = ((data.get("json") or {}).get("data") or {}).get("things") or []
        if things:
            out.extend(things)

        # mali delay da ne lupa prebrzo
        time.sleep(0.35)

    return out


def fetch_comment_context(post_id: str, parent_comment_id: str, timeout: int = 30) -> List[Dict[str, Any]]:
    """
    Fallback za neke "more" čvorove bez children liste.
    Obrazac koji se koristi je /comments/{submission}/_/{comment}.json
    """
    headers = {"User-Agent": USER_AGENT}
    url = f"https://www.reddit.com/comments/{post_id}/_/{parent_comment_id}.json?limit=500&raw_json=1"
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    if not isinstance(data, list) or len(data) < 2:
        return []

    return (((data[1] or {}).get("data") or {}).get("children") or [])


def flatten_comments(
    children: List[Dict[str, Any]],
    out: List[Dict[str, Any]],
    post_meta: Dict[str, Any],
    source_url: str,
    seen_comment_ids: Set[str],
    seen_more_keys: Set[str],
) -> None:
    for child in children:
        kind = child.get("kind")

        # Standardni komentar
        if kind == "t1":
            data = child.get("data", {})
            comment_id = data.get("id")
            if not comment_id or comment_id in seen_comment_ids:
                continue

            seen_comment_ids.add(comment_id)

            body_raw = data.get("body", "")
            body = clean_text(body_raw)

            if body and body not in ("[deleted]", "[removed]"):
                out.append({
                    "post_id": post_meta["post_id"],
                    "post_title": post_meta["title"],
                    "subreddit": post_meta["subreddit"],
                    "comment_id": comment_id,
                    "thing_id": data.get("name"),
                    "parent_id": data.get("parent_id"),
                    "author": data.get("author"),
                    "body": body,
                    "score": data.get("score", 0),
                    "depth": data.get("depth", 0),
                    "created_utc": data.get("created_utc"),
                    "controversiality": data.get("controversiality", 0),
                    "permalink": data.get("permalink"),
                    "url": source_url,
                    "is_submitter": bool(data.get("is_submitter", False)),
                    "stickied": bool(data.get("stickied", False)),
                    "distinguished": data.get("distinguished"),
                    "tokens_est": estimate_tokens(body),
                })

            replies = data.get("replies")
            if isinstance(replies, dict):
                reply_children = (replies.get("data") or {}).get("children") or []
                flatten_comments(
                    reply_children,
                    out,
                    post_meta,
                    source_url,
                    seen_comment_ids,
                    seen_more_keys,
                )
            continue

        # "more" čvorovi = još komentara koji nisu odmah isporučeni
        if kind == "more":
            data = child.get("data", {})
            children_ids = data.get("children") or []
            parent_id = data.get("parent_id")
            more_key = f"{parent_id}|{','.join(children_ids[:10])}|{len(children_ids)}"

            if more_key in seen_more_keys:
                continue
            seen_more_keys.add(more_key)

            # Najbolji slučaj: imamo children ID-eve
            if children_ids:
                try:
                    more_things = fetch_more_comments(children_ids, post_meta["thing_id"])
                    if more_things:
                        flatten_comments(
                            more_things,
                            out,
                            post_meta,
                            source_url,
                            seen_comment_ids,
                            seen_more_keys,
                        )
                except Exception:
                    pass
                continue

            # Fallback: ponekad "more" nema children nego samo parent context
            if parent_id and isinstance(parent_id, str) and parent_id.startswith("t1_"):
                parent_comment_id = parent_id[3:]
                try:
                    context_children = fetch_comment_context(post_meta["post_id"], parent_comment_id)
                    if context_children:
                        flatten_comments(
                            context_children,
                            out,
                            post_meta,
                            source_url,
                            seen_comment_ids,
                            seen_more_keys,
                        )
                except Exception:
                    pass
                continue


def scrape_reddit_post(post_url: str) -> Dict[str, Any]:
    raw = fetch_reddit_json(post_url)

    post_data = raw[0]["data"]["children"][0]["data"]
    post_meta = extract_post(post_data, post_url)

    comments: List[Dict[str, Any]] = []
    comment_children = raw[1]["data"]["children"]

    flatten_comments(
        comment_children,
        comments,
        post_meta,
        post_url,
        seen_comment_ids=set(),
        seen_more_keys=set(),
    )

    return {
        "post": post_meta,
        "comments": comments,
    }


# -----------------------------
# Chunking
# -----------------------------

def comment_to_prompt_block(comment: Dict[str, Any]) -> str:
    flags = []
    if comment.get("is_submitter"):
        flags.append("OP")
    if comment.get("stickied"):
        flags.append("STICKIED")
    if comment.get("controversiality", 0):
        flags.append("CONTROVERSIAL")
    if comment.get("distinguished"):
        flags.append(f"DISTINGUISHED={comment['distinguished']}")

    flags_str = ",".join(flags) if flags else "none"

    return (
        f"[comment_id={comment['comment_id']} "
        f"score={comment.get('score', 0)} "
        f"depth={comment.get('depth', 0)} "
        f"author={comment.get('author', 'unknown')} "
        f"flags={flags_str}]\n"
        f"{comment.get('body', '')}\n"
    )


def sort_comments_for_analysis(comments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        comments,
        key=lambda c: (
            c.get("depth", 0),
            -(c.get("score", 0) or 0),
            c.get("created_utc", 0) or 0
        )
    )


def chunk_comments(
    comments: List[Dict[str, Any]],
    max_tokens: int = 2500,
    max_comments_per_chunk: int = 50
) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []
    current_comments: List[Dict[str, Any]] = []
    current_token_sum = 0

    for comment in comments:
        t = int(comment.get("tokens_est", 0))
        must_split = False

        if current_comments and current_token_sum + t > max_tokens:
            must_split = True
        if current_comments and len(current_comments) >= max_comments_per_chunk:
            must_split = True

        if must_split:
            chunks.append({
                "chunk_id": len(chunks),
                "comment_count": len(current_comments),
                "token_estimate": current_token_sum,
                "comments": current_comments,
                "text": "\n".join(comment_to_prompt_block(c) for c in current_comments),
            })
            current_comments = []
            current_token_sum = 0

        current_comments.append(comment)
        current_token_sum += t

    if current_comments:
        chunks.append({
            "chunk_id": len(chunks),
            "comment_count": len(current_comments),
            "token_estimate": current_token_sum,
            "comments": current_comments,
            "text": "\n".join(comment_to_prompt_block(c) for c in current_comments),
        })

    return chunks


# -----------------------------
# Ollama
# -----------------------------

def extract_json_from_text(text: str) -> Dict[str, Any]:
    text = text.strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        candidate = match.group(0)
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    return {
        "raw_output": text,
        "parse_error": True
    }


def call_ollama(
    prompt: str,
    model: str,
    ollama_url: str = OLLAMA_URL_DEFAULT,
    temperature: float = 0.2,
    timeout: int = 180
) -> str:
    base_url = ollama_url.rsplit("/api/", 1)[0]
    tags_url = f"{base_url}/api/tags"

    health = requests.get(tags_url, timeout=10)
    health.raise_for_status()

    tags_data = health.json()
    installed_models = [m.get("name") for m in tags_data.get("models", []) if m.get("name")]

    if model not in installed_models:
        raise RuntimeError(
            f"Model '{model}' nije pronađen lokalno. Dostupni modeli: {installed_models}"
        )

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": temperature
        }
    }

    resp = requests.post(ollama_url, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    response_text = data.get("response", "")
    if not response_text:
        raise RuntimeError(f"Ollama nije vratio 'response'. Raw odgovor: {data}")

    return response_text


# -----------------------------
# Prompts
# -----------------------------

def build_chunk_prompt(post: Dict[str, Any], chunk_text: str) -> str:
    title = post.get("title", "")
    subreddit = post.get("subreddit", "")
    selftext = post.get("selftext", "")

    return f"""
Ti analiziraš chunk Reddit komentara i moraš vratiti ISKLJUČIVO valjan JSON objekt.

Kontekst posta:
- naslov: {title}
- subreddit: {subreddit}
- tekst posta: {selftext}

Cilj:
Sažmi što ljudi u ovom chunku stvarno govore, kako reagiraju i oko čega se slažu ili prepiru.

Vrati JSON sa sljedećim ključevima:
{{
  "summary": "Konkretan sažetak ovog chunka u 3-6 rečenica.",
  "main_topics": ["string"],
  "overall_sentiment": "positive|negative|mixed|neutral",
  "opinions_for": ["string"],
  "opinions_against": ["string"],
  "disputed_points": ["string"],
  "misunderstandings_or_uncertain_claims": ["string"],
  "notable_insights": ["string"],
  "tone_notes": ["string"],
  "reader_takeaway": "Što bi netko trebao znati ako ne želi čitati ovaj chunk."
}}

Upute za stil:
- fokus na stvarni sadržaj komentara
- ne ponavljaj isto drugim riječima
- izdvoji ono što je stvarno dominantno u raspravi
- ako chunk ode off-topic, navedi to
- ako ima humora, sarkazma, prepucavanja ili ideološkog sukoba, zabilježi to kratko i jasno

Komentari:
{chunk_text}
""".strip()


def build_final_merge_prompt(post: Dict[str, Any], chunk_summaries: List[Dict[str, Any]]) -> str:
    title = post.get("title", "")
    subreddit = post.get("subreddit", "")
    selftext = post.get("selftext", "")

    summaries_json = json.dumps(chunk_summaries, ensure_ascii=False, indent=2)

    return f"""
Ti spajaš više sažetaka chunkova iste Reddit rasprave.

Kontekst:
- naslov posta: {title}
- subreddit: {subreddit}
- tekst posta: {selftext}

Cilj:
Napravi završni sažetak koji je stvarno koristan osobi koja NE želi čitati sve komentare redom.
Želimo dobiti jedan prirodan, jasan i informativan TL;DR komentar koji prenosi:
- opći dojam komentara
- glavne teme
- gdje se ljudi slažu
- gdje nastaju rasprave ili sukobi mišljenja
- što je najbitnije za znati prije čitanja originalnog threada

Vrati ISKLJUČIVO jedan JSON objekt sa sljedećim ključevima:
{{
  "tldr_comment": "Jedan prirodan i čitljiv sažetak komentara, 5-10 rečenica, kao koristan komentar za čitatelja.",
  "reader_summary": "Kratak sažetak u 2-3 rečenice.",
  "final_summary": "Širi analitički sažetak rasprave.",
  "main_topics": ["string"],
  "consensus_points": ["string"],
  "disputed_points": ["string"],
  "strongest_arguments_for": ["string"],
  "strongest_arguments_against": ["string"],
  "tone_overview": "string",
  "controversial_elements": ["string"],
  "misinformation_or_uncertain_claims": ["string"],
  "practical_takeaways": ["string"],
  "worth_reading_original_comments": "string"
}}

Upute za stil:
- piši konkretno, ne generički
- nemoj samo nabrajati
- nemoj izmišljati detalje koji nisu prisutni u sažecima
- ako komentari skreću s teme, to jasno reci
- ako se thread pretvara u ideološko prepucavanje, reci to sažeto i neutralno
- tldr_comment mora zvučati kao nešto što bi čovjek stvarno htio pročitati umjesto cijelog threada

Chunk sažeci:
{summaries_json}
""".strip()


def build_tldr_comment_prompt(post: Dict[str, Any], final_summary: Dict[str, Any]) -> str:
    return f"""
Na temelju ove analize Reddit komentara napiši jedan koristan TL;DR komentar za osobu
koja ne želi čitati cijeli thread.

Post:
- naslov: {post.get("title", "")}
- subreddit: {post.get("subreddit", "")}
- tekst posta: {post.get("selftext", "")}

Analiza:
{json.dumps(final_summary, ensure_ascii=False, indent=2)}

Vrati ISKLJUČIVO JSON:
{{
  "tldr_comment": "Jedan prirodan komentar od 4-8 rečenica.",
  "reader_summary": "Kratak sažetak u 2-3 rečenice."
}}

Upute:
- neka zvuči prirodno
- neka bude informativno
- nemoj biti previše formalan
- reci gdje je stvarna vrijednost komentara, a gdje thread skreće u raspravu
- nemoj prepisivati analitičke točke kao bullet listu
""".strip()


# -----------------------------
# Reporting
# -----------------------------

def build_markdown_report(
    post: Dict[str, Any],
    final_summary: Dict[str, Any],
    chunk_summaries: List[Dict[str, Any]]
) -> str:
    lines: List[str] = []

    lines.append("# Reddit Summary Report")
    lines.append("")
    lines.append(f"**Naslov:** {post.get('title', '')}")
    lines.append(f"**Subreddit:** {post.get('subreddit', '')}")
    lines.append(f"**Autor:** {post.get('author', '')}")
    lines.append(f"**Score:** {post.get('score', '')}")
    lines.append(f"**Broj komentara po postu:** {post.get('num_comments', '')}")
    lines.append(f"**Komentara dohvaćeno:** {final_summary.get('_meta', {}).get('comment_count', '')}")
    lines.append(f"**URL:** {post.get('url', '')}")
    lines.append("")

    lines.append("## TL;DR komentar")
    lines.append("")
    lines.append(final_summary.get("tldr_comment", ""))
    lines.append("")

    lines.append("## Kratki sažetak za čitatelja")
    lines.append("")
    lines.append(final_summary.get("reader_summary", ""))
    lines.append("")

    if post.get("selftext"):
        lines.append("## Tekst posta")
        lines.append("")
        lines.append(post["selftext"])
        lines.append("")

    lines.append("## Analitički sažetak")
    lines.append("")
    lines.append(final_summary.get("final_summary", ""))
    lines.append("")

    def add_list_section(title: str, values: Any) -> None:
        lines.append(f"## {title}")
        lines.append("")
        if isinstance(values, list) and values:
            for item in values:
                lines.append(f"- {item}")
        elif isinstance(values, str) and values.strip():
            lines.append(values)
        else:
            lines.append("- Nema podataka")
        lines.append("")

    add_list_section("Glavne teme", final_summary.get("main_topics"))
    add_list_section("Točke slaganja", final_summary.get("consensus_points"))
    add_list_section("Sporne točke", final_summary.get("disputed_points"))
    add_list_section("Najjači argumenti ZA", final_summary.get("strongest_arguments_for"))
    add_list_section("Najjači argumenti PROTIV", final_summary.get("strongest_arguments_against"))
    add_list_section("Kontroverzni elementi", final_summary.get("controversial_elements"))
    add_list_section("Upitne tvrdnje", final_summary.get("misinformation_or_uncertain_claims"))
    add_list_section("Praktični zaključci", final_summary.get("practical_takeaways"))

    lines.append("## Treba li čitati originalne komentare?")
    lines.append("")
    lines.append(final_summary.get("worth_reading_original_comments", ""))
    lines.append("")

    return "\n".join(lines)


# -----------------------------
# Main
# -----------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Reddit scraper + chunking + Ollama summarizer")
    parser.add_argument("--url", required=False, help="Reddit post URL; ako izostaviš, skripta pita u konzoli")
    parser.add_argument("--model", default="llama3.1:latest", help="Ollama model name")
    parser.add_argument("--out", default="./reddit_output", help="Output folder")
    parser.add_argument("--max-tokens", type=int, default=2500, help="Max procijenjenih tokena po chunku")
    parser.add_argument("--max-comments-per-chunk", type=int, default=50, help="Max komentara po chunku")
    parser.add_argument("--temperature", type=float, default=0.2, help="Ollama temperature")
    parser.add_argument("--ollama-url", default=OLLAMA_URL_DEFAULT, help="Ollama API URL")
    parser.add_argument("--skip-ollama", action="store_true", help="Samo scrape + chunking bez Ollama summarization")
    parser.add_argument("--skip-tldr-pass", action="store_true", help="Preskoči dodatni završni TL;DR pass")
    args = parser.parse_args()

    if not args.url:
        try:
            args.url = input("Zalijepi Reddit link: ").strip()
        except KeyboardInterrupt:
            print("\nPrekinuto.")
            return 1

    if not args.url:
        print("Nisi unio link.", file=sys.stderr)
        return 1

    out_dir = Path(args.out)
    ensure_dir(out_dir)

    print(f"[{now_ts()}] Dohvaćam Reddit post i komentare...")
    try:
        result = scrape_reddit_post(args.url)
    except Exception as e:
        print(f"Greška pri dohvaćanju Reddit posta: {e}", file=sys.stderr)
        return 1

    post = result["post"]
    comments = sort_comments_for_analysis(result["comments"])

    slug = safe_filename(post.get("title", "reddit_post"))
    post_dir = out_dir / f"{post.get('post_id', 'unknown')}_{slug}"
    ensure_dir(post_dir)

    print(f"[{now_ts()}] Spremam clean podatke...")
    save_json(post_dir / "clean_post.json", post)
    save_json(post_dir / "clean_full.json", {"post": post, "comments": comments})
    save_jsonl(post_dir / "comments.jsonl", comments)

    print(f"[{now_ts()}] Komentara po postu: {post.get('num_comments', 0)}")
    print(f"[{now_ts()}] Komentara dohvaćeno: {len(comments)}")

    print(f"[{now_ts()}] Radim chunking...")
    chunks = chunk_comments(
        comments,
        max_tokens=args.max_tokens,
        max_comments_per_chunk=args.max_comments_per_chunk
    )

    chunks_preview = []
    for ch in chunks:
        chunks_preview.append({
            "chunk_id": ch["chunk_id"],
            "comment_count": ch["comment_count"],
            "token_estimate": ch["token_estimate"],
            "comment_ids": [c["comment_id"] for c in ch["comments"]],
        })
    save_json(post_dir / "chunks.json", chunks_preview)

    print(f"[{now_ts()}] Chunkova: {len(chunks)}")

    if args.skip_ollama:
        print(f"[{now_ts()}] --skip-ollama je uključen. Završavam nakon chunkinga.")
        print(f"Izlaz spremljen u: {post_dir}")
        return 0

    chunk_summaries: List[Dict[str, Any]] = []

    print(f"[{now_ts()}] Pokrećem Ollama chunk analizu...")
    for chunk in chunks:
        chunk_id = chunk["chunk_id"]
        print(f"[{now_ts()}] Chunk {chunk_id + 1}/{len(chunks)}")

        prompt = build_chunk_prompt(post, chunk["text"])

        try:
            response_text = call_ollama(
                prompt=prompt,
                model=args.model,
                ollama_url=args.ollama_url,
                temperature=args.temperature
            )
            parsed = extract_json_from_text(response_text)
        except Exception as e:
            parsed = {
                "summary": "",
                "main_topics": [],
                "overall_sentiment": "unknown",
                "opinions_for": [],
                "opinions_against": [],
                "disputed_points": [],
                "misunderstandings_or_uncertain_claims": [],
                "notable_insights": [],
                "tone_notes": [],
                "reader_takeaway": "",
                "error": str(e),
            }

        parsed["_meta"] = {
            "chunk_id": chunk_id,
            "comment_count": chunk["comment_count"],
            "token_estimate": chunk["token_estimate"],
        }
        chunk_summaries.append(parsed)

    save_json(post_dir / "chunk_summaries.json", chunk_summaries)

    print(f"[{now_ts()}] Radim final merge preko Ollame...")
    final_prompt = build_final_merge_prompt(post, chunk_summaries)

    try:
        final_response_text = call_ollama(
            prompt=final_prompt,
            model=args.model,
            ollama_url=args.ollama_url,
            temperature=args.temperature
        )
        final_summary = extract_json_from_text(final_response_text)
    except Exception as e:
        final_summary = {
            "tldr_comment": "",
            "reader_summary": "",
            "final_summary": "",
            "main_topics": [],
            "consensus_points": [],
            "disputed_points": [],
            "strongest_arguments_for": [],
            "strongest_arguments_against": [],
            "tone_overview": "",
            "controversial_elements": [],
            "misinformation_or_uncertain_claims": [],
            "practical_takeaways": [],
            "worth_reading_original_comments": "",
            "error": str(e),
        }

    if not args.skip_tldr_pass:
        print(f"[{now_ts()}] Radim dodatni TL;DR pass...")
        tldr_prompt = build_tldr_comment_prompt(post, final_summary)
        try:
            tldr_response_text = call_ollama(
                prompt=tldr_prompt,
                model=args.model,
                ollama_url=args.ollama_url,
                temperature=args.temperature
            )
            tldr_json = extract_json_from_text(tldr_response_text)

            if tldr_json.get("tldr_comment"):
                final_summary["tldr_comment"] = tldr_json["tldr_comment"]
            if tldr_json.get("reader_summary"):
                final_summary["reader_summary"] = tldr_json["reader_summary"]

        except Exception as e:
            final_summary["_tldr_pass_error"] = str(e)

    final_summary["_meta"] = {
        "model": args.model,
        "post_id": post.get("post_id"),
        "title": post.get("title"),
        "generated_at": now_ts(),
        "chunk_count": len(chunks),
        "comment_count": len(comments),
        "post_num_comments": post.get("num_comments", 0),
    }

    save_json(post_dir / "final_summary.json", final_summary)

    md_report = build_markdown_report(post, final_summary, chunk_summaries)
    with (post_dir / "final_summary.md").open("w", encoding="utf-8") as f:
        f.write(md_report)

    print(f"[{now_ts()}] Gotovo.")
    print(f"Izlaz spremljen u: {post_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())