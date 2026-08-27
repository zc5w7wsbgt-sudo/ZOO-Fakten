#!/usr/bin/env python3
"""Publish approved Zoo Fakten posts through Meta's Instagram API."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

QUEUE_PATH = Path(os.getenv("QUEUE_PATH", "posts/queue.json"))
GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v26.0")
GRAPH_ROOT = f"https://graph.facebook.com/{GRAPH_VERSION}"
ENABLE_PUBLISHING = os.getenv("ENABLE_PUBLISHING", "false").lower() == "true"
MAX_CAPTION_LENGTH = 2200


class PublishError(RuntimeError):
    pass


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("scheduled_at braucht eine Zeitzone, z. B. +02:00")
    return parsed.astimezone(timezone.utc)


def api_post(path: str, data: dict[str, object], token: str) -> dict:
    body = urllib.parse.urlencode({**data, "access_token": token}).encode()
    request = urllib.request.Request(f"{GRAPH_ROOT}/{path}", data=body, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        try:
            message = json.loads(payload).get("error", {}).get("message", payload)
        except json.JSONDecodeError:
            message = payload
        raise PublishError(f"Meta API HTTP {exc.code}: {message}") from exc
    except urllib.error.URLError as exc:
        raise PublishError(f"Meta API nicht erreichbar: {exc.reason}") from exc


def api_get(path: str, params: dict[str, object], token: str) -> dict:
    query = urllib.parse.urlencode({**params, "access_token": token})
    request = urllib.request.Request(f"{GRAPH_ROOT}/{path}?{query}")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError) as exc:
        raise PublishError(f"Containerstatus konnte nicht gelesen werden: {exc}") from exc


def validate_post(post: dict) -> list[str]:
    errors: list[str] = []
    for field in ("id", "status", "scheduled_at", "caption", "media"):
        if field not in post:
            errors.append(f"Feld fehlt: {field}")
    caption = post.get("caption", "")
    if not isinstance(caption, str) or not caption.strip():
        errors.append("caption ist leer")
    elif len(caption) > MAX_CAPTION_LENGTH:
        errors.append(f"caption hat {len(caption)} statt maximal {MAX_CAPTION_LENGTH} Zeichen")
    media = post.get("media", [])
    if not isinstance(media, list) or not 1 <= len(media) <= 10:
        errors.append("media muss 1 bis 10 Elemente enthalten")
    else:
        for index, item in enumerate(media, 1):
            if item.get("type") not in {"IMAGE", "VIDEO"}:
                errors.append(f"media[{index}].type muss IMAGE oder VIDEO sein")
            url = item.get("url", "")
            if not isinstance(url, str) or not url.startswith("https://"):
                errors.append(f"media[{index}].url muss eine öffentliche HTTPS-Adresse sein")
    try:
        parse_time(post.get("scheduled_at", ""))
    except (TypeError, ValueError) as exc:
        errors.append(f"scheduled_at ungültig: {exc}")
    return errors


def wait_until_ready(container_id: str, token: str, attempts: int = 20) -> None:
    for _ in range(attempts):
        status = api_get(container_id, {"fields": "status_code,status"}, token)
        code = status.get("status_code")
        if code == "FINISHED":
            return
        if code in {"ERROR", "EXPIRED"}:
            raise PublishError(f"Mediencontainer meldet {code}: {status.get('status', '')}")
        time.sleep(3)
    raise PublishError("Mediencontainer wurde nicht rechtzeitig fertig")


def create_child(ig_user_id: str, item: dict, token: str) -> str:
    payload: dict[str, object] = {"is_carousel_item": "true"}
    if item["type"] == "VIDEO":
        payload.update({"media_type": "VIDEO", "video_url": item["url"]})
    else:
        payload["image_url"] = item["url"]
    result = api_post(f"{ig_user_id}/media", payload, token)
    container_id = result.get("id")
    if not container_id:
        raise PublishError("Meta lieferte keine Container-ID")
    wait_until_ready(container_id, token)
    return container_id


def publish(post: dict, ig_user_id: str, token: str) -> str:
    media = post["media"]
    if len(media) == 1:
        item = media[0]
        payload: dict[str, object] = {"caption": post["caption"]}
        if item["type"] == "VIDEO":
            payload.update({"media_type": "REELS", "video_url": item["url"]})
        else:
            payload["image_url"] = item["url"]
        result = api_post(f"{ig_user_id}/media", payload, token)
        container_id = result.get("id")
        if not container_id:
            raise PublishError("Meta lieferte keine Container-ID")
        wait_until_ready(container_id, token)
    else:
        children = [create_child(ig_user_id, item, token) for item in media]
        result = api_post(
            f"{ig_user_id}/media",
            {"media_type": "CAROUSEL", "children": ",".join(children), "caption": post["caption"]},
            token,
        )
        container_id = result.get("id")
        if not container_id:
            raise PublishError("Meta lieferte keine Karussell-Container-ID")
        wait_until_ready(container_id, token)
    published = api_post(f"{ig_user_id}/media_publish", {"creation_id": container_id}, token)
    media_id = published.get("id")
    if not media_id:
        raise PublishError("Meta bestätigte die Veröffentlichung nicht")
    return media_id


def main() -> int:
    queue = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    if not isinstance(queue, list):
        raise SystemExit("queue.json muss eine JSON-Liste sein")

    due: list[dict] = []
    validation_failed = False
    for post in queue:
        if post.get("status") != "approved":
            continue
        errors = validate_post(post)
        if errors:
            post["status"] = "error"
            post["error"] = "; ".join(errors)
            validation_failed = True
            continue
        if parse_time(post["scheduled_at"]) <= now_utc():
            due.append(post)

    if not ENABLE_PUBLISHING:
        print(f"Testmodus: {len(due)} freigegebene und fällige Beiträge gefunden; nichts veröffentlicht.")
        if validation_failed:
            QUEUE_PATH.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 0

    token = os.getenv("META_ACCESS_TOKEN", "")
    ig_user_id = os.getenv("INSTAGRAM_ACCOUNT_ID", "")
    if not token or not ig_user_id:
        raise SystemExit("META_ACCESS_TOKEN und INSTAGRAM_ACCOUNT_ID fehlen")

    for post in due:
        try:
            media_id = publish(post, ig_user_id, token)
            post.update({
                "status": "published",
                "instagram_media_id": media_id,
                "published_at": now_utc().isoformat(),
                "error": None,
            })
            print(f"Veröffentlicht: {post['id']} ({media_id})")
        except Exception as exc:  # keep the queue auditable even on API failures
            post.update({"status": "error", "error": str(exc), "failed_at": now_utc().isoformat()})
            print(f"Fehler bei {post.get('id')}: {exc}", file=sys.stderr)

    QUEUE_PATH.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
